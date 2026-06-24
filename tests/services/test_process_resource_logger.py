import csv
import os

from src.services.process_resource_logger import (
    ProcessMetrics,
    ProcessResourceLogger,
)


class _FakeSampler:
    def __init__(self) -> None:
        self.cpu_seconds = 1.0

    def sample_process(self, process_id: int) -> ProcessMetrics:
        self.cpu_seconds += 0.25
        return ProcessMetrics(
            rss_bytes=process_id * 1024,
            private_bytes=process_id * 2048,
            cpu_seconds=self.cpu_seconds,
        )

    def available_memory_bytes(self) -> int:
        return 8 * 1024 * 1024


class _FakeClock:
    def __init__(self) -> None:
        self.value = 100.0

    def __call__(self) -> float:
        self.value += 1.0
        return self.value


def test_resource_logger_writes_flushed_lifecycle_and_progress_rows(tmp_path):
    logger = ProcessResourceLogger(
        tmp_path,
        sampler=_FakeSampler(),
        clock=_FakeClock(),
    )

    logger.start("python", ["main.py", "--mode", "auto"])
    logger.process_started(4321)
    logger.record_output(
        "stderr",
        "Preparing lazy complete-system stream...\n",
    )
    logger.record_output(
        "stdout",
        "Total complete systems: 22,809,600\nComplete System #1\n",
    )
    logger.sample()
    logger.finish(0, "NormalExit")

    with logger.path.open(newline="", encoding="utf-8") as log_file:
        rows = list(csv.DictReader(log_file))

    assert logger.path.parent == tmp_path
    assert rows[0]["event"] == "start_requested"
    assert rows[0]["code_revision"] == "unknown"
    assert rows[0]["python_version"]
    assert any(row["event"] == "process_started" for row in rows)
    assert any(row["event"] == "first_result" for row in rows)
    assert rows[-1]["event"] == "process_finished"
    assert rows[-1]["exit_code"] == "0"
    assert rows[-1]["exit_status"] == "NormalExit"
    assert rows[-1]["results_seen"] == "1"
    assert rows[-1]["total_results"] == "22809600"
    assert rows[-1]["child_peak_rss_mb"]
    assert rows[-1]["available_memory_mb"] == "8.00"


def test_resource_logger_records_gui_process_separately(tmp_path):
    logger = ProcessResourceLogger(
        tmp_path,
        sampler=_FakeSampler(),
        clock=_FakeClock(),
    )

    logger.start("python", ["main.py"])
    logger.process_started(9876)
    logger.sample()
    logger.finish(1, "CrashExit")

    with logger.path.open(newline="", encoding="utf-8") as log_file:
        rows = list(csv.DictReader(log_file))

    sample = next(row for row in rows if row["event"] == "sample")
    assert sample["child_pid"] == "9876"
    assert sample["gui_pid"] == str(os.getpid())
    assert sample["child_rss_mb"] != sample["gui_rss_mb"]
    assert sample["child_cpu_percent_one_core"]
    assert sample["gui_cpu_percent_one_core"]
