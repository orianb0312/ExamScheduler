"""Output view for streamed schedule systems."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from src.ui.pagination_bar import PaginationBar
from src.ui.ui_cache import DEFAULT_BATCH_SIZE, ScheduleCache, ScheduleSystem


class OutputView(QWidget):
    """Display live CLI logs and cached schedule pages."""

    back_requested = pyqtSignal()
    more_requested = pyqtSignal()

    def __init__(self, batch_size: int = DEFAULT_BATCH_SIZE, parent=None) -> None:
        super().__init__(parent)
        self.cache = ScheduleCache(batch_size=batch_size)
        self._pending_more_page: int | None = None

        self.title_label = QLabel("Output Screen")
        self.title_label.setObjectName("screenTitle")
        self.status_label = QLabel("Ready")
        self.pagination_bar = PaginationBar()
        self.back_button = QPushButton("Back to Input")
        self.log_label = QLabel("CLI output")
        self.cache_label = QLabel("Cached schedule pages")
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.system_view = QPlainTextEdit()
        self.system_view.setReadOnly(True)

        self._build_layout()
        self._connect_signals()
        self._refresh_page()

    def clear(self) -> None:
        self.cache.clear()
        self.log_view.clear()
        self.system_view.clear()
        self.status_label.setText("Ready")
        self.pagination_bar.reset()
        self._refresh_page()

    def set_running(self, running: bool) -> None:
        self.status_label.setText("Running..." if running else "Ready")

    def set_finished(self, exit_code: int, status: str) -> None:
        self.status_label.setText(f"Finished: exit {exit_code}, {status}")

    def set_stream_progress(self, system_count: int) -> None:
        self.status_label.setText(f"Running... cached {system_count:,} schedule systems")

    def set_more_available(self, available: bool) -> None:
        self.pagination_bar.set_can_request_more(available)

    def set_error(self, message: str) -> None:
        self.status_label.setText(f"Error: {message}")

    def append_log(self, text: str) -> None:
        self.log_view.moveCursor(QTextCursor.MoveOperation.End)
        self.log_view.insertPlainText(text)
        self.log_view.moveCursor(QTextCursor.MoveOperation.End)

    def add_systems(self, systems: list[ScheduleSystem]) -> None:
        if not systems:
            return

        self.cache.extend(systems)
        self.pagination_bar.set_page_count(self.cache.batch_count)
        if (
            self._pending_more_page is not None
            and self.cache.batch_count >= self._pending_more_page
        ):
            self.pagination_bar.set_current_page(self._pending_more_page)
            self._pending_more_page = None
        self._refresh_page()

    def _build_layout(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 18, 18, 18)
        root_layout.setSpacing(10)

        header = QHBoxLayout()
        header.addWidget(self.title_label)
        header.addStretch()
        header.addWidget(self.back_button)
        root_layout.addLayout(header)

        self.status_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        root_layout.addWidget(self.status_label)
        root_layout.addWidget(self.pagination_bar)

        splitter = QSplitter()
        splitter.setOrientation(Qt.Orientation.Horizontal)
        splitter.addWidget(self._labeled_pane(self.log_label, self.log_view))
        splitter.addWidget(self._labeled_pane(self.cache_label, self.system_view))
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        root_layout.addWidget(splitter)

    def _connect_signals(self) -> None:
        self.pagination_bar.page_changed.connect(lambda _page: self._refresh_page())
        self.pagination_bar.more_requested.connect(self._request_more_systems)
        self.back_button.clicked.connect(self.back_requested.emit)

    def _request_more_systems(self) -> None:
        self._pending_more_page = self.pagination_bar.current_page + 1
        self.set_more_available(False)
        self.status_label.setText("Generating next 1,000 schedule systems...")
        self.more_requested.emit()

    def _refresh_page(self) -> None:
        if self.cache.batch_count == 0:
            self.system_view.setPlainText(
                "No schedule pages are available yet.\n\n"
                "This is expected before a run finishes, or when using complete-count "
                "mode because that mode only reports totals."
            )
            return

        systems = self.cache.get_page(self.pagination_bar.current_page)
        text = "\n\n".join(system.text for system in systems)
        self.system_view.setPlainText(text)

    @staticmethod
    def _labeled_pane(label: QLabel, editor: QPlainTextEdit) -> QWidget:
        pane = QWidget()
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        label.setObjectName("paneTitle")
        layout.addWidget(label)
        layout.addWidget(editor)
        return pane
