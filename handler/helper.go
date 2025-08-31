package handler

import (
	"agent-sentinel/audit"
)

func removeProcessEventFromRecord(record *audit.TraceRecord, tgid uint32) {
	foundIndex := make([]int, 0)

	for i, e := range record.ProcessEventSet {
		if e.ChildTgid == tgid {
			foundIndex = append(foundIndex, i)
		}
	}

	// reverse
	i := len(foundIndex) - 1
	for i > 0 {
		j := foundIndex[i]

		if j == len(record.ProcessEventSet)-1 {
			record.ProcessEventSet = record.ProcessEventSet[:len(record.ProcessEventSet)-1]
		} else {
			// case 2: first switch it with the last element, then resize the slice
			record.ProcessEventSet[j] = record.ProcessEventSet[len(record.ProcessEventSet)-1]
			record.ProcessEventSet = record.ProcessEventSet[:len(record.ProcessEventSet)-1]
		}
		i--
	}
}
