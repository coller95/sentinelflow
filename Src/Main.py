"""
SentinelFlow Main Dashboard
Description: PySide6 GUI for live capture, launcher, and window management.
Refactored to Microsoft CamelCase guidelines.
"""

# -------------------------
# Standard library imports
# -------------------------
import os
import sys
import time
from enum import Enum, auto

# -------------------------
# Third-party imports
# -------------------------
from PySide6.QtCore import Signal, QThread, Qt, QPoint
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

class EventItem:
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
        self._activationType = activationType

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str):
        if not value:
            raise ValueError("Name cannot be empty")
        self._name = value

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value

    @property
    def activationType(self) -> ActivationType:
        return self._activationType

    @activationType.setter
    def activationType(self, value: ActivationType):
        self._activationType = value

# -------------------------
# Live Capture Thread
# -------------------------
class LiveCaptureThread(QThread):
    imageCaptured = Signal(object)

    def __init__(self, hwnd, intervalMs=200, parent=None):
        super().__init__(parent)
        self.hwnd = hwnd
        self.intervalMs = intervalMs
        self._running = True

    def run(self):
        """Main loop: periodically capture the target window."""
        self._running = True
        while self._running:
            img = captureWindowByHwnd(self.hwnd)
            self.imageCaptured.emit(img)
            time.sleep(self.intervalMs / 1000.0)

    def stop(self):
        self._running = False
        self.wait()

class ClickableImageLabel(QLabel):
    clicked = Signal(QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.nxValue = None
        self.nyValue = None
        self.setMouseTracking(True)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            w = self.width()
            h = self.height()
            if w > 0 and h > 0:
                self.nxValue = event.position().x() / w
                self.nyValue = event.position().y() / h
                self.clicked.emit(event.position().toPoint())
                self.update()

    def setMarkerNormalized(self, nx: float, ny: float):
        self.nxValue = nx
        self.nyValue = ny
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.nxValue is None or self.nyValue is None:
            return

        x = int(self.nxValue * self.width())
        y = int(self.nyValue * self.height())
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(Qt.red, 2))

        size = 10
        painter.drawLine(x - size, y, x + size, y)
        painter.drawLine(x, y - size, x, y + size)

class Dashboard(QWidget):
    def __init__(self):
        super().__init__()
        # Data/State
        self.eventItems = []
        self.currentHwnd = None
        self.liveThread = None
        self.lastLiveImg = None
        
        # UI Initialization
        self.InitializeComponents()
        self.WireUpSignals()

    def CreateSeparator(self) -> QFrame:
        """Creates a thin vertical line to separate panels."""
        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setFrameShadow(QFrame.Plain)
        # This color (Dark Gray) matches most modern 'Dark Mode' apps
        line.setStyleSheet("color: #3f3f46;") 
        line.setFixedWidth(1) # Keeps the line very thin
        return line

    def InitializeComponents(self):
        """Primary entry point for UI setup."""
        self.setWindowTitle("SentinelFlow Dashboard")
        self.resize(1000, 650)

        self.MainLayout = QHBoxLayout(self)
        self.MainLayout.setContentsMargins(0, 0, 0, 0)
        self.MainLayout.setSpacing(5) # We want the line to touch the panels

        # Build Panels via specialized methods
        self.MainLayout.addLayout(self.SetupLeftPanel(), 0)
        # self.MainLayout.addWidget(self.CreateSeparator())
        self.MainLayout.addLayout(self.SetupCenterPanel(), 1)
        # self.MainLayout.addWidget(self.CreateSeparator())
        self.MainLayout.addLayout(self.SetupRightPanel(), 0)

    # --- Panel Builders ---

    def SetupLeftPanel(self) -> QVBoxLayout:
        """Logic for the Event List and Management buttons."""
        layout = QVBoxLayout()
        
        # Toolbar
        btnLayout = QHBoxLayout()
        self.btnAddEvent = QPushButton("+")
        self.btnDelEvent = QPushButton("-")
        self.btnAddEvent.setFixedWidth(30)
        self.btnDelEvent.setFixedWidth(30)
        
        btnLayout.addWidget(self.btnAddEvent)
        btnLayout.addWidget(self.btnDelEvent)
        btnLayout.addStretch()

        # List
        self.eventListWidget = QListWidget()
        self.eventListWidget.setFixedWidth(200)
        self.eventListWidget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        layout.addLayout(btnLayout)
        layout.addWidget(self.eventListWidget)
        return layout
    
    def SetupCenterPanel(self) -> QVBoxLayout:
        """Main interaction area: Management Group, Live View, and Manual Controls."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5) # Space between the GroupBox and the Image

        managementGroupBox = QGroupBox("Target Application Management")
        managementGroupBox.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

        # Master layout for the group
        groupMasterLayout = QVBoxLayout()
        groupMasterLayout.setSpacing(0)  # Reduce space between rows
        groupMasterLayout.setContentsMargins(10, 15, 10, 10) # Adjust internal padding
        

        # --- Row 1: Executable Management ---
        exeLayout = QHBoxLayout()
        self.exePathEdit = QLineEdit(r"C:\Users\HONG\Desktop\frozenthrone1.26\war3.exe -window")
        self.btnBrowse = QPushButton("Browse")
        self.btnLaunch = QPushButton("Launch")
        exeLayout.addWidget(QLabel("Path:"))
        exeLayout.addWidget(self.exePathEdit)
        exeLayout.addWidget(self.btnBrowse)
        exeLayout.addWidget(self.btnLaunch)
        groupMasterLayout.addLayout(exeLayout) # Add row to master

        # --- Row 2: Process Management ---
        procLayout = QHBoxLayout()
        self.titleEdit = QLineEdit("Warcraft III")
        self.btnFindHwnd = QPushButton("Find Process")
        self.pidLabel = QLabel("Pid: -")
        procLayout.addWidget(QLabel("Title:"))
        procLayout.addWidget(self.titleEdit)
        procLayout.addWidget(self.btnFindHwnd)
        procLayout.addWidget(self.pidLabel)
        groupMasterLayout.addLayout(procLayout) # Add row to master

        # --- Row 3: Window Metrics ---
        resLayout = QHBoxLayout()
        self.resizeWidthEdit = QLineEdit("800")
        self.resizeHeightEdit = QLineEdit("600")
        self.btnResize = QPushButton("Resize Window")
        resLayout.addWidget(QLabel("W:"))
        resLayout.addWidget(self.resizeWidthEdit)
        resLayout.addWidget(QLabel("H:"))
        resLayout.addWidget(self.resizeHeightEdit)
        resLayout.addWidget(self.btnResize)
        groupMasterLayout.addLayout(resLayout) # Add row to master

        # VITAL: This pushes everything up and removes the big gaps
        groupMasterLayout.addStretch(1)

        # Set the master layout into the GroupBox
        managementGroupBox.setLayout(groupMasterLayout)

        # --- Group 4: Live Viewport ---
        self.liveCaptureBtn = QPushButton("Start Live Capture")
        self.liveCaptureBtn.setCheckable(True)
        self.liveImageLabel = ClickableImageLabel()
        self.liveImageLabel.setScaledContents(True)

        self.liveImageLabel.setMinimumSize(640, 480)
        self.liveImageLabel.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.liveImageLabel.setAlignment(Qt.AlignCenter)

        # --- Group 5: Interaction Controls ---
        interactLayout = QHBoxLayout()
        self.keystrokeEdit = QLineEdit()
        self.btnSendKeystroke = QPushButton("Send Key")
        self.mouseXEdit = QLineEdit()
        self.mouseYEdit = QLineEdit()
        self.btnSendClick = QPushButton("Send Click")
        
        interactLayout.addWidget(self.keystrokeEdit)
        interactLayout.addWidget(self.btnSendKeystroke)
        interactLayout.addSpacing(10)
        interactLayout.addWidget(QLabel("X:"))
        interactLayout.addWidget(self.mouseXEdit)
        interactLayout.addWidget(QLabel("Y:"))
        interactLayout.addWidget(self.mouseYEdit)
        interactLayout.addWidget(self.btnSendClick)

        # Add components to the Center Panel layout
        layout.addWidget(managementGroupBox)
        layout.addWidget(self.liveCaptureBtn)
        layout.addWidget(self.liveImageLabel)
        layout.addLayout(interactLayout)
        
        return layout

    def SetupRightPanel(self) -> QVBoxLayout:
        """Property Editor for the selected event."""
        layout = QVBoxLayout()
        
        self.eventNameEdit = QLineEdit()
        self.eventNameEdit.setEnabled(False)
        self.activationDropdown = QComboBox()
        self.activationDropdown.setEnabled(False)
        self.activationDropdown.addItems([at.name for at in EventItem.ActivationType])

        layout.addWidget(QLabel("<b>Event Settings</b>"))
        layout.addWidget(QLabel("Name:"))
        layout.addWidget(self.eventNameEdit)
        layout.addWidget(QLabel("Trigger Type:"))
        layout.addWidget(self.activationDropdown)
        layout.addStretch()
        
        return layout

    def WireUpSignals(self):
        """Dedicated method for all event connections."""
        # Management
        self.btnAddEvent.clicked.connect(self.handleAddEvent)
        self.btnDelEvent.clicked.connect(self.handleDeleteEvent)
        self.eventListWidget.currentItemChanged.connect(self.onEventSelected)

        # Launcher/Binding
        self.btnBrowse.clicked.connect(self.browseExecutable)
        self.btnLaunch.clicked.connect(self.launchExecutable)
        self.btnFindHwnd.clicked.connect(self.findWindowHandle)
        self.btnResize.clicked.connect(self.handleResizeWindow)

        # Capture & Input
        self.liveCaptureBtn.toggled.connect(self.toggleLiveCapture)
        self.liveImageLabel.clicked.connect(self.handleImageClick)
        self.btnSendKeystroke.clicked.connect(self.handleSendKeystroke)
        self.btnSendClick.clicked.connect(self.handleSendMouseClick)
        self.mouseXEdit.textChanged.connect(self.handleMouseTextChanged)
        self.mouseYEdit.textChanged.connect(self.handleMouseTextChanged)

        # Property Editor
        self.eventNameEdit.editingFinished.connect(self.handleEventNameEdit)
        self.activationDropdown.currentIndexChanged.connect(self.handleActivationTypeChange)

    # --- Event Management Methods ---
    def handleAddEvent(self):
        newEvent = EventItem(name="New Event")
        self.addEventToUi(newEvent)

    def addEventToUi(self, eventObj: EventItem):
        item = QListWidgetItem(eventObj.name)
        item.setData(Qt.UserRole, eventObj)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked if eventObj.enabled else Qt.Unchecked)
        self.eventListWidget.addItem(item)
        self.eventItems.append(eventObj)

    def handleDeleteEvent(self):
        row = self.eventListWidget.currentRow()
        if row >= 0:
            item = self.eventListWidget.takeItem(row)
            eventObj = item.data(Qt.UserRole)
            if eventObj in self.eventItems:
                self.eventItems.remove(eventObj)

    def onEventSelected(self, current: 'QListWidgetItem | None', previous: 'QListWidgetItem | None'):
        if current:
            eventObj: EventItem = current.data(Qt.UserRole)
            self.eventNameEdit.setText(eventObj.name)
            self.eventNameEdit.setEnabled(True)
            
            idx = self.activationDropdown.findText(eventObj.activationType.name)
            self.activationDropdown.setCurrentIndex(idx)
            self.activationDropdown.setEnabled(True)
        else:
            self.eventNameEdit.clear()
            self.eventNameEdit.setEnabled(False)
            self.activationDropdown.setEnabled(False)

    def handleEventNameEdit(self):
        item = self.eventListWidget.currentItem()
        if item:
            eventObj: EventItem = item.data(Qt.UserRole)
            newName = self.eventNameEdit.text().strip()
            if newName:
                eventObj.name = newName
                item.setText(newName)

    def handleActivationTypeChange(self, index):
        item = self.eventListWidget.currentItem()
        if item and index >= 0:
            eventObj: EventItem = item.data(Qt.UserRole)
            typeName = self.activationDropdown.currentText()
            # Direct lookup from Enum (First Principle)
            eventObj.activationType = EventItem.ActivationType[typeName]

    # --- Window & Process Control ---
    def findWindowHandle(self):
        title = self.titleEdit.text().strip()
        hwnd = findHwndByTitle(title)
        if hwnd:
            self.currentHwnd = hwnd
            self.pidLabel.setText(f"PID: {findPidByHwnd(hwnd)}")
        else:
            self.currentHwnd = None
            self.pidLabel.setText("PID: -")
            QMessageBox.warning(self, "Error", "Window not found.")

    def browseExecutable(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select EXE", "", "Executables (*.exe)")
        if path:
            self.exePathEdit.setText(path)

    def launchExecutable(self):
        path = self.exePathEdit.text().strip()
        if path:
            pid = launchHwndByExecutable(path)
            QMessageBox.information(self, "Success", f"Launched PID: {pid}")

    def handleResizeWindow(self):
        if not self.currentHwnd:
            QMessageBox.warning(self, "Error", "Please find a window first.")
            return
        try:
            width = int(self.resizeWidthEdit.text())
            height = int(self.resizeHeightEdit.text())
            ResizeWindow(self.currentHwnd, width, height)
        except ValueError:
            QMessageBox.warning(self, "Error", "Invalid width or height.")            

    # --- Capture Logic ---
    def toggleLiveCapture(self, checked):
        if checked:
            if not self.currentHwnd:
                self.liveCaptureBtn.setChecked(False)
                QMessageBox.warning(self, "Error", "Please find a window first.")
                return
            self.startLiveThread()
        else:
            self.stopLiveThread()

    def startLiveThread(self):
        self.stopLiveThread()
        self.liveThread = LiveCaptureThread(self.currentHwnd)
        self.liveThread.imageCaptured.connect(self.updateLiveImage)
        self.liveThread.start()

    def stopLiveThread(self):
        if self.liveThread:
            self.liveThread.stop()
            self.liveThread = None

    def updateLiveImage(self, img):
        if img is not None:
            self.lastLiveImg = img
            h, w, ch = img.shape
            bytesPerLine = ch * w
            qImg = QImage(img.data, w, h, bytesPerLine, QImage.Format_BGR888)
            pix = QPixmap.fromImage(qImg).scaled(
                self.liveImageLabel.width(), self.liveImageLabel.height(), 
                Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.liveImageLabel.setPixmap(pix)
        else:
            self.liveImageLabel.clear()

    # --- Interaction Logic ---
    def handleImageClick(self, pos: QPoint):
        nx = float(pos.x()) / self.liveImageLabel.width()
        ny = float(pos.y()) / self.liveImageLabel.height()
        self.mouseXEdit.setText(f"{nx:.7f}")
        self.mouseYEdit.setText(f"{ny:.7f}")

    def handleMouseTextChanged(self):
        try:
            nx = float(self.mouseXEdit.text()) if self.mouseXEdit.text() else 0.0
            ny = float(self.mouseYEdit.text()) if self.mouseYEdit.text() else 0.0
            self.liveImageLabel.setMarkerNormalized(nx, ny)
        except ValueError:
            pass

    def handleSendMouseClick(self):
        if self.currentHwnd:
            try:
                nx = float(self.mouseXEdit.text())
                ny = float(self.mouseYEdit.text())
                sendMouseClickToWindow(self.currentHwnd, nx, ny)
            except ValueError:
                QMessageBox.warning(self, "Error", "Invalid coordinates.")

    def handleSendKeystroke(self):
        macroName = self.keystrokeNameEdit.text().strip()
        if not macroName or not self.currentHwnd:
            return
        vk = vkFromKeyName(macroName)
        if vk:
            sendKeystrokeToWindow(self.currentHwnd, vk)
        else:
            QMessageBox.warning(self, "Error", f"Unknown key: {macroName}")

    def closeEvent(self, event):
        self.stopLiveThread()
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Dashboard()
    window.show()
    sys.exit(app.exec())