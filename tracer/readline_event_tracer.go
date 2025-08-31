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
	"golang.org/x/sys/unix"
	"sync"
)

const (
	// bashPATH = "/tmp/bash"
	symbol = "readline"
)

type readlineEventTracer struct {
	bpfObjs          *tracingObjects
	bpfLinks         []link.Link
	bashExec         *link.Executable
	ringbufReader    *ringbuf.Reader
	eventSubscribers map[string]chan<- interface{}
	lock             sync.Mutex
}

func newReadlineEventTracer(bpfObjs *tracingObjects, args ...interface{}) (*readlineEventTracer, error) {
	rt := &readlineEventTracer{
		bpfObjs:          bpfObjs,
		eventSubscribers: make(map[string]chan<- interface{}),
	}

	if len(args) != 1 {
		log.Error().Msg("Missing bash path")
		return nil, fmt.Errorf("missing bash path")
	}

	bashPATH, ok := args[0].(string)
	if !ok {
		log.Error().Msg("Bad bash path")
		return nil, fmt.Errorf("bad bash path")
	}

	// TODO: remote bash path ???
	ex, err := link.OpenExecutable(bashPATH)
	if err != nil {
		log.Error().Err(err).Msg("Open bash binary failed")
		return nil, err
	}
	rt.bashExec = ex
	return rt, nil
}

func (rt *readlineEventTracer) startTracing() error {
	l, err := rt.bashExec.Uretprobe(symbol, rt.bpfObjs.BashReadlineRet, nil)

	if err != nil {
		log.Error().Err(err).Msg("Attaching bash_readline_uretprobe failed")
		return err
	}
	rt.bpfLinks = append(rt.bpfLinks, l)

	// create ringbuf reader
	rt.ringbufReader, err = ringbuf.NewReader(rt.bpfObjs.ReadlineEvents)
	if err != nil {
		log.Error().Err(err).Msg("Creating ringbuf reader failed")
		return err
	}

	// start callback of process event
	go rt.handleProcessEvents()

	log.Info().Msg("readline tracer started")
	return nil
}

func (rt *readlineEventTracer) stopTracing() {
	for _, l := range rt.bpfLinks {
		if err := l.Close(); err != nil {
			log.Error().Err(err).Msg("Unattaching bash_readline_uretprobe failed")
		}
	}

	if rt.ringbufReader != nil {
		if err := rt.ringbufReader.Close(); err != nil {
			log.Error().Err(err).Msg("Closing ringbuf reader failed")
		}
	}

	// notify if subscribers are available
	if len(rt.eventSubscribers) > 0 {
		for _, sub := range rt.eventSubscribers {
			close(sub)
		}
		rt.eventSubscribers = make(map[string]chan<- interface{})
	}
	log.Info().Msg("readline tracer stopped")
}

func (rt *readlineEventTracer) Close() {
	rt.stopTracing()
}

func (rt *readlineEventTracer) handleProcessEvents() {
	var rawEvent tracingReadlineEvent
	for {
		record, err := rt.ringbufReader.Read()
		if err != nil {
			if errors.Is(err, ringbuf.ErrClosed) {
				log.Info().Msg("ringbuf reader closed")
				return
			}
			log.Err(err).Msg("ringbuf read failed")
			continue
		}

		// parse the ringbuf event entry into a process_event structure.
		if err := binary.Read(bytes.NewBuffer(record.RawSample), binary.LittleEndian, &rawEvent); err != nil {
			log.Err(err).Msg("Parsing ringbuf event failed")
			continue
		}

		event := rt.postEventHandle(&rawEvent)

		log.Debug().
			Dict("data", ReadlineEventToLogEvent(event)).Msg("readline_event_record")

		for _, sub := range rt.eventSubscribers {
			sub <- event
		}
	}
}

func (rt *readlineEventTracer) postEventHandle(rawEvent *tracingReadlineEvent) *ReadlineEvent {
	return &ReadlineEvent{
		Time:         rawEvent.Time,
		Tgid:         rawEvent.Tgid,
		ParentTgid:   rawEvent.ParentTgid,
		NsTgid:       rawEvent.NsTgid,
		NsParentTgid: rawEvent.NsParentTgid,
		TaskComm:     unix.ByteSliceToString(rawEvent.TaskComm[:]),
		Readline:     unix.ByteSliceToString(rawEvent.Readline[:]),
	}
}

func (rt *readlineEventTracer) AddSubscriber(name string) (<-chan interface{}, error) {
	ch := make(chan interface{})
	rt.lock.Lock()
	rt.eventSubscribers[name] = ch
	rt.lock.Unlock()

	// enable tracing
	if len(rt.eventSubscribers) == 1 {
		err := rt.startTracing()
		if err != nil {
			return nil, err
		}
	}

	return ch, nil
}

func (rt *readlineEventTracer) DeleteSubscriber(name string) {
	close(rt.eventSubscribers[name])
	rt.lock.Lock()
	delete(rt.eventSubscribers, name)
	rt.lock.Unlock()

	// disable tracing if there is no available subscriber
	if len(rt.eventSubscribers) == 0 {
		rt.stopTracing()
	}
}

func ReadlineEventToLogEvent(event *ReadlineEvent) *zerolog.Event {
	return zerolog.Dict().
		Uint64("time", event.Time).
		Uint32("pid", event.Tgid).
		Uint32("ppid", event.ParentTgid).
		Uint32("ns_pid", event.NsTgid).
		Uint32("ns_ppid", event.NsParentTgid).
		Str("comm", event.TaskComm).
		Str("readline", event.Readline)
}
