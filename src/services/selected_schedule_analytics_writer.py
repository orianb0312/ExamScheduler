"""Write analytics for a currently selected schedule."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from src.analytics.exporters import SUPPORTED_ANALYTICS_FORMATS
from src.services.analytics_export_service import ScheduleAnalyticsExportService
from src.services.schedule_output_service import ScheduleSystem


class SelectedScheduleAnalyticsWriter:
    """Save one selected schedule as a deterministic analytics report."""

    def __init__(
        self,
        export_service: ScheduleAnalyticsExportService | None = None,
    ) -> None:
        self._export_service = export_service or ScheduleAnalyticsExportService()

    @property
    def file_filter(self) -> str:
        return (
            "Analytics Files (*.json *.txt *.csv *.pdf);;"
            "JSON Files (*.json);;Text Files (*.txt);;"
            "CSV Files (*.csv);;PDF Files (*.pdf);;All Files (*)"
        )

    def suggested_filename(
        self,
        schedule: ScheduleSystem,
        format_name: str = "json",
    ) -> str:
        clean_format = _normalize_format(format_name)
        return f"schedule_{schedule.number}_analytics.{clean_format}"

    def write(
        self,
        schedule: ScheduleSystem | None,
        destination: str | Path,
        *,
        format_name: str | None = None,
        active_priorities: Sequence[str] = (),
    ) -> Path:
        if schedule is None:
            raise ValueError("No schedule is currently selected.")

        output_path = Path(destination)
        clean_format = _normalize_format(format_name or output_path.suffix or "json")
        # Match the saved suffix to the chosen format even when the dialog omits it.
        if output_path.suffix.casefold() != f".{clean_format}":
            output_path = output_path.with_suffix(f".{clean_format}")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        return self._export_service.export_schedule_system(
            schedule,
            output_path,
            format_name=clean_format,
            active_priorities=active_priorities,
        )


def _normalize_format(value: str) -> str:
    clean = str(value).strip().casefold().lstrip(".")
    if clean == "text":
        clean = "txt"
    if clean not in SUPPORTED_ANALYTICS_FORMATS:
        valid = ", ".join(SUPPORTED_ANALYTICS_FORMATS)
        raise ValueError(f"Unsupported analytics format '{value}'. Valid: {valid}.")
    return clean
