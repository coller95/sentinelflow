"""Orchestrator server entrypoint.

Runs the centralized SentinelFlow orchestrator API that keeps track of cluster nodes
by UUID and human label.

Tech stack matches the cluster server: FastAPI + Hypercorn.
"""

import os
import sys
from pathlib import Path
from typing import Any, cast

# Ensure project root is on sys.path so `import Src.*` works regardless of CWD.
_PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from Src.orchestrator.backend import app  # noqa: E402
from Src.orchestrator.services import OrchestratorServices  # noqa: E402


def main() -> int:
    svc = OrchestratorServices()
    try:
        from Src.orchestrator.backend import _STATE_PATH  # type: ignore
        svc.LoadState(_STATE_PATH)
    except FileNotFoundError:
        pass
    except Exception as exc:
        print(f"[orchestrator_state] Load failed: {exc}")

    app.state.services = svc

    port = int(os.getenv("SENTINELFLOW_ORCH_PORT", os.getenv("PORT", "8010")))

    print(f"[orchestrator] Starting server on port {port}...")
    import asyncio
    import signal
    import threading
    from hypercorn.config import Config  # type: ignore
    from hypercorn.asyncio import serve  # type: ignore

    async def run_server():
        shutdown_trigger = asyncio.Event()
        loop = asyncio.get_running_loop()

        def _force_exit():
            print("[orchestrator] Shutdown timed out. Forcing exit.")
            os._exit(0)

        def _do_shutdown(*args):
            print(f"[orchestrator] Shutdown signal received. Shutting down services...")
            # 1. Break application loops (SSE, monitor)
            svc.Shutdown()
            # 2. Trigger Hypercorn shutdown
            loop.call_soon_threadsafe(shutdown_trigger.set)
            
            # 3. Failsafe: Force exit if graceful shutdown takes too long (2s)
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
                print("[orchestrator] Warning: win32api not found, falling back to signal.")

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
        print("[orchestrator] Interrupted (KeyboardInterrupt/SystemExit).")
    except Exception as e:
        print(f"[orchestrator] Unexpected error: {e}")
    finally:
        print("[orchestrator] Entering finally block. Ensuring services are stopped...")
        svc.Shutdown()
        print("[orchestrator] Services shutdown complete.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
