from __future__ import annotations

import csv
import os
import shutil
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pytest
from PyQt6.QtCore import QObject, pyqtSignal

from src.services.process_resource_logger import (
    ProcessMetrics,
    SystemResourceSampler,
)
from src.ui.ai_copilot_worker import AICopilotWorker


class _FakeProcess(QObject):
    readyReadStandardOutput = pyqtSignal()
    readyReadStandardError = pyqtSignal()
    finished = pyqtSignal(int, object)
    errorOccurred = pyqtSignal(object)

    def __init__(self) -> None:
        super().__init__()
        self.program = None
        self.arguments = None
        self.environment = None
        self.stdout = b""
        self.stderr = b""
        self.killed = False

    def setProcessEnvironment(self, environment) -> None:
        self.environment = environment

    def start(self, program, arguments) -> None:
        self.program = program
        self.arguments = list(arguments)

    def closeWriteChannel(self) -> None:
        return None

    def readAllStandardOutput(self):
        output, self.stdout = self.stdout, b""
        return output

    def readAllStandardError(self):
        output, self.stderr = self.stderr, b""
        return output

    def kill(self) -> None:
        self.killed = True


class _MemorySampler:
    def __init__(self, available_memory: int) -> None:
        self.available_memory = available_memory

    def available_memory_bytes(self) -> int:
        return self.available_memory

    def sample_process(self, _process_id: int):
        return None


def test_chatbot_rejects_inference_before_oom(tmp_path, qtbot):
    process = _FakeProcess()
    worker = AICopilotWorker(
        "Please help with the Physics exam schedule",
        process=process,
        ollama_program="ollama-test",
        model_name="test-model",
        security_log_path=tmp_path / "security_log.txt",
        resource_sampler=_MemorySampler(
            AICopilotWorker.MIN_AVAILABLE_MEMORY_BYTES - 1
        ),
    )
    responses: list[str] = []
    worker.response_ready.connect(responses.append)

    with qtbot.waitSignal(worker.finished, timeout=1000):
        worker.start()

    assert responses == [worker.MODEL_MEMORY_MESSAGE]
    assert process.program is None
    assert not worker.isRunning()


def test_chatbot_reports_runtime_oom_without_changing_rules(tmp_path, qtbot):
    process = _FakeProcess()
    worker = AICopilotWorker(
        "Please help with the Physics exam schedule",
        process=process,
        ollama_program="ollama-test",
        model_name="test-model",
        security_log_path=tmp_path / "security_log.txt",
        resource_sampler=_MemorySampler(
            AICopilotWorker.MIN_AVAILABLE_MEMORY_BYTES * 4
        ),
    )
    responses: list[str] = []
    constraints: list[dict] = []
    worker.response_ready.connect(responses.append)
    worker.constraint_ready.connect(constraints.append)

    worker.start()
    process.stderr = b"fatal: out of memory while loading local model"
    with qtbot.waitSignal(worker.finished, timeout=1000):
        process.finished.emit(1, None)

    assert responses == [worker.MODEL_MEMORY_MESSAGE]
    assert constraints == []
    assert not worker.isRunning()


def test_chatbot_forces_process_stop_after_timeout(tmp_path, qtbot):
    process = _FakeProcess()
    worker = AICopilotWorker(
        "Please help with the Physics exam schedule",
        process=process,
        ollama_program="ollama-test",
        model_name="test-model",
        security_log_path=tmp_path / "security_log.txt",
        resource_sampler=_MemorySampler(
            AICopilotWorker.MIN_AVAILABLE_MEMORY_BYTES * 4
        ),
    )
    responses: list[str] = []
    constraints: list[dict] = []
    worker.response_ready.connect(responses.append)
    worker.constraint_ready.connect(constraints.append)

    worker.start()
    with qtbot.waitSignal(worker.finished, timeout=1000):
        worker._handle_inference_timeout()

    assert process.killed
    assert responses == [worker.MODEL_TIMEOUT_MESSAGE]
    assert constraints == []
    assert not worker.isRunning()


def test_chatbot_missing_model_fails_closed(tmp_path, qtbot):
    process = _FakeProcess()
    worker = AICopilotWorker(
        "Please help with the Physics exam schedule",
        process=process,
        ollama_program="missing-ollama",
        model_name="test-model",
        security_log_path=tmp_path / "security_log.txt",
        resource_sampler=_MemorySampler(
            AICopilotWorker.MIN_AVAILABLE_MEMORY_BYTES * 4
        ),
    )
    responses: list[str] = []
    constraints: list[dict] = []
    worker.response_ready.connect(responses.append)
    worker.constraint_ready.connect(constraints.append)

    worker.start()
    with qtbot.waitSignal(worker.finished, timeout=1000):
        process.errorOccurred.emit("FailedToStart")

    assert responses == [worker.GENERIC_FALLBACK_MESSAGE]
    assert constraints == []
    assert not worker.isRunning()


RUN_LIVE_STRESS = (
    os.environ.get("EXAMSCHEDULER_RUN_AI_RESOURCE_STRESS") == "1"
)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(
    not RUN_LIVE_STRESS,
    reason=(
        "Set EXAMSCHEDULER_RUN_AI_RESOURCE_STRESS=1 to launch the real "
        "local model and measure CPU/RAM."
    ),
)
def test_live_chatbot_and_total_system_cpu_ram_stress(tmp_path, qtbot):
    """Stress the real local chatbot and write per-request resource metrics."""
    ollama_program = AICopilotWorker._resolve_ollama_program()
    if not Path(ollama_program).is_file() and shutil.which(ollama_program) is None:
        pytest.skip("Ollama is not installed or configured.")

    iterations = int(
        os.environ.get("EXAMSCHEDULER_AI_STRESS_ITERATIONS", "20")
    )
    sample_interval_ms = int(
        os.environ.get("EXAMSCHEDULER_AI_STRESS_SAMPLE_INTERVAL_MS", "200")
    )
    max_gui_rss_mb = float(
        os.environ.get("EXAMSCHEDULER_AI_STRESS_MAX_GUI_RSS_MB", "2048")
    )
    max_ollama_rss_mb = float(
        os.environ.get("EXAMSCHEDULER_AI_STRESS_MAX_OLLAMA_RSS_MB", "12288")
    )
    max_system_memory_percent = float(
        os.environ.get(
            "EXAMSCHEDULER_AI_STRESS_MAX_SYSTEM_MEMORY_PERCENT",
            "98",
        )
    )

    prompts = (
        "Schedule Physics on 2026-07-15",
        "Professor Cohen cannot examine on Sunday",
        "Limit program 83101 to 2 exams per day",
        "Keep at least 3 days between exams",
    )
    sampler = SystemResourceSampler()
    report_directory = Path(
        os.environ.get(
            "EXAMSCHEDULER_AI_STRESS_REPORT_DIR",
            PROJECT_ROOT / "performance_logs",
        )
    ).expanduser().resolve()
    report_directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = (
        report_directory
        / f"ai_copilot_resource_stress_{timestamp}.csv"
    )
    fieldnames = (
        "iteration",
        "elapsed_seconds",
        "gui_peak_rss_mb",
        "ollama_peak_rss_mb",
        "gui_cpu_percent_one_core",
        "ollama_cpu_percent_one_core",
        "system_cpu_percent",
        "system_memory_used_percent",
        "available_memory_mb",
        "result",
    )
    rows: list[dict[str, object]] = []

    with report_path.open("w", encoding="utf-8", newline="") as report:
        writer = csv.DictWriter(report, fieldnames=fieldnames)
        writer.writeheader()

        for iteration in range(iterations):
            worker = AICopilotWorker(
                prompts[iteration % len(prompts)],
                security_log_path=tmp_path / "security_log.txt",
                resource_sampler=sampler,
            )
            responses: list[str] = []
            constraints: list[dict] = []
            worker.response_ready.connect(responses.append)
            worker.constraint_ready.connect(constraints.append)

            started_at = time.perf_counter()
            system_before = _system_snapshot()
            gui_before = sampler.sample_process(os.getpid())
            ollama_before = _aggregate_process_metrics(
                sampler,
                _ollama_process_ids(),
            )
            gui_peak = gui_before.rss_bytes if gui_before else 0
            ollama_peak = ollama_before.rss_bytes if ollama_before else 0

            worker.start()
            while worker.isRunning():
                qtbot.wait(sample_interval_ms)
                gui_metrics = sampler.sample_process(os.getpid())
                ollama_metrics = _aggregate_process_metrics(
                    sampler,
                    _ollama_process_ids(),
                )
                if gui_metrics is not None:
                    gui_peak = max(gui_peak, gui_metrics.rss_bytes)
                if ollama_metrics is not None:
                    ollama_peak = max(ollama_peak, ollama_metrics.rss_bytes)

            elapsed = max(time.perf_counter() - started_at, 0.001)
            gui_after = sampler.sample_process(os.getpid())
            ollama_after = _aggregate_process_metrics(
                sampler,
                _ollama_process_ids(),
            )
            system_after = _system_snapshot()
            result = (
                "constraint"
                if constraints
                else responses[-1] if responses else "no_result"
            )
            row = {
                "iteration": iteration + 1,
                "elapsed_seconds": f"{elapsed:.3f}",
                "gui_peak_rss_mb": f"{_mb(gui_peak):.2f}",
                "ollama_peak_rss_mb": f"{_mb(ollama_peak):.2f}",
                "gui_cpu_percent_one_core": f"{_process_cpu_percent(gui_before, gui_after, elapsed):.2f}",
                "ollama_cpu_percent_one_core": f"{_process_cpu_percent(ollama_before, ollama_after, elapsed):.2f}",
                "system_cpu_percent": f"{_system_cpu_percent(system_before, system_after):.2f}",
                "system_memory_used_percent": f"{system_after.memory_used_percent:.2f}",
                "available_memory_mb": f"{_mb(system_after.available_memory):.2f}",
                "result": result,
            }
            rows.append(row)
            writer.writerow(row)
            report.flush()

            assert result not in {
                worker.MODEL_MEMORY_MESSAGE,
                worker.MODEL_TIMEOUT_MESSAGE,
                "no_result",
            }
            worker.deleteLater()

    print(f"AI resource stress report: {report_path}")
    assert max(float(row["gui_peak_rss_mb"]) for row in rows) <= max_gui_rss_mb
    assert max(float(row["ollama_peak_rss_mb"]) for row in rows) <= max_ollama_rss_mb
    assert max(
        float(row["system_memory_used_percent"]) for row in rows
    ) <= max_system_memory_percent


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
        return 100.0 * (
            self.total_memory - self.available_memory
        ) / self.total_memory


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
    idle_ticks = _filetime_value(idle)
    return _SystemSnapshot(
        idle_ticks=idle_ticks,
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


def _ollama_process_ids() -> set[int]:
    if sys.platform != "win32":
        return {
            int(path.name)
            for path in Path("/proc").iterdir()
            if path.name.isdigit()
            and _process_name(int(path.name)).casefold().startswith("ollama")
        }

    import ctypes
    from ctypes import wintypes

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = (
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        )

    kernel32 = ctypes.windll.kernel32
    kernel32.CreateToolhelp32Snapshot.argtypes = (
        wintypes.DWORD,
        wintypes.DWORD,
    )
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Process32FirstW.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(PROCESSENTRY32W),
    )
    kernel32.Process32FirstW.restype = wintypes.BOOL
    kernel32.Process32NextW.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(PROCESSENTRY32W),
    )
    kernel32.Process32NextW.restype = wintypes.BOOL
    snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
    if snapshot == wintypes.HANDLE(-1).value:
        return set()

    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(entry)
    process_ids: set[int] = set()
    try:
        has_entry = kernel32.Process32FirstW(
            snapshot,
            ctypes.byref(entry),
        )
        while has_entry:
            if entry.szExeFile.casefold().startswith("ollama"):
                process_ids.add(int(entry.th32ProcessID))
            has_entry = kernel32.Process32NextW(
                snapshot,
                ctypes.byref(entry),
            )
    finally:
        kernel32.CloseHandle(snapshot)
    return process_ids


def _process_name(process_id: int) -> str:
    try:
        return Path(f"/proc/{process_id}/comm").read_text(
            encoding="ascii"
        ).strip()
    except OSError:
        return ""


def _aggregate_process_metrics(
    sampler: SystemResourceSampler,
    process_ids: set[int],
) -> ProcessMetrics | None:
    metrics = [
        sample
        for process_id in process_ids
        if (sample := sampler.sample_process(process_id)) is not None
    ]
    if not metrics:
        return None
    return ProcessMetrics(
        rss_bytes=sum(item.rss_bytes for item in metrics),
        private_bytes=sum(item.private_bytes or 0 for item in metrics),
        cpu_seconds=sum(item.cpu_seconds for item in metrics),
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
    before: _SystemSnapshot,
    after: _SystemSnapshot,
) -> float:
    total_delta = after.total_ticks - before.total_ticks
    idle_delta = after.idle_ticks - before.idle_ticks
    if total_delta <= 0:
        return 0.0
    return max(0.0, min(100.0, 100.0 * (total_delta - idle_delta) / total_delta))


def _filetime_value(filetime) -> int:
    return (filetime.dwHighDateTime << 32) | filetime.dwLowDateTime


def _mb(value: int) -> float:
    return value / (1024 * 1024)
