#!/bin/bash
# Small representative audit-LLM comparison: one attack type (default
# direct_task_inject) x sandbox defense, agent fixed on claude-sonnet-4-5,
# audit backend = Claude vs gpt-oss:20b. Keeps lab-API usage low.
cd /home/agentsentinel/test/agent-sentinel/tests/scripts || exit 1
ATTACK="${1:-direct_task_inject}"
PY=~/.local/py311/bin/python3.11
SUMMARY="cmp_results/SAMPLE_SUMMARY.txt"
TASKS=all_attack_task.json

{
  echo "=== AgentSentinel audit-LLM comparison (SAMPLE: $ATTACK) ==="
  echo "agent model (fixed): claude-sonnet-4-5-20250929   defense: sandbox"
  echo "audit backends: A) claude-sonnet-4-5   B) gpt-oss:20b (Ollama, local)"
  echo "OVERALL_START $(date -Iseconds)"
} > "$SUMMARY"

echo "CLAUDE_AUDIT_START $(date -Iseconds)" >> "$SUMMARY"
$PY run_all_tasks.py -c claude_audit_config.json -t "$TASKS" -a "$ATTACK" -d sandbox -o "cmp_results/sample_claude" > "cmp_results/sample_claude.stdout" 2>&1
echo "CLAUDE_AUDIT_END   $(date -Iseconds) rc=$?" >> "$SUMMARY"

sudo -n pkill -SIGINT agent-sentinel 2>/dev/null
docker ps -q | xargs -r docker stop >/dev/null 2>&1

echo "GPTOSS_AUDIT_START $(date -Iseconds)" >> "$SUMMARY"
$PY run_all_tasks.py -c gptoss_audit_config.json -t "$TASKS" -a "$ATTACK" -d sandbox -o "cmp_results/sample_gptoss" > "cmp_results/sample_gptoss.stdout" 2>&1
echo "GPTOSS_AUDIT_END   $(date -Iseconds) rc=$?" >> "$SUMMARY"

sudo -n pkill -SIGINT agent-sentinel 2>/dev/null
docker ps -q | xargs -r docker stop >/dev/null 2>&1

echo "OVERALL_END $(date -Iseconds)" >> "$SUMMARY"
echo "DONE"
