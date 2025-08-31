package handler

import (
	"agent-sentinel/audit"
	"agent-sentinel/tracer"
	"net"
	"time"
)

type TraceChannel struct {
	processEventCh  <-chan interface{}
	readlineEventCh <-chan interface{}
	netEventCh      <-chan interface{}
	fileEventCh     <-chan interface{}
}

type TraceEventCallback struct {
	fileEventCallback     func(*tracer.FileEvent)
	processEventCallback  func(*tracer.ProcessEvent)
	readlineEventCallback func(*tracer.ReadlineEvent)
	netEventCallback      func(*tracer.SocketEvent)
}

type ActiveTracing struct {
	name              string
	ch                *TraceChannel
	record            map[uint32]*audit.ProcessEventTable
	ctrEvenHandlingCh chan int
}

type PassiveTracing struct {
	name                 string
	ch                   *TraceChannel
	record               map[uint32]*audit.ProcessEventTable
	ctrEvenHandlingCh    chan int
	toolUseMsgProducerCh chan []*audit.ToolUseMessage
	toolUseMsgReceiverCh chan []*audit.ToolUseMessage
	toolUseMsgRequestCh  chan bool
	unusedToolUseMsg     []*audit.ToolUseMessage
	curToolUseMsg        []*audit.ToolUseMessage
}

const (
	AuditTimeout = time.Minute * 10
)

// helpers

// FIXME: maybe filter?

type callbackFunc func()

type callbackChannel struct {
	ch       chan bool
	callback callbackFunc
}

// DNS cache

type DNSRecord struct {
	Ip     net.IP
	Domain string
}

type SecurityAlert struct {
	IsSafe  bool   `json:"is_safe"`
	Message string `json:"msg"`
}
