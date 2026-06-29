"""
Dashboard rendering — empty / uninitialized data (Step 1)
=========================================================
Injects empty or uninitialized schedule datasets into the analytics dashboard
and verifies the chart canvas renders a safe empty placeholder without raising
null-pointer / division-by-zero exceptions.

These complement (do not duplicate) tests/ui/test_dashboard_view.py, which
covers the populated-data refresh behavior.

Run:
    pytest tests/ui/test_dashboard_empty_data.py -v
"""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QMouseEvent

from src.ui.dashboard_view import (
    ExamLoadChart,
    ExamSchedulerDashboard,
    _chart_ticks,
)


def test_chart_renders_empty_placeholder_without_crashing(qtbot):
    """An empty chart must paint the placeholder, not raise."""
    chart = ExamLoadChart()
    qtbot.addWidget(chart)
    chart.update_chart_data([], [])
    chart.resize(800, 500)

    # grab() forces a real paintEvent; this is where a null/zero bug would surface.
    pixmap = chart.grab()
    assert not pixmap.isNull()
    assert chart._bar_hitboxes == []


def test_chart_ticks_never_empty_so_max_tick_is_safe():
    """
    _chart_ticks must never return an empty list, because the bar drawing
    divides by ticks[-1]. Empty or all-zero data must still yield a valid axis.
    """
    for values in ([], [0], [0, 0, 0]):
        ticks = _chart_ticks(values)
        assert ticks, f"ticks empty for {values!r}"
        assert ticks[-1] > 0  # safe denominator


def test_chart_hover_on_empty_data_does_not_crash(qtbot):
    """Moving the mouse over an empty chart must not raise (no hitboxes)."""
    chart = ExamLoadChart()
    qtbot.addWidget(chart)
    chart.update_chart_data([], [])
    chart.resize(400, 300)
    chart.grab()  # build paint state

    event = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(200, 150),
        QPointF(200, 150),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    chart.mouseMoveEvent(event)  # must simply do nothing
    assert chart._bar_hitboxes == []


def test_dashboard_builds_with_default_empty_state(qtbot):
    """A freshly built dashboard shows safe placeholders and disabled actions."""
    dashboard = ExamSchedulerDashboard()
    qtbot.addWidget(dashboard)

    assert dashboard.total_card.value_label.text() == "No schedules"
    assert dashboard.fitness_card.value_label.text() == "No schedule"
    assert dashboard.gap_card.value_label.text() == "No data"
    assert dashboard.health_card.value_label.text() == "No batch"
    assert dashboard.pagination_label.text() == "No schedules to display"
    assert not dashboard.previous_button.isEnabled()
    assert not dashboard.next_button.isEnabled()


def test_dashboard_paints_with_empty_chart_and_pagination(qtbot):
    """The whole dashboard must paint with empty data injected."""
    dashboard = ExamSchedulerDashboard()
    qtbot.addWidget(dashboard)
    dashboard.update_chart_data([], [])
    dashboard.set_pagination(0, 0, 0)

    pixmap = dashboard.grab()
    assert not pixmap.isNull()
    assert dashboard.pagination_label.text() == "No schedules to display"


def test_dashboard_metrics_and_insights_accept_empty_strings(qtbot):
    """Updating metrics/insights with empty values must not raise."""
    dashboard = ExamSchedulerDashboard()
    qtbot.addWidget(dashboard)

    dashboard.update_metrics("", "", "", "")
    dashboard.update_insights("", "")
    dashboard.grab()

    assert dashboard.total_card.value_label.text() == ""
    assert dashboard.insights.winning_card.body_label.text() == ""
    assert dashboard.insights.bottleneck_card.body_label.text() == ""


def test_pagination_rejects_nonpositive_indices(qtbot):
    """Any non-positive chunk/index must fall back to the empty-state label."""
    dashboard = ExamSchedulerDashboard()
    qtbot.addWidget(dashboard)

    for chunk, start, end in [(0, 1, 1), (1, 0, 1), (1, 1, 0), (-1, -1, -1)]:
        dashboard.set_pagination(chunk, start, end)
        assert dashboard.pagination_label.text() == "No schedules to display"


def test_empty_chart_actually_paints_placeholder_text(qtbot):
    """Assert the placeholder string is genuinely drawn on the empty chart."""
    from unittest.mock import patch
    from src.ui import dashboard_view

    drawn_texts: list[str] = []
    real_painter_cls = dashboard_view.QPainter

    class _SpyPainter(real_painter_cls):
        def drawText(self, *args):
            for arg in args:
                if isinstance(arg, str):
                    drawn_texts.append(arg)
            return super().drawText(*args)

    with patch.object(dashboard_view, "QPainter", _SpyPainter):
        chart = ExamLoadChart()
        qtbot.addWidget(chart)
        chart.update_chart_data([], [])
        chart.resize(800, 500)
        chart.grab()

    assert "No schedules to visualize yet" in drawn_texts