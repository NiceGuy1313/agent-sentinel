import json
import os
import socket

from base import *

class AgentDefender:
    computer_monitor_cli = None
    messages = []

    def __init__(self, config, sock_file = None):
        if sock_file is None:
            sock_file = os.getenv("COMPUTER_MONITOR_SOCK")

        if not os.path.exists(sock_file):
            # fixme: other specific error ?
            raise AgentDefenderError("agent_defender: sock file %s is invalid" % sock_file)

        if "pid" in config:
            self.pid = config["pid"]
        else:
            self.pid = os.getpid()

        self.core_file_paths = []

        if "core_file_paths" in config:
            self.core_file_paths = config["core_file_paths"]

        self.__connect(sock_file)

    def __discard_cm_rep(self):
        try:
            buf = self.computer_monitor_cli.recv(CM_HEADER_LEN)
        except Exception as e:
            raise AgentDefenderError("agent_defender: %s" % e)

        if not buf or len(buf) != CM_HEADER_LEN:
            raise AgentDefenderError("agent_defender: recv failed")

        data_len = int.from_bytes(buf[2:6], "little", signed=True)
        read_count = data_len
        while read_count:
            tmp_read = min(read_count, 256)
            try:
                buf = self.computer_monitor_cli.recv(tmp_read)
            except Exception as e:
                raise AgentDefenderError("agent_defender: %s" % e)
            if not buf and len(buf) != tmp_read:
                raise AgentDefenderError("agent_defender: recv failed")
            read_count = read_count - tmp_read


    def __recv_cm_rep(self):
        try:
            buf = self.computer_monitor_cli.recv(CM_HEADER_LEN)
        except Exception as e:
            raise AgentDefenderError("agent_defender: %s" % e)

        if not buf or len(buf) != CM_HEADER_LEN:
            raise AgentDefenderError("agent_defender: recv failed")

        op = int.from_bytes(buf[0:2], "little", signed=True)
        data_len = int.from_bytes(buf[2:6], "little", signed=True)
        read_count = data_len
        buf = b""
        while read_count:
            tmp_read = min(read_count, 256)
            try:
                tmp_buf = self.computer_monitor_cli.recv(tmp_read)
            except Exception as e:
                raise AgentDefenderError("agent_defender: %s" % e)

            if not buf and len(tmp_buf) != tmp_read:
                raise AgentDefenderError("agent_defender: recv failed")
            buf = buf + tmp_buf
            read_count = read_count - tmp_read

        req = ComputerMonitorResponse(op, buf)
        return req

    def __send_cm_req(self, req: ComputerMonitorRequest, ignore_recv = False) -> ComputerMonitorResponse | None:
        try:
            self.computer_monitor_cli.sendall(req.to_bytes())
        except socket.error as e:
            raise AgentDefenderError("agent_defender: send computer monitor request failed, error: %s" % e)

        if ignore_recv:
            self.__discard_cm_rep()
            return None
        else:
            return self.__recv_cm_rep()


    def __sayhello(self):
        try:
            n = self.computer_monitor_cli.send(CM_HELLO_MSG.encode())
        except Exception as e:
            raise AgentDefenderError("agent_defender: %s" % e)

        if n != len(CM_HELLO_MSG):
            raise AgentDefenderError("agent_defender: send hello request failed")

        try:
            buf = self.computer_monitor_cli.recv(len(CM_HELLO_MSG))
        except Exception as e:
            raise AgentDefenderError("agent_defender: %s" % e)

        if not buf or len(buf) != len(CM_HELLO_MSG):
            raise AgentDefenderError("agent_defender: send hello request failed")

    def __send_connect_request(self):
        data = {
            "pid" : self.pid,
            "core_file_paths": self.core_file_paths
        }
        raw_data = json.dumps(data).encode()

        req = ComputerMonitorRequest(CM_OP_CONNECT, raw_data)
        self.__send_cm_req(req, ignore_recv=True)

    def __connect(self, sock_file: str):
        try:
            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client.connect(sock_file)
        except socket.error as e:
            raise AgentDefenderError("agent_defender: connect to computer monitor api failed, error: %s" % e)

        # TODO: timeout???

        self.computer_monitor_cli = client
        # step1: say hello
        self.__sayhello()
        # step2: send connect request
        self.__send_connect_request()

    def start_tracing(self):
        req = ComputerMonitorRequest(CM_OP_START_TRACING, b"")
        self.__send_cm_req(req, ignore_recv=True)

    def stop_tracing(self):
        req = ComputerMonitorRequest(CM_OP_STOP_TRACING, b"")
        self.__send_cm_req(req, ignore_recv=True)

    def get_last_trace_record(self):
        req = ComputerMonitorRequest(CM_OP_GET_LAST_TRACE_RECORD, b"")
        rep = self.__send_cm_req(req)
        data = json.loads(rep.data)
        return data

    def start_passive_tracing(self):
        req = ComputerMonitorRequest(CM_OP_START_PASSIVE_TRACING, b"")
        self.__send_cm_req(req, ignore_recv=True)

    def send_text_message(self, text : str, role):
        self.messages.append({"role": role, "message" : text})

    # TODO: need role for each message
    def send_tool_use(self, text):
        self.messages.append({"role": CM_MESSAGE_ROLE_AGENT, "message" : text})

        raw_msg = json.dumps(self.messages).encode()
        req = ComputerMonitorRequest(CM_OP_SEND_TOOL_USE, raw_msg)
        self.__send_cm_req(req, ignore_recv=True)

        # clear messages after each tool use
        self.messages = []

    def try_to_get_security_alert(self):
        req = ComputerMonitorRequest(CM_OP_GET_LAST_ENFORCEMENT_RESULT, b"")
        rep = self.__send_cm_req(req)

        if rep.data_len == 0:
            return ""

        data = json.loads(rep.data)
        if "msg" in data:
            return data["msg"]
        else:
            return ""

    def try_to_get_security_alert_raw(self):
        req = ComputerMonitorRequest(CM_OP_GET_LAST_ENFORCEMENT_RESULT, b"")
        rep = self.__send_cm_req(req)

        if rep.data_len == 0:
            return None

        data = json.loads(rep.data)
        return data

    def close(self):
        self.computer_monitor_cli.close()