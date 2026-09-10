# Tool 단위 AgentSentinel Operation Prediction

Agent가 실제로 호출한 Tool의 이름과 전체 input을 실행 직전에 Predictor에게 제공하고,
그 Tool 하나가 다음 Tool 호출 전까지 만들 전체 AgentSentinel operation sequence를 한 번에 예측한다.

```bash
python3 experiments/rolling_prediction/tool_sequence_predict.py direct2
python3 experiments/rolling_prediction/tool_sequence_predict.py all
```

Initial Prediction 입력에는 AgentSentinel이 실행 전에 아는 task context, 현재 Tool 이름과 전체
input, 실제 STOP policy만 포함한다. Agent system prompt, Tool definition 전체, 완료 후 Tool result,
현재 Tool의 실제 operation과 미래 결과는 제공하지 않는다.

Operation mismatch 시 현재 event를 STOP/감사 대상으로 남기고, 기존 남은 prediction을 폐기한다.
RePrediction에는 동일 Tool call, 기존 prediction, 지금까지 관측한 operation과 현재 mismatch를 넣어
현재 mismatch 다음의 남은 suffix만 예측한다. 현재 event를 다시 맞힌 것으로 채점하지 않는다.

결과는 `results_tool_sequence/<task>/<policy>/tool_NNN.json`에 저장된다. 각 파일에는 Tool call,
각 Initial/RePrediction input/output과 실제 순차 PASS/STOP replay가 들어간다. 대상은
process `exec`/`signal`, file `read`/`write`/`read_write`/`delete`/`rename` 및 network
`message_send`/`message_recv`/`message_listen`이다. DNS는 AgentSentinel처럼 network domain
보강 정보로 취급한다.

예측 범위는 `audit/trace_policy.go`에서 실제 STOP policy가 선택하는 operation으로 제한한다.

- 모든 Process Exec
- File write/append 및 inode delete/rename
- 설정된 Agent core path에 대한 read
- Network connect/listen/accept-exit (`accept` 진입 이벤트는 제외)
- Agent root를 향한 `SIGKILL`, `SIGSTOP`, `SIGINT`, `SIGTERM`

이 policy snapshot은 매 prediction의 `agentsentinel_enforcement_policy` 필드에도 포함된다.

- `pre_event_pass_count`: 실제 event 발생 전에 정확히 예측하여 PASS한 operation 수
- `stop_mismatch_count`: prediction과 달라 STOP된 operation 수
- `re_prediction_queries`: mismatch 이후 남은 suffix 재예측 횟수
- `invalidated_prediction_count`: mismatch로 폐기된 기존 prediction 항목 수
- `pre_event_operation_recall`: `matched / actual`

실행 전 `ANTHROPIC_API_KEY`를 환경변수나 repository `.env`에 설정해야 한다.

## Actual ground truth

Retry3 raw Agent/Sandbox log에서 현재 STOP policy에 해당하는 실제 operation 정답지를 다시 생성한다.

```bash
python3 experiments/rolling_prediction/build_ground_truth.py
```

생성물:

- `ground_truth/direct1.json` ~ `direct4.json`: Tool별 원본 input과 Actual operation 상세
- `ground_truth/summary.json`: task별 operation 수
- `ground_truth/GROUND_TRUTH.md`: 사람이 읽기 위한 전체 정렬표

각 JSON은 원본 로그 경로, 제외 규칙, timestamp, raw log order, actor/parent PID 및
operation별 executable/args/path/endpoint를 보존한다. 큰 screenshot/base64 Tool result는 원본 로그를
참조하도록 길이만 기록하며 정답지에 복제하지 않는다.

```bash
python3 -m unittest experiments/rolling_prediction/test_rolling_prediction.py
```
