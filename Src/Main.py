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
from Src.Helper import *

from PySide6.QtCore import Signal, QThread, Qt, QPoint 
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QFileDialog, QListWidget, QMessageBox, QSizePolicy, QListWidgetItem
from PySide6.QtGui import QPainter, QPen

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

class ClickableImageLabel(QLabel):
    clicked = Signal(QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._nx = None
        self._ny = None
        self.setMouseTracking(True)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            w = self.width()
            h = self.height()

            if w > 0 and h > 0:
                self._nx = event.position().x() / w
                self._ny = event.position().y() / h
                self.clicked.emit(event.position().toPoint())
                self.update()

    def setMarkerNormalized(self, nx: float, ny: float):
        self._nx = nx
        self._ny = ny
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)

        if self._nx is None or self._ny is None:
            return

        x = int(self._nx * self.width())
        y = int(self._ny * self.height())

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(Qt.red, 2)
        painter.setPen(pen)

        size = 10
        painter.drawLine(x - size, y, x + size, y)
        painter.drawLine(x, y - size, x, y + size)

class CoordinateQLineEdit(QWidget):
    def __init__(self):
        super().__init__()
        self.text : str = ""
        self.initUi()

    def initUi(self):
        self.userInput = QLineEdit(self)
        self.userInput.textChanged.connect(self.whenTextChanged)
        
        layout = QVBoxLayout()
        layout.addWidget(self.userInput)
        self.setLayout(layout)

    def whenTextChanged(self, newText: str) -> None:
        self.text = newText

    def bind(self, newText: str) -> None:
        self.text = newText
        return self.userInput.setText(newText)

    def setPlaceholderText(self, text: str) -> None:
        return self.userInput.setPlaceholderText(text)

    def setFixedWidth(self, w: int) -> None:
        return self.userInput.setFixedWidth(w)
        

class Dashboard(QWidget):
    """Main application window (dashboard).

    Handles UI layout, user actions, and live capture updates.
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
        # Add/Del buttons layout
        event_btn_layout = QHBoxLayout()
        self.add_event_btn = QPushButton("+")
        self.add_event_btn.setFixedWidth(28)
        self.add_event_btn.setToolTip("Add Event")
        self.add_event_btn.clicked.connect(self.handle_add_event)
        self.del_event_btn = QPushButton("-")
        self.del_event_btn.setFixedWidth(28)
        self.del_event_btn.setToolTip("Delete Selected Event")
        self.del_event_btn.clicked.connect(self.handle_del_event)
        event_btn_layout.addWidget(self.add_event_btn)
        event_btn_layout.addWidget(self.del_event_btn)
        event_btn_layout.addStretch()
        left_panel.addLayout(event_btn_layout)
        # Add event list widget
        self.event_list = QListWidget()
        self.event_list.setFixedWidth(200)
        left_panel.addWidget(self.event_list)

        # Center panel
        center_panel = QVBoxLayout()
        exe_layout = QHBoxLayout()
        self.exe_path_edit = QLineEdit()
        self.exe_path_edit.setPlaceholderText("Executable path...")
        self.exe_path_edit.setText(r"C:\Users\HONG\Desktop\frozenthrone1.26\war3.exe -window")
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

        self.live_image_label = ClickableImageLabel()
        self.live_image_label.setAlignment(Qt.AlignVCenter | Qt.AlignHCenter)
        self.live_image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.live_image_label.setScaledContents(True)
        self.live_image_label.clicked.connect(self.handle_image_click)
        center_panel.addWidget(self.live_image_label)


        self.keystroke_layout = QHBoxLayout()
        self.keystroke_name_edit = QLineEdit()
        self.keystroke_name_edit.setPlaceholderText("Keystroke name...")
        self.keystroke_layout.addWidget(self.keystroke_name_edit)
        self.keystroke_add_btn = QPushButton("Send Keystroke")
        self.keystroke_add_btn.clicked.connect(self.handle_send_keystroke)
        self.keystroke_layout.addWidget(self.keystroke_add_btn)
        center_panel.addLayout(self.keystroke_layout)

        self.mouse_layout = QHBoxLayout()
        self.mouse_label = QLabel("x:")
        self.mouse_x_edit = QLineEdit()
        self.mouse_x_edit.setPlaceholderText("X")
        self.mouse_x_edit.setFixedWidth(120)
        self.mouse_x_edit.textChanged.connect(self.handle_mouse_text_changed)
        self.mouse_y_label = QLabel("y:")
        self.mouse_y_edit = QLineEdit()
        self.mouse_y_edit.setPlaceholderText("Y")
        self.mouse_y_edit.setFixedWidth(120)
        self.mouse_y_edit.textChanged.connect(self.handle_mouse_text_changed)
        self.mouse_click_btn = QPushButton("Send Mouse Click")  
        self.mouse_click_btn.clicked.connect(self.handle_send_mouse_click)
        self.mouse_layout.addWidget(self.mouse_label)
        self.mouse_layout.addWidget(self.mouse_x_edit)
        self.mouse_layout.addWidget(self.mouse_y_label)
        self.mouse_layout.addWidget(self.mouse_y_edit)
        self.mouse_layout.addWidget(self.mouse_click_btn)

        center_panel.addLayout(self.mouse_layout)

        # Right panel
        right_panel = QVBoxLayout()
        # Event name edit
        self.event_name_edit = QLineEdit()
        self.event_name_edit.setFixedWidth(200)
        self.event_name_edit.setPlaceholderText("Edit event name...")
        self.event_name_edit.setEnabled(False)
        self.event_name_edit.editingFinished.connect(self.handle_event_name_edit)
        right_panel.addWidget(QLabel("Selected Event Name:"))
        right_panel.addWidget(self.event_name_edit)
        right_panel.addStretch()
        # Connect event selection to update name edit
        self.event_list.currentItemChanged.connect(self.on_event_selected)

        # Assemble root layout
        root_layout.addLayout(left_panel, stretch=1)
        root_layout.addLayout(center_panel, stretch=4)
        root_layout.addLayout(right_panel, stretch=1)
        self.setLayout(root_layout)

        self.current_hwnd = None
        self.live_thread = None
        self.last_live_img = None


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

    # ---- Image Rendering ----
    def update_live_image(self, img=None):
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
            from PySide6.QtGui import QImage, QPixmap
            h, w, ch = img.shape
            bytes_per_line = ch * w
            qimg = QImage(img.data, w, h, bytes_per_line, QImage.Format_BGR888)
            pixmap = QPixmap.fromImage(qimg).scaled(
                self.live_image_label.width(), self.live_image_label.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
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

    def add_event(self, name):
        item = QListWidgetItem(name)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Unchecked)
        self.event_list.addItem(item)

    def handle_add_event(self):
        # Add event with default name
        self.add_event("New Event")

    def handle_del_event(self):
        row = self.event_list.currentRow()
        if row >= 0:
            self.event_list.takeItem(row)

    def set_event_color(self, row, color):
        """Set the background color of the event at the given row."""
        item = self.event_list.item(row)
        if item:
            item.setBackground(color)

    def alert_event(self, row):
        """Temporarily alert by changing background to red, then revert."""
        from PySide6.QtGui import QColor
        from PySide6.QtCore import QTimer
        item = self.event_list.item(row)
        if not item:
            return
        original_brush = item.background()
        self.set_event_color(row, QColor('#ff0000'))  # Light red
        
        def revert_color():
            item.setBackground(original_brush)
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(revert_color)
        timer.start(200)  # 1000 ms = 1 second


    def on_event_selected(self, current, previous):
        if current:
            self.event_name_edit.setText(current.text())
            self.event_name_edit.setEnabled(True)
        else:
            self.event_name_edit.clear()
            self.event_name_edit.setEnabled(False)

    def handle_event_name_edit(self):
        item = self.event_list.currentItem()
        if item and self.event_name_edit.isEnabled():
            new_name = self.event_name_edit.text().strip()
            if new_name:
                item.setText(new_name)

    def handle_send_keystroke(self):
        macro_name = self.keystroke_name_edit.text().strip()
        if not macro_name:
            QMessageBox.warning(self, "Error", "Please enter a macro name.")
            return
        # Here you would implement the actual macro sending logic.
        vk = vk_from_keyname(macro_name)
        send_keystroke_to_window(self.current_hwnd, vk)

    def handle_send_mouse_click(self):
        x_n = self.mouse_x_edit.text().strip()
        y_n = self.mouse_y_edit.text().strip()
        if not x_n or not y_n:
            QMessageBox.warning(self, "Error", "Please enter both X and Y coordinates.")
            return
        try:
            x_n = float(x_n)
            y_n = float(y_n)
        except ValueError:
            QMessageBox.warning(self, "Error", "X and Y must be floats.")
            return
        # Here you would implement the actual mouse click sending logic.
        # For now, just print the coordinates.
        
        print(f"Sending mouse click at ({x_n}, {y_n})")
        send_mouseclick_to_window(self.current_hwnd, x_n, y_n)

    def handle_image_click(self, pos: QPoint):
        self.mouse_x_edit.setText(f"{float(pos.x())/self.live_image_label.width():.7f}")
        self.mouse_y_edit.setText(f"{float(pos.y())/self.live_image_label.height():.7f}")

    def handle_mouse_text_changed(self):
        nx = float(self.mouse_x_edit.text()) if self.mouse_x_edit.text() else 0.0
        ny = float(self.mouse_y_edit.text()) if self.mouse_y_edit.text() else 0.0
        self.live_image_label.setMarkerNormalized(nx, ny)
            


if __name__ == "__main__": 
    app = QApplication(sys.argv)
    dashboard = Dashboard()
    dashboard.show()
    sys.exit(app.exec())
    
