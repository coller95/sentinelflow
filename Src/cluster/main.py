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
    from Src.cluster.backend import make_os_handlers

    # OS Detection (shared factory: win32 / linux / mock).
    win_mgr, capturer, input_ctrl = make_os_handlers()

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
    import signal
    import threading
    from hypercorn.config import Config  # type: ignore
    from hypercorn.asyncio import serve  # type: ignore

    async def run_server():
        shutdown_trigger = asyncio.Event()
        loop = asyncio.get_running_loop()

        def _install_exception_handler(target_loop):
            def _handler(loop_ref, context):
                exc = context.get("exception")
                if isinstance(exc, (ConnectionResetError, ConnectionAbortedError)):
                    return
                if isinstance(exc, OSError) and getattr(exc, "winerror", None) in (10053, 10054):
                    return
                message = str(context.get("message", ""))
                if "ConnectionResetError" in message or "ConnectionAbortedError" in message:
                    return
                loop_ref.default_exception_handler(context)

            target_loop.set_exception_handler(_handler)

        _install_exception_handler(loop)

        def _force_exit():
            print("[cluster] Shutdown timed out. Forcing exit.")
            os._exit(0)

        def _do_shutdown(*args):
            print(f"[cluster] Shutdown signal received. Shutting down services...")
            # 1. Break application loops (SSE, workers)
            svc.Shutdown()
            # 2. Trigger Hypercorn shutdown
            loop.call_soon_threadsafe(shutdown_trigger.set)
            
            # 3. Failsafe: Force exit if graceful shutdown takes too long (2s)
            # This prevents the process from hanging if Hypercorn waits for "stuck" connections.
            t = threading.Timer(2.0, _force_exit)
            t.daemon = True
            t.start()
            return True

        # Windows: SetConsoleCtrlHandler is more reliable for Ctrl+C than signal.signal with asyncio
        if sys.platform == "win32":
            try:
                import win32api
                win32api.SetConsoleCtrlHandler(_do_shutdown, True)
            except ImportError:
                print("[cluster] Warning: win32api not found, falling back to signal.")

        # Universal fallback (Linux, or if win32api fails)
        try:
            signal.signal(signal.SIGINT, lambda s, f: _do_shutdown())
            signal.signal(signal.SIGTERM, lambda s, f: _do_shutdown())
        except ValueError:
            pass

        config = Config()
        config.bind = [f"0.0.0.0:{port}"]
        config.shutdown_trigger = shutdown_trigger.wait

        await cast(Any, serve)(cast(Any, app), config)

    try:
        asyncio.run(run_server())
    except (KeyboardInterrupt, SystemExit):
        print("[cluster] Interrupted (KeyboardInterrupt/SystemExit).")
    except Exception as e:
        print(f"[cluster] Unexpected error: {e}")
    finally:
        print("[cluster] Entering finally block. Ensuring services are stopped...")
        svc.Shutdown()
        print("[cluster] Services shutdown complete.")
    
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
