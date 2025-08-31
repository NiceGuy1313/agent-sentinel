package audit

import (
	"bytes"
	"encoding/binary"
	"github.com/rs/zerolog/log"
	"agent-sentinel/tracer"
	"net"
	"strings"
)

const AgentProcessName = "main_process_of_agent"

// process chain
func (audit *Audit) NewTransformTraceRecordToProcessTree(pid uint32, record map[uint32]*ProcessEventTable) *ProcessTree {
	tree := &ProcessTree{
		&ProcessNode{
			Type: AgentProcessName,
			Pid:  uint32(audit.traceCTR.nsRootPid),
		},
	}
	procTable, ok := record[pid]
	if !ok {
		return tree
	}

	var previousNode *ProcessNode

	for procTable != nil {
		execEvent := procTable.GetExecEvent()
		fileEvents := procTable.GetFileEvents(audit.config.EventCountLimit)
		netEvents := procTable.GetNetEvents(audit.config.EventCountLimit)
		readlineEvents := procTable.GetReadlineEvents(audit.config.EventCountLimit)

		cmdline := strings.Join(execEvent.Args, " ")
		isBash := strings.Contains(cmdline, "bash")

		typeStr := "fork"
		if execEvent.Type == tracer.ProcessEventTypeExec {
			typeStr = "exec"
			if previousNode != nil {
				if previousNode.Type == "fork" {
					// TODO: Can these properties be ignored?
					previousNode.ExecutablePath = execEvent.ExecutablePath
					previousNode.Cmdline = cmdline
					previousNode.IsBash = isBash
				}
			}
		}

		node := &ProcessNode{
			Parent:         nil,
			Time:           execEvent.Time,
			Type:           typeStr,
			Pid:            execEvent.NsChildTgid,
			ExecutablePath: execEvent.ExecutablePath,
			Cmdline:        cmdline,
			IsBash:         isBash,
		}

		// node connection
		if previousNode != nil {
			previousNode.Parent = node
			node.Children = []*ProcessNode{previousNode}
		}

		if len(readlineEvents) > 0 {
			readline := make([]string, 0)
			for _, event := range readlineEvents {
				readline = append(readline, event.Readline)
			}
			node.Readline = readline
		}

		if len(fileEvents) > 0 {
			fileOps := make([]*FileOperation, 0)
			for _, event := range fileEvents {
				if QueryFileOperationCache(event, audit.cache, true) != AUDIT_OP_NOT_FOUND_IN_CACHE {
					continue
				}

				fileOp := &FileOperation{
					Type: getFileOperationType(event),
					Path: event.Path,
				}

				if event.Type == tracer.FileEventTypeInodeRename {
					fileOp.NewPath = event.NewPath
				}

				fileOps = append(fileOps, fileOp)
			}
			node.FileOps = fileOps
		}

		if len(netEvents) > 0 {
			netOps := make([]*NetOperation, 0)
			for _, event := range netEvents {
				domain := ""
				if audit.DNSCache != nil {
					domain, _ = audit.DNSCache.IP2Domain(event.RemoteIP)
				}

				if QueryNetOperationCache(event, domain, audit.cache, true) != AUDIT_OP_NOT_FOUND_IN_CACHE {
					continue
				}

				netOp := &NetOperation{
					Type:         getNetOperationType(event),
					RemotePort:   event.RemotePort,
					RemoteIP:     event.RemoteIP.String(),
					RemoteDomain: domain,
				}

				netOps = append(netOps, netOp)
			}

			node.NetOps = netOps
		}

		previousNode = node
		procTable, ok = record[execEvent.ParentTgid]
		if !ok {
			break
		}
	}

	if previousNode != nil {
		tree.RootNode.Children = append(tree.RootNode.Children, previousNode)
	}

	return tree
}

// FIXME: refactor
func (audit *Audit) TransformTraceRecordToProcessTree(record *TraceRecord) *ProcessTree {
	tree := &ProcessTree{}
	treeMap := make(map[uint32]*ProcessNode)

	log.Debug().Msgf("process_tree: record %+v", record)

	// init root process
	tree.RootNode = &ProcessNode{
		Pid:            uint32(audit.traceCTR.nsRootPid),
		FileMap:        make(map[FileOperation]int),
		NetMap:         make(map[NetOperation]int),
		ExecutablePath: AgentProcessName,
		Parent:         nil,
	}
	// always pointer to the newest process
	treeMap[uint32(audit.traceCTR.nsRootPid)] = tree.RootNode

	for _, event := range record.ProcessEventSet {
		ppid := uint32(0)
		typeStr := ""
		if event.Type == tracer.ProcessEventTypeFork {
			// fork: generate new process
			ppid = event.NsParentTgid
			typeStr = "fork"
		} else {
			// skip the bprm check
			if event.Type == tracer.ProcessEventTypeBprmCheck || event.Type == tracer.ProcessEventTypeExit || event.Type == tracer.ProcessEventTypeFork {
				continue
			}

			// ProcessEventTypeExec: replace current process
			ppid = event.NsChildTgid
			typeStr = "exec"
		}

		// only record the dependent process
		if parentNode, ok := treeMap[ppid]; ok {
			exePath := ""
			cmdline := ""
			if event.Type == tracer.ProcessEventTypeExec {
				exePath = event.ExecutablePath
				cmdline = strings.Join(event.Args, " ")
			} else {
				// fork process
				exePath = parentNode.ExecutablePath
				cmdline = parentNode.Cmdline
			}

			// fixme: according to readline event ???
			isBash := false
			if strings.Contains(exePath, "bash") {
				isBash = true
			}

			node := &ProcessNode{
				Time:           event.Time,
				Type:           typeStr,
				Pid:            event.NsChildTgid,
				ExecutablePath: exePath,
				// TODO: preserve ?
				Cmdline: cmdline,
				IsBash:  isBash,
				FileMap: make(map[FileOperation]int),
				NetMap:  make(map[NetOperation]int),
			}

			node.Parent = parentNode
			parentNode.Children = append(parentNode.Children, node)
			treeMap[node.Pid] = node
		}
	}

readlineLoop:
	for _, event := range record.ReadlineEventSet {
		if node, ok := treeMap[event.NsTgid]; ok {
			if node.IsBash == false {
				node.IsBash = true
			}

			// consider the timestamp
			for event.Time < node.Time {
				if node.Parent == nil {
					continue readlineLoop
				}
				node = node.Parent
			}

			node.Readline = append(node.Readline, event.Readline)
		}
	}

	// log.Debug().Msg("process_tree: readline")

fileLoop:
	for _, event := range record.FileEventSet {
		// log.Debug().Msgf("process_tree: start file op event %+v", event)

		// ignore if it is at cache
		if QueryFileOperationCache(event, audit.cache, true) != AUDIT_OP_NOT_FOUND_IN_CACHE {
			continue
		}

		// log.Debug().Msgf("process_tree: done cache file op event %+v", event)

		if node, ok := treeMap[event.NsTgid]; ok {
			// time sequence
			for event.Time < node.Time {
				if node.Parent == nil {
					continue fileLoop
				}
				node = node.Parent
			}

			fileOp := FileOperation{
				Type: getFileOperationType(event),
				Path: event.Path,
			}

			if event.Type == tracer.FileEventTypeInodeRename {
				fileOp.NewPath = event.NewPath
			}

			if _, ok = node.FileMap[fileOp]; !ok {
				node.FileMap[fileOp] = 1
				node.FileOps = append(node.FileOps, &fileOp)
			}
		}

		// log.Debug().Msgf("process_tree: done all file op event %+v", event)
	}

	// log.Debug().Msg("process_tree: fileop")

netLoop:
	for _, event := range record.NetEventSet {
		domain := ""
		if audit.DNSCache != nil {
			domain, _ = audit.DNSCache.IP2Domain(event.RemoteIP)
		}

		// log.Debug().Msgf("process_tree: start net op event %+v", event)

		// ignore if it is at cache
		if QueryNetOperationCache(event, domain, audit.cache, true) != AUDIT_OP_NOT_FOUND_IN_CACHE {
			continue
		}

		// log.Debug().Msgf("process_tree: done cache net op event %+v", event)

		// key := getIPKey(event.Raddr, event.Rport)
		if node, ok := treeMap[event.NsTgid]; ok {
			// time sequence
			for event.Time < node.Time {
				if node.Parent == nil {
					continue netLoop
				}
				node = node.Parent
			}

			netOp := NetOperation{
				Type:         getNetOperationType(event),
				RemotePort:   event.RemotePort,
				RemoteIP:     event.RemoteIP.String(),
				RemoteDomain: domain,
			}

			// ignore if it is at cache

			if _, ok = node.NetMap[netOp]; !ok {
				node.NetMap[netOp] = 1
				node.NetOps = append(node.NetOps, &netOp)
			}
		}

		// log.Debug().Msgf("process_tree: done all net op event %+v", event)
	}

	// log.Debug().Msg("process_tree: netop")

	return tree
}

func getIPKey(ip net.IP, port uint32) string {
	tmp := make([]byte, 4)
	binary.LittleEndian.PutUint32(tmp, port)
	buf := new(bytes.Buffer)
	buf.Write(ip)
	buf.Write(tmp)
	return buf.String()
}

func getNetOperationType(event *tracer.SocketEvent) string {
	switch event.Type {
	case tracer.SocketEventTypeConnect:
		return NET_OP_SEND
	case tracer.SocketEventTypeListen:
		return NET_OP_LISTEN
	case tracer.SocketEventTypeAccept:
		return NET_OP_LISTEN
	case tracer.SocketEventTypeAcceptExit:
		return NET_OP_RECV
	}

	// unreachable
	return "N/A"
}

func getFileOperationType(event *tracer.FileEvent) string {
	t := FILE_OP_READ
	switch event.Type {
	case tracer.FileEventTypeFileOpen:
		if isRead(event.AccMode) && isWrite(event.AccMode) {
			t = FILE_OP_READ_WRITE
		} else if isWrite(event.AccMode) {
			t = FILE_OP_WRITE
		} else {
			t = FILE_OP_READ
		}
	case tracer.FileEventTypeInodeUnlink:
		t = FILE_OP_UNLINK
	case tracer.FileEventTypeInodeRename:
		t = FILE_OP_RENAME
	}
	return t
}

func isRead(mode uint32) bool {
	return mode&tracer.MayRead != 0
}

func isWrite(mode uint32) bool {
	return mode&tracer.MayWrite != 0
}

func isAppend(mode uint32) bool {
	return mode&tracer.MayAppend != 0
}

func isExec(mode uint32) bool {
	return mode&tracer.MayExec != 0
}
