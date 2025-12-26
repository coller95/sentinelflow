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
from PySide6.QtCore import Signal, QThread, Qt, QPoint, QTimer
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QFileDialog, QListWidget, QMessageBox, 
    QSizePolicy, QListWidgetItem, QComboBox
)
from PySide6.QtGui import QPainter, QPen, QColor, QImage, QPixmap

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
        self.eventItems = []
        self.currentHwnd = None
        self.liveThread = None
        self.lastLiveImg = None
        self.initUi()

    def initUi(self):
        self.setWindowTitle("SentinelFlow Dashboard")
        self.setGeometry(100, 100, 800, 520)

        rootLayout = QHBoxLayout()

        # --- Left Panel: Event List ---
        leftPanel = QVBoxLayout()
        eventBtnLayout = QHBoxLayout()
        
        self.addEventBtn = QPushButton("+")
        self.addEventBtn.setFixedWidth(28)
        self.addEventBtn.clicked.connect(self.handleAddEvent)
        
        self.delEventBtn = QPushButton("-")
        self.delEventBtn.setFixedWidth(28)
        self.delEventBtn.clicked.connect(self.handleDeleteEvent)
        
        eventBtnLayout.addWidget(self.addEventBtn)
        eventBtnLayout.addWidget(self.delEventBtn)
        eventBtnLayout.addStretch()
        
        self.eventListWidget = QListWidget()
        self.eventListWidget.setFixedWidth(200)
        self.eventListWidget.currentItemChanged.connect(self.onEventSelected)
        
        leftPanel.addLayout(eventBtnLayout)
        leftPanel.addWidget(self.eventListWidget)

        # --- Center Panel: Capture & Actions ---
        centerPanel = QVBoxLayout()
        
        # Row 1: Executable Path
        exeLayout = QHBoxLayout()
        self.exePathEdit = QLineEdit()
        self.exePathEdit.setText(r"C:\Users\HONG\Desktop\frozenthrone1.26\war3.exe -window")
        self.browseBtn = QPushButton("Browse")
        self.launchBtn = QPushButton("Launch")
        self.browseBtn.clicked.connect(self.browseExecutable)
        self.launchBtn.clicked.connect(self.launchExecutable)
        exeLayout.addWidget(QLabel("Executable:"))
        exeLayout.addWidget(self.exePathEdit)
        exeLayout.addWidget(self.browseBtn)
        exeLayout.addWidget(self.launchBtn)
        
        # Row 2: Window Handle Find
        hwndLayout = QHBoxLayout()
        self.titleEdit = QLineEdit()
        self.titleEdit.setText("Warcraft III")
        self.findHwndBtn = QPushButton("Find Process")
        self.findHwndBtn.clicked.connect(self.findWindowHandle)
        self.pidLabel = QLabel("Pid: -")
        hwndLayout.addWidget(QLabel("Window Title:"))
        hwndLayout.addWidget(self.titleEdit)
        hwndLayout.addWidget(self.findHwndBtn)
        hwndLayout.addWidget(self.pidLabel)

        resizeWindowLayout = QHBoxLayout()
        self.resizeWidthEdit = QLineEdit()
        self.resizeHeightEdit = QLineEdit()
        self.resizeWidthEdit.setFixedWidth(100)
        self.resizeHeightEdit.setFixedWidth(100)
        self.resizeWidthEdit.setText("800")
        self.resizeHeightEdit.setText("600")
        self.resizeBtn = QPushButton("Resize Window")
        self.resizeBtn.clicked.connect(self.handleResizeWindow)
        resizeWindowLayout.addWidget(QLabel("Width:"))
        resizeWindowLayout.addWidget(self.resizeWidthEdit)
        resizeWindowLayout.addWidget(QLabel("Height:"))
        resizeWindowLayout.addWidget(self.resizeHeightEdit)
        resizeWindowLayout.addWidget(self.resizeBtn)

        # Row 3: Live Capture Start/Stop
        self.liveCaptureBtn = QPushButton("Start Live Capture")
        self.liveCaptureBtn.setCheckable(True)
        self.liveCaptureBtn.toggled.connect(self.toggleLiveCapture)
        
        # Row 4: Image View
        self.liveImageLabel = ClickableImageLabel()
        self.liveImageLabel.setScaledContents(True)
        self.liveImageLabel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.liveImageLabel.clicked.connect(self.handleImageClick)

        # Row 5: Keystroke Sending
        keystrokeLayout = QHBoxLayout()
        self.keystrokeNameEdit = QLineEdit()
        self.keystrokeNameEdit.setPlaceholderText("Keystroke (e.g., 'F1', 'Enter')...")
        self.sendKeystrokeBtn = QPushButton("Send Keystroke")
        self.sendKeystrokeBtn.clicked.connect(self.handleSendKeystroke)
        keystrokeLayout.addWidget(self.keystrokeNameEdit)
        keystrokeLayout.addWidget(self.sendKeystrokeBtn)

        # Row 6: Mouse Clicking
        mouseLayout = QHBoxLayout()
        self.mouseXEdit = QLineEdit()
        self.mouseYEdit = QLineEdit()
        self.mouseXEdit.setFixedWidth(100)
        self.mouseYEdit.setFixedWidth(100)
        self.mouseXEdit.textChanged.connect(self.handleMouseTextChanged)
        self.mouseYEdit.textChanged.connect(self.handleMouseTextChanged)
        self.sendMouseBtn = QPushButton("Send Click")
        self.sendMouseBtn.clicked.connect(self.handleSendMouseClick)
        mouseLayout.addWidget(QLabel("X:"))
        mouseLayout.addWidget(self.mouseXEdit)
        mouseLayout.addWidget(QLabel("Y:"))
        mouseLayout.addWidget(self.mouseYEdit)
        mouseLayout.addWidget(self.sendMouseBtn)

        centerPanel.addLayout(exeLayout)
        centerPanel.addLayout(hwndLayout)
        centerPanel.addLayout(resizeWindowLayout)
        centerPanel.addWidget(self.liveCaptureBtn)
        centerPanel.addWidget(self.liveImageLabel)
        centerPanel.addLayout(keystrokeLayout)
        centerPanel.addLayout(mouseLayout)

        # --- Right Panel: Property Editor ---
        rightPanel = QVBoxLayout()
        self.eventNameEdit = QLineEdit()
        self.eventNameEdit.setFixedWidth(200)
        self.eventNameEdit.setEnabled(False)
        self.eventNameEdit.editingFinished.connect(self.handleEventNameEdit)
        
        self.activationDropdown = QComboBox()
        self.activationDropdown.setFixedWidth(200)
        self.activationDropdown.addItems([at.name for at in EventItem.ActivationType])
        self.activationDropdown.setEnabled(False)
        self.activationDropdown.currentIndexChanged.connect(self.handleActivationTypeChange)

        rightPanel.addWidget(QLabel("Selected Event Name:"))
        rightPanel.addWidget(self.eventNameEdit)
        rightPanel.addWidget(QLabel("Activation Type:"))
        rightPanel.addWidget(self.activationDropdown)
        rightPanel.addStretch()

        rootLayout.addLayout(leftPanel, 1)
        rootLayout.addLayout(centerPanel, 4)
        rootLayout.addLayout(rightPanel, 1)
        self.setLayout(rootLayout)

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

    def onEventSelected(self, current, previous):
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