"""
SentinelFlow Main Dashboard
Description: PySide6 GUI for live capture, launcher, and window management.
"""

# -------------------------
# Standard library imports
# -------------------------
import os
import sys
import time

# -------------------------
# Third-party imports
# -------------------------
from PySide6.QtCore import Signal, QThread

# -------------------------
# Environment / Qt settings
# -------------------------
# Ensure high DPI scaling and automatic scaling is enabled for Qt applications
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

# -------------------------
# Local helpers (explicit imports for clarity)
# -------------------------
from Src.Helper import (
    capture_window_by_hwnd,
    find_hwnd_by_title,
    launch_hwnd_by_executable,
    crop_image,
    template_match,
    estimate_progress_bar_percentage,
)

# -------------------------
# Live Capture Thread
# -------------------------
class LiveCaptureThread(QThread):
    image_captured = Signal(object)

    def __init__(self, hwnd, interval_ms=200, parent=None):
        super().__init__(parent)
        self.hwnd = hwnd
        self.interval_ms = interval_ms
        self._running = True

    def run(self):
        """Main loop: periodically capture the target window and emit images."""
        self._running = True
        while self._running:
            try:
                img = capture_window_by_hwnd(self.hwnd)
                self.image_captured.emit(img)
            except Exception:
                self.image_captured.emit(None)
            time.sleep(self.interval_ms / 1000.0)

    def stop(self):
        self._running = False
        self.wait()

# Note: environment settings and helper imports are defined above in the imports section.

if __name__ == "__main__": 
    from PySide6.QtWidgets import (
        QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QFileDialog, QProgressBar, QMessageBox, QSizePolicy
    )
    from PySide6.QtCore import Qt, QTimer

    class Dashboard(QWidget):
        """Main application window (dashboard).

        Handles UI layout, user actions, ROI selection, and live capture updates.
        """

        def __init__(self):
            super().__init__()
            # ---- UI Setup ----
            self.setWindowTitle("SentinelFlow Dashboard")
            self.setGeometry(100, 100, 720, 480)

            # Root layout
            root_layout = QHBoxLayout()

            # Left panel
            left_panel = QVBoxLayout()
            self.left_panel_label = QLabel("Left Panel Label")
            self.left_panel_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            left_panel.addWidget(self.left_panel_label)
            left_panel.addStretch()

            # Center panel
            center_panel = QVBoxLayout()
            exe_layout = QHBoxLayout()
            self.exe_path_edit = QLineEdit()
            self.exe_path_edit.setPlaceholderText("Executable path...")
            exe_browse_btn = QPushButton("Browse")
            exe_launch_btn = QPushButton("Launch")
            exe_browse_btn.clicked.connect(self.browse_exe)
            exe_launch_btn.clicked.connect(self.launch_exe)
            exe_layout.addWidget(QLabel("Executable:"))
            exe_layout.addWidget(self.exe_path_edit)
            exe_layout.addWidget(exe_browse_btn)
            exe_layout.addWidget(exe_launch_btn)
            center_panel.addLayout(exe_layout)

            hwnd_layout = QHBoxLayout()
            self.title_edit = QLineEdit()
            self.title_edit.setPlaceholderText("Window title...")
            self.title_edit.setText("Warcraft III")
            hwnd_find_btn = QPushButton("Find HWND")
            hwnd_find_btn.clicked.connect(self.find_hwnd)
            self.hwnd_label = QLabel("HWND: -")
            hwnd_layout.addWidget(QLabel("Window Title:"))
            hwnd_layout.addWidget(self.title_edit)
            hwnd_layout.addWidget(hwnd_find_btn)
            hwnd_layout.addWidget(self.hwnd_label)
            center_panel.addLayout(hwnd_layout)

            live_btn_layout = QHBoxLayout()
            self.live_capture_btn = QPushButton("Start Live Capture")
            self.live_capture_btn.setCheckable(True)
            self.live_capture_btn.toggled.connect(self.toggle_live_capture)
            live_btn_layout.addWidget(self.live_capture_btn)
            live_btn_layout.setAlignment(Qt.AlignVCenter | Qt.AlignHCenter)
            center_panel.addLayout(live_btn_layout)

            self.live_image_label = QLabel()
            self.live_image_label.setAlignment(Qt.AlignVCenter | Qt.AlignHCenter)
            self.live_image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.live_image_label.setScaledContents(True)
            center_panel.addWidget(self.live_image_label)

            # Right panel
            right_panel = QVBoxLayout()
            self.right_panel_btn = QPushButton("Right Panel Button")
            right_panel.addWidget(self.right_panel_btn)
            right_panel.addStretch()

            # Assemble root layout
            root_layout.addLayout(left_panel, stretch=1)
            root_layout.addLayout(center_panel, stretch=4)
            root_layout.addLayout(right_panel, stretch=1)
            self.setLayout(root_layout)

            self.current_hwnd = None
            self.live_thread = None
            self.roi_start = None
            self.roi_end = None
            self.selected_roi = None
            self.live_image_label.installEventFilter(self)

        # ---- ROI / Mouse Handling ----
        def eventFilter(self, obj, event):
            from PySide6.QtCore import QEvent
            if obj is self.live_image_label:
                if event.type() == QEvent.Type.MouseButtonPress:
                    if self.last_live_img is not None:
                        self.roi_start = event.position().toPoint()
                        self.roi_end = self.roi_start
                        self.selected_roi = None
                        self.update_live_image(draw_roi=True)
                elif event.type() == QEvent.Type.MouseMove and self.roi_start is not None:
                    self.roi_end = event.position().toPoint()
                    self.update_live_image(draw_roi=True)
                elif event.type() == QEvent.Type.MouseButtonRelease and self.roi_start is not None:
                    self.roi_end = event.position().toPoint()
                    self.selected_roi = self.get_roi_from_live_label()
                    self.roi_start = None
                    self.roi_end = None
                    self.update_live_image(draw_roi=True)
            return super().eventFilter(obj, event)

        def get_roi_from_live_label(self):
            if self.last_live_img is None or self.roi_start is None or self.roi_end is None:
                return None
            x1, y1 = self.roi_start.x(), self.roi_start.y()
            x2, y2 = self.roi_end.x(), self.roi_end.y()
            x, y = min(x1, x2), min(y1, y2)
            w, h = abs(x2 - x1), abs(y2 - y1)
            if w < 5 or h < 5:
                return None
            label_w = self.live_image_label.width()
            label_h = self.live_image_label.height()
            img = self.last_live_img
            img_h, img_w, _ = img.shape
            scale_x = img_w / label_w
            scale_y = img_h / label_h
            roi_x = int(x * scale_x)
            roi_y = int(y * scale_y)
            roi_w = int(w * scale_x)
            roi_h = int(h * scale_y)
            roi_x = max(0, min(roi_x, img_w-1))
            roi_y = max(0, min(roi_y, img_h-1))
            roi_w = max(1, min(roi_w, img_w - roi_x))
            roi_h = max(1, min(roi_h, img_h - roi_y))
            return (roi_x, roi_y, roi_w, roi_h)

        # ---- Live Capture Controls ----
        def toggle_live_capture(self, checked):
            if checked:
                if not self.current_hwnd:
                    self.live_capture_btn.setChecked(False)
                    QMessageBox.warning(self, "Error", "No HWND selected. Please find a window first.")
                    return
                self.live_capture_btn.setText("Stop Live Capture")
                self.start_live_thread()
            else:
                self.live_capture_btn.setText("Start Live Capture")
                self.stop_live_thread()
                self.live_image_label.clear()

        def start_live_thread(self):
            self.stop_live_thread()
            self.live_thread = LiveCaptureThread(self.current_hwnd, interval_ms=200)
            self.live_thread.image_captured.connect(self.on_live_image_captured)
            self.live_thread.start()

        def stop_live_thread(self):
            if self.live_thread:
                self.live_thread.stop()
                self.live_thread = None

        def on_live_image_captured(self, img):
            self.update_live_image(img=img)

        # ---- Image Rendering & ROI drawing ----
        def update_live_image(self, draw_roi=False, img=None):
            if img is None:
                if not self.current_hwnd:
                    self.live_image_label.clear()
                    self.last_live_img = None
                    return
                try:
                    img = capture_window_by_hwnd(self.current_hwnd)
                except Exception:
                    self.live_image_label.setText("Capture error")
                    self.last_live_img = None
                    return
            self.last_live_img = img
            if img is not None and hasattr(img, 'size') and img.size > 0:
                from PySide6.QtGui import QImage, QPixmap, QPainter, QColor, QPen
                h, w, ch = img.shape
                bytes_per_line = ch * w
                qimg = QImage(img.data, w, h, bytes_per_line, QImage.Format_BGR888)
                pixmap = QPixmap.fromImage(qimg).scaled(
                    self.live_image_label.width(), self.live_image_label.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                if (draw_roi or (self.roi_start and self.roi_end)) and self.roi_start and self.roi_end:
                    painter = QPainter(pixmap)
                    pen = QPen(QColor(255, 0, 0), 2, Qt.DashLine)
                    painter.setPen(pen)
                    rect_x = min(self.roi_start.x(), self.roi_end.x())
                    rect_y = min(self.roi_start.y(), self.roi_end.y())
                    rect_w = abs(self.roi_end.x() - self.roi_start.x())
                    rect_h = abs(self.roi_end.y() - self.roi_start.y())
                    painter.drawRect(rect_x, rect_y, rect_w, rect_h)
                    painter.end()
                self.live_image_label.setPixmap(pixmap)
            else:
                self.live_image_label.clear()
                self.last_live_img = None

        def closeEvent(self, event):
            self.stop_live_thread()
            super().closeEvent(event)

        def browse_exe(self):
            dialog = QFileDialog(self, "Select Executable", "", "Executables (*.exe)")
            dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
            if dialog.exec() == QFileDialog.Accepted:
                files = dialog.selectedFiles()
                if files:
                    self.exe_path_edit.setText(files[0])

        def launch_exe(self):
            exe_path = self.exe_path_edit.text().strip()
            if not exe_path:
                QMessageBox.warning(self, "Error", "Please select an executable.")
                return
            pid = launch_hwnd_by_executable(exe_path)
            QMessageBox.information(self, "Launched", f"Process launched with PID: {pid}")

        def find_hwnd(self):
            title = self.title_edit.text().strip()
            if not title:
                QMessageBox.warning(self, "Error", "Please enter a window title.")
                return
            hwnd = find_hwnd_by_title(title)
            if hwnd:
                self.hwnd_label.setText(f"HWND: {hwnd}")
                self.current_hwnd = hwnd
            else:
                self.hwnd_label.setText("HWND: -")
                self.current_hwnd = None
                QMessageBox.warning(self, "Not found", "Window not found.")

    app = QApplication(sys.argv)
    dashboard = Dashboard()
    dashboard.show()
    sys.exit(app.exec())
    
