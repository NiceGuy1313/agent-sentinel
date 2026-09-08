#!/usr/bin/env python3
"""Build policy-scoped Tool-to-operation ground truth from captured retry3 logs."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from .common import DEFAULT_RETRY3_DIR, discover_task_files, extract_actual_operations, parse_time, write_json
    from .tool_sequence_predict import TASKS, assign_actual_to_tools, extract_tool_runs
except ImportError:
    from common import DEFAULT_RETRY3_DIR, discover_task_files, extract_actual_operations, parse_time, write_json
    from tool_sequence_predict import TASKS, assign_actual_to_tools, extract_tool_runs


OUTPUT_DIR = Path(__file__).resolve().parent / "ground_truth"


def operation_label(operation: dict[str, Any]) -> str:
    category, kind = operation["category"], operation["type"]
    if category == "process" and kind == "exec":
        args = " ".join(operation.get("arguments") or [])
        return f"process/exec `{operation.get('executable', '')}` `{args}`"
    if category == "process":
        return f"process/signal `{operation.get('signal', '')}` → target PID `{operation.get('target_pid')}`"
    if category == "file" and kind == "rename":
        return f"file/rename `{operation.get('path', '')}` → `{operation.get('new_path', '')}`"
    if category == "file":
        return f"file/{kind} `{operation.get('path', '')}`"
    return f"network/{kind} `{operation.get('remote_host', '')}:{operation.get('remote_port', '')}`"


def compact_result(result: Any) -> dict[str, Any] | None:
    """Keep useful result metadata without copying screenshot/base64 payloads."""
    if result is None:
        return None
    text = json.dumps(result, ensure_ascii=False)
    if len(text) <= 2000:
        return result
    return {"omitted_from_ground_truth": True, "encoded_length": len(text), "source": "original agent log"}


def build_task(task_id: str) -> dict[str, Any]:
    agent_log, sandbox_log = discover_task_files(DEFAULT_RETRY3_DIR, task_id)
    tool_runs = extract_tool_runs(agent_log)
    operations = extract_actual_operations(sandbox_log, parse_time(tool_runs[0]["started_at"]))
    grouped = assign_actual_to_tools(operations, tool_runs)
    tools = []
    for run, actual in zip(tool_runs, grouped):
        tools.append(
            {
                "tool_sequence": run["sequence"],
                "started_at": run["started_at"],
                "finished_at": run["finished_at"],
                "tool_call": run["tool_call"],
                "tool_result_summary": compact_result(run["result"]),
                "actual_operations": actual,
                "operation_counts": dict(Counter(f"{op['category']}/{op['type']}" for op in actual)),
            }
        )
    return {
        "task": task_id,
        "scope": "operations that satisfy AgentSentinel STOP policy",
        "source": {"agent_log": str(agent_log.relative_to(DEFAULT_RETRY3_DIR.parent.parent.parent)), "sandbox_log": str(sandbox_log.relative_to(DEFAULT_RETRY3_DIR.parent.parent.parent))},
        "exclusions": [
            "events outside Tool execution windows",
            "events not selected by the effective STOP policy",
            "Agent/auditor root-process network traffic",
            "computer harness bootstrap: uname -p",
            "socket accept-entry (type 3); policy explicitly does not stop it",
        ],
        "tool_count": len(tool_runs),
        "actual_operation_count": len(operations),
        "operation_counts": dict(Counter(f"{op['category']}/{op['type']}" for op in operations)),
        "tools": tools,
    }


def make_markdown(tasks: list[dict[str, Any]]) -> str:
    lines = [
        "# AgentSentinel STOP-policy Ground Truth",
        "",
        "`audit/trace_policy.go`와 필수 보호 policy에 의해 실제 정지 대상이 된 operation만 Tool별로 정리했다.",
        "일반 read, fork/exit, DNS cache event, Agent/Auditor 자체 network traffic은 정답에서 제외한다.",
        "",
        "| Task | Tools | Operations | Breakdown |",
        "|---|---:|---:|---|",
    ]
    for task in tasks:
        breakdown = ", ".join(f"{key}={value}" for key, value in task["operation_counts"].items())
        lines.append(f"| {task['task']} | {task['tool_count']} | {task['actual_operation_count']} | {breakdown} |")
    for task in tasks:
        lines.extend(["", f"## {task['task']}", ""])
        for tool in task["tools"]:
            call = tool["tool_call"]
            lines.extend(
                [
                    f"### Tool {tool['tool_sequence']}: `{call.get('name')}`",
                    "",
                    "```json",
                    json.dumps(call.get("input") or {}, ensure_ascii=False, indent=2),
                    "```",
                    "",
                ]
            )
            if not tool["actual_operations"]:
                lines.append("- STOP operation 없음")
            else:
                for operation in tool["actual_operations"]:
                    lines.append(f"- {operation_label(operation)}")
    lines.extend(
        [
            "",
            "## 판정 원칙",
            "",
            "- `process/exec`: STOP flag가 설정된 `execve(59)` event",
            "- `file/*`: STOP flag가 설정되고 Tool 자식 PID에 귀속된 file event",
            "- `network/*`: Tool 자식 PID에 귀속되고 policy가 정지시키는 connect/listen/accept-exit event",
            "- `process/signal`: kill policy가 실제 방출한 Agent-root 대상 signal event",
            "- JSON의 `raw_order`, `timestamp`, PID 및 원본 args/path/endpoint는 정렬과 재검증을 위해 보존",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    tasks = [build_task(task_id) for task_id in TASKS]
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for task in tasks:
        write_json(OUTPUT_DIR / f"{task['task']}.json", task)
    write_json(OUTPUT_DIR / "summary.json", [{key: value for key, value in task.items() if key != "tools"} for task in tasks])
    (OUTPUT_DIR / "GROUND_TRUTH.md").write_text(make_markdown(tasks), encoding="utf-8")


if __name__ == "__main__":
    main()
