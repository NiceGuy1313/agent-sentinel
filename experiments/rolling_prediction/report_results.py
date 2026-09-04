#!/usr/bin/env python3
"""Build readable and machine-readable indexes for rolling-prediction results."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
TASKS = ("direct1", "direct2", "direct3", "direct4")
POLICIES = ("executable_only", "executable_args")


def load(path: Path) -> Any:
    return json.loads(path.read_text())


def process_name(process: dict[str, Any] | None) -> str:
    if not process:
        return "—"
    return os.path.basename(process.get("executable", "")) or "?"


def compact_prediction(processes: list[dict[str, Any]]) -> str:
    names = [f"`{process_name(process)}`" for process in processes]
    return " → ".join(names) if names else "_(empty)_"


def query_trigger_map(replay: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for row in replay:
        number = row.get("re_prediction_query_number")
        if number:
            result[int(number)] = row
    return result


def token_totals(query_files: list[Path]) -> tuple[int, int]:
    input_tokens = 0
    output_tokens = 0
    for path in query_files:
        usage = load(path).get("usage") or {}
        input_tokens += int(usage.get("input_tokens", 0))
        output_tokens += int(usage.get("output_tokens", 0))
    return input_tokens, output_tokens


def relative_link(path: Path) -> str:
    return path.relative_to(RESULTS).as_posix()


def build() -> None:
    markdown = [
        "# Rolling Prediction: Task별 결과와 LLM Query/Response",
        "",
        "## 전체 결과",
        "",
        "| Policy | Task | STOP | Initial | Re-Prediction | Total Queries | Query 없이 연속 Match | 최종 Match | Fallback | Reduction |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    consolidated: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []

    for policy in POLICIES:
        for task in TASKS:
            base = RESULTS / task / policy
            summary = load(base / "summary.json")
            replay = load(base / "replay.json")
            no_query_matches = sum(row["initial_comparison"] == "match" for row in replay)
            summary = dict(summary)
            summary["matches_without_reprediction"] = no_query_matches
            summaries.append(summary)
            markdown.append(
                f"| `{policy}` | {task.title()} | {summary['actual_stop_process_exec_count']} "
                f"| {summary['initial_prediction_queries']} | {summary['re_prediction_queries']} "
                f"| **{summary['total_prediction_llm_queries']}** | {no_query_matches} "
                f"| {summary['prediction_matched_events']} | {summary['fallback_events']} "
                f"| {summary['query_reduction_relative_to_stop_count']:.1%} |"
            )

        selected = [item for item in summaries if item["matching_policy"] == policy]
        stops = sum(item["actual_stop_process_exec_count"] for item in selected)
        initial = sum(item["initial_prediction_queries"] for item in selected)
        repred = sum(item["re_prediction_queries"] for item in selected)
        total = sum(item["total_prediction_llm_queries"] for item in selected)
        no_query = sum(item["matches_without_reprediction"] for item in selected)
        matched = sum(item["prediction_matched_events"] for item in selected)
        fallback = sum(item["fallback_events"] for item in selected)
        markdown.append(
            f"| `{policy}` | **Total** | **{stops}** | **{initial}** | **{repred}** "
            f"| **{total}** | **{no_query}** | **{matched}** | **{fallback}** "
            f"| **{1-total/stops:.1%}** |"
        )

    markdown.extend(
        [
            "",
            "`Query 없이 연속 Match`는 event 도착 시 기존 prediction head와 바로 맞아 re-prediction을",
            "발생시키지 않은 횟수다. `최종 Match`에는 mismatch 후 현재 STOP event를 보여주고 다시",
            "질의하여 맞힌 경우도 포함된다.",
            "",
            "## Task별 핵심 해석",
            "",
            "| Task | Executable-only | Executable+args | 관찰 |",
            "|---|---|---|---|",
            "| Direct1 | 18 STOP → 11 query (38.9%) | 18 STOP → 19 query (-5.6%) | `sed` 반복은 executable-only streak에 도움. GCC child와 세부 argv 때문에 strict policy는 매 event 재질의 |",
            "| Direct2 | 4 STOP → 3 query (25.0%) | 4 STOP → 3 query (25.0%) | 최초 `bash/echo/sed` 예측이 실제 Editor 구현인 `dash/cat`과 달랐지만 한 번 관측한 뒤 다음 `cat`을 예측 |",
            "| Direct3 | 11 STOP → 6 query (45.5%) | 11 STOP → 10 query (9.1%) | 반복 `find/stat` 덕분에 executable-only가 가장 좋은 감소율. 기간·`-ls`·대상 path 차이가 strict match를 끊음 |",
            "| Direct4 | 7 STOP → 6 query (14.3%) | 7 STOP → 8 query (-14.3%) | 최초 예측은 `timedatectl/sudo` 중심이지만 실제는 screenshot wrapper와 `date/ls/cat` fallback이라 연속성이 낮음 |",
            "",
            "## Prompt와 로그 저장 방식",
            "",
            "| 파일 | 저장 내용 |",
            "|---|---|",
            "| `query_NNN_input.json` | 실제 API `system`, `messages`와 trusted context 전체. API key는 저장하지 않음 |",
            "| `query_NNN_prediction.json` | 파싱한 `predicted_processes`, API raw response, response ID, token usage |",
            "| `replay.json` | actual event, 당시 expected head, mismatch/re-match, query 번호, fallback 여부 |",
            "| `query_response_log.jsonl` | 모든 task/policy의 query와 response를 한 줄씩 합친 66-record 통합 로그 |",
            "",
            "고정 Predictor system prompt는 `../prompts.py`의 `PREDICTOR_SYSTEM_PROMPT`이며, 각 호출의",
            "실제 렌더링 결과는 아래 표의 `input` 링크에서 확인할 수 있다.",
            "",
        ]
    )

    for task in TASKS:
        markdown.extend([f"## {task.title()}", ""])
        for policy in POLICIES:
            base = RESULTS / task / policy
            summary = load(base / "summary.json")
            replay = load(base / "replay.json")
            trigger_by_query = query_trigger_map(replay)
            fallback_events = [
                f"#{row['actual_event']['sequence']} `{process_name(row['actual_event'])}`"
                for row in replay
                if row["fallback"]
            ]
            direct_matches = [
                f"#{row['actual_event']['sequence']} `{process_name(row['actual_event'])}`"
                for row in replay
                if row["initial_comparison"] == "match"
            ]
            query_files = sorted(base.glob("query_*_prediction.json"))
            input_tokens, output_tokens = token_totals(query_files)

            markdown.extend(
                [
                    f"### `{policy}`",
                    "",
                    "| 항목 | 결과 |",
                    "|---|---:|",
                    f"| Actual STOP | {summary['actual_stop_process_exec_count']} |",
                    f"| Initial query | {summary['initial_prediction_queries']} |",
                    f"| Re-prediction query | {summary['re_prediction_queries']} |",
                    f"| **Total Predictor query** | **{summary['total_prediction_llm_queries']}** |",
                    f"| Query 없이 바로 match | {len(direct_matches)} |",
                    f"| 최종 matched event | {summary['prediction_matched_events']} |",
                    f"| Fallback | {summary['fallback_events']} |",
                    f"| Query reduction | {summary['query_reduction_relative_to_stop_count']:.1%} |",
                    f"| 논리적 input tokens | {input_tokens} |",
                    f"| 논리적 output tokens | {output_tokens} |",
                    "",
                    "바로 match: " + (", ".join(direct_matches) if direct_matches else "없음"),
                    "",
                    "Fallback: " + (", ".join(fallback_events) if fallback_events else "없음"),
                    "",
                    "| Query | 종류/trigger | 공개 history | LLM predicted process sequence | Input/Output tokens | 원본 |",
                    "|---:|---|---:|---|---:|---|",
                ]
            )

            for prediction_path in query_files:
                output_record = load(prediction_path)
                number = int(output_record["query_number"])
                input_path = base / f"query_{number:03d}_input.json"
                input_record = load(input_path)
                context = input_record["context"]
                prediction = output_record["prediction"]
                processes = prediction.get("predicted_processes") or []
                usage = output_record.get("usage") or {}
                trigger = trigger_by_query.get(number)
                if number == 1:
                    trigger_text = "Initial"
                    outcome = ""
                else:
                    event = trigger["actual_event"]
                    trigger_text = f"Actual #{event['sequence']} `{process_name(event)}` mismatch"
                    outcome = "fallback" if trigger["fallback"] else "re-match"
                    trigger_text += f" → {outcome}"
                markdown.append(
                    f"| {number} | {trigger_text} "
                    f"| {len(context['observed_process_exec_history'])} "
                    f"| {compact_prediction(processes)} "
                    f"| {usage.get('input_tokens', 0)}/{usage.get('output_tokens', 0)} "
                    f"| [input]({relative_link(input_path)}) / "
                    f"[response]({relative_link(prediction_path)}) |"
                )
                consolidated.append(
                    {
                        "task": task,
                        "matching_policy": policy,
                        "query_number": number,
                        "query_kind": "initial" if number == 1 else "re_prediction",
                        "trigger_actual_event": trigger["actual_event"] if trigger else None,
                        "input": input_record,
                        "response": output_record,
                    }
                )
            markdown.append("")

    markdown.extend(
        [
            "## 로그 해석 주의사항",
            "",
            "- 각 policy 관점에서는 initial query를 1회씩 계산하지만 실제 API 실행에서는 task별",
            "  initial response를 두 policy가 공유했다.",
            "- 따라서 표의 논리적 query 합은 66회이고, 실제 외부 API 호출은 shared initial 4회와",
            "  re-prediction 58회를 합한 62회다.",
            "- 모든 `query_*_input.json`에는 해당 시점의 현재 STOP event까지만 있으며 이후 actual",
            "  trace는 없다.",
            "- response 파일의 `prediction`은 파싱된 응답이며 `raw_response`에는 API 원문과 usage가",
            "  함께 보존돼 있다.",
            "- 이 실험의 reduction은 STOP 40회 대비 Predictor query 횟수일 뿐 latency 또는 보안",
            "  개선율이 아니다.",
            "",
        ]
    )

    (RESULTS / "TASK_AND_QUERY_REPORT.md").write_text("\n".join(markdown))
    with (RESULTS / "query_response_log.jsonl").open("w") as handle:
        for record in consolidated:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    build()
