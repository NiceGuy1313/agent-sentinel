package audit

import (
	"fmt"
	"github.com/rs/zerolog/log"
	"github.com/twmb/murmur3"
	"agent-sentinel/tracer"
	"maps"
	"sync"
)

type ProcessEventTable struct {
	// a fork event or exec event
	execEvent      *tracer.ProcessEvent
	fileEvents     []*tracer.FileEvent
	netEvents      []*tracer.SocketEvent
	readlineEvents []*tracer.ReadlineEvent
	aliveChildNum  int
	fileMap        map[uint32]int
	netMap         map[uint32]int
	lock           sync.RWMutex
}

func NewProcessEventTable() *ProcessEventTable {
	return &ProcessEventTable{
		execEvent:      nil,
		fileEvents:     make([]*tracer.FileEvent, 0),
		netEvents:      make([]*tracer.SocketEvent, 0),
		readlineEvents: make([]*tracer.ReadlineEvent, 0),
		aliveChildNum:  0,
		fileMap:        make(map[uint32]int),
		netMap:         make(map[uint32]int),
		lock:           sync.RWMutex{},
	}
}

func (pet *ProcessEventTable) RLock() {
	pet.lock.RLock()
}

func (pet *ProcessEventTable) RUnlock() {
	pet.lock.RUnlock()
}

func (pet *ProcessEventTable) Lock() {
	pet.lock.Lock()
}

func (pet *ProcessEventTable) Unlock() {
	pet.lock.Unlock()
}

func (pet *ProcessEventTable) SetExecEvent(execEvent *tracer.ProcessEvent) {
	pet.lock.Lock()
	defer pet.lock.Unlock()

	pet.execEvent = execEvent
}

func (pet *ProcessEventTable) GetExecEvent() *tracer.ProcessEvent {
	pet.lock.RLock()
	defer pet.lock.RUnlock()

	return pet.execEvent
}

func (pet *ProcessEventTable) IncAliveChildProcess() {
	pet.lock.Lock()
	defer pet.lock.Unlock()

	pet.aliveChildNum++
}

func (pet *ProcessEventTable) DecAliveChildProcess() {
	pet.lock.Lock()
	defer pet.lock.Unlock()

	pet.aliveChildNum--
}

func (pet *ProcessEventTable) GetAliveChildProcess() int {
	pet.lock.RLock()
	defer pet.lock.RUnlock()

	return pet.aliveChildNum
}

func (pet *ProcessEventTable) AreAllChildProcessExited() bool {
	pet.lock.RLock()
	defer pet.lock.RUnlock()

	if pet.aliveChildNum == 0 {
		return true
	}

	return false
}

func (pet *ProcessEventTable) AddFileEvent(e *tracer.FileEvent) {
	sign, err := getSignOfFileEvent(e)

	pet.lock.Lock()
	defer pet.lock.Unlock()

	if err == nil {
		// ignore duplicated event
		if _, ok := pet.fileMap[sign]; ok {
			return
		}
		pet.fileMap[sign] = 1
	}

	pet.fileEvents = append(pet.fileEvents, e)
}

func (pet *ProcessEventTable) GetFileEvents(limit int) []*tracer.FileEvent {
	pet.lock.RLock()
	defer pet.lock.RUnlock()

	if len(pet.fileEvents) < limit {
		return pet.fileEvents
	}

	return pet.fileEvents[len(pet.fileEvents)-limit:]
}

func (pet *ProcessEventTable) DelFileEventById(id int) {
	pet.lock.Lock()
	defer pet.lock.Unlock()

	if id < 0 || id >= len(pet.fileEvents) {
		return
	}

	pet.fileEvents = append(pet.fileEvents[:id], pet.fileEvents[id:]...)
}

func (pet *ProcessEventTable) AddNetEvent(e *tracer.SocketEvent) {
	sign, err := getSignOfNetEvent(e)

	pet.lock.Lock()
	defer pet.lock.Unlock()

	if err == nil {
		// ignore duplicated event
		if _, ok := pet.netMap[sign]; ok {
			return
		}
		log.Debug().Msgf("process_event_table: %d", sign)
		pet.netMap[sign] = 1
	}

	pet.netEvents = append(pet.netEvents, e)
}

func (pet *ProcessEventTable) GetNetEvents(limit int) []*tracer.SocketEvent {
	pet.lock.RLock()
	defer pet.lock.RUnlock()

	if len(pet.netEvents) < limit {
		return pet.netEvents
	}

	return pet.netEvents[len(pet.netEvents)-limit:]
}

func (pet *ProcessEventTable) DelNetEventById(id int) {
	pet.lock.Lock()
	defer pet.lock.Unlock()

	if id < 0 || id >= len(pet.netEvents) {
		return
	}

	pet.netEvents = append(pet.netEvents[:id], pet.netEvents[id:]...)
}

func (pet *ProcessEventTable) AddReadlineEvent(e *tracer.ReadlineEvent) {
	// TODO: remove duplicate readline operations
	pet.lock.Lock()
	defer pet.lock.Unlock()

	pet.readlineEvents = append(pet.readlineEvents, e)
}

func (pet *ProcessEventTable) GetReadlineEvents(limit int) []*tracer.ReadlineEvent {
	pet.lock.RLock()
	defer pet.lock.RUnlock()

	if len(pet.readlineEvents) < limit {
		return pet.readlineEvents
	}

	return pet.readlineEvents[len(pet.readlineEvents)-limit:]
}

func (pet *ProcessEventTable) DelReadlineEventById(id int) {
	pet.lock.Lock()
	defer pet.lock.Unlock()

	pet.readlineEvents = append(pet.readlineEvents[:id], pet.readlineEvents[id:]...)
}

func CopyTraceRecord(tr map[uint32]*ProcessEventTable) map[uint32]*ProcessEventTable {
	copied := make(map[uint32]*ProcessEventTable)
	maps.Copy(copied, tr)
	return copied
}

func getSignOfFileEvent(e *tracer.FileEvent) (uint32, error) {
	h32 := murmur3.New32()

	newPath := ""
	if e.Type == tracer.FileEventTypeInodeRename {
		newPath = e.NewPath
	}

	sign := fmt.Sprintf("%s:%s:%s", getFileOperationType(e), e.Path, newPath)

	_, err := h32.Write([]byte(sign))
	if err != nil {
		log.Debug().Msg("process_event_table: generate signature of file event failed")
		return 0, err
	}

	return h32.Sum32(), nil
}

func getSignOfNetEvent(e *tracer.SocketEvent) (uint32, error) {
	h32 := murmur3.New32()

	sign := fmt.Sprintf("%s:%d:%s", getNetOperationType(e), e.RemotePort, e.RemoteIP.String())

	_, err := h32.Write([]byte(sign))
	if err != nil {
		log.Debug().Err(err).Msg("process_event_table: generate signature of net event failed")
		return 0, err
	}

	return h32.Sum32(), nil
}
