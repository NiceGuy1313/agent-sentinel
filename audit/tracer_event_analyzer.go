package audit

import (
	"fmt"
	"agent-sentinel/tracer"
)

func TraceEventToString(event interface{}, values ...interface{}) string {
	switch t := event.(type) {
	case *tracer.ProcessEvent:
		return ExecEventToString(t)
	case *tracer.FileEvent:
		return FileEventToString(t)
	case *tracer.SocketEvent:
		domain := ""
		if len(values) > 0 {
			value, ok := values[0].(string)
			if ok {
				domain = value
			}
		}

		return NetEventToString(t, domain)
	default:
		return ""
	}
}

func FileEventToString(event *tracer.FileEvent) string {
	prefix := fmt.Sprintf("[File Event]\nProcess %d ", event.NsTgid)

	eventT := getFileOperationType(event)
	action := ""
	switch eventT {
	case FILE_OP_READ:
		action = fmt.Sprintf("read file %s\n", event.Path)
	case FILE_OP_WRITE:
		action = fmt.Sprintf("write file %s\n", event.Path)
	case FILE_OP_READ_WRITE:
		action = fmt.Sprintf("read and write file %s\n", event.Path)
	case FILE_OP_UNLINK:
		action = fmt.Sprintf("unlink file %s\n", event.Path)
	case FILE_OP_RENAME:
		action = fmt.Sprintf("rename file %s to %s\n", event.Path, event.NewPath)
	}

	// TODO: add some information already in process tree
	extra := fmt.Sprintf("[Extra Information]\n**Parent PID**: %d", event.NsParentTgid)
	return prefix + action + extra
}

func NetEventToString(event *tracer.SocketEvent, domain string) string {
	prefix := fmt.Sprintf("[Network Event]\nProcess %d ", event.NsTgid)

	eventT := getNetOperationType(event)
	action := ""
	switch eventT {
	case NET_OP_RECV:
		if domain != "" {
			action = fmt.Sprintf("recv a message from %s:%d (%s)\n", event.RemoteIP.String(), event.RemotePort, domain)
		} else {
			action = fmt.Sprintf("recv a message from %s:%d\n", event.RemoteIP.String(), event.RemotePort)
		}
	case NET_OP_SEND:
		if domain != "" {
			action = fmt.Sprintf("send a message to %s:%d (%s)\n", event.RemoteIP.String(), event.RemotePort, domain)
		} else {
			action = fmt.Sprintf("send a message to %s:%d\n", event.RemoteIP.String(), event.RemotePort)
		}
	case NET_OP_LISTEN:
		// TODO: need add domain here?
		action = fmt.Sprintf("listen at %s:%d\n", event.RemoteIP.String(), event.RemotePort)
	}

	extra := fmt.Sprintf("[Extra Information]\n**Parent PID**: %d", event.NsParentTgid)
	return prefix + action + extra
}

func ExecEventToString(event *tracer.ProcessEvent) string {
	prefix := fmt.Sprintf("[Execution Event]\nProcess %d ", event.NsChildTgid)

	action := fmt.Sprintf("execute binary %s with arguments %+q\n", event.ExecutablePath, event.Args)

	extra := fmt.Sprintf("[Extra Information]\n**Parent PID**: %d", event.NsParentTgid)

	return prefix + action + extra
}
