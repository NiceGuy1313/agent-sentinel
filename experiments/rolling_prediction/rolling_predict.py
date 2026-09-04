#!/usr/bin/env python3
"""Offline rolling-prediction replay over retry3 Process Exec STOP events."""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

try:
    from .matcher import POLICIES, processes_match
    from .prompts import PREDICTOR_SYSTEM_PROMPT, build_prediction_context, build_user_message
except ImportError:  # Support direct execution by file path.
    from matcher import POLICIES, processes_match
    from prompts import PREDICTOR_SYSTEM_PROMPT, build_prediction_context, build_user_message


EXPERIMENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = EXPERIMENT_DIR.parents[1]
DEFAULT_RETRY3_DIR = (
    REPO_ROOT / "tests/scripts/normal_direct_task_1_4_sandbox_20260903_retry3"
)
DEFAULT_RESULTS_DIR = EXPERIMENT_DIR / "results"
EXPECTED_STOP_COUNTS = {"direct1": 18, "direct2": 4, "direct3": 11, "direct4": 7}
DEFAULT_MODEL = "claude-sonnet-4-5-20250929"


def read_json_lines(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open() as handle:
        for line_number, line in enumerate(handle, 1):
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}") from error
    return records


def parse_embedded_json(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


def parse_time(value: str) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    # Agent logs omit the timezone while sandbox logs use Z. Both clocks in
    # retry3 are UTC, so normalize them to comparable aware datetimes.
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def first_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    return "\n".join(
        str(block.get("text", ""))
        for block in (content or [])
        if isinstance(block, dict) and block.get("type") == "text"
    )


def discover_task_files(retry3_dir: Path, task_id: str) -> tuple[Path, Path]:
    task_number = task_id.removeprefix("direct")
    task_dirs = sorted(retry3_dir.glob(f"direct_task_inject{task_number}.json"))
    if len(task_dirs) != 1:
        raise RuntimeError(f"Expected one retry3 directory for {task_id}, got {task_dirs}")
    agent_logs = sorted(task_dirs[0].glob("*_agent_output.log"))
    sandbox_logs = sorted(task_dirs[0].glob("*_sandbox_output.log"))
    if len(agent_logs) != 1 or len(sandbox_logs) != 1:
        raise RuntimeError(f"Could not uniquely resolve logs under {task_dirs[0]}")
    return agent_logs[0], sandbox_logs[0]


def load_agent_initial_state(agent_log: Path) -> tuple[dict[str, Any], dt.datetime]:
    initial_request: dict[str, Any] | None = None
    first_tool_time: dt.datetime | None = None
    for record in read_json_lines(agent_log):
        if record.get("type") == "api_request" and initial_request is None:
            initial_request = parse_embedded_json(record.get("data"))
        if record.get("type") == "action" and first_tool_time is None:
            action = parse_embedded_json(record.get("data"))
            if isinstance(action, dict) and "tool" in action:
                first_tool_time = parse_time(record["time"])
        if initial_request is not None and first_tool_time is not None:
            break
    if initial_request is None or first_tool_time is None:
        raise RuntimeError(f"Missing initial request or first tool action in {agent_log}")
    return initial_request, first_tool_time


def extract_actual_processes(sandbox_log: Path, first_tool_time: dt.datetime) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    # Sandbox timestamps have one-second precision, while Agent action logs
    # include microseconds. Allow the event in the same displayed second.
    tool_boundary = first_tool_time - dt.timedelta(seconds=1)
    for record in read_json_lines(sandbox_log):
        if record.get("message") != "process_event_record":
            continue
        data = record.get("data", {})
        if not isinstance(data, dict):
            continue
        is_stopped_exec = (
            int(data.get("flag", 0)) & 1
            and data.get("type") == 3
            and data.get("syscall") == 59
        )
        if not is_stopped_exec or parse_time(record["time"]) < tool_boundary:
            continue
        executable = data.get("executable_path", "")
        if executable.endswith("/uname"):
            continue
        events.append(
            {
                "sequence": len(events) + 1,
                "timestamp": record["time"],
                "pid": data.get("ns_child_pid"),
                "parent_pid": data.get("ns_parent_tgid"),
                "executable": executable,
                "arguments": data.get("args", []),
                "syscall": data.get("syscall"),
            }
        )
    return events


def extract_initial_context(request: dict[str, Any]) -> dict[str, Any]:
    system = first_text(request.get("system"))
    messages = request.get("messages") or []
    if not messages:
        raise RuntimeError("Initial Agent API request contains no messages")
    return {
        "model": request.get("model", DEFAULT_MODEL),
        "user_task": first_text(messages[0].get("content")),
        "agent_system_prompt": system,
        "tools": request.get("tools") or [],
    }


def load_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key:
        return key
    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        for raw_line in env_path.read_text().splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export ") :]
            name, separator, value = line.partition("=")
            if separator and name.strip() == "ANTHROPIC_API_KEY":
                return value.strip().strip("'\"")
    raise RuntimeError("ANTHROPIC_API_KEY is not set in the environment or repository .env")


def extract_json_payload(raw_text: str) -> dict[str, Any]:
    cleaned = raw_text.strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Predictor returned no JSON object")
    return json.loads(cleaned[start : end + 1])


class AnthropicPredictor:
    def __init__(self, *, api_key: str, model: str, max_tokens: int = 1536) -> None:
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens

    def predict(self, context: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": PREDICTOR_SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": build_user_message(context)}],
        }
        request = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(payload).encode(),
            headers={
                "content-type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                raw_response = json.load(response)
        except urllib.error.HTTPError as error:
            body = error.read().decode(errors="replace")
            raise RuntimeError(f"Anthropic API HTTP {error.code}: {body}") from error

        text = "\n".join(
            block.get("text", "")
            for block in raw_response.get("content", [])
            if block.get("type") == "text"
        )
        prediction = extract_json_payload(text)
        processes = prediction.get("predicted_processes")
        if not isinstance(processes, list):
            raise ValueError("Prediction has no predicted_processes list")
        return prediction, raw_response, payload


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def public_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "sequence": event["sequence"],
        "executable": event["executable"],
        "arguments": event["arguments"],
    }


def issue_query(
    *,
    predictor: AnthropicPredictor,
    task_id: str,
    initial: dict[str, Any],
    observed: list[dict[str, Any]],
    current: dict[str, Any] | None,
    query_number: int,
    result_dir: Path,
) -> list[dict[str, Any]]:
    context = build_prediction_context(
        task_id=task_id,
        user_task=initial["user_task"],
        agent_system_prompt=initial["agent_system_prompt"],
        tools=initial["tools"],
        observed_history=[public_event(event) for event in observed],
        current_mismatch_event=public_event(current) if current else None,
    )
    prediction, raw_response, api_payload = predictor.predict(context)
    input_record = {
        "query_number": query_number,
        "context": context,
        "api_payload": api_payload,
        "future_trace_included": False,
    }
    output_record = {
        "query_number": query_number,
        "prediction": prediction,
        "response_id": raw_response.get("id"),
        "model": raw_response.get("model"),
        "usage": raw_response.get("usage"),
        "stop_reason": raw_response.get("stop_reason"),
        "raw_response": raw_response,
    }
    write_json(result_dir / f"query_{query_number:03d}_input.json", input_record)
    write_json(result_dir / f"query_{query_number:03d}_prediction.json", output_record)
    return prediction["predicted_processes"]


def save_shared_initial_query(
    *,
    predictor: AnthropicPredictor,
    task_id: str,
    initial: dict[str, Any],
    result_dirs: list[Path],
) -> list[dict[str, Any]]:
    context = build_prediction_context(
        task_id=task_id,
        user_task=initial["user_task"],
        agent_system_prompt=initial["agent_system_prompt"],
        tools=initial["tools"],
        observed_history=[],
        current_mismatch_event=None,
    )
    prediction, raw_response, api_payload = predictor.predict(context)
    input_record = {
        "query_number": 1,
        "context": context,
        "api_payload": api_payload,
        "future_trace_included": False,
        "shared_between_matching_policies": True,
    }
    output_record = {
        "query_number": 1,
        "prediction": prediction,
        "response_id": raw_response.get("id"),
        "model": raw_response.get("model"),
        "usage": raw_response.get("usage"),
        "stop_reason": raw_response.get("stop_reason"),
        "raw_response": raw_response,
        "shared_between_matching_policies": True,
    }
    for result_dir in result_dirs:
        write_json(result_dir / "query_001_input.json", input_record)
        write_json(result_dir / "query_001_prediction.json", output_record)
    return prediction["predicted_processes"]


def replay_policy(
    *,
    task_id: str,
    policy: str,
    actual: list[dict[str, Any]],
    initial: dict[str, Any],
    initial_prediction: list[dict[str, Any]],
    predictor: AnthropicPredictor,
    result_dir: Path,
) -> dict[str, Any]:
    expected = copy.deepcopy(initial_prediction)
    observed: list[dict[str, Any]] = []
    replay: list[dict[str, Any]] = []
    query_number = 1
    reprediction_queries = 0
    matched = 0
    fallbacks = 0

    for event in actual:
        first_expected = expected[0] if expected else None
        first_match = processes_match(first_expected, event, policy)
        row: dict[str, Any] = {
            "actual_event": event,
            "expected_prediction_before_event": first_expected,
            "initial_comparison": "match" if first_match else "mismatch",
            "prediction_query_number": query_number,
            "re_prediction_query_number": None,
            "expected_after_re_prediction": None,
            "final_match": first_match,
            "fallback": False,
        }

        if first_match:
            expected.pop(0)
            matched += 1
            observed.append(event)
            replay.append(row)
            continue

        # At runtime this process is now the current stopped event, so it is
        # observable. No event after it is exposed to the predictor.
        observed.append(event)
        query_number += 1
        reprediction_queries += 1
        expected = issue_query(
            predictor=predictor,
            task_id=task_id,
            initial=initial,
            observed=observed,
            current=event,
            query_number=query_number,
            result_dir=result_dir,
        )
        retry_expected = expected[0] if expected else None
        retry_match = processes_match(retry_expected, event, policy)
        row["re_prediction_query_number"] = query_number
        row["expected_after_re_prediction"] = retry_expected
        row["final_match"] = retry_match
        if retry_match:
            expected.pop(0)
            matched += 1
        else:
            row["fallback"] = True
            fallbacks += 1
        replay.append(row)

    summary = {
        "task": task_id,
        "matching_policy": policy,
        "actual_stop_process_exec_count": len(actual),
        "initial_prediction_queries": 1,
        "re_prediction_queries": reprediction_queries,
        "total_prediction_llm_queries": 1 + reprediction_queries,
        "prediction_matched_events": matched,
        "fallback_events": fallbacks,
        "query_reduction_relative_to_stop_count": 1 - ((1 + reprediction_queries) / len(actual)),
    }
    write_json(result_dir / "actual_processes.json", actual)
    write_json(result_dir / "replay.json", replay)
    write_json(result_dir / "summary.json", summary)
    return summary


def make_summary_markdown(summaries: list[dict[str, Any]]) -> str:
    lines = [
        "# Rolling Prediction 결과",
        "",
        "| Policy | Task | Existing STOPs | Initial Queries | Re-Prediction Queries | Total Prediction Queries | Matched Exec Events | Fallbacks | Reduction |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for policy in POLICIES:
        selected = [item for item in summaries if item["matching_policy"] == policy]
        for item in selected:
            lines.append(
                f"| `{policy}` | {item['task'].title()} | {item['actual_stop_process_exec_count']} "
                f"| {item['initial_prediction_queries']} | {item['re_prediction_queries']} "
                f"| {item['total_prediction_llm_queries']} | {item['prediction_matched_events']} "
                f"| {item['fallback_events']} | {item['query_reduction_relative_to_stop_count']:.1%} |"
            )
        if selected:
            stops = sum(item["actual_stop_process_exec_count"] for item in selected)
            initial_queries = sum(item["initial_prediction_queries"] for item in selected)
            repredictions = sum(item["re_prediction_queries"] for item in selected)
            queries = sum(item["total_prediction_llm_queries"] for item in selected)
            matches = sum(item["prediction_matched_events"] for item in selected)
            fallbacks = sum(item["fallback_events"] for item in selected)
            lines.append(
                f"| `{policy}` | **Total** | **{stops}** | **{initial_queries}** "
                f"| **{repredictions}** | **{queries}** | **{matches}** | **{fallbacks}** "
                f"| **{1 - queries / stops:.1%}** |"
            )
    lines.extend(
        [
            "",
            "> Reduction = `1 - (Total Prediction Queries / Existing STOPs)`. ",
            "> 이 값은 audit latency 또는 security improvement를 의미하지 않는다.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", choices=[*EXPECTED_STOP_COUNTS, "all"])
    parser.add_argument("--policy", choices=[*POLICIES, "both"], default="both")
    parser.add_argument("--retry3-dir", type=Path, default=DEFAULT_RETRY3_DIR)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-tokens", type=int, default=1536)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse policy summaries already present under the results directory",
    )
    args = parser.parse_args()

    tasks = list(EXPECTED_STOP_COUNTS) if args.target == "all" else [args.target]
    policies = list(POLICIES) if args.policy == "both" else [args.policy]
    predictor = AnthropicPredictor(
        api_key=load_api_key(), model=args.model, max_tokens=args.max_tokens
    )
    summaries: list[dict[str, Any]] = []

    for task_id in tasks:
        pending_policies: list[str] = []
        for policy in policies:
            summary_path = args.results_dir / task_id / policy / "summary.json"
            if args.resume and summary_path.exists():
                summary = json.loads(summary_path.read_text())
                summaries.append(summary)
                print(f"[=] {task_id}: reusing completed {policy}", flush=True)
            else:
                pending_policies.append(policy)
        if not pending_policies:
            continue

        agent_log, sandbox_log = discover_task_files(args.retry3_dir, task_id)
        initial_request, first_tool_time = load_agent_initial_state(agent_log)
        initial = extract_initial_context(initial_request)
        actual = extract_actual_processes(sandbox_log, first_tool_time)
        expected_count = EXPECTED_STOP_COUNTS[task_id]
        if len(actual) != expected_count:
            raise RuntimeError(
                f"{task_id}: extracted {len(actual)} STOP events, expected {expected_count}"
            )

        result_dirs = [args.results_dir / task_id / policy for policy in pending_policies]
        print(
            f"[+] {task_id}: initial prediction (shared by {len(pending_policies)} policies)",
            flush=True,
        )
        initial_prediction = save_shared_initial_query(
            predictor=predictor,
            task_id=task_id,
            initial=initial,
            result_dirs=result_dirs,
        )
        for policy, result_dir in zip(pending_policies, result_dirs):
            print(f"[+] {task_id}: replaying {policy}", flush=True)
            summary = replay_policy(
                task_id=task_id,
                policy=policy,
                actual=actual,
                initial=initial,
                initial_prediction=initial_prediction,
                predictor=predictor,
                result_dir=result_dir,
            )
            summaries.append(summary)
            print(json.dumps(summary, ensure_ascii=False), flush=True)

    write_json(args.results_dir / "summary.json", summaries)
    (args.results_dir / "SUMMARY.md").write_text(make_summary_markdown(summaries))
    print(f"[+] Saved aggregate results to {args.results_dir}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
