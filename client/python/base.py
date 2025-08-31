import struct

CM_HELLO_MSG = "x$!@"
CM_HEADER_LEN = 6

CM_OP_CONNECT = 0
CM_OP_START_TRACING = 1
CM_OP_STOP_TRACING = 2
CM_OP_GET_LAST_TRACE_RECORD = 3
CM_OP_START_PASSIVE_TRACING = 4
CM_OP_SEND_TOOL_USE        = 5
CM_OP_GET_LAST_ENFORCEMENT_RESULT = 6

CM_MESSAGE_ROLE_USER = "user"
CM_MESSAGE_ROLE_AGENT = "ai_agent"

class ComputerMonitorRequest:
    op = None
    data_len = 0
    data = None

    def __init__(self, op: int, data: bytes):
        self.op = op
        self.data = data
        self.data_len = len(data)

    def to_bytes(self) -> bytes:
        header = struct.pack("<hl", self.op, self.data_len)
        buf = header + self.data
        return buf

class ComputerMonitorResponse(ComputerMonitorRequest):
    """"""

class AgentDefenderError(Exception):
    def __init__(self, message):
        self.message = message