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

# Third-party imports for backend
import uvicorn

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
    svc = ControllerServices()
    try:
        # Backend.py will also lazy-load if needed, but load here for predictable startup.
        from Src.cluster.backend import _STATE_PATH  # type: ignore
        svc.LoadState(_STATE_PATH)
    except FileNotFoundError:
        pass
    except Exception as exc:
        print(f"[state] Load failed: {exc}")

    app.state.services = svc
    # Run FastAPI backend in the main thread
    port = int(os.getenv("SENTINELFLOW_PORT", os.getenv("PORT", "8000")))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
