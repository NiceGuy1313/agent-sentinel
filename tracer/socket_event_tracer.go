package tracer

import (
	"bytes"
	"encoding/binary"
	"errors"
	"fmt"
	"github.com/cilium/ebpf/link"
	"github.com/cilium/ebpf/ringbuf"
	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
	"agent-sentinel/helper"
	"sync"
	"syscall"
)

type sockOpsEventTracer struct {
	bpfObjs          *tracingObjects
	bpfLinks         []link.Link
	cgroupV2Path     string
	ringbufReader    *ringbuf.Reader
	eventSubscribers map[string]chan<- interface{}
	lock             sync.Mutex
}

func newSockOpsEventTracer(bpfObjs *tracingObjects, args ...interface{}) (*sockOpsEventTracer, error) {
	rt := &sockOpsEventTracer{
		bpfObjs:          bpfObjs,
		eventSubscribers: make(map[string]chan<- interface{}),
	}

	if len(args) != 1 {
		log.Error().Msg("Missing container cgroup path")
		return nil, fmt.Errorf("missing container cgroup path")
	}

	cgroupV2Path, ok := args[0].(string)
	if !ok {
		log.Error().Msg("Bad container cgroup path")
		return nil, fmt.Errorf("bad container cgroup path")
	}
	rt.cgroupV2Path = cgroupV2Path

	return rt, nil
}

func (se *sockOpsEventTracer) startTracing() error {
	l, err := link.Kprobe("security_socket_connect", se.bpfObjs.KprobeSecuritySocketConnect, nil)
	if err != nil {
		log.Error().Err(err).Msg("Attaching security_socket_connect failed")
		return err
	}
	se.bpfLinks = append(se.bpfLinks, l)

	l, err = link.Kprobe("security_socket_listen", se.bpfObjs.KprobeSecuritySocketListen, nil)
	if err != nil {
		log.Error().Err(err).Msg("Attaching security_socket_listen failed")
		return err
	}
	se.bpfLinks = append(se.bpfLinks, l)

	l, err = link.Kprobe("security_socket_accept", se.bpfObjs.KprobeSecuritySocketAccept, nil)
	if err != nil {
		log.Error().Err(err).Msg("Attaching security_socket_accept failed")
		return err
	}
	se.bpfLinks = append(se.bpfLinks, l)

	// create ringbuf reader
	se.ringbufReader, err = ringbuf.NewReader(se.bpfObjs.SocketEvents)
	if err != nil {
		log.Error().Err(err).Msg("Creating ringbuf reader failed")
		return err
	}

	// start callback of net event
	go se.handleNetEvents()

	log.Info().Msg("socket tracer started")
	return nil
}

func (se *sockOpsEventTracer) stopTracing() {
	for _, l := range se.bpfLinks {
		if err := l.Close(); err != nil {
			log.Error().Err(err).Msg("Unattaching BPF_PROG_TYPE_SOCK_OPS failed")
		}
	}

	if se.ringbufReader != nil {
		if err := se.ringbufReader.Close(); err != nil {
			log.Error().Err(err).Msg("Closing ringbuf reader failed")
		}
	}

	// notify if subscribers are available
	if len(se.eventSubscribers) > 0 {
		for _, sub := range se.eventSubscribers {
			close(sub)
		}
		se.eventSubscribers = make(map[string]chan<- interface{})
	}
	log.Info().Msg("sock_ops tracer stopped")
}

func (se *sockOpsEventTracer) Close() {
	se.stopTracing()
}

func (se *sockOpsEventTracer) handleNetEvents() {
	for {
		record, err := se.ringbufReader.Read()
		if err != nil {
			if errors.Is(err, ringbuf.ErrClosed) {
				log.Info().Msg("ringbuf reader closed")
				return
			}
			log.Err(err).Msg("ringbuf read failed")
			continue
		}

		event, err := se.postEventHandle(record.RawSample)

		log.Debug().
			Dict("data", SockOpsEventToLogEvent(event)).Msg("sock_ops_event_record")

		for _, sub := range se.eventSubscribers {
			sub <- event
		}
	}
}

func (se *sockOpsEventTracer) postEventHandle(raw []byte) (*SocketEvent, error) {
	buffer := bytes.NewBuffer(raw)
	var header SocketEventHeader

	if err := binary.Read(buffer, binary.LittleEndian, &header); err != nil {
		log.Err(err).Msg("Parse ringbuf event failed")
		return nil, err
	}

	event := &SocketEvent{
		Time:         header.Time,
		Flag:         header.Flag,
		Tgid:         header.Tgid,
		ParentTgid:   header.ParentTgid,
		NsTgid:       header.NsTgid,
		NsParentTgid: header.NsParentTgid,
		Type:         header.Type,
	}

	var family uint16
	if err := binary.Read(buffer, binary.LittleEndian, &family); err != nil {
		log.Err(err).Msg("Parse ringbuf event failed")
		return nil, err
	}

	event.Family = uint32(family)

	switch family {
	case syscall.AF_INET:
		var sockaddr SockaddrInet4
		if err := binary.Read(buffer, binary.LittleEndian, &sockaddr); err != nil {
			log.Err(err).Msg("Parse ringbuf event failed")
			return nil, err
		}

		event.RemotePort = sockaddr.SinPort
		event.RemoteIP = helper.Int2ip(sockaddr.SinAddr)
	case syscall.AF_INET6:
		var sockaddr SockaddrInet6
		if err := binary.Read(buffer, binary.LittleEndian, &sockaddr); err != nil {
			log.Err(err).Msg("Parse ringbuf event failed")
			return nil, err
		}

		event.RemotePort = sockaddr.Sin6Port
		event.RemoteIP = sockaddr.Sin6Addr[:]
	}

	return event, nil
}

func (se *sockOpsEventTracer) AddSubscriber(name string) (<-chan interface{}, error) {
	ch := make(chan interface{})
	se.lock.Lock()
	se.eventSubscribers[name] = ch
	se.lock.Unlock()

	// enable tracing
	if len(se.eventSubscribers) == 1 {
		err := se.startTracing()
		if err != nil {
			return nil, err
		}
	}

	return ch, nil
}

func (se *sockOpsEventTracer) DeleteSubscriber(name string) {
	close(se.eventSubscribers[name])
	se.lock.Lock()
	delete(se.eventSubscribers, name)
	se.lock.Unlock()

	// disable tracing if there is no available subscriber
	if len(se.eventSubscribers) == 0 {
		se.stopTracing()
	}
}

func SockOpsEventToLogEvent(event *SocketEvent) *zerolog.Event {
	if event.Family == syscall.AF_INET {
		return zerolog.Dict().
			Uint64("time", event.Time).
			Stringer("remote_addr", event.RemoteIP).
			Uint16("remote_port", event.RemotePort).
			Uint32("pid", event.Tgid).
			Uint32("ppid", event.ParentTgid).
			Uint32("ns_pid", event.NsTgid).
			Uint32("ns_ppid", event.NsParentTgid).
			Uint32("type", event.Type)
	} else {
		return zerolog.Dict().
			Uint64("time", event.Time).
			Stringer("remote_addr", event.RemoteIP).
			Uint16("remote_port", event.RemotePort).
			Uint32("pid", event.Tgid).
			Uint32("ppid", event.ParentTgid).
			Uint32("ns_pid", event.NsTgid).
			Uint32("ns_ppid", event.NsParentTgid).
			Uint32("type", event.Type)
	}
}
