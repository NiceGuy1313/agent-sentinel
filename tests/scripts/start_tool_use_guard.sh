#!/bin/bash

log_file=""
if [ "$#" -gt 0 ]; then
    log_file="$1"
fi

model="claude-3-5-sonnet-20241022"
if [ "$#" -gt 1 ]; then
    model="$2"
fi

ANTHROPIC_API_KEY=xxx \
../../agent-sentinel -debug=1 \
-output=$log_file \
-mount-path=~/.anthropic \
-audit-without-tracer \
-model=$model