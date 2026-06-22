"""Settings screen widget for the five scheduling constraints.

"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIntValidator
from PyQt6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from src.services.constraint_settings_policy import (
    CONSTRAINT_DEFINITIONS,
    ConstraintDefinition,
    ConstraintSettingsPolicy,
    DEFAULT_CONSTRAINT_SETTINGS_POLICY,
)


class _ConstraintRow(QWidget):
    """One constraint: a toggle, a k input, and an inline error label."""

    changed = pyqtSignal()

    def __init__(
        self,
        definition: ConstraintDefinition,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._definition = definition
        self.setObjectName("constraintRow")

        self.toggle = QCheckBox()
        self.toggle.setObjectName("constraintToggle")
        self.toggle.setCursor(Qt.CursorShape.PointingHandCursor)

        self.title_label = QLabel(definition.title)
        self.title_label.setObjectName("constraintTitle")
        self.description_label = QLabel(definition.description)
        self.description_label.setObjectName("constraintDescription")
        self.description_label.setWordWrap(True)

        self.k_input = QLineEdit()
        self.k_input.setObjectName("constraintKInput")
        self.k_input.setFixedWidth(90)
        self.k_input.setPlaceholderText("set value")
        # A light front-line guard; the policy remains the source of truth.
        minimum = 0 if definition.allows_zero else 1
        self.k_input.setValidator(QIntValidator(minimum, 10_000_000, self))

        self.error_label = QLabel("")
        self.error_label.setObjectName("constraintError")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)

        self._build_ui()
        self._connect_signals()
        self._sync_input_enabled()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(12)
        top.addWidget(self.toggle)

        text_column = QVBoxLayout()
        text_column.setContentsMargins(0, 0, 0, 0)
        text_column.setSpacing(2)
        text_column.addWidget(self.title_label)
        text_column.addWidget(self.description_label)
        top.addLayout(text_column, 1)

        k_column = QVBoxLayout()
        k_column.setContentsMargins(0, 0, 0, 0)
        k_column.setSpacing(2)
        k_label = QLabel("threshold value")
        k_label.setObjectName("constraintKLabel")
        k_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        k_column.addWidget(k_label)
        k_column.addWidget(self.k_input)
        top.addLayout(k_column)

        layout.addLayout(top)
        layout.addWidget(self.error_label)

    def _connect_signals(self) -> None:
        self.toggle.toggled.connect(self._on_toggled)
        self.k_input.textChanged.connect(lambda _text: self.changed.emit())

    def _on_toggled(self, _checked: bool) -> None:
        self._sync_input_enabled()
        self.changed.emit()

    def _sync_input_enabled(self) -> None:
        # Disabled constraint = the k input is greyed out and cannot be edited.
        enabled = self.toggle.isChecked()
        self.k_input.setEnabled(enabled)
        if not enabled:
            self.clear_error()

    @property
    def key(self) -> str:
        return self._definition.key

    @property
    def is_enabled(self) -> bool:
        return self.toggle.isChecked()

    @property
    def raw_value(self) -> str:
        return self.k_input.text()

    def set_enabled_state(self, enabled: bool) -> None:
        self.toggle.setChecked(enabled)
        self._sync_input_enabled()

    def set_value(self, value: str) -> None:
        self.k_input.setText(value)

    def show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.setVisible(True)
        self.k_input.setProperty("invalid", True)
        self._repolish_input()

    def clear_error(self) -> None:
        self.error_label.clear()
        self.error_label.setVisible(False)
        self.k_input.setProperty("invalid", False)
        self._repolish_input()

    def _repolish_input(self) -> None:
        self.k_input.style().unpolish(self.k_input)
        self.k_input.style().polish(self.k_input)


class ConstraintSettingsWidget(QWidget):
    """Settings page: five constraint toggles with independent k values.

    Like the program selector, every valid change streams straight into the
    surrounding state through settings_changed; there is no explicit save step.
    The parameters become a runtime file only when schedules are generated.
    """

    settings_changed = pyqtSignal(dict)

    def __init__(
        self,
        parent=None,
        policy: ConstraintSettingsPolicy | None = None,
    ) -> None:
        super().__init__(parent)
        self._policy = policy or DEFAULT_CONSTRAINT_SETTINGS_POLICY
        self._rows: dict[str, _ConstraintRow] = {}

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 24)
        layout.setSpacing(18)

        header = QVBoxLayout()
        header.setContentsMargins(0, 0, 0, 10)
        header.setSpacing(6)
        title = QLabel("Scheduling Constraints")
        title.setObjectName("screenTitle")
        subtitle = QLabel(
            "Enable the threshold constraints you want enforced and set an "
            "independent threshold value for each one."
        )
        subtitle.setObjectName("pageSubtitleLabel")
        header.addWidget(title)
        header.addWidget(subtitle)
        layout.addLayout(header)

        card = QWidget()
        card.setObjectName("cardPanel")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 10, 10, 10)
        card_layout.setSpacing(6)

        for index, definition in enumerate(CONSTRAINT_DEFINITIONS):
            row = _ConstraintRow(definition)
            row.changed.connect(self._on_row_changed)
            self._rows[definition.key] = row
            card_layout.addWidget(row)
            if index < len(CONSTRAINT_DEFINITIONS) - 1:
                card_layout.addWidget(self._divider())

        layout.addWidget(card)
        layout.addStretch(1)

    @staticmethod
    def _divider() -> QWidget:
        line = QWidget()
        line.setObjectName("constraintDivider")
        line.setFixedHeight(1)
        return line

    def _on_row_changed(self) -> None:
        # Validate continuously so the user sees errors as they type, and push
        # the clean, valid subset to whoever is listening (the input state).
        validation = self._validate_into_rows()
        self.settings_changed.emit(validation.sanitized_parameters())

    def _current_states(self) -> dict[str, tuple[bool, str]]:
        return {
            key: (row.is_enabled, row.raw_value)
            for key, row in self._rows.items()
        }

    def _validate_into_rows(self):
        validation = self._policy.validate_all(self._current_states())
        for result in validation.results:
            row = self._rows[result.key]
            if result.is_valid:
                row.clear_error()
            else:
                row.show_error(result.error or "Invalid value.")
        return validation

    def validate(self):
        """Run validation and reflect results in the UI. Returns the result."""
        return self._validate_into_rows()

    @property
    def is_valid(self) -> bool:
        return self._policy.validate_all(self._current_states()).is_valid

    def sanitized_parameters(self) -> dict[str, int]:
        """Return the clean enabled+valid constraint parameters for the backend."""
        return self._policy.validate_all(
            self._current_states()
        ).sanitized_parameters()

    def set_constraint(self, key: str, enabled: bool, value: str = "") -> None:
        """Programmatically set a constraint's toggle and value."""
        row = self._rows.get(key)
        if row is None:
            return
        row.set_enabled_state(enabled)
        if value:
            row.set_value(value)