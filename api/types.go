package api

/*
	 Message format of computer monitor protocol:
		|-------------------|
		| op: int16         |
		|-------------------| header
		| data_len: int32   |
		--------------------|
		| data              |
		| ...               |
	 	---------------------
*/
const (
	CM_OP_CONNECT = 0

	// active tracer
	CM_OP_START_TRACING         = 1
	CM_OP_STOP_TRACING          = 2
	CM_OP_GET_LAST_TRACE_RECORD = 3

	// passive tracer
	CM_OP_START_PASSIVE_TRACING       = 4
	CM_OP_SEND_TOOL_USE               = 5
	CM_OP_GET_LAST_ENFORCEMENT_RESULT = 6

	// tests tracer
	CM_OP_START_TEST_TRACING = 7
	CM_OP_STOP_TEST_TRACING  = 8
)

const HELLO_REPLY = "$@!$"

const CONNECTION_REQUEST_SIZE = 4

//type ComputerMonitorConnectionRequest struct {}

type computerMonitorMessageResponseHeader computerMonitorMessageRequestHeader

type computerMonitorMessageRequestHeader struct {
	Op      int16
	DateLen int32
}

type ComputerMonitorMessage struct {
	Op      int16
	DateLen int32
	Data    []byte
}

type ComputerMonitorCallbackResponse struct {
	Close bool
	Data  []byte
}

type ComputerMonitorMessageCallback func(op int16, msg *ComputerMonitorMessage) *ComputerMonitorCallbackResponse
