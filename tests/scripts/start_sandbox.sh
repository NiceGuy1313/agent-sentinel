#!/bin/bash

if [ "$#" -lt 1 ]; then
    echo "invalid container id"
    exit
fi

cid="$1"

log_file=""
if [ "$#" -gt 1 ]; then
    log_file="$2"
fi

model="claude-3-5-sonnet-20241022"
if [ "$#" -gt 2 ]; then
    model="$3"
fi

# load ANTHROPIC_API_KEY from the (gitignored) .env; sudo resets the env so we
# cannot rely on it being inherited.
set -a
. /home/agentsentinel/test/agent-sentinel/.env
set +a

# The bundled docker Go SDK defaults to API v1.47, but the installed daemon
# (docker.io 26.1.3) only supports up to v1.45. client.FromEnv honours this.
export DOCKER_API_VERSION=1.45

../../agent-sentinel -debug=1 \
-output=$log_file \
-cid=$cid \
-mount-path=/home/agentsentinel/.anthropic \
-audit=1 \
-process-trace-level=4 \
-binary-level-cache=1 \
-tool-use-timeout=110 \
-model=$model