# defenses combination
from ..llms.base import TextMessage, ToolUseMessage, ToolResultMessage

class DefensesCombination:
    def __init__(self):
        self.defenses = []

    def add_defense(self, defense):
        self.defenses.append(defense)

    def secure_system_prompt(self, base_prompt: str):
        for defense in self.defenses:
            base_prompt = defense.secure_system_prompt(base_prompt)

        return base_prompt

    def secure_user_instruction(self, instruction: str):
        for defense in self.defenses:
            instruction = defense.secure_user_instruction(instruction)

        return instruction

    def secure_action(self, action: TextMessage|ToolUseMessage):
        for defense in self.defenses:
            action = defense.secure_action(action)

        return action

    def reject_tool_use(self, action: ToolUseMessage):
        for defense in self.defenses:
            reject = defense.reject_tool_use(action)
            if reject is not None:
                return reject
        return None

    def secure_tool_use_result(self, result: ToolResultMessage):
        for defense in self.defenses:
            result = defense.secure_tool_use_result(result)

        return result