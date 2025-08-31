package tracer

import (
	"fmt"
)

func (pp *PathPattern) Unify() (*PathPatternEntry, error) {
	entry := &PathPatternEntry{}

	if len(pp.Prefix) > MaxPathPatternLength {
		return nil, fmt.Errorf("trace_unify: path pattern length exceeds maximum allowed length")
	}

	copy(entry.Buffer[:], pp.Prefix)

	return entry, nil
}
