# P1.1 Prompt 실험 결과

P1의 네 규칙은 유지하고 다음 세 항목만 System Prompt에 추가했다.

1. shell token 순서가 아니라 OS 실행 인과관계에 따른 chronology 예측
2. 일부 runtime-dependent field가 불명이어도 derivable operation과 known field 유지
3. RePrediction에서 observed history를 authoritative progress로 사용하고 workflow를 재시작하지 않음

Runtime profile, symbolic schema, matcher는 변경하지 않았다.

## 전체 비교

| 지표 | P0 Baseline | P1 | P1.1 | P1 → P1.1 |
|---|---:|---:|---:|---:|
| Actual operations | 50 | 50 | 50 | 0 |
| PASS | 13 | 18 | **22** | **+4** |
| STOP | 37 | 32 | **28** | **-4** |
| Exact recall | 26% | 36% | **44%** | **+8%p** |
| Initial queries | 16 | 16 | 16 | 0 |
| RePrediction queries | 37 | 32 | **28** | **-4** |
| Total queries | 53 | 48 | **44** | **-4** |
| Query reduction vs events | -6% | 4% | **12%** | **+8%p** |
| Input tokens | 95,068 | 104,967 | 104,745 | -222 |
| Output tokens | 21,597 | 20,121 | 18,955 | -1,166 |

P0 대비 PASS는 9개 증가했고 RePrediction은 9회 감소했다. P1.1의 prompt가 더 길어졌지만 query 감소로 P1 대비 총 input token은 거의 동일하고 output token은 감소했다.

## Direct별

| Task | P0 PASS | P1 PASS | P1.1 PASS | P1 → P1.1 | P1 RePred | P1.1 RePred |
|---|---:|---:|---:|---:|---:|---:|
| direct1 | 6/22 | 6/22 | **7/22** | +1 | 16 | 15 |
| direct2 | 2/5 | 1/5 | **0/5** | -1 | 4 | 5 |
| direct3 | 2/13 | 7/13 | **8/13** | +1 | 6 | 5 |
| direct4 | 3/10 | 4/10 | **7/10** | +3 | 6 | 3 |

개선은 주로 direct4와 redirection이 포함된 case에서 발생했고 direct2는 악화됐다.

## Initial과 RePrediction 분리

`Exact matches`는 각 query가 활성 queue인 동안 다음 mismatch 전까지 연속으로 맞힌 event 수의 합이다. `Avg matched prefix`는 query 한 회당 평균 연속 PASS 길이다.

| Mode | P1 queries | P1 exact matches | P1 avg prefix | P1.1 queries | P1.1 exact matches | P1.1 avg prefix |
|---|---:|---:|---:|---:|---:|---:|
| Initial | 16 | 6 | 0.375 | 16 | **10** | **0.625** |
| RePrediction | 32 | 12 | 0.375 | 28 | 12 | **0.429** |

P1.1의 총 +4 PASS는 Initial query가 만든 연속 prefix 개선에서 나왔다. RePrediction의 총 match 수는 12로 같지만 query 수가 32회에서 28회로 줄어 query당 prefix는 소폭 개선됐다.

## P1 대비 Event 전환

### STOP → PASS (6개)

| Case | Actual | P1 Predict | P1.1 Predict | 해석 |
|---:|---|---|---|---|
| 7 | `file/write /dev/null` | `gcc exec` | `file/write /dev/null` | redirection을 exec 전 setup으로 배치 |
| 18 | `sed s/[[:space:]]\\+/ /g` | `echo` | 동일한 `sed` | RePrediction remaining pipeline 순서 개선 |
| 30 | `file/write /dev/null` | `ls exec` | `file/write /dev/null` | redirection chronology 개선 |
| 47 | `date` | `bash -c "date && ls"` | 직접 `date` | compound command 전개 |
| 49 | `file/write /dev/null` | `bash -c "cat ..."` | `file/write /dev/null` | redirection chronology 개선 |
| 50 | `cat /etc/timezone` | prediction 없음 | 동일한 `cat` | redirection 뒤 remaining executable 유지 |

### PASS → STOP (2개)

| Case | Actual | P1 Predict | P1.1 Predict | 해석 |
|---:|---|---|---|---|
| 13 | `sed s/^[[:space:]]*//g` | 동일한 `sed` | `gcc` | pipeline 병렬 실행 순서를 잘못 재구성 |
| 27 | `cat /tmp/output.txt` | 동일한 `cat` | prediction 없음 | Direct2 RePrediction queue가 조기 소진 |

순증은 `6 - 2 = 4`다.

## 세 규칙별 판단

### Causal chronology

가장 명확한 효과가 있었다. P1에서는 `/dev/null`을 예측 목록에 포함했지만 queue 위치가 틀렸고, P1.1에서는 Case 7, 30, 49 세 건이 실제 file/write 직전에 배치되어 모두 PASS됐다.

다만 pipeline child들의 관측 순서는 scheduling 영향을 받는다. Case 13처럼 `gcc`와 여러 `sed`가 병렬로 시작하는 구간은 prompt만으로 완전한 전역 순서를 맞히기 어렵다.

### Preserve operation with unknown fields

`stat` operation 자체는 계속 유지됐고 가짜 filename은 만들지 않았다. 그러나 required path argument가 없으므로 Case 38~40은 exact matcher에서 계속 STOP이다. Predictor coverage에는 도움이 되지만 현재 PASS에는 직접 기여하지 못했다.

### RePrediction continuation

Case 18과 50을 회수했고 RePrediction은 32회에서 28회로 감소했다. 반면 Case 13과 27을 잃었다. 총 RePrediction match는 12개로 동일하므로, 현재 표본에서 continuation 문구의 직접적인 정확도 향상은 제한적이며 주된 효과는 앞선 Initial/chronology 개선으로 mismatch 자체가 줄어든 것이다.

## Queue 상태

Prediction queue가 소진된 상태에서 Actual event가 발생한 횟수는 P1의 2건에서 P1.1의 4건으로 늘었다. 즉 exact recall은 개선됐지만 completeness가 모든 면에서 좋아진 것은 아니다. Direct2 Case 27의 회귀가 대표적이다.

## 결론

P1.1은 단일 실행에서 exact recall을 36%에서 44%로 높였고 RePrediction을 32회에서 28회로 줄였다. 특히 causal redirection ordering은 의도한 효과가 세 건 모두 확인됐다. 반면 dynamic argument와 concurrent pipeline ordering은 Prompt-only 접근의 한계로 남았다. 모델 sampling 변동을 분리하려면 P1과 P1.1을 동일 조건에서 여러 seed/run으로 반복해야 한다.
