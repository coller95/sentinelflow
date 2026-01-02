from Src.DashboardViewModel import DashboardViewModel
from PySide6.QtWidgets import QWidget, QHBoxLayout
from PySide6.QtGui import QCloseEvent

from Src.Ui.LeftPanelWidget import LeftPanelWidget
from Src.Ui.CenterPanelWidget import CenterPanelWidget
from Src.Ui.RightPanelWidget import RightPanelWidget
class DashboardView(QWidget):
    def __init__(self, viewModel: DashboardViewModel) -> None:
        super().__init__()
        self.ViewModel = viewModel
        self._initializeComponents()

    def _initializeComponents(self) -> None:
        self.setWindowTitle("SentinelFlow Dashboard")
        self.resize(1000, 650)
        self.mainLayout = QHBoxLayout(self)
        self.mainLayout.setContentsMargins(0, 0, 0, 0)
        self.mainLayout.setSpacing(5)
        self.leftPanel = LeftPanelWidget(self.ViewModel)
        self.centerPanel = CenterPanelWidget(self.ViewModel)
        self.rightPanel = RightPanelWidget(self.ViewModel)
        self.mainLayout.addWidget(self.leftPanel, 0)
        self.mainLayout.addWidget(self.centerPanel, 1)
        self.mainLayout.addWidget(self.rightPanel, 0)

    def closeEvent(self, event: QCloseEvent) -> None:
        self.ViewModel.StopCapture()
        self.ViewModel.StopSentinel()
        super().closeEvent(event)
