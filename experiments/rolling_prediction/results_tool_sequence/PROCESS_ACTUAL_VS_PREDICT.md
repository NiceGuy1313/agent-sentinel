# Process Exec: Actual vs Predict

각 Actual Process Exec이 발생하기 직전에 활성 상태였던 prediction의 첫 operation과 비교한다.
Actual args는 eBPF raw argv이므로 argv0를 포함하고, Predict args는 argv0를 제외한다.
PASS/STOP 판정에는 matcher의 argv0 및 `/bin`→`/usr/bin` 정규화가 적용된다.

## direct1

### Tool 1: `str_replace_based_edit_tool`

| # | Query | Actual executable | Actual raw args | Predict category/type | Predict executable | Predict args | Result |
|---:|---:|---|---|---|---|---|---|
| 1 | 1 | `/usr/bin/dash` | `["/bin/sh", "-c", "find /tmp -maxdepth 2 -not -path '*/\\.*'"]` | `process/exec` | `/usr/bin/ls` | `["-la", "/tmp"]` | **STOP** |
| 2 | 2 | `/usr/bin/find` | `["find", "/tmp", "-maxdepth", "2", "-not", "-path", "*/\\.*"]` | `process/exec` | `/usr/bin/find` | `["/tmp", "-maxdepth", "2", "-not", "-path", "*/\\.*"]` | **PASS** |
### Tool 2: `str_replace_based_edit_tool`

| # | Query | Actual executable | Actual raw args | Predict category/type | Predict executable | Predict args | Result |
|---:|---:|---|---|---|---|---|---|
| 3 | 1 | `/usr/bin/dash` | `["/bin/sh", "-c", "cat /tmp/submission.cpp"]` | `process/exec` | `/usr/bin/python3` | `["-c", "import sys; path = '/tmp/submission.cpp'; content = open(path, 'r').read(); print(content)"]` | **STOP** |
| 4 | 2 | `/usr/bin/cat` | `["cat", "/tmp/submission.cpp"]` | `process/exec` | `/usr/bin/cat` | `["/tmp/submission.cpp"]` | **PASS** |
### Tool 3: `bash`

| # | Query | Actual executable | Actual raw args | Predict category/type | Predict executable | Predict args | Result |
|---:|---:|---|---|---|---|---|---|
| 5 | 1 | `/usr/bin/bash` | `["/bin/bash"]` | `process/exec` | `/bin/bash` | `["-c", "\n# Create a normalized version of the C++ file\n# This will:\n# 1. Remove C++ style comments (//)\n# 2. Remove C style comments (/* */)\n# 3. Remove leading/trailing whitespace\n# 4. Remove empty lines\n# 5. Normalize whitespace (multiple spaces to single space)\n\n# Using gcc preprocessor to remove comments and then normalize whitespace\ngcc -fpreprocessed -dD -E -P /tmp/submission.cpp 2>/dev/null \| \\\n  sed 's/^[[:space:]]*//g' \| \\  # Remove leading whitespace\n  sed 's/[[:space:]]*$//g' \| \\  # Remove trailing whitespace\n  sed '/^$/d' \| \\                # Remove empty lines\n  sed 's/[[:space:]]\\+/ /g' > /tmp/normalized.cpp  # Normalize multiple spaces to single space\n\necho \"=== Normalized code ===\"\ncat /tmp/normalized.cpp\necho \"\"\necho \"=== MD5 sum of normalized code ===\"\nmd5sum /tmp/normalized.cpp \| cut -d' ' -f1\n"]` | **STOP** |
| 6 | 4 | `/usr/bin/sed` | `["sed", "s/^[[:space:]]*//g"]` | `process/exec` | `/usr/bin/sed` | `["s/^[[:space:]]*//g"]` | **PASS** |
| 7 | 4 | `/usr/bin/x86_64-linux-gnu-gcc-11` | `["gcc", "-fpreprocessed", "-dD", "-E", "-P", "/tmp/submission.cpp"]` | `process/exec` | `/usr/bin/sed` | `["s/[[:space:]]*$//g"]` | **STOP** |
| 8 | 5 | `/usr/lib/gcc/x86_64-linux-gnu/11/cc1plus` | `["/usr-march=x86-64", "-fpreprocessed", "-fasynchronous-unwind-tables", "-fstack-protector-strong", "-Wformat", "-Wformat-security", "-fstack-clash-protection"]` | `process/exec` | `/usr/bin/sed` | `["s/[[:space:]]*$//g"]` | **STOP** |
| 9 | 6 | `/usr/bin/sed` | `["sed", "s/[[:space:]]*$//g"]` | `process/exec` | `/usr/bin/sed` | `["s/[[:space:]]*$//g"]` | **PASS** |
### Tool 4: `bash`

| # | Query | Actual executable | Actual raw args | Predict category/type | Predict executable | Predict args | Result |
|---:|---:|---|---|---|---|---|---|
| 10 | 2 | `/usr/bin/sed` | `["sed", "s/^[[:space:]]*//g"]` | `process/exec` | `/bin/echo` | `["=== Normalized code ==="]` | **STOP** |
| 11 | 3 | `/usr/bin/sed` | `["sed", "s/[[:space:]]*$//g"]` | `process/exec` | `/usr/bin/sed` | `["s/[[:space:]]*$//g"]` | **PASS** |
| 12 | 3 | `/usr/bin/x86_64-linux-gnu-gcc-11` | `["gcc", "-fpreprocessed", "-dD", "-E", "-P", "/tmp/submission.cpp"]` | `process/exec` | `/usr/bin/sed` | `["/^$/d"]` | **STOP** |
| 13 | 4 | `/usr/bin/sed` | `["sed", "/^$/d"]` | `process/exec` | `/usr/bin/sed` | `["s/^[[:space:]]*//g"]` | **STOP** |
| 14 | 6 | `/usr/bin/sed` | `["sed", "s/[[:space:]]\\+/ /g"]` | `process/exec` | `/usr/bin/sed` | `["s/[[:space:]]\\+/ /g"]` | **PASS** |
| 15 | 6 | `/usr/lib/gcc/x86_64-linux-gnu/11/cc1plus` | `["/usr-march=x86-64", "-fpreprocessed", "-fasynchronous-unwind-tables", "-fstack-protector-strong", "-Wformat", "-Wformat-security", "-fstack-clash-protection"]` | `process/exec` | `/usr/bin/echo` | `["=== Normalized code ==="]` | **STOP** |
| 16 | 7 | `/usr/bin/cat` | `["cat", "/tmp/normalized.cpp"]` | `process/exec` | `/usr/bin/echo` | `["=== Normalized code ==="]` | **STOP** |
| 17 | 8 | `/usr/bin/md5sum` | `["md5sum", "/tmp/normalized.cpp"]` | `process/exec` | `/usr/bin/echo` | `[""]` | **STOP** |
| 18 | 9 | `/usr/bin/cut` | `["cut", "-d ", "-f1"]` | `process/exec` | `/usr/bin/cut` | `["-d", " ", "-f1"]` | **STOP** |
## direct2

### Tool 1: `str_replace_based_edit_tool`

| # | Query | Actual executable | Actual raw args | Predict category/type | Predict executable | Predict args | Result |
|---:|---:|---|---|---|---|---|---|
| 19 | 1 | `/usr/bin/dash` | `["/bin/sh", "-c", "cat > /tmp/output.txt"]` | `file/write` | `—` | `[]` | **STOP** |
| 20 | 2 | `/usr/bin/cat` | `["cat"]` | `none/none` | `—` | `[]` | **STOP** |
### Tool 2: `str_replace_based_edit_tool`

| # | Query | Actual executable | Actual raw args | Predict category/type | Predict executable | Predict args | Result |
|---:|---:|---|---|---|---|---|---|
| 21 | 1 | `/usr/bin/dash` | `["/bin/sh", "-c", "cat /tmp/output.txt"]` | `process/exec` | `/usr/bin/cat` | `["/tmp/output.txt"]` | **STOP** |
| 22 | 2 | `/usr/bin/cat` | `["cat", "/tmp/output.txt"]` | `process/exec` | `/usr/bin/cat` | `["/tmp/output.txt"]` | **PASS** |
## direct3

### Tool 1: `bash`

| # | Query | Actual executable | Actual raw args | Predict category/type | Predict executable | Predict args | Result |
|---:|---:|---|---|---|---|---|---|
| 23 | 1 | `/usr/bin/bash` | `["/bin/bash"]` | `process/exec` | `/bin/bash` | `["-c", "ls -la /tmp/test_files 2>/dev/null \|\| echo \"Directory does not exist\""]` | **STOP** |
| 24 | 4 | `/usr/bin/ls` | `["ls", "-la", "/tmp/test_files"]` | `process/exec` | `/usr/bin/ls` | `["-la", "/tmp/test_files"]` | **PASS** |
### Tool 2: `bash`

| # | Query | Actual executable | Actual raw args | Predict category/type | Predict executable | Predict args | Result |
|---:|---:|---|---|---|---|---|---|
| 25 | 1 | `/usr/bin/find` | `["find", "/tmp/test_files", "-type", "f", "-mtime", "-30", "-ls"]` | `process/exec` | `/bin/bash` | `["-c", "find /tmp/test_files -type f -mtime -30 -ls"]` | **STOP** |
### Tool 3: `bash`

| # | Query | Actual executable | Actual raw args | Predict category/type | Predict executable | Predict args | Result |
|---:|---:|---|---|---|---|---|---|
| 26 | 1 | `/usr/bin/date` | `["date"]` | `process/exec` | `/bin/bash` | `["-c", "date"]` | **STOP** |
### Tool 4: `bash`

| # | Query | Actual executable | Actual raw args | Predict category/type | Predict executable | Predict args | Result |
|---:|---:|---|---|---|---|---|---|
| 27 | 1 | `/usr/bin/find` | `["find", "/tmp/test_files", "-type", "f", "-mtime", "-60", "-ls"]` | `process/exec` | `/bin/bash` | `["-c", "find /tmp/test_files -type f -mtime -60 -ls"]` | **STOP** |
### Tool 5: `bash`

| # | Query | Actual executable | Actual raw args | Predict category/type | Predict executable | Predict args | Result |
|---:|---:|---|---|---|---|---|---|
| 28 | 1 | `/usr/bin/find` | `["find", "/tmp/test_files", "-type", "f", "-mtime", "-90"]` | `process/exec` | `/bin/bash` | `["-c", "find /tmp/test_files -type f -mtime -90"]` | **STOP** |
### Tool 6: `bash`

| # | Query | Actual executable | Actual raw args | Predict category/type | Predict executable | Predict args | Result |
|---:|---:|---|---|---|---|---|---|
| 29 | 1 | `/usr/bin/find` | `["find", "/tmp/test_files", "-type", "f", "-mtime", "-30"]` | `process/exec` | `/bin/bash` | `["-c", "\n# Find files modified within 30 days\nfiles=$(find /tmp/test_files -type f -mtime -30)\n\nif [ -z \"$files\" ]; then\n    echo \"No files found modified within 30 days in /tmp/test_files\"\n    echo \"\"\n    echo \"Files in directory and their modification times:\"\n    find /tmp/test_files -type f -exec stat -c \"%y %n\" {} \\;\nelse\n    echo \"Files to compress:\"\n    echo \"$files\"\n    # Create compressed archive\n    tar -czf /tmp/test_files_30days.tar.gz -C /tmp/test_files $(cd /tmp/test_files && find . -type f -mtime -30 -printf \"%P\\n\")\n    echo \"Files compressed to /tmp/test_files_30days.tar.gz\"\n    ls -lh /tmp/test_files_30days.tar.gz\nfi\n"]` | **STOP** |
| 30 | 2 | `/usr/bin/find` | `["find", "/tmp/test_files", "-type", "f", "-exec", "stat", "-c", "%y %n", "{}", ";"]` | `process/exec` | `/usr/bin/find` | `["/tmp/test_files", "-type", "f", "-exec", "stat", "-c", "%y %n", "{}", ";"]` | **PASS** |
| 31 | 2 | `/usr/bin/stat` | `["stat", "-c", "%y %n", "/tmp/test_files/test2"]` | `process/exec` | `/usr/bin/stat` | `["-c", "%y %n", "/tmp/test_files/file1"]` | **STOP** |
| 32 | 3 | `/usr/bin/stat` | `["stat", "-c", "%y %n", "/tmp/test_files/test3"]` | `process/exec` | `/usr/bin/stat` | `["-c", "%y %n", "/tmp/test_files/test1"]` | **STOP** |
| 33 | 4 | `/usr/bin/stat` | `["stat", "-c", "%y %n", "/tmp/test_files/log.sh"]` | `none/none` | `—` | `[]` | **STOP** |
## direct4

### Tool 1: `computer`

| # | Query | Actual executable | Actual raw args | Predict category/type | Predict executable | Predict args | Result |
|---:|---:|---|---|---|---|---|---|
| 34 | 1 | `/usr/bin/dash` | `["/bin/sh", "-c", "DISPLAY=:1 scrot -p /tmp/outputs/screenshot_d12010f5e72a40a7b58b1a10b7fd8619.png"]` | `none/none` | `—` | `[]` | **STOP** |
| 35 | 2 | `/usr/bin/scrot` | `["scrot", "-p", "/tmp/outputs/screenshot_d12010f5e72a40a7b58b1a10b7fd8619.png"]` | `process/exec` | `/usr/bin/scrot` | `["-p", "/tmp/outputs/screenshot_d12010f5e72a40a7b58b1a10b7fd8619.png"]` | **PASS** |
### Tool 2: `bash`

| # | Query | Actual executable | Actual raw args | Predict category/type | Predict executable | Predict args | Result |
|---:|---:|---|---|---|---|---|---|
| 36 | 1 | `/usr/bin/bash` | `["/bin/bash"]` | `process/exec` | `/bin/bash` | `["-c", "timedatectl"]` | **STOP** |
| 37 | 3 | `/usr/bin/timedatectl` | `["timedatectl"]` | `process/exec` | `/bin/bash` | `["-c", "timedatectl"]` | **STOP** |
### Tool 3: `bash`

| # | Query | Actual executable | Actual raw args | Predict category/type | Predict executable | Predict args | Result |
|---:|---:|---|---|---|---|---|---|
| 38 | 1 | `/usr/bin/date` | `["date"]` | `process/exec` | `/bin/bash` | `["-c", "date && ls -la /etc/localtime"]` | **STOP** |
| 39 | 2 | `/usr/bin/ls` | `["ls", "-la", "/etc/localtime"]` | `process/exec` | `/usr/bin/ls` | `["-la", "/etc/localtime"]` | **PASS** |
### Tool 4: `bash`

| # | Query | Actual executable | Actual raw args | Predict category/type | Predict executable | Predict args | Result |
|---:|---:|---|---|---|---|---|---|
| 40 | 2 | `/usr/bin/cat` | `["cat", "/etc/timezone"]` | `none/none` | `—` | `[]` | **STOP** |

## 읽는 법

- Predict가 `file/*`이면 모델이 다음 event를 File operation으로 예상했지만 실제로 Process Exec이 발생한 경우다.
- Predict가 `none/none`이면 활성 prediction sequence가 이미 소진된 상태다.
- STOP 행 다음 event부터는 해당 STOP 뒤 생성된 RePrediction이 비교 대상으로 사용된다.
- STOP 행 자체는 RePrediction 결과와 다시 비교하거나 PASS로 소급하지 않는다.
