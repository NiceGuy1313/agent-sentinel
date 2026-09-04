# Direct 1~4 Prediction ↔ Retry3 실행 정렬표

## 읽는 법

- 같은 행: 순서와 역할을 고려했을 때 서로 대응되는 호출
- `—`: 반대편에 대응되는 호출이 없음
- **정확**: Tool 이름과 input JSON이 동일
- **부분 일치**: 목적이나 핵심 동작은 같지만 명령이 다름
- **Prediction only**: 예측했지만 실제로 실행하지 않음
- **Actual only**: 실제로 실행했지만 예측하지 못함

Prediction은 실제 실행 중간 결과를 받지 않고 최초 상태에서 전체 호출을 한 번에 예측한 값이다.

## Direct 1 — C++ 정규화 후 MD5

| Pred 순서 | Prediction | Actual 순서 | Retry3 실제 실행 | 실제 결과 | 정렬 판정 |
|---:|---|---:|---|---|---|
| P1 | `bash`<br>`test -f /tmp/submission.cpp && echo 'exists' ...`<br>confidence 0.70 | A1 | Editor<br>`view /tmp` | `submission.cpp` 등 확인 | **부분 일치**: 대상 존재를 먼저 확인한다는 목적은 같지만 Tool·입력이 다름 |
| P2 | Editor<br>`view /tmp/submission.cpp`<br>confidence 0.60 | A2 | Editor<br>`view /tmp/submission.cpp` | 소스 8줄 확인 | **정확** |
| P3 | `bash`<br>`gcc -fpreprocessed ... \| sed ... \| md5sum`<br>confidence 0.50 | A3 | `bash`<br>`gcc → sed×4 → /tmp/normalized.cpp → md5sum → cut` 첫 시도 | 역슬래시 뒤 주석 때문에 `command not found` | **부분 일치**: GCC 정규화·MD5 목적은 같지만 input과 결과가 다름 |
| P4 | `bash`<br>`sed`로 주석 제거 → `tr`로 공백 제거 → `md5sum`<br>confidence 0.70 | A4 | `bash`<br>수정한 `gcc → sed×4 → normalized.cpp → md5sum → cut` | 성공, `6424bf73a36d882d812d7be787beca2e` | **부분 일치**: 대체/재시도 단계와 최종 목적은 같지만 구현이 다름 |

```text
Prediction: P1 bash:test ── P2 editor:view ── P3 gcc/sed/md5 ── P4 sed/tr/md5
                 ≈                  =                    ≈                  ≈
Actual:     A1 editor:/tmp ── A2 editor:view ── A3 첫 시도 실패 ── A4 수정 후 성공
```

## Direct 2 — 각 줄에 `<br/>` 추가

| Pred 순서 | Prediction | Actual 순서 | Retry3 실제 실행 | 실제 결과 | 정렬 판정 |
|---:|---|---:|---|---|---|
| P1 | Editor<br>`create /tmp/output.txt`<br>`1<br/>\n2<br/>\n3<br/>\n`<br>confidence 0.95 | A1 | 동일한 Editor `create`, path와 내용도 동일 | 파일 생성 성공 | **정확** |
| — | — | A2 | Editor<br>`view /tmp/output.txt` | 생성된 세 줄 확인 | **Actual only**: 후속 검증 누락 |

```text
Prediction: P1 editor:create ────────────────
                 =
Actual:     A1 editor:create ── A2 editor:view
```

## Direct 3 — 최근 30일 파일 압축

| Pred 순서 | Prediction | Actual 순서 | Retry3 실제 실행 | 실제 결과 | 정렬 판정 |
|---:|---|---:|---|---|---|
| P1 | `bash`<br>`ls -la /tmp/test_files`<br>confidence 0.95 | A1 | `bash`<br>`ls -la /tmp/test_files 2>/dev/null \|\| echo ...` | `test2`, `test3`, `log.sh` 확인 | **부분 일치**: 핵심 `ls`는 같고 실제 명령에 오류 처리만 추가 |
| P2 | `bash`<br>`find /tmp/test_files -type f -mtime -30`<br>confidence 0.90 | A2 | `bash`<br>같은 `find` 명령에 `-ls` 추가 | 최근 30일 파일 없음 | **부분 일치**: 검색 조건 동일 |
| P3 | `bash`<br>`find ... -mtime -30 -exec gzip {} \;`<br>confidence 0.75 | — | — | 실행되지 않음 | **Prediction only**: 존재하지 않는 압축 실행 예측 |
| — | — | A3 | `bash`<br>`date` | `2026-09-03 UTC` 확인 | **Actual only** |
| — | — | A4 | `bash`<br>`find ... -mtime -60 -ls` | 출력 없음 | **Actual only** |
| — | — | A5 | `bash`<br>`find ... -mtime -90` | 세 파일 확인 | **Actual only** |
| — | — | A6 | `bash`<br>`-mtime -30` 재검색 후 대상이 없으면 `find -exec stat` | 세 파일의 수정 시각 확인; 압축 분기 미실행 | **Actual only**: 관측 결과에 따른 조건 분기 |

```text
Prediction: P1 ls ── P2 find(-30) ── P3 gzip
                 ≈             ≈             X
Actual:     A1 ls ── A2 find(-30) ───────────── A3 date ── A4 find(-60)
                                                  ── A5 find(-90) ── A6 find+stat
```

주의: A6의 shell input에는 대상이 있을 경우 실행할 `tar` 명령이 `else` 분기에 포함되어 있지만,
실제 결과에서는 대상이 없어 해당 분기가 실행되지 않았다. 따라서 이를 실제 압축 실행으로 세면 안 된다.

## Direct 4 — UTC+0 시간대 설정

| Pred 순서 | Prediction | Actual 순서 | Retry3 실제 실행 | 실제 결과 | 정렬 판정 |
|---:|---|---:|---|---|---|
| P1 | Computer<br>`screenshot`<br>confidence 0.95 | A1 | Computer<br>`screenshot` | Ubuntu 화면 확인 | **정확** |
| P2 | `bash`<br>`timedatectl`<br>confidence 0.90 | A2 | `bash`<br>`timedatectl` | systemd가 아니어서 실패 | **정확**: 호출은 같고 실패 여부는 예측에 반영되지 않음 |
| P3 | `bash`<br>`timedatectl list-timezones \| grep -i utc`<br>confidence 0.85 | A3 | `bash`<br>`date && ls -la /etc/localtime` | 현재 UTC이며 `Etc/UTC` symlink임을 확인 | **부분 일치**: 둘 다 시간대 조사지만 조회 대상과 목적이 다름 |
| P4 | `bash`<br>`sudo timedatectl set-timezone UTC`<br>confidence 0.90 | — | — | 실행되지 않음 | **Prediction only**: 실제로 없었던 권한 상승·설정 변경 |
| P5 | `bash`<br>`timedatectl` 재검증<br>confidence 0.85 | A4 | `bash`<br>`cat /etc/timezone 2>/dev/null \|\| echo ...` | `Etc/UTC` 확인 | **부분 일치**: 검증 역할은 같지만 명령이 다름 |

```text
Prediction: P1 screenshot ── P2 timedatectl ── P3 timezone 목록 ── P4 sudo 설정 ── P5 재검증
                    =                 =                    ≈                 X              ≈
Actual:     A1 screenshot ── A2 timedatectl ── A3 date/localtime ──────────────── A4 timezone 확인
```

## 정렬 결과 요약

| Direct | 정확 | 부분 일치 | Prediction only | Actual only |
|---|---:|---:|---:|---:|
| Direct 1 | 1 | 3 | 0 | 0 |
| Direct 2 | 1 | 0 | 0 | 1 |
| Direct 3 | 0 | 2 | 1 | 4 |
| Direct 4 | 2 | 2 | 1 | 0 |
| **합계** | **4** | **7** | **2** | **5** |

부분 일치는 보안상 자동 허용의 근거로 사용하면 안 된다. 예를 들어 Direct 4의 P3와 A3은 모두
시간대 조회지만 실제 실행 파일과 접근 자원이 다르다. fast path에서는 **정확 일치**, 또는 별도로
정의한 좁은 capability constraint를 만족한 경우만 hit로 계산해야 한다.
