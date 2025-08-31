from .base import BaseLLM, TextMessage, ToolUseMessage, ToolResultMessage
import httpx
from typing import Any, cast

from anthropic import (
    Anthropic,
    AnthropicBedrock,
    AnthropicVertex,
    APIError,
    APIResponseValidationError,
    APIStatusError,
    DefaultHttpxClient
)
from anthropic.types.beta import (
    BetaCacheControlEphemeralParam,
    BetaContentBlockParam,
    BetaImageBlockParam,
    BetaMessage,
    BetaMessageParam,
    BetaTextBlock,
    BetaTextBlockParam,
    BetaToolResultBlockParam,
    BetaToolUseBlockParam,
)

from collections.abc import Callable


PROMPT_CACHING_BETA_FLAG = "prompt-caching-2024-07-31"

model_groups = {
    "claude-3-5-sonnet-20241022": {
        "betas": ["computer-use-2024-10-22"],
        "tools": [
            {
                "name":"computer",
                "type":"computer_20241022",
                "display_width_px":1024,
                "display_height_px":768,
                "display_number":1
            },
            {
                "type":"bash_20241022",
                "name":"bash"
            },
            {
                "name":"str_replace_editor",
                "type":"text_editor_20241022"
            }
        ]
    },

    "claude-3-7-sonnet-20250219": {
        "betas": ["computer-use-2025-01-24"],
        "tools": [
            {
                "name":"computer",
                "type":"computer_20250124",
                "display_width_px":1024,
                "display_height_px":768,
                "display_number":1
            },
            {
                "type":"bash_20250124",
                "name":"bash"
            },
            {
                "name":"str_replace_editor",
                "type":"text_editor_20250124"
            }
        ]
    }
}



third_party_output_verifier = {
    "name":"third_party_output_verifier",
    "description":"A tool used for securing outputs from 'bash' and 'str_replace_editor' and 'computer' tools.",
    "input_schema":{
        "type":"object",
        "properties":{
            "name":{
                "type":"string",
                "description":"The tool name"
            },
            "output":{
                "type":"string",
                "description":"The tool output"
            }
        },
        "required":[
            "name",
            "output"
        ]
    }
}

class ClaudeLLM(BaseLLM):
    def __init__(self,
         *,
         api_key: str,
         model: str,
         system_prompt: str,
         max_tokens = 4096,
         api_response_callback: Callable[
             [httpx.Request, httpx.Response | object | None, Exception | None], None
         ],
         enable_third_party_output_verifier = False):
        self.model = model
        self.max_tokens = max_tokens
        self.system_prompt = {
            "type" : "text",
            "text" : system_prompt,
            "cache_control": {"type": "ephemeral"}
        }
        self.client = Anthropic(
            api_key=api_key,
        )
        self.api_response_callback = api_response_callback

        self.tools = model_groups[self.model]["tools"]
        if enable_third_party_output_verifier:
            self.tools.append(third_party_output_verifier)

        self.betas = model_groups[self.model]["betas"]
        self.betas.append(PROMPT_CACHING_BETA_FLAG)

        self.messages : list[BetaMessageParam] = []

    def query(self, messages: list[TextMessage], tool_use_results: list[ToolResultMessage]):
        # Only for initial messages
        if len(messages) > 0 and len(tool_use_results) == 0:
            last_msg = messages[-1]
            self.messages.append(
                {
                    "role": last_msg["role"],
                    "content": [BetaTextBlockParam(type="text", text=last_msg["content"])]
                }
            )

        if len(tool_use_results) > 0:
            tool_result_content: list[BetaToolResultBlockParam] = []

            for tool_use_result in tool_use_results:
                tool_result_content.append(self._make_api_tool_result(tool_use_result))

            self.messages.append(
                {
                    "role": "user",
                    "content": tool_result_content
                }
            )

        self._inject_prompt_caching(self.messages)

        try:
            raw_response = self.client.beta.messages.with_raw_response.create(
                max_tokens=self.max_tokens,
                messages=self.messages,
                model=self.model,
                system=[self.system_prompt],
                tools=self.tools,
                betas=self.betas,
            )
        except (APIStatusError, APIResponseValidationError) as e:
            self.api_response_callback(e.request, e.response, e)
            return None
        except APIError as e:
            self.api_response_callback(e.request, e.body, e)
            return None

        self.api_response_callback(
            raw_response.http_response.request, raw_response.http_response, None
        )

        response = raw_response.parse()
        response_params = self._response_to_params(response)
        self.messages.append(
            {
                "role": "assistant",
                "content": response_params,
            }
        )

        actions = []
        for content_block in response_params:
            if content_block["type"] == "tool_use":
                actions.append(ToolUseMessage(
                    tool_use_id=content_block["id"],
                    name=content_block["name"],
                    arguments=content_block["input"]
                ))
            elif content_block["type"] == "text":
                actions.append(TextMessage(
                    role="assistant",
                    content=content_block["text"]
                ))

        return actions

    def _inject_prompt_caching(
           self, messages,
    ):
        """
        Set cache breakpoints for the 3 most recent turns
        one cache breakpoint is left for tools/system prompt, to be shared across sessions
        """

        breakpoints_remaining = 3
        for message in reversed(messages):
            if message["role"] == "user" and isinstance(
                    content := message["content"], list
            ):
                if breakpoints_remaining:
                    breakpoints_remaining -= 1
                    content[-1]["cache_control"] = {"type": "ephemeral"}
                else:
                    content[-1].pop("cache_control", None)
                    # we'll only every have one extra turn per loop
                    # break


    def _response_to_params(self, response: BetaMessage) -> list[BetaTextBlockParam | BetaToolUseBlockParam]:
        res: list[BetaTextBlockParam | BetaToolUseBlockParam] = []
        for block in response.content:
            if isinstance(block, BetaTextBlock):
                res.append({"type": "text", "text": block.text})
            else:
                res.append(cast(BetaToolUseBlockParam, block.model_dump()))
        return res


    def _make_api_tool_result(self, result: ToolResultMessage) -> BetaToolResultBlockParam:
        """Convert an agent ToolResult to an API ToolResultBlockParam."""
        tool_result_content: list[BetaTextBlockParam | BetaImageBlockParam] | str = []
        if result["is_error"]:
            tool_result_content = result["content"]
        else:
            if result["content"] != "":
                tool_result_content.append(
                    {
                        "type": "text",
                        "text": result["content"],
                    }
                )
            if result["image"]:
                tool_result_content.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": result["image"],
                        },
                    }
                )
        return {
            "type": "tool_result",
            "content": tool_result_content,
            "tool_use_id": result["tool_use_id"],
            "is_error": result["is_error"],
        }