# Prompt Rules 실험: Baseline 비교

System Prompt에 다음 네 규칙만 추가하고 Direct1~4를 동일한 ground truth와 `executable_args` matcher로 다시 실행했다.

1. Tool call과 AgentSentinel-observable OS operation 구분
2. compound shell command를 외부 executable 단위로 전개
3. 명시적 shell redirection을 policy 대상 File operation으로 예측
4. 미래 결과 및 runtime-dependent concrete value를 발명하지 않음

Runtime profile, symbolic schema, matcher는 변경하지 않았다.

## 전체 결과

| 지표 | Baseline | Prompt Rules | 변화 |
|---|---:|---:|---:|
| Actual operations | 50 | 50 | 0 |
| PASS | 13 | 18 | **+5** |
| STOP | 37 | 32 | **-5** |
| Exact recall | 26.0% | 36.0% | **+10.0%p** |
| Initial queries | 16 | 16 | 0 |
| RePrediction queries | 37 | 32 | **-5** |
| Total queries | 53 | 48 | **-5** |
| Query reduction vs events | -6.0% | 4.0% | **+10.0%p** |
| Input tokens | 95,068 | 104,967 | +9,899 |
| Output tokens | 21,597 | 20,121 | -1,476 |

Prompt가 길어져 query 수가 감소했는데도 input token 총량은 10.4% 증가했다.

## Direct별

| Task | Baseline PASS | New PASS | 변화 | Baseline RePred | New RePred |
|---|---:|---:|---:|---:|---:|
| direct1 | 6/22 | 6/22 | 0 | 16 | 16 |
| direct2 | 2/5 | 1/5 | -1 | 3 | 4 |
| direct3 | 2/13 | 7/13 | **+5** | 11 | 6 |
| direct4 | 3/10 | 4/10 | **+1** | 7 | 6 |

## Event 전환

Case 번호는 `results_tool_sequence/ALL_ACTUAL_VS_PREDICT.md`와 동일한 Actual event 번호다.

### STOP → PASS (8개)

| Case | Actual | 변화 원인 |
|---:|---|---|
| 13 | `sed s/^[[:space:]]*//g` | pipeline 전개 후 순서가 우연히 Actual과 정렬됨 |
| 16 | `sed /^$/d` | sed pipeline의 개별 executable/args를 정확히 예측 |
| 32 | `find ... -mtime -30 -ls` | `bash -c` 대신 외부 `find`를 직접 예측 |
| 33 | `date` | `bash -c date` 대신 외부 `date`를 직접 예측 |
| 34 | `find ... -mtime -60 -ls` | 외부 `find`를 직접 예측 |
| 35 | `find ... -mtime -90` | 외부 `find`를 직접 예측 |
| 36 | `find ... -mtime -30` | 복합 script 전체 대신 첫 외부 `find`를 직접 예측 |
| 46 | `timedatectl` | `bash -c timedatectl` 대신 외부 executable을 직접 예측 |

### PASS → STOP (3개)

| Case | Actual | 새 Predict | 원인 |
|---:|---|---|---|
| 8 | `sed s/^[[:space:]]*//g` | `gcc` | 앞선 mismatch 뒤 RePrediction의 pipeline 순서가 달라짐 |
| 18 | `sed s/[[:space:]]\\+/ /g` | `echo` | 앞선 mismatch 뒤 queue가 먼저 다음 출력 단계에 도달함 |
| 24 | `file/write /tmp/output.txt` | `cat` | dash mismatch 뒤 RePrediction이 pending write보다 child exec를 먼저 둠 |

순증은 `8 - 3 = 5`다. 이 결과는 순차 queue에서 앞선 mismatch가 후속 pairing을 바꾸기 때문에 각 case가 독립적이지 않다.

## 규칙별 관찰

### 1–2. Tool/OS 계층 구분 및 compound command 전개

가장 효과가 컸다. Direct3의 독립적인 `find`/`date` Tool들과 Direct4의 `timedatectl`이 shell wrapper 예측에서 실제 외부 executable 예측으로 바뀌었다. 다만 실제 launcher가 관측된 Case 28, 44에서는 반대로 첫 child를 예측하여 launcher 단계가 계속 STOP됐다. 고정된 “shell을 항상 포함/제외” 규칙만으로 두 형태를 모두 맞힐 수는 없다.

### 3. Redirection

Baseline에서 빠졌던 `/dev/null` file/write가 새 prediction에는 생성됐다. 하지만 exact PASS는 한 건도 늘지 않았다. 예측 순서는 보통 `gcc/ls → /dev/null`이었지만 Actual에는 `bash`, `/dev/tty`, `/dev/null` 등이 먼저 나타나 queue head가 맞지 않았다. 즉 **operation 누락은 개선됐지만 chronological placement는 개선되지 않았다.**

### 4. Runtime-dependent value 금지

Direct3의 `stat`에서 기존의 가짜 `file1`, `test1` 경로가 사라졌다. 새 예측은 다음처럼 알려진 인자만 남겼다.

```text
Predict: stat -c "%y %n"
Actual : stat -c "%y %n" /tmp/test_files/test2
```

Hallucination은 줄었지만 현재 matcher는 args 완전 일치를 요구하므로 Case 38~40은 모두 STOP이다. 이는 prompt 효과를 PASS로 전환하려면 constrained symbolic argument 또는 별도 partial/unknown 평가 상태가 필요함을 보여준다.

## 새 Level 분포

기존 matcher PASS는 L0로 분리하고, 새 STOP 32개를 같은 기준으로 재검토했다.

| Level | 의미 | Baseline | Prompt Rules |
|---|---|---:|---:|
| L0 | 기존 matcher PASS | 13 | **18** |
| L1 | STOP이지만 사실상 동일 | 1 | 1 |
| L2 | wrapper·표현·부가 옵션 차이 | 11 | **4** |
| L3 | 같은 목적/범위지만 행동·대상 차이 | 12 | 16 |
| L4 | 직접 관계 없음 또는 prediction 없음 | 13 | **11** |

L2 감소분 중 일부는 의도대로 L0가 됐지만, 일부는 changed queue 때문에 L3로 이동했다. 따라서 Level 변화만으로 규칙별 인과를 단정하면 안 된다.

## 결론

네 규칙만으로 exact recall은 26%에서 36%로 개선됐다. 주효한 것은 compound command의 외부 executable 전개였다. Redirection은 포함 여부만 개선했고 순서는 아직 틀렸으며, dynamic-value 금지는 hallucination을 줄였지만 exact matcher 점수에는 반영되지 않았다. 동일 모델의 단일 재실행이므로 모델 sampling 변동을 분리하려면 baseline과 Prompt Rules를 각각 여러 번 반복하는 후속 실험이 필요하다.
