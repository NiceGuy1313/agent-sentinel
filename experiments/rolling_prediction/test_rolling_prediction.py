from __future__ import annotations

import unittest

from experiments.rolling_prediction.matcher import (
    POLICY_EXECUTABLE_ARGS,
    POLICY_EXECUTABLE_ONLY,
    processes_match,
)
from experiments.rolling_prediction.prompts import build_prediction_context


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
    def test_context_contains_only_supplied_history(self) -> None:
        observed = [
            {"sequence": 1, "executable": "/usr/bin/bash", "arguments": []},
            {"sequence": 2, "executable": "/usr/bin/find", "arguments": ["/tmp"]},
        ]
        context = build_prediction_context(
            task_id="direct3",
            user_task="test task",
            agent_system_prompt="system",
            tools=[],
            observed_history=observed,
            current_mismatch_event=observed[-1],
        )
        self.assertEqual(context["observed_process_exec_history"], observed)
        self.assertNotIn("actual_future", context)
        self.assertNotIn("future_processes", context)


if __name__ == "__main__":
    unittest.main()
