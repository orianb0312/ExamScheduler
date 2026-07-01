"""Service hooks for analytics exports from CLI and UI schedule data."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

from src.analytics.exporters import AnalyticsExportService
from src.analytics.models import ScheduleAnalyticsReport
from src.analytics.schedule_analytics import (
    ScheduleAnalyticsEngine,
    analytics_exams_from_display_system,
)
from src.models.academic import Course
from src.services.schedule_output_service import (
    ScheduleOutputDataAdapter,
    ScheduleSystem,
    StdoutScheduleParser,
)


DEFAULT_ANALYTICS_SCHEDULE_LIMIT = 50


class ScheduleAnalyticsExportService:
    """Build and write analytics reports from generated schedule systems."""

    def __init__(
        self,
        engine: ScheduleAnalyticsEngine | None = None,
        exporter: AnalyticsExportService | None = None,
    ) -> None:
        self._engine = engine or ScheduleAnalyticsEngine()
        self._exporter = exporter or AnalyticsExportService()

    def reports_from_systems(
        self,
        systems: Iterable[ScheduleSystem],
        active_priorities: Sequence[str],
    ) -> tuple[ScheduleAnalyticsReport, ...]:
        reports: list[ScheduleAnalyticsReport] = []
        for system in systems:
            reports.append(
                self._engine.analyze(
                    analytics_exams_from_display_system(system),
                    active_priorities,
                    schedule_label=system.label,
                    schedule_number=system.number,
                )
            )
        return tuple(reports)

    def reports_from_output_file(
        self,
        output_path: Path,
        *,
        courses: Iterable[Course],
        selected_program_ids: Iterable[int | str],
        active_priorities: Sequence[str],
        max_schedules: int = DEFAULT_ANALYTICS_SCHEDULE_LIMIT,
    ) -> tuple[tuple[ScheduleAnalyticsReport, ...], bool]:
        if max_schedules <= 0:
            raise ValueError("analytics max schedules must be greater than zero.")

        adapter = ScheduleOutputDataAdapter(courses, selected_program_ids)
        parser = StdoutScheduleParser()
        reports: list[ScheduleAnalyticsReport] = []
        reached_limit = False

        # Read in chunks so large schedule files can be analyzed without loading all text.
        with Path(output_path).open(encoding="utf-8") as file:
            while chunk := file.read(64 * 1024):
                systems = adapter.convert(parser.feed(chunk))
                reached_limit = self._extend_reports(
                    reports,
                    systems,
                    active_priorities,
                    max_schedules,
                )
                if reached_limit:
                    break

        if not reached_limit:
            reached_limit = self._extend_reports(
                reports,
                adapter.convert(parser.flush()),
                active_priorities,
                max_schedules,
            )

        return tuple(reports), reached_limit

    def export_reports(
        self,
        reports: Sequence[ScheduleAnalyticsReport],
        formats: Iterable[str],
        output_dir: Path,
        base_filename: str,
    ) -> list[Path]:
        return self._exporter.export(
            reports,
            formats,
            output_dir,
            base_filename=base_filename,
        )

    def export_schedule_system(
        self,
        schedule: ScheduleSystem,
        destination: str | Path,
        *,
        format_name: str,
        active_priorities: Sequence[str] = (),
    ) -> Path:
        output_path = Path(destination)
        reports = self.reports_from_systems((schedule,), active_priorities)
        written_paths = self.export_reports(
            reports,
            (format_name,),
            output_path.parent,
            output_path.stem,
        )
        return written_paths[0]

    def _extend_reports(
        self,
        reports: list[ScheduleAnalyticsReport],
        systems: Sequence[ScheduleSystem],
        active_priorities: Sequence[str],
        max_schedules: int,
    ) -> bool:
        for system in systems:
            # Empty parsed systems are headers or partial chunks, not reportable schedules.
            if not any(period.exams for period in system.periods):
                continue
            if len(reports) >= max_schedules:
                return True
            reports.extend(self.reports_from_systems((system,), active_priorities))
        return False
