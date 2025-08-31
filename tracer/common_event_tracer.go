package tracer

import (
	"github.com/cilium/ebpf/link"
	"github.com/rs/zerolog/log"
)

type CommonEventTracer struct {
	bpfObjs  *tracingObjects
	bpfLinks []link.Link
}

func newCommonEventTracer(bpfObjs *tracingObjects, args ...interface{}) (*CommonEventTracer, error) {
	rt := &CommonEventTracer{
		bpfObjs:  bpfObjs,
		bpfLinks: make([]link.Link, 0),
	}

	return rt, nil
}

func (ct *CommonEventTracer) startTracing() error {
	l, err := link.AttachRawTracepoint(link.RawTracepointOptions{
		Name:    "sys_exit",
		Program: ct.bpfObjs.TracepointRawSyscallsSysExit,
	})
	if err != nil {
		log.Error().Err(err).Msg("Attaching sys_exit failed")
		return err
	}
	ct.bpfLinks = append(ct.bpfLinks, l)

	log.Info().Msg("Common tracer started")
	return nil
}

func (ct *CommonEventTracer) stopTracing() {
	for _, l := range ct.bpfLinks {
		if err := l.Close(); err != nil {
			log.Error().Err(err).Msg("Unattaching common handler failed")
		}
	}

	log.Info().Msg("common tracer stopped")
}

func (ct *CommonEventTracer) Close() {
	ct.stopTracing()
}

func (ct *CommonEventTracer) AddSubscriber(name string) (<-chan interface{}, error) {
	if len(ct.bpfLinks) == 0 {
		err := ct.startTracing()
		if err != nil {
			return nil, err
		}
	}

	return nil, nil
}

func (ct *CommonEventTracer) DeleteSubscriber(name string) {
	return
}
