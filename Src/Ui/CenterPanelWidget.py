from typing import Any, Optional, Protocol
import numpy as np
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QLabel, QGroupBox, QSizePolicy,
    QMessageBox, QFileDialog
)

from Src.Ui.UiShared import ClickableImageLabel

class DashboardViewModelProtocol(Protocol):
    WindowHandleUpdated: Any
    CaptureImageReady: Any

    def HasTargetWindow(self) -> bool: ...

    @property
    def CaptureMousePositionNormalized(self) -> Optional[tuple[float, float]]: ...

    @CaptureMousePositionNormalized.setter
    def CaptureMousePositionNormalized(self, point: Optional[tuple[float, float]]) -> None: ...

    def FindWindow(self, title: str) -> Optional[int]: ...
    def GetCurrentTargetPid(self) -> Optional[int]: ...
    def LaunchApplication(self, path: str) -> Optional[int]: ...
    def ResizeTargetWindow(self, width: int, height: int) -> None: ...
    def ToggleCapture(self, active: bool) -> None: ...
    def TrySendMouseClick(self, normalizedX: float, normalizedY: float) -> bool: ...
    def TrySendKeystrokeByName(self, keyName: str) -> bool: ...


class CenterPanelWidget(QWidget):
    """Center panel widget containing target management, live capture, and interaction controls."""

    def __init__(self, viewModel: DashboardViewModelProtocol) -> None:
        super().__init__()
        self.ViewModel = viewModel
        self._setupCenterPanel()
        self._wireUpBindings()

    def _setupCenterPanel(self) -> None:
        """Set up the center panel with application management and live view."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        mgmtGroupBox = QGroupBox("Target Application Management")
        mgmtGroupBox.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

        groupMasterLayout = QVBoxLayout()
        groupMasterLayout.setContentsMargins(10, 15, 10, 10)

        # Row 1: Exe
        exeLayout = QHBoxLayout()
        self.exePathEdit = QLineEdit(r"C:\Users\HONG\Desktop\frozenthrone1.26\war3.exe -window")
        self.browseButton = QPushButton("Browse")
        self.launchButton = QPushButton("Launch")

        exeLayout.addWidget(QLabel("Path:"))
        exeLayout.addWidget(self.exePathEdit)
        exeLayout.addWidget(self.browseButton)
        exeLayout.addWidget(self.launchButton)
        groupMasterLayout.addLayout(exeLayout)

        # Row 2: Proc
        procLayout = QHBoxLayout()
        self.titleEdit = QLineEdit("Warcraft III")
        self.findWindowButton = QPushButton("Find Process")
        self.pidLabel = QLabel("Pid: -")

        procLayout.addWidget(QLabel("Title:"))
        procLayout.addWidget(self.titleEdit)
        procLayout.addWidget(self.findWindowButton)
        procLayout.addWidget(self.pidLabel)
        groupMasterLayout.addLayout(procLayout)

        # Row 3: Metrics
        resLayout = QHBoxLayout()
        self.resizeWidthEdit = QLineEdit("640")
        self.resizeHeightEdit = QLineEdit("480")
        self.resizeWindowButton = QPushButton("Resize Window")

        resLayout.addWidget(QLabel("W:"))
        resLayout.addWidget(self.resizeWidthEdit)
        resLayout.addWidget(QLabel("H:"))
        resLayout.addWidget(self.resizeHeightEdit)
        resLayout.addWidget(self.resizeWindowButton)
        groupMasterLayout.addLayout(resLayout)

        groupMasterLayout.addStretch(1)
        mgmtGroupBox.setLayout(groupMasterLayout)

        # Live View
        self.liveCaptureButton = QPushButton("Start Live Capture")
        self.liveCaptureButton.setCheckable(True)

        self.liveImageLabel = ClickableImageLabel()
        self.liveImageLabel.setScaledContents(True)
        self.liveImageLabel.setMinimumSize(640, 480)
        self.liveImageLabel.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.liveImageLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Interaction
        interactLayout = QHBoxLayout()
        self.keystrokeEdit = QLineEdit()
        self.sendKeystrokeButton = QPushButton("Send Key")
        self.mouseXEdit = QLineEdit()
        self.mouseYEdit = QLineEdit()
        self.sendClickButton = QPushButton("Send Click")

        interactLayout.addWidget(self.keystrokeEdit)
        interactLayout.addWidget(self.sendKeystrokeButton)
        interactLayout.addSpacing(10)
        interactLayout.addWidget(QLabel("X:"))
        interactLayout.addWidget(self.mouseXEdit)
        interactLayout.addWidget(QLabel("Y:"))
        interactLayout.addWidget(self.mouseYEdit)
        interactLayout.addWidget(self.sendClickButton)

        layout.addWidget(mgmtGroupBox)
        layout.addWidget(self.liveCaptureButton)
        layout.addWidget(self.liveImageLabel)
        layout.addLayout(interactLayout)

    def _wireUpBindings(self) -> None:
        """Connect UI signals to ViewModel methods and ViewModel signals to UI updates."""
        self.findWindowButton.clicked.connect(lambda: self.ViewModel.FindWindow(self.titleEdit.text().strip()))
        self.browseButton.clicked.connect(self._onBrowseExecutable)
        self.launchButton.clicked.connect(self._onLaunchExecutable)
        self.resizeWindowButton.clicked.connect(self._onResizeRequested)

        self.liveCaptureButton.toggled.connect(self._onToggleCapture)

        # Interaction
        self.liveImageLabel.Clicked.connect(self._onImageClicked)
        self.sendClickButton.clicked.connect(self._onSendMouseClick)
        self.sendKeystrokeButton.clicked.connect(self._onSendKeystroke)

        self.mouseXEdit.textChanged.connect(self._onManualCoordsChanged)
        self.mouseYEdit.textChanged.connect(self._onManualCoordsChanged)

        # --- ViewModel to View ---
        self.ViewModel.WindowHandleUpdated.connect(self._updateUiWindowHandleInfo)
        self.ViewModel.CaptureImageReady.connect(self._updateUiImage)

    def _onBrowseExecutable(self) -> None:
        """Handle browse executable button click."""
        path, _ = QFileDialog.getOpenFileName(self, "Select EXE", "", "Executables (*.exe)")
        if path:
            self.exePathEdit.setText(path)

    def _onLaunchExecutable(self) -> None:
        """Handle launch executable button click."""
        pid = self.ViewModel.LaunchApplication(self.exePathEdit.text().strip())
        if pid:
            QMessageBox.information(self, "Success", f"Launched PID: {pid}")

    def _onResizeRequested(self) -> None:
        """Handle resize window button click."""
        try:
            width, height = int(self.resizeWidthEdit.text()), int(self.resizeHeightEdit.text())
            self.ViewModel.ResizeTargetWindow(width, height)
        except ValueError:
            QMessageBox.warning(self, "Error", "Invalid dimensions.")

    def _onToggleCapture(self, checked: bool) -> None:
        """Handle live capture toggle."""
        if checked and not self.ViewModel.HasTargetWindow():
            self.liveCaptureButton.setChecked(False)
            QMessageBox.warning(self, "Error", "Please find a window first.")
            return

        self.ViewModel.ToggleCapture(checked)

    def _onImageClicked(self, position: QPoint) -> None:
        """Handle image click events."""
        normalizedX = float(position.x()) / self.liveImageLabel.width()
        normalizedY = float(position.y()) / self.liveImageLabel.height()
        self.mouseXEdit.setText(f"{normalizedX:.7f}")
        self.mouseYEdit.setText(f"{normalizedY:.7f}")

    def _onManualCoordsChanged(self) -> None:
        """Handle manual coordinate changes."""
        try:
            normalizedX = float(self.mouseXEdit.text()) if self.mouseXEdit.text() else 0.0
            normalizedY = float(self.mouseYEdit.text()) if self.mouseYEdit.text() else 0.0
            self.ViewModel.CaptureMousePositionNormalized = (normalizedX, normalizedY)
            self.liveImageLabel.SetMarkerNormalized(normalizedX, normalizedY)
        except ValueError:
            pass

    def _onSendMouseClick(self) -> None:
        """Handle send mouse click button click."""
        try:
            normalizedX, normalizedY = float(self.mouseXEdit.text()), float(self.mouseYEdit.text())
        except ValueError:
            QMessageBox.warning(self, "Error", "Invalid coordinates.")
            return

        if not self.ViewModel.TrySendMouseClick(normalizedX, normalizedY):
            QMessageBox.warning(self, "Error", "No target window selected.")

    def _onSendKeystroke(self) -> None:
        """Handle send keystroke button click."""
        keyName = self.keystrokeEdit.text().strip()
        if not keyName:
            return

        if not self.ViewModel.TrySendKeystrokeByName(keyName):
            QMessageBox.warning(self, "Error", f"Failed to send key: {keyName}")

    def _updateUiWindowHandleInfo(self, windowHandle: Optional[int]) -> None:
        """Update UI with window handle information."""
        if not windowHandle:
            self.pidLabel.setText("PID: -")
            QMessageBox.warning(self, "Error", "Window not found.")
            return

        pid = self.ViewModel.GetCurrentTargetPid()
        self.pidLabel.setText(f"PID: {pid if pid is not None else '-'}")

    def _updateUiImage(self, image: Optional[np.ndarray[Any, Any]]) -> None:
        """Update UI with a new image."""
        if image is not None:
            height, width, channels = image.shape
            qImage = QImage(image.data, width, height, channels * width, QImage.Format.Format_BGR888)
            pixmap = QPixmap.fromImage(qImage).scaled(
                self.liveImageLabel.width(),
                self.liveImageLabel.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.liveImageLabel.setPixmap(pixmap)
        else:
            self.liveImageLabel.clear()

