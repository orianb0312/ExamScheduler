"""Professional PyQt6 dashboard viewport for ExamScheduler analytics."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QToolTip,
    QVBoxLayout,
    QWidget,
)


DEMO_DATES = [
    "Oct 12", "Oct 14", "Oct 16", "Oct 18", "Oct 20",
    "Oct 22", "Oct 24", "Oct 16", "Oct 12", "Oct 16",
]
DEMO_VALUES = [4, 6, 8, 9, 12, 15, 16, 8, 5, 4]

DEMO_WINNING_TEXT = (
    "Optimized study gap m=3.2d achieved for all Program 83101 Software "
    "Engineering students while respecting 100% of Prof. Cohen block constraints."
)
DEMO_BOTTLENECK_TEXT = (
    "Week 2 overload is calculated due to severe constraint strain in Program "
    "83101 obligatory courses, resulting from 5 overlaps within that chunk."
)


class NeonButton(QPushButton):
    """Rounded dark button with orange neon border."""

    def __init__(self, text: str, parent=None) -> None:
        super().__init__(text, parent)
        self.setObjectName("dashboardNeonButton")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(190, 52)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        _add_shadow(self, QColor("#ff9c3d"), blur=24, alpha=110)


class MetricCard(QWidget):
    """Top KPI card with accent icon, title, and large value."""

    def __init__(
        self,
        title: str,
        value: str,
        icon: str,
        accent: QColor,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("dashboardMetricCard")
        self._accent = accent
        self._icon = icon

        self.icon_label = QLabel(icon)
        self.icon_label.setObjectName("dashboardMetricIcon")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setFixedSize(68, 68)
        self.icon_label.setStyleSheet(
            "QLabel#dashboardMetricIcon {"
            f"color: {accent.name()};"
            f"border: 2px solid {accent.name()};"
            "border-radius: 34px;"
            "background: rgba(255, 255, 255, 6);"
            "font-size: 30px;"
            "font-weight: 800;"
            "}"
        )

        self.title_label = QLabel(title)
        self.title_label.setObjectName("dashboardMetricTitle")
        self.title_label.setWordWrap(True)

        self.value_label = QLabel(value)
        self.value_label.setObjectName("dashboardMetricValue")
        self.value_label.setStyleSheet(
            "QLabel#dashboardMetricValue {"
            f"color: {accent.name()};"
            "background: transparent;"
            "font-size: 29px;"
            "font-weight: 850;"
            "}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 20)
        layout.setSpacing(18)
        layout.addWidget(self.icon_label)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(8)
        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.value_label)
        text_layout.addStretch(1)
        layout.addLayout(text_layout, 1)

        self.setMinimumHeight(160)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        _add_shadow(self, accent, blur=28, alpha=70)

    def set_value(self, value: object) -> None:
        self.value_label.setText(str(value))

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), 18, 18)

        gradient = QLinearGradient(QPointF(rect.topLeft()), QPointF(rect.bottomRight()))
        gradient.setColorAt(0.0, QColor(18, 18, 39, 230))
        gradient.setColorAt(1.0, QColor(6, 8, 25, 245))
        painter.fillPath(path, gradient)

        border = QColor(self._accent)
        border.setAlpha(145)
        painter.setPen(QPen(border, 1.4))
        painter.drawPath(path)

        dotted = QColor(self._accent)
        dotted.setAlpha(26)
        painter.setPen(QPen(dotted, 1))
        step = 16
        for x in range(18, rect.width(), step):
            for y in range(16, rect.height(), step):
                painter.drawPoint(rect.left() + x, rect.top() + y)


class ExamLoadChart(QWidget):
    """Custom QPainter bar chart for exams per scheduled date."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("dashboardChartPanel")
        self._dates: list[str] = []
        self._values: list[int] = []
        self._bar_hitboxes: list[tuple[QRectF, str, int]] = []
        self.setMouseTracking(True)
        self.setMinimumHeight(500)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        _add_shadow(self, QColor("#00d9ff"), blur=34, alpha=45)

    def update_chart_data(self, dates: Sequence[str], values: Sequence[int]) -> None:
        self._dates = [str(date) for date in dates]
        self._values = [int(value) for value in values]
        self.update()

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        panel = self.rect().adjusted(1, 1, -1, -1)
        _draw_panel(painter, panel, QColor("#18213b"), QColor("#263653"))

        painter.setPen(QColor("#f6fbff"))
        painter.setFont(_font(16, 760))
        painter.drawText(
            QRectF(panel.adjusted(26, 18, -20, -20)),
            _alignment_flags(Qt.AlignmentFlag.AlignLeft, Qt.AlignmentFlag.AlignTop),
            "Exam Load Distribution",
        )

        chart = panel.adjusted(72, 72, -28, -72)
        ticks = _chart_ticks(self._values)
        max_tick = ticks[-1]
        grid_color = QColor("#6b7892")
        grid_color.setAlpha(70)
        painter.setPen(QPen(grid_color, 1, Qt.PenStyle.DashLine))
        for tick in ticks:
            y = chart.bottom() - (tick / max_tick) * chart.height()
            painter.drawLine(QPointF(chart.left(), y), QPointF(chart.right(), y))
            painter.setPen(QColor("#a7b4ca"))
            painter.setFont(_font(9, 500))
            painter.drawText(
                QRectF(22, y - 9, 40, 18),
                _alignment_flags(
                    Qt.AlignmentFlag.AlignRight,
                    Qt.AlignmentFlag.AlignVCenter,
                ),
                str(tick),
            )
            painter.setPen(QPen(grid_color, 1, Qt.PenStyle.DashLine))

        axis = QColor("#77859f")
        painter.setPen(QPen(axis, 1.2))
        painter.drawLine(chart.bottomLeft(), chart.bottomRight())
        painter.drawLine(chart.bottomLeft(), chart.topLeft())

        if not self._values:
            self._bar_hitboxes = []
            painter.setPen(QColor("#aeb8c7"))
            painter.setFont(_font(13, 650))
            painter.drawText(
                QRectF(chart),
                _alignment_flags(Qt.AlignmentFlag.AlignCenter),
                "No schedules to visualize yet",
            )
        else:
            self._draw_bars(painter, chart, max_tick)

        painter.save()
        painter.translate(18, chart.center().y() + 65)
        painter.rotate(-90)
        painter.setPen(QColor("#aeb8c7"))
        painter.setFont(_font(10, 650))
        painter.drawText(
            QRectF(0, 0, 170, 22),
            _alignment_flags(Qt.AlignmentFlag.AlignCenter),
            "Exams on Date",
        )
        painter.restore()

        painter.setPen(QColor("#aeb8c7"))
        painter.setFont(_font(10, 650))
        painter.drawText(
            QRectF(chart.center().x() - 80, panel.bottom() - 42, 160, 24),
            _alignment_flags(Qt.AlignmentFlag.AlignCenter),
            "Exam Dates",
        )

    def _draw_bars(self, painter: QPainter, chart, max_tick: int) -> None:
        self._bar_hitboxes = []
        bar_count = len(self._values)
        slot = chart.width() / max(bar_count, 1)
        bar_width = min(38.0, slot * 0.48)
        for index, value in enumerate(self._values):
            height_ratio = min(max(value, 0), max_tick) / max_tick
            bar_height = height_ratio * chart.height()
            left = chart.left() + index * slot + (slot - bar_width) / 2
            top = chart.bottom() - bar_height
            rect = QRectF(left, top, bar_width, bar_height)
            hover_rect = QRectF(left - 8, top - 8, bar_width + 16, bar_height + 16)
            self._bar_hitboxes.append((hover_rect, self._dates[index], value))
            glow = QColor("#00d9ff")
            glow.setAlpha(65)
            painter.setPen(QPen(glow, 8))
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 7, 7)
            fill = QColor("#00d9ff")
            fill.setAlpha(70)
            painter.setPen(QPen(QColor("#3bf3ff"), 1.8))
            painter.setBrush(fill)
            painter.drawRoundedRect(rect, 7, 7)

            painter.setPen(QColor("#9eb3c8"))
            painter.setFont(_font(8, 500))
            label_rect = QRectF(left - 18, chart.bottom() + 8, bar_width + 36, 28)
            painter.drawText(
                label_rect,
                _alignment_flags(Qt.AlignmentFlag.AlignCenter),
                self._dates[index],
            )

    def mouseMoveEvent(self, event) -> None:
        position = event.position()
        for rect, label, value in self._bar_hitboxes:
            if rect.contains(position):
                QToolTip.showText(
                    event.globalPosition().toPoint(),
                    f"{label}: {value} {_plural('exam', value)}",
                    self,
                )
                return
        QToolTip.hideText()

    def leaveEvent(self, event) -> None:
        del event
        QToolTip.hideText()


class InsightCard(QWidget):
    """Single insight row with large status icon and accent edge."""

    def __init__(
        self,
        icon: str,
        title: str,
        body: str,
        accent: QColor,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("dashboardInsightCard")
        self._accent = accent

        self.icon_label = QLabel(icon)
        self.icon_label.setObjectName("dashboardInsightIcon")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setFixedSize(52, 52)
        self.icon_label.setStyleSheet(
            "QLabel#dashboardInsightIcon {"
            f"color: {accent.name()};"
            f"border: 2px solid {accent.name()};"
            "border-radius: 26px;"
            "font-size: 25px;"
            "font-weight: 900;"
            "background: rgba(255, 255, 255, 6);"
            "}"
        )

        self.title_label = QLabel(title)
        self.title_label.setObjectName("dashboardInsightTitle")
        self.title_label.setWordWrap(True)

        self.body_label = QLabel(body)
        self.body_label.setObjectName("dashboardInsightBody")
        self.body_label.setWordWrap(True)

        text = QVBoxLayout()
        text.setSpacing(7)
        text.addWidget(self.title_label)
        text.addWidget(self.body_label)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(18)
        layout.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(text, 1)
        self.setMinimumHeight(154)

    def set_body(self, body: str) -> None:
        self.body_label.setText(body)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)
        _draw_panel(painter, rect, QColor("#121a2d"), QColor("#1e2a43"), radius=18)
        accent = QColor(self._accent)
        accent.setAlpha(210)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(accent)
        painter.drawRoundedRect(QRectF(rect.left(), rect.top() + 12, 5, rect.height() - 24), 2, 2)


class InsightPanel(QWidget):
    """Right-side AI insights panel."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("dashboardInsightPanel")
        self.setMinimumHeight(500)
        _add_shadow(self, QColor("#52ff87"), blur=30, alpha=70)

        header_icon = QLabel("\u2713")
        header_icon.setObjectName("dashboardInsightHeaderIcon")
        header_icon.setFixedSize(34, 34)
        header_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("Analytical AI Insights Engine")
        title.setObjectName("dashboardInsightHeaderTitle")

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(12)
        header.addWidget(header_icon)
        header.addWidget(title)
        header.addStretch(1)

        self.winning_card = InsightCard(
            "\u2713",
            "Winning Schedule Performance (Calculated):",
            "Generate schedules to display calculated dashboard analytics.",
            QColor("#52ff87"),
        )
        self.bottleneck_card = InsightCard(
            "\u26a0",
            "Chunk 1 Bottleneck Analysis (Calculated):",
            "No bottleneck analysis is available before schedules are generated.",
            QColor("#ff9c3d"),
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 24)
        layout.setSpacing(20)
        layout.addLayout(header)
        layout.addWidget(self.winning_card)
        layout.addWidget(self.bottleneck_card)
        layout.addStretch(1)

    def update_insights(self, winning_text: str, bottleneck_text: str) -> None:
        self.winning_card.set_body(winning_text)
        self.bottleneck_card.set_body(bottleneck_text)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)
        _draw_panel(painter, rect, QColor("#111d2f"), QColor("#0a1324"), radius=22)
        glow = QColor("#52ff87")
        glow.setAlpha(150)
        painter.setPen(QPen(glow, 1.6))
        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), 22, 22)
        painter.drawPath(path)


class ExamSchedulerDashboard(QWidget):
    """Reusable dark analytics dashboard for the ExamScheduler application."""

    view_results_requested = pyqtSignal()
    next_batch_requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("examSchedulerDashboard")
        self.setMinimumSize(1180, 680)

        self.total_card = MetricCard(
            "Total Valid Schedules",
            "No schedules",
            "\u2713",
            QColor("#52ff87"),
        )
        self.fitness_card = MetricCard(
            "Best So Far",
            "No schedule",
            "\u25a5",
            QColor("#00d9ff"),
        )
        self.gap_card = MetricCard(
            "Min Study Gap",
            "No data",
            "\u25a6",
            QColor("#8c5bff"),
        )
        self.health_card = MetricCard(
            "Current Batch Best",
            "No batch",
            "\u26e8",
            QColor("#ff9c3d"),
        )
        self.chart = ExamLoadChart()
        self.insights = InsightPanel()
        self.previous_button = NeonButton("View Best Schedule")
        self.next_button = NeonButton("Generate Next 1,000 \u25b6")
        self.pagination_small_label = QLabel("Combinatorial Pagination")
        self.pagination_small_label.setObjectName("dashboardPaginationSmall")
        self.pagination_label = QLabel("No schedules to display")
        self.pagination_label.setObjectName("dashboardPaginationLarge")

        self._build_layout()
        self.previous_button.clicked.connect(self.view_results_requested.emit)
        self.next_button.clicked.connect(self.next_batch_requested.emit)
        self._has_results = False
        self._can_request_more = False
        self.set_action_state(has_results=False, can_request_more=False)
        self.setStyleSheet(_dashboard_qss())

    def _build_layout(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 22, 22, 22)
        root.setSpacing(20)
        root.addWidget(self._build_header())
        root.addLayout(self._build_metrics_row())
        root.addLayout(self._build_main_content(), 1)
        root.addWidget(self._build_pagination_bar())

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("dashboardHeader")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        logo = QLabel("ES")
        logo.setObjectName("dashboardLogo")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setFixedSize(54, 54)
        logo_path = Path(__file__).with_name("assets") / "exam_scheduler_logo.png"
        if logo_path.is_file():
            pixmap = QPixmap(str(logo_path))
            if not pixmap.isNull():
                logo.setText("")
                logo.setPixmap(
                    pixmap.scaled(
                        46,
                        46,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )

        exam = QLabel("Exam")
        exam.setObjectName("dashboardTitleExam")
        scheduler = QLabel("Scheduler")
        scheduler.setObjectName("dashboardTitleScheduler")
        title = QHBoxLayout()
        title.setContentsMargins(0, 0, 0, 0)
        title.setSpacing(0)
        title.addWidget(exam)
        title.addWidget(scheduler)

        layout.addWidget(logo)
        layout.addLayout(title)
        layout.addStretch(1)
        return header

    def _build_metrics_row(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)
        for card in (
            self.total_card,
            self.fitness_card,
            self.gap_card,
            self.health_card,
        ):
            layout.addWidget(card, 1)
        return layout

    def _build_main_content(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)
        layout.addWidget(self.chart, 58)
        layout.addWidget(self.insights, 42)
        return layout

    def _build_pagination_bar(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("dashboardPaginationBar")
        _add_shadow(panel, QColor("#ff9c3d"), blur=24, alpha=55)

        center = QVBoxLayout()
        center.setSpacing(2)
        center.addWidget(self.pagination_small_label, 0, Qt.AlignmentFlag.AlignCenter)
        center.addWidget(self.pagination_label, 0, Qt.AlignmentFlag.AlignCenter)

        layout = QHBoxLayout(panel)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(18)
        layout.addWidget(self.previous_button)
        layout.addStretch(1)
        layout.addLayout(center)
        layout.addStretch(1)
        layout.addWidget(self.next_button)
        panel.setMinimumHeight(92)
        return panel

    def update_metrics(
        self,
        total_schedules,
        fitness_score,
        min_study_gap,
        current_batch_score,
    ) -> None:
        self.total_card.set_value(total_schedules)
        self.fitness_card.set_value(fitness_score)
        self.gap_card.set_value(min_study_gap)
        self.health_card.set_value(current_batch_score)

    def update_chart_data(
        self,
        dates: Sequence[str],
        values: Sequence[int],
    ) -> None:
        self.chart.update_chart_data(dates, values)

    def update_insights(self, winning_text: str, bottleneck_text: str) -> None:
        self.insights.update_insights(winning_text, bottleneck_text)

    def set_action_state(
        self,
        *,
        has_results: bool,
        can_request_more: bool,
    ) -> None:
        self._has_results = has_results
        self._can_request_more = can_request_more
        self._sync_action_buttons()

    def _sync_action_buttons(self) -> None:
        self.previous_button.setEnabled(self._has_results)
        self.next_button.setEnabled(self._can_request_more)

    def set_pagination(
        self,
        chunk_number: int,
        start_index: int,
        end_index: int,
    ) -> None:
        if chunk_number <= 0 or start_index <= 0 or end_index <= 0:
            self.pagination_label.setText("No schedules to display")
            return
        self.pagination_label.setText(
            f"Displaying Chunk {chunk_number} | "
            f"Schedules {start_index:,} - {end_index:,}"
        )

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        gradient = QLinearGradient(
            QPointF(self.rect().topLeft()),
            QPointF(self.rect().bottomRight()),
        )
        gradient.setColorAt(0.0, QColor("#040917"))
        gradient.setColorAt(0.45, QColor("#071021"))
        gradient.setColorAt(1.0, QColor("#02040c"))
        painter.fillRect(self.rect(), gradient)


def _draw_panel(
    painter: QPainter,
    rect,
    top_color: QColor,
    bottom_color: QColor,
    radius: int = 20,
) -> None:
    path = QPainterPath()
    path.addRoundedRect(QRectF(rect), radius, radius)
    gradient = QLinearGradient(QPointF(rect.topLeft()), QPointF(rect.bottomRight()))
    gradient.setColorAt(0, top_color)
    gradient.setColorAt(1, bottom_color)
    painter.fillPath(path, gradient)
    painter.setPen(QPen(QColor(70, 92, 125, 120), 1.2))
    painter.drawPath(path)


def _add_shadow(
    widget: QWidget,
    color: QColor,
    *,
    blur: int,
    alpha: int,
) -> None:
    shadow_color = QColor(color)
    shadow_color.setAlpha(alpha)
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(blur)
    shadow.setOffset(0, 0)
    shadow.setColor(shadow_color)
    widget.setGraphicsEffect(shadow)


def _font(point_size: int, weight: int = 500) -> QFont:
    font = QFont("Segoe UI")
    font.setPointSize(point_size)
    if weight >= 850:
        qt_weight = QFont.Weight.Black
    elif weight >= 800:
        qt_weight = QFont.Weight.ExtraBold
    elif weight >= 700:
        qt_weight = QFont.Weight.Bold
    elif weight >= 600:
        qt_weight = QFont.Weight.DemiBold
    elif weight >= 500:
        qt_weight = QFont.Weight.Medium
    else:
        qt_weight = QFont.Weight.Normal
    font.setWeight(qt_weight)
    return font


def _alignment_flags(*flags: Qt.AlignmentFlag) -> int:
    value = 0
    for flag in flags:
        value |= flag.value
    return value


def _chart_ticks(values: Sequence[int]) -> list[int]:
    max_value = max((max(0, int(value)) for value in values), default=0)
    if max_value <= 4:
        return [0, 1, 2, 3, 4]
    if max_value <= 10:
        return [0, 2, 4, 6, 8, 10]
    if max_value <= 20:
        return [0, 4, 8, 12, 16, 20]

    top = ((max_value + 9) // 10) * 10
    step = max(1, top // 5)
    return [step * index for index in range(6)]


def _plural(noun: str, count: int) -> str:
    if count == 1:
        return noun
    return f"{noun}s"


def _dashboard_qss() -> str:
    return """
    QWidget#examSchedulerDashboard {
        background: transparent;
    }
    QWidget#dashboardHeader {
        background: transparent;
    }
    QLabel#dashboardLogo {
        background: rgba(0, 217, 255, 20);
        border: 1px solid rgba(0, 217, 255, 140);
        border-radius: 14px;
        color: #00d9ff;
        font-size: 18px;
        font-weight: 850;
    }
    QLabel#dashboardTitleExam {
        color: #00d9ff;
        background: transparent;
        font-size: 28px;
        font-weight: 850;
    }
    QLabel#dashboardTitleScheduler {
        color: #ffffff;
        background: transparent;
        font-size: 28px;
        font-weight: 850;
    }
    QWidget#dashboardMetricCard,
    QWidget#dashboardChartPanel {
        background: transparent;
    }
    QWidget#dashboardInsightPanel {
        background: transparent;
    }
    QFrame#dashboardPaginationBar {
        background: #10182a;
        border: 1px solid rgba(255, 156, 61, 112);
        border-radius: 22px;
    }
    QLabel#dashboardMetricTitle {
        color: #b9c6d9;
        background: transparent;
        font-size: 13px;
        font-weight: 650;
    }
    QLabel#dashboardInsightHeaderIcon {
        color: #52ff87;
        border: 2px solid #52ff87;
        border-radius: 17px;
        background: rgba(82, 255, 135, 20);
        font-size: 18px;
        font-weight: 900;
    }
    QLabel#dashboardInsightHeaderTitle {
        color: #52ff87;
        background: transparent;
        font-size: 20px;
        font-weight: 850;
    }
    QLabel#dashboardInsightTitle {
        color: #ffffff;
        background: transparent;
        font-size: 15px;
        font-weight: 850;
    }
    QLabel#dashboardInsightBody {
        color: #c9d4e4;
        background: transparent;
        font-size: 13px;
        line-height: 150%;
    }
    QPushButton#dashboardNeonButton {
        background: rgba(15, 18, 32, 235);
        color: #ffc47a;
        border: 1.5px solid #ff9c3d;
        border-radius: 18px;
        font-size: 14px;
        font-weight: 800;
        padding: 12px 18px;
    }
    QPushButton#dashboardNeonButton:hover {
        background: rgba(255, 156, 61, 26);
        color: #ffffff;
    }
    QLabel#dashboardPaginationSmall {
        color: #aeb8c7;
        background: transparent;
        font-size: 12px;
        font-weight: 650;
    }
    QLabel#dashboardPaginationLarge {
        color: #ffffff;
        background: transparent;
        font-size: 20px;
        font-weight: 900;
    }
    """


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    dashboard = ExamSchedulerDashboard()
    dashboard.update_metrics("4.9 Billion", "98.4%", "3.2 Days", "RAM: 66MB | Safe")
    dashboard.update_chart_data(DEMO_DATES, DEMO_VALUES)
    dashboard.update_insights(DEMO_WINNING_TEXT, DEMO_BOTTLENECK_TEXT)
    dashboard.set_pagination(1, 1, 1000)
    dashboard.resize(1660, 900)
    dashboard.show()
    sys.exit(app.exec())
