"""Orchestrator server entrypoint.

Runs the centralized SentinelFlow orchestrator API that keeps track of cluster nodes
by UUID and human label.

Tech stack matches the cluster server: FastAPI + Uvicorn.
"""

import os
import sys
from pathlib import Path

import uvicorn

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
    print(f"[orchestrator] UI: http://127.0.0.1:{port}/")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
