"""Slide-out sorting priority controls for generated schedules."""

from __future__ import annotations

from PyQt6.QtCore import QPoint, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.sorting.schedule_priority import (
    SORT_CRITERIA_BY_KEY,
    SORT_CRITERION_DEFINITIONS,
    normalize_sort_priority,
)


_DESCRIPTIONS = {
    "mandatory_min_gap": "Largest minimum calendar-day gap between mandatory exams.",
    "average_cohort_gap": "Highest average calendar-day gap for shared cohorts.",
    "elective_conflicts": "Highest same-day elective conflict count.",
    "mandatory_span": "Largest span between first and last mandatory exam.",
    "max_daily_exams": "Highest maximum number of exams on one date.",
}


def _refresh_style(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class ToggleSwitch(QCheckBox):
    """Compact switch used to enable or disable a sorting criterion."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("sortToggle")
        self.setChecked(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(48, 26)

    def sizeHint(self) -> QSize:
        return QSize(48, 26)

    def hitButton(self, position: QPoint) -> bool:
        return self.rect().contains(position)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        track = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        border_color = QColor("#53d18e" if self.isChecked() else "#6b7380")
        track_color = QColor("#20a464" if self.isChecked() else "#596273")

        painter.setPen(QPen(border_color, 1))
        painter.setBrush(track_color)
        painter.drawRoundedRect(track, track.height() / 2, track.height() / 2)

        knob_size = track.height() - 6
        knob_x = track.right() - knob_size - 3 if self.isChecked() else track.left() + 3
        knob = QRectF(knob_x, track.top() + 3, knob_size, knob_size)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(knob)


class SortDragHandle(QLabel):
    """Small handle that drives layout-owned drag reordering."""

    drag_started = pyqtSignal()
    drag_moved = pyqtSignal(object)
    drag_finished = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(". .\n. .\n. .", parent)
        self.setObjectName("sortDragHandle")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setFixedWidth(22)
        self.setToolTip("Drag to reorder")
        self._dragging = False
        self._press_position: QPoint | None = None

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        self._press_position = event.position().toPoint()
        self._dragging = False
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._press_position is None:
            super().mouseMoveEvent(event)
            return

        move_distance = (event.position().toPoint() - self._press_position).manhattanLength()
        if not self._dragging and move_distance >= 4:
            self._dragging = True
            self.drag_started.emit()

        if self._dragging:
            self.drag_moved.emit(event.globalPosition().toPoint())
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._dragging:
            self.drag_finished.emit()
            event.accept()
        else:
            super().mouseReleaseEvent(event)
        self._press_position = None
        self._dragging = False
        self.setCursor(Qt.CursorShape.OpenHandCursor)


class SortCriterionCard(QWidget):
    """One sortable criterion row inside the slide-out panel."""

    toggled = pyqtSignal()
    move_up_requested = pyqtSignal(object)
    move_down_requested = pyqtSignal(object)
    drag_started = pyqtSignal(object)
    drag_moved = pyqtSignal(object, object)
    drag_finished = pyqtSignal(object)

    def __init__(self, key: str, parent=None) -> None:
        super().__init__(parent)
        self.key = key
        self.setObjectName("sortCriteriaCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumHeight(86)

        definition = SORT_CRITERIA_BY_KEY[key]

        self.drag_handle = SortDragHandle()
        self.rank_label = QLabel("")
        self.rank_label.setObjectName("sortRankCircle")
        self.rank_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rank_label.setFixedSize(26, 26)

        self.title_label = QLabel(definition.title)
        self.title_label.setObjectName("sortCriterionTitle")
        self.description_label = QLabel(_DESCRIPTIONS.get(key, ""))
        self.description_label.setObjectName("sortCriterionDescription")
        self.description_label.setWordWrap(True)

        self.up_button = QPushButton("^")
        self.up_button.setObjectName("sortArrowButton")
        self.up_button.setToolTip("Move up")
        self.up_button.setFixedSize(28, 24)
        self.down_button = QPushButton("v")
        self.down_button.setObjectName("sortArrowButton")
        self.down_button.setToolTip("Move down")
        self.down_button.setFixedSize(28, 24)

        self.toggle = ToggleSwitch()
        self.toggle.setToolTip("Enable criterion")
        self.toggle.setChecked(True)

        self._build_layout()
        self._connect_signals()
        self._sync_active_style()

    @property
    def is_active(self) -> bool:
        return self.toggle.isChecked()

    def set_active(self, active: bool) -> None:
        self.toggle.setChecked(active)
        self._sync_active_style()

    def set_dragging(self, dragging: bool) -> None:
        self.setProperty("dragging", dragging)
        _refresh_style(self)

    def set_rank(self, rank: int) -> None:
        self.rank_label.setText(str(rank))

    def _build_layout(self) -> None:
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(12, 10, 12, 10)
        root_layout.setSpacing(10)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(4)
        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.description_label)

        arrows_layout = QVBoxLayout()
        arrows_layout.setContentsMargins(0, 0, 0, 0)
        arrows_layout.setSpacing(5)
        arrows_layout.addWidget(self.up_button)
        arrows_layout.addWidget(self.down_button)

        root_layout.addWidget(self.drag_handle)
        root_layout.addWidget(self.rank_label)
        root_layout.addLayout(text_layout, 1)
        root_layout.addLayout(arrows_layout)
        root_layout.addWidget(self.toggle)

    def _connect_signals(self) -> None:
        self.toggle.toggled.connect(lambda _checked: self._handle_toggled())
        self.up_button.clicked.connect(lambda: self.move_up_requested.emit(self))
        self.down_button.clicked.connect(lambda: self.move_down_requested.emit(self))
        self.drag_handle.drag_started.connect(lambda: self.drag_started.emit(self))
        self.drag_handle.drag_moved.connect(
            lambda global_pos: self.drag_moved.emit(self, global_pos)
        )
        self.drag_handle.drag_finished.connect(lambda: self.drag_finished.emit(self))

    def _handle_toggled(self) -> None:
        self._sync_active_style()
        self.toggled.emit()

    def _sync_active_style(self) -> None:
        self.setProperty("inactive", not self.is_active)
        self.toggle.setToolTip("Disable criterion" if self.is_active else "Enable criterion")
        _refresh_style(self)


class SortingPriorityWidget(QWidget):
    """Let users visually set the schedule sorting hierarchy."""

    close_requested = pyqtSignal()
    priority_changed = pyqtSignal(tuple)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("sortOptionsPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._cards: list[SortCriterionCard] = []
        self._dragged_card: SortCriterionCard | None = None
        self._is_refreshing = False

        self.title_label = QLabel("Sort priority")
        self.title_label.setObjectName("sortPanelTitle")
        self.subtitle_label = QLabel(
            "Drag or use ^ v to reorder. Active criteria are applied top-first."
        )
        self.subtitle_label.setObjectName("sortPanelSubtitle")
        self.subtitle_label.setWordWrap(True)

        self.enabled_count_label = QLabel("")
        self.enabled_count_label.setObjectName("sortPriorityBadge")
        self.reset_button = QPushButton("Reset")
        self.reset_button.setObjectName("sortResetButton")
        self.close_button = QPushButton("X")
        self.close_button.setObjectName("sortCloseButton")
        self.close_button.setToolTip("Close sort options")
        self.close_button.setFixedSize(30, 30)

        self.card_scroll = QScrollArea()
        self.card_scroll.setObjectName("sortCriteriaScroll")
        self.card_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.card_scroll.setWidgetResizable(True)
        self.card_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.card_stack = QWidget()
        self.card_stack.setObjectName("sortCriteriaStack")
        self.card_stack.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.card_stack_layout = QVBoxLayout(self.card_stack)
        self.card_stack_layout.setContentsMargins(0, 0, 0, 0)
        self.card_stack_layout.setSpacing(10)
        self.card_stack_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.card_scroll.setWidget(self.card_stack)

        self._build_layout()
        self._connect_signals()
        self.set_priority((), emit_change=False)

    @property
    def cards(self) -> tuple[SortCriterionCard, ...]:
        return tuple(self._cards)

    @property
    def priority(self) -> tuple[str, ...]:
        return tuple(card.key for card in self._cards if card.is_active)

    def set_priority(
        self,
        priority: tuple[str, ...] | list[str],
        *,
        emit_change: bool = True,
    ) -> None:
        clean_priority = normalize_sort_priority(priority)
        enabled_keys = set(clean_priority)
        remaining_keys = [
            definition.key
            for definition in SORT_CRITERION_DEFINITIONS
            if definition.key not in enabled_keys
        ]
        ordered_keys = (*clean_priority, *remaining_keys)

        self._is_refreshing = True
        try:
            self._clear_cards()
            for key in ordered_keys:
                self._add_card(key, active=key in enabled_keys)
            self._rebuild_card_stack()
        finally:
            self._is_refreshing = False

        self._refresh_state()
        if emit_change:
            self.priority_changed.emit(self.priority)

    def reset(self) -> None:
        self.set_priority(())

    def _build_layout(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(14)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(8)
        title_row.addWidget(self.title_label)
        title_row.addStretch()
        title_row.addWidget(self.close_button)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(8)
        action_row.addStretch()
        action_row.addWidget(self.enabled_count_label)
        action_row.addWidget(self.reset_button)

        root_layout.addLayout(title_row)
        root_layout.addWidget(self.subtitle_label)
        root_layout.addLayout(action_row)
        root_layout.addWidget(self.card_scroll, 1)

    def _connect_signals(self) -> None:
        self.reset_button.clicked.connect(self.reset)
        self.close_button.clicked.connect(self.close_requested.emit)

    def _clear_cards(self) -> None:
        for card in self._cards:
            self.card_stack_layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()

    def _add_card(self, key: str, active: bool) -> None:
        card = SortCriterionCard(key)
        card.set_active(active)
        card.toggled.connect(self._handle_card_toggled)
        card.move_up_requested.connect(self._move_card_up)
        card.move_down_requested.connect(self._move_card_down)
        card.drag_started.connect(self._start_drag)
        card.drag_moved.connect(self._drag_card)
        card.drag_finished.connect(self._finish_drag)
        self._cards.append(card)

    def _rebuild_card_stack(self) -> None:
        for card in self._cards:
            self.card_stack_layout.removeWidget(card)
        for card in self._cards:
            self.card_stack_layout.addWidget(card)

    def _move_card_up(self, card: SortCriterionCard) -> None:
        self._move_card(card, -1)

    def _move_card_down(self, card: SortCriterionCard) -> None:
        self._move_card(card, 1)

    def _move_card(self, card: SortCriterionCard, direction: int) -> None:
        current_row = self._row_for_card(card)
        target_row = current_row + direction
        if current_row < 0 or target_row < 0 or target_row >= len(self._cards):
            return

        self._cards.pop(current_row)
        self._cards.insert(target_row, card)
        self._keep_inactive_cards_below_active()
        self._rebuild_card_stack()
        self._emit_priority()

    def _start_drag(self, card: SortCriterionCard) -> None:
        self._dragged_card = card
        card.set_dragging(True)

    def _drag_card(self, card: SortCriterionCard, global_position: QPoint) -> None:
        if card is not self._dragged_card:
            return

        current_row = self._row_for_card(card)
        target_row = self._target_row_for_global_position(global_position)
        if current_row < 0 or target_row == current_row:
            return

        self._cards.pop(current_row)
        self._cards.insert(target_row, card)
        self._keep_inactive_cards_below_active()
        self._rebuild_card_stack()
        self._refresh_state()
        self.priority_changed.emit(self.priority)

    def _finish_drag(self, card: SortCriterionCard) -> None:
        if card is self._dragged_card:
            card.set_dragging(False)
            self._dragged_card = None
            self._refresh_state()

    def _target_row_for_global_position(self, global_position: QPoint) -> int:
        local_position = self.card_stack.mapFromGlobal(global_position)
        if not self._cards:
            return 0

        for index, card in enumerate(self._cards):
            if local_position.y() < card.geometry().center().y():
                return index
        return len(self._cards) - 1

    def _handle_card_toggled(self) -> None:
        self._keep_inactive_cards_below_active()
        self._rebuild_card_stack()
        self._emit_priority()

    def _keep_inactive_cards_below_active(self) -> None:
        active_cards = [card for card in self._cards if card.is_active]
        inactive_cards = [card for card in self._cards if not card.is_active]
        self._cards = [*active_cards, *inactive_cards]

    def _emit_priority(self) -> None:
        if self._is_refreshing:
            return
        self._refresh_state()
        self.priority_changed.emit(self.priority)

    def _refresh_state(self) -> None:
        active_count = 0
        for row, card in enumerate(self._cards):
            card.set_rank(row + 1)
            card.up_button.setEnabled(row > 0)
            card.down_button.setEnabled(row < len(self._cards) - 1)
            active_count += 1 if card.is_active else 0
        self.enabled_count_label.setText(f"{active_count} active")

    def _row_for_card(self, card: SortCriterionCard) -> int:
        try:
            return self._cards.index(card)
        except ValueError:
            return -1
