"""Pagination controls for schedule pages."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget


PAGE_RULER_VISIBLE_NUMBERS = 3
PAGE_RULER_LOOKAHEAD_SIZE = 1000


class PaginationBar(QWidget):
    """Navigate between generated schedule pages."""

    page_changed = pyqtSignal(int)
    more_requested = pyqtSignal()
    future_page_requested = pyqtSignal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._current_page = 0
        self._page_count = 0
        self._total_page_count: int | None = None
        self._can_request_more = False
        self._page_buttons: list[QPushButton] = []

        self.previous_button = QPushButton("Previous")
        self.next_button = QPushButton("Next")
        self.save_button = QPushButton("Save")
        self.page_label = QLabel("Page 0 of 0")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.previous_button.setFixedWidth(110)
        self.next_button.setFixedWidth(110)
        self.save_button.setFixedWidth(110)
        self.page_label.setMinimumWidth(90)
        self.page_label.hide()

        self.page_ruler = QWidget()
        self.page_ruler.setObjectName("pageRuler")
        self.page_ruler_layout = QHBoxLayout(self.page_ruler)
        self.page_ruler_layout.setContentsMargins(0, 0, 0, 0)
        self.page_ruler_layout.setSpacing(4)
        self.leading_ellipsis_label = QLabel("...")
        self.leading_ellipsis_label.setObjectName("pageRulerEllipsis")
        for index in range(PAGE_RULER_VISIBLE_NUMBERS + 1):
            button = QPushButton("")
            button.setObjectName("pageRulerButton")
            button.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
            button.setProperty("pageNumber", 0)
            button.clicked.connect(
                lambda _checked=False, source=button: self._go_to_page_button(source)
            )
            self._page_buttons.append(button)
            self.page_ruler_layout.addWidget(button)
            if index == 0:
                self.page_ruler_layout.addWidget(self.leading_ellipsis_label)
        self.ellipsis_label = QLabel("...")
        self.ellipsis_label.setObjectName("pageRulerEllipsis")
        self.page_ruler_layout.addWidget(self.ellipsis_label)
        self.last_page_button = QPushButton("")
        self.last_page_button.setObjectName("pageRulerButton")
        self.last_page_button.setSizePolicy(
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Fixed,
        )
        self.last_page_button.setProperty("pageNumber", 0)
        self.last_page_button.clicked.connect(
            lambda _checked=False: self._go_to_page_button(self.last_page_button)
        )
        self.page_ruler_layout.addWidget(self.last_page_button)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(self.previous_button)
        layout.addWidget(self.page_ruler)
        layout.addWidget(self.next_button)
        layout.addWidget(self.save_button)
        layout.addStretch()

        self.previous_button.clicked.connect(self._go_previous)
        self.next_button.clicked.connect(self._go_next)
        self.save_button.clicked.connect(self._go_save)
        self.set_page_count(0)

    @property
    def current_page(self) -> int:
        return self._current_page

    @property
    def page_count(self) -> int:
        return self._page_count

    def set_page_count(self, page_count: int) -> None:
        self._page_count = max(0, page_count)
        if self._page_count == 0:
            self._current_page = 0
        elif self._current_page == 0:
            self._current_page = 1
        else:
            self._current_page = min(self._current_page, self._page_count)
        self._refresh()

    def set_total_page_count(self, total_page_count: int | None) -> None:
        self._total_page_count = total_page_count if total_page_count and total_page_count > 0 else None
        self._refresh()

    def set_can_request_more(self, can_request_more: bool) -> None:
        self._can_request_more = can_request_more
        self._refresh()

    def set_current_page(self, page_number: int) -> None:
        if page_number < 1 or page_number > self._page_count:
            return

        self._current_page = page_number
        self._refresh()
        self.page_changed.emit(self._current_page)

    def reset(self) -> None:
        self._current_page = 0
        self._page_count = 0
        self._can_request_more = False
        self._refresh()

    def _go_previous(self) -> None:
        if self._current_page <= 1:
            return
        self._current_page -= 1
        self._refresh()
        self.page_changed.emit(self._current_page)

    def _go_next(self) -> None:
        if self._current_page >= self._page_count:
            if self._can_request_more and self._page_count > 0:
                self.more_requested.emit()
            return
        self._current_page += 1
        self._refresh()
        self.page_changed.emit(self._current_page)

    def _go_to_page_button(self, button: QPushButton) -> None:
        page_number = int(button.property("pageNumber") or 0)
        if 1 <= page_number <= self._page_count:
            self.set_current_page(page_number)
            return

        if page_number > self._page_count and self._can_request_more:
            self.future_page_requested.emit(page_number)

    def _go_save(self) -> None:
        # Save behavior belongs to a later export task, so this button is idle for now.
        pass

    def _refresh(self) -> None:
        self.page_label.setText(f"Page {self._current_page} of {self._page_count}")
        self._refresh_page_ruler()
        self.previous_button.setEnabled(self._current_page > 1)
        self.next_button.setEnabled(
            self._page_count > 0
            and (self._current_page < self._page_count or self._can_request_more)
        )

    def _refresh_page_ruler(self) -> None:
        if self._page_count == 0:
            for button in self._page_buttons:
                self._set_page_button(button, page_number=0, active=False)
            self.leading_ellipsis_label.hide()
            self.ellipsis_label.hide()
            self._set_page_button(self.last_page_button, page_number=0, active=False)
            return

        # Student note: showing millions of buttons would freeze the screen,
        # so the ruler keeps page 1, then shows the current page area and the tail.
        display_page_count = self._display_page_count()
        window_start = self._current_page
        window_end = min(window_start + PAGE_RULER_VISIBLE_NUMBERS - 1, display_page_count)
        page_numbers = _unique_pages([1, *range(window_start, window_end + 1)])
        self.leading_ellipsis_label.setVisible(
            len(page_numbers) > 1 and page_numbers[1] > 2
        )

        for index, button in enumerate(self._page_buttons):
            page_number = page_numbers[index] if index < len(page_numbers) else 0
            self._set_page_button(
                button,
                page_number=page_number,
                active=page_number == self._current_page,
            )

        has_hidden_tail = window_end < display_page_count
        self.ellipsis_label.setVisible(has_hidden_tail)
        self._set_page_button(
            self.last_page_button,
            page_number=display_page_count if has_hidden_tail else 0,
            active=self._current_page == display_page_count,
        )

    def _display_page_count(self) -> int:
        if self._page_count == 0:
            return 0

        if not self._can_request_more:
            return self._page_count

        lookahead_page_count = self._current_page + PAGE_RULER_LOOKAHEAD_SIZE - 1
        if self._total_page_count is not None:
            lookahead_page_count = min(lookahead_page_count, self._total_page_count)

        return max(self._page_count, lookahead_page_count)

    def _set_page_button(
        self,
        button: QPushButton,
        *,
        page_number: int,
        active: bool,
    ) -> None:
        button.setVisible(page_number > 0)
        button.setEnabled(page_number > 0)
        button.setText(str(page_number) if page_number else "")
        width = button.fontMetrics().horizontalAdvance(button.text()) + 24
        button.setMinimumWidth(max(34, width))
        button.setProperty("pageNumber", page_number)
        button.setObjectName("pageRulerButtonActive" if active else "pageRulerButton")
        button.style().unpolish(button)
        button.style().polish(button)


def _unique_pages(page_numbers) -> list[int]:
    unique_pages: list[int] = []
    for page_number in page_numbers:
        if page_number not in unique_pages:
            unique_pages.append(page_number)
    return unique_pages
