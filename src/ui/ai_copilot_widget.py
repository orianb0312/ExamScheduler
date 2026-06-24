from __future__ import annotations

from html import escape

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class AICopilotWidget(QWidget):
    message_submitted = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.chat_display = QTextEdit()
        self.input_field = QLineEdit()
        self.send_button = QPushButton("Send")
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        title_label = QLabel("Local AI Copilot")
        title_label.setObjectName("aiCopilotTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        self.chat_display.setObjectName("aiCopilotDisplay")
        self.chat_display.setReadOnly(True)
        self.chat_display.setPlaceholderText(
            "Your conversation with the scheduling copilot will appear here..."
        )
        self.chat_display.document().setMaximumBlockCount(200)
        layout.addWidget(self.chat_display, 1)

        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(10)

        self.input_field.setObjectName("aiCopilotInput")
        self.input_field.setPlaceholderText(
            "Type a constraint here (for example: do not schedule Physics on Sunday)..."
        )
        self.input_field.setMaxLength(300)
        self.input_field.setClearButtonEnabled(True)

        self.send_button.setObjectName("aiCopilotSend")
        self.send_button.setCursor(Qt.CursorShape.PointingHandCursor)

        input_layout.addWidget(self.input_field, 1)
        input_layout.addWidget(self.send_button)
        layout.addLayout(input_layout)

        self.send_button.clicked.connect(self.handle_send_click)
        self.input_field.returnPressed.connect(self.handle_send_click)

    def handle_send_click(self) -> None:
        user_text = self.input_field.text().strip()
        if not user_text:
            return

        self.append_message("Coordinator", user_text, "#7ed3ff")
        self.input_field.clear()
        self.message_submitted.emit(user_text)

    def set_processing(self, processing: bool) -> None:
        self.input_field.setEnabled(not processing)
        self.send_button.setEnabled(not processing)
        self.send_button.setText("Working..." if processing else "Send")

    def append_message(self, sender: str, text: str, color: str) -> None:
        safe_sender = escape(sender)
        safe_text = escape(text).replace("\n", "<br>")
        formatted_message = (
            f'<span style="color: {color}; font-weight: 700;">{safe_sender}:</span> '
            f"{safe_text}"
        )
        self.chat_display.append(formatted_message)
