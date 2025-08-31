package filters

import (
	"agent-sentinel/audit/helper"
	"agent-sentinel/tracer"
)

type FileEventFilter struct {
	rules []*FileRules
}

func NewFileEventFilter() (*FileEventFilter, error) {
	filter := &FileEventFilter{}
	err := filter.initDefaultRules()
	if err != nil {
		return nil, err
	}
	return filter, nil
}

func (f *FileEventFilter) initDefaultRules() error {
	f.rules = []*FileRules{
		// libraries access
		{
			Type: FILE_FILTER_RULE_EXCLUDE,
			Path: "/usr/lib/x86_64-linux-gnu/**",
			Op:   tracer.MayRead,
		},
		// python libraries
		{
			Type: FILE_FILTER_RULE_EXCLUDE,
			Path: "/home/computeruse/.pyenv/versions/3.11.6/lib/python3.11/site-packages/**",
			Op:   tracer.MayRead,
		},
		// devs
		{
			Type: FILE_FILTER_RULE_EXCLUDE,
			Path: "/dev/null",
			Op:   tracer.MayRead | tracer.MayWrite,
		},
		{
			Type: FILE_FILTER_RULE_EXCLUDE,
			Path: "/dev/tty",
			Op:   tracer.MayRead | tracer.MayWrite,
		},
		// tempdir
		{
			Type: FILE_FILTER_RULE_EXCLUDE,
			Path: "/tmp/**",
			Op:   tracer.MayRead | tracer.MayWrite | tracer.MayAppend,
		},
		// docker overlay2
		{
			Type: FILE_FILTER_RULE_EXCLUDE,
			Path: "/var/lib/docker/overlay2/**",
			Op:   tracer.MayRead | tracer.MayWrite | tracer.MayAppend,
		},
	}

	for _, rule := range f.rules {
		pattern, err := helper.CompileFilePattern(rule.Path)
		if err != nil {
			return err
		}

		rule.Pattern = pattern
	}

	return nil
}

func (f *FileEventFilter) Filter(e *tracer.FileEvent) bool {
	for _, rule := range f.rules {
		if rule.Type == FILE_FILTER_RULE_EXCLUDE && rule.Pattern.MatchString(e.Path) {
			if e.AccMode&rule.Op == e.AccMode {
				return true
			}

			// any file modification can be regarded a file write
			if e.Type == tracer.FileEventTypeInodeUnlink || e.Type == tracer.FileEventTypeInodeRename {
				if rule.Op&tracer.MayWrite == tracer.MayWrite {
					return true
				}
			}
		}
	}

	return false
}
