package tracer

import (
	"bufio"
	"bytes"
	"encoding/binary"
	"errors"
	"fmt"
	"github.com/cilium/ebpf/link"
	"github.com/cilium/ebpf/ringbuf"
	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
	"golang.org/x/sys/unix"
	"strings"
	"sync"
	"syscall"
)

type processEventTracer struct {
	bpfObjs          *tracingObjects
	bpfLinks         []link.Link
	ringbufReader    *ringbuf.Reader
	eventSubscribers map[string]chan<- interface{}
	lock             sync.Mutex
}

func newProcessEventTracer(bpfObjs *tracingObjects) (*processEventTracer, error) {
	pt := &processEventTracer{
		bpfObjs:          bpfObjs,
		eventSubscribers: make(map[string]chan<- interface{}),
	}

	return pt, nil
}

func (pt *processEventTracer) startTracing() error {
	l, err := link.Kprobe("__x64_sys_execve", pt.bpfObjs.KprobeSyscallExecve, nil)
	if err != nil {
		log.Error().Err(err).Msg("Attaching __x64_sys_execve failed")
		return err
	}
	pt.bpfLinks = append(pt.bpfLinks, l)

	l, err = link.Kprobe("__x64_sys_execveat", pt.bpfObjs.KprobeSyscallExecveat, nil)
	if err != nil {
		log.Error().Err(err).Msg("Attaching __x64_sys_execveat failed")
		return err
	}
	pt.bpfLinks = append(pt.bpfLinks, l)

	l, err = link.AttachRawTracepoint(link.RawTracepointOptions{
		Name:    "sched_process_fork",
		Program: pt.bpfObjs.TracepointSchedSchedProcessFork,
	})
	if err != nil {
		log.Error().Err(err).Msg("Attaching sched_process_fork failed")
		return err
	}
	pt.bpfLinks = append(pt.bpfLinks, l)

	l, err = link.AttachRawTracepoint(link.RawTracepointOptions{
		Name:    "sched_process_exec",
		Program: pt.bpfObjs.TracepointSchedSchedProcessExec,
	})
	if err != nil {
		log.Error().Err(err).Msg("Attaching sched_process_exec failed")
		return err
	}
	pt.bpfLinks = append(pt.bpfLinks, l)

	l, err = link.AttachRawTracepoint(link.RawTracepointOptions{
		Name:    "sched_process_exit",
		Program: pt.bpfObjs.TracepointSchedSchedProcessExit,
	})
	if err != nil {
		log.Error().Err(err).Msg("Attaching sched_process_exit failed")
		return err
	}
	pt.bpfLinks = append(pt.bpfLinks, l)

	l, err = link.Kprobe("security_bprm_check", pt.bpfObjs.KprobeSecurityBprmCheck, nil)
	if err != nil {
		log.Error().Err(err).Msg("Attaching security_bprm_check failed")
		return err
	}
	pt.bpfLinks = append(pt.bpfLinks, l)

	l, err = link.AttachLSM(link.LSMOptions{
		Program: pt.bpfObjs.TaskKill,
	})
	if err != nil {
		log.Error().Err(err).Msg("Attaching lsm_task_kill failed")
		return err
	}

	// create ringbuf reader
	pt.ringbufReader, err = ringbuf.NewReader(pt.bpfObjs.ProcessEvents)
	if err != nil {
		log.Error().Err(err).Msg("Creating ringbuf reader failed")
		return err
	}

	// start callback of process event
	go pt.handleProcessEvents()

	log.Info().Msg("process tracer started")
	return nil
}

func (pt *processEventTracer) stopTracing() {
	for _, l := range pt.bpfLinks {
		if err := l.Close(); err != nil {
			log.Error().Err(err).Msg("Unattaching sched_process_exec failed")
		}
	}
	pt.bpfLinks = make([]link.Link, 0)

	if pt.ringbufReader != nil {
		if err := pt.ringbufReader.Close(); err != nil {
			log.Error().Err(err).Msg("Closing ringbuf reader failed")
		}
	}
	pt.ringbufReader = nil

	// close channel if subscribers are available
	if len(pt.eventSubscribers) > 0 {
		for _, sub := range pt.eventSubscribers {
			close(sub)
		}
		pt.eventSubscribers = make(map[string]chan<- interface{})
	}

	log.Info().Msg("process tracer stopped")
}

func (pt *processEventTracer) Close() {
	pt.stopTracing()
}

func (pt *processEventTracer) handleProcessEvents() {
	for {
		record, err := pt.ringbufReader.Read()
		if err != nil {
			if errors.Is(err, ringbuf.ErrClosed) {
				log.Info().Msg("ringbuf reader closed")
				return
			}
			log.Err(err).Msg("ringbuf read failed")
			continue
		}

		event, err := pt.postEventHandle(record.RawSample)
		if err != nil {
			continue
		}

		log.Debug().
			Dict("data", processEventToLogEvent(event)).Msg("process_event_record")

		for _, sub := range pt.eventSubscribers {
			sub <- event
		}
	}
}

func (pt *processEventTracer) postEventHandle(raw []byte) (*ProcessEvent, error) {
	buffer := bytes.NewBuffer(raw)
	var header ProcessEventHeader

	if err := binary.Read(buffer, binary.LittleEndian, &header); err != nil {
		log.Err(err).Msg("Parse ringbuf event failed")
		return nil, err
	}

	event := &ProcessEvent{
		Time:         header.Time,
		Flag:         header.Flag,
		ParentPid:    header.ParentPid,
		ParentTgid:   header.ParentTgid,
		NsParentPid:  header.NsParentPid,
		NsParentTgid: header.NsParentTgid,
		ChildPid:     header.ChildPid,
		ChildTgid:    header.ChildTgid,
		NsChildPid:   header.NsChildPid,
		NsChildTgid:  header.NsChildTgid,
		Type:         header.Type,
	}

	switch header.Type {
	case ProcessEventTypeFork:
		break
	case ProcessEventTypeExec:
		fallthrough
	case ProcessEventTypeBprmCheck:
		var processExecEvent tracingProcessExecEvent

		if err := binary.Read(buffer, binary.LittleEndian, &processExecEvent); err != nil {
			log.Err(err).Msg("Parse ringbuf event failed")
			return nil, err
		}

		event.Syscall = processExecEvent.Syscall
		event.ExecutableCtime = processExecEvent.Ctime
		event.ExecutableDev = processExecEvent.Dev
		event.ExecutableInode = processExecEvent.Inode
		event.ExecutablePath = unix.ByteSliceToString(processExecEvent.Filepath[:])
		args, err := parsingArgsArray(processExecEvent.ArgsArr[:])
		if err == nil {
			event.Args = args
		} else {
			event.Args = make([]string, 0)
		}
	case ProcessEventTypeExit:
		break
	case ProcessEventTypeKill:
		var processKillEvent tracingProcessKillEvent

		if err := binary.Read(buffer, binary.LittleEndian, &processKillEvent); err != nil {
			log.Err(err).Msg("Parse ringbuf event failed")
			return nil, err
		}

		event.Syscall = processKillEvent.Syscall
		event.Signal = syscall.Signal(processKillEvent.Signal)
		event.TargetNSTgid = processKillEvent.TargetNsTgid
	}

	return event, nil
}

func (pt *processEventTracer) AddSubscriber(name string) (<-chan interface{}, error) {
	ch := make(chan interface{})
	pt.lock.Lock()
	pt.eventSubscribers[name] = ch
	pt.lock.Unlock()

	// enable tracing
	// fixme: same subscribe name may result in attaching the bpf program twice
	if len(pt.eventSubscribers) == 1 {
		err := pt.startTracing()
		if err != nil {
			return nil, err
		}
	}

	return ch, nil
}

func (pt *processEventTracer) DeleteSubscriber(name string) {
	pt.lock.Lock()
	delete(pt.eventSubscribers, name)
	pt.lock.Unlock()

	// disable tracing if there is no available subscriber
	if len(pt.eventSubscribers) == 0 {
		pt.stopTracing()
	}
}

func parsingArgsArray(raw []byte) ([]string, error) {
	// log.Debug().Msgf("raw: %+v", raw)

	reader := bufio.NewReader(bytes.NewBuffer(raw))

	var length int32
	var num int32

	if err := binary.Read(reader, binary.LittleEndian, &length); err != nil {
		return nil, err
	}

	if length == 0 {
		return nil, fmt.Errorf("process_tracer: empty argv")
	}

	if err := binary.Read(reader, binary.LittleEndian, &num); err != nil {
		return nil, err
	}

	args := make([]string, 0)
	for reader.Size() > 0 {
		b, err := reader.Peek(1)
		if err != nil {
			break
		}

		if b[0] == 0 {
			break
		}

		arg, err := reader.ReadString(0)
		if err != nil {
			break
		}

		args = append(args, strings.Trim(arg, string(byte(0))))
	}

	return args, nil
}

func processEventToLogEvent(event *ProcessEvent) *zerolog.Event {
	output := zerolog.Dict().
		Uint64("time", event.Time).
		Uint32("flag", event.Flag).
		Uint32("type", event.Type).
		Uint32("parent_pid", event.ParentPid).
		Uint32("parent_tgid", event.ParentTgid).
		Uint32("ns_parent_pid", event.NsParentPid).
		Uint32("ns_parent_tgid", event.NsParentTgid).
		Uint32("child_pid", event.ChildPid).
		Uint32("child_tgid", event.ChildTgid).
		Uint32("ns_child_pid", event.NsChildPid).
		Uint32("ns_child_tgid", event.NsChildTgid)

	if event.Type == ProcessEventTypeExec || event.Type == ProcessEventTypeBprmCheck {
		output = output.Uint32("syscall", event.Syscall).
			Uint64("ctime", event.ExecutableCtime).
			Uint32("device", event.ExecutableDev).
			Uint32("inode", event.ExecutableInode).
			Str("executable_path", event.ExecutablePath).
			Strs("args", event.Args)
	} else if event.Type == ProcessEventTypeKill {
		output = output.Uint32("syscall", event.Syscall).
			Str("signal", event.Signal.String()).
			Uint32("target_ns_tgid", event.TargetNSTgid)
	}

	return output
}
