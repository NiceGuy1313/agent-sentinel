package audit

import (
	"sync"
	"time"
)

// optimize the QPS and improve security capability

type Optimizer struct {
	timeout      time.Duration
	timeCountMap map[int]time.Duration
	traceCRT     *tracePolicy
	lock         sync.Mutex
}

func NewOptimizer(traceCRT *tracePolicy, timeout time.Duration) *Optimizer {
	op := &Optimizer{
		timeout:      timeout,
		timeCountMap: make(map[int]time.Duration),
		traceCRT:     traceCRT,
	}

	return op
}

// Optimization 1: The total time for auditing a tool use should not more than the timeout. Otherwise, it may affect the normal task completion.
func (op *Optimizer) timeAccumulating(pid int, time time.Duration) {
	op.lock.Lock()
	if sum, ok := op.timeCountMap[pid]; ok {
		op.timeCountMap[pid] = sum + time
	} else {
		op.timeCountMap[pid] = time
	}
	op.lock.Unlock()
}

func (op *Optimizer) getRemainingTime(pid int) time.Duration {
	op.lock.Lock()
	sum, ok := op.timeCountMap[pid]
	op.lock.Unlock()

	if ok {
		return op.timeout - sum
	} else {
		op.timeCountMap[pid] = 0
		return op.timeout
	}
}

func (op *Optimizer) removeTimeCount(pid int) {
	op.lock.Lock()
	delete(op.timeCountMap, pid)
	op.lock.Unlock()
}

func (op *Optimizer) clearTimeout(pid int) {
	op.lock.Lock()
	op.timeCountMap[pid] = 0
	op.lock.Unlock()
}

func (op *Optimizer) isTimeout(pid int) bool {
	op.lock.Lock()
	sum, ok := op.timeCountMap[pid]
	op.lock.Unlock()

	if ok {
		return sum > op.timeout
	}
	return false
}

func (op *Optimizer) removeTimeCountIfTimeout(pid int) {
	if op.isTimeout(pid) {
		op.removeTimeCount(pid)
		op.traceCRT.removeEnforcedProcess(pid)
	}
}

// TODO: may more Optimizations
