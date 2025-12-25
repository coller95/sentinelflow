# --- DPI/COM Fix for PySide6 ---
import os
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
# --- Imports ---
from Helper import *




if __name__ == "__main__":
    # PySide6 dashboard with launcher, hwnd finder, and progress bar capture
    import sys
    from PySide6.QtWidgets import (
        QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QFileDialog, QProgressBar, QMessageBox
    )
    from PySide6.QtCore import Qt, QTimer

    class Dashboard(QWidget):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("SentinelFlow Dashboard")
            self.setGeometry(100, 100, 500, 300)

            layout = QVBoxLayout()

            # Executable launcher
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
            layout.addLayout(exe_layout)

            # Window title finder
            hwnd_layout = QHBoxLayout()
            self.title_edit = QLineEdit()
            self.title_edit.setPlaceholderText("Window title...")
            self.title_edit.setText("Warcraft III")  # Default title for convenience
            hwnd_find_btn = QPushButton("Find HWND")
            hwnd_find_btn.clicked.connect(self.find_hwnd)
            self.hwnd_label = QLabel("HWND: -")
            hwnd_layout.addWidget(QLabel("Window Title:"))
            hwnd_layout.addWidget(self.title_edit)
            hwnd_layout.addWidget(hwnd_find_btn)
            hwnd_layout.addWidget(self.hwnd_label)
            layout.addLayout(hwnd_layout)

            # Progress bar capture
            bar_layout = QHBoxLayout()
            self.capture_btn = QPushButton("Capture Progress Bar")
            self.capture_btn.clicked.connect(self.capture_progress_bar)
            self.progress_label = QLabel("Progress: - %")
            bar_layout.addWidget(self.capture_btn)
            bar_layout.addWidget(self.progress_label)
            layout.addLayout(bar_layout)

            # Optionally, show a QProgressBar (visual only)
            self.qprogress = QProgressBar()
            self.qprogress.setRange(0, 100)
            layout.addWidget(self.qprogress)


            # Live preview label for the progress bar ROI
            self.live_bar_label = QLabel()
            self.live_bar_label.setFixedHeight(40)
            layout.addWidget(self.live_bar_label)

            self.setLayout(layout)

            self.current_hwnd = None

            # Timer for periodic progress bar capture
            self.capture_timer = QTimer(self)
            self.capture_timer.setInterval(500)  # 0.5 seconds
            self.capture_timer.timeout.connect(self.auto_update_progress)
            self.auto_roi = None

        def start_auto_capture(self, roi):
            self.auto_roi = roi
            self.capture_timer.start()

        def stop_auto_capture(self):
            self.capture_timer.stop()
            self.auto_roi = None

        def auto_update_progress(self):
            if not self.current_hwnd or not self.auto_roi:
                return
            try:
                img = capture_window_by_hwnd(self.current_hwnd)
                bar_img = crop_image(img, self.auto_roi)
                percent = estimate_progress_bar_percentage(bar_img)
                self.progress_label.setText(f"Progress: {percent:.1f} %")
                self.qprogress.setValue(int(percent))
                # Show live preview of the ROI
                self.update_live_bar_preview(bar_img)
            except Exception as e:
                self.progress_label.setText("Progress: error")

        def update_live_bar_preview(self, bar_img):
            from PySide6.QtGui import QImage, QPixmap
            if bar_img is not None and bar_img.size > 0:
                h, w, ch = bar_img.shape
                bytes_per_line = ch * w
                qimg = QImage(bar_img.data, w, h, bytes_per_line, QImage.Format_BGR888)
                pixmap = QPixmap.fromImage(qimg).scaled(self.live_bar_label.width(), self.live_bar_label.height(), Qt.KeepAspectRatio)
                self.live_bar_label.setPixmap(pixmap)
            else:
                self.live_bar_label.clear()

        def browse_exe(self):
            # Use non-native dialog to avoid Windows COM/threading issues
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

        def capture_progress_bar(self):
            if not self.current_hwnd:
                QMessageBox.warning(self, "Error", "No HWND selected.")
                return
            try:
                img = capture_window_by_hwnd(self.current_hwnd)
                roi = self.get_roi_from_user(img)
                if roi is None:
                    return
                # Start periodic capture with selected ROI
                self.start_auto_capture(roi)
            except Exception as e:
                QMessageBox.critical(self, "Capture Error", str(e))

        def get_roi_from_user(self, img):
            from PySide6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QLabel
            from PySide6.QtGui import QPixmap, QImage, QPainter, QColor, QPen
            from PySide6.QtCore import Qt, QRect
            import numpy as np

            class ROIDialog(QDialog):
                def __init__(self, img, parent=None):
                    super().__init__(parent)
                    self.setWindowTitle("Draw ROI on Screenshot")
                    self.img = img
                    h, w, ch = img.shape
                    bytes_per_line = ch * w
                    qimg = QImage(img.data, w, h, bytes_per_line, QImage.Format_BGR888)
                    self.pixmap = QPixmap.fromImage(qimg)
                    self.label = QLabel()
                    self.label.setPixmap(self.pixmap)
                    self.label.setFixedSize(w, h)
                    self.start = None
                    self.end = None
                    self.rect = None
                    self.drawing = False
                    self.setFixedSize(w, h+40)
                    layout = QVBoxLayout()
                    layout.addWidget(self.label)
                    ok_btn = QPushButton("OK")
                    ok_btn.clicked.connect(self.accept)
                    layout.addWidget(ok_btn)
                    self.setLayout(layout)
                    self.label.installEventFilter(self)

                def eventFilter(self, obj, event):
                    from PySide6.QtCore import QEvent
                    if obj is self.label:
                        if event.type() == QEvent.Type.MouseButtonPress:
                            self.start = event.position().toPoint()
                            self.end = self.start
                            self.drawing = True
                            self.update_pixmap()
                        elif event.type() == QEvent.Type.MouseMove and self.drawing:
                            self.end = event.position().toPoint()
                            self.update_pixmap()
                        elif event.type() == QEvent.Type.MouseButtonRelease and self.drawing:
                            self.end = event.position().toPoint()
                            self.drawing = False
                            self.update_pixmap()
                    return super().eventFilter(obj, event)

                def update_pixmap(self):
                    temp = self.pixmap.copy()
                    if self.start and self.end:
                        painter = QPainter(temp)
                        pen = QPen(QColor(255, 0, 0), 2, Qt.DashLine)
                        painter.setPen(pen)
                        rect = QRect(self.start, self.end)
                        painter.drawRect(rect)
                        painter.end()
                    self.label.setPixmap(temp)

                def get_roi(self):
                    if self.start and self.end:
                        x1, y1 = self.start.x(), self.start.y()
                        x2, y2 = self.end.x(), self.end.y()
                        x, y = min(x1, x2), min(y1, y2)
                        w, h = abs(x2 - x1), abs(y2 - y1)
                        if w > 0 and h > 0:
                            return (x, y, w, h)
                    return None

            dlg = ROIDialog(img, self)
            if dlg.exec() == QDialog.Accepted:
                return dlg.get_roi()
            return None

    app = QApplication(sys.argv)
    dashboard = Dashboard()
    dashboard.show()
    sys.exit(app.exec())
    
