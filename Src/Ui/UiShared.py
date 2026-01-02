from __future__ import annotations

import numpy as np
import cv2
from typing import List, Optional, Final, Callable, Any

from PySide6.QtCore import Qt, QPoint, QRect, QSize, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent, QResizeEvent, QPixmap, QImage, QPaintEvent, QPainter, QPen
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout, QWidget, QRubberBand


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
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Capture Hotkey Combination")
        self.setFixedSize(250, 100)
        self.CapturedVirtualKeyCodes: List[int] = []
        self._currentVirtualKeyCodes: List[int] = []
        self._currentVirtualKeyCodeSet: set[int] = set()
        layout = QVBoxLayout(self)
        self.StatusLabel = QLabel("Holding: 0 keys", alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.StatusLabel)
        self.setModal(True)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        virtualKeyCode = event.nativeVirtualKey()
        if virtualKeyCode > 0:
            if virtualKeyCode not in self._currentVirtualKeyCodeSet:
                self._currentVirtualKeyCodeSet.add(virtualKeyCode)
                self._currentVirtualKeyCodes.append(virtualKeyCode)
            self.StatusLabel.setText(f"Holding: {len(self._currentVirtualKeyCodes)} keys")

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if self._currentVirtualKeyCodes:
            self.CapturedVirtualKeyCodes = list(self._currentVirtualKeyCodes)
            self.accept()


class CropperWidget(QWidget):
    def __init__(
        self,
        imageData: np.ndarray[Any, Any],
        onCrop: Callable[[np.ndarray[Any, Any], float, float, float, float], None]
    ) -> None:
        super().__init__()
        self.onCrop = onCrop
        self.setMinimumSize(640, 480)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.imageLabel = QLabel()
        self.imageLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.imageLabel.setMinimumSize(1, 1)
        self.originalPixmap = self._ndarrayToQPixmap(imageData)
        layout.addWidget(self.imageLabel)
        self.setLayout(layout)
        self.showMaximized()
        self.rubberBand = QRubberBand(QRubberBand.Shape.Rectangle, self.imageLabel)
        self.origin = QPoint()

    def resizeEvent(self, event: QResizeEvent) -> None:
        """
        Handle resize events to scale the image.
        
        Args:
            event: Resize event
        """
        if not self.originalPixmap.isNull():
            # Scale the original image to fit the current label size
            scaledPixmap = self.originalPixmap.scaled(
                self.imageLabel.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.imageLabel.setPixmap(scaledPixmap)
        super().resizeEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """
        Handle mouse press events to start selection.
        
        Args:
            event: Mouse event
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self.origin = event.position().toPoint()
            self.rubberBand.setGeometry(QRect(self.origin, QSize()))
            self.rubberBand.show()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """
        Handle mouse move events to update selection.
        
        Args:
            event: Mouse event
        """
        if not self.origin.isNull():
            # Update selection rectangle dynamically
            self.rubberBand.setGeometry(QRect(self.origin, event.position().toPoint()).normalized())

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """
        Handle mouse release events to complete selection.
        
        Args:
            event: Mouse event
        """
        if event.button() == Qt.MouseButton.LeftButton:
            # 1. Get the geometry of the rubber band (Screen Space)
            selectionRect = self.rubberBand.geometry()
            
            # 2. Calculate the scaling ratio
            shownPixmapSize = self.imageLabel.pixmap().size()
            fullPixmapSize = self.originalPixmap.size()
            fullWidth = fullPixmapSize.width()
            fullHeight = fullPixmapSize.height()
            
            ratioX = fullWidth / shownPixmapSize.width()
            ratioY = fullHeight / shownPixmapSize.height()
            
            # 3. Calculate the actual crop area on the ORIGINAL image
            offsetX = (self.imageLabel.width() - shownPixmapSize.width()) / 2
            offsetY = (self.imageLabel.height() - shownPixmapSize.height()) / 2
            
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
            croppedPixmap = self.originalPixmap.copy(realRect)
            cvImage = self._qpixmapToNdarray(croppedPixmap)
            
            # Passing normalized values to the callback
            self.onCrop(cvImage, normX, normY, normW, normH)
            self.close()

    def _qpixmapToNdarray(self, pixmap: QPixmap) -> np.ndarray[Any, Any]:
        """
        Convert QPixmap to NumPy array.
        
        Args:
            pixmap: QPixmap to convert
            
        Returns:
            NumPy array representation
        """
        # 1. Convert to a reliable format
        image = pixmap.toImage().convertToFormat(QImage.Format.Format_RGB888)
        width = image.width()
        height = image.height()
        bytesPerLine = image.bytesPerLine()  # This is the "772" in your case
        
        # 2. Get the memoryview
        ptr = image.bits()
        
        # 3. Create a 1D array first
        array = np.frombuffer(ptr, np.uint8)
        
        # 4. Reshape to (Height, BytesPerLine) to include padding
        # This matches the 169068 size perfectly
        array = array.reshape((height, bytesPerLine))
        
        # 5. Crop out the padding
        # We only want the first (width * 3) bytes of every row
        actualDataWidth = width * 3
        array = array[:, :actualDataWidth]
        
        # 6. Final reshape to (Height, Width, Channels)
        array = array.reshape((height, width, 3))
        
        # 7. Convert RGB to BGR and return a safe copy
        return cv2.cvtColor(array, cv2.COLOR_RGB2BGR).copy()

    def _ndarrayToQPixmap(self, cvImage: np.ndarray[Any, Any]) -> QPixmap:
        """
        Convert OpenCV BGR array to QPixmap.
        
        Args:
            cvImage: OpenCV BGR array
            
        Returns:
            QPixmap representation
        """
        height, width, _channel = cvImage.shape
        bytesPerLine = 3 * width
        
        # Convert BGR to RGB
        cvRgb = cv2.cvtColor(cvImage, cv2.COLOR_BGR2RGB)
        
        # Create QImage
        qImage = QImage(cvRgb.data, width, height, bytesPerLine, QImage.Format.Format_RGB888)
        
        # Important: QImage uses the underlying buffer of the ndarray.
        # We must return a copy as a Pixmap to avoid memory access issues.
        return QPixmap.fromImage(qImage)




class ClickableImageLabel(QLabel):
    Clicked = Signal(QPoint)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.NormalizedX: Optional[float] = None
        self.NormalizedY: Optional[float] = None
        self.setMouseTracking(True)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """
        Handle mouse press events.
        
        Args:
            event: Mouse event
        """
        if event.button() == Qt.MouseButton.LeftButton:
            width, height = self.width(), self.height()
            if width > 0 and height > 0:
                self.NormalizedX = event.position().x() / width
                self.NormalizedY = event.position().y() / height
                self.Clicked.emit(event.position().toPoint())
                self.update()

    def SetMarkerNormalized(self, normalizedX: float, normalizedY: float) -> None:
        """
        Set the marker position using normalized coordinates.
        
        Args:
            normalizedX: Normalized X coordinate (0.0 to 1.0)
            normalizedY: Normalized Y coordinate (0.0 to 1.0)
        """
        self.NormalizedX = normalizedX
        self.NormalizedY = normalizedY
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        """
        Handle paint events to draw the marker.
        
        Args:
            event: Paint event
        """
        super().paintEvent(event)
        if self.NormalizedX is None or self.NormalizedY is None:
            return
            
        x = int(self.NormalizedX * self.width())
        y = int(self.NormalizedY * self.height())
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(Qt.GlobalColor.red, 2))
        
        size = 10
        painter.drawLine(x - size, y, x + size, y)
        painter.drawLine(x, y - size, x, y + size)

