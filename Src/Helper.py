import cv2
import numpy as np
import ctypes
import time
import win32gui
import win32ui
from pywinauto import findwindows  # pyright: ignore[reportMissingTypeStubs]
from pywinauto.win32functions import GetWindowRect

def find_hwnd_by_title(window_title: str) -> int:
    """
    Find the first window handle (hwnd) matching the given window title.
    """
    hwnds = findwindows.find_windows(title=window_title)
    if hwnds:
        return hwnds[0]
    else:
        return None


def launch_hwnd_by_executable(executable_path: str) -> int:
    """
    Launch an application by its executable path and return its window handle (hwnd).
    """
    import subprocess
    # Launch the script as a separate process
    proc = subprocess.Popen(executable_path, shell=True)
    time.sleep(1.5)  # Wait for the window to appear
    # Find the window by title after launching
    # (Assume the window title is known and passed separately if needed)
    return proc.pid

                                                  

def capture_window_by_hwnd(hwnd: int) -> np.ndarray:
    """
    Capture the window of a process by PID and return as OpenCV image (BGR).
    Uses Windows GDI for direct window capture.
    """
    rect = ctypes.wintypes.RECT()
    GetWindowRect(hwnd, ctypes.byref(rect))
    left, top, right, bottom = rect.left, rect.top, rect.right, rect.bottom
    width, height = right - left, bottom - top

    hwndDC = win32gui.GetWindowDC(hwnd)
    mfcDC = win32ui.CreateDCFromHandle(hwndDC)
    saveDC = mfcDC.CreateCompatibleDC()
    saveBitMap = win32ui.CreateBitmap()
    saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
    saveDC.SelectObject(saveBitMap)

    # Use ctypes to call PrintWindow from user32.dll
    user32 = ctypes.windll.user32
    PW_RENDERFULLCONTENT = 0x00000002  # For Windows 8 and above, else use 0
    try:
        result = user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), PW_RENDERFULLCONTENT)
    except Exception:
        # fallback for older Windows
        result = user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 0)

    bmpinfo = saveBitMap.GetInfo()
    bmpstr = saveBitMap.GetBitmapBits(True)
    img_np = np.frombuffer(bmpstr, dtype='uint8').reshape((height, width, 4))
    img_cv = cv2.cvtColor(img_np, cv2.COLOR_BGRA2BGR)

    # Free resources
    win32gui.DeleteObject(saveBitMap.GetHandle())
    saveDC.DeleteDC()
    mfcDC.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwndDC)

    if result != 1:
        raise Exception("Failed to capture window image using PrintWindow.")
    return img_cv



def crop_image(img: np.ndarray, roi: tuple[int, int, int, int]) -> np.ndarray:
    """
    Given an image and ROI coordinates, return the cropped image.
    ROI: (x, y, w, h)
    """
    x, y, w, h = roi
    return img[y:y+h, x:x+w]


def template_match(img: np.ndarray, template: np.ndarray, threshold: float = 0.8) -> list[tuple[int, int]]:
    """
    Perform template matching to find template in image.
    Returns list of top-left points where matches are found.
    """
    result = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
    locations = np.where(result >= threshold)
    return list(zip(*locations[::-1]))


def estimate_progress_bar_percentage(bar_img: np.ndarray) -> float:
    """
    Estimate the filled percentage of a horizontal progress bar
    filled from left to right. Correctly distinguishes 0% vs 100%.
    """

    if bar_img is None or bar_img.size == 0:
        return 0.0

    gray = cv2.cvtColor(bar_img, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)

    h, w = gray.shape
    if w == 0:
        return 0.0

    # Column mean intensity
    col_means = gray.mean(axis=0)

    # Background reference: narrow vertical strip at right edge
    bg_strip = gray[:, int(w * 0.95):w]
    bg_mean = bg_strip.mean()

    # Interior reference: center region
    center_strip = gray[:, int(w * 0.45):int(w * 0.55)]
    center_mean = center_strip.mean()

    # If flat signal, decide between 0% and 100%
    range_ = np.ptp(col_means)
    if range_ < 1e-6:
        # Compare interior to background
        if abs(center_mean - bg_mean) < 5:
            return 0.0   # empty
        else:
            return 100.0 # full

    # Determine fill polarity
    sample_width = max(1, w // 10)
    left_mean = np.mean(col_means[:sample_width])
    right_mean = np.mean(col_means[-sample_width:])
    fill_is_darker = left_mean < right_mean

    # Normalize
    col_norm = (col_means - col_means.min()) / range_

    signal = 1.0 - col_norm if fill_is_darker else col_norm
    signal = cv2.GaussianBlur(signal.reshape(1, -1), (1, 31), 0).flatten()

    threshold = 0.5
    filled_cols = np.where(signal > threshold)[0]

    if len(filled_cols) == 0:
        return 0.0

    fill_end = filled_cols[-1]
    percent = (fill_end + 1) / w * 100.0

    return float(np.clip(percent, 0.0, 100.0))