from abc import ABC, abstractmethod
from typing import Any, Optional, Tuple
import numpy as np
from numpy.typing import NDArray

# Type definitions
Handle = Any        # e.g. HWND (int)
ProcessID = int
Image = NDArray[np.uint8]
NormalizedRect = Tuple[float, float, float, float] # x, y, width, height

class IWindowManager(ABC):
    """Abstract interface for OS-level window management."""

    @abstractmethod
    def find_window_by_title(self, title: str) -> Optional[Handle]:
        """Find a window handle by its title string."""
        pass

    @abstractmethod
    def find_window_by_pid(self, pid: ProcessID) -> Optional[Handle]:
        """Find the main window handle for a given process ID."""
        pass

    @abstractmethod
    def find_pid_by_window(self, handle: Handle) -> ProcessID:
        """Get the process ID associated with a window handle."""
        pass

    @abstractmethod
    def launch_process(self, executable_path: str) -> ProcessID:
        """Launch a new process from an executable path and return its PID."""
        pass

    @abstractmethod
    def terminate_process(self, pid: ProcessID) -> None:
        """Terminate a process by its PID."""
        pass

    @abstractmethod
    def resize_window(self, handle: Handle, width: int, height: int) -> None:
        """Resize a window to specific dimensions."""
        pass

    @abstractmethod
    def move_and_resize_window(self, handle: Handle, left: int, top: int, width: int, height: int) -> None:
        """Move and resize a window."""
        pass

    @abstractmethod
    def focus_window(self, handle: Handle) -> None:
        """Bring the window to foreground/focus."""
        pass


class IScreenCapturer(ABC):
    """Abstract interface for capturing screen content."""

    @abstractmethod
    def capture_window(self, handle: Handle) -> Image:
        """Capture the content of a specific window as an image."""
        pass


class IInputController(ABC):
    """Abstract interface for simulating user input."""

    @abstractmethod
    def click(self, handle: Handle, x_normalized: float, y_normalized: float) -> None:
        """Perform a mouse click at normalized coordinates (0..1) within the window."""
        pass

    @abstractmethod
    def press_key(self, handle: Handle, key_name: str) -> None:
        """Simulate a key press sent to the window."""
        pass


class IComputerVision(ABC):
    """Abstract interface for image processing and recognition."""

    @abstractmethod
    def crop_image(self, image: Image, roi: NormalizedRect) -> Image:
        """Crop an image based on normalized coordinates."""
        pass

    @abstractmethod
    def match_template(self, image: Image, template: Image) -> float:
        """Return the best match confidence (0..1) of template within image."""
        pass

    @abstractmethod
    def estimate_progress_bar(self, image: Image) -> float:
        """Estimate the fill percentage (0..1) of a progress bar image."""
        pass

    @abstractmethod
    def encode_image_to_b64(self, image: Image) -> Optional[str]:
        """Encode an image to a base64 string (e.g., PNG/JPG)."""
        pass

    @abstractmethod
    def decode_image_from_b64(self, b64_string: str) -> Optional[Image]:
        """Decode a base64 string back into an image."""
        pass

    @abstractmethod
    def resize_image(self, image: Image, width: int, height: int) -> Image:
        """Resize an image to specific dimensions."""
        pass
