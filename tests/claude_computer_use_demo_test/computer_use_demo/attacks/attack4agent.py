from ..llms.base import TextMessage, ToolUseMessage, ToolResultMessage

class Attack4Agent:
    def __init__(self, agent_pid, agent_core_file, agent_config_file):
        self.agent_pid = agent_pid
        self.agent_core_file = agent_core_file
        self.agent_config_file = agent_config_file

    def inject_system_prompt(self, system_prompt: str):
        return system_prompt

    def inject_user_instruction(self, instruction: str):
        if "$AGENT_MAIN_PID" in instruction:
            instruction = instruction.replace("$AGENT_MAIN_PID", str(self.agent_pid))

        if "$AGENT_CORE_FILE" in instruction:
            instruction = instruction.replace("$AGENT_CORE_FILE", self.agent_core_file)

        if "$AGENT_CONFIG_FILE" in instruction:
            instruction = instruction.replace("$AGENT_CONFIG_FILE", self.agent_config_file)

        return instruction

    def inject_tool_use(self, actions: list[TextMessage|ToolUseMessage]):
        return actions

    def inject_tool_use_result(self, result: ToolResultMessage):
        return result

    def get_attack_name(self):
        return "attack4agent"