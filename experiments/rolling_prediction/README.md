# Rolling Process Prediction Replay

`retry3`의 Tool 구간에서 발생한 Process Exec STOP 40건을 시간순으로 추출하고, LLM의
process prediction sequence와 offline replay 방식으로 비교한다.

이번 실험은 file/network/kill event, syscall prediction, AgentSentinel binary cache 및
SAFE/UNSAFE 판단을 다루지 않는다. 측정값은 단순히 다음 두 수의 비교다.

```text
Existing Process Exec STOP count
Rolling Prediction LLM query count
```

## 실행

Repository `.env`에 `ANTHROPIC_API_KEY`가 있어야 한다.

```bash
python3 experiments/rolling_prediction/rolling_predict.py direct1
python3 experiments/rolling_prediction/rolling_predict.py all --resume
```

한 matching policy만 실행할 수도 있다.

```bash
python3 experiments/rolling_prediction/rolling_predict.py all --policy executable_only
python3 experiments/rolling_prediction/rolling_predict.py all --policy executable_args
```

테스트:

```bash
python3 -m unittest experiments/rolling_prediction/test_rolling_prediction.py
```

실행 후 task별 결과와 모든 LLM query/response의 통합 색인을 다시 생성하려면:

```bash
python3 experiments/rolling_prediction/report_results.py
```

생성물은 `results/TASK_AND_QUERY_REPORT.md`와 `results/query_response_log.jsonl`이다.

## Rolling mismatch 처리

Runtime에서는 mismatch를 일으킨 현재 STOP event까지 관찰할 수 있다. 따라서 re-prediction에는
그 event를 `observed_process_exec_history`와 `current_mismatch_event`로 제공하고, Predictor가
현재 event를 첫 항목으로 확인한 뒤 이후 trajectory를 예측하도록 한다. 현재보다 뒤의 actual
event는 절대 제공하지 않는다.

동일 event가 re-prediction 후에도 match되지 않으면 fallback으로 기록하고 다음 event로 진행한다.
각 actual event마다 re-prediction은 최대 한 번만 허용한다.

## 결과 구조

```text
results/
  SUMMARY.md
  summary.json
  direct3/
    executable_only/
      query_001_input.json
      query_001_prediction.json
      replay.json
      summary.json
    executable_args/
      ...
```

두 policy가 동일한 최초 context를 사용하도록 task별 initial API response는 공유하되, 양쪽 결과
디렉터리에 각각 저장한다. mismatch 시점이 달라진 뒤의 rolling query는 policy별로 독립 실행한다.
`--resume`은 이미 `summary.json`이 있는 task/policy를 다시 호출하지 않고 aggregate 결과에 포함한다.
