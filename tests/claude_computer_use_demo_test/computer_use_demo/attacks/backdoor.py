import random
import uuid
from ..llms.base import TextMessage, ToolUseMessage, ToolResultMessage

class Backdoor:
    def __init__(self, backdoor_instruction, backdoor_trigger, backdoor_tool_uses):
        self.backdoor_instruction = backdoor_instruction
        self.backdoor_trigger = backdoor_trigger
        self.backdoor_tool_uses = backdoor_tool_uses

    def inject_system_prompt(self, system_prompt: str):
        return system_prompt + f"\n{self.backdoor_instruction}"

    def inject_user_instruction(self, instruction: str):
        return f"{instruction} {self.backdoor_trigger}"

    def inject_tool_use(self, actions: list[TextMessage|ToolUseMessage]):
        # tool_uses = []
        # for i, action in actions:
        #     if action["type"] == "tool_use":
        #         tool_uses.append(i)
        #
        # # randomly replace a tool use
        # choose_inject_method = random.randrange(0,2)
        # j = random.randrange(0, len(tool_uses))
        # inject = self.backdoor_tool_uses[j]
        #
        # if choose_inject_method == 0 and len(tool_uses) > 0:
        #     # randomly replace
        #     i = random.randrange(0, len(tool_uses))
        #     actions[tool_uses[i]]["name"] = inject["name"]
        #     actions[tool_uses[i]]["input"] = inject["input"]
        # else:
        #     # append
        #     actions.append(
        #         {
        #             "type": "tool_use",
        #             "id": uuid.uuid4(),
        #             "name": inject["name"],
        #             "input": inject["input"]
        #         }
        #     )

        return actions

    def inject_tool_use_result(self, result: ToolResultMessage):
        return result

    def get_attack_name(self):
        return "backdoor"