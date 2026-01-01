"""
SentinelFlow Main Dashboard
Description: PySide6 GUI application for window automation using MVVM pattern.
Author: SentinelFlow Team
Version: 1.0.0
"""
# =============================================================================
# IMPORTS
# =============================================================================
# Standard library imports
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path so `import Src.*` works regardless of CWD.
# (Helps when you later move this entrypoint into a better `app/` directory.)
_PROJECT_ROOT = str(Path(__file__).resolve().parents[1])  # ...\sentinelflow
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Third-party imports
from PySide6.QtWidgets import QApplication
# Local application imports
from Src.DashboardViewModel import DashboardViewModel
from Src.DashboardView import DashboardView

# =============================================================================
# CONSTANTS AND GLOBAL CONFIGURATION
# =============================================================================
# High DPI Scaling setup
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
# UI styling constants are in Src.UiShared

# =============================================================================
# MAIN ENTRY POINT
# =============================================================================
def main() -> int:
    application = QApplication(sys.argv)

    # MVVM Initialization
    viewModel = DashboardViewModel()
    view = DashboardView(viewModel)
    view.show()

    return application.exec()

if __name__ == "__main__":
    raise SystemExit(main())