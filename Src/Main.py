"""
SentinelFlow Main Dashboard
Description: PySide6 GUI refactored using MVVM pattern.
Naming Convention: Microsoft CamelCase Guidelines.
"""

import os
import sys
import time
from enum import Enum, auto
from typing import List, Optional

from PySide6.QtCore import Signal, QThread, Qt, QPoint, QObject
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QFileDialog, QListWidget, QMessageBox, 
    QSizePolicy, QListWidgetItem, QComboBox, QGroupBox, QFrame
)
from PySide6.QtGui import QPainter, QPen, QImage, QPixmap

# -------------------------
# Local imports
# -------------------------
from Src.Helper import *

# High DPI Scaling setup
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

# =========================
# MODELS
# =========================

class EventItem:
    # The Enum (The Type)
    class ActivationType(Enum):
        NotSet = auto()
        ImageMatch = auto()
        ImageMatchRoi = auto()
        ImagePercent = auto()
        Interval = auto()
        SetTime = auto()
        Hotkey = auto()
        Manual = auto()
        Script = auto()

    def __init__(self, name: str, enabled: bool = False, activationType: ActivationType = ActivationType.NotSet):
        self._name = name
        self._enabled = enabled
        self._selectedActivationType = activationType # Internal field

    @property
    def Name(self) -> str:
        return self._name

    @Name.setter
    def Name(self, value: str):
        self._name = value

    @property
    def Enabled(self) -> bool:
        return self._enabled

    @Enabled.setter
    def Enabled(self, value: bool):
        self._enabled = value

    # Renamed property to avoid shadowing the Enum class name
    @property
    def SelectedActivationType(self) -> ActivationType:
        return self._selectedActivationType

    @SelectedActivationType.setter
    def SelectedActivationType(self, value: ActivationType):
        self._selectedActivationType = value

# =========================
# VIEWMODEL
# =========================

class LiveCaptureThread(QThread):
    ImageCaptured = Signal(object)

    def __init__(self, hwnd, intervalMs=200, parent=None):
        super().__init__(parent)
        self.Hwnd = hwnd
        self.IntervalMs = intervalMs
        self._isRunning = True

    def run(self):
        self._isRunning = True
        while self._isRunning:
            try:
                img = captureWindowByHwnd(self.Hwnd)
                if img is not None:
                    self.ImageCaptured.emit(img)
                else:
                    print("Failed to capture image: Window might be closed or hidden.")
                    self._isRunning = False 
            except Exception as e:
                print(f"Live capture error: {e}")
                self.ImageCaptured.emit(None)
                self._isRunning = False
            
            time.sleep(self.IntervalMs / 1000.0)

    def Stop(self):
        self._isRunning = False
        self.wait()

class DashboardViewModel(QObject):
    """Handles the business logic and state management."""
    EventAdded = Signal(EventItem)
    EventRemoved = Signal(int)
    HwndUpdated = Signal(object) # HWND
    CaptureImageReady = Signal(object) # Image data

    def __init__(self):
        super().__init__()
        self.EventItems: List[EventItem] = []
        self.CurrentHwnd = None
        self.LiveThread: Optional[LiveCaptureThread] = None
        self.LastLiveImg = None

    def AddNewEvent(self):
        newEvent = EventItem(name="New Event")
        self.EventItems.append(newEvent)
        self.EventAdded.emit(newEvent)

    def DeleteEvent(self, index: int):
        if 0 <= index < len(self.EventItems):
            self.EventItems.pop(index)
            self.EventRemoved.emit(index)

    def FindWindow(self, title: str):
        hwnd = findHwndByTitle(title)
        self.CurrentHwnd = hwnd
        self.HwndUpdated.emit(hwnd)
        return hwnd

    def LaunchApp(self, path: str):
        if path:
            return launchHwndByExecutable(path)
        return None

    def ResizeTargetWindow(self, width: int, height: int):
        if self.CurrentHwnd:
            ResizeWindow(self.CurrentHwnd, width, height)

    def ToggleCapture(self, active: bool):
        if active and self.CurrentHwnd:
            self.StopCapture()
            self.LiveThread = LiveCaptureThread(self.CurrentHwnd)
            self.LiveThread.ImageCaptured.connect(self._HandleImageCaptured)
            self.LiveThread.start()
        else:
            self.StopCapture()

    def _HandleImageCaptured(self, img):
        self.LastLiveImg = img
        self.CaptureImageReady.emit(img)

    def StopCapture(self):
        if self.LiveThread:
            self.LiveThread.Stop()
            self.LiveThread = None

# =========================
# VIEW COMPONENTS
# =========================

class ClickableImageLabel(QLabel):
    Clicked = Signal(QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.NxValue = None
        self.NyValue = None
        self.setMouseTracking(True)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            w, h = self.width(), self.height()
            if w > 0 and h > 0:
                self.NxValue = event.position().x() / w
                self.NyValue = event.position().y() / h
                self.Clicked.emit(event.position().toPoint())
                self.update()

    def SetMarkerNormalized(self, nx: float, ny: float):
        self.NxValue = nx
        self.NyValue = ny
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.NxValue is None or self.NyValue is None:
            return
        x = int(self.NxValue * self.width())
        y = int(self.NyValue * self.height())
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(Qt.red, 2))
        size = 10
        painter.drawLine(x - size, y, x + size, y)
        painter.drawLine(x, y - size, x, y + size)

class DashboardView(QWidget):
    def __init__(self, viewModel: DashboardViewModel):
        super().__init__()
        self.ViewModel = viewModel
        self.InitializeComponents()
        self.WireUpBindings()

    def InitializeComponents(self):
        self.setWindowTitle("SentinelFlow Dashboard")
        self.resize(1000, 650)
        self.MainLayout = QHBoxLayout(self)
        self.MainLayout.setContentsMargins(0, 0, 0, 0)
        self.MainLayout.setSpacing(5)

        # Panels
        self.MainLayout.addLayout(self.SetupLeftPanel(), 0)
        self.MainLayout.addLayout(self.SetupCenterPanel(), 1)
        self.MainLayout.addLayout(self.SetupRightPanel(), 0)

    def SetupLeftPanel(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        btnLayout = QHBoxLayout()
        self.BtnAddEvent = QPushButton("+")
        self.BtnDelEvent = QPushButton("-")
        self.BtnAddEvent.setFixedWidth(30)
        self.BtnDelEvent.setFixedWidth(30)
        btnLayout.addWidget(self.BtnAddEvent)
        btnLayout.addWidget(self.BtnDelEvent)
        btnLayout.addStretch()

        self.EventListWidget = QListWidget()
        self.EventListWidget.setFixedWidth(200)
        self.EventListWidget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        layout.addLayout(btnLayout)
        layout.addWidget(self.EventListWidget)
        return layout

    def SetupCenterPanel(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        mgmtGroupBox = QGroupBox("Target Application Management")
        mgmtGroupBox.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        groupMasterLayout = QVBoxLayout()
        groupMasterLayout.setContentsMargins(10, 15, 10, 10)

        # Row 1: Exe
        exeLayout = QHBoxLayout()
        self.ExePathEdit = QLineEdit(r"C:\Users\HONG\Desktop\frozenthrone1.26\war3.exe -window")
        self.BtnBrowse = QPushButton("Browse")
        self.BtnLaunch = QPushButton("Launch")
        exeLayout.addWidget(QLabel("Path:"))
        exeLayout.addWidget(self.ExePathEdit)
        exeLayout.addWidget(self.BtnBrowse)
        exeLayout.addWidget(self.BtnLaunch)
        groupMasterLayout.addLayout(exeLayout)

        # Row 2: Proc
        procLayout = QHBoxLayout()
        self.TitleEdit = QLineEdit("Warcraft III")
        self.BtnFindHwnd = QPushButton("Find Process")
        self.PidLabel = QLabel("Pid: -")
        procLayout.addWidget(QLabel("Title:"))
        procLayout.addWidget(self.TitleEdit)
        procLayout.addWidget(self.BtnFindHwnd)
        procLayout.addWidget(self.PidLabel)
        groupMasterLayout.addLayout(procLayout)

        # Row 3: Metrics
        resLayout = QHBoxLayout()
        self.ResizeWidthEdit = QLineEdit("800")
        self.ResizeHeightEdit = QLineEdit("600")
        self.BtnResize = QPushButton("Resize Window")
        resLayout.addWidget(QLabel("W:"))
        resLayout.addWidget(self.ResizeWidthEdit)
        resLayout.addWidget(QLabel("H:"))
        resLayout.addWidget(self.ResizeHeightEdit)
        resLayout.addWidget(self.BtnResize)
        groupMasterLayout.addLayout(resLayout)

        groupMasterLayout.addStretch(1)
        mgmtGroupBox.setLayout(groupMasterLayout)

        # Live View
        self.BtnLiveCapture = QPushButton("Start Live Capture")
        self.BtnLiveCapture.setCheckable(True)
        self.LiveImageLabel = ClickableImageLabel()
        self.LiveImageLabel.setScaledContents(True)
        self.LiveImageLabel.setMinimumSize(640, 480)
        self.LiveImageLabel.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.LiveImageLabel.setAlignment(Qt.AlignCenter)

        # Interaction
        interactLayout = QHBoxLayout()
        self.KeystrokeEdit = QLineEdit()
        self.BtnSendKeystroke = QPushButton("Send Key")
        self.MouseXEdit = QLineEdit()
        self.MouseYEdit = QLineEdit()
        self.BtnSendClick = QPushButton("Send Click")
        interactLayout.addWidget(self.KeystrokeEdit)
        interactLayout.addWidget(self.BtnSendKeystroke)
        interactLayout.addSpacing(10)
        interactLayout.addWidget(QLabel("X:"))
        interactLayout.addWidget(self.MouseXEdit)
        interactLayout.addWidget(QLabel("Y:"))
        interactLayout.addWidget(self.MouseYEdit)
        interactLayout.addWidget(self.BtnSendClick)

        layout.addWidget(mgmtGroupBox)
        layout.addWidget(self.BtnLiveCapture)
        layout.addWidget(self.LiveImageLabel)
        layout.addLayout(interactLayout)
        return layout

    def SetupRightPanel(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        self.EventNameEdit = QLineEdit()
        self.EventNameEdit.setEnabled(False)
        self.ActivationDropdown = QComboBox()
        self.ActivationDropdown.setEnabled(False)
        self.ActivationDropdown.addItems([at.name for at in EventItem.ActivationType])

        layout.addWidget(QLabel("<b>Event Settings</b>"))
        layout.addWidget(QLabel("Name:"))
        layout.addWidget(self.EventNameEdit)
        layout.addWidget(QLabel("Trigger Type:"))
        layout.addWidget(self.ActivationDropdown)
        layout.addStretch()
        return layout

    def WireUpBindings(self):
        """Connects UI signals to ViewModel and ViewModel signals to UI updates."""
        # --- View to ViewModel ---
        self.BtnAddEvent.clicked.connect(self.ViewModel.AddNewEvent)
        self.BtnDelEvent.clicked.connect(lambda: self.ViewModel.DeleteEvent(self.EventListWidget.currentRow()))
        self.BtnFindHwnd.clicked.connect(lambda: self.ViewModel.FindWindow(self.TitleEdit.text().strip()))
        self.BtnBrowse.clicked.connect(self.OnBrowseExecutable)
        self.BtnLaunch.clicked.connect(self.OnLaunchExecutable)
        self.BtnResize.clicked.connect(self.OnResizeRequested)
        self.BtnLiveCapture.toggled.connect(self.OnToggleCapture)
        
        # Interaction
        self.LiveImageLabel.Clicked.connect(self.OnImageClicked)
        self.BtnSendClick.clicked.connect(self.OnSendMouseClick)
        self.BtnSendKeystroke.clicked.connect(self.OnSendKeystroke)
        self.MouseXEdit.textChanged.connect(self.OnManualCoordsChanged)
        self.MouseYEdit.textChanged.connect(self.OnManualCoordsChanged)

        # Property Editing
        self.EventListWidget.currentItemChanged.connect(self.OnSelectionChanged)
        self.EventNameEdit.editingFinished.connect(self.OnCommitEventName)
        self.ActivationDropdown.currentIndexChanged.connect(self.OnCommitActivationType)

        # --- ViewModel to View ---
        self.ViewModel.EventAdded.connect(self.UpdateUiAddEvent)
        self.ViewModel.EventRemoved.connect(self.UpdateUiRemoveEvent)
        self.ViewModel.HwndUpdated.connect(self.UpdateUiHwndInfo)
        self.ViewModel.CaptureImageReady.connect(self.UpdateUiImage)

    # --- Interaction Handlers ---

    def OnBrowseExecutable(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select EXE", "", "Executables (*.exe)")
        if path: self.ExePathEdit.setText(path)

    def OnLaunchExecutable(self):
        pid = self.ViewModel.LaunchApp(self.ExePathEdit.text().strip())
        if pid: QMessageBox.information(self, "Success", f"Launched PID: {pid}")

    def OnResizeRequested(self):
        try:
            w, h = int(self.ResizeWidthEdit.text()), int(self.ResizeHeightEdit.text())
            self.ViewModel.ResizeTargetWindow(w, h)
        except ValueError:
            QMessageBox.warning(self, "Error", "Invalid dimensions.")

    def OnToggleCapture(self, checked):
        if checked and not self.ViewModel.CurrentHwnd:
            self.BtnLiveCapture.setChecked(False)
            QMessageBox.warning(self, "Error", "Please find a window first.")
            return
        self.ViewModel.ToggleCapture(checked)

    def OnImageClicked(self, pos: QPoint):
        nx = float(pos.x()) / self.LiveImageLabel.width()
        ny = float(pos.y()) / self.LiveImageLabel.height()
        self.MouseXEdit.setText(f"{nx:.7f}")
        self.MouseYEdit.setText(f"{ny:.7f}")

    def OnManualCoordsChanged(self):
        try:
            nx = float(self.MouseXEdit.text()) if self.MouseXEdit.text() else 0.0
            ny = float(self.MouseYEdit.text()) if self.MouseYEdit.text() else 0.0
            self.LiveImageLabel.SetMarkerNormalized(nx, ny)
        except ValueError: pass

    def OnSendMouseClick(self):
        if self.ViewModel.CurrentHwnd:
            try:
                nx, ny = float(self.MouseXEdit.text()), float(self.MouseYEdit.text())
                sendMouseClickToWindow(self.ViewModel.CurrentHwnd, nx, ny)
            except ValueError:
                QMessageBox.warning(self, "Error", "Invalid coordinates.")

    def OnSendKeystroke(self):
        keyName = self.KeystrokeEdit.text().strip()
        if keyName and self.ViewModel.CurrentHwnd:
            vk = vkFromKeyName(keyName)
            if vk: sendKeystrokeToWindow(self.ViewModel.CurrentHwnd, vk)
            else: QMessageBox.warning(self, "Error", f"Unknown key: {keyName}")

    def OnSelectionChanged(self, current: QListWidgetItem, previous: QListWidgetItem):
        if current:
            eventObj: EventItem = current.data(Qt.UserRole)
            self.EventNameEdit.setText(eventObj.Name)
            self.EventNameEdit.setEnabled(True)
            idx = self.ActivationDropdown.findText(eventObj.SelectedActivationType.name)
            self.ActivationDropdown.setCurrentIndex(idx)
            self.ActivationDropdown.setEnabled(True)
        else:
            self.EventNameEdit.clear()
            self.EventNameEdit.setEnabled(False)
            self.ActivationDropdown.setEnabled(False)

    def OnCommitEventName(self):
        item = self.EventListWidget.currentItem()
        if item:
            eventObj: EventItem = item.data(Qt.UserRole)
            newName = self.EventNameEdit.text().strip()
            if newName:
                eventObj.Name = newName
                item.setText(newName)

    def OnCommitActivationType(self, index):
        item = self.EventListWidget.currentItem()
        if item and index >= 0:
            eventObj: EventItem = item.data(Qt.UserRole)
            typeName = self.ActivationDropdown.currentText()
            # Update via the new property name
            eventObj.SelectedActivationType = EventItem.ActivationType[typeName]

    # --- UI Update Slots ---

    def UpdateUiAddEvent(self, eventObj: EventItem):
        item = QListWidgetItem(eventObj.Name)
        item.setData(Qt.UserRole, eventObj)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked if eventObj.Enabled else Qt.Unchecked)
        self.EventListWidget.addItem(item)

    def UpdateUiRemoveEvent(self, index: int):
        self.EventListWidget.takeItem(index)

    def UpdateUiHwndInfo(self, hwnd):
        if hwnd:
            self.PidLabel.setText(f"PID: {findPidByHwnd(hwnd)}")
        else:
            self.PidLabel.setText("PID: -")
            QMessageBox.warning(self, "Error", "Window not found.")

    def UpdateUiImage(self, img):
        if img is not None:
            h, w, ch = img.shape
            qImg = QImage(img.data, w, h, ch * w, QImage.Format_BGR888)
            pix = QPixmap.fromImage(qImg).scaled(
                self.LiveImageLabel.width(), self.LiveImageLabel.height(), 
                Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.LiveImageLabel.setPixmap(pix)
        else:
            self.LiveImageLabel.clear()

    def closeEvent(self, event):
        self.ViewModel.StopCapture()
        super().closeEvent(event)

# =========================
# MAIN ENTRY
# =========================

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # MVVM Initialization
    vm = DashboardViewModel()
    view = DashboardView(vm)
    
    view.show()
    sys.exit(app.exec())