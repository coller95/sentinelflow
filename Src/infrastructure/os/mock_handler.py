from typing import Any, Optional
import numpy as np
from Src.domain.interfaces import IWindowManager, IScreenCapturer, IInputController

# Dummy types
Handle = Any
ProcessID = int

class MockWindowManager(IWindowManager):
    def find_window_by_title(self, title: str) -> Optional[Handle]:
        print(f"[Mock] Finding window by title: {title}")
        return 12345 # Dummy handle

    def find_window_by_pid(self, pid: ProcessID) -> Optional[Handle]:
        print(f"[Mock] Finding window by pid: {pid}")
        return 12345

    def find_pid_by_window(self, handle: Handle) -> ProcessID:
        return 9999

    def launch_process(self, executable_path: str) -> ProcessID:
        print(f"[Mock] Launching process: {executable_path}")
        return 9999

    def terminate_process(self, pid: ProcessID) -> None:
        print(f"[Mock] Terminating process: {pid}")

    def resize_window(self, handle: Handle, width: int, height: int) -> None:
        print(f"[Mock] Resizing window {handle} to {width}x{height}")

    def move_and_resize_window(self, handle: Handle, left: int, top: int, width: int, height: int) -> None:
        print(f"[Mock] Moving window {handle} to ({left},{top}) {width}x{height}")

    def focus_window(self, handle: Handle) -> None:
        print(f"[Mock] Focusing window {handle}")


class MockScreenCapturer(IScreenCapturer):
    def capture_window(self, handle: Handle) -> Any:
        # Return a black 640x480 image
        return np.zeros((480, 640, 3), dtype=np.uint8)


class MockInputController(IInputController):
    def click(self, handle: Handle, x_normalized: float, y_normalized: float) -> None:
        print(f"[Mock] Click at ({x_normalized}, {y_normalized}) on window {handle}")

    def press_key(self, handle: Handle, key_name: str) -> None:
        print(f"[Mock] Press key '{key_name}' on window {handle}")
