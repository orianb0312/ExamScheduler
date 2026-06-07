"""Pagination controls for schedule pages."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget


class PaginationBar(QWidget):
    """Navigate between generated schedule pages."""

    page_changed = pyqtSignal(int)
    more_requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._current_page = 0
        self._page_count = 0
        self._can_request_more = False

        self.previous_button = QPushButton("Previous")
        self.next_button = QPushButton("Next")
        self.page_label = QLabel("Page 0 of 0")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.previous_button.setFixedWidth(110)
        self.next_button.setFixedWidth(110)
        self.page_label.setMinimumWidth(90)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(self.previous_button)
        layout.addWidget(self.page_label)
        layout.addWidget(self.next_button)
        layout.addStretch()

        self.previous_button.clicked.connect(self._go_previous)
        self.next_button.clicked.connect(self._go_next)
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

    def _refresh(self) -> None:
        self.page_label.setText(f"Page {self._current_page} of {self._page_count}")
        self.previous_button.setEnabled(self._current_page > 1)
        self.next_button.setEnabled(
            self._page_count > 0
            and (self._current_page < self._page_count or self._can_request_more)
        )
