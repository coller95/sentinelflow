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
    QSizePolicy, QListWidgetItem, QComboBox, QGroupBox, QFrame, QDialog
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

class MacroStep:
    class InputType(Enum):
        Mouse = auto()
        Keyboard = auto()
        Delay = auto()

    def __init__(self, inputType: InputType, value = None, description: str = ""):
        self._inputType = inputType
        self._value = value
        self._description = description

    @property
    def Description(self) -> str:
        return self._description

    @Description.setter
    def Description(self, value: str):
        self._description = value

    def Execute(self, windowHandle: int):
        """Public entry point to run this specific step."""
        if self._inputType == self.InputType.Keyboard:
            self._sendKeystroke(windowHandle, self._value)
            
        elif self._inputType == self.InputType.Mouse:
            # self._value is expected to be a tuple (xN, yN)
            self._sendMouseClick(windowHandle, self._value[0], self._value[1])
            
        elif self._inputType == self.InputType.Delay:
            # self._value is milliseconds
            time.sleep(self._value / 1000.0)

    def _sendKeystroke(self, hwnd: int, vk: int):
        """Private: Handles low-level background keyboard input."""
        # Win32 PostMessage logic goes here
        pass

    def _sendMouseClick(self, hwnd: int, xN: float, yN: float):
        """Private: Handles low-level background mouse input."""
        # Win32 PostMessage logic goes here
        pass

class ActionItem:
    def __init__(self, name: str):
        self._name = name
        self._macroSteps: List[MacroStep] = []

    @property
    def Name(self) -> str:
        return self._name

    @Name.setter
    def Name(self, value: str):
        self._name = value

    @property
    def MacroSteps(self) -> List[MacroStep]:
        return self._macroSteps

    def AddStep(self, macroStep: MacroStep):
        self._macroSteps.append(macroStep)

    def RemoveStep(self, index: int):
        if 0 <= index < len(self._macroSteps):
            self._macroSteps.pop(index)

    def Execute(self, windowHandle: int):
        if not self._macroSteps:
            return

        for step in self._macroSteps:
            step.Execute(windowHandle)

class EventItem:
    class ActivationType(Enum):
        NotSet = auto()
        Hotkey = auto()

    def __init__(self, name: str, action: ActionItem, enabled: bool = False, activationType: ActivationType = ActivationType.NotSet, hotkeyVk: int = None):
        self._name = name
        self._enabled = enabled
        self._selectedActivationType = activationType
        self._activationVkList: List[int] = []
        self._assignedAction = action

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

    @property
    def SelectedActivationType(self) -> ActivationType:
        return self._selectedActivationType

    @SelectedActivationType.setter
    def SelectedActivationType(self, value: ActivationType):
        self._selectedActivationType = value

    @property
    def ActivationVkList(self) -> List[int]:
        return self._activationVkList

    @ActivationVkList.setter
    def ActivationVkList(self, value: List[int]):
        self._activationVkList = value

    @property
    def AssignedAction(self) -> ActionItem:
        return self._assignedAction

    @AssignedAction.setter
    def AssignedAction(self, value: ActionItem):
        self._assignedAction = value

    def Trigger(self, windowHandle: int):
        if self._enabled and self._assignedAction:
            self._assignedAction.Execute(windowHandle)

# =========================
# VIEWMODEL
# =========================

class TriggerMonitorThread(QThread):
    EventTriggered = Signal(EventItem)

    def __init__(self, viewModel, pollIntervalMs=50):
        super().__init__()
        self._viewModel = viewModel
        self._pollIntervalMs = pollIntervalMs
        self._isRunning = True
        self._isCurrentlyHeld = False

    def run(self):
        while self._isRunning:
            for event in self._viewModel.EventItems:
                if not event.Enabled:
                    continue

                if event.SelectedActivationType != EventItem.ActivationType.Hotkey:
                    continue

                if len(event.ActivationVkList) == 0:
                    continue

                # Get the current hardware state using pywin32
                # We check if ALL keys in the combo are currently pressed
                isDownNow = IsHotkeyActive(event.ActivationVkList)

                if self._isCurrentlyHeld and not isDownNow:
                    self.EventTriggered.emit(event)

                self._isCurrentlyHeld = isDownNow
            time.sleep(self._pollIntervalMs / 1000.0)

    def Stop(self):
        self._isRunning = False
        self.wait()

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
    ActionAdded = Signal(ActionItem)
    ActionRemoved = Signal(int)
    HwndUpdated = Signal(object) # HWND
    CaptureImageReady = Signal(object) # Image data

    def __init__(self):
        super().__init__()
        self.EventItems: List[EventItem] = []
        self.ActionItems: List[ActionItem] = []
        self.CurrentHwnd = None
        self.LiveThread: Optional[LiveCaptureThread] = None
        self.LastLiveImg = None
        self.TriggerThread = None

        self.StartSentinel()

    def AddNewEvent(self):
        newAction = ActionItem(name="") 
        newEvent = EventItem(name="New Event", action=newAction)
        
        self.EventItems.append(newEvent)
        self.EventAdded.emit(newEvent)

    def DeleteEvent(self, index: int):
        if 0 <= index < len(self.EventItems):
            self.EventItems.pop(index)
            self.EventRemoved.emit(index)

    def AddNewAction(self):
        newAction = ActionItem(name="New Action")
        self.ActionItems.append(newAction)
        return newAction
    
    def DeleteAction(self, index: int):
        if 0 <= index < len(self.ActionItems):
            self.ActionItems.pop(index)

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
            
    def StartSentinel(self):
        if not self.TriggerThread:
            self.TriggerThread = TriggerMonitorThread(self)
            self.TriggerThread.EventTriggered.connect(self._OnEventTriggered)
            self.TriggerThread.start()

    def _OnEventTriggered(self, event: EventItem):
        print(f"Event Triggered: {event.Name}")
        if self.CurrentHwnd:
            event.Trigger(self.CurrentHwnd)


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

class HotkeyCaptureDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Capture VK Combo")
        self.setFixedSize(250, 100)
        self.CapturedVks = []
        self._currentVks = set()
        
        layout = QVBoxLayout(self)
        self.StatusLabel = QLabel("Holding: 0 keys", alignment=Qt.AlignCenter)
        layout.addWidget(self.StatusLabel)
        
        self.setModal(True)

    def keyPressEvent(self, event):
        vk = event.nativeVirtualKey()
        if vk > 0:
            self._currentVks.add(vk)
            self.StatusLabel.setText(f"Holding: {len(self._currentVks)} keys")

    def keyReleaseEvent(self, event):
        # When keys are released, we finalize the list
        if self._currentVks:
            self.CapturedVks = list(self._currentVks)
            self.accept()

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
        self.MainLayout.addWidget(self.SetupRightPanel())

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

    def SetupRightPanel(self) -> QWidget:
        # Create a container to fix the width as discussed
        rightPanelContainer = QWidget()
        rightPanelContainer.setFixedWidth(350)
        layout = QVBoxLayout(rightPanelContainer)

        self.EventSettingsHeader = QLabel("<b>Event Settings</b>")
        
        # Event Properties
        self.EventNameEdit = QLineEdit()
        self.EventNameEdit.setEnabled(False)
        self.ActivationDropdown = QComboBox()
        self.ActivationDropdown.setEnabled(False)
        self.ActivationDropdown.addItems([at.name for at in EventItem.ActivationType])

        self.ActivationHotkeyLayout = QHBoxLayout()
        self.ActivationHotkeyLayout.addWidget(QLabel("Hotkey:"))
        self.ActivationHotkeyEdit = QLineEdit()
        self.ActivationHotkeyEdit.setReadOnly(True)
        self.ActivationHotkeyLayout.addWidget(self.ActivationHotkeyEdit)
        self.ActivationHotkeyBtn = QPushButton("Capture")
        self.ActivationHotkeyLayout.addWidget(self.ActivationHotkeyBtn)
        self.ActivationHotkeyBtn.setEnabled(False)

        # Action Sequence Properties
        self.ActionNameLabel = QLabel("<b>Action Sequence</b>")

        # The actual list of MacroSteps
        self.MacroStepListWidget = QListWidget()
        self.MacroStepListWidget.setMinimumHeight(200)
        
        # Buttons for Step Management
        stepButtonLayout = QHBoxLayout()
        self.BtnAddStep = QPushButton("Add Step")
        self.BtnDelStep = QPushButton("Remove Step")
        self.BtnAddStep.setEnabled(False)
        self.BtnDelStep.setEnabled(False)
        stepButtonLayout.addWidget(self.BtnAddStep)
        stepButtonLayout.addWidget(self.BtnDelStep)

        # Add to Layout
        layout.addWidget(self.EventSettingsHeader)
        layout.addWidget(QLabel("Event Name:"))
        layout.addWidget(self.EventNameEdit)
        layout.addWidget(QLabel("Trigger Type:"))
        layout.addWidget(self.ActivationDropdown)
        layout.addLayout(self.ActivationHotkeyLayout)
        
        layout.addWidget(self.CreateHorizontalLine()) # Optional visual separator
        
        layout.addWidget(self.ActionNameLabel)
        layout.addWidget(self.MacroStepListWidget)
        layout.addLayout(stepButtonLayout)
        
        layout.addStretch()
        return rightPanelContainer

    def CreateHorizontalLine(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        return line

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
        self.BtnAddStep.clicked.connect(self.OnAddStepClicked)
        self.BtnDelStep.clicked.connect(self.OnRemoveStepClicked)
        self.ActivationHotkeyBtn.clicked.connect(self.OnCaptureHotkey)
        
        # Interaction
        self.LiveImageLabel.Clicked.connect(self.OnImageClicked)
        self.BtnSendClick.clicked.connect(self.OnSendMouseClick)
        self.BtnSendKeystroke.clicked.connect(self.OnSendKeystroke)
        self.MouseXEdit.textChanged.connect(self.OnManualCoordsChanged)
        self.MouseYEdit.textChanged.connect(self.OnManualCoordsChanged)

        # Property Editing
        self.EventListWidget.currentItemChanged.connect(self.OnSelectionChanged)
        self.EventListWidget.itemChanged.connect(self.OnEventItemChanged)
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

    def OnAddStepClicked(self):
        item = self.EventListWidget.currentItem()
        if item:
            eventObj: EventItem = item.data(Qt.UserRole)
            if eventObj.AssignedAction:
                # For now, add a dummy step to test
                newStep = MacroStep(MacroStep.InputType.Delay, 500, "Wait 500ms")
                eventObj.AssignedAction.AddStep(newStep)
                self.RefreshMacroStepList(eventObj.AssignedAction)

    def OnRemoveStepClicked(self):
        currentRow = self.MacroStepListWidget.currentRow()
        item = self.EventListWidget.currentItem()
        if item and currentRow >= 0:
            eventObj: EventItem = item.data(Qt.UserRole)
            if eventObj.AssignedAction:
                eventObj.AssignedAction.RemoveStep(currentRow)
                self.RefreshMacroStepList(eventObj.AssignedAction)

    def OnCaptureHotkey(self):
        item = self.EventListWidget.currentItem()
        if not item: return

        eventObj: EventItem = item.data(Qt.UserRole)
        
        dialog = HotkeyCaptureDialog(self)
        if dialog.exec() == QDialog.Accepted:
            eventObj.ActivationVkList = dialog.CapturedVks
            # Show the raw VKs on the button for debugging/clarity
            self.ActivationHotkeyEdit.setText(", ".join(map(KeyNameFromVk, eventObj.ActivationVkList)))

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
        if not current:
            self.EventNameEdit.clear()
            self.MacroStepListWidget.clear()
            self.EventNameEdit.setEnabled(False)
            self.ActivationDropdown.setEnabled(False)
            self.ActivationHotkeyBtn.setEnabled(False)
            self.BtnAddStep.setEnabled(False)
            self.BtnDelStep.setEnabled(False)
            return

        eventObj: EventItem = current.data(Qt.UserRole)
        
        self.EventNameEdit.setText(eventObj.Name)
        self.EventNameEdit.setEnabled(True)

        idx = self.ActivationDropdown.findText(eventObj.SelectedActivationType.name)
        self.ActivationDropdown.setCurrentIndex(idx)
        self.ActivationDropdown.setEnabled(True)

        self.ActivationHotkeyEdit.setText(", ".join(map(KeyNameFromVk, eventObj.ActivationVkList)))
        self.ActivationHotkeyBtn.setEnabled(True)

        self.RefreshMacroStepList(eventObj.AssignedAction)
        
        self.BtnAddStep.setEnabled(True)
        self.BtnDelStep.setEnabled(True)
        
    def OnEventItemChanged(self, item: QListWidgetItem):
        """Triggered when an item is renamed or check state changes."""
        eventObj: EventItem = item.data(Qt.UserRole)
        if not eventObj:
            return
        eventObj.Enabled = (item.checkState() == Qt.Checked)
            
    def RefreshMacroStepList(self, actionObj: ActionItem):
        """Refreshes the UI list based on the ActionItem's steps."""
        self.MacroStepListWidget.clear()
        for step in actionObj.MacroSteps:
            # We use the 'Description' property we defined earlier
            item = QListWidgetItem(step.Description)
            self.MacroStepListWidget.addItem(item)

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