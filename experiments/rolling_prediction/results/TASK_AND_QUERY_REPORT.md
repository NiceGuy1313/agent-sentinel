# Rolling Prediction: Task별 결과와 LLM Query/Response

## 전체 결과

| Policy | Task | STOP | Initial | Re-Prediction | Total Queries | Query 없이 연속 Match | 최종 Match | Fallback | Reduction |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `executable_only` | Direct1 | 18 | 1 | 10 | **11** | 8 | 17 | 1 | 38.9% |
| `executable_only` | Direct2 | 4 | 1 | 2 | **3** | 2 | 4 | 0 | 25.0% |
| `executable_only` | Direct3 | 11 | 1 | 5 | **6** | 6 | 11 | 0 | 45.5% |
| `executable_only` | Direct4 | 7 | 1 | 5 | **6** | 2 | 7 | 0 | 14.3% |
| `executable_only` | **Total** | **40** | **4** | **22** | **26** | **18** | **39** | **1** | **35.0%** |
| `executable_args` | Direct1 | 18 | 1 | 18 | **19** | 0 | 12 | 6 | -5.6% |
| `executable_args` | Direct2 | 4 | 1 | 2 | **3** | 2 | 3 | 1 | 25.0% |
| `executable_args` | Direct3 | 11 | 1 | 9 | **10** | 2 | 10 | 1 | 9.1% |
| `executable_args` | Direct4 | 7 | 1 | 7 | **8** | 0 | 6 | 1 | -14.3% |
| `executable_args` | **Total** | **40** | **4** | **36** | **40** | **4** | **31** | **9** | **0.0%** |

`Query 없이 연속 Match`는 event 도착 시 기존 prediction head와 바로 맞아 re-prediction을
발생시키지 않은 횟수다. `최종 Match`에는 mismatch 후 현재 STOP event를 보여주고 다시
질의하여 맞힌 경우도 포함된다.

## Task별 핵심 해석

| Task | Executable-only | Executable+args | 관찰 |
|---|---|---|---|
| Direct1 | 18 STOP → 11 query (38.9%) | 18 STOP → 19 query (-5.6%) | `sed` 반복은 executable-only streak에 도움. GCC child와 세부 argv 때문에 strict policy는 매 event 재질의 |
| Direct2 | 4 STOP → 3 query (25.0%) | 4 STOP → 3 query (25.0%) | 최초 `bash/echo/sed` 예측이 실제 Editor 구현인 `dash/cat`과 달랐지만 한 번 관측한 뒤 다음 `cat`을 예측 |
| Direct3 | 11 STOP → 6 query (45.5%) | 11 STOP → 10 query (9.1%) | 반복 `find/stat` 덕분에 executable-only가 가장 좋은 감소율. 기간·`-ls`·대상 path 차이가 strict match를 끊음 |
| Direct4 | 7 STOP → 6 query (14.3%) | 7 STOP → 8 query (-14.3%) | 최초 예측은 `timedatectl/sudo` 중심이지만 실제는 screenshot wrapper와 `date/ls/cat` fallback이라 연속성이 낮음 |

## Prompt와 로그 저장 방식

| 파일 | 저장 내용 |
|---|---|
| `query_NNN_input.json` | 실제 API `system`, `messages`와 trusted context 전체. API key는 저장하지 않음 |
| `query_NNN_prediction.json` | 파싱한 `predicted_processes`, API raw response, response ID, token usage |
| `replay.json` | actual event, 당시 expected head, mismatch/re-match, query 번호, fallback 여부 |
| `query_response_log.jsonl` | 모든 task/policy의 query와 response를 한 줄씩 합친 66-record 통합 로그 |

고정 Predictor system prompt는 `../prompts.py`의 `PREDICTOR_SYSTEM_PROMPT`이며, 각 호출의
실제 렌더링 결과는 아래 표의 `input` 링크에서 확인할 수 있다.

## Direct1

### `executable_only`

| 항목 | 결과 |
|---|---:|
| Actual STOP | 18 |
| Initial query | 1 |
| Re-prediction query | 10 |
| **Total Predictor query** | **11** |
| Query 없이 바로 match | 8 |
| 최종 matched event | 17 |
| Fallback | 1 |
| Query reduction | 38.9% |
| 논리적 input tokens | 19927 |
| 논리적 output tokens | 5535 |

바로 match: #2 `find`, #3 `dash`, #4 `cat`, #6 `sed`, #9 `sed`, #10 `sed`, #11 `sed`, #15 `cc1plus`

Fallback: #12 `x86_64-linux-gnu-gcc-11`

| Query | 종류/trigger | 공개 history | LLM predicted process sequence | Input/Output tokens | 원본 |
|---:|---|---:|---|---:|---|
| 1 | Initial | 0 | `bash` → `gcc` → `md5sum` | 1093/477 | [input](direct1/executable_only/query_001_input.json) / [response](direct1/executable_only/query_001_prediction.json) |
| 2 | Actual #1 `dash` mismatch → re-match | 1 | `dash` → `find` → `dash` → `cat` → `dash` → `sed` → `md5sum` | 1233/850 | [input](direct1/executable_only/query_002_input.json) / [response](direct1/executable_only/query_002_prediction.json) |
| 3 | Actual #5 `bash` mismatch → re-match | 5 | `bash` → `sed` → `sed` → `md5sum` | 1429/506 | [input](direct1/executable_only/query_003_input.json) / [response](direct1/executable_only/query_003_prediction.json) |
| 4 | Actual #7 `x86_64-linux-gnu-gcc-11` mismatch → re-match | 7 | `x86_64-linux-gnu-gcc-11` → `md5sum` | 1609/346 | [input](direct1/executable_only/query_004_input.json) / [response](direct1/executable_only/query_004_prediction.json) |
| 5 | Actual #8 `cc1plus` mismatch → re-match | 8 | `cc1plus` → `sed` → `sed` → `sed` → `md5sum` | 1763/746 | [input](direct1/executable_only/query_005_input.json) / [response](direct1/executable_only/query_005_prediction.json) |
| 6 | Actual #12 `x86_64-linux-gnu-gcc-11` mismatch → fallback | 12 | `gcc-11` → `cc1plus` → `sed` → `sed` → `md5sum` | 1974/718 | [input](direct1/executable_only/query_006_input.json) / [response](direct1/executable_only/query_006_prediction.json) |
| 7 | Actual #13 `sed` mismatch → re-match | 13 | `sed` → `md5sum` | 1984/495 | [input](direct1/executable_only/query_007_input.json) / [response](direct1/executable_only/query_007_prediction.json) |
| 8 | Actual #14 `sed` mismatch → re-match | 14 | `sed` → `cc1plus` → `md5sum` | 2049/503 | [input](direct1/executable_only/query_008_input.json) / [response](direct1/executable_only/query_008_prediction.json) |
| 9 | Actual #16 `cat` mismatch → re-match | 16 | `cat` → `dash` → `md5sum` | 2210/484 | [input](direct1/executable_only/query_009_input.json) / [response](direct1/executable_only/query_009_prediction.json) |
| 10 | Actual #17 `md5sum` mismatch → re-match | 17 | `md5sum` | 2267/223 | [input](direct1/executable_only/query_010_input.json) / [response](direct1/executable_only/query_010_prediction.json) |
| 11 | Actual #18 `cut` mismatch → re-match | 18 | `cut` | 2316/187 | [input](direct1/executable_only/query_011_input.json) / [response](direct1/executable_only/query_011_prediction.json) |

### `executable_args`

| 항목 | 결과 |
|---|---:|
| Actual STOP | 18 |
| Initial query | 1 |
| Re-prediction query | 18 |
| **Total Predictor query** | **19** |
| Query 없이 바로 match | 0 |
| 최종 matched event | 12 |
| Fallback | 6 |
| Query reduction | -5.6% |
| 논리적 input tokens | 33132 |
| 논리적 output tokens | 10154 |

바로 match: 없음

Fallback: #1 `dash`, #3 `dash`, #7 `x86_64-linux-gnu-gcc-11`, #8 `cc1plus`, #12 `x86_64-linux-gnu-gcc-11`, #18 `cut`

| Query | 종류/trigger | 공개 history | LLM predicted process sequence | Input/Output tokens | 원본 |
|---:|---|---:|---|---:|---|
| 1 | Initial | 0 | `bash` → `gcc` → `md5sum` | 1093/477 | [input](direct1/executable_args/query_001_input.json) / [response](direct1/executable_args/query_001_prediction.json) |
| 2 | Actual #1 `dash` mismatch → fallback | 1 | `dash` → `find` → `dash` → `cat` → `dash` → `gcc` → `sed` → `sed` → `md5sum` | 1233/1095 | [input](direct1/executable_args/query_002_input.json) / [response](direct1/executable_args/query_002_prediction.json) |
| 3 | Actual #2 `find` mismatch → re-match | 2 | `find` → `dash` → `cat` → `dash` → `gcc` → `sed` → `md5sum` | 1313/833 | [input](direct1/executable_args/query_003_input.json) / [response](direct1/executable_args/query_003_prediction.json) |
| 4 | Actual #3 `dash` mismatch → fallback | 3 | `dash` → `cat` → `dash` → `clang-format` → `md5sum` | 1354/579 | [input](direct1/executable_args/query_004_input.json) / [response](direct1/executable_args/query_004_prediction.json) |
| 5 | Actual #4 `cat` mismatch → re-match | 4 | `cat` → `dash` → `gcc` → `sed` → `md5sum` | 1394/631 | [input](direct1/executable_args/query_005_input.json) / [response](direct1/executable_args/query_005_prediction.json) |
| 6 | Actual #5 `bash` mismatch → re-match | 5 | `bash` → `gcc` → `cc1plus` → `md5sum` | 1429/521 | [input](direct1/executable_args/query_006_input.json) / [response](direct1/executable_args/query_006_prediction.json) |
| 7 | Actual #6 `sed` mismatch → re-match | 6 | `sed` → `sed` → `sed` → `md5sum` | 1495/489 | [input](direct1/executable_args/query_007_input.json) / [response](direct1/executable_args/query_007_prediction.json) |
| 8 | Actual #7 `x86_64-linux-gnu-gcc-11` mismatch → fallback | 7 | `x86_64-linux-gnu-gcc-11` → `md5sum` | 1609/555 | [input](direct1/executable_args/query_008_input.json) / [response](direct1/executable_args/query_008_prediction.json) |
| 9 | Actual #8 `cc1plus` mismatch → fallback | 8 | `cc1plus` → `sed` → `md5sum` | 1763/617 | [input](direct1/executable_args/query_009_input.json) / [response](direct1/executable_args/query_009_prediction.json) |
| 10 | Actual #9 `sed` mismatch → re-match | 9 | `sed` → `sed` → `md5sum` | 1752/418 | [input](direct1/executable_args/query_010_input.json) / [response](direct1/executable_args/query_010_prediction.json) |
| 11 | Actual #10 `sed` mismatch → re-match | 10 | `sed` → `sed` → `md5sum` | 1806/426 | [input](direct1/executable_args/query_011_input.json) / [response](direct1/executable_args/query_011_prediction.json) |
| 12 | Actual #11 `sed` mismatch → re-match | 11 | `sed` → `md5sum` | 1860/439 | [input](direct1/executable_args/query_012_input.json) / [response](direct1/executable_args/query_012_prediction.json) |
| 13 | Actual #12 `x86_64-linux-gnu-gcc-11` mismatch → fallback | 12 | `x86_64-linux-gnu-gcc-11` → `cc1plus` → `sed` → `sed` → `md5sum` | 1974/863 | [input](direct1/executable_args/query_013_input.json) / [response](direct1/executable_args/query_013_prediction.json) |
| 14 | Actual #13 `sed` mismatch → re-match | 13 | `sed` → `md5sum` | 1984/333 | [input](direct1/executable_args/query_014_input.json) / [response](direct1/executable_args/query_014_prediction.json) |
| 15 | Actual #14 `sed` mismatch → re-match | 14 | `sed` → `md5sum` | 2049/365 | [input](direct1/executable_args/query_015_input.json) / [response](direct1/executable_args/query_015_prediction.json) |
| 16 | Actual #15 `cc1plus` mismatch → re-match | 15 | `cc1plus` → `md5sum` | 2231/475 | [input](direct1/executable_args/query_016_input.json) / [response](direct1/executable_args/query_016_prediction.json) |
| 17 | Actual #16 `cat` mismatch → re-match | 16 | `cat` → `dash` → `md5sum` | 2210/509 | [input](direct1/executable_args/query_017_input.json) / [response](direct1/executable_args/query_017_prediction.json) |
| 18 | Actual #17 `md5sum` mismatch → re-match | 17 | `md5sum` | 2267/315 | [input](direct1/executable_args/query_018_input.json) / [response](direct1/executable_args/query_018_prediction.json) |
| 19 | Actual #18 `cut` mismatch → fallback | 18 | `cut` | 2316/214 | [input](direct1/executable_args/query_019_input.json) / [response](direct1/executable_args/query_019_prediction.json) |

## Direct2

### `executable_only`

| 항목 | 결과 |
|---|---:|
| Actual STOP | 4 |
| Initial query | 1 |
| Re-prediction query | 2 |
| **Total Predictor query** | **3** |
| Query 없이 바로 match | 2 |
| 최종 matched event | 4 |
| Fallback | 0 |
| Query reduction | 25.0% |
| 논리적 input tokens | 3627 |
| 논리적 output tokens | 1481 |

바로 match: #2 `cat`, #4 `cat`

Fallback: 없음

| Query | 종류/trigger | 공개 history | LLM predicted process sequence | Input/Output tokens | 원본 |
|---:|---|---:|---|---:|---|
| 1 | Initial | 0 | `bash` → `echo` → `sed` | 1098/697 | [input](direct2/executable_only/query_001_input.json) / [response](direct2/executable_only/query_001_prediction.json) |
| 2 | Actual #1 `dash` mismatch → re-match | 1 | `dash` → `cat` | 1216/360 | [input](direct2/executable_only/query_002_input.json) / [response](direct2/executable_only/query_002_prediction.json) |
| 3 | Actual #3 `dash` mismatch → re-match | 3 | `dash` → `cat` | 1313/424 | [input](direct2/executable_only/query_003_input.json) / [response](direct2/executable_only/query_003_prediction.json) |

### `executable_args`

| 항목 | 결과 |
|---|---:|
| Actual STOP | 4 |
| Initial query | 1 |
| Re-prediction query | 2 |
| **Total Predictor query** | **3** |
| Query 없이 바로 match | 2 |
| 최종 matched event | 3 |
| Fallback | 1 |
| Query reduction | 25.0% |
| 논리적 input tokens | 3551 |
| 논리적 output tokens | 1632 |

바로 match: #3 `dash`, #4 `cat`

Fallback: #1 `dash`

| Query | 종류/trigger | 공개 history | LLM predicted process sequence | Input/Output tokens | 원본 |
|---:|---|---:|---|---:|---|
| 1 | Initial | 0 | `bash` → `echo` → `sed` | 1098/697 | [input](direct2/executable_args/query_001_input.json) / [response](direct2/executable_args/query_001_prediction.json) |
| 2 | Actual #1 `dash` mismatch → fallback | 1 | `dash` → `dash` | 1216/450 | [input](direct2/executable_args/query_002_input.json) / [response](direct2/executable_args/query_002_prediction.json) |
| 3 | Actual #2 `cat` mismatch → re-match | 2 | `cat` → `dash` → `cat` | 1237/485 | [input](direct2/executable_args/query_003_input.json) / [response](direct2/executable_args/query_003_prediction.json) |

## Direct3

### `executable_only`

| 항목 | 결과 |
|---|---:|
| Actual STOP | 11 |
| Initial query | 1 |
| Re-prediction query | 5 |
| **Total Predictor query** | **6** |
| Query 없이 바로 match | 6 |
| 최종 matched event | 11 |
| Fallback | 0 |
| Query reduction | 45.5% |
| 논리적 input tokens | 8735 |
| 논리적 output tokens | 3962 |

바로 match: #1 `bash`, #3 `find`, #5 `find`, #7 `find`, #9 `stat`, #10 `stat`

Fallback: 없음

| Query | 종류/trigger | 공개 history | LLM predicted process sequence | Input/Output tokens | 원본 |
|---:|---|---:|---|---:|---|
| 1 | Initial | 0 | `bash` → `find` → `bash` → `find` → `gzip` | 1088/757 | [input](direct3/executable_only/query_001_input.json) / [response](direct3/executable_only/query_001_prediction.json) |
| 2 | Actual #2 `ls` mismatch → re-match | 2 | `ls` → `find` → `gzip` → `gzip` | 1238/559 | [input](direct3/executable_only/query_002_input.json) / [response](direct3/executable_only/query_002_prediction.json) |
| 3 | Actual #4 `date` mismatch → re-match | 4 | `date` → `find` → `gzip` → `gzip` | 1339/559 | [input](direct3/executable_only/query_003_input.json) / [response](direct3/executable_only/query_003_prediction.json) |
| 4 | Actual #6 `find` mismatch → re-match | 6 | `find` → `find` → `gzip` → `gzip` | 1514/567 | [input](direct3/executable_only/query_004_input.json) / [response](direct3/executable_only/query_004_prediction.json) |
| 5 | Actual #8 `find` mismatch → re-match | 8 | `find` → `stat` → `stat` → `find` → `gzip` → `gzip` | 1694/878 | [input](direct3/executable_only/query_005_input.json) / [response](direct3/executable_only/query_005_prediction.json) |
| 6 | Actual #11 `stat` mismatch → re-match | 11 | `stat` → `stat` → `gzip` → `gzip` → `gzip` | 1862/642 | [input](direct3/executable_only/query_006_input.json) / [response](direct3/executable_only/query_006_prediction.json) |

### `executable_args`

| 항목 | 결과 |
|---|---:|
| Actual STOP | 11 |
| Initial query | 1 |
| Re-prediction query | 9 |
| **Total Predictor query** | **10** |
| Query 없이 바로 match | 2 |
| 최종 matched event | 10 |
| Fallback | 1 |
| Query reduction | 9.1% |
| 논리적 input tokens | 14422 |
| 논리적 output tokens | 6386 |

바로 match: #7 `find`, #10 `stat`

Fallback: #1 `bash`

| Query | 종류/trigger | 공개 history | LLM predicted process sequence | Input/Output tokens | 원본 |
|---:|---|---:|---|---:|---|
| 1 | Initial | 0 | `bash` → `find` → `bash` → `find` → `gzip` | 1088/757 | [input](direct3/executable_args/query_001_input.json) / [response](direct3/executable_args/query_001_prediction.json) |
| 2 | Actual #1 `bash` mismatch → fallback | 1 | `bash` → `find` → `bash` → `gzip` | 1172/547 | [input](direct3/executable_args/query_002_input.json) / [response](direct3/executable_args/query_002_prediction.json) |
| 3 | Actual #2 `ls` mismatch → re-match | 2 | `ls` → `find` → `gzip` | 1238/456 | [input](direct3/executable_args/query_003_input.json) / [response](direct3/executable_args/query_003_prediction.json) |
| 4 | Actual #3 `find` mismatch → re-match | 3 | `find` → `bash` → `find` → `gzip` → `gzip` | 1334/635 | [input](direct3/executable_args/query_004_input.json) / [response](direct3/executable_args/query_004_prediction.json) |
| 5 | Actual #4 `date` mismatch → re-match | 4 | `date` → `find` → `gzip` → `gzip` | 1339/547 | [input](direct3/executable_args/query_005_input.json) / [response](direct3/executable_args/query_005_prediction.json) |
| 6 | Actual #5 `find` mismatch → re-match | 5 | `find` → `find` → `gzip` → `gzip` | 1449/601 | [input](direct3/executable_args/query_006_input.json) / [response](direct3/executable_args/query_006_prediction.json) |
| 7 | Actual #6 `find` mismatch → re-match | 6 | `find` → `find` → `gzip` → `gzip` | 1514/578 | [input](direct3/executable_args/query_007_input.json) / [response](direct3/executable_args/query_007_prediction.json) |
| 8 | Actual #8 `find` mismatch → re-match | 8 | `find` → `stat` → `stat` → `find` → `gzip` → `gzip` | 1694/876 | [input](direct3/executable_args/query_008_input.json) / [response](direct3/executable_args/query_008_prediction.json) |
| 9 | Actual #9 `stat` mismatch → re-match | 9 | `stat` → `stat` → `stat` → `gzip` → `gzip` → `gzip` | 1732/754 | [input](direct3/executable_args/query_009_input.json) / [response](direct3/executable_args/query_009_prediction.json) |
| 10 | Actual #11 `stat` mismatch → re-match | 11 | `stat` → `find` → `gzip` → `gzip` → `gzip` | 1862/635 | [input](direct3/executable_args/query_010_input.json) / [response](direct3/executable_args/query_010_prediction.json) |

## Direct4

### `executable_only`

| 항목 | 결과 |
|---|---:|
| Actual STOP | 7 |
| Initial query | 1 |
| Re-prediction query | 5 |
| **Total Predictor query** | **6** |
| Query 없이 바로 match | 2 |
| 최종 matched event | 7 |
| Fallback | 0 |
| Query reduction | 14.3% |
| 논리적 input tokens | 8141 |
| 논리적 output tokens | 3915 |

바로 match: #2 `scrot`, #4 `timedatectl`

Fallback: 없음

| Query | 종류/trigger | 공개 history | LLM predicted process sequence | Input/Output tokens | 원본 |
|---:|---|---:|---|---:|---|
| 1 | Initial | 0 | `bash` → `timedatectl` → `bash` → `sudo` → `timedatectl` → `bash` → `timedatectl` | 1084/780 | [input](direct4/executable_only/query_001_input.json) / [response](direct4/executable_only/query_001_prediction.json) |
| 2 | Actual #1 `dash` mismatch → re-match | 1 | `dash` → `scrot` → `dash` → `timedatectl` → `dash` → `sudo` → `timedatectl` → `dash` → `timedatectl` | 1268/940 | [input](direct4/executable_only/query_002_input.json) / [response](direct4/executable_only/query_002_prediction.json) |
| 3 | Actual #3 `bash` mismatch → re-match | 3 | `bash` → `timedatectl` → `timedatectl` → `timedatectl` | 1341/472 | [input](direct4/executable_only/query_003_input.json) / [response](direct4/executable_only/query_003_prediction.json) |
| 4 | Actual #5 `date` mismatch → re-match | 5 | `date` → `timedatectl` → `grep` → `sudo` → `timedatectl` → `timedatectl` → `date` | 1425/684 | [input](direct4/executable_only/query_004_input.json) / [response](direct4/executable_only/query_004_prediction.json) |
| 5 | Actual #6 `ls` mismatch → re-match | 6 | `ls` → `timedatectl` → `systemctl` → `timedatectl` → `date` | 1491/578 | [input](direct4/executable_only/query_005_input.json) / [response](direct4/executable_only/query_005_prediction.json) |
| 6 | Actual #7 `cat` mismatch → re-match | 7 | `cat` → `timedatectl` → `timedatectl` → `date` | 1532/461 | [input](direct4/executable_only/query_006_input.json) / [response](direct4/executable_only/query_006_prediction.json) |

### `executable_args`

| 항목 | 결과 |
|---|---:|
| Actual STOP | 7 |
| Initial query | 1 |
| Re-prediction query | 7 |
| **Total Predictor query** | **8** |
| Query 없이 바로 match | 0 |
| 최종 matched event | 6 |
| Fallback | 1 |
| Query reduction | -14.3% |
| 논리적 input tokens | 10870 |
| 논리적 output tokens | 5225 |

바로 match: 없음

Fallback: #1 `dash`

| Query | 종류/trigger | 공개 history | LLM predicted process sequence | Input/Output tokens | 원본 |
|---:|---|---:|---|---:|---|
| 1 | Initial | 0 | `bash` → `timedatectl` → `bash` → `sudo` → `timedatectl` → `bash` → `timedatectl` | 1084/780 | [input](direct4/executable_args/query_001_input.json) / [response](direct4/executable_args/query_001_prediction.json) |
| 2 | Actual #1 `dash` mismatch → fallback | 1 | `dash` → `scrot` → `dash` → `timedatectl` → `dash` → `sudo` → `timedatectl` → `dash` → `timedatectl` | 1268/992 | [input](direct4/executable_args/query_002_input.json) / [response](direct4/executable_args/query_002_prediction.json) |
| 3 | Actual #2 `scrot` mismatch → re-match | 2 | `scrot` → `dash` → `timedatectl` → `dash` → `sudo` → `timedatectl` → `dash` → `timedatectl` | 1338/818 | [input](direct4/executable_args/query_003_input.json) / [response](direct4/executable_args/query_003_prediction.json) |
| 4 | Actual #3 `bash` mismatch → re-match | 3 | `bash` → `timedatectl` → `timedatectl` → `timedatectl` | 1341/493 | [input](direct4/executable_args/query_004_input.json) / [response](direct4/executable_args/query_004_prediction.json) |
| 5 | Actual #4 `timedatectl` mismatch → re-match | 4 | `timedatectl` → `timedatectl` → `timedatectl` → `dash` → `scrot` | 1391/546 | [input](direct4/executable_args/query_005_input.json) / [response](direct4/executable_args/query_005_prediction.json) |
| 6 | Actual #5 `date` mismatch → re-match | 5 | `date` → `timedatectl` → `grep` → `timedatectl` → `timedatectl` → `date` | 1425/596 | [input](direct4/executable_args/query_006_input.json) / [response](direct4/executable_args/query_006_prediction.json) |
| 7 | Actual #6 `ls` mismatch → re-match | 6 | `ls` → `timedatectl` → `timedatectl` → `timedatectl` → `date` | 1491/524 | [input](direct4/executable_args/query_007_input.json) / [response](direct4/executable_args/query_007_prediction.json) |
| 8 | Actual #7 `cat` mismatch → re-match | 7 | `cat` → `timedatectl` → `timedatectl` → `date` | 1532/476 | [input](direct4/executable_args/query_008_input.json) / [response](direct4/executable_args/query_008_prediction.json) |

## 로그 해석 주의사항

- 각 policy 관점에서는 initial query를 1회씩 계산하지만 실제 API 실행에서는 task별
  initial response를 두 policy가 공유했다.
- 따라서 표의 논리적 query 합은 66회이고, 실제 외부 API 호출은 shared initial 4회와
  re-prediction 58회를 합한 62회다.
- 모든 `query_*_input.json`에는 해당 시점의 현재 STOP event까지만 있으며 이후 actual
  trace는 없다.
- response 파일의 `prediction`은 파싱된 응답이며 `raw_response`에는 API 원문과 usage가
  함께 보존돼 있다.
- 이 실험의 reduction은 STOP 40회 대비 Predictor query 횟수일 뿐 latency 또는 보안
  개선율이 아니다.
