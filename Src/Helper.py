import cv2
import numpy as np
import ctypes
import time
import win32gui
import win32ui
import win32con
import win32api
import win32process

def findHwndByTitle(windowTitle: str) -> int:
    """
    Find the window handle (HWND) using the exact window title.
    Returns None if no window is found.
    """
    hwnd = win32gui.FindWindow(None, windowTitle)
    
    if hwnd == 0:
        return None
        
    return hwnd

def findPidByHwnd(hwnd: int) -> int:
    """
    Find the process ID (PID) associated with the given window handle (HWND).
    """
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    return pid

def launchHwndByExecutable(executablePath: str) -> int:
    """
    Launch an application by its executable path and return its PID.
    """
    import subprocess
    proc = subprocess.Popen(executablePath, shell=True)
    time.sleep(1.5)  # Wait for the window to appear
    return proc.pid


def captureWindowByHwnd(hwnd: int) -> np.ndarray:
    """
    Capture the window by HWND and return as OpenCV image (BGR).
    Uses Windows GDI for direct window capture.
    """
    (left, top, right, bottom) = win32gui.GetWindowRect(hwnd)
    width, height = right - left, bottom - top

    hwndDc = win32gui.GetWindowDC(hwnd)
    mfcDc = win32ui.CreateDCFromHandle(hwndDc)
    saveDc = mfcDc.CreateCompatibleDC()
    saveBitmap = win32ui.CreateBitmap()
    saveBitmap.CreateCompatibleBitmap(mfcDc, width, height)
    saveDc.SelectObject(saveBitmap)

    # Use ctypes to call PrintWindow from user32.dll
    user32 = ctypes.windll.user32
    pwRenderFullContent = 0x00000002  # For Windows 8 and above
    
    try:
        result = user32.PrintWindow(hwnd, saveDc.GetSafeHdc(), pwRenderFullContent)
    except Exception:
        # Fallback for older Windows
        result = user32.PrintWindow(hwnd, saveDc.GetSafeHdc(), 0)

    bmpStr = saveBitmap.GetBitmapBits(True)
    imgNp = np.frombuffer(bmpStr, dtype='uint8').reshape((height, width, 4))
    imgCv = cv2.cvtColor(imgNp, cv2.COLOR_BGRA2BGR)

    # Free resources
    win32gui.DeleteObject(saveBitmap.GetHandle())
    saveDc.DeleteDC()
    mfcDc.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwndDc)

    if result != 1:
        raise Exception("Failed to capture window image using PrintWindow.")
    return imgCv

def ResizeWindow(hwnd: int, width: int, height: int) -> None:
    """
    Resizes the window identified by the handle to the specified width and height.

    :param hwnd: The handle to the window to be resized.
    :param width: The new width of the window.
    :param height: The new height of the window.
    """
    # Get current position to maintain the window's top-left coordinates.
    # Microsoft style emphasizes clarity in variable naming and comments.
    windowRect = win32gui.GetWindowRect(hwnd)
    currentX = windowRect[0]
    currentY = windowRect[1]

    # SetWindowPos is often preferred in Windows development for fine-grained control,
    # but MoveWindow is used here as a direct refactor of your logic.
    win32gui.MoveWindow(
        hwnd, 
        currentX, 
        currentY, 
        width, 
        height, 
        True
    )


def cropImage(img: np.ndarray, roi: tuple[int, int, int, int]) -> np.ndarray:
    """
    Given an image and ROI coordinates, return the cropped image.
    ROI: (x, y, w, h)
    """
    x, y, w, h = roi
    return img[y:y+h, x:x+w]


def templateMatch(img: np.ndarray, template: np.ndarray, threshold: float = 0.8) -> list[tuple[int, int]]:
    """
    Perform template matching to find template in image.
    Returns list of top-left points where matches are found.
    """
    result = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
    locations = np.where(result >= threshold)
    return list(zip(*locations[::-1]))


def estimateProgressBarPercentage(barImg: np.ndarray) -> float:
    """
    Estimate the filled percentage of a horizontal progress bar.
    """
    if barImg is None or barImg.size == 0:
        return 0.0

    gray = cv2.cvtColor(barImg, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)

    h, w = gray.shape
    if w == 0:
        return 0.0

    # Column mean intensity
    colMeans = gray.mean(axis=0)

    # Background reference: narrow vertical strip at right edge
    bgStrip = gray[:, int(w * 0.95):w]
    bgMean = bgStrip.mean()

    # Interior reference: center region
    centerStrip = gray[:, int(w * 0.45):int(w * 0.55)]
    centerMean = centerStrip.mean()

    # If flat signal, decide between 0% and 100%
    rangeValue = np.ptp(colMeans)
    if rangeValue < 1e-6:
        if abs(centerMean - bgMean) < 5:
            return 0.0
        else:
            return 100.0

    # Determine fill polarity
    sampleWidth = max(1, w // 10)
    leftMean = np.mean(colMeans[:sampleWidth])
    rightMean = np.mean(colMeans[-sampleWidth:])
    fillIsDarker = leftMean < rightMean

    # Normalize
    colNorm = (colMeans - colMeans.min()) / rangeValue

    signal = 1.0 - colNorm if fillIsDarker else colNorm
    signal = cv2.GaussianBlur(signal.reshape(1, -1), (1, 31), 0).flatten()

    thresholdValue = 0.5
    filledCols = np.where(signal > thresholdValue)[0]

    if len(filledCols) == 0:
        return 0.0

    fillEnd = filledCols[-1]
    percent = (fillEnd + 1) / w * 100.0

    return float(np.clip(percent, 0.0, 100.0))


def vkFromKeyName(keyName: str) -> int:
    """
    Convert a key name to its virtual key code.
    """
    vk = win32api.VkKeyScan(keyName)
    if vk == -1:
        raise ValueError(f"Invalid key name: {keyName}")
    return vk & 0xff

def sendKeystrokeToWindow(hwnd: int, vk: int) -> None:
    """
    Send a virtual key keystroke to the window with the given hwnd.
    """
    if not hwnd:
        return
    
    WaitForWindowFocus(hwnd, timeoutSeconds=0.03)
    win32api.keybd_event(vk, 0, 0, 0)
    win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)


def sendMouseClickToWindow(hwnd: int, xN: float, yN: float) -> None:
    """
    Send a mouse click to the window at normalized (0.0 to 1.0) coordinates.
    """
    if not hwnd:
        return
        
    # Calculate absolute screen coordinates   
    (left, top, right, bottom) = win32gui.GetWindowRect(hwnd)
    width = right - left
    height = bottom - top
    
    x = float(xN * width)
    y = float(yN * height)

    clickX = left + int(x)
    clickY = top + int(y)

    # Restore and focus the window
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    win32gui.SetForegroundWindow(hwnd)
    time.sleep(0.05)

    win32api.SetCursorPos((clickX, clickY))
    time.sleep(0.05)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, clickX, clickY, 0, 0)
    time.sleep(0.01)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, clickX, clickY, 0, 0)