# llm sandbox
from .computer_monitor_api.agent_defender import AgentDefender
from .computer_monitor_api.base import CM_MESSAGE_ROLE_USER,CM_MESSAGE_ROLE_AGENT
from ..llms.base import TextMessage, ToolUseMessage, ToolResultMessage

class LLMSandbox:
    def __init__(self, config):
        self.server = AgentDefender(config)
        self.server.start_passive_tracing()

    def secure_system_prompt(self, base_prompt):
        return base_prompt

    def secure_user_instruction(self, instruction):
        if isinstance(instruction, str):
            self.server.send_text_message(instruction, CM_MESSAGE_ROLE_USER)

        return instruction

    # actions include thoughts and tool uses
    def secure_action(self, action: TextMessage | ToolUseMessage):
        if isinstance(action, TextMessage):
            self.server.send_text_message(action["content"], CM_MESSAGE_ROLE_AGENT)
        else:
            name = action["name"]
            args = action["arguments"]
            tool_desc = ""
            if  name == "bash":
                tool_desc = "A tool that allows the agent to run bash commands. Importantly, it will launch a bash process or use existed bash process, then send the bash commands to the bash process."
            elif name == "computer":
                tool_desc = "A tool that uses xdotool to mock keyboard and mouse actions."
            elif name == "str_replace_editor":
                tool_desc = "An filesystem editor tool that allows the agent to view, create, and edit files."

            self.server.send_tool_use(f'Tool Use: {name}\nTool Description:{tool_desc}\nTool Input: {args}')

        return action

    def reject_tool_use(self, action: ToolUseMessage):
        return None

    def secure_tool_use_result(self, result: ToolResultMessage):
        text = result["content"]
        if result["is_error"]:
            if result["is_error"]:
                alert = self.server.try_to_get_security_alert()
                if alert != "":
                    result["content"] = result["content"] + f"\n{alert}"
        elif text == "" and result["image"]:
            text = "This is a image."

        if text != "":
            text = f"Tool Use Results:\n{text}"
            self.server.send_text_message(text, CM_MESSAGE_ROLE_USER)

        return result