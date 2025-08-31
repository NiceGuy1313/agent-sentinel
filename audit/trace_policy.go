package audit

import (
	"fmt"
	"github.com/rs/zerolog/log"
	"agent-sentinel/tracer"
)

type tracePolicy struct {
	tracer            *tracer.Tracer
	processTraceLevel int
	processLevelCache map[int]int
	nsRootPid         int
	hostRootPid       int
}

func newTracePolicy(tracer *tracer.Tracer, processTraceLevel int, nsRootPid int, hostRootPid int) (*tracePolicy, error) {
	tp := &tracePolicy{
		tracer:            tracer,
		processTraceLevel: processTraceLevel,
		processLevelCache: make(map[int]int),
		nsRootPid:         nsRootPid,
		hostRootPid:       hostRootPid,
	}

	return tp, nil
}

func (tp *tracePolicy) getDefaultEnforcePolicy() *EnforcePolicy {
	ep := &EnforcePolicy{
		Exec: &tracer.ProcessStopPolicyExec{
			Common: tracer.ProcessStopCommonAlwaysStop,
		},
		Net: &tracer.ProcessStopPolicyNet{
			Common: tracer.ProcessStopCommonAlwaysStop,
		},
		File: &tracer.ProcessStopPolicyFile{
			Common:         0,
			Flag:           0,
			FilePermission: tracer.MayWrite | tracer.MayAppend,
			NSRootTgid:     uint32(tp.nsRootPid),
		},
		Kill: nil,
	}

	return ep
}

func (tp *tracePolicy) SetEnforcePolicy(policies []*EnforcePolicy) error {
	var err error

	tp.processLevelCache[tp.hostRootPid] = 1
	if tp.processTraceLevel > 0 {
		err = tp.tracer.SetProcessTraceLevel(tp.processTraceLevel)
		if err != nil {
			log.Error().Err(err).Msg("tracer_policy: set process trace level failed")
		}
		log.Debug().Msgf("trace_policy: set process trace level %d", tp.processTraceLevel)

		err = tp.tracer.AddEnforcedProcess(tp.hostRootPid)
		if err != nil {
			log.Error().Err(err).Msg("tracer_policy: add root process to enforced process failed")
			return err
		}
		log.Debug().Msgf("trace_policy: add root pid %d (%d) to enforced process map", tp.hostRootPid, tp.nsRootPid)
	}

	mergedPolicy := tp.getDefaultEnforcePolicy()

	for _, policy := range policies {
		mergedPolicy, err = tp.MergeEnforcePolicy(mergedPolicy, policy)
		if err != nil {
			return err
		}
	}

	if mergedPolicy.Exec != nil {
		err = tp.tracer.AddProcessStopPolicy(tracer.ProcessStopTypeExec, mergedPolicy.Exec)
		if err != nil {
			log.Error().Msg("tracer_policy: Add process stop exec policy failed")
			return err
		}
	}

	if mergedPolicy.File != nil {
		err = tp.tracer.AddProcessStopPolicy(tracer.ProcessStopTypeFile, mergedPolicy.File)
		if err != nil {
			log.Error().Msg("tracer_policy: Add process stop file policy failed")
			return err
		}
	}

	if mergedPolicy.Net != nil {
		err = tp.tracer.AddProcessStopPolicy(tracer.ProcessStopTypeNet, mergedPolicy.Net)
		if err != nil {
			log.Error().Msg("tracer_policy: Add process stop net policy failed")
			return err
		}
	}

	if mergedPolicy.Kill != nil {
		err = tp.tracer.AddProcessStopPolicy(tracer.ProcessStopTypeKill, mergedPolicy.Kill)
		if err != nil {
			log.Error().Msg("tracer_policy: Add process stop kill policy failed")
			return err
		}
	}

	return nil
}

func (tp *tracePolicy) MergeEnforcePolicy(s1 *EnforcePolicy, s2 *EnforcePolicy) (*EnforcePolicy, error) {
	d := &EnforcePolicy{
		Exec: s1.Exec,
		Net:  s1.Net,
		File: s1.File,
		Kill: s1.Kill,
	}

	if s2.Exec != nil {
		if d.Exec != nil {
			d.Exec.Common |= s2.Exec.Common
		} else {
			d.Exec = s2.Exec
		}
	}

	if s2.Net != nil {
		if d.Net != nil {
			d.Net.Common |= s2.Net.Common
		} else {
			d.Net = s2.Net
		}
	}

	if s2.File != nil {
		if d.File != nil {
			d.File.Common |= s2.File.Common
			d.File.Flag |= s2.File.Flag
			d.File.FilePermission |= s2.File.FilePermission
			if d.File.NSRootTgid != s2.File.NSRootTgid {
				log.Error().Msg("tracer_policy: two different root tgid detected")
				return nil, fmt.Errorf("two different root tgid detected")
			}
		} else {
			d.File = s2.File
		}
	}

	if s2.Kill != nil {
		if d.Kill != nil {
			d.Kill.Common |= s2.Kill.Common
			d.Kill.Flag |= s2.Kill.Flag

			if d.Kill.RootTgid != s2.Kill.RootTgid {
				log.Error().Msg("tracer_policy: two different root tgid detected")
				return nil, fmt.Errorf("two different root tgid detected")
			}
		} else {
			d.Kill = s2.Kill
		}
	}

	return d, nil
}

func (tp *tracePolicy) NotifyProcessFork(ppid int, pid int) {
	if parentLevel, ok := tp.processLevelCache[ppid]; ok {
		tp.processLevelCache[pid] = parentLevel + 1
		// eBPF will automatically add new process to the map
		if parentLevel < tp.processTraceLevel {
			log.Debug().Msgf("tracer_policy: add pid %d to enforced process map", pid)
		}
	} else {
		log.Error().Msgf("tracer_policy: found a untracked process %d", pid)
	}
}

func (tp *tracePolicy) NotifyProcessExec(pid int) {
	// FIXME: `exec` actually does not generate a new process. But it may run with a different executable
	//if level, ok := tp.processLevelCache[pid]; ok {
	//	tp.processLevelCache[pid] = level + 1
	//}
}

func (tp *tracePolicy) NotifyProcessExit(pid int) {
	log.Debug().Msgf("trace_policy: delete pid %d to enforced process map", pid)
	delete(tp.processLevelCache, pid)
	// eBPF will automatically remove exited process from the map
}

func (tp *tracePolicy) removeEnforcedProcess(pid int) {
	// manually remove a process from the map
	log.Debug().Msgf("trace_policy: remove pid %d to enforced process map", pid)
	_ = tp.tracer.RemoveEnforcedProcess(pid)
}
