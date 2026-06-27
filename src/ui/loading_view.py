from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class LoadingView(QWidget):
    """A dedicated loading screen shown while the scheduler process runs."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("loadingView")

        self.title_label = QLabel("Generating Schedules...")
        self.title_label.setObjectName("screenTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.subtitle_label = QLabel("Analyzing constraints and finding optimal combinations.")
        self.subtitle_label.setObjectName("pageSubtitleLabel")
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("loadingProgress")
        self.progress_bar.setRange(0, 0)  # Creates an indeterminate loading animation
        self.progress_bar.setFixedWidth(400)
        self.progress_bar.setTextVisible(False)

        self.log_label = QLabel("Starting process...")
        self.log_label.setObjectName("loadingLogLabel")
        self.log_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.cancel_button = QPushButton("Cancel Generation")
        self.cancel_button.setFixedWidth(160)
        self.cancel_button.setMinimumHeight(36)

        self._build_layout()

    def _build_layout(self) -> None:
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(40, 40, 40, 40)

        layout.addStretch(1)
        layout.addWidget(self.title_label)
        layout.addSpacing(10)
        layout.addWidget(self.subtitle_label)
        layout.addSpacing(40)
        layout.addWidget(self.progress_bar, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(20)
        layout.addWidget(self.log_label)
        layout.addSpacing(40)
        layout.addWidget(self.cancel_button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(2)

    def reset(self) -> None:
        """Reset the loading screen state for a new run."""
        self.log_label.setText("Starting process...")

    def set_status(self, text: str) -> None:
        """Update the sub-status with short log lines from the process."""
        clean_text = text.strip().split('\n')[-1][:80]
        if clean_text:
            self.log_label.setText(clean_text)