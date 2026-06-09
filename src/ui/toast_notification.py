"""Small animated toast used for non-blocking UI messages."""

from __future__ import annotations

from PyQt6.QtCore import (
    QEasingCurve,
    Qt,
    QPoint,
    QParallelAnimationGroup,
    QPropertyAnimation,
    QTimer,
)
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QWidget,
)


class ToastNotification(QFrame):
    """Top-center notification that fades in, waits, and then fades away."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("toastNotification")
        self.setVisible(False)

        self.message_label = QLabel("")
        self.message_label.setObjectName("toastMessage")
        self.message_label.setWordWrap(True)
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.close_button = QPushButton("X")
        self.close_button.setObjectName("toastCloseButton")
        self.close_button.setFixedSize(22, 22)
        self.close_button.clicked.connect(self.hide_toast)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 12, 12, 12)
        layout.setSpacing(10)
        layout.addWidget(self.message_label, 1)
        layout.addWidget(self.close_button, 0)

        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide_toast)

        self._animation: QParallelAnimationGroup | None = None

    def show_message(self, message: str, duration_ms: int = 6000) -> None:
        self._hide_timer.stop()
        self._stop_animation()

        self.message_label.setText(message)
        self._fit_to_parent()

        target = self._target_position()
        self.move(target - QPoint(0, 28))
        self._opacity.setOpacity(0.0)
        self.show()
        self.raise_()

        self._animate_to(target, 1.0, finished=None)
        self._hide_timer.start(duration_ms)

    def hide_toast(self) -> None:
        if self.isHidden():
            return

        self._hide_timer.stop()
        self._stop_animation()

        target = self._target_position() - QPoint(0, 28)
        self._animate_to(target, 0.0, finished=self.hide)

    def reposition(self) -> None:
        if self.isVisible():
            self._fit_to_parent()
            self.move(self._target_position())
            self.raise_()

    def _fit_to_parent(self) -> None:
        parent = self.parentWidget()
        parent_width = parent.width() if parent is not None else 900
        width = min(640, max(360, parent_width - 96))
        self.setFixedWidth(width)
        self.message_label.setMaximumWidth(width - 72)
        self.message_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )
        self.adjustSize()

    def _target_position(self) -> QPoint:
        parent = self.parentWidget()
        parent_width = parent.width() if parent is not None else self.width()
        x = max(16, (parent_width - self.width()) // 2)
        return QPoint(x, 76)

    def _animate_to(self, pos: QPoint, opacity: float, finished) -> None:
        group = QParallelAnimationGroup(self)

        move_animation = QPropertyAnimation(self, b"pos", group)
        move_animation.setDuration(260)
        move_animation.setEndValue(pos)
        move_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        opacity_animation = QPropertyAnimation(self._opacity, b"opacity", group)
        opacity_animation.setDuration(220)
        opacity_animation.setEndValue(opacity)
        opacity_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        group.addAnimation(move_animation)
        group.addAnimation(opacity_animation)
        if finished is not None:
            group.finished.connect(finished)

        self._animation = group
        group.start()

    def _stop_animation(self) -> None:
        if self._animation is not None:
            self._animation.stop()
            self._animation.deleteLater()
            self._animation = None
