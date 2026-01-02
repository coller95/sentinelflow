import ctypes
import shlex
import subprocess
import time
from pathlib import Path
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


# ────────────────────────────────────────
# Window Management
# ────────────────────────────────────────

def FindHwndByTitle(windowTitle: str) -> Optional[HWND]:
    hwnd: HWND = win32gui.FindWindow(None, windowTitle)
    return hwnd if hwnd != 0 else None


def FindPidByHwnd(hwnd: HWND) -> PID:
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    return pid


def LaunchProcessByExecutable(executablePath: str) -> PID:
    command = executablePath.strip()
    if not command:
        raise ValueError("Executable path cannot be empty.")

    try:
        argv = shlex.split(command, posix=False)
    except ValueError:
        argv = [command]

    recoveredArgv: Optional[List[str]] = None
    if argv:
        for i in range(1, len(argv) + 1):
            candidate = " ".join(argv[:i]).strip('"')
            candidatePath = Path(candidate)
            if candidatePath.exists() and candidatePath.suffix.lower() in (".exe", ".com"):
                recoveredArgv = [candidate] + argv[i:]
                break

    argvToUse = recoveredArgv or argv

    exeCandidate = argvToUse[0].strip('"') if argvToUse else command.strip('"')
    exePath = Path(exeCandidate)
    suffix = exePath.suffix.lower()

    useShell = True
    popenArg: object = command

    if exePath.exists() and suffix in (".exe", ".com"):
        useShell = False
        popenArg = argvToUse
    elif exePath.exists() and suffix in (".bat", ".cmd"):
        useShell = True
        popenArg = command

    process = subprocess.Popen(popenArg, shell=useShell)
    time.sleep(1.5)  # Allow time for window creation
    return process.pid


def ResizeWindow(hwnd: HWND, width: int, height: int) -> None:
    left, top, _, _ = win32gui.GetWindowRect(hwnd)
    win32gui.MoveWindow(hwnd, left, top, width, height, True)


# ────────────────────────────────────────
# Window Capture & Image Processing
# ────────────────────────────────────────

def CaptureWindowByHwnd(hwnd: HWND) -> np.ndarray[Any, Any]:
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    width = right - left
    height = bottom - top

    windowDc = win32gui.GetWindowDC(hwnd)
    memoryDc = win32ui.CreateDCFromHandle(windowDc)
    compatibleDc = memoryDc.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()
    bitmap.CreateCompatibleBitmap(memoryDc, width, height)
    compatibleDc.SelectObject(bitmap)

    user32 = ctypes.windll.user32
    pwRenderFullContent = 0x00000002  # Windows 8+

    try:
        result = user32.PrintWindow(hwnd, compatibleDc.GetSafeHdc(), pwRenderFullContent)
    except Exception:
        result = user32.PrintWindow(hwnd, compatibleDc.GetSafeHdc(), 0)

    bitmapBits = bitmap.GetBitmapBits(True)
    imageArray = np.frombuffer(bitmapBits, dtype=np.uint8).reshape((height, width, 4))
    bgrImage = cv2.cvtColor(imageArray, cv2.COLOR_BGRA2BGR)

    # Cleanup
    win32gui.DeleteObject(bitmap.GetHandle())
    compatibleDc.DeleteDC()
    memoryDc.DeleteDC()
    win32gui.ReleaseDC(hwnd, windowDc)

    if result != 1:
        raise RuntimeError("Failed to capture window using PrintWindow.")
    return bgrImage


def CropImage(image: np.ndarray[Any, Any], roiNormalized: RoiTuple) -> np.ndarray[Any, Any]:
    imageHeight, imageWidth = image.shape[:2]
    normalizedX, normalizedY, normalizedWidth, normalizedHeight = roiNormalized

    pixelX = int(normalizedX * imageWidth)
    pixelY = int(normalizedY * imageHeight)
    pixelWidth = int(normalizedWidth * imageWidth)
    pixelHeight = int(normalizedHeight * imageHeight)

    # Clamp to valid bounds
    pixelX = max(0, min(pixelX, imageWidth - 1))
    pixelY = max(0, min(pixelY, imageHeight - 1))
    pixelWidth = max(1, min(pixelWidth, imageWidth - pixelX))
    pixelHeight = max(1, min(pixelHeight, imageHeight - pixelY))

    return image[pixelY:pixelY + pixelHeight, pixelX:pixelX + pixelWidth].copy()


def MatchTemplate(image: np.ndarray[Any, Any], template: np.ndarray[Any, Any]) -> float:
    result = cv2.matchTemplate(image, template, cv2.TM_SQDIFF_NORMED)
    minVal, _, _, _ = cv2.minMaxLoc(result)
    return 1.0 - minVal


def TemplateMatch(
    image: np.ndarray[Any, Any],
    template: np.ndarray[Any, Any],
    threshold: float = 0.8
) -> List[MatchLocation]:
    result = cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)
    matchLocations = np.where(result >= threshold)
    return list(zip(*matchLocations[::-1]))


def EstimateProgressBarPercentage(barImage: np.ndarray[Any, Any]) -> float:
    if barImage.size == 0:
        return 0.0

    grayImage = cv2.cvtColor(barImage, cv2.COLOR_BGR2GRAY)
    grayImage = cv2.GaussianBlur(grayImage, (5, 5), 0)

    _imageHeight, imageWidth = grayImage.shape
    if imageWidth == 0:
        return 0.0

    columnMeans = grayImage.mean(axis=0).astype(np.float32)

    # Background and center reference
    backgroundMean = grayImage[:, int(imageWidth * 0.95):].mean()
    centerMean = grayImage[:, int(imageWidth * 0.45):int(imageWidth * 0.55)].mean()

    intensityRange = np.ptp(columnMeans)
    if intensityRange < 1e-6:
        return 0.0 if abs(centerMean - backgroundMean) < 5 else 1.0

    sampleWidth = max(1, imageWidth // 10)
    leftMean = float(np.mean(columnMeans[:sampleWidth]).item()) # type: ignore
    rightMean = float(np.mean(columnMeans[-sampleWidth:]).item()) # type: ignore
    fillIsDarker = leftMean < rightMean

    normalizedSignal = (columnMeans - columnMeans.min()) / max(intensityRange, 1e-6)
    processedSignal: np.ndarray[Any, Any] = 1.0 - normalizedSignal if fillIsDarker else normalizedSignal
    processedSignal = cv2.GaussianBlur(processedSignal.reshape(1, -1), (1, 31), 0).flatten()

    filledColumns = np.where(processedSignal > 0.5)[0]
    if len(filledColumns) == 0:
        return 0.0

    fillEndIndex = filledColumns[-1]
    percentage = (fillEndIndex + 1) / imageWidth
    return float(np.clip(percentage, 0.0, 1.0))


# ────────────────────────────────────────
# Input Simulation
# ────────────────────────────────────────

def VkFromKeyName(keyName: str) -> VirtualKey:
    vk = VirtualKey(win32api.VkKeyScan(keyName))  # type: ignore
    if vk == -1:
        raise ValueError(f"Invalid key name: {keyName}")
    return vk & 0xFF


def KeyNameFromVk(virtualKey: VirtualKey) -> str:
    scanCode = int(win32api.MapVirtualKey(virtualKey, 0))  # type: ignore
    lParam = scanCode << 16
    nameBuffer = ctypes.create_unicode_buffer(32)
    result = ctypes.windll.user32.GetKeyNameTextW(lParam, nameBuffer, 32)
    if result == 0:
        raise ValueError(f"Invalid virtual key code: {virtualKey}")
    return nameBuffer.value


def SendKeystrokeToWindow(hwnd: HWND, virtualKey: VirtualKey) -> None:
    if not hwnd:
        return

    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    win32gui.SetForegroundWindow(hwnd)
    time.sleep(0.05)

    win32api.keybd_event(virtualKey, 0, 0, 0)  # type: ignore
    win32api.keybd_event(virtualKey, 0, win32con.KEYEVENTF_KEYUP, 0)  # type: ignore


def SendKeyDownToWindow(hwnd: HWND, virtualKey: VirtualKey) -> None:
    if not hwnd:
        return

    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    win32gui.SetForegroundWindow(hwnd)
    time.sleep(0.05)

    win32api.keybd_event(virtualKey, 0, 0, 0)  # type: ignore


def SendKeyUpToWindow(hwnd: HWND, virtualKey: VirtualKey) -> None:
    if not hwnd:
        return

    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    win32gui.SetForegroundWindow(hwnd)
    time.sleep(0.05)

    win32api.keybd_event(virtualKey, 0, win32con.KEYEVENTF_KEYUP, 0)  # type: ignore


def SendKeyStrokeToWindow(hwnd: HWND, virtualKey: VirtualKey) -> None:
    SendKeystrokeToWindow(hwnd, virtualKey)


def SendKeyChordToWindow(hwnd: HWND, virtualKeys: List[VirtualKey]) -> None:
    if not hwnd:
        return
    if not virtualKeys:
        return

    # Normalize input and drop invalid values
    keys: List[VirtualKey] = [VirtualKey(vk) for vk in virtualKeys if int(vk) > 0]
    if not keys:
        return

    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    win32gui.SetForegroundWindow(hwnd)
    time.sleep(0.05)

    modifiers = keys[:-1]
    primary = keys[-1]

    for vk in modifiers:
        win32api.keybd_event(vk, 0, 0, 0)  # type: ignore
        time.sleep(0.005)

    win32api.keybd_event(primary, 0, 0, 0)  # type: ignore
    time.sleep(0.005)
    win32api.keybd_event(primary, 0, win32con.KEYEVENTF_KEYUP, 0)  # type: ignore

    for vk in reversed(modifiers):
        time.sleep(0.005)
        win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)  # type: ignore


def SendMouseClickToWindow(hwnd: HWND, normalizedX: NormalizedCoord, normalizedY: NormalizedCoord) -> None:
    if not hwnd:
        return

    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    windowWidth = right - left
    windowHeight = bottom - top

    screenX = left + int(normalizedX * windowWidth)
    screenY = top + int(normalizedY * windowHeight)

    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    win32gui.SetForegroundWindow(hwnd)
    time.sleep(0.05)

    win32api.SetCursorPos((screenX, screenY))
    time.sleep(0.05)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, screenX, screenY, 0, 0)  # type: ignore
    time.sleep(0.01)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, screenX, screenY, 0, 0)  # type: ignore


def IsHotkeyActive(virtualKeyList: List[VirtualKey]) -> bool:
    if not virtualKeyList:
        return False
    for vk in virtualKeyList:
        if win32api.GetAsyncKeyState(vk) >= 0:  # type: ignore
            return False
    return True