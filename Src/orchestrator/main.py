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
    from hypercorn.config import Config  # type: ignore
    from hypercorn.asyncio import serve  # type: ignore

    config = Config()
    config.bind = [f"0.0.0.0:{port}"]
    asyncio.run(cast(Any, serve)(cast(Any, app), config))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
