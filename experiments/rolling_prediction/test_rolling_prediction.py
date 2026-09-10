from __future__ import annotations

import datetime as dt
import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from experiments.rolling_prediction.matcher import (
    POLICY_EXECUTABLE_ARGS,
    POLICY_EXECUTABLE_ONLY,
    processes_match,
    operations_match,
)
from experiments.rolling_prediction.common import extract_actual_processes
from experiments.rolling_prediction.prompts import (
    TOOL_SEQUENCE_SYSTEM_PROMPT,
    build_reprediction_context,
    build_tool_prediction_context,
)
from experiments.rolling_prediction.tool_sequence_predict import align_sequences


class MatcherTest(unittest.TestCase):
    def test_executable_only_ignores_arguments(self) -> None:
        predicted = {"executable": "/usr/bin/find", "likely_arguments": ["/tmp/a"]}
        actual = {"executable": "/usr/bin/find", "arguments": ["find", "/tmp/b"]}
        self.assertTrue(processes_match(predicted, actual, POLICY_EXECUTABLE_ONLY))

    def test_executable_and_arguments_removes_argv_zero(self) -> None:
        predicted = {
            "executable": "/usr/bin/ls",
            "likely_arguments": ["-la", "/tmp/test_files"],
        }
        actual = {
            "executable": "/usr/bin/ls",
            "arguments": ["ls", "-la", "/tmp/test_files"],
        }
        self.assertTrue(processes_match(predicted, actual, POLICY_EXECUTABLE_ARGS))

    def test_meaningful_argument_difference_is_mismatch(self) -> None:
        predicted = {
            "executable": "/usr/bin/find",
            "likely_arguments": ["/tmp/test_files", "-mtime", "-30"],
        }
        actual = {
            "executable": "/usr/bin/find",
            "arguments": ["find", "/tmp/test_files", "-mtime", "-90"],
        }
        self.assertFalse(processes_match(predicted, actual, POLICY_EXECUTABLE_ARGS))

    def test_extractor_drops_only_bootstrap_uname(self) -> None:
        records = []
        for args in (["uname", "-p"], ["uname", "-an"]):
            records.append(
                {
                    "time": "2026-07-05T12:46:13Z",
                    "message": "process_event_record",
                    "data": {
                        "flag": 1,
                        "type": 3,
                        "syscall": 59,
                        "executable_path": "/usr/bin/uname",
                        "args": args,
                    },
                }
            )
        content = "".join(json.dumps(record) + "\n" for record in records)
        with patch.object(Path, "open", return_value=io.StringIO(content)):
            actual = extract_actual_processes(
                Path("sandbox.log"), dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
            )
        self.assertEqual(len(actual), 1)
        self.assertEqual(actual[0]["arguments"], ["uname", "-an"])

    def test_screenshot_temporary_name_is_normalized(self) -> None:
        predicted = {
            "executable": "/usr/bin/scrot",
            "likely_arguments": ["-p", "/tmp/outputs/screenshot_aaaaaaaa.png"],
        }
        actual = {
            "executable": "/usr/bin/scrot",
            "arguments": ["scrot", "-p", "/tmp/outputs/screenshot_bbbbbbbb.png"],
        }
        self.assertTrue(processes_match(predicted, actual, POLICY_EXECUTABLE_ARGS))


class NoFutureLeakTest(unittest.TestCase):
    def test_context_contains_current_tool_but_no_actual_process(self) -> None:
        current = {"name": "bash", "input": {"command": "find /tmp"}}
        context = build_tool_prediction_context(
            user_task="test task",
            current_tool_call=current,
        )
        self.assertEqual(context["current_tool_call"], current)
        self.assertNotIn("agent_system_prompt", context)
        self.assertNotIn("agent_tool_definitions", context)
        self.assertNotIn("actual_future", context)
        self.assertNotIn("observed_process_exec_history", context)

    def test_reprediction_starts_after_current_mismatch(self) -> None:
        current = {"name": "bash", "input": {"command": "find /tmp"}}
        mismatch = {"category": "file", "type": "write", "path": "/tmp/a"}
        context = build_reprediction_context(
            user_task="test task",
            current_tool_call=current,
            previous_prediction=[],
            observed_operation_history=[mismatch],
            current_mismatch_operation=mismatch,
        )
        self.assertEqual(context["prediction_mode"], "re_prediction")
        self.assertIn("Do not reproduce", context["prediction_target"])

    def test_reprediction_prompt_invalidates_previous_queue(self) -> None:
        self.assertIn("the previous prediction is invalid", TOOL_SEQUENCE_SYSTEM_PROMPT)
        self.assertIn("Do not preserve, repair, resume, or continue", TOOL_SEQUENCE_SYSTEM_PROMPT)
        self.assertIn("Independently reconstruct", TOOL_SEQUENCE_SYSTEM_PROMPT)


class ToolSequenceAlignmentTest(unittest.TestCase):
    def test_alignment_separates_missing_and_extra_processes(self) -> None:
        predicted = [
            {"category": "process", "type": "exec", "executable": "/usr/bin/bash", "arguments": []},
            {"category": "process", "type": "exec", "executable": "/usr/bin/cat", "arguments": ["/tmp/a"]},
        ]
        actual = [
            {"category": "process", "type": "exec", "executable": "/usr/bin/bash", "arguments": ["bash"]},
            {"category": "process", "type": "exec", "executable": "/usr/bin/find", "arguments": ["find", "/tmp"]},
        ]
        alignment = align_sequences(predicted, actual, POLICY_EXECUTABLE_ARGS)
        statuses = [row["status"] for row in alignment]
        self.assertEqual(statuses.count("match"), 1)
        self.assertEqual(statuses.count("predicted_only"), 1)
        self.assertEqual(statuses.count("actual_only"), 1)

    def test_file_and_signal_operations(self) -> None:
        self.assertTrue(
            operations_match(
                {"category": "file", "type": "rename", "path": "/tmp/a", "new_path": "/tmp/b"},
                {"category": "file", "type": "rename", "path": "/tmp/a", "new_path": "/tmp/b"},
                POLICY_EXECUTABLE_ARGS,
            )
        )
        self.assertTrue(
            operations_match(
                {"category": "process", "type": "signal", "signal": "SIGTERM", "target_process": "worker"},
                {"category": "process", "type": "signal", "signal": "sigterm", "target_pid": 1234},
                POLICY_EXECUTABLE_ARGS,
            )
        )


if __name__ == "__main__":
    unittest.main()
