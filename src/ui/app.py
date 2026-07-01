"""PyQt6 application bootstrap for the standalone desktop UI."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from src.ui.main_window import MainWindow


def run(argv: Sequence[str] | None = None) -> int:
    """Create QApplication, show the main window, and enter the event loop."""
    app_args = list(argv) if argv is not None else sys.argv
    app = QApplication(app_args)
    app.setApplicationName("ExamScheduler")

    project_root = Path(__file__).resolve().parents[2]
    icon_path = project_root / "src" / "ui" / "assets" / "exam_scheduler.ico"
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))

    window = MainWindow(project_root=project_root)
    window.show_resizable_maximized()

    return app.exec()
