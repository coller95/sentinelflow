import cv2
import numpy as np
import ctypes
import time
import win32gui
import win32ui
import win32con
import win32api

def find_hwnd_by_title(window_title: str) -> int:
    """
    Find the window handle (HWND) using the exact window title.
    Returns 0 if no window is found.
    """
    # FindWindow(ClassName, WindowName)
    # Passing None to ClassName searches by Title only
    Hwnd = win32gui.FindWindow(None, window_title)
    
    if Hwnd == 0:
        return None
        
    return Hwnd


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
    (left, top, right, bottom) = win32gui.GetWindowRect(hwnd)
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

def vk_from_keyname(key_name: str) -> int:
    """
    Convert a key name (like 'a', 'ENTER', 'F5') to its virtual key code.
    """
    vk = win32api.VkKeyScan(key_name)
    if vk == -1:
        raise ValueError(f"Invalid key name: {key_name}")
    return vk & 0xff  # Return only the low byte (virtual key code)

def send_keystroke_to_window(hwnd: int, vk: int) -> None:
    """
    Send a keystroke to the window with the given hwnd.
    Keystroke should be a string like 'a', 'ENTER', 'F5', etc.
    """
    if not hwnd:
        return
    
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    win32gui.SetForegroundWindow(hwnd)
    win32api.keybd_event(vk, 0, 0, 0)
    win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)

def send_mouseclick_to_window(hwnd: int, x_n: float, y_n: float) -> None:
    """
    Send a mouse click to the window with the given hwnd at (x, y) coordinates.
    Coordinates are relative to the window's client area.
    """
    if not hwnd:
        return
        

    # Calculate absolute screen coordinates   
    (left, top, right, bottom) = win32gui.GetWindowRect(hwnd)
    x = float(x_n * (right - left))
    y = float(y_n * (bottom - top))

    click_x = left + int(x)
    click_y = top + int(y)

    # Restore and focus the window
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    win32gui.SetForegroundWindow(hwnd)
    time.sleep(0.03)

    win32api.SetCursorPos((click_x, click_y))
    time.sleep(0.02)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, click_x, click_y, 0, 0)
    time.sleep(0.1) # A short delay is often needed
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, click_x, click_y, 0, 0)