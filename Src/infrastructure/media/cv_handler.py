import base64
from typing import Any, Optional, cast

import cv2
import numpy as np
from numpy.typing import NDArray

from Src.domain.interfaces import IComputerVision, NormalizedRect, Image

class CvComputerVision(IComputerVision):
    def crop_image(self, image: Image, roi: NormalizedRect) -> Image:
        img_arr = image
        imageHeight, imageWidth = img_arr.shape[:2]
        normalizedX, normalizedY, normalizedWidth, normalizedHeight = roi

        pixelX = int(normalizedX * imageWidth)
        pixelY = int(normalizedY * imageHeight)
        pixelWidth = int(normalizedWidth * imageWidth)
        pixelHeight = int(normalizedHeight * imageHeight)

        # Clamp to valid bounds
        pixelX = max(0, min(pixelX, imageWidth - 1))
        pixelY = max(0, min(pixelY, imageHeight - 1))
        pixelWidth = max(1, min(pixelWidth, imageWidth - pixelX))
        pixelHeight = max(1, min(pixelHeight, imageHeight - pixelY))

        return img_arr[pixelY:pixelY + pixelHeight, pixelX:pixelX + pixelWidth].copy()

    def match_template(self, image: Image, template: Image) -> float:
        img_arr = image
        tmpl_arr = template
        
        # Guard against empty images
        if img_arr.size == 0 or tmpl_arr.size == 0:
            return 0.0
            
        # Helper logic: ensure template is smaller than image
        h, w = img_arr.shape[:2]
        th, tw = tmpl_arr.shape[:2]
        if th > h or tw > w:
            return 0.0

        result = cv2.matchTemplate(img_arr, tmpl_arr, cv2.TM_SQDIFF_NORMED)
        minVal, _, _, _ = cv2.minMaxLoc(result)
        return 1.0 - minVal

    def estimate_progress_bar(self, image: Image) -> float:
        barImage = image
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
        processedSignal: NDArray[Any] = 1.0 - normalizedSignal if fillIsDarker else normalizedSignal
        processedSignal = cv2.GaussianBlur(processedSignal.reshape(1, -1), (1, 31), 0).flatten()

        filledColumns = np.where(processedSignal > 0.5)[0]
        if len(filledColumns) == 0:
            return 0.0

        fillEndIndex = filledColumns[-1]
        percentage = (fillEndIndex + 1) / imageWidth
        return float(np.clip(percentage, 0.0, 1.0))

    def encode_image_to_b64(self, image: Image) -> Optional[str]:
        img = image
        if getattr(img, "size", 0) == 0:
            return None
        ok, encoded = cv2.imencode(".png", img)
        if not ok:
            return None
        return base64.b64encode(encoded.tobytes()).decode("ascii")

    def decode_image_from_b64(self, b64_string: str) -> Optional[Image]:
        raw_b64 = (b64_string or "").strip()
        if not raw_b64:
            return None
        if "," in raw_b64:
            raw_b64 = raw_b64.split(",", 1)[1]
        try:
            binary = base64.b64decode(raw_b64, validate=True)
        except Exception:
            return None
        arr = np.frombuffer(binary, dtype=np.uint8)
        decoded = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if decoded is None:
            return None
        return cast(NDArray[np.uint8], decoded)

    def resize_image(self, image: Image, width: int, height: int) -> Image:
        img_arr = image
        return cv2.resize(img_arr, (width, height), interpolation=cv2.INTER_AREA)
