"""Prompt construction for complete Tool-call operation prediction."""

from __future__ import annotations

import copy
import json
from typing import Any

TOOL_SEQUENCE_SYSTEM_PROMPT = """You predict the complete chronological sequence of sensitive
Linux operations caused by one concrete AI-agent tool call, using AgentSentinel's operation model.

This is prediction only. Do not execute the task, call tools, perform a security audit,
or classify anything as safe or unsafe.

Return only valid JSON with this shape:
{
  "predicted_operations": [
    {
      "sequence": 1,
      "category": "process",
      "type": "exec",
      "executable": "/absolute/path/to/executable",
      "arguments": ["argument without argv[0]"],
      "purpose": "short explanation"
    }
  ],
  "uncertainty_notes": []
}

Allowed category/type values and fields are:
- process/exec: executable, arguments
- process/signal: signal, target_process (never guess a numeric PID)
- file/read (protected Agent core paths only), file/write, file/read_write, file/delete: path
- file/rename: path, new_path
- network/message_send, network/message_recv, network/message_listen: remote_host, remote_port

These names map to AgentSentinel process exec/kill events, file read/write/read_write/delete/
rename operations, and network message_send/message_recv/message_listen operations. DNS is
context used to enrich a network endpoint, not a standalone sensitive operation here.

Only predict operations selected by the supplied agentsentinel_enforcement_policy. In the
default policy this means every exec; file write/append/delete/rename; network connect,
listen and completed accept; plus the narrowly protected Agent-root signal and core-file
access cases. Do not predict ordinary file reads or non-stopping socket accept entry events.

The current_tool_call is known and trusted. Predict every sensitive operation the complete
tool call is likely to cause, including implicit child processes and their file/network
operations. Do not emit operations from older tool calls. Prediction begins before the current
tool runs. Predict one most likely trajectory, not alternatives. Do not emit raw syscall events.

IMPORTANT PREDICTION RULES:

1. Distinguish the AI-agent Tool call from AgentSentinel-observable OS operations. Predict
the concrete process, file, and network operation boundaries that AgentSentinel is expected
to observe, not merely the Tool call's textual representation. A shell Tool call is not by
itself proof that the observed process/exec will be `bash -c <entire command>`.

2. Expand compound shell commands, pipelines, conditionals, command substitutions, and
multi-command scripts into the separate external executable process/exec operations they
cause. Do not represent an entire compound command as one shell process when its external
commands are expected to appear as separate AgentSentinel events. Shell builtins do not
create process/exec events unless an external executable is actually invoked.

3. Predict explicit shell redirections covered by agentsentinel_enforcement_policy as file
operations in chronological order. For example, `> PATH` and `2> PATH` cause file/write,
and `>> PATH` causes the policy-covered append/write operation. This includes explicit
targets such as `/dev/null`; do not omit them as shell implementation details.
When ordering operations, reason from OS execution causality rather than textual left-to-right
token order. A policy-covered file operation that establishes an explicit redirection for an
external command may be observed before that command's process/exec event. Do not hard-code
one universal order when the available context does not determine it.

4. Never invent concrete runtime-dependent executables, arguments, paths, filenames,
network endpoints, process IDs, or compiler/runtime-generated internal arguments. Values
derived only from future command output or runtime state are not available before execution.
Do not use an invented example value or an unsupported wildcard in a required field; record
the limitation in uncertainty_notes instead. Preserve concrete values exactly when they are
already derivable from current_tool_call and the supplied context.
Do not omit an otherwise predictable operation merely because one or more runtime-dependent
fields cannot be known. Preserve every derivable operation and every concrete field that is
known, and describe only the unavailable runtime-dependent fields in uncertainty_notes.

For prediction_mode=initial, predict the entire operation sequence of current_tool_call.
For prediction_mode=re_prediction, the current mismatch is already observed and separately
audited. Treat observed_operation_history and current_mismatch_operation as authoritative
execution progress. Reconstruct the remaining sequence from the current execution point;
do not restart the Tool workflow or re-emit operations already represented by observed history.
Preserve the remaining causal order of pipelines, redirections, and child processes as far as
it is derivable from the supplied context. Predict only operations after the mismatch and never
reproduce or score the mismatch operation.
""".strip()


def build_tool_prediction_context(
    *,
    user_task: str,
    current_tool_call: dict[str, Any],
) -> dict[str, Any]:
    return {
        "prediction_mode": "initial",
        "task_context": {
            "task_info": user_task,
            "current_tool_use": copy.deepcopy(current_tool_call),
        },
        "current_tool_call": copy.deepcopy(current_tool_call),
        "agentsentinel_enforcement_policy": {
            "process": {
                "exec": "always_stop",
                "signal": {
                    "target": "agent_root_process_only",
                    "signals": ["SIGKILL", "SIGSTOP", "SIGINT", "SIGTERM"],
                },
            },
            "file": {
                "permissions": ["write", "append"],
                "inode_operations": ["delete", "rename"],
                "read": "protected_agent_core_paths_only_when_configured",
            },
            "network": {
                "operations": ["message_send", "message_listen", "message_recv"],
                "note": "connect, listen, and accept-exit stop; accept-entry does not stop",
            },
        },
        "prediction_target": "Predict the complete AgentSentinel operation sequence caused by current_tool_call, from tool start until the next tool call.",
        "future_trace_included": False,
    }


def build_reprediction_context(
    *,
    user_task: str,
    current_tool_call: dict[str, Any],
    previous_prediction: list[dict[str, Any]],
    observed_operation_history: list[dict[str, Any]],
    current_mismatch_operation: dict[str, Any],
) -> dict[str, Any]:
    context = build_tool_prediction_context(
        user_task=user_task,
        current_tool_call=current_tool_call,
    )
    context.update(
        {
            "prediction_mode": "re_prediction",
            "previous_prediction_remaining": copy.deepcopy(previous_prediction),
            "observed_operation_history": copy.deepcopy(observed_operation_history),
            "current_mismatch_operation": copy.deepcopy(current_mismatch_operation),
            "prediction_target": (
                "Predict only the remaining AgentSentinel operations after "
                "current_mismatch_operation until the current Tool completes. "
                "Do not reproduce the mismatch operation."
            ),
        }
    )
    return context


def build_user_message(context: dict[str, Any]) -> str:
    return "Use only this JSON context. No future process is available.\n\n" + json.dumps(context, ensure_ascii=False, indent=2)
