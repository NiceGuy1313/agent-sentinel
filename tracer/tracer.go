package tracer

import (
	"errors"
	"fmt"
	"github.com/cilium/ebpf"
	"github.com/cilium/ebpf/rlimit"
	"github.com/rs/zerolog/log"
	"agent-sentinel/helper"
	"slices"
)

//go:generate go run github.com/cilium/ebpf/cmd/bpf2go -type process_stop_policy_t -type process_event -type process_kill_event -type process_exec_event -type readline_event -type file_event -type file_open_event -type inode_unlink_event -type inode_rename_event -type socket_event -type sockaddr_in -type sockaddr_in6 -type net_event_context -target amd64 tracing ../ebpf/tracer/tracer.c -- -I../ebpf/headers

type Tracer struct {
	bpfObjs    tracingObjects
	opts       *Options
	commTracer BpfTracer
	tracers    map[int]BpfTracer
	mountNSID  int
	pidNSID    int
}

func NewTracer(options *Options) (*Tracer, error) {
	tracer := &Tracer{
		tracers:    make(map[int]BpfTracer),
		opts:       options,
		commTracer: nil,
	}

	if len(options.EnableTracer) == 0 {
		log.Error().Msg("tracer: no tracer enabled")
		return nil, fmt.Errorf("tracer: require at least one tracer")
	}

	if options.MountNSID == 0 || options.PidNSID == 0 {
		log.Error().Msg("tracer: invalid mount or pid namespace ID")
		return nil, fmt.Errorf("tracer: invalid mount or pid namespace ID")
	}

	err := tracer.InitAndLoadBPFPrograms()
	if err != nil {
		return nil, err
	}

	log.Info().Msgf("tracer: target mount ns id is %d", options.MountNSID)
	if err = tracer.bpfObjs.MntNsIdList.Put(uint32(0), uint32(options.MountNSID)); err != nil {
		log.Error().Err(err).Msg("Register target mount namespace id failed")
		tracer.Close()
		return nil, err
	}

	tracer.commTracer, err = newCommonEventTracer(&tracer.bpfObjs)
	if err != nil {
		return nil, err
	}

	for _, T := range options.EnableTracer {
		err = tracer.registerTracer(T)
		if err != nil {
			tracer.Close()
			return nil, err
		}
	}

	_, err = tracer.commTracer.AddSubscriber("tracer")
	if err != nil {
		tracer.Close()
		return nil, err
	}

	return tracer, nil
}

func (t *Tracer) InitAndLoadBPFPrograms() error {
	// Remove resource limits for kernels <5.11.
	if err := rlimit.RemoveMemlock(); err != nil {
		log.Error().Err(err).Msg("Removing memlock failed")
		return err
	}

	if err := loadTracingObjects(&t.bpfObjs, nil); err != nil {
		var verr *ebpf.VerifierError
		if errors.As(err, &verr) {
			fmt.Printf("%+v\n", verr)
		}
		log.Error().Err(err).Msg("Loading eBPF objects failed")
		return err
	}

	return nil
}

func (t *Tracer) Close() {
	if t.commTracer != nil {
		t.commTracer.Close()
	}

	for _, subt := range t.tracers {
		subt.Close()
	}

	_ = t.bpfObjs.Close()
}

func (t *Tracer) registerTracer(T int) error {
	switch T {
	case ProcessTracer:
		pt, err := newProcessEventTracer(&t.bpfObjs)
		if err != nil {
			log.Error().Err(err).Msg("Register process tracer failed")
			return err
		}
		t.tracers[T] = pt
		return nil
	case ReadlineTracer:
		rt, err := newReadlineEventTracer(&t.bpfObjs, t.opts.BashPath)
		if err != nil {
			log.Error().Err(err).Msg("Register readline tracer failed")
			return err
		}
		t.tracers[T] = rt
		return nil
	case SocketTracer:
		st, err := newSockOpsEventTracer(&t.bpfObjs, t.opts.CgroupPath)
		if err != nil {
			log.Error().Err(err).Msg("Register socket tracer failed")
			return err
		}
		t.tracers[T] = st
		return nil
	case DNSTracer:
		dt, err := newDNSEventTracer(&t.bpfObjs, t.opts.CgroupPath)
		if err != nil {
			log.Error().Err(err).Msg("Register dns tracer failed")
			return err
		}
		t.tracers[T] = dt
		return nil
	case FileTracer:
		ft, err := newFilePermEventTracer(&t.bpfObjs)
		if err != nil {
			log.Error().Err(err).Msg("Register file permission tracer failed")
			return err
		}
		t.tracers[T] = ft
		return nil
	default:
		log.Error().Msgf("Invalid tracer type %d", T)
		return fmt.Errorf("invalid tracer type %d", T)
	}
}

func (t *Tracer) AddSubscriber(T int, name string) (<-chan interface{}, error) {
	switch T {
	case ProcessTracer:
		fallthrough
	case ReadlineTracer:
		fallthrough
	case SocketTracer:
		fallthrough
	case DNSTracer:
		fallthrough
	case FileTracer:
		ch, err := t.tracers[T].AddSubscriber(name)
		if err != nil {
			return nil, err
		}
		log.Info().Msgf("Added subscriber %s to %d", name, T)
		return ch, nil
	default:
		log.Error().Msg(fmt.Sprintf("Invalid tracer type %d", T))
		return nil, fmt.Errorf("invalid tracer type %d", T)
	}
}

func (t *Tracer) DeleteSubscriber(T int, name string) error {
	switch T {
	case ProcessTracer:
		fallthrough
	case ReadlineTracer:
		fallthrough
	case SocketTracer:
		fallthrough
	case DNSTracer:
		fallthrough
	case FileTracer:
		t.tracers[T].DeleteSubscriber(name)
		return nil
	default:
		log.Error().Msg(fmt.Sprintf("Invalid tracer type %d", T))
		return fmt.Errorf("invalid tracer type %d", T)
	}
}

func (t *Tracer) HasTracer(T int) bool {
	if _, ok := t.tracers[T]; ok {
		return true
	}

	return false
}

func (t *Tracer) AddInterestingPID(pid uint32, host bool) error {
	if host == false {
		hpid, err := helper.GetHostPID(int(pid), t.pidNSID)
		if err != nil {
			return err
		}

		pid = uint32(hpid)
	}

	err := t.bpfObjs.InterestingPidsMap.Put(pid, uint32(DefaultInterestingPidMapValue))
	if err != nil {
		log.Error().Err(err).Msgf("tracer: adding interesting pid %d failed", pid)
		return err
	}

	log.Info().Msgf("Added interesting pid %d", pid)

	return nil
}

func (t *Tracer) RemoveInterestingPID(pid uint32, host bool) error {
	if host == false {
		hpid, err := helper.GetHostPID(int(pid), t.pidNSID)
		if err != nil {
			return err
		}

		pid = uint32(hpid)
	}

	err := t.bpfObjs.InterestingPidsMap.Delete(pid)
	if err != nil {
		log.Error().Err(err).Msgf("tracer: adding interesting pid %d failed", pid)
		return err
	}

	log.Info().Msgf("Added interesting pid %d", pid)

	return nil
}

func (t *Tracer) SetProcessTraceLevel(level int) error {
	cpus, err := ebpf.PossibleCPU()
	if err != nil {
		log.Error().Err(err).Msgf("tracer: adding core file pattern failed")
		return err
	}

	set := slices.Repeat([]uint32{uint32(level)}, cpus)
	err = t.bpfObjs.ProcessTraceLevel.Put(uint32(0), set)
	if err != nil {
		log.Error().Err(err).Msgf("tracer: setting process trace level failed")
		return err
	}

	return nil
}

func (t *Tracer) AddEnforcedProcess(pid int) error {
	err := t.bpfObjs.ProcessEnforcementMap.Put(uint32(pid), uint8(DefaultEnforcedProcessMapValue))
	if err != nil {
		log.Error().Err(err).Msgf("tracer: adding process enforcement map failed for process %d", pid)
		return err
	}

	return nil
}

func (t *Tracer) RemoveEnforcedProcess(pid int) error {
	err := t.bpfObjs.ProcessEnforcementMap.Delete(uint32(pid))
	if err != nil {
		log.Error().Err(err).Msgf("tracer: removing process enforcement map failed for process %d", pid)
		return err
	}

	return nil
}

func (t *Tracer) AddProcessStopPolicy(T int, policy ProcessStopPolicy) error {
	entry, err := policy.Unify()
	if err != nil {
		log.Error().Err(err).Msgf("tracer: adding process stop policy failed")
		return err
	}

	err = t.bpfObjs.ProcessStopPolicy.Put(uint16(T), entry)
	if err != nil {
		log.Error().Err(err).Msgf("tracer: adding process stop policy failed")
		return err
	}

	return nil
}

func (t *Tracer) GetProcessStopPolicy(T int) (*ProcessStopPolicyEntry, error) {
	var entry ProcessStopPolicyEntry
	err := t.bpfObjs.ProcessStopPolicy.Lookup(uint32(T), &entry)
	if err != nil {
		log.Error().Err(err).Msgf("tracer: getting process stop policy %d failed", T)
		return nil, err
	}

	return &entry, nil
}

func (t *Tracer) AddCoreFilePathPattern(id int, pp *PathPattern) error {
	preCUPEntry, err := pp.Unify()
	if err != nil {
		log.Error().Err(err).Msgf("tracer: adding core file pattern failed")
		return err
	}

	cpus, err := ebpf.PossibleCPU()
	if err != nil {
		log.Error().Err(err).Msgf("tracer: adding core file pattern failed")
		return err
	}

	set := make([]*PathPatternEntry, cpus)
	for i := 0; i < cpus; i++ {
		set[i] = preCUPEntry
	}

	err = t.bpfObjs.CoreFilePathPatterns.Put(uint32(id), set)
	if err != nil {
		log.Error().Err(err).Msgf("tracer: adding core file pattern failed")
		return err
	}

	return nil
}

// FIXME: maybe can be done in kernel?
func (t *Tracer) FinishEnforcementOperation(pid int) (int, error) {
	var numberOfEnforcementOperations uint8
	err := t.bpfObjs.ProcessEnforcementMap.Lookup(uint32(pid), &numberOfEnforcementOperations)
	if err != nil {
		log.Error().Err(err).Msgf("tracer: read process enforcement map failed")
		return 0, err
	}

	if numberOfEnforcementOperations > 0 {
		err = t.bpfObjs.ProcessEnforcementMap.Put(uint32(pid), numberOfEnforcementOperations-1)
		log.Error().Err(err).Msgf("tracer: update process enforcement map failed")
		return 0, err
	}

	return int(numberOfEnforcementOperations - 1), nil
}
