from __future__ import annotations

from typing import Any, List, Optional, Protocol

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget,
    QListWidgetItem, QFileDialog, QMessageBox, QLineEdit, QSizePolicy, QDialog
)

from Src.Models import EventItem
from Src.Ui.UiShared import (
    BUTTON_STYLE_RUNNING,
    BUTTON_STYLE_STOPPED,
    HotkeyCaptureDialog,
)


class DashboardViewModelProtocol(Protocol):
    EventItemAddedSignal: Any
    EventItemRemovedSignal: Any
    EventItemSelectedSignal: Any
    EventItemChangedSignal: Any
    EventExecutionStateChangedSignal: Any
    EventExecutionStateHotkeyChangedSignal: Any

    @property
    def SelectedEventItem(self) -> Optional[EventItem]: ...

    @SelectedEventItem.setter
    def SelectedEventItem(self, event: Optional[EventItem]) -> None: ...

    def AddEvent(self) -> None: ...
    def RemoveEvent(self) -> None: ...
    def SaveState(self, filePath: str) -> None: ...
    def LoadState(self, filePath: str) -> None: ...
    def ToggleSentinelFlow(self) -> None: ...
    def SetSentinelFlowHotkey(self, virtualKeyCodes: List[int]) -> None: ...
    def SetEventEnabled(self, eventItem: EventItem, isEnabled: bool) -> None: ...
    def KeyNameFromVk(self, virtualKeyCode: int) -> str: ...

class LeftPanelWidget(QWidget):    
    def __init__(self, viewModel: DashboardViewModelProtocol) -> None:
        super().__init__()
        self.ViewModel = viewModel
        self._setupLeftPanel()
        self._wireUpBindings()

    def _setupLeftPanel(self) -> None:

        layout = QVBoxLayout(self)
        buttonLayout = QHBoxLayout()
        
        self.addEventButton = QPushButton("+")
        self.removeEventButton = QPushButton("-")
        self.addEventButton.setFixedWidth(30)
        self.removeEventButton.setFixedWidth(30)
        
        self.saveEventButton = QPushButton("Save")
        self.loadEventButton = QPushButton("Load")
        self.saveEventButton.setFixedWidth(40)
        self.loadEventButton.setFixedWidth(40)
        
        buttonLayout.addWidget(self.addEventButton)
        buttonLayout.addWidget(self.removeEventButton)
        buttonLayout.addStretch()
        buttonLayout.addWidget(self.saveEventButton)
        buttonLayout.addWidget(self.loadEventButton)
        
        self.eventListWidget = QListWidget()
        self.eventListWidget.setFixedWidth(200)
        self.eventListWidget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        
        layout.addLayout(buttonLayout)
        layout.addWidget(self.eventListWidget)
        
        # Sentinel Control
        self.EventExecutionStateButton = QPushButton("Stop Sentinel")
        self.EventExecutionStateButton.setStyleSheet(BUTTON_STYLE_RUNNING)
        layout.addWidget(self.EventExecutionStateButton)
        
        # for Sentinel Control Hotkey capture dialog
        self.EventExecutionStateHotkeyEdit = QLineEdit()
        self.EventExecutionStateHotkeyEdit.setReadOnly(True)
        self.EventExecutionStateHotkeyButton = QPushButton("Capture Sentinel Hotkey")
        layout.addWidget(self.EventExecutionStateHotkeyEdit)
        layout.addWidget(self.EventExecutionStateHotkeyButton)

    def _wireUpBindings(self) -> None:
        # to view model
        self.addEventButton.clicked.connect(self._onEventAddedClicked)
        self.removeEventButton.clicked.connect(self._onRemoveEventClicked)
        self.saveEventButton.clicked.connect(self._onSaveEventClicked)
        self.loadEventButton.clicked.connect(self._onLoadEventClicked)
        self.eventListWidget.currentItemChanged.connect(self._onEventListCurrentItemChanged)
        self.EventExecutionStateButton.clicked.connect(self._onEventExecutionStateClicked)
        self.EventExecutionStateHotkeyButton.clicked.connect(self._onEventExecutionStateHotkeyClicked)

        # Property Editing
        self.eventListWidget.itemChanged.connect(self._onEventItemChanged)

        # from view model
        self.ViewModel.EventItemAddedSignal.connect(self._onEventAddedSignal)
        self.ViewModel.EventItemRemovedSignal.connect(self._onRemoveEventSignal)
        self.ViewModel.EventItemSelectedSignal.connect(self._onEventItemSelectedSignal)
        self.ViewModel.EventItemChangedSignal.connect(self._onEventItemChangedSignal)
        self.ViewModel.EventExecutionStateChangedSignal.connect(self._onEventExecutionStateChangedSignal)
        self.ViewModel.EventExecutionStateHotkeyChangedSignal.connect(self._onEventExecutionStateHotkeyChangedSignal)

    def _onEventAddedClicked(self) -> None:
        self.ViewModel.AddEvent()

    def _onRemoveEventClicked(self) -> None:
        self.ViewModel.RemoveEvent()

    def _onSaveEventClicked(self) -> None:
        filePath, _ = QFileDialog.getSaveFileName(
            self,
            "Save Macro Configuration",
            "",
            "Data Files (*.dat);;Pickle Files (*.pkl);;All Files (*)"
        )
        if filePath:
            try:
                self.ViewModel.SaveState(filePath)
                QMessageBox.information(self, "Success", "Configuration saved successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save file: {e}")

    def _onLoadEventClicked(self) -> None:
        filePath, _ = QFileDialog.getOpenFileName(
            self,
            "Load Macro Configuration",
            "",
            "Data Files (*.dat);;Pickle Files (*.pkl);;All Files (*)"
        )
        if filePath:
            try:
                self.eventListWidget.clear()
                self.ViewModel.LoadState(filePath)
                QMessageBox.information(self, "Success", "Configuration loaded successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load file: {e}")

    def _onEventListCurrentItemChanged(self, current: QListWidgetItem, previous: QListWidgetItem) -> None:
        eventItem: EventItem = current.data(Qt.ItemDataRole.UserRole)
        self.ViewModel.SelectedEventItem = eventItem

    def _onEventExecutionStateClicked(self) -> None:
        self.ViewModel.ToggleSentinelFlow()

    def _onEventExecutionStateHotkeyClicked(self) -> None:
        dialog = HotkeyCaptureDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.ViewModel.SetSentinelFlowHotkey(dialog.CapturedVirtualKeyCodes)
    
    # Property Editing
    def _onEventItemChanged(self, item: QListWidgetItem) -> None:
        eventItem: EventItem = item.data(Qt.ItemDataRole.UserRole)
        isEnabled = item.checkState() == Qt.CheckState.Checked
        self.ViewModel.SetEventEnabled(eventItem, isEnabled)

    # from view model
    def _onEventAddedSignal(self, eventItem: EventItem) -> None:
        item = QListWidgetItem(eventItem.Name)
        item.setData(Qt.ItemDataRole.UserRole, eventItem)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Checked if eventItem.IsEnabled else Qt.CheckState.Unchecked)
        self.eventListWidget.addItem(item)

    def _onRemoveEventSignal(self, index: int) -> None:
        self.eventListWidget.takeItem(index)

    def _onEventItemSelectedSignal(self, eventItem: EventItem) -> None:
        self.eventListWidget.currentItem().setText(eventItem.Name)

    def _onEventItemChangedSignal(self, eventItem: EventItem) -> None:
        for index in range(self.eventListWidget.count()):
            item = self.eventListWidget.item(index)
            storedEventItem: EventItem = item.data(Qt.ItemDataRole.UserRole)
            if storedEventItem == eventItem:
                item.setText(eventItem.Name)
                item.setCheckState(Qt.CheckState.Checked if eventItem.IsEnabled else Qt.CheckState.Unchecked)
                break

    def _onEventExecutionStateChangedSignal(self, isRunning: bool) -> None:
        if isRunning:
            self.EventExecutionStateButton.setText("Stop Sentinel")
            self.EventExecutionStateButton.setStyleSheet(BUTTON_STYLE_RUNNING)
        else:
            self.EventExecutionStateButton.setText("Start Sentinel")
            self.EventExecutionStateButton.setStyleSheet(BUTTON_STYLE_STOPPED)

    def _onEventExecutionStateHotkeyChangedSignal(self, hotkeyList: List[int]) -> None:
        self.EventExecutionStateHotkeyEdit.setText(", ".join(map(self.ViewModel.KeyNameFromVk, hotkeyList)))
