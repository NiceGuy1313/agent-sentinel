"""
Agentic sampling loop that calls the Anthropic API and local implementation of anthropic-defined computer use tools.
"""

from collections.abc import Callable
from typing import Any, cast

from .attacks.backdoor import Backdoor
from .attacks.indirect_prompt_injection import IndirectPromptInjection
from .defenses.delimiters_defense import DelimitersDefender
from .defenses.instructional_prevention import InstructionalPrevention
from .defenses.sandbox import LLMSandbox
from .tools import BashTool, ComputerTool, EditTool, ToolCollection, ToolResult, ToolResultVerifier
from .tools.base import ToolFailure

from .llms.base import TextMessage, ToolUseMessage, ToolResultMessage
from .llms.claude import ClaudeLLM

async def sampling_loop(
        *,
        # TODO: more
        llm_client: ClaudeLLM,
        messages: list[TextMessage],
        output_callback: Callable[[TextMessage|ToolUseMessage], None],
        tool_output_callback: Callable[[ToolResultMessage, str], None],
        max_requests: int = 30,
        attack: Backdoor | IndirectPromptInjection | None,
        defense: LLMSandbox | DelimitersDefender | InstructionalPrevention | None,
):
    """
    Agentic sampling loop for the assistant/tool interaction of computer use.
    """
    request_count = 0

    if (attack is not None
            and (attack.get_attack_name() == "indirect_prompt_injection"
                 or attack.get_attack_name() == "backdoor"
                 or attack.get_attack_name() == "hallucination"
                 or attack.get_attack_name() == "bad_tool_result"
                 or attack.get_attack_name() == "direct_task_inject")):
        tool_collection = ToolCollection(
            ComputerTool(),
            BashTool(),
            EditTool(),
            ToolResultVerifier(),
        )
    else:
        tool_collection = ToolCollection(
            ComputerTool(),
            BashTool(),
            EditTool(),
        )

    tool_result_content: list[ToolResultMessage] = []

    # initial query
    actions = llm_client.query(messages, tool_result_content)
    request_count = request_count + 1

    # A such neat agent loop !!!
    while True:
        if actions is None:
            return messages

        tool_result_content: list[ToolResultMessage] = []
        messages.extend(actions)

        if attack is not None:
            actions = attack.inject_tool_use(actions)

        for action in actions:
            output_callback(action)

            if defense is not None:
                action = defense.secure_action(action)

            if isinstance(action, ToolUseMessage):
                reject = None
                if defense is not None:
                    reject = defense.reject_tool_use(action)
                if reject is not None:
                    result = ToolFailure(error=reject)
                else:
                    result = await tool_collection.run(
                        name=action["name"],
                        tool_input=cast(dict[str, Any], action["arguments"]),
                    )

                result = _make_tool_result_message(result, action["name"], action["tool_use_id"])

                if attack is not None:
                    result = attack.inject_tool_use_result(result)

                if defense is not None:
                    result = defense.secure_tool_use_result(result)

                tool_result_content.append(result)
                tool_output_callback(result, action["tool_use_id"])
                messages.append(result)

        if not tool_result_content:
            return messages

        # control llm requests for each task
        if request_count >= max_requests:
            return messages
        request_count = request_count + 1
        actions = llm_client.query([], tool_result_content)

def _make_tool_result_message(
        result: ToolResult, name: str, tool_use_id: str
) -> ToolResultMessage:
    is_error = False
    tool_result_content = ""
    message_type = "text"
    image = None

    if result.error:
        is_error = True
        tool_result_content = _maybe_prepend_system_tool_result(result, result.error)
    else:
        if result.output or result.system:
            tool_result_content = _maybe_prepend_system_tool_result(result, result.output)
        if result.base64_image:
            image = result.base64_image

    if image:
        return ToolResultMessage(
            tool_use_id=tool_use_id,
            name=name,
            content=tool_result_content,
            is_error=is_error,
            image=image
        )
    else:
        return ToolResultMessage(
            tool_use_id=tool_use_id,
            name=name,
            content=tool_result_content,
            is_error=is_error
        )

def _maybe_prepend_system_tool_result(result: ToolResult, result_text: str) -> str:
    if result.system:
        result_text = f"<system>{result.system}</system>\n{result_text}"

    return result_text