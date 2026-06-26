from __future__ import annotations

from html import escape

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class AICopilotWidget(QWidget):
    message_submitted = pyqtSignal(str)
    constraint_generated = pyqtSignal(dict)
    clear_rules_requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.chat_display = QTextEdit()
        self.input_field = QLineEdit()
        self.send_button = QPushButton("Send")
        self.clear_rules_button = QPushButton("Clear all AI Rules")
        self.active_rules_label = QLabel("No active AI rules")
        self._active_rule_count = 0
        self._setup_ui()

    def _setup_ui(self) -> None:
        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(12)

        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(8)

        title_label = QLabel("Local AI Copilot")
        title_label.setObjectName("aiCopilotTitle")
        title_layout.addWidget(title_label)
        title_layout.addStretch(1)

        self.clear_rules_button.setObjectName("aiCopilotClearRules")
        self.clear_rules_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_rules_button.setToolTip(
            "Remove every rule created by the AI copilot. Base rules are not affected."
        )
        self.clear_rules_button.setEnabled(False)
        title_layout.addWidget(self.clear_rules_button)
        self._root_layout.addLayout(title_layout)

        self.active_rules_label.setObjectName("aiCopilotRulesSummary")
        self.active_rules_label.setTextFormat(Qt.TextFormat.PlainText)
        self.active_rules_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self._root_layout.addWidget(self.active_rules_label)

        self.chat_display.setObjectName("aiCopilotDisplay")
        self.chat_display.setReadOnly(True)
        self.chat_display.setPlaceholderText(
            "Your conversation with the scheduling copilot will appear here..."
        )
        self.chat_display.document().setMaximumBlockCount(200)
        self.chat_display.setMinimumHeight(170)
        self.chat_display.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._root_layout.addWidget(self.chat_display, 1)

        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(10)

        self.input_field.setObjectName("aiCopilotInput")
        self.input_field.setPlaceholderText(
            "Type a constraint here (for example: do not schedule Physics on Sunday)..."
        )
        self.input_field.setMaxLength(250)
        self.input_field.setClearButtonEnabled(True)

        self.send_button.setObjectName("aiCopilotSend")
        self.send_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_button.setMinimumWidth(72)
        self.send_button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        input_layout.addWidget(self.input_field, 4)
        input_layout.addWidget(self.send_button, 1)
        self._root_layout.addLayout(input_layout)

        self.send_button.clicked.connect(self.handle_send_click)
        self.input_field.returnPressed.connect(self.handle_send_click)
        self.clear_rules_button.clicked.connect(
            self.clear_rules_requested.emit
        )

    def set_responsive_height(self, height: int) -> None:
        """Resize the conversation area to fit its current dashboard row."""
        target_height = max(108, height)
        compact = target_height < 170
        self._root_layout.setSpacing(6 if compact else 12)
        display_height = max(
            30 if compact else 64,
            target_height - (88 if compact else 104),
        )
        self.setMinimumHeight(target_height)
        self.setMaximumHeight(target_height)
        self.chat_display.setMinimumHeight(display_height)
        self.chat_display.setMaximumHeight(display_height)

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
        self.clear_rules_button.setEnabled(
            not processing and self._active_rule_count > 0
        )
        self.send_button.setText("Working..." if processing else "Send")

    def set_active_rules(self, rules: dict[str, dict]) -> None:
        """Show a compact, persistent summary of the currently loaded AI rules."""
        self._active_rule_count = len(rules)
        if not rules:
            self.active_rules_label.setText("No active AI rules")
            self.active_rules_label.setToolTip("")
            self.clear_rules_button.setEnabled(False)
            return

        entries = [
            f'{rule_id}: {rule.get("description", "AI scheduling rule")}'
            for rule_id, rule in rules.items()
        ]
        visible_entries = [
            entry if len(entry) <= 52 else f"{entry[:49]}..."
            for entry in entries[:2]
        ]
        summary = "  •  ".join(visible_entries)
        if len(entries) > len(visible_entries):
            summary += f"  •  +{len(entries) - len(visible_entries)} more"

        self.active_rules_label.setText(
            f"Active AI rules ({len(entries)}): {summary}"
        )
        self.active_rules_label.setToolTip("\n".join(entries))
        self.clear_rules_button.setEnabled(self.input_field.isEnabled())

    def append_message(self, sender: str, text: str, color: str) -> None:
        safe_sender = escape(sender)
        safe_text = escape(text).replace("\n", "<br>")
        formatted_message = (
            f'<span style="color: {color}; font-weight: 700;">{safe_sender}:</span> '
            f"{safe_text}"
        )
        self.chat_display.append(formatted_message)
