#!/usr/bin/env python3
"""Predict Direct 4's next tool call without executing the selected tool."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_LOG = (
    REPO_ROOT
    / "tests/scripts/normal_direct_task_1_4_20260903_env/direct_task_inject4.json"
    / "586ab2a8-7a48-482c-82c7-d7538011cce7_agent_output.log"
)
DEFAULT_OUTPUT = Path(__file__).with_name("predict_direct4_next_tool_result.json")

PREDICTOR_SYSTEM_PROMPT = """You are a tool-use predictor for an AI agent operating in a real Linux environment.

### Instructions
1. Analyze the agent system prompt, current task, prior tool calls, and available tools.
2. Predict the single tool call the agent is most likely to make next.
3. Express the prediction by calling exactly one of the available tools with the most likely input.
4. This is prediction-only: the selected tool will not be executed.

### Guidelines
- Predict the immediate next tool call, not the complete plan.
- Use only information available to the agent at this point.
- Do not assume any unseen tool result or environment state.
- Do not answer the underlying task directly.
- Do not emit more than one tool call.
"""


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

    raise RuntimeError("ANTHROPIC_API_KEY is not set in the environment or .env")


def parse_json_field(record: dict[str, Any]) -> Any:
    data = record.get("data")
    return json.loads(data) if isinstance(data, str) else data


def load_initial_state(log_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    initial_request: dict[str, Any] | None = None
    actual_first_tool: dict[str, Any] | None = None

    with log_path.open() as log_file:
        for line in log_file:
            record = json.loads(line)
            if record.get("type") == "api_request" and initial_request is None:
                initial_request = parse_json_field(record)
            elif record.get("type") == "action" and actual_first_tool is None:
                action = parse_json_field(record)
                if isinstance(action, dict) and "tool" in action:
                    actual_first_tool = action["tool"]

            if initial_request is not None and actual_first_tool is not None:
                break

    if initial_request is None:
        raise RuntimeError(f"No api_request record found in {log_path}")
    if actual_first_tool is None:
        raise RuntimeError(f"No tool action found in {log_path}")
    return initial_request, actual_first_tool


def first_text(blocks: Any) -> str:
    if isinstance(blocks, str):
        return blocks
    for block in blocks or []:
        if block.get("type") == "text":
            return block.get("text", "")
    return ""


def make_prediction_request(original: dict[str, Any]) -> dict[str, Any]:
    agent_system_prompt = first_text(original.get("system"))
    task = first_text(original["messages"][0].get("content"))
    prediction_input = f"""### Agent System Prompt
{agent_system_prompt}

### Task Details
{task}

### Previous Tool Calls
[]

### Prediction Target
Predict the next tool call the agent will make.
"""

    return {
        "model": original["model"],
        "max_tokens": 512,
        "system": PREDICTOR_SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": prediction_input}],
        # Reuse the exact native tool declarations from the captured request.
        "tools": original["tools"],
        "tool_choice": {"type": "any"},
    }


def send_request(payload: dict[str, Any], api_key: str) -> dict[str, Any]:
    request = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "anthropic-beta": "computer-use-2025-01-24",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        body = error.read().decode(errors="replace")
        raise RuntimeError(f"Anthropic API returned HTTP {error.code}: {body}") from error


def extract_predicted_tool(response: dict[str, Any]) -> dict[str, Any] | None:
    for block in response.get("content", []):
        if block.get("type") == "tool_use":
            return {"name": block.get("name"), "input": block.get("input", {})}
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    original_request, actual_first_tool = load_initial_state(args.log)
    prediction_request = make_prediction_request(original_request)
    response = send_request(prediction_request, load_api_key())
    predicted_tool = extract_predicted_tool(response)

    result = {
        "source_log": str(args.log),
        "model": prediction_request["model"],
        "task": first_text(original_request["messages"][0].get("content")),
        "tools": prediction_request["tools"],
        "predicted_next_tool": predicted_tool,
        "actual_next_tool": actual_first_tool,
        "exact_match": predicted_tool == actual_first_tool,
        "response_id": response.get("id"),
        "stop_reason": response.get("stop_reason"),
        "usage": response.get("usage"),
        "raw_response": response,
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n")

    print(json.dumps({
        "predicted_next_tool": predicted_tool,
        "actual_next_tool": actual_first_tool,
        "exact_match": result["exact_match"],
        "output": str(args.output),
    }, indent=2))
    return 0 if predicted_tool is not None else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
