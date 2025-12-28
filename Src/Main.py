"""
SentinelFlow Main Dashboard
Description: PySide6 GUI refactored using MVVM pattern.
Naming Convention: Microsoft CamelCase Guidelines.
"""

import os
import sys
import time
import pickle
from enum import Enum, auto
from typing import List, Optional

from PySide6.QtCore import Signal, QThread, Qt, QPoint, QObject, QSize, QRect, QMutexLocker, QMutex
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QFileDialog, QListWidget, QMessageBox, 
    QSizePolicy, QListWidgetItem, QComboBox, QGroupBox, QFrame, QDialog, QInputDialog, QRubberBand, 
)
from PySide6.QtGui import QPainter, QPen, QImage, QPixmap, QIcon

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

class RectangleRegion:
    def __init__(self, xN: float = 0.0, yN: float = 0.0, wN: float = 1.0, hN: float = 1.0):
        self._xN = xN
        self._yN = yN
        self._wN = wN
        self._hN = hN

    @property
    def XN(self) -> float:
        return self._xN

    @XN.setter
    def XN(self, value: float):
        self._xN = value

    @property
    def YN(self) -> float:
        return self._yN

    @YN.setter
    def YN(self, value: float):
        self._yN = value

    @property
    def WN(self) -> float:
        return self._wN

    @WN.setter
    def WN(self, value: float):
        self._wN = value

    @property
    def HN(self) -> float:
        return self._hN

    @HN.setter
    def HN(self, value: float):
        self._hN = value

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
        sendKeystrokeToWindow(hwnd, vk)
        pass

    def _sendMouseClick(self, hwnd: int, xN: float, yN: float):
        """Private: Handles low-level background mouse input."""
        sendMouseClickToWindow(hwnd, xN, yN)
        pass

class ActionItem:
    def __init__(self):
        self._macroSteps: List[MacroStep] = []

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
        Loop = auto()
        ImageMatchRoi = auto()
        ProgessBar = auto()

    def __init__(self, name: str, action: ActionItem, enabled: bool = False, activationType: ActivationType = ActivationType.NotSet, loopCount: int = 0, intervalMs: int = 1000, roi: RectangleRegion = RectangleRegion(0.0, 0.0, 1.0, 1.0), threshold: float = 0.9):
        self._name = name
        self._enabled = enabled
        self._selectedActivationType = activationType
        self._activationVkList: List[int] = []
        self.__isCurrentlyHeld = False
        self._loopCount = loopCount
        self.__loopCounter = 0
        self._intervalMs = intervalMs
        self.__timeOfLastTriggerMs = 0.0
        self._roi = roi  # Normalized ROI (xN, yN, wN, hN)
        self._threshold = threshold  # Image match threshold
        self.__templateImage = None  # Loaded template image for matching
        self.__percentFilled = 0.0  # For progress bar
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
    def IsCurrentlyHeld(self) -> bool:
        return self.__isCurrentlyHeld

    @IsCurrentlyHeld.setter
    def IsCurrentlyHeld(self, value: bool):
        self.__isCurrentlyHeld = value

    @property
    def LoopCount(self) -> int:
        return self._loopCount

    @LoopCount.setter
    def LoopCount(self, value: int):
        self._loopCount = value

    @property
    def LoopCounter(self) -> int:
        return self.__loopCounter

    @LoopCounter.setter
    def LoopCounter(self, value: int):
        self.__loopCounter = value

    @property
    def IntervalMs(self) -> int:
        return self._intervalMs

    @IntervalMs.setter
    def IntervalMs(self, value: int):
        self._intervalMs = value

    @property
    def TimeOfLastTriggerMs(self) -> float:
        return self.__timeOfLastTriggerMs

    @TimeOfLastTriggerMs.setter
    def TimeOfLastTriggerMs(self, value: float):
        self.__timeOfLastTriggerMs = value

    @property
    def Roi(self) -> RectangleRegion:
        return self._roi
    
    @Roi.setter
    def Roi(self, value: RectangleRegion):
        self._roi = value

    @property
    def TemplateImage(self) -> np.ndarray:
        return self.__templateImage

    @TemplateImage.setter
    def TemplateImage(self, value: np.ndarray):
        self.__templateImage = value

    @property
    def Threshold(self) -> float:
        return self._threshold

    @Threshold.setter
    def Threshold(self, value: float):
        self._threshold = value

    @property
    def PercentFilled(self) -> float:
        return self.__percentFilled

    @PercentFilled.setter
    def PercentFilled(self, value: float):
        self.__percentFilled = value

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
    EventDisabled = Signal(EventItem)

    def __init__(self, viewModel, pollIntervalMs=50):
        super().__init__()
        self._viewModel = viewModel
        self._pollIntervalMs = pollIntervalMs
        self._isRunning = True

        # New additions for image injection
        self._image_mutex = QMutex()
        self._current_img = None

    def SetImage(self, img):
        """Called by the Capture Thread to provide a new frame"""
        with QMutexLocker(self._image_mutex):
            self._current_img = img

    def run(self):
        while self._isRunning:
            with QMutexLocker(self._image_mutex):
                local_img = self._current_img
                self._current_img = None

            for event in self._viewModel.EventItems:
                if not event.Enabled:
                    continue

                if event.SelectedActivationType == EventItem.ActivationType.Hotkey:
                    if len(event.ActivationVkList) == 0:
                        continue
                    isDownNow = IsHotkeyActive(event.ActivationVkList)
                    if event.IsCurrentlyHeld and not isDownNow:
                        self.EventTriggered.emit(event)
                    event.IsCurrentlyHeld = isDownNow
                elif event.SelectedActivationType == EventItem.ActivationType.Loop:
                    if event.LoopCount < 0:
                        continue
                    elif event.LoopCount > 0:
                        if event.LoopCounter >= event.LoopCount:
                            event.Enabled = False
                            self.EventDisabled.emit(event)
                    else: # LoopCount == 0 means infinite
                        pass

                    if time.time() * 1000 - event.TimeOfLastTriggerMs < event.IntervalMs:
                        continue

                    event.LoopCounter += 1
                    event.TimeOfLastTriggerMs = time.time()*1000
                    self.EventTriggered.emit(event)
                
                elif event.SelectedActivationType == EventItem.ActivationType.ImageMatchRoi:
                    if local_img is None or event.TemplateImage is None:
                        continue
                    
                    cropImage(local_img, (event.Roi.XN, event.Roi.YN, event.Roi.WN, event.Roi.HN))
                    matchScore = matchTemplate(local_img, event.TemplateImage)
                    if matchScore >= event.Threshold:
                        self.EventTriggered.emit(event)

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
        self._imageCount = 0

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
    EventDisabled = Signal(int) # Index of changed event

    def __init__(self):
        super().__init__()
        self.EventItems: List[EventItem] = []
        self.CurrentHwnd = None
        self.LiveThread: Optional[LiveCaptureThread] = None
        self.LastLiveImg = None
        self.TriggerThread = None

        self.StartSentinel()

    def AddNewEvent(self):
        newAction = ActionItem()
        newEvent = EventItem(name="New Event", action=newAction)
        
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
            self.LiveThread.ImageCaptured.connect(self.TriggerThread.SetImage)
            self.LiveThread.start()
        else:
            self.StopCapture()

    def _HandleImageCaptured(self, img):
        self.LastLiveImg = img
        self.CaptureImageReady.emit(img)

    def StopCapture(self):
        if self.LiveThread:
            # 1. Stop the loop
            self.LiveThread.Stop()
            
            # 2. Break all connections immediately 
            # This prevents the thread from sending any more images to 
            # _HandleImageCaptured or TriggerThread while it's closing.
            try:
                self.LiveThread.ImageCaptured.disconnect()
            except RuntimeError:
                # If the thread object is already partially deleted, 
                # disconnect might throw an error; we catch it to prevent a crash.
                pass

            # 3. Wait for the hardware/OS resources to be released
            self.LiveThread.wait()
            self.LiveThread = None
            
    def StartSentinel(self):
        if not self.TriggerThread:
            self.TriggerThread = TriggerMonitorThread(self)
            self.TriggerThread.EventTriggered.connect(self._OnEventTriggered)
            self.TriggerThread.EventDisabled.connect(self._OnEventDisabled)
            self.TriggerThread.start()

    def _OnEventTriggered(self, event: EventItem):
        print(f"Event Triggered: {event.Name}")
        if self.CurrentHwnd:
            event.Trigger(self.CurrentHwnd)

    def _OnEventDisabled(self, event: EventItem):
        print(f"Event Disabled: {event.Name}")
        self.EventDisabled.emit(self.EventItems.index(event))

    def SaveState(self, filePath: str):
        """Serializes the EventItems list to a binary file using Pickle."""
        try:
            # Pickle can save the list of objects directly. 
            # No need for ToDictionary() or manual Enum/Array handling.
            with open(filePath, 'wb') as f:
                pickle.dump(self.EventItems, f)
            print(f"State successfully saved to {filePath}")
        except Exception as e:
            print(f"SaveState Error: {e}")

    def LoadState(self, filePath: str):
        """Deserializes the EventItems list from a binary file."""
        if not os.path.exists(filePath):
            return

        try:
            with open(filePath, 'rb') as f:
                # Pickle reconstructs the entire object tree perfectly
                loadedItems = pickle.load(f)

            self.EventItems.clear()
            
            # We extend the list with the loaded objects
            for event in loadedItems:
                self.EventItems.append(event)
                
                # Emit signal if applicable
                if hasattr(self, 'EventAdded'):
                    self.EventAdded.emit(event)
                    
            print(f"State successfully loaded from {filePath}")
        except Exception as e:
            print(f"LoadState Error: {e}")

    def EnableEvent(self, event: EventItem):
        event.Enabled = True
        event.LoopCounter = 0

    def DisableEvent(self, event: EventItem):
        event.Enabled = False

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

class CropperWidget(QWidget):
    """A PySide ROI selector that mimics the behavior of the Tkinter version."""
    def __init__(self, image_data, on_crop):
        super().__init__()
        self.on_crop = on_crop
        self.setMinimumSize(800, 600) # Give it a starting minimum size
        
        # 1. Setup Layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # 2. Setup Label
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # This is critical: allows the label to shrink smaller than the image
        self.image_label.setMinimumSize(1, 1) 
        
        # 3. Store the Original Pixmap
        if isinstance(image_data, np.ndarray):
            self.original_pixmap = self._ndarray_to_qpixmap(image_data)
        else:
            self.original_pixmap = QPixmap(image_data)
            
        self.layout.addWidget(self.image_label)
        self.showMaximized()

        self.rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self.image_label)
        self.origin = QPoint()

    def resizeEvent(self, event):
        """This triggers every time the window is stretched."""
        if not self.original_pixmap.isNull():
            # Scale the original image to fit the current label size
            scaled_pixmap = self.original_pixmap.scaled(
                self.image_label.size(), 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_label.setPixmap(scaled_pixmap)
        super().resizeEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.origin = event.position().toPoint()
            self.rubber_band.setGeometry(QRect(self.origin, QSize()))
            self.rubber_band.show()

    def mouseMoveEvent(self, event):
        if not self.origin.isNull():
            # Update selection rectangle dynamically
            self.rubber_band.setGeometry(QRect(self.origin, event.position().toPoint()).normalized())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # 1. Get the geometry of the rubber band (Screen Space)
            selectionRect = self.rubber_band.geometry()
            
            # 2. Calculate the scaling ratio
            shownPixmapSize = self.image_label.pixmap().size()
            fullPixmapSize = self.original_pixmap.size()
            
            fullWidth = fullPixmapSize.width()
            fullHeight = fullPixmapSize.height()
            
            ratioX = fullWidth / shownPixmapSize.width()
            ratioY = fullHeight / shownPixmapSize.height()
            
            # 3. Calculate the actual crop area on the ORIGINAL image
            offsetX = (self.image_label.width() - shownPixmapSize.width()) / 2
            offsetY = (self.image_label.height() - shownPixmapSize.height()) / 2
            
            realX = int((selectionRect.x() - offsetX) * ratioX)
            realY = int((selectionRect.y() - offsetY) * ratioY)
            realW = int(selectionRect.width() * ratioX)
            realH = int(selectionRect.height() * ratioY)
            
            realRect = QRect(realX, realY, realW, realH)

            # --- Normalized Coordinates ---
            normX = float(realX) / float(fullWidth)
            normY = float(realY) / float(fullHeight)
            normW = float(realW) / float(fullWidth)
            normH = float(realH) / float(fullHeight)
            
            # 4. Crop from the high-res original
            croppedPixmap = self.original_pixmap.copy(realRect)
            cvImage = self._qpixmap_to_ndarray(croppedPixmap)
            
            # Passing normalized values to the callback
            self.on_crop(cvImage, normX, normY, normW, normH)
            self.close()

    def _qpixmap_to_ndarray(self, pixmap):
        """Converts QPixmap to NumPy, handling row padding (stride)."""
        # 1. Convert to a reliable format
        image = pixmap.toImage().convertToFormat(QImage.Format.Format_RGB888)
        
        width = image.width()
        height = image.height()
        bytes_per_line = image.bytesPerLine() # This is the "772" in your case
        
        # 2. Get the memoryview
        ptr = image.bits()
        
        # 3. Create a 1D array first
        arr = np.frombuffer(ptr, np.uint8)
        
        # 4. Reshape to (Height, BytesPerLine) to include padding
        # This matches the 169068 size perfectly
        arr = arr.reshape((height, bytes_per_line))
        
        # 5. Crop out the padding
        # We only want the first (width * 3) bytes of every row
        actual_data_width = width * 3
        arr = arr[:, :actual_data_width]
        
        # 6. Final reshape to (Height, Width, Channels)
        arr = arr.reshape((height, width, 3))
        
        # 7. Convert RGB to BGR and return a safe copy
        return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR).copy()

    def _ndarray_to_qpixmap(self, cv_img):
        """Converts an OpenCV BGR array to a QPixmap."""
        height, width, channel = cv_img.shape
        bytes_per_line = 3 * width
        
        # Convert BGR to RGB
        cv_rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        
        # Create QImage
        q_img = QImage(cv_rgb.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
        
        # Important: QImage uses the underlying buffer of the ndarray. 
        # We must return a copy as a Pixmap to avoid memory access issues.
        return QPixmap.fromImage(q_img)

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
        self.BtnSaveEvent = QPushButton("Save")
        self.BtnLoadEvent = QPushButton("Load")
        self.BtnSaveEvent.setFixedWidth(40)
        self.BtnLoadEvent.setFixedWidth(40)
        btnLayout.addWidget(self.BtnAddEvent)
        btnLayout.addWidget(self.BtnDelEvent)
        btnLayout.addStretch()
        btnLayout.addWidget(self.BtnSaveEvent)
        btnLayout.addWidget(self.BtnLoadEvent)

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

        # hotkey capture widget
        self.ActivationHotkeyWidget = QWidget()
        self.ActivationHotkeyLayout = QHBoxLayout()
        self.ActivationHotkeyLayout.addWidget(QLabel("Hotkey:"))
        self.ActivationHotkeyEdit = QLineEdit()
        self.ActivationHotkeyEdit.setReadOnly(True)
        self.ActivationHotkeyLayout.addWidget(self.ActivationHotkeyEdit)
        self.ActivationHotkeyBtn = QPushButton("Capture")
        self.ActivationHotkeyLayout.addWidget(self.ActivationHotkeyBtn)
        self.ActivationHotkeyBtn.setEnabled(False)
        self.ActivationHotkeyWidget.setLayout(self.ActivationHotkeyLayout)
        self.ActivationHotkeyWidget.hide()

        # loop and interval widgets can be added here similarly if needed
        self.LoopWidget = QWidget()
        self.LoopWidgetLayout = QHBoxLayout()
        self.LoopCountLayout = QVBoxLayout()
        self.LoopCountLabel = QLabel("Count:")
        self.LoopCountEdit = QLineEdit("1")
        self.LoopIntervalLayout = QVBoxLayout()
        self.LoopIntervalLabel = QLabel("Interval (ms):")
        self.LoopIntervalEdit = QLineEdit("1000")
        self.LoopCountLayout.addWidget(self.LoopCountLabel)
        self.LoopCountLayout.addWidget(self.LoopCountEdit)
        self.LoopIntervalLayout.addWidget(self.LoopIntervalLabel)
        self.LoopIntervalLayout.addWidget(self.LoopIntervalEdit)
        self.LoopWidgetLayout.addLayout(self.LoopCountLayout)
        self.LoopWidgetLayout.addLayout(self.LoopIntervalLayout)
        self.LoopWidget.setLayout(self.LoopWidgetLayout)
        
        self.LoopCountEdit.setEnabled(False)
        self.LoopIntervalEdit.setEnabled(False)
        self.LoopWidget.hide()

        # Roi widget
        self.RoiWidget = QWidget()
        self.RoiWidgetLayout = QHBoxLayout()
        self.RoiWidgetLayoutInner = QVBoxLayout()
        self.RoiXEditLayout = QHBoxLayout()
        self.RoiYEditLayout = QHBoxLayout()
        self.RoiWEditLayout = QHBoxLayout()
        self.RoiHEditLayout = QHBoxLayout()
        self.RoiXEdit = QLineEdit("0.0")
        self.RoiYEdit = QLineEdit("0.0")
        self.RoiWEdit = QLineEdit("1.0")
        self.RoiHEdit = QLineEdit("1.0")
        self.RoiXEditLayout.addWidget(QLabel("X:"))
        self.RoiXEditLayout.addWidget(self.RoiXEdit)
        self.RoiYEditLayout.addWidget(QLabel("Y:"))
        self.RoiYEditLayout.addWidget(self.RoiYEdit)
        self.RoiWEditLayout.addWidget(QLabel("W:"))
        self.RoiWEditLayout.addWidget(self.RoiWEdit)
        self.RoiHEditLayout.addWidget(QLabel("H:"))
        self.RoiHEditLayout.addWidget(self.RoiHEdit)
        self.RoiWidgetLayoutInner.addWidget(QLabel("Roi:"))
        self.RoiWidgetLayoutInner.addLayout(self.RoiXEditLayout)
        self.RoiWidgetLayoutInner.addLayout(self.RoiYEditLayout)
        self.RoiWidgetLayoutInner.addLayout(self.RoiWEditLayout)
        self.RoiWidgetLayoutInner.addLayout(self.RoiHEditLayout)
        self.RoiWidgetLayout.addLayout(self.RoiWidgetLayoutInner)

        self.RoiButtonLayout = QVBoxLayout()
        self.RoiButtonLayout.setContentsMargins(0, 0, 0, 0)
        self.RoiButton = QPushButton("Select from Image")
        self.RoiButton.setFixedSize(150,150)
        self.RoiButtonLayout.addWidget(self.RoiButton)
        self.RoiWidgetLayout.addLayout(self.RoiButtonLayout)
        self.RoiButton.setEnabled(False)

        self.RoiWidget.setLayout(self.RoiWidgetLayout)
        self.RoiXEdit.setReadOnly(True)
        self.RoiYEdit.setReadOnly(True)
        self.RoiWEdit.setReadOnly(True)
        self.RoiHEdit.setReadOnly(True)
        self.RoiWidget.hide()

        # Threshold widget
        self.ThresholdWidget = QWidget()
        self.ThresholdWidgetLayout = QHBoxLayout()
        self.ThresholdWidgetLayout.addWidget(QLabel("Threshold:"))
        self.ThresholdEdit = QLineEdit("0.9")
        self.ThresholdWidgetLayout.addWidget(self.ThresholdEdit)
        self.ThresholdWidget.setLayout(self.ThresholdWidgetLayout)
        self.ThresholdEdit.setEnabled(False)
        self.ThresholdWidget.hide()

        # Action Sequence Properties
        self.ActionNameLabel = QLabel("<b>Action Sequence</b>")

        # The actual list of MacroSteps
        self.MacroStepListWidgetLayout = QHBoxLayout()
        self.MacroStepListWidget = QListWidget()
        self.MacroStepListWidget.setMinimumHeight(200)

        self.BtnMoveLayout = QVBoxLayout()
        self.BtnMoveUp = QPushButton("↑")
        self.BtnMoveDown = QPushButton("↓")
        self.BtnMoveUp.setFixedWidth(30)
        self.BtnMoveDown.setFixedWidth(30)
        self.BtnMoveUp.setEnabled(False)
        self.BtnMoveDown.setEnabled(False)

        self.MacroStepListWidgetLayout.addWidget(self.MacroStepListWidget)
        self.BtnMoveLayout.addWidget(self.BtnMoveUp)
        self.BtnMoveLayout.addWidget(self.BtnMoveDown)
        self.MacroStepListWidgetLayout.addLayout(self.BtnMoveLayout)
        
        self.stepDropDown = QComboBox()
        self.stepDropDown.addItems([mt.name for mt in MacroStep.InputType])
        self.stepDropDown.setEnabled(False)
        
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
        layout.addWidget(self.ActivationHotkeyWidget)
        layout.addWidget(self.LoopWidget)
        layout.addWidget(self.RoiWidget)
        layout.addWidget(self.ThresholdWidget)
        
        layout.addWidget(self.CreateHorizontalLine()) # Optional visual separator
        
        layout.addWidget(self.ActionNameLabel)
        layout.addLayout(self.MacroStepListWidgetLayout)
        layout.addWidget(self.stepDropDown)
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
        
        self.BtnSaveEvent.clicked.connect(self.OnSaveEvent)
        self.BtnLoadEvent.clicked.connect(self.OnLoadEvent)
        self.BtnFindHwnd.clicked.connect(lambda: self.ViewModel.FindWindow(self.TitleEdit.text().strip()))
        self.BtnBrowse.clicked.connect(self.OnBrowseExecutable)
        self.BtnLaunch.clicked.connect(self.OnLaunchExecutable)
        self.BtnResize.clicked.connect(self.OnResizeRequested)
        self.BtnLiveCapture.toggled.connect(self.OnToggleCapture)
        self.BtnMoveUp.clicked.connect(lambda: self.MoveStep(-1))
        self.BtnMoveDown.clicked.connect(lambda: self.MoveStep(1))
        self.BtnAddStep.clicked.connect(self.OnAddStepClicked)
        self.BtnDelStep.clicked.connect(self.OnRemoveStepClicked)
        self.ActivationHotkeyBtn.clicked.connect(self.OnCaptureHotkey)
        self.RoiButton.clicked.connect(self.OnSelectRoi)
        
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
        self.LoopCountEdit.editingFinished.connect(self.OnCommitLoopCount)
        self.LoopIntervalEdit.editingFinished.connect(self.OnCommitLoopInterval)
        self.ThresholdEdit.editingFinished.connect(self.OnCommitThreshold)

        # --- ViewModel to View ---
        self.ViewModel.EventAdded.connect(self.UpdateUiAddEvent)
        self.ViewModel.EventRemoved.connect(self.UpdateUiRemoveEvent)
        self.ViewModel.HwndUpdated.connect(self.UpdateUiHwndInfo)
        self.ViewModel.CaptureImageReady.connect(self.UpdateUiImage)
        self.ViewModel.EventDisabled.connect(self.UpdateUiEventDisabled)

    # --- Interaction Handlers ---
    def OnSaveEvent(self):
        # Updated filter to show Data/Pickle files instead of JSON
        filePath, _ = QFileDialog.getSaveFileName(
            self, 
            "Save Macro Configuration", 
            "", 
            "Data Files (*.dat);;Pickle Files (*.pkl);;All Files (*)"
        )
        
        if filePath:
            try:
                # ViewModel.SaveState now handles binary Pickle serialization
                self.ViewModel.SaveState(filePath)
                QMessageBox.information(self, "Success", "Configuration saved successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save file: {e}")

    def OnLoadEvent(self):
        # Updated filter to look for binary files
        filePath, _ = QFileDialog.getOpenFileName(
            self, 
            "Load Macro Configuration", 
            "", 
            "Data Files (*.dat);;Pickle Files (*.pkl);;All Files (*)"
        )
        
        if filePath:
            try:
                # Clear existing UI list before loading new data
                self.EventListWidget.clear()
                self.MacroStepListWidget.clear()
                
                # ViewModel.LoadState now handles binary Pickle deserialization
                self.ViewModel.LoadState(filePath)
                QMessageBox.information(self, "Success", "Configuration loaded successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load file: {e}")

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
                stepTypeName = self.stepDropDown.currentText()
                if stepTypeName in MacroStep.InputType.__members__:
                    stepType = MacroStep.InputType[stepTypeName]
                    # Create a default step based on type
                    if stepType == MacroStep.InputType.Mouse:
                        nx, ny = float(self.MouseXEdit.text()), float(self.MouseYEdit.text())
                        newStep = MacroStep(MacroStep.InputType.Mouse, (nx, ny), f"Click at ({nx:7f}, {ny:7f})")
                    elif stepType == MacroStep.InputType.Keyboard:
                        dialog = HotkeyCaptureDialog(self)
                        if dialog.exec() == QDialog.Accepted:
                            # We take the first key from the captured list
                            if dialog.CapturedVks:
                                vk = dialog.CapturedVks[0]
                                newStep = MacroStep(MacroStep.InputType.Keyboard, vk, f"Press \"{KeyNameFromVk(vk)}\"")
                    elif stepType == MacroStep.InputType.Delay:
                        ms, ok = QInputDialog.getInt(self, "Add Delay", "Milliseconds (ms):", 100, 1, 60000, 10)
                        if ok:
                            newStep = MacroStep(MacroStep.InputType.Delay, ms, f"Wait {ms}ms")
                    else:
                        return
                    
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

    def OnSelectRoi(self):
        if self.ViewModel.LastLiveImg is None:
            # Handle the case where there is no image
            QMessageBox.warning(self, "Error", "Please start the capture before selecting an ROI.")
            return
        self.cropper = CropperWidget(self.ViewModel.LastLiveImg, self.handleNewCrop)
        self.cropper.show()

    def handleNewCrop(self, cv_img, normX, normY, normW, normH):
        # set model
        item = self.EventListWidget.currentItem()
        if item:
            eventObj: EventItem = item.data(Qt.UserRole)
            eventObj.TemplateImage = cv_img
            eventObj.Roi = RectangleRegion(normX, normY, normW, normH)
        
        # set view
        self.setButtonWithImage(self.RoiButton, cv_img)

        self.RoiXEdit.setText(f"{normX:.4f}")
        self.RoiYEdit.setText(f"{normY:.4f}")
        self.RoiWEdit.setText(f"{normW:.4f}")
        self.RoiHEdit.setText(f"{normH:.4f}")

    def setButtonWithImage(self, button, cv_img):
        if cv_img is None:
            return
        height, width, channel = cv_img.shape
        bytesPerLine = 3 * width
        cv_rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        q_img = QImage(cv_rgb.data, width, height, bytesPerLine, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(q_img)
        icon = QIcon(pixmap)
        button.setIcon(icon)
        button.setIconSize(button.size())
        button.setText("")

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
            self.LoopCountEdit.setEnabled(False)
            self.LoopIntervalEdit.setEnabled(False)
            self.stepDropDown.setEnabled(False)
            self.BtnAddStep.setEnabled(False)
            self.BtnDelStep.setEnabled(False)
            self.BtnMoveUp.setEnabled(False)
            self.BtnMoveDown.setEnabled(False)
            self.ThresholdEdit.setEnabled(False)
            self.RoiButton.setEnabled(False)
            return

        eventObj: EventItem = current.data(Qt.UserRole)
        
        self.EventNameEdit.setText(eventObj.Name)
        self.EventNameEdit.setEnabled(True)

        activation = eventObj.SelectedActivationType
        typeName = activation.name if hasattr(activation, 'name') else str(activation)

        idx = self.ActivationDropdown.findText(typeName)
        if idx >= 0:
            self.ActivationDropdown.setCurrentIndex(idx)
        self.ActivationDropdown.setCurrentIndex(idx)
        self.ActivationDropdown.setEnabled(True)

        self.ActivationHotkeyEdit.setText(", ".join(map(KeyNameFromVk, eventObj.ActivationVkList)))
        self.ActivationHotkeyBtn.setEnabled(True)

        self.LoopCountEdit.setText(str(eventObj.LoopCount))
        self.LoopIntervalEdit.setText(str(eventObj.IntervalMs))
        self.LoopCountEdit.setEnabled(True)
        self.LoopIntervalEdit.setEnabled(True)

        self.RoiXEdit.setText(f"{eventObj.Roi.XN:.4f}")
        self.RoiYEdit.setText(f"{eventObj.Roi.YN:.4f}")
        self.RoiWEdit.setText(f"{eventObj.Roi.WN:.4f}")
        self.RoiHEdit.setText(f"{eventObj.Roi.HN:.4f}")        
        self.setButtonWithImage(self.RoiButton, eventObj.TemplateImage)
        self.RoiButton.setEnabled(True)

        self.ThresholdEdit.setText(f"{eventObj.Threshold:.2f}")
        self.ThresholdEdit.setEnabled(True)

        self.RefreshMacroStepList(eventObj.AssignedAction)
        self.stepDropDown.setEnabled(True)
        self.BtnAddStep.setEnabled(True)
        self.BtnDelStep.setEnabled(True)
        self.BtnMoveUp.setEnabled(True)
        self.BtnMoveDown.setEnabled(True)
        
    def OnEventItemChanged(self, item: QListWidgetItem):
        """Triggered when an item is renamed or check state changes."""
        # ui
        eventObj: EventItem = item.data(Qt.UserRole)
        if not eventObj:
            return
        
        # model
        if item.checkState() == Qt.Checked:
            self.ViewModel.EnableEvent(eventObj)
        else:
            self.ViewModel.DisableEvent(eventObj)
            
    def RefreshMacroStepList(self, actionObj: ActionItem):
        """Refreshes the UI list based on the ActionItem's steps."""
        self.MacroStepListWidget.clear()
        for step in actionObj.MacroSteps:
            # Check if it's a dict (raw data) or an object
            description = ""
            if isinstance(step, dict):
                description = step.get("Description", "Unknown Step")
            else:
                description = step.Description
                
            item = QListWidgetItem(description)
            item.setData(Qt.UserRole, step) # Store the step data/object
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

            if eventObj.SelectedActivationType == EventItem.ActivationType.Hotkey:
                self.ActivationHotkeyWidget.show()
            else:
                self.ActivationHotkeyWidget.hide()

            if eventObj.SelectedActivationType == EventItem.ActivationType.Loop:
                self.LoopWidget.show()
            else:
                self.LoopWidget.hide()

            if eventObj.SelectedActivationType == EventItem.ActivationType.ImageMatchRoi:
                self.RoiWidget.show()
                self.ThresholdWidget.show()
            elif eventObj.SelectedActivationType == EventItem.ActivationType.ProgessBar:
                self.RoiWidget.show()
                self.ThresholdWidget.hide()
            else:
                self.RoiWidget.hide()
                self.ThresholdWidget.hide()

    def OnCommitLoopCount(self):
        item = self.EventListWidget.currentItem()
        if item:
            eventObj: EventItem = item.data(Qt.UserRole)
            try:
                count = int(self.LoopCountEdit.text())
                eventObj.LoopCount = count
            except ValueError:
                QMessageBox.warning(self, "Error", "Invalid loop count.")

    def OnCommitLoopInterval(self):
        item = self.EventListWidget.currentItem()
        if item:
            eventObj: EventItem = item.data(Qt.UserRole)
            try:
                interval = int(self.LoopIntervalEdit.text())
                eventObj.IntervalMs = interval
            except ValueError:
                QMessageBox.warning(self, "Error", "Invalid interval.")

    def OnCommitThreshold(self):
        item = self.EventListWidget.currentItem()
        if item:
            eventObj: EventItem = item.data(Qt.UserRole)
            try:
                threshold = float(self.ThresholdEdit.text())
                eventObj.Threshold = threshold
            except ValueError:
                QMessageBox.warning(self, "Error", "Invalid threshold.")

    def MoveStep(self, direction: int):
        """direction: -1 for Up, 1 for Down"""
        # 1. Get current selection
        currentRow = self.MacroStepListWidget.currentRow()
        if currentRow == -1: return
        
        # 2. Calculate target row and check boundaries
        targetRow = currentRow + direction
        if targetRow < 0 or targetRow >= self.MacroStepListWidget.count():
            return

        # 3. Get the Action object from the selected Event
        eventItem = self.EventListWidget.currentItem()
        if not eventItem: return
        eventObj: EventItem = eventItem.data(Qt.UserRole)
        steps = eventObj.AssignedAction.MacroSteps

        # 4. Swap in the Python List (The Data Model)
        steps[currentRow], steps[targetRow] = steps[targetRow], steps[currentRow]

        # 5. Swap in the UI (The View)
        # We take the item out and re-insert it at the new position
        item = self.MacroStepListWidget.takeItem(currentRow)
        self.MacroStepListWidget.insertItem(targetRow, item)
        
        # 6. Keep the moved item selected so the user can click multiple times
        self.MacroStepListWidget.setCurrentRow(targetRow)

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

    def UpdateUiEventDisabled(self, index: int):
        item = self.EventListWidget.item(index)
        if item:
            eventObj: EventItem = item.data(Qt.UserRole)
            # Update the check state to reflect Enabled status
            item.setCheckState(Qt.Checked if eventObj.Enabled else Qt.Unchecked)

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