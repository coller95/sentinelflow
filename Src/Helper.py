"""
SentinelFlow Helper Module
Description: Window management, image processing, and input simulation utilities.
Naming Convention: Microsoft CamelCase Guidelines.
"""
import ctypes
import subprocess
import time
from typing import Any, List, Optional, Tuple

import cv2
import numpy as np
import win32api
import win32con
import win32gui
import win32process
import win32ui

# Type aliases for clarity
HWND = int
PID = int
VirtualKey = int
NormalizedCoord = float
RoiTuple = Tuple[NormalizedCoord, NormalizedCoord, NormalizedCoord, NormalizedCoord]
MatchLocation = Tuple[int, int]


def findHwndByTitle(windowTitle: str) -> Optional[HWND]:
    """
    Find the window handle (HWND) using the exact window title.
    Returns None if no window is found.
    """
    hwnd: HWND = win32gui.FindWindow(None, windowTitle)
    return hwnd if hwnd != 0 else None


def findPidByHwnd(hwnd: HWND) -> PID:
    """
    Find the process ID (PID) associated with the given window handle (HWND).
    """
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    return pid


def launchHwndByExecutable(executablePath: str) -> PID:
    """
    Launch an application by its executable path and return its PID.
    """
    proc = subprocess.Popen([executablePath], shell=True)
    time.sleep(1.5)  # Wait for the window to appear
    return proc.pid


def captureWindowByHwnd(hwnd: HWND) -> np.ndarray[Any, Any]:
    """
    Capture the window by HWND and return as OpenCV image (BGR).
    Uses Windows GDI for direct window capture.
    """
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    width, height = right - left, bottom - top

    hwndDc = win32gui.GetWindowDC(hwnd)
    mfcDc = win32ui.CreateDCFromHandle(hwndDc)
    saveDc = mfcDc.CreateCompatibleDC()
    saveBitmap = win32ui.CreateBitmap()
    saveBitmap.CreateCompatibleBitmap(mfcDc, width, height)
    saveDc.SelectObject(saveBitmap)

    # Use ctypes to call PrintWindow from user32.dll
    user32 = ctypes.windll.user32
    pw_render_full_content = 0x00000002  # For Windows 8 and above

    try:
        result = user32.PrintWindow(hwnd, saveDc.GetSafeHdc(), pw_render_full_content)
    except Exception:
        # Fallback for older Windows
        result = user32.PrintWindow(hwnd, saveDc.GetSafeHdc(), 0)

    bmp_str = saveBitmap.GetBitmapBits(True)
    img_np = np.frombuffer(bmp_str, dtype=np.uint8).reshape((height, width, 4))
    img_cv = cv2.cvtColor(img_np, cv2.COLOR_BGRA2BGR)

    # Free resources
    win32gui.DeleteObject(saveBitmap.GetHandle())
    saveDc.DeleteDC()
    mfcDc.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwndDc)

    if result != 1:
        raise RuntimeError("Failed to capture window image using PrintWindow.")
    return img_cv


def ResizeWindow(hwnd: HWND, width: int, height: int) -> None:
    """
    Resizes the window identified by the handle to the specified width and height.

    :param hwnd: The handle to the window to be resized.
    :param width: The new width of the window.
    :param height: The new height of the window.
    """
    # Get current position to maintain the window's top-left coordinates
    window_rect = win32gui.GetWindowRect(hwnd)
    current_x, current_y = window_rect[0], window_rect[1]

    win32gui.MoveWindow(hwnd, current_x, current_y, width, height, True)


def cropImage(img: np.ndarray[Any, Any], roi_normalized: RoiTuple) -> np.ndarray[Any, Any]:
    """
    Crop an image using normalized coordinates (0.0-1.0).

    :param img: Source image as numpy array
    :param roi_normalized: Tuple (xn, yn, wn, hn) representing normalized ROI
    :return: Cropped image section
    """
    h_max, w_max = img.shape[:2]
    xn, yn, wn, hn = roi_normalized

    # Convert normalized coordinates to pixel values
    x = int(xn * w_max)
    y = int(yn * h_max)
    w = int(wn * w_max)
    h = int(hn * h_max)

    # Ensure coordinates are within bounds
    x = max(0, min(x, w_max - 1))
    y = max(0, min(y, h_max - 1))
    w = max(1, min(w, w_max - x))
    h = max(1, min(h, h_max - y))

    return img[y:y + h, x:x + w].copy()


def matchTemplate(img: np.ndarray[Any, Any], template: np.ndarray[Any, Any]) -> float:
    """
    Calculate template match similarity using normalized squared difference.

    :param img: Source image
    :param template: Template image to match
    :return: Similarity score (0.0 to 1.0, higher is better)
    """
    result = cv2.matchTemplate(img, template, cv2.TM_SQDIFF_NORMED)
    min_val, _, _, _ = cv2.minMaxLoc(result)
    return 1.0 - min_val


def templateMatch(
    img: np.ndarray[Any, Any], 
    template: np.ndarray[Any, Any], 
    threshold: float = 0.8
) -> List[MatchLocation]:
    """
    Perform template matching to find template in image.

    :param img: Source image
    :param template: Template image to match
    :param threshold: Minimum similarity threshold (0.0 to 1.0)
    :return: List of top-left coordinates where matches were found
    """
    result = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
    locations = np.where(result >= threshold)
    return list(zip(*locations[::-1]))


def estimateProgressBarPercentage(barImg: np.ndarray[Any, Any]) -> float:
    """
    Estimate the filled percentage of a horizontal progress bar.

    :param barImg: Image containing the progress bar
    :return: Filled percentage (0.0 to 1.0)
    """
    if barImg.size == 0:
        return 0.0

    gray = cv2.cvtColor(barImg, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)

    _h, w = gray.shape
    if w == 0:
        return 0.0

    # Column mean intensity
    col_means = gray.mean(axis=0).astype(np.float32)

    # Background reference: narrow vertical strip at right edge
    bg_strip = gray[:, int(w * 0.95):w]
    bg_mean = bg_strip.mean()

    # Interior reference: center region
    center_start = int(w * 0.45)
    center_end = int(w * 0.55)
    center_strip = gray[:, center_start:center_end]
    center_mean = center_strip.mean()

    # If flat signal, decide between 0% and 100%
    range_value = np.ptp(col_means)
    if range_value < 1e-6:
        return 0.0 if abs(center_mean - bg_mean) < 5 else 1.0

    # Determine fill polarity
    sample_width = max(1, w // 10)
    left_mean: float = float(np.mean(col_means[:sample_width])) # type: ignore
    right_mean: float = float(np.mean(col_means[-sample_width:])) # type: ignore
    fill_is_darker = left_mean < right_mean

    # Normalize and process signal
    col_norm = (col_means - col_means.min()) / max(range_value, 1e-6)
    signal: np.ndarray[Any, Any] = 1.0 - col_norm if fill_is_darker else col_norm
    signal = cv2.GaussianBlur(signal.reshape(1, -1), (1, 31), 0).flatten()

    threshold_value = 0.5
    filled_cols = np.where(signal > threshold_value)[0]

    if len(filled_cols) == 0:
        return 0.0

    fill_end = filled_cols[-1]
    percent = (fill_end + 1) / w
    return float(np.clip(percent, 0.0, 1.0))


def vkFromKeyName(keyName: str) -> VirtualKey:
    """
    Convert a key name to its virtual key code.

    :param keyName: Single character key name
    :return: Virtual key code
    :raises ValueError: If key name is invalid
    """
    vk: VirtualKey = VirtualKey(win32api.VkKeyScan(keyName)) # type: ignore
    if vk == -1:
        raise ValueError(f"Invalid key name: {keyName}")
    return vk & 0xFF


def KeyNameFromVk(virtualKey: VirtualKey) -> str:
    """
    Convert a virtual key code to its display name.

    :param virtualKey: Virtual key code
    :return: Human-readable key name
    :raises ValueError: If virtual key is invalid
    """
    scan_code: int = int(win32api.MapVirtualKey(virtualKey, 0))  # type: ignore
    lParam: int = scan_code << 16
    name_buffer = ctypes.create_unicode_buffer(32)
    result = ctypes.windll.user32.GetKeyNameTextW(lParam, name_buffer, 32)
    if result == 0:
        raise ValueError(f"Invalid virtual key code: {virtualKey}")
    return name_buffer.value


def sendKeystrokeToWindow(hwnd: HWND, vk: VirtualKey) -> None:
    """
    Send a virtual key keystroke to the specified window.

    :param hwnd: Window handle
    :param vk: Virtual key code to send
    """
    if not hwnd:
        return

    # Restore and focus the window
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    win32gui.SetForegroundWindow(hwnd)
    time.sleep(0.05)

    # Type ignore needed for win32api functions with incomplete type stubs
    win32api.keybd_event(vk, 0, 0, 0)  # type: ignore
    win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)  # type: ignore


def sendMouseClickToWindow(hwnd: HWND, xN: NormalizedCoord, yN: NormalizedCoord) -> None:
    """
    Send a mouse click to the window at normalized coordinates.

    :param hwnd: Window handle
    :param xN: Normalized X coordinate (0.0 to 1.0)
    :param yN: Normalized Y coordinate (0.0 to 1.0)
    """
    if not hwnd:
        return

    # Calculate absolute screen coordinates
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    width = right - left
    height = bottom - top

    x = float(xN * width)
    y = float(yN * height)

    click_x = left + int(x)
    click_y = top + int(y)

    # Restore and focus the window
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    win32gui.SetForegroundWindow(hwnd)
    time.sleep(0.05)

    win32api.SetCursorPos((click_x, click_y))
    time.sleep(0.05)
    # Type ignore needed for win32api mouse_event with incomplete type stubs
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, click_x, click_y, 0, 0)  # type: ignore
    time.sleep(0.01)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, click_x, click_y, 0, 0)  # type: ignore


def IsHotkeyActive(vkList: List[VirtualKey]) -> bool:
    """
    Check if all keys in a virtual key list are currently pressed.

    :param vkList: List of virtual key codes to check
    :return: True if all keys are pressed, False otherwise
    """
    if not vkList:
        return False

    for vk in vkList:
        # GetAsyncKeyState returns negative value when key is pressed
        if win32api.GetAsyncKeyState(vk) >= 0:  # type: ignore
            return False
    return True