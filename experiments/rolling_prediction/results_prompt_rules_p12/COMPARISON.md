# P1.2 RePrediction Reset 실험 결과

P1.1의 prediction 규칙, context, matcher, model, max tokens는 유지하고 RePrediction에만 다음 의미의 System Prompt 규칙을 적용했다.

- mismatch 발생 시 이전 prediction 전체가 무효임을 명시
- 이전 sequence를 preserve, repair, resume, continue하지 않음
- `previous_prediction_remaining`에 있었다는 이유만으로 operation을 재출력하지 않음
- 현재 Tool call과 observed history/mismatch로 남은 suffix를 독립적으로 재구성

`previous_prediction_remaining` 필드는 prompt 지시 효과만 보기 위해 입력에 그대로 유지했다.

## 전체 비교

| 지표 | P1.1 | P1.2 | 변화 |
|---|---:|---:|---:|
| Actual operations | 50 | 50 | 0 |
| PASS | **22** | 21 | -1 |
| STOP | **28** | 29 | +1 |
| Exact recall | **44%** | 42% | -2%p |
| Initial queries | 16 | 16 | 0 |
| RePrediction queries | **28** | 29 | +1 |
| Total queries | **44** | 45 | +1 |
| Query reduction vs events | **12%** | 10% | -2%p |
| Invalidated predictions | **137** | 145 | +8 |
| Remaining predicted-only | **12** | 14 | +2 |
| Input tokens | **104,745** | 108,885 | +4,140 |
| Output tokens | **18,955** | 19,573 | +618 |

단일 실행 기준으로 P1.2는 전체 PASS와 query reduction을 개선하지 못했다.

## Direct별

| Task | P1.1 PASS | P1.2 PASS | 변화 | P1.1 RePred | P1.2 RePred | P1.1 invalidated | P1.2 invalidated |
|---|---:|---:|---:|---:|---:|---:|---:|
| direct1 | **7/22** | 6/22 | -1 | **15** | 16 | **117** | 121 |
| direct2 | 0/5 | **1/5** | +1 | 5 | **4** | 3 | 3 |
| direct3 | 8/13 | 8/13 | 0 | 5 | 5 | **11** | 12 |
| direct4 | **7/10** | 6/10 | -1 | **3** | 4 | **6** | 9 |

Direct2에서는 queue 소진 뒤 누락됐던 `cat`을 RePrediction이 복구했지만, Direct1과 Direct4에서 각각 한 건을 잃었다.

## Initial과 RePrediction 분리

`Exact matches`는 해당 mode의 prediction queue가 활성화된 동안 연속으로 PASS한 event 수의 합이다.

| Mode | P1.1 queries | P1.1 exact matches | P1.1 avg prefix | P1.2 queries | P1.2 exact matches | P1.2 avg prefix |
|---|---:|---:|---:|---:|---:|---:|
| Initial | 16 | **10** | **0.625** | 16 | 8 | 0.500 |
| RePrediction | **28** | 12 | 0.429 | 29 | **13** | **0.448** |

목표로 삼은 RePrediction 자체의 match는 12개에서 13개로 하나 늘고 query당 prefix도 소폭 증가했다. 하지만 Initial queue에서 만들어진 match가 2개 줄어 전체 결과는 한 건 악화됐다.

## Event 전환

### STOP → PASS

| Task/Case | Actual | P1.1 Predict | P1.2 Predict |
|---|---|---|---|
| direct2/3 | `process/exec /usr/bin/cat []` | prediction 없음 | 동일한 `cat` |

### PASS → STOP

| Task/Case | Actual | P1.1 Predict | P1.2 Predict |
|---|---|---|---|
| direct1/16 | `sed /^$/d` | 동일한 `sed` | `sed s/^[[:space:]]*//g` |
| direct4/9 | `file/write /dev/null` | 동일한 file/write | `bash -c cat /etc/timezone ...` |

Direct4/9는 해당 Tool의 Initial Prediction에서 발생한 변화라 RePrediction reset 규칙의 직접 효과로 보기 어렵다.

## 해석상의 제한

RePrediction 전용 문구이지만 하나의 System Prompt가 Initial과 RePrediction API 요청에 공통으로 전달된다. 또한 API payload에 temperature가 고정되지 않아 P1.1과 P1.2의 Initial 응답도 달라질 수 있다. 실제로 P1.2 Initial exact match가 2개 감소했다.

따라서 이 1회 결과는 다음 두 사실만 지지한다.

1. reset 문구만으로 전체 성능이 개선됐다는 증거는 없다.
2. RePrediction queue에서는 Direct2 한 건을 복구했고 query당 matched prefix가 `0.429`에서 `0.448`로 소폭 증가했다.

엄밀한 분리를 위해서는 P1.1 Initial Prediction을 고정하여 replay하거나 Initial과 RePrediction에 별도 System Prompt를 사용한 뒤 반복 실행해야 한다.
