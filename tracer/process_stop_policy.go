package tracer

import (
	"encoding/binary"
)

func (p *ProcessStopPolicyExec) Unify() (*ProcessStopPolicyEntry, error) {
	entry := &ProcessStopPolicyEntry{}

	_, err := binary.Encode(entry.Buffer[:], binary.LittleEndian, p)
	if err != nil {
		return nil, err
	}

	return entry, nil
}

func (p *ProcessStopPolicyNet) Unify() (*ProcessStopPolicyEntry, error) {
	entry := &ProcessStopPolicyEntry{}

	_, err := binary.Encode(entry.Buffer[:], binary.LittleEndian, p)
	if err != nil {
		return nil, err
	}

	return entry, nil
}

func (p *ProcessStopPolicyFile) Unify() (*ProcessStopPolicyEntry, error) {
	entry := &ProcessStopPolicyEntry{}

	_, err := binary.Encode(entry.Buffer[:], binary.LittleEndian, p)
	if err != nil {
		return nil, err
	}

	return entry, nil
}

func (p *ProcessStopPolicyKill) Unify() (*ProcessStopPolicyEntry, error) {
	entry := &ProcessStopPolicyEntry{}

	_, err := binary.Encode(entry.Buffer[:], binary.LittleEndian, p)
	if err != nil {
		return nil, err
	}

	return entry, nil
}
