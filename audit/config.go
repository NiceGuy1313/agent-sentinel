package audit

import (
	"agent-sentinel/audit/llm"
	"time"
)

type Config struct {
	// This configures for process level cache.
	// Process level cache contains the safe processes in current task.
	// All operations from a safe process are considered safe.
	// These operations include process, file and network operations.
	// Moreover, the child processes of a safe process is also considered as a safe process.
	// A process is considered safe if the first `ProcessTraceLevel` processes in the ancestor chain of are allowed to be executed.
	// Process level cache is enabled if `ProcessTraceLevel` is a positive number. for example, only trace the main agent process if `ProcessTraceLevel` is `1`
	// enforced mode is disabled if `ProcessTraceLevel` is `-1`.
	// enforced mode for all process if `ProcessTraceLevel` is `0`.
	ProcessTraceLevel int
	// Binary level cache contains the safe executables in current task.
	// When binary level cache is enabled, a process event is considered safe if the executable path is existed in the cache.
	// It may introduce security issues because this cache ignores the related cmdline.
	BinaryLevelCache bool
	// A general timeout for a tool use.
	ToolUseTime time.Duration
	// Selected base LLM for security query
	SecurityQueryBaseLLM string
	// Customized base LLM for security query
	CustomizedSecurityQueryClient llm.Client
	// Selected base LLM for task context summarizing
	TaskCtxSummarizingBaseLLM string
	// Customized base LLM for task context summarizing
	CustomizedTaskCtxSummarizingClient llm.Client
	// Enable protection for agent process.
	SecureAgentProcess bool
	// Limit of event count for each process.
	EventCountLimit int
	// TODO: more
}
