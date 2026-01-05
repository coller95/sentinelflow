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
from pathlib import Path

# Third-party imports for backend
import uvicorn

# Ensure project root is on sys.path so `import Src.*` works regardless of CWD.
_PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from Src.Backend import app

# =============================================================================
# MAIN ENTRY POINT
# =============================================================================
def main() -> int:
    # Run FastAPI backend in the main thread
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())