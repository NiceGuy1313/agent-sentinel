"""Shared log parsing and Anthropic client helpers for Tool-sequence prediction."""

from __future__ import annotations

import datetime as dt
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

EXPERIMENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = EXPERIMENT_DIR.parents[1]
DEFAULT_RETRY3_DIR = REPO_ROOT / "tests/scripts/normal_direct_task_1_4_sandbox_20260903_retry3"
DEFAULT_MODEL = "claude-sonnet-4-5-20250929"


def read_json_lines(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open(encoding="utf-8") as handle:
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
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def first_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    return "\n".join(str(block.get("text", "")) for block in (content or []) if isinstance(block, dict) and block.get("type") == "text")


def discover_task_files(retry3_dir: Path, task_id: str) -> tuple[Path, Path]:
    number = task_id.removeprefix("direct")
    task_dirs = sorted(retry3_dir.glob(f"direct_task_inject{number}.json"))
    if len(task_dirs) != 1:
        raise RuntimeError(f"Expected one retry3 directory for {task_id}, got {task_dirs}")
    agent_logs = sorted(task_dirs[0].glob("*_agent_output.log"))
    sandbox_logs = sorted(task_dirs[0].glob("*_sandbox_output.log"))
    if len(agent_logs) != 1 or len(sandbox_logs) != 1:
        raise RuntimeError(f"Could not uniquely resolve logs under {task_dirs[0]}")
    return agent_logs[0], sandbox_logs[0]


def extract_actual_processes(sandbox_log: Path, first_tool_time: dt.datetime) -> list[dict[str, Any]]:
    events = []
    boundary = first_tool_time - dt.timedelta(seconds=1)
    for record in read_json_lines(sandbox_log):
        if record.get("message") != "process_event_record":
            continue
        data = record.get("data", {})
        stopped_exec = isinstance(data, dict) and int(data.get("flag", 0)) & 1 and data.get("type") == 3 and data.get("syscall") == 59
        if not stopped_exec or parse_time(record["time"]) < boundary:
            continue
        executable, arguments = data.get("executable_path", ""), data.get("args", [])
        if executable.endswith("/uname") and arguments == ["uname", "-p"]:
            continue
        events.append({"sequence": len(events) + 1, "timestamp": record["time"], "pid": data.get("ns_child_pid"), "parent_pid": data.get("ns_parent_tgid"), "executable": executable, "arguments": arguments, "syscall": data.get("syscall")})
    return events


def extract_actual_operations(sandbox_log: Path, first_tool_time: dt.datetime) -> list[dict[str, Any]]:
    """Extract AgentSentinel operation types while excluding Agent/auditor network noise."""
    records = read_json_lines(sandbox_log)
    boundary = first_tool_time - dt.timedelta(seconds=1)
    exec_pids = {
        data.get("ns_child_pid")
        for record in records
        if record.get("message") == "process_event_record"
        and isinstance((data := record.get("data", {})), dict)
        and int(data.get("flag", 0)) & 1
        and data.get("type") == 3
        and data.get("syscall") == 59
    }
    operations: list[dict[str, Any]] = []
    for raw_order, record in enumerate(records):
        if "time" not in record or parse_time(record["time"]) < boundary:
            continue
        message, data = record.get("message"), record.get("data", {})
        if not isinstance(data, dict):
            continue
        operation: dict[str, Any] | None = None
        if message == "process_event_record":
            if int(data.get("flag", 0)) & 1 and data.get("type") == 3 and data.get("syscall") == 59:
                executable, arguments = data.get("executable_path", ""), data.get("args", [])
                if executable.endswith("/uname") and arguments == ["uname", "-p"]:
                    continue
                operation = {"category": "process", "type": "exec", "executable": executable, "arguments": arguments, "actor_pid": data.get("ns_child_pid"), "parent_pid": data.get("ns_parent_tgid")}
            elif data.get("type") == 5:
                operation = {"category": "process", "type": "signal", "signal": data.get("signal", ""), "actor_pid": data.get("ns_parent_tgid"), "target_pid": data.get("target_ns_tgid")}
        elif message == "file_event_record" and int(data.get("flag", 0)) & 1 and data.get("ns_pid") in exec_pids:
            event_type, mode = data.get("type"), int(data.get("acc_mode", 0))
            if event_type == 1:
                operation_type = "delete"
            elif event_type == 2:
                operation_type = "rename"
            elif mode & 4 and mode & 2:
                operation_type = "read_write"
            elif mode & 2:
                operation_type = "write"
            else:
                operation_type = "read"
            operation = {"category": "file", "type": operation_type, "path": data.get("path", ""), "actor_pid": data.get("ns_pid")}
            if event_type == 2:
                operation["new_path"] = data.get("new_path", "")
        elif message == "sock_ops_event_record" and data.get("ns_pid") in exec_pids:
            # Socket accept-entry (type 3) explicitly does not stop in network.h.
            operation_type = {1: "message_send", 2: "message_listen", 4: "message_recv"}.get(data.get("type"))
            if operation_type:
                operation = {"category": "network", "type": operation_type, "remote_host": data.get("remote_addr", ""), "remote_port": data.get("remote_port"), "actor_pid": data.get("ns_pid")}
        if operation is not None:
            operation.update({"sequence": len(operations) + 1, "timestamp": record["time"], "raw_order": raw_order})
            operations.append(operation)
    return operations


def extract_initial_context(request: dict[str, Any]) -> dict[str, Any]:
    messages = request.get("messages") or []
    if not messages:
        raise RuntimeError("Initial Agent API request contains no messages")
    return {"model": request.get("model", DEFAULT_MODEL), "user_task": first_text(messages[0].get("content")), "agent_system_prompt": first_text(request.get("system")), "tools": request.get("tools") or []}


def load_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key:
        return key
    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if line.startswith("export "):
                line = line[len("export ") :]
            name, separator, value = line.partition("=")
            if separator and name.strip() == "ANTHROPIC_API_KEY":
                return value.strip().strip("'\"")
    raise RuntimeError("ANTHROPIC_API_KEY is not set in the environment or repository .env")


def extract_json_payload(raw_text: str) -> dict[str, Any]:
    start, end = raw_text.find("{"), raw_text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Predictor returned no JSON object")
    return json.loads(raw_text[start : end + 1])


class AnthropicPredictor:
    def __init__(self, *, api_key: str, model: str, system_prompt: str, max_tokens: int = 2048) -> None:
        self.api_key, self.model, self.system_prompt, self.max_tokens = api_key, model, system_prompt, max_tokens

    def predict(self, context: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        try:
            from .prompts import build_user_message
        except ImportError:
            from prompts import build_user_message
        payload = {"model": self.model, "max_tokens": self.max_tokens, "system": self.system_prompt, "messages": [{"role": "user", "content": build_user_message(context)}]}
        request = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(payload).encode(), headers={"content-type": "application/json", "x-api-key": self.api_key, "anthropic-version": "2023-06-01"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                raw_response = json.load(response)
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"Anthropic API HTTP {error.code}: {error.read().decode(errors='replace')}") from error
        text = "\n".join(block.get("text", "") for block in raw_response.get("content", []) if block.get("type") == "text")
        prediction = extract_json_payload(text)
        if not isinstance(prediction.get("predicted_operations"), list):
            raise ValueError("Prediction has no predicted_operations list")
        return prediction, raw_response, payload


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
