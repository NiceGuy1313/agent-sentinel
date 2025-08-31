#!/bin/bash
set -e

scripts/start_all.sh
scripts/novnc_startup.sh
# ./scripts/sandbox.sh

python scripts/http_server.py > scripts/server_logs.txt 2>&1 &

echo "✨ Computer Use Demo is ready!"
echo "➡️  Open http://localhost:8080 in your browser to begin"

# Keep the container running
tail -f /dev/null
