"""Matching and conservative normalization for predicted process executions."""

from __future__ import annotations

import os
import re
from typing import Any, Iterable


POLICY_EXECUTABLE_ONLY = "executable_only"
POLICY_EXECUTABLE_ARGS = "executable_args"
POLICIES = (POLICY_EXECUTABLE_ONLY, POLICY_EXECUTABLE_ARGS)

_SCREENSHOT_RE = re.compile(r"/tmp/outputs/screenshot_[0-9a-fA-F-]+\.png")
_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_SPACE_RE = re.compile(r"\s+")


def normalize_executable(value: str) -> str:
    value = os.path.normpath(str(value).strip())
    # Ubuntu images commonly use usrmerge. Treat these spellings as equivalent.
    if value.startswith("/bin/"):
        value = "/usr/bin/" + value[len("/bin/") :]
    if value.startswith("/sbin/"):
        value = "/usr/sbin/" + value[len("/sbin/") :]
    return value


def _normalize_argument(value: Any) -> str:
    text = str(value).strip()
    text = _SCREENSHOT_RE.sub("<SCREENSHOT_PATH>", text)
    text = _UUID_RE.sub("<UUID>", text)
    return _SPACE_RE.sub(" ", text)


def normalize_arguments(executable: str, arguments: Iterable[Any] | None) -> list[str]:
    result = [_normalize_argument(arg) for arg in (arguments or [])]
    executable_name = os.path.basename(normalize_executable(executable))

    # Actual exec traces contain argv[0], while the predictor schema asks for
    # arguments without it. Remove it on either side when present.
    if result:
        arg0_name = os.path.basename(normalize_executable(result[0]))
        if arg0_name == executable_name:
            result = result[1:]
    return result


def normalized_event(event: dict[str, Any]) -> dict[str, Any]:
    executable = normalize_executable(event.get("executable", ""))
    arguments = event.get("arguments", event.get("likely_arguments", []))
    return {
        "executable": executable,
        "arguments": normalize_arguments(executable, arguments),
    }


def processes_match(
    predicted: dict[str, Any] | None,
    actual: dict[str, Any],
    policy: str,
) -> bool:
    if predicted is None:
        return False
    if policy not in POLICIES:
        raise ValueError(f"Unknown matching policy: {policy}")

    pred = normalized_event(predicted)
    observed = normalized_event(actual)
    if pred["executable"] != observed["executable"]:
        return False
    if policy == POLICY_EXECUTABLE_ONLY:
        return True
    return pred["arguments"] == observed["arguments"]
