from __future__ import annotations

from typing import List, Optional, Final

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout, QWidget


BUTTON_STYLE_RUNNING: Final[str] = """
QPushButton {
    background-color: #c0392b; /* Darker Red */
    color: white;
    border-radius: 6px;
    font-weight: bold;
    padding: 8px;
}
QPushButton:hover {
    background-color: #e74c3c; /* Brighter Red */
}
"""

BUTTON_STYLE_STOPPED: Final[str] = """
QPushButton {
    background-color: #27ae60; /* Darker Green */
    color: white;
    border-radius: 6px;
    font-weight: bold;
    padding: 8px;
}
QPushButton:hover {
    background-color: #2ecc71; /* Brighter Green */
}
"""


class HotkeyCaptureDialog(QDialog):
    """Dialog that captures a key combination when keys are pressed and released."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Capture Hotkey Combination")
        self.setFixedSize(250, 100)
        self.CapturedVirtualKeyCodes: List[int] = []
        self._currentVirtualKeyCodes: set[int] = set()

        layout = QVBoxLayout(self)
        self.StatusLabel = QLabel("Holding: 0 keys", alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.StatusLabel)
        self.setModal(True)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        virtualKeyCode = event.nativeVirtualKey()
        if virtualKeyCode > 0:
            self._currentVirtualKeyCodes.add(virtualKeyCode)
            self.StatusLabel.setText(f"Holding: {len(self._currentVirtualKeyCodes)} keys")

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if self._currentVirtualKeyCodes:
            self.CapturedVirtualKeyCodes = list(self._currentVirtualKeyCodes)
            self.accept()
