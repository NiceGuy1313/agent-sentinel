package tracer

import (
	"bytes"
	"encoding/binary"
	"errors"
	"fmt"
	"github.com/cilium/ebpf"
	"github.com/cilium/ebpf/link"
	"github.com/cilium/ebpf/perf"
	"github.com/cilium/ebpf/ringbuf"
	"github.com/google/gopacket"
	"github.com/google/gopacket/layers"
	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
	"sync"
)

type DNSEventTracer struct {
	bpfObjs          *tracingObjects
	bpfLinks         []link.Link
	cgroupV2Path     string
	perfReader       *perf.Reader
	eventSubscribers map[string]chan<- interface{}
	lock             sync.Mutex
}

func newDNSEventTracer(bpfObjs *tracingObjects, args ...interface{}) (*DNSEventTracer, error) {
	rt := &DNSEventTracer{
		bpfObjs:          bpfObjs,
		eventSubscribers: make(map[string]chan<- interface{}),
	}

	if len(args) != 1 {
		log.Error().Msg("Missing net.Interface")
		return nil, fmt.Errorf("missing net.Interface")
	}

	cgroupV2Path, ok := args[0].(string)
	if !ok {
		log.Error().Msg("Bad container cgroup path")
		return nil, fmt.Errorf("bad container cgroup path")
	}
	rt.cgroupV2Path = cgroupV2Path

	return rt, nil
}

func (dt *DNSEventTracer) startTracing() error {
	l, err := link.AttachCgroup(link.CgroupOptions{
		Path:    dt.cgroupV2Path,
		Program: dt.bpfObjs.BpfDnsHandler,
		Attach:  ebpf.AttachCGroupInetIngress,
	})

	if err != nil {
		log.Error().Err(err).Msg("Attaching dns handler failed")
		return err
	}
	dt.bpfLinks = append(dt.bpfLinks, l)

	// create ringbuf reader
	dt.perfReader, err = perf.NewReader(dt.bpfObjs.DnsEvents, 1024)
	if err != nil {
		log.Error().Err(err).Msg("Creating perf reader failed")
		return err
	}

	// start callback of net event
	go dt.handleDNSEvents()

	log.Info().Msg("dns tracer started")
	return nil
}

func (dt *DNSEventTracer) stopTracing() {
	for _, l := range dt.bpfLinks {
		if err := l.Close(); err != nil {
			log.Error().Err(err).Msg("Unattaching dns handler failed")
		}
	}

	if dt.perfReader != nil {
		if err := dt.perfReader.Close(); err != nil {
			log.Error().Err(err).Msg("Closing perf reader failed")
		}
	}

	// notify if subscribers are available
	if len(dt.eventSubscribers) > 0 {
		for _, sub := range dt.eventSubscribers {
			close(sub)
		}
		dt.eventSubscribers = make(map[string]chan<- interface{})
	}
	log.Info().Msg("dns tracer stopped")
}

func (dt *DNSEventTracer) Close() {
	dt.stopTracing()
}

func (dt *DNSEventTracer) handleDNSEvents() {
	for {
		record, err := dt.perfReader.Read()
		if err != nil {
			if errors.Is(err, ringbuf.ErrClosed) {
				log.Info().Msg("ringbuf reader closed")
				return
			}
			log.Err(err).Msg("ringbuf read failed")
			continue
		}

		event, err := dt.postEventHandle(record.RawSample)
		if err != nil {
			continue
		}

		log.Debug().
			Dict("data", DNSEventToLogEvent(event)).Msg("dns_event_record")

		for _, sub := range dt.eventSubscribers {
			sub <- event
		}
	}
}

func (dt *DNSEventTracer) postEventHandle(rawEvent []byte) (*DNSEvent, error) {
	var metadata tracingNetEventContext
	buf := bytes.NewBuffer(rawEvent)

	if err := binary.Read(buf, binary.LittleEndian, &metadata); err != nil {
		log.Error().Err(err).Msg("parsing perf event failed")
		return nil, err
	}

	packet := gopacket.NewPacket(
		buf.Bytes(),
		layers.LayerTypeIPv4,
		gopacket.Default,
	)

	layer := packet.ApplicationLayer()
	if layer == nil {
		log.Error().Msg("Parse application layer failed")
		return nil, fmt.Errorf("parse application layer failed")
	}

	dns, ok := layer.(*layers.DNS)
	if !ok {
		log.Error().Msg("Invalid dns message")
		return nil, fmt.Errorf("invalid dns message")
	}

	// do necessary check
	if !dns.QR || len(dns.Questions) != 1 || len(dns.Answers) < 1 {
		return nil, fmt.Errorf("invalid DNS message")
	}

	event := &DNSEvent{
		Time:      metadata.Time,
		Questions: dns.Questions,
		Answers:   dns.Answers,
	}

	return event, nil
}

func (dt *DNSEventTracer) AddSubscriber(name string) (<-chan interface{}, error) {
	ch := make(chan interface{})
	dt.lock.Lock()
	dt.eventSubscribers[name] = ch
	dt.lock.Unlock()

	// enable tracing
	if len(dt.eventSubscribers) == 1 {
		err := dt.startTracing()
		if err != nil {
			return nil, err
		}
	}

	return ch, nil
}

func (dt *DNSEventTracer) DeleteSubscriber(name string) {
	close(dt.eventSubscribers[name])
	dt.lock.Lock()
	delete(dt.eventSubscribers, name)
	dt.lock.Unlock()

	// disable tracing if there is no available subscriber
	if len(dt.eventSubscribers) == 0 {
		dt.stopTracing()
	}
}

func DNSEventToLogEvent(event *DNSEvent) *zerolog.Event {
	return zerolog.Dict().
		Uint64("time", event.Time).
		Int("QuestionCount", len(event.Questions)).
		Int("AnswerCount", len(event.Answers))
}
