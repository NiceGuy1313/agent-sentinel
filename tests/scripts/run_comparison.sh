#!/bin/bash
# Audit-LLM comparison driver: all attacks x sandbox defense, agent fixed on
# claude-sonnet-4-5, audit backend = Claude vs gpt-oss:20b (Ollama). Records
# start/end times. Per-task timing is in each run's cmp_results/*/timing.jsonl.
cd /home/agentsentinel/test/agent-sentinel/tests/scripts || exit 1
PY=~/.local/py311/bin/python3.11
SUMMARY=cmp_results/SUMMARY.txt
TASKS=all_attack_task.json

{
  echo "=== AgentSentinel audit-LLM comparison ==="
  echo "agent model (fixed): claude-sonnet-4-5-20250929"
  echo "attacks: all (60 tasks)   defense: sandbox"
  echo "audit backends: A) claude-sonnet-4-5   B) gpt-oss:20b (Ollama)"
  echo "OVERALL_START $(date -Iseconds)"
} > "$SUMMARY"

echo "CLAUDE_AUDIT_START $(date -Iseconds)" >> "$SUMMARY"
$PY run_all_tasks.py -c claude_audit_config.json -t "$TASKS" -a all -d sandbox -o cmp_results/claude_audit > cmp_results/claude_audit.stdout 2>&1
echo "CLAUDE_AUDIT_END   $(date -Iseconds) rc=$?" >> "$SUMMARY"

# make sure nothing is left attached before the next backend
sudo -n pkill -SIGINT agent-sentinel 2>/dev/null
docker ps -q | xargs -r docker stop >/dev/null 2>&1

echo "GPTOSS_AUDIT_START $(date -Iseconds)" >> "$SUMMARY"
$PY run_all_tasks.py -c gptoss_audit_config.json -t "$TASKS" -a all -d sandbox -o cmp_results/gptoss_audit > cmp_results/gptoss_audit.stdout 2>&1
echo "GPTOSS_AUDIT_END   $(date -Iseconds) rc=$?" >> "$SUMMARY"

sudo -n pkill -SIGINT agent-sentinel 2>/dev/null
docker ps -q | xargs -r docker stop >/dev/null 2>&1

echo "OVERALL_END $(date -Iseconds)" >> "$SUMMARY"
echo "DONE"
