from __future__ import annotations

import csv
import json
import os
import queue
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from src.parser.file_parser import FileParser
from src.process_protocol import BATCH_END_MARKER, LAZY_NEXT_COMMAND, LAZY_STOP_COMMAND
from src.services.dashboard_analytics_service import DashboardAnalyticsService
from src.services.process_resource_logger import ProcessMetrics, SystemResourceSampler
from src.services.schedule_output_service import (
    ScheduleOutputDataAdapter,
    StdoutScheduleParser,
    parse_schedule_total,
)
from src.sorting.schedule_priority import (
    AVERAGE_COHORT_GAP,
    MANDATORY_MIN_GAP,
    MAX_DAILY_EXAMS,
)
from src.ui.schedule_best_tracker import ScheduleBestTracker
from src.workflow import load_domain_context


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUN_FULL_STRESS = os.environ.get("EXAMSCHEDULER_RUN_FULL_SYSTEM_STRESS") == "1"


@pytest.mark.skipif(
    not RUN_FULL_STRESS,
    reason="Set EXAMSCHEDULER_RUN_FULL_SYSTEM_STRESS=1 to run the full stress suite.",
)
def test_full_system_lazy_scheduler_dashboard_ai_rules_and_reload_stress(tmp_path):
    """Opt-in full-system stress test for the real scheduler process.

    The test intentionally keeps normal pytest runs safe. When enabled, it covers:
    parser/file loading, active AI rules, lazy CLI scheduling, bounded cancellation,
    repeated generation, sorting on a bounded run, stdout parsing, rolling best
    schedule tracking, deterministic dashboard analytics, and resource reporting.
    """
    report_dir = Path(
        os.environ.get(
            "EXAMSCHEDULER_FULL_STRESS_REPORT_DIR",
            PROJECT_ROOT / "performance_logs",
        )
    ).expanduser().resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    sample_report = report_dir / f"full_system_stress_samples_{timestamp}.csv"
    summary_report = report_dir / f"full_system_stress_summary_{timestamp}.json"

    extreme = _StressDataset.write(
        tmp_path / "extreme",
        course_count=_env_int("EXAMSCHEDULER_FULL_STRESS_COURSES", 18),
        period_days=_env_int("EXAMSCHEDULER_FULL_STRESS_DAYS", 42),
        include_sorting=False,
        include_spacing_rule=False,
    )
    sorted_case = _StressDataset.write(
        tmp_path / "sorted",
        course_count=_env_int("EXAMSCHEDULER_FULL_STRESS_SORTED_COURSES", 6),
        period_days=_env_int("EXAMSCHEDULER_FULL_STRESS_SORTED_DAYS", 10),
        include_sorting=True,
        include_spacing_rule=True,
    )

    summary: dict[str, object] = {
        "sample_report": str(sample_report),
        "summary_report": str(summary_report),
        "phases": [],
    }

    with _StressRecorder(sample_report) as recorder:
        cancelled = _run_lazy_phase(
            name="cancel_running_scheduler_before_reload",
            dataset=extreme,
            max_systems=1000,
            requested_batches=1,
            recorder=recorder,
            terminate_after_first_batch=True,
        )
        summary["phases"].append(cancelled)

        extreme_result = _run_lazy_phase(
            name="extreme_unsorted_lazy_generation",
            dataset=extreme,
            max_systems=_env_int("EXAMSCHEDULER_FULL_STRESS_MAX_SYSTEMS", 3000),
            requested_batches=_env_int("EXAMSCHEDULER_FULL_STRESS_BATCHES", 3),
            recorder=recorder,
        )
        summary["phases"].append(extreme_result)

        sorted_result = _run_lazy_phase(
            name="bounded_sorted_dashboard_generation",
            dataset=sorted_case,
            max_systems=_env_int(
                "EXAMSCHEDULER_FULL_STRESS_SORTED_MAX_SYSTEMS",
                300,
            ),
            requested_batches=1,
            recorder=recorder,
        )
        summary["phases"].append(sorted_result)

        summary["resource_peaks"] = recorder.peaks

    summary_report.write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    max_child_rss_mb = _env_float("EXAMSCHEDULER_FULL_STRESS_MAX_CHILD_RSS_MB", 2048)
    max_gui_rss_mb = _env_float("EXAMSCHEDULER_FULL_STRESS_MAX_GUI_RSS_MB", 1024)
    max_system_memory_percent = _env_float(
        "EXAMSCHEDULER_FULL_STRESS_MAX_SYSTEM_MEMORY_PERCENT",
        98,
    )

    print(f"Full system stress sample report: {sample_report}")
    print(f"Full system stress summary report: {summary_report}")

    assert all(phase["process_exited"] for phase in summary["phases"])
    assert all(phase["parsed_schedule_count"] > 0 for phase in summary["phases"])
    assert all(phase["dashboard_has_data"] for phase in summary["phases"])
    assert summary["resource_peaks"]["child_peak_rss_mb"] <= max_child_rss_mb
    assert summary["resource_peaks"]["gui_peak_rss_mb"] <= max_gui_rss_mb
    assert (
        summary["resource_peaks"]["system_memory_used_peak_percent"]
        <= max_system_memory_percent
    )


def _run_lazy_phase(
    *,
    name: str,
    dataset: "_StressDataset",
    max_systems: int,
    requested_batches: int,
    recorder: "_StressRecorder",
    terminate_after_first_batch: bool = False,
) -> dict[str, object]:
    context = load_domain_context(
        dataset.config_file,
        parser=FileParser(),
        course_file=dataset.course_file,
        dates_file=dataset.dates_file,
        user_file=dataset.user_file,
        ai_rules_file=dataset.ai_rules_file,
        sorting_file=dataset.sorting_file,
    )
    assert context.courses
    assert context.periods
    assert context.selected_programs

    command = [
        sys.executable,
        "-u",
        str(PROJECT_ROOT / "main.py"),
        "--mode",
        "complete-write",
        "--output-config",
        str(dataset.config_file),
        "--source-type",
        "file",
        "--lazy-schedules",
        "--max-systems",
        str(max_systems),
        "--course-file",
        str(dataset.course_file),
        "--dates-file",
        str(dataset.dates_file),
        "--user-file",
        str(dataset.user_file),
        "--ai-rules-file",
        str(dataset.ai_rules_file),
    ]
    if dataset.sorting_file is not None:
        command.extend(["--sorting-file", str(dataset.sorting_file)])

    process = subprocess.Popen(
        command,
        cwd=PROJECT_ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    stdout_reader = _StreamReader(process.stdout)
    stderr_reader = _StreamReader(process.stderr)
    stdout_reader.start()
    stderr_reader.start()
    recorder.begin_phase(name, process.pid)

    parser = StdoutScheduleParser()
    adapter = ScheduleOutputDataAdapter(context.courses, context.selected_programs)
    best_tracker = ScheduleBestTracker()
    best_tracker.reset(context.sort_priority)
    dashboard_service = DashboardAnalyticsService()

    parsed_count = 0
    total_schedules = 0
    current_batch_best = None
    first_number = None
    last_number = None
    dashboard_has_data = False
    stderr_text = ""

    try:
        for batch_index in range(requested_batches):
            if batch_index > 0:
                assert process.stdin is not None
                process.stdin.write(f"{LAZY_NEXT_COMMAND}\n")
                process.stdin.flush()

            chunk = stdout_reader.read_until_marker(
                marker=BATCH_END_MARKER,
                timeout_seconds=_env_float(
                    "EXAMSCHEDULER_FULL_STRESS_BATCH_TIMEOUT_SECONDS",
                    120,
                ),
                recorder=lambda: recorder.sample(name, process.pid),
            )
            total_schedules = parse_schedule_total(chunk) or total_schedules
            systems = adapter.convert(parser.feed(chunk))
            assert systems, f"{name} did not produce schedules in batch {batch_index + 1}"

            parsed_count += len(systems)
            first_number = first_number or systems[0].number
            last_number = systems[-1].number

            batch_tracker = ScheduleBestTracker()
            batch_tracker.reset(context.sort_priority)
            batch_tracker.update_batch(systems)
            current_batch_best = batch_tracker.best_schedule
            best_tracker.update_batch(systems)

            snapshot = dashboard_service.build_snapshot(
                best_tracker.best_schedule,
                current_batch_schedule=current_batch_best,
                active_priorities=context.sort_priority,
                total_schedules=total_schedules,
                current_page=batch_index + 1,
            )
            dashboard_has_data = bool(snapshot.chart_dates or snapshot.winning_text)

            if terminate_after_first_batch:
                break

        if terminate_after_first_batch:
            _terminate_process(process, recorder, name)
        else:
            _stop_process(process)
    finally:
        if process.poll() is None:
            _terminate_process(process, recorder, name)
        recorder.sample(name, process.pid)
        stdout_reader.close()
        stderr_reader.close()
        stderr_text = stderr_reader.drain()
        recorder.end_phase(name)

    return {
        "name": name,
        "command": command,
        "process_exited": process.poll() is not None,
        "exit_code": process.returncode,
        "parsed_schedule_count": parsed_count,
        "first_schedule_number": first_number,
        "last_schedule_number": last_number,
        "best_schedule_so_far": (
            best_tracker.best_schedule.number if best_tracker.best_schedule else None
        ),
        "current_batch_best": (
            current_batch_best.number if current_batch_best else None
        ),
        "total_schedules": total_schedules,
        "dashboard_has_data": dashboard_has_data,
        "stderr_tail": stderr_text[-4000:],
    }


@dataclass(frozen=True)
class _StressDataset:
    root: Path
    config_file: Path
    course_file: Path
    dates_file: Path
    user_file: Path
    ai_rules_file: Path
    sorting_file: Path | None

    @classmethod
    def write(
        cls,
        root: Path,
        *,
        course_count: int,
        period_days: int,
        include_sorting: bool,
        include_spacing_rule: bool,
    ) -> "_StressDataset":
        root.mkdir(parents=True, exist_ok=True)
        course_file = root / "Courses_stress.txt"
        dates_file = root / "ExamDates_stress.txt"
        user_file = root / "Programs_stress.txt"
        config_file = root / "config_stress.json"
        ai_rules_file = root / "active_ai_rules.json"
        sorting_file = root / "sorting_priority.txt" if include_sorting else None

        course_file.write_text(_course_text(course_count), encoding="utf-8")
        dates_file.write_text(_dates_text(period_days), encoding="utf-8")
        user_file.write_text("83101, 83102, 83104, 83107, 83108", encoding="utf-8")
        ai_rules_file.write_text(
            json.dumps(
                _ai_rules(include_spacing_rule),
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        if sorting_file is not None:
            sorting_file.write_text(
                "\n".join(
                    [
                        "$$$$",
                        "sorting_priority",
                        MANDATORY_MIN_GAP,
                        AVERAGE_COHORT_GAP,
                        MAX_DAILY_EXAMS,
                    ]
                ),
                encoding="utf-8",
            )
        config_file.write_text(
            json.dumps(
                {
                    "source_type": "file",
                    "file": {
                        "course_file": str(course_file),
                        "dates_file": str(dates_file),
                        "user_file": str(user_file),
                        "ai_rules_file": str(ai_rules_file),
                    },
                    "output_settings": {
                        "base_directory": str(root / "outputs"),
                        "master_filename": "stress_master_schedule",
                    },
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return cls(
            root=root,
            config_file=config_file,
            course_file=course_file,
            dates_file=dates_file,
            user_file=user_file,
            ai_rules_file=ai_rules_file,
            sorting_file=sorting_file,
        )


class _StreamReader:
    def __init__(self, stream) -> None:
        self._stream = stream
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._lines: list[str] = []
        self._thread = threading.Thread(target=self._read_loop, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def read_until_marker(
        self,
        *,
        marker: str,
        timeout_seconds: float,
        recorder,
    ) -> str:
        deadline = time.monotonic() + timeout_seconds
        collected: list[str] = []
        while time.monotonic() < deadline:
            recorder()
            try:
                line = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue
            if line is None:
                break
            collected.append(line)
            if marker in line:
                return "".join(collected)
        raise TimeoutError(f"Timed out waiting for {marker}")

    def drain(self) -> str:
        while True:
            try:
                line = self._queue.get_nowait()
            except queue.Empty:
                break
            if line is not None:
                self._lines.append(line)
        return "".join(self._lines)

    def close(self) -> None:
        self._thread.join(timeout=1.0)

    def _read_loop(self) -> None:
        try:
            for line in self._stream:
                self._lines.append(line)
                self._queue.put(line)
        finally:
            self._queue.put(None)


class _StressRecorder:
    _fieldnames = (
        "phase",
        "elapsed_seconds",
        "child_rss_mb",
        "child_peak_rss_mb",
        "gui_rss_mb",
        "gui_peak_rss_mb",
        "child_cpu_percent_one_core",
        "system_cpu_percent",
        "system_memory_used_percent",
        "available_memory_mb",
    )

    def __init__(self, path: Path) -> None:
        self.path = path
        self._sampler = SystemResourceSampler()
        self._file = None
        self._writer = None
        self._phase_started_at = 0.0
        self._phase_child_start: ProcessMetrics | None = None
        self._phase_system_start: _SystemSnapshot | None = None
        self._peaks = {
            "child_peak_rss_mb": 0.0,
            "gui_peak_rss_mb": 0.0,
            "system_memory_used_peak_percent": 0.0,
        }

    @property
    def peaks(self) -> dict[str, float]:
        return dict(self._peaks)

    def __enter__(self) -> "_StressRecorder":
        self._file = self.path.open("w", encoding="utf-8", newline="")
        self._writer = csv.DictWriter(self._file, fieldnames=self._fieldnames)
        self._writer.writeheader()
        return self

    def __exit__(self, *_exc_info) -> None:
        if self._file is not None:
            self._file.close()

    def begin_phase(self, _phase: str, process_id: int) -> None:
        self._phase_started_at = time.perf_counter()
        self._phase_child_start = self._sampler.sample_process(process_id)
        self._phase_system_start = _system_snapshot()

    def sample(self, phase: str, process_id: int) -> None:
        if self._writer is None:
            return
        elapsed = max(time.perf_counter() - self._phase_started_at, 0.001)
        child = self._sampler.sample_process(process_id)
        gui = self._sampler.sample_process(os.getpid())
        system = _system_snapshot()
        child_rss = _mb(child.rss_bytes) if child else 0.0
        gui_rss = _mb(gui.rss_bytes) if gui else 0.0
        system_memory = system.memory_used_percent

        self._peaks["child_peak_rss_mb"] = max(
            self._peaks["child_peak_rss_mb"],
            child_rss,
        )
        self._peaks["gui_peak_rss_mb"] = max(
            self._peaks["gui_peak_rss_mb"],
            gui_rss,
        )
        self._peaks["system_memory_used_peak_percent"] = max(
            self._peaks["system_memory_used_peak_percent"],
            system_memory,
        )

        self._writer.writerow(
            {
                "phase": phase,
                "elapsed_seconds": f"{elapsed:.3f}",
                "child_rss_mb": f"{child_rss:.2f}",
                "child_peak_rss_mb": f"{self._peaks['child_peak_rss_mb']:.2f}",
                "gui_rss_mb": f"{gui_rss:.2f}",
                "gui_peak_rss_mb": f"{self._peaks['gui_peak_rss_mb']:.2f}",
                "child_cpu_percent_one_core": f"{_process_cpu_percent(self._phase_child_start, child, elapsed):.2f}",
                "system_cpu_percent": f"{_system_cpu_percent(self._phase_system_start, system):.2f}",
                "system_memory_used_percent": f"{system_memory:.2f}",
                "available_memory_mb": f"{_mb(system.available_memory):.2f}",
            }
        )
        self._file.flush()

    def end_phase(self, _phase: str) -> None:
        self._phase_child_start = None
        self._phase_system_start = None


@dataclass(frozen=True)
class _SystemSnapshot:
    idle_ticks: int
    total_ticks: int
    total_memory: int
    available_memory: int

    @property
    def memory_used_percent(self) -> float:
        if self.total_memory <= 0:
            return 0.0
        return 100.0 * (self.total_memory - self.available_memory) / self.total_memory


def _course_text(course_count: int) -> str:
    programs = ("83101", "83102", "83104", "83107", "83108")
    records = []
    for index in range(course_count):
        program = programs[index % len(programs)]
        year = (index % 4) + 1
        requirement = "Elective" if index % 3 else "Obligatory"
        semester = "FALL" if index % 2 == 0 else "SPRI"
        records.append(
            "\n".join(
                [
                    "$$$$",
                    f"Stress Course {index + 1:02d}",
                    f"{11000 + index}",
                    f"Dr. Stress {index % 5}",
                    f"{program},{year},{semester},{requirement}",
                    "Exam",
                ]
            )
        )
    return "\n".join(records) + "\n"


def _dates_text(period_days: int) -> str:
    days = max(period_days, 10)
    fall_start = date(2027, 1, 1)
    spring_start = date(2027, 3, 1)
    fall_end = fall_start + timedelta(days=days - 1)
    spring_end = spring_start + timedelta(days=days - 1)
    return "\n".join(
        [
            "$$$$",
            "FALL,Aleph",
            f"{fall_start:%d-%m-%Y}, {fall_end:%d-%m-%Y}",
            "02-01-2027 Synthetic maintenance day",
            "$$$$",
            "SPRI,Aleph",
            f"{spring_start:%d-%m-%Y}, {spring_end:%d-%m-%Y}",
            "02-03-2027 Synthetic maintenance day",
            "",
        ]
    )


def _ai_rules(include_spacing_rule: bool) -> list[dict]:
    rules = [
        {
            "rule_id": "ai_rule_1",
            "description": "Exclude Friday from stress scheduling",
            "rule_type": "exclude_day",
            "parameters": {"weekday": "Friday"},
        },
        {
            "rule_id": "ai_rule_2",
            "description": "Dr. Stress 1 unavailable on Monday",
            "rule_type": "lecturer_unavailable",
            "parameters": {"lecturer": "Stress 1", "weekday": "Monday"},
        },
        {
            "rule_id": "ai_rule_3",
            "description": "Wide safety limit for program 83101",
            "rule_type": "program_limit",
            "parameters": {"program": "83101", "max_exams_per_day": 9},
        },
    ]
    if include_spacing_rule:
        rules.append(
            {
                "rule_id": "ai_rule_4",
                "description": "Keep at least one day between exams",
                "rule_type": "exam_spacing",
                "parameters": {"min_days": 1},
            }
        )
    return rules


def _stop_process(process: subprocess.Popen) -> None:
    if process.stdin is not None:
        process.stdin.write(f"{LAZY_STOP_COMMAND}\n")
        process.stdin.flush()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def _terminate_process(
    process: subprocess.Popen,
    recorder: _StressRecorder,
    phase: str,
) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    deadline = time.monotonic() + 1.5
    while process.poll() is None and time.monotonic() < deadline:
        recorder.sample(phase, process.pid)
        time.sleep(0.1)
    if process.poll() is None:
        process.kill()
    process.wait(timeout=5)


def _system_snapshot() -> _SystemSnapshot:
    if sys.platform == "win32":
        return _windows_system_snapshot()
    if sys.platform.startswith("linux"):
        return _linux_system_snapshot()
    return _SystemSnapshot(0, 0, 0, 0)


def _windows_system_snapshot() -> _SystemSnapshot:
    import ctypes
    from ctypes import wintypes

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = (
            ("dwLength", wintypes.DWORD),
            ("dwMemoryLoad", wintypes.DWORD),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        )

    idle = wintypes.FILETIME()
    kernel = wintypes.FILETIME()
    user = wintypes.FILETIME()
    kernel32 = ctypes.windll.kernel32
    if not kernel32.GetSystemTimes(
        ctypes.byref(idle),
        ctypes.byref(kernel),
        ctypes.byref(user),
    ):
        raise OSError("GetSystemTimes failed")
    memory = MEMORYSTATUSEX()
    memory.dwLength = ctypes.sizeof(memory)
    if not kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
        raise OSError("GlobalMemoryStatusEx failed")
    return _SystemSnapshot(
        idle_ticks=_filetime_value(idle),
        total_ticks=_filetime_value(kernel) + _filetime_value(user),
        total_memory=int(memory.ullTotalPhys),
        available_memory=int(memory.ullAvailPhys),
    )


def _linux_system_snapshot() -> _SystemSnapshot:
    cpu_values = [
        int(value)
        for value in Path("/proc/stat")
        .read_text(encoding="ascii")
        .splitlines()[0]
        .split()[1:]
    ]
    memory_values = {}
    for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
        key, value, *_unit = line.replace(":", "").split()
        memory_values[key] = int(value) * 1024
    return _SystemSnapshot(
        idle_ticks=cpu_values[3] + cpu_values[4],
        total_ticks=sum(cpu_values),
        total_memory=memory_values.get("MemTotal", 0),
        available_memory=memory_values.get("MemAvailable", 0),
    )


def _process_cpu_percent(
    before: ProcessMetrics | None,
    after: ProcessMetrics | None,
    elapsed: float,
) -> float:
    if before is None or after is None:
        return 0.0
    return max(0.0, 100.0 * (after.cpu_seconds - before.cpu_seconds) / elapsed)


def _system_cpu_percent(
    before: _SystemSnapshot | None,
    after: _SystemSnapshot,
) -> float:
    if before is None:
        return 0.0
    total_delta = after.total_ticks - before.total_ticks
    idle_delta = after.idle_ticks - before.idle_ticks
    if total_delta <= 0:
        return 0.0
    return max(0.0, min(100.0, 100.0 * (total_delta - idle_delta) / total_delta))


def _filetime_value(filetime) -> int:
    return (filetime.dwHighDateTime << 32) | filetime.dwLowDateTime


def _mb(value: int) -> float:
    return value / (1024 * 1024)


def _env_int(name: str, default: int) -> int:
    return int(os.environ.get(name, str(default)))


def _env_float(name: str, default: float) -> float:
    return float(os.environ.get(name, str(default)))
