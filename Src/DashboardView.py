from Src.DashboardViewModel import DashboardViewModel
from PySide6.QtWidgets import QWidget, QHBoxLayout
from PySide6.QtGui import QCloseEvent

from Src.Ui.LeftPanelWidget import LeftPanelWidget
from Src.Ui.CenterPanelWidget import CenterPanelWidget
from Src.Ui.RightPanelWidget import RightPanelWidget
class DashboardView(QWidget):
    """
    Main UI view for the SentinelFlow dashboard.
    
    Properties:
        ViewModel: Reference to the dashboard view model
    """
    def __init__(self, viewModel: DashboardViewModel) -> None:
        """
        Initialize the dashboard view.
        
        Args:
            viewModel: View model for this view
        """
        super().__init__()
        self.ViewModel = viewModel
        self._initializeComponents()

    def _initializeComponents(self) -> None:
        """Initialize all UI components."""
        self.setWindowTitle("SentinelFlow Dashboard")
        self.resize(1000, 650)
        
        self.mainLayout = QHBoxLayout(self)
        self.mainLayout.setContentsMargins(0, 0, 0, 0)
        self.mainLayout.setSpacing(5)
        
        # Panels
        self.leftPanel = LeftPanelWidget(self.ViewModel)
        self.centerPanel = CenterPanelWidget(self.ViewModel)
        self.rightPanel = RightPanelWidget(self.ViewModel)
        self.mainLayout.addWidget(self.leftPanel, 0)
        self.mainLayout.addWidget(self.centerPanel, 1)
        self.mainLayout.addWidget(self.rightPanel, 0)

    def closeEvent(self, event: QCloseEvent) -> None:
        """
        Handle window close event.
        
        Args:
            event: Close event
        """
        # Stop background work before exiting (important once code is split into app/core dirs).
        self.ViewModel.StopCapture()
        self.ViewModel.StopSentinel()
        super().closeEvent(event)
