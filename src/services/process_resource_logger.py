"""CSV resource logging for scheduler subprocess benchmark runs."""

from __future__ import annotations

import csv
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol


_COMPLETE_SYSTEM_PATTERN = re.compile(r"Complete System #([\d,]+)")
_TOTAL_SYSTEM_PATTERN = re.compile(r"Total complete systems:\s*([\d,]+)")


@dataclass(frozen=True)
class ProcessMetrics:
    """One process resource snapshot."""

    rss_bytes: int
    private_bytes: int | None
    cpu_seconds: float


class ResourceSampler(Protocol):
    """Read process and machine resource counters."""

    def sample_process(self, process_id: int) -> ProcessMetrics | None:
        ...

    def available_memory_bytes(self) -> int | None:
        ...


class SystemResourceSampler:
    """Standard-library resource sampler with Windows and Linux support."""

    def sample_process(self, process_id: int) -> ProcessMetrics | None:
        if sys.platform == "win32":
            return _sample_windows_process(process_id)
        if sys.platform.startswith("linux"):
            return _sample_linux_process(process_id)
        return None

    def available_memory_bytes(self) -> int | None:
        if sys.platform == "win32":
            return _windows_available_memory()
        if sys.platform.startswith("linux"):
            return _linux_available_memory()
        return None


class ProcessResourceLogger:
    """Write scheduler and GUI resource usage to a crash-resilient CSV file."""

    HEADER = (
        "timestamp_utc",
        "elapsed_seconds",
        "code_revision",
        "python_version",
        "event",
        "phase",
        "child_pid",
        "child_rss_mb",
        "child_peak_rss_mb",
        "child_private_mb",
        "child_cpu_percent_one_core",
        "child_cpu_percent_total_capacity",
        "gui_pid",
        "gui_rss_mb",
        "gui_peak_rss_mb",
        "gui_private_mb",
        "gui_cpu_percent_one_core",
        "gui_cpu_percent_total_capacity",
        "available_memory_mb",
        "stdout_chars",
        "stderr_chars",
        "results_seen",
        "total_results",
        "exit_code",
        "exit_status",
        "detail",
    )

    def __init__(
        self,
        log_directory: str | Path,
        sampler: ResourceSampler | None = None,
        clock=time.perf_counter,
        project_root: str | Path | None = None,
    ) -> None:
        self._log_directory = Path(log_directory)
        self._project_root = Path(project_root or self._log_directory.parent)
        self._sampler = sampler or SystemResourceSampler()
        self._clock = clock
        self._code_revision = _read_git_revision(self._project_root)
        self._python_version = ".".join(str(value) for value in sys.version_info[:3])
        self._started_at = self._clock()
        self._gui_pid = os.getpid()
        self._child_pid: int | None = None
        self._phase = "starting"
        self._stdout_chars = 0
        self._stderr_chars = 0
        self._results_seen = 0
        self._total_results: int | None = None
        self._output_tail = ""
        self._last_cpu_samples: dict[int, tuple[float, float]] = {}
        self._peak_rss_bytes: dict[int, int] = {}
        self._closed = False
        self._file = None
        self._writer = None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        revision_label = self._code_revision[:8]
        self.path = (
            self._log_directory
            / f"scheduler_run_{revision_label}_{timestamp}.csv"
        )

    def start(self, program: str, arguments: list[str]) -> None:
        """Create the CSV and record the exact command being benchmarked."""
        try:
            self._log_directory.mkdir(parents=True, exist_ok=True)
            self._file = self.path.open("w", encoding="utf-8", newline="")
            self._writer = csv.writer(self._file)
            self._writer.writerow(self.HEADER)
            self._file.flush()
            self.record_event(
                "start_requested",
                detail=_safe_detail(" ".join([program, *arguments])),
            )
        except OSError:
            self._disable()

    def process_started(self, child_pid: int) -> None:
        self._child_pid = child_pid
        self._phase = "process_started"
        self.record_event("process_started")

    def record_output(self, stream_name: str, text: str) -> None:
        if stream_name == "stdout":
            self._stdout_chars += len(text)
        else:
            self._stderr_chars += len(text)

        combined = self._output_tail + text
        self._output_tail = combined[-256:]

        result_numbers = [
            int(raw_number.replace(",", ""))
            for raw_number in _COMPLETE_SYSTEM_PATTERN.findall(combined)
        ]
        if result_numbers:
            first_result = self._results_seen == 0
            self._results_seen = max(self._results_seen, max(result_numbers))
            self._phase = "streaming_results"
            if first_result:
                self.record_event("first_result")

        totals = _TOTAL_SYSTEM_PATTERN.findall(combined)
        if totals:
            self._total_results = int(totals[-1].replace(",", ""))

        inferred_phase = _infer_phase(text)
        if inferred_phase is not None and inferred_phase != self._phase:
            self._phase = inferred_phase
            self.record_event(
                "phase_changed",
                detail=_safe_detail(text),
            )

    def record_event(
        self,
        event: str,
        *,
        exit_code: int | None = None,
        exit_status: str = "",
        detail: str = "",
    ) -> None:
        self._write_row(
            event=event,
            exit_code=exit_code,
            exit_status=exit_status,
            detail=detail,
        )

    def sample(self) -> None:
        self._write_row(event="sample")

    def finish(self, exit_code: int, exit_status: str) -> None:
        self._phase = "finished"
        self._write_row(
            event="process_finished",
            exit_code=exit_code,
            exit_status=exit_status,
        )
        self.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._file is not None:
            try:
                self._file.flush()
                self._file.close()
            except OSError:
                pass
        self._file = None
        self._writer = None

    def _write_row(
        self,
        *,
        event: str,
        exit_code: int | None = None,
        exit_status: str = "",
        detail: str = "",
    ) -> None:
        if self._writer is None or self._file is None or self._closed:
            return

        now = self._clock()
        child_metrics = (
            self._sampler.sample_process(self._child_pid)
            if self._child_pid is not None
            else None
        )
        gui_metrics = self._sampler.sample_process(self._gui_pid)
        available_memory = self._sampler.available_memory_bytes()
        child_cpu_one_core, child_cpu_total = self._cpu_percents(
            self._child_pid,
            child_metrics,
            now,
        )
        gui_cpu_one_core, gui_cpu_total = self._cpu_percents(
            self._gui_pid,
            gui_metrics,
            now,
        )

        try:
            self._writer.writerow(
                (
                    datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                    f"{now - self._started_at:.3f}",
                    self._code_revision,
                    self._python_version,
                    event,
                    self._phase,
                    self._child_pid or "",
                    _megabytes(child_metrics.rss_bytes if child_metrics else None),
                    self._peak_rss_megabytes(self._child_pid, child_metrics),
                    _megabytes(child_metrics.private_bytes if child_metrics else None),
                    child_cpu_one_core,
                    child_cpu_total,
                    self._gui_pid,
                    _megabytes(gui_metrics.rss_bytes if gui_metrics else None),
                    self._peak_rss_megabytes(self._gui_pid, gui_metrics),
                    _megabytes(gui_metrics.private_bytes if gui_metrics else None),
                    gui_cpu_one_core,
                    gui_cpu_total,
                    _megabytes(available_memory),
                    self._stdout_chars,
                    self._stderr_chars,
                    self._results_seen,
                    self._total_results if self._total_results is not None else "",
                    exit_code if exit_code is not None else "",
                    exit_status,
                    _safe_detail(detail),
                )
            )
            self._file.flush()
        except OSError:
            self._disable()

    def _cpu_percents(
        self,
        process_id: int | None,
        metrics: ProcessMetrics | None,
        now: float,
    ) -> tuple[str, str]:
        if process_id is None or metrics is None:
            return "", ""

        key = process_id
        previous = self._last_cpu_samples.get(key)
        self._last_cpu_samples[key] = (now, metrics.cpu_seconds)
        if previous is None:
            return "", ""

        elapsed = now - previous[0]
        cpu_delta = metrics.cpu_seconds - previous[1]
        if elapsed <= 0 or cpu_delta < 0:
            return "", ""

        one_core_percent = 100.0 * cpu_delta / elapsed
        total_capacity_percent = one_core_percent / max(1, os.cpu_count() or 1)
        return f"{one_core_percent:.2f}", f"{total_capacity_percent:.2f}"

    def _peak_rss_megabytes(
        self,
        process_id: int | None,
        metrics: ProcessMetrics | None,
    ) -> str:
        if process_id is None or metrics is None:
            return ""
        peak = max(self._peak_rss_bytes.get(process_id, 0), metrics.rss_bytes)
        self._peak_rss_bytes[process_id] = peak
        return _megabytes(peak)

    def _disable(self) -> None:
        if self._file is not None:
            try:
                self._file.close()
            except OSError:
                pass
        self._file = None
        self._writer = None
        self._closed = True


def _infer_phase(text: str) -> str | None:
    lowered = text.lower()
    phase_markers = (
        (("parse", "reading input", "loading"), "parsing_input"),
        (("preparing", "building"), "preparing_schedules"),
        (("calculating", "solving", "generating"), "solving"),
        (("batch ready", "complete system #"), "streaming_results"),
        (("stream finished", "lazy stream finished"), "finishing"),
    )
    for markers, phase in phase_markers:
        if any(marker in lowered for marker in markers):
            return phase
    return None


def _read_git_revision(project_root: Path) -> str:
    git_entry = project_root / ".git"
    try:
        if git_entry.is_file():
            git_dir_text = git_entry.read_text(encoding="utf-8").strip()
            if not git_dir_text.lower().startswith("gitdir:"):
                return "unknown"
            git_directory = Path(git_dir_text.split(":", 1)[1].strip())
            if not git_directory.is_absolute():
                git_directory = (project_root / git_directory).resolve()
        else:
            git_directory = git_entry

        head = (git_directory / "HEAD").read_text(encoding="ascii").strip()
        if not head.startswith("ref:"):
            return head

        ref_name = head.split(":", 1)[1].strip()
        loose_ref = git_directory / ref_name
        if loose_ref.exists():
            return loose_ref.read_text(encoding="ascii").strip()

        common_directory = git_directory
        common_dir_file = git_directory / "commondir"
        if common_dir_file.exists():
            common_path = Path(
                common_dir_file.read_text(encoding="utf-8").strip()
            )
            common_directory = (
                common_path
                if common_path.is_absolute()
                else (git_directory / common_path).resolve()
            )
            common_ref = common_directory / ref_name
            if common_ref.exists():
                return common_ref.read_text(encoding="ascii").strip()

        for line in (common_directory / "packed-refs").read_text(
            encoding="ascii"
        ).splitlines():
            if not line or line.startswith(("#", "^")):
                continue
            revision, packed_ref_name = line.split(" ", 1)
            if packed_ref_name == ref_name:
                return revision
    except (OSError, ValueError):
        return "unknown"
    return "unknown"


def _safe_detail(text: str, limit: int = 500) -> str:
    return " ".join(text.split())[:limit]


def _megabytes(value: int | None) -> str:
    if value is None:
        return ""
    return f"{value / (1024 * 1024):.2f}"


def _sample_windows_process(process_id: int) -> ProcessMetrics | None:
    import ctypes
    from ctypes import wintypes

    class FILETIME(ctypes.Structure):
        _fields_ = (
            ("dwLowDateTime", wintypes.DWORD),
            ("dwHighDateTime", wintypes.DWORD),
        )

    class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
        _fields_ = (
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
            ("PrivateUsage", ctypes.c_size_t),
        )

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32.OpenProcess.argtypes = (
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.DWORD,
    )
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.GetProcessTimes.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(FILETIME),
        ctypes.POINTER(FILETIME),
        ctypes.POINTER(FILETIME),
        ctypes.POINTER(FILETIME),
    )
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    psapi.GetProcessMemoryInfo.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(PROCESS_MEMORY_COUNTERS_EX),
        wintypes.DWORD,
    )
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    process_handle = kernel32.OpenProcess(0x1000 | 0x0010, False, process_id)
    if not process_handle:
        return None

    try:
        counters = PROCESS_MEMORY_COUNTERS_EX()
        counters.cb = ctypes.sizeof(counters)
        if not psapi.GetProcessMemoryInfo(
            process_handle,
            ctypes.byref(counters),
            counters.cb,
        ):
            return None

        creation = FILETIME()
        exit_time = FILETIME()
        kernel = FILETIME()
        user = FILETIME()
        if not kernel32.GetProcessTimes(
            process_handle,
            ctypes.byref(creation),
            ctypes.byref(exit_time),
            ctypes.byref(kernel),
            ctypes.byref(user),
        ):
            return None

        cpu_seconds = (_filetime_value(kernel) + _filetime_value(user)) / 10_000_000
        return ProcessMetrics(
            rss_bytes=int(counters.WorkingSetSize),
            private_bytes=int(counters.PrivateUsage),
            cpu_seconds=cpu_seconds,
        )
    finally:
        kernel32.CloseHandle(process_handle)


def _filetime_value(filetime) -> int:
    return (filetime.dwHighDateTime << 32) | filetime.dwLowDateTime


def _windows_available_memory() -> int | None:
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

    status = MEMORYSTATUSEX()
    status.dwLength = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    return int(status.ullAvailPhys)


def _sample_linux_process(process_id: int) -> ProcessMetrics | None:
    try:
        statm = Path(f"/proc/{process_id}/statm").read_text(encoding="ascii").split()
        stat = Path(f"/proc/{process_id}/stat").read_text(encoding="ascii").split()
        page_size = os.sysconf("SC_PAGE_SIZE")
        clock_ticks = os.sysconf("SC_CLK_TCK")
        rss_bytes = int(statm[1]) * page_size
        cpu_seconds = (int(stat[13]) + int(stat[14])) / clock_ticks
    except (OSError, ValueError, IndexError):
        return None
    return ProcessMetrics(
        rss_bytes=rss_bytes,
        private_bytes=None,
        cpu_seconds=cpu_seconds,
    )


def _linux_available_memory() -> int | None:
    try:
        for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        return None
    return None
