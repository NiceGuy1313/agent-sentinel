from ..llms.base import TextMessage, ToolUseMessage, ToolResultMessage

class DirectTaskInjection:
    def __init__(self, inject_instruction):
        self.inject_instruction = inject_instruction

    def inject_system_prompt(self, system_prompt: str):
        return system_prompt

    def inject_user_instruction(self, instruction: str):
        return instruction + self.inject_instruction

    def inject_tool_use(self, actions: list[TextMessage|ToolUseMessage]):
        return actions

    def inject_tool_use_result(self, result: ToolResultMessage):
        return result

    def get_attack_name(self):
        return "direct_task_inject"