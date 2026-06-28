from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tools.ai_model_benchmark import (
    DEFAULT_CASES_PATH,
    DEFAULT_MODELS,
    BenchmarkCase,
    filter_cases,
    load_cases,
    same_top_level_intent,
)


DEFAULT_OUTPUT_DIR = ROOT_DIR / "outputs" / "ai_copilot_real_benchmark"
FALLBACK_RESPONSE = "The request is not valid for exam scheduling. Please rephrase."
SUPPORTED_BLOCK_REASONS = {
    "invalid_context",
    "security_violation",
    "unsupported_constraint",
    "protected_constraint",
    "duplicate_constraint",
    "invalid_json",
    "invalid_schema",
    "model_timeout",
    "model_unavailable",
}


@dataclass(frozen=True)
class RealRunResult:
    case: BenchmarkCase
    model: str
    repeat: int
    elapsed_ms: int
    finished: bool
    constraint: dict[str, Any] | None
    response: str
    blocked_reason: str
    raw_model_output: str
    raw_model_stderr: str
    score: int
    reason: str


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cases = load_cases(args.cases)
    selected_cases = filter_cases(cases, args.case_id, args.category)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not selected_cases:
        raise SystemExit("No benchmark cases matched the selected filters.")

    if args.validate_only:
        print(f"Validated {len(selected_cases)} English-only benchmark cases.")
        return 0

    try:
        ensure_qt_runtime_available()
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "PyQt6 is required for the real AI Copilot benchmark. "
            "Run it from the same environment that launches the desktop app."
        ) from exc

    results: list[RealRunResult] = []
    for model in args.models:
        if args.warmup:
            run_real_worker(
                selected_cases[0],
                model=model,
                repeat=0,
                ollama_program=args.ollama or None,
                output_dir=output_dir,
                outer_timeout_seconds=args.outer_timeout_seconds,
                worker_timeout_seconds=args.worker_timeout_seconds,
            )
        for case in selected_cases:
            for repeat in range(1, args.repeats + 1):
                result = run_real_worker(
                    case,
                    model=model,
                    repeat=repeat,
                    ollama_program=args.ollama or None,
                    output_dir=output_dir,
                    outer_timeout_seconds=args.outer_timeout_seconds,
                    worker_timeout_seconds=args.worker_timeout_seconds,
                )
                results.append(result)
                print(
                    f"{model} | {case.id} | repeat {repeat} | "
                    f"score {result.score}/2 | {result.elapsed_ms} ms | {result.reason}",
                    flush=True,
                )

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    raw_csv = output_dir / f"ai_copilot_real_benchmark_raw_{timestamp}.csv"
    summary_csv = output_dir / f"ai_copilot_real_benchmark_summary_{timestamp}.csv"
    summary_md = output_dir / f"ai_copilot_real_benchmark_summary_{timestamp}.md"

    write_raw_csv(raw_csv, results)
    write_summary_csv(summary_csv, results)
    write_summary_markdown(summary_md, results, args.models)

    print("")
    print(f"Raw results: {raw_csv}")
    print(f"Summary CSV: {summary_csv}")
    print(f"Summary report: {summary_md}")
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare local Ollama models through the real AICopilotWorker path: "
            "sanitization, deterministic routing, model invocation, validation, "
            "signals, and blocked-request audit reasons."
        )
    )
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--models", nargs="+", default=list(DEFAULT_MODELS))
    parser.add_argument(
        "--ollama",
        default="",
        help=(
            "Optional path to ollama.exe. When omitted, the worker uses the same "
            "resolution logic as the desktop app."
        ),
    )
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--category", action="append", default=[])
    parser.add_argument(
        "--outer-timeout-seconds",
        type=int,
        default=45,
        help="Hard safety timeout around each worker run.",
    )
    parser.add_argument(
        "--worker-timeout-seconds",
        type=int,
        default=30,
        help="AICopilotWorker model timeout. Default matches production.",
    )
    parser.add_argument("--warmup", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args(argv)


def ensure_qt_runtime_available() -> None:
    import PyQt6.QtCore  # noqa: F401


def run_real_worker(
    case: BenchmarkCase,
    *,
    model: str,
    repeat: int,
    ollama_program: str | None,
    output_dir: Path,
    outer_timeout_seconds: int,
    worker_timeout_seconds: int,
) -> RealRunResult:
    from PyQt6.QtCore import QCoreApplication, QEventLoop, QTimer

    from src.ui.ai_copilot_worker import AICopilotWorker

    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication(["ai-copilot-real-benchmark"])

    log_dir = output_dir / "security_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    security_log_path = log_dir / (
        f"{safe_filename(model)}_{case.id}_repeat{repeat}_{time.time_ns()}.jsonl"
    )

    context = case.context or {}
    worker = AICopilotWorker(
        case.request,
        ollama_program=ollama_program,
        model_name=model,
        existing_constraints=context.get("existing_constraints", {}),
        chatbot_rules=context.get("chatbot_rules", {}),
        security_log_path=security_log_path,
    )
    worker.INFERENCE_TIMEOUT_MS = max(1, worker_timeout_seconds) * 1000

    constraints: list[dict[str, Any]] = []
    responses: list[str] = []
    finished = {"value": False}
    outer_timeout = {"value": False}

    loop = QEventLoop()
    timer = QTimer()
    timer.setSingleShot(True)

    def mark_finished() -> None:
        finished["value"] = True
        if timer.isActive():
            timer.stop()
        if loop.isRunning():
            loop.quit()

    def mark_outer_timeout() -> None:
        outer_timeout["value"] = True
        if worker.isRunning():
            try:
                worker._handle_inference_timeout()  # Uses the production timeout path.
            except Exception:
                pass
        if loop.isRunning():
            loop.quit()

    worker.constraint_ready.connect(lambda payload: constraints.append(dict(payload)))
    worker.response_ready.connect(lambda message: responses.append(str(message)))
    worker.finished.connect(mark_finished)
    timer.timeout.connect(mark_outer_timeout)

    started = time.perf_counter()
    worker.start()
    if not finished["value"] and worker.isRunning():
        timer.start(max(1, outer_timeout_seconds) * 1000)
        loop.exec()
    elapsed_ms = int((time.perf_counter() - started) * 1000)

    blocked_reason = read_latest_block_reason(security_log_path)
    constraint = constraints[-1] if constraints else None
    response = responses[-1] if responses else ""
    raw_model_output = "".join(getattr(worker, "_stdout_chunks", []))
    raw_model_stderr = str(getattr(worker, "_stderr_text", ""))

    if outer_timeout["value"] and not blocked_reason:
        blocked_reason = "outer_timeout"

    score, reason = score_real_result(
        case,
        constraint=constraint,
        response=response,
        blocked_reason=blocked_reason,
        finished=finished["value"] or outer_timeout["value"],
    )

    worker.deleteLater()
    app.processEvents()

    return RealRunResult(
        case=case,
        model=model,
        repeat=repeat,
        elapsed_ms=elapsed_ms,
        finished=finished["value"],
        constraint=constraint,
        response=response,
        blocked_reason=blocked_reason,
        raw_model_output=raw_model_output,
        raw_model_stderr=raw_model_stderr,
        score=score,
        reason=reason,
    )


def score_real_result(
    case: BenchmarkCase,
    *,
    constraint: dict[str, Any] | None,
    response: str,
    blocked_reason: str,
    finished: bool,
) -> tuple[int, str]:
    if not finished:
        return 0, "worker_not_finished"

    expected = case.expected
    expected_error = expected.get("error")
    if expected_error:
        if constraint is not None:
            return 0, "unexpected_constraint_for_blocked_case"
        if blocked_reason == expected_error:
            return 2, "expected_block_reason"
        if blocked_reason in SUPPORTED_BLOCK_REASONS or response == FALLBACK_RESPONSE:
            return 1, f"blocked_with_different_reason:{blocked_reason or 'unknown'}"
        return 0, "not_blocked"

    if constraint is None:
        return 0, f"missing_constraint:{blocked_reason or response or 'no_output'}"

    if case.match == "exact":
        if constraint == expected:
            return 2, "exact_match"
        if same_top_level_intent(constraint, expected):
            return 1, "same_intent_wrong_details"
        return 0, "wrong_intent"

    if case.match == "action":
        if constraint.get("action") != expected.get("action"):
            return 0, "wrong_action"
        if all(key in constraint for key in case.required_keys):
            return 2, "action_match"
        return 1, "action_match_missing_required_key"

    return 0, "unknown_match_type"


def read_latest_block_reason(path: Path) -> str:
    if not path.exists():
        return ""
    reason = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        reason = str(record.get("reason", ""))
    return reason


def write_raw_csv(path: Path, results: list[RealRunResult]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "model",
                "case_id",
                "category",
                "repeat",
                "score",
                "reason",
                "elapsed_ms",
                "finished",
                "request",
                "expected_json",
                "constraint_json",
                "response",
                "blocked_reason",
                "raw_model_output",
                "raw_model_stderr",
            ],
        )
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "model": result.model,
                    "case_id": result.case.id,
                    "category": result.case.category,
                    "repeat": result.repeat,
                    "score": result.score,
                    "reason": result.reason,
                    "elapsed_ms": result.elapsed_ms,
                    "finished": result.finished,
                    "request": result.case.request,
                    "expected_json": json.dumps(result.case.expected, sort_keys=True),
                    "constraint_json": json.dumps(result.constraint, sort_keys=True) if result.constraint is not None else "",
                    "response": result.response,
                    "blocked_reason": result.blocked_reason,
                    "raw_model_output": result.raw_model_output,
                    "raw_model_stderr": result.raw_model_stderr,
                }
            )


def write_summary_csv(path: Path, results: list[RealRunResult]) -> None:
    rows = summarize_by_model(results)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "model",
                "runs",
                "max_score",
                "score",
                "score_percent",
                "full_passes",
                "avg_elapsed_ms",
                "p95_elapsed_ms",
                "worst_elapsed_ms",
                "blocked_cases_full_passes",
                "constraint_cases_full_passes",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def write_summary_markdown(
    path: Path,
    results: list[RealRunResult],
    models: list[str],
) -> None:
    rows = summarize_by_model(results)
    lines = [
        "# Real AI Copilot Benchmark Summary",
        "",
        "This report uses the production AICopilotWorker path, not a hand-built prompt.",
        "",
        "| Model | Score | Passes | Avg ms | P95 ms | Worst ms | Blocked pass | Constraint pass |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {model} | {score}/{max_score} ({score_percent:.1f}%) | "
            "{full_passes}/{runs} | {avg_elapsed_ms:.0f} | {p95_elapsed_ms:.0f} | "
            "{worst_elapsed_ms:.0f} | {blocked_cases_full_passes} | "
            "{constraint_cases_full_passes} |".format(**row)
        )

    lines.extend(["", "## Per-Case Average Score", ""])
    lines.append("| Case | Category | " + " | ".join(models) + " |")
    lines.append("|---|---|" + "|".join(["---:"] * len(models)) + "|")
    per_case = summarize_by_case_and_model(results)
    case_order = []
    seen = set()
    for result in results:
        if result.case.id not in seen:
            seen.add(result.case.id)
            case_order.append((result.case.id, result.case.category))
    for case_id, category in case_order:
        scores = [f"{per_case.get((case_id, model), 0.0):.2f}" for model in models]
        lines.append(f"| {case_id} | {category} | " + " | ".join(scores) + " |")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def summarize_by_model(results: list[RealRunResult]) -> list[dict[str, Any]]:
    grouped: dict[str, list[RealRunResult]] = defaultdict(list)
    for result in results:
        grouped[result.model].append(result)

    rows = []
    for model, model_results in grouped.items():
        elapsed = sorted(result.elapsed_ms for result in model_results)
        runs = len(model_results)
        score = sum(result.score for result in model_results)
        max_score = runs * 2
        blocked = [result for result in model_results if "error" in result.case.expected]
        constraints = [result for result in model_results if "error" not in result.case.expected]
        rows.append(
            {
                "model": model,
                "runs": runs,
                "max_score": max_score,
                "score": score,
                "score_percent": (score / max_score * 100) if max_score else 0.0,
                "full_passes": sum(1 for result in model_results if result.score == 2),
                "avg_elapsed_ms": sum(elapsed) / runs if runs else 0.0,
                "p95_elapsed_ms": percentile(elapsed, 95),
                "worst_elapsed_ms": max(elapsed) if elapsed else 0.0,
                "blocked_cases_full_passes": f"{sum(1 for result in blocked if result.score == 2)}/{len(blocked)}",
                "constraint_cases_full_passes": f"{sum(1 for result in constraints if result.score == 2)}/{len(constraints)}",
            }
        )
    return rows


def summarize_by_case_and_model(results: list[RealRunResult]) -> dict[tuple[str, str], float]:
    grouped: dict[tuple[str, str], list[int]] = defaultdict(list)
    for result in results:
        grouped[(result.case.id, result.model)].append(result.score)
    return {key: sum(scores) / len(scores) for key, scores in grouped.items()}


def percentile(values: list[int], percentile_value: int) -> float:
    if not values:
        return 0.0
    index = min(len(values) - 1, round((percentile_value / 100) * (len(values) - 1)))
    return float(values[index])


def safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
