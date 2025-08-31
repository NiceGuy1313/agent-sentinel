package audit

import (
	"github.com/rs/zerolog/log"
	"agent-sentinel/tracer"
)

type SecureAgentProcess struct {
	info   *AgentProcessInfo
	tracer *tracer.Tracer
}

func NewSecureAgentProcess(tracer *tracer.Tracer, info *AgentProcessInfo) *SecureAgentProcess {
	return &SecureAgentProcess{
		info:   info,
		tracer: tracer,
	}
}

func (sap *SecureAgentProcess) getRequiredEnforcePolicy() *EnforcePolicy {
	killPolicy := &tracer.ProcessStopPolicyKill{
		Common:   0,
		Flag:     tracer.ProcessStopKillRootProcess,
		RootTgid: uint32(sap.info.NSPid),
		// RootTgid: uint32(3572),
	}

	fflag := uint32(0)
	if len(sap.info.CoreFilePaths) > 0 {
		fflag |= tracer.ProcessStopFileAccessCoreFiles
	}

	filePolicy := &tracer.ProcessStopPolicyFile{
		Common:         0,
		Flag:           fflag,
		FilePermission: 0,
		NSRootTgid:     uint32(sap.info.NSPid),
	}

	return &EnforcePolicy{
		File: filePolicy,
		Kill: killPolicy,
	}
}

func (sap *SecureAgentProcess) Start() {
	log.Debug().Msg("secure_agent_process: enabled")
	for id, path := range sap.info.CoreFilePaths {
		err := sap.tracer.AddCoreFilePathPattern(id, &tracer.PathPattern{Prefix: path})
		if err != nil {
			log.Error().Msgf("secure_agent_process: adding path %s with id %d to core_files_path_map failed", path, id)
			continue
		}
	}
}

func (sap *SecureAgentProcess) Query(pid int, sensitiveOp interface{}, traceRecord map[uint32]*ProcessEventTable, toolUseMsg []*ToolUseMessage, newToolUseMsg []*ToolUseMessage) (int, string) {
	switch t := sensitiveOp.(type) {
	case *tracer.ProcessEvent:
		if t.Type == tracer.ProcessEventTypeKill && (t.Flag&tracer.EventFlagProcessMayAttackRootProcess) == tracer.EventFlagProcessMayAttackRootProcess {
			log.Debug().Msg("secure_agent_process: detected sending kill signal to agent process")
			return AUDIT_OP_TERMINATE_PROCESS, "The process is sending kill signal to agent process. This may result in unpredictable behavior"
		}
	case *tracer.FileEvent:
		if t.Type == tracer.FileEventTypeFileOpen && (t.Flag&tracer.EventFlagProcessMayAttackRootProcess) == tracer.EventFlagProcessMayAttackRootProcess {
			log.Debug().Msg("secure_agent_process: detected viewing core files of agent process")
			return AUDIT_OP_TERMINATE_PROCESS, "The process is viewing core files of agent process. This may result in privacy leak"
		}
	}

	return AUDIT_OP_UNKNOWN, ""
}
