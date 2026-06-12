"""py_trees Behaviour leaves for the verified-action engine."""

from __future__ import annotations

import time
from types import MappingProxyType
from typing import Final

import cv2
import numpy as np
import py_trees
import py_trees.behaviour
import py_trees.common

from .client import NodeError, NoFrameYet
from .context import EngineContext

Status = py_trees.common.Status

# Pixel-diff threshold for VerifyRegionChanged
_PIXEL_DIFF_THRESH: Final[int] = 30


class EngineLeaf(py_trees.behaviour.Behaviour):
    """Base class for all engine leaves.

    Stores a shared EngineContext and provides _fail() for concise failure
    returns with a feedback message.
    """

    def __init__(self, name: str, ctx: EngineContext) -> None:
        super().__init__(name=name)
        self.ctx = ctx

    def _fail(self, msg: str) -> Status:
        """Set feedback_message and return FAILURE."""
        self.feedback_message = msg
        return Status.FAILURE


# ---------------------------------------------------------------------------
# Concrete leaves
# ---------------------------------------------------------------------------


class WaitAttached(EngineLeaf):
    """RUNNING until app_status()['attached'] is True; FAILURE after deadline."""

    def __init__(
        self, name: str = "WaitAttached", ctx: EngineContext = None, timeout_s: float = 30.0  # type: ignore[assignment]
    ) -> None:
        super().__init__(name=name, ctx=ctx)
        self._timeout_s = timeout_s
        self._deadline: float = 0.0

    def initialise(self) -> None:
        self._deadline = time.monotonic() + self._timeout_s

    def update(self) -> Status:
        if time.monotonic() >= self._deadline:
            return self._fail(f"WaitAttached timed out after {self._timeout_s}s")
        try:
            status = self.ctx.client.app_status()
        except NodeError as exc:
            # Transient: node not yet reachable
            self.feedback_message = str(exc)
            return Status.RUNNING
        if status.get("attached"):
            return Status.SUCCESS
        self.feedback_message = "not yet attached"
        return Status.RUNNING


class StartCapture(EngineLeaf):
    """Issue capture_start once; retry on NodeError up to deadline."""

    _DEADLINE_S: Final[float] = 10.0

    def __init__(
        self,
        name: str = "StartCapture",
        ctx: EngineContext = None,  # type: ignore[assignment]
        interval_s: float = 0.5,
    ) -> None:
        super().__init__(name=name, ctx=ctx)
        self._interval_s = interval_s
        self._deadline: float = 0.0

    def initialise(self) -> None:
        self._deadline = time.monotonic() + self._DEADLINE_S

    def update(self) -> Status:
        if time.monotonic() >= self._deadline:
            return self._fail(f"StartCapture timed out after {self._DEADLINE_S}s")
        try:
            self.ctx.client.capture_start(self._interval_s)
            return Status.SUCCESS
        except NodeError as exc:
            self.feedback_message = str(exc)
            return Status.RUNNING


class Snapshot(EngineLeaf):
    """Grab the latest frame, save PNG to evidence_dir, store in ctx.frames."""

    _DEADLINE_S: Final[float] = 15.0

    def __init__(
        self,
        name: str = "Snapshot",
        ctx: EngineContext = None,  # type: ignore[assignment]
        slot: str = "default",
    ) -> None:
        super().__init__(name=name, ctx=ctx)
        self._slot = slot
        self._deadline: float = 0.0

    def initialise(self) -> None:
        self._deadline = time.monotonic() + self._DEADLINE_S
        self.feedback_message = ""

    def update(self) -> Status:
        if time.monotonic() >= self._deadline:
            return self._fail(f"Snapshot({self._slot}) timed out after {self._DEADLINE_S}s")
        try:
            frame = self.ctx.client.capture_latest()
        except NoFrameYet as exc:
            self.feedback_message = str(exc)
            return Status.RUNNING
        except NodeError as exc:
            return self._fail(f"Snapshot({self._slot}) error: {exc}")
        out_path = self.ctx.evidence_dir / f"{self._slot}.png"
        cv2.imwrite(str(out_path), frame)
        self.ctx.frames[self._slot] = frame
        self.feedback_message = f"saved {self._slot}.png"
        return Status.SUCCESS


class ClickNorm(EngineLeaf):
    """Click at normalized (x, y); one-shot — NodeError -> FAILURE."""

    def __init__(
        self,
        name: str = "ClickNorm",
        ctx: EngineContext = None,  # type: ignore[assignment]
        x: float = 0.5,
        y: float = 0.5,
    ) -> None:
        super().__init__(name=name, ctx=ctx)
        self._x = x
        self._y = y

    def update(self) -> Status:
        try:
            self.ctx.client.click(self._x, self._y)
            return Status.SUCCESS
        except NodeError as exc:
            return self._fail(f"ClickNorm error: {exc}")


class TypeText(EngineLeaf):
    """Send one key per tick until all chars in *text* are dispatched.

    Re-entry (re-initialise) resets the index to 0, so the leaf can be
    wired into a Sequence that restarts cleanly.

    Raises ValueError in ctor if *text* contains '"' or '\\'.
    """

    _CHAR_MAP: Final = MappingProxyType({" ": "space"})

    def __init__(
        self,
        name: str = "TypeText",
        ctx: EngineContext = None,  # type: ignore[assignment]
        text: str = "",
    ) -> None:
        for bad in ('"', "\\"):
            if bad in text:
                raise ValueError(
                    f"TypeText: text must not contain {bad!r}; got {text!r}"
                )
        super().__init__(name=name, ctx=ctx)
        self._text = text
        self._index: int = 0

    def initialise(self) -> None:
        self._index = 0

    def update(self) -> Status:
        if self._index >= len(self._text):
            return Status.SUCCESS
        char = self._text[self._index]
        key_name = self._CHAR_MAP.get(char, char)
        try:
            self.ctx.client.key(key_name)
        except NodeError as exc:
            return self._fail(f"TypeText key({key_name!r}) error: {exc}")
        self._index += 1
        self.feedback_message = f"sent {self._index}/{len(self._text)} chars"
        if self._index >= len(self._text):
            return Status.SUCCESS
        return Status.RUNNING


class DrainPause(EngineLeaf):
    """RUNNING for *seconds* (control-queue drain window); then SUCCESS."""

    def __init__(
        self,
        name: str = "DrainPause",
        ctx: EngineContext = None,  # type: ignore[assignment]
        seconds: float = 1.0,
    ) -> None:
        super().__init__(name=name, ctx=ctx)
        self._seconds = seconds
        self._deadline: float = 0.0

    def initialise(self) -> None:
        self._deadline = time.monotonic() + self._seconds

    def update(self) -> Status:
        if time.monotonic() >= self._deadline:
            return Status.SUCCESS
        remaining = self._deadline - time.monotonic()
        self.feedback_message = f"{remaining:.2f}s remaining"
        return Status.RUNNING


class VerifyRegionChanged(EngineLeaf):
    """Compare an ROI between two stored frames; SUCCESS iff enough pixels changed.

    *roi* is (x0, y0, x1, y1) as normalized fractions of the frame dimensions.
    Missing slot -> FAILURE (never KeyError crash).
    """

    def __init__(
        self,
        name: str = "VerifyRegionChanged",
        ctx: EngineContext = None,  # type: ignore[assignment]
        before_slot: str = "before",
        after_slot: str = "after",
        roi: tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0),
        min_changed_pixels: int = 100,
    ) -> None:
        super().__init__(name=name, ctx=ctx)
        self._before_slot = before_slot
        self._after_slot = after_slot
        self._roi = roi
        self._min_changed_pixels = min_changed_pixels

    def update(self) -> Status:
        before = self.ctx.frames.get(self._before_slot)
        after = self.ctx.frames.get(self._after_slot)
        if before is None:
            return self._fail(f"VerifyRegionChanged: slot {self._before_slot!r} missing")
        if after is None:
            return self._fail(f"VerifyRegionChanged: slot {self._after_slot!r} missing")

        h_b, w_b = before.shape[:2]
        h_a, w_a = after.shape[:2]
        x0_n, y0_n, x1_n, y1_n = self._roi

        # Use the smaller frame's dimensions for clipping
        h, w = min(h_b, h_a), min(w_b, w_a)
        x0 = int(x0_n * w)
        y0 = int(y0_n * h)
        x1 = int(x1_n * w)
        y1 = int(y1_n * h)

        if x1 <= x0 or y1 <= y0:
            return self._fail(
                f"empty ROI after scaling: x0={x0} x1={x1} y0={y0} y1={y1} "
                f"(roi={self._roi}, frame={w}x{h})"
            )

        roi_before = before[y0:y1, x0:x1]
        roi_after = after[y0:y1, x0:x1]

        gray_before = cv2.cvtColor(roi_before, cv2.COLOR_BGR2GRAY)
        gray_after = cv2.cvtColor(roi_after, cv2.COLOR_BGR2GRAY)

        diff = cv2.absdiff(gray_before, gray_after)
        changed_count = int(np.count_nonzero(diff > _PIXEL_DIFF_THRESH))

        if changed_count >= self._min_changed_pixels:
            self.feedback_message = f"{changed_count} pixels changed (>= {self._min_changed_pixels})"
            return Status.SUCCESS
        return self._fail(
            f"VerifyRegionChanged: only {changed_count} pixels changed "
            f"(need {self._min_changed_pixels})"
        )
