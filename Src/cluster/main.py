"""
SentinelFlow Main Dashboard
Description: application for window automation.
Author: SentinelFlow Team
Version: 1.0.0
"""
# =============================================================================
# IMPORTS
# =============================================================================
# Standard library imports

import sys
import os
from pathlib import Path
from typing import Any, cast

# Ensure project root is on sys.path so `import Src.*` works regardless of CWD.
_PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from Src.cluster.backend import app
from Src.cluster.services import ControllerServices

# =============================================================================
# MAIN ENTRY POINT
# =============================================================================
def main() -> int:
    # Wire Services into the backend app state so API handlers can access it.
    from Src.infrastructure.media.cv_handler import CvComputerVision

    # OS Detection
    if sys.platform == "win32":
        from Src.infrastructure.os.windows_handler import WindowsWindowManager, WindowsScreenCapturer, WindowsInputController
        win_mgr = WindowsWindowManager()
        capturer = WindowsScreenCapturer()
        input_ctrl = WindowsInputController(win_mgr)
    else:
        print(f"[Main] Running on non-Windows platform ({sys.platform}). Using Mock handlers.")
        from Src.infrastructure.os.mock_handler import MockWindowManager, MockScreenCapturer, MockInputController
        win_mgr = MockWindowManager()
        capturer = MockScreenCapturer()
        input_ctrl = MockInputController()

    svc = ControllerServices(
        window_manager=win_mgr,
        screen_capturer=capturer,
        input_controller=input_ctrl,
        computer_vision=CvComputerVision(),
    )
    try:
        # Backend.py will also lazy-load if needed, but load here for predictable startup.
        from Src.cluster.backend import _STATE_PATH  # type: ignore
        svc.LoadState(_STATE_PATH)
    except FileNotFoundError:
        pass
    except Exception as exc:
        print(f"[state] Load failed: {exc}")

    app.state.services = svc
    # Run FastAPI backend
    port = int(os.getenv("SENTINELFLOW_PORT", os.getenv("PORT", "8000")))

    print(f"[cluster] Starting server on port {port}...")
    import asyncio
    from hypercorn.config import Config  # type: ignore
    from hypercorn.asyncio import serve  # type: ignore

    config = Config()
    config.bind = [f"0.0.0.0:{port}"]
    asyncio.run(cast(Any, serve)(cast(Any, app), config))
    
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
