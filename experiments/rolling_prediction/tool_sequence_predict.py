#!/usr/bin/env python3
"""Predict and evaluate a complete AgentSentinel operation sequence per tool call."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

try:
    from .matcher import POLICIES, operations_match
    from .prompts import (
        TOOL_SEQUENCE_SYSTEM_PROMPT,
        build_reprediction_context,
        build_tool_prediction_context,
    )
    from .common import (
        DEFAULT_MODEL,
        DEFAULT_RETRY3_DIR,
        AnthropicPredictor,
        discover_task_files,
        extract_actual_operations,
        extract_initial_context,
        load_api_key,
        parse_embedded_json,
        parse_time,
        read_json_lines,
        write_json,
    )
except ImportError:  # Support direct execution by file path.
    from matcher import POLICIES, operations_match
    from prompts import TOOL_SEQUENCE_SYSTEM_PROMPT, build_reprediction_context, build_tool_prediction_context
    from common import (
        DEFAULT_MODEL,
        DEFAULT_RETRY3_DIR,
        AnthropicPredictor,
        discover_task_files,
        extract_actual_operations,
        extract_initial_context,
        load_api_key,
        parse_embedded_json,
        parse_time,
        read_json_lines,
        write_json,
    )


EXPERIMENT_DIR = Path(__file__).resolve().parent
DEFAULT_RESULTS_DIR = EXPERIMENT_DIR / "results_tool_sequence"
TASKS = ("direct1", "direct2", "direct3", "direct4")


def extract_tool_runs(agent_log: Path) -> list[dict[str, Any]]:
    """Extract concrete tool calls and their results without exposing future calls."""
    runs: list[dict[str, Any]] = []
    pending: dict[str, Any] | None = None
    for record in read_json_lines(agent_log):
        kind = record.get("type")
        if kind == "action":
            action = parse_embedded_json(record.get("data"))
            tool = action.get("tool") if isinstance(action, dict) else None
            if isinstance(tool, dict):
                if pending is not None:
                    runs.append(pending)
                pending = {
                    "sequence": len(runs) + 1,
                    "started_at": record["time"],
                    "tool_call": {
                        "name": tool.get("name"),
                        "input": tool.get("input") or {},
                    },
                    "result": None,
                    "finished_at": None,
                }
        elif kind == "tool_use_result" and pending is not None:
            pending["result"] = parse_embedded_json(record.get("data"))
            pending["finished_at"] = record["time"]
            runs.append(pending)
            pending = None
    if pending is not None:
        runs.append(pending)
    return runs


def assign_actual_to_tools(
    actual: list[dict[str, Any]], tool_runs: list[dict[str, Any]]
) -> list[list[dict[str, Any]]]:
    """Assign STOP events to the most recent tool start, bounded by the next start."""
    assigned: list[list[dict[str, Any]]] = [[] for _ in tool_runs]
    starts = [parse_time(run["started_at"]) - dt.timedelta(seconds=1) for run in tool_runs]
    for event in actual:
        event_time = parse_time(event["timestamp"])
        owner: int | None = None
        for index, start in enumerate(starts):
            if event_time >= start:
                owner = index
            else:
                break
        if owner is not None:
            assigned[owner].append(event)
    return assigned


def align_sequences(
    predicted: list[dict[str, Any]], actual: list[dict[str, Any]], policy: str
) -> list[dict[str, Any]]:
    """LCS-align predictions and observations using the selected exact matcher."""
    rows, cols = len(predicted), len(actual)
    dp = [[0] * (cols + 1) for _ in range(rows + 1)]
    for i in range(rows - 1, -1, -1):
        for j in range(cols - 1, -1, -1):
            if operations_match(predicted[i], actual[j], policy):
                dp[i][j] = 1 + dp[i + 1][j + 1]
            else:
                dp[i][j] = max(dp[i + 1][j], dp[i][j + 1])

    alignment: list[dict[str, Any]] = []
    i = j = 0
    while i < rows or j < cols:
        if i < rows and j < cols and operations_match(predicted[i], actual[j], policy):
            alignment.append({"status": "match", "predicted": predicted[i], "actual": actual[j]})
            i += 1
            j += 1
        elif i < rows and (j == cols or dp[i + 1][j] >= dp[i][j + 1]):
            alignment.append({"status": "predicted_only", "predicted": predicted[i], "actual": None})
            i += 1
        else:
            alignment.append({"status": "actual_only", "predicted": None, "actual": actual[j]})
            j += 1
    return alignment


def completed_history(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "sequence": run["sequence"],
        "tool_call": run["tool_call"],
        "tool_result": run["result"],
    }


def run_task(
    *,
    task_id: str,
    retry3_dir: Path,
    result_dir: Path,
    predictor: AnthropicPredictor,
    policy: str,
) -> dict[str, Any]:
    agent_log, sandbox_log = discover_task_files(retry3_dir, task_id)
    records = read_json_lines(agent_log)
    initial_request_record = next(record for record in records if record.get("type") == "api_request")
    initial = extract_initial_context(parse_embedded_json(initial_request_record["data"]))
    tool_runs = extract_tool_runs(agent_log)
    if not tool_runs:
        raise RuntimeError(f"{task_id}: no tool calls found")
    actual = extract_actual_operations(sandbox_log, parse_time(tool_runs[0]["started_at"]))
    actual_by_tool = assign_actual_to_tools(actual, tool_runs)

    total_matches = total_mismatches = total_invalidated = total_predicted_only = 0
    total_reprediction_queries = 0
    for run, tool_actual in zip(tool_runs, actual_by_tool):
        context = build_tool_prediction_context(
            user_task=initial["user_task"],
            current_tool_call=run["tool_call"],
        )
        prediction, raw_response, api_payload = predictor.predict(context)
        expected = prediction["predicted_operations"]
        queries = [
            {
                "query_number": 1,
                "mode": "initial",
                "context": context,
                "prediction": prediction,
                "api_payload": api_payload,
                "response_id": raw_response.get("id"),
                "model": raw_response.get("model"),
                "usage": raw_response.get("usage"),
            }
        ]
        observed: list[dict[str, Any]] = []
        replay: list[dict[str, Any]] = []
        matches = mismatches = invalidated = 0
        for actual_operation in tool_actual:
            predicted_operation = expected[0] if expected else None
            matched = operations_match(predicted_operation, actual_operation, policy)
            row = {
                "actual_operation": actual_operation,
                "predicted_before_event": predicted_operation,
                "result": "pass" if matched else "stop_mismatch",
                "re_prediction_query_number": None,
            }
            observed.append(actual_operation)
            if matched:
                expected.pop(0)
                matches += 1
            else:
                mismatches += 1
                invalidated += len(expected)
                previous_remaining = expected
                re_context = build_reprediction_context(
                    user_task=initial["user_task"],
                    current_tool_call=run["tool_call"],
                    previous_prediction=previous_remaining,
                    observed_operation_history=observed,
                    current_mismatch_operation=actual_operation,
                )
                re_prediction, re_raw, re_payload = predictor.predict(re_context)
                expected = re_prediction["predicted_operations"]
                total_reprediction_queries += 1
                query_number = len(queries) + 1
                row["re_prediction_query_number"] = query_number
                queries.append(
                    {
                        "query_number": query_number,
                        "mode": "re_prediction",
                        "context": re_context,
                        "prediction": re_prediction,
                        "api_payload": re_payload,
                        "response_id": re_raw.get("id"),
                        "model": re_raw.get("model"),
                        "usage": re_raw.get("usage"),
                    }
                )
            replay.append(row)
        predicted_only = len(expected)
        total_matches += matches
        total_mismatches += mismatches
        total_invalidated += invalidated
        total_predicted_only += predicted_only
        record = {
            "tool_sequence": run["sequence"],
            "tool_call": run["tool_call"],
            "actual_operations": tool_actual,
            "queries": queries,
            "replay": replay,
            "metrics": {
                "actual_count": len(tool_actual),
                "pre_event_pass_count": matches,
                "stop_mismatch_count": mismatches,
                "re_prediction_queries": len(queries) - 1,
                "invalidated_prediction_count": invalidated,
                "remaining_predicted_only_count": predicted_only,
            },
        }
        write_json(result_dir / f"tool_{run['sequence']:03d}.json", record)

    total_queries = len(tool_runs) + total_reprediction_queries
    summary = {
        "task": task_id,
        "matching_policy": policy,
        "initial_tool_prediction_queries": len(tool_runs),
        "re_prediction_queries": total_reprediction_queries,
        "total_prediction_queries": total_queries,
        "actual_operation_count": len(actual),
        "pre_event_pass_count": total_matches,
        "stop_mismatch_count": total_mismatches,
        "invalidated_prediction_count": total_invalidated,
        "remaining_predicted_only_count": total_predicted_only,
        "pre_event_operation_recall": total_matches / len(actual) if actual else 1.0,
        "query_reduction_relative_to_operation_events": 1 - total_queries / len(actual) if actual else 0.0,
    }
    write_json(result_dir / "summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", choices=[*TASKS, "all"])
    parser.add_argument("--policy", choices=POLICIES, default="executable_args")
    parser.add_argument("--retry3-dir", type=Path, default=DEFAULT_RETRY3_DIR)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-tokens", type=int, default=2048)
    args = parser.parse_args()

    predictor = AnthropicPredictor(
        api_key=load_api_key(),
        model=args.model,
        max_tokens=args.max_tokens,
        system_prompt=TOOL_SEQUENCE_SYSTEM_PROMPT,
    )
    tasks = TASKS if args.target == "all" else (args.target,)
    summaries = []
    for task_id in tasks:
        print(f"[+] {task_id}: predicting complete AgentSentinel operations per tool call", flush=True)
        summary = run_task(
            task_id=task_id,
            retry3_dir=args.retry3_dir,
            result_dir=args.results_dir / task_id / args.policy,
            predictor=predictor,
            policy=args.policy,
        )
        summaries.append(summary)
        print(json.dumps(summary, ensure_ascii=False), flush=True)
    write_json(args.results_dir / "summary.json", summaries)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
