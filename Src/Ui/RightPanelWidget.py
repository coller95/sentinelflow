from typing import Any, Dict, Optional, Protocol, cast
import numpy as np
import cv2
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QListWidget, QListWidgetItem, QCheckBox, QInputDialog, QMessageBox, 
    QDialog
)
from Src.Models import RectangleRegion, ActivationType, InputType, ActionItem, ConditionItem, EventItem
from Src.Ui.UiShared import (
    HotkeyCaptureDialog,
    CropperWidget,
)

class DashboardViewModelProtocol(Protocol):
    EventItemSelectedSignal: Any
    MatchScoreUpdated: Any

    @property
    def SelectedEventItem(self) -> Optional[EventItem]: ...

    @SelectedEventItem.setter
    def SelectedEventItem(self, event: Optional[EventItem]) -> None: ...

    def GetLastLiveImage(self) -> Optional[Any]: ...

    def UpdateSelectedEventName(self, name: str) -> None: ...
    def UpdateSelectedActivationType(self, activationType: ActivationType) -> None: ...
    def UpdateSelectedActivationHotkey(self, virtualKeyCodes: list[int]) -> None: ...
    def UpdateSelectedLoopCount(self, loopCount: int) -> None: ...
    def UpdateSelectedLoopIntervalMs(self, intervalMs: int) -> None: ...
    def UpdateSelectedThreshold(self, threshold: float) -> None: ...
    def UpdateSelectedTriggerOnThresholdExceed(self, isEnabled: bool) -> None: ...
    def UpdateSelectedRetriggerTimeMs(self, retriggerTimeMs: float) -> None: ...
    def SetSelectedTemplateAndRoi(
        self,
        templateImage: np.ndarray[Any, Any],
        roi: RectangleRegion,
    ) -> None: ...

    def GetConditionLibrary(self) -> list[ConditionItem]: ...
    def CreateCondition(self, name: str) -> ConditionItem: ...
    def RenameCondition(self, conditionUuid: str, name: str) -> None: ...
    def SetSelectedEventCondition(self, conditionUuid: str) -> None: ...
    def AddSelectedMouseStepFromCapturedPosition(self) -> None: ...
    def AddSelectedKeyboardStep(self, virtualKeyCodes: list[int]) -> None: ...
    def AddSelectedDelayStep(self, milliseconds: int) -> None: ...
    def MoveSelectedStep(self, fromIndex: int, toIndex: int) -> None: ...
    def RemoveSelectedStep(self, index: int) -> None: ...
    def KeyNameFromVk(self, virtualKeyCode: int) -> str: ...

class RightPanelWidget(QWidget):
    def __init__(self, viewModel : DashboardViewModelProtocol) -> None:
        super().__init__()
        self.ViewModel = viewModel
        self._isUpdatingConditionDropdown = False
        self._setupRightPanel()
        self._wireUpBindings()

    def _setupRightPanel(self) -> None:
        self.setFixedWidth(350)
        
        layout = QVBoxLayout(self)
        self.eventSettingsHeader = QLabel("<b>Event Settings</b>")
        
        # Event Properties
        self.eventNameEdit = QLineEdit()
        self.eventNameEdit.setEnabled(False)
        
        self.activationDropdown = QComboBox()
        self.activationDropdown.setEnabled(False)
        self.activationDropdown.addItems([activationType.name for activationType in ActivationType])
        
        # hotkey capture widget
        self.activationHotkeyWidget = QWidget()
        self.activationHotkeyLayout = QHBoxLayout()
        self.activationHotkeyLayout.addWidget(QLabel("Hotkey:"))
        self.activationHotkeyEdit = QLineEdit()
        self.activationHotkeyEdit.setReadOnly(True)
        self.activationHotkeyLayout.addWidget(self.activationHotkeyEdit)
        self.activationHotkeyButton = QPushButton("Capture")
        self.activationHotkeyLayout.addWidget(self.activationHotkeyButton)
        self.activationHotkeyButton.setEnabled(False)
        self.activationHotkeyWidget.setLayout(self.activationHotkeyLayout)
        self.activationHotkeyWidget.hide()
        
        # loop and interval widgets
        self.loopWidget = QWidget()
        self.loopWidgetLayout = QHBoxLayout()
        
        self.loopCountLayout = QVBoxLayout()
        self.loopCountLabel = QLabel("Count:")
        self.loopCountEdit = QLineEdit("1")
        self.loopCountLayout.addWidget(self.loopCountLabel)
        self.loopCountLayout.addWidget(self.loopCountEdit)
        
        self.loopIntervalLayout = QVBoxLayout()
        self.loopIntervalLabel = QLabel("Interval (ms):")
        self.loopIntervalEdit = QLineEdit("1000")
        self.loopIntervalLayout.addWidget(self.loopIntervalLabel)
        self.loopIntervalLayout.addWidget(self.loopIntervalEdit)
        
        self.loopWidgetLayout.addLayout(self.loopCountLayout)
        self.loopWidgetLayout.addLayout(self.loopIntervalLayout)
        self.loopWidget.setLayout(self.loopWidgetLayout)
        self.loopCountEdit.setEnabled(False)
        self.loopIntervalEdit.setEnabled(False)
        self.loopWidget.hide()

        # Condition dropdown (shared ConditionItem library)
        self.conditionWidget = QWidget()
        self.conditionWidgetLayout = QHBoxLayout()
        self.conditionWidgetLayout.setContentsMargins(0, 0, 0, 0)
        self.conditionWidgetLayout.addWidget(QLabel("Condition:"))
        self.conditionDropdown = QComboBox()
        self.conditionDropdown.setEnabled(False)
        self.conditionWidgetLayout.addWidget(self.conditionDropdown)
        self.conditionWidget.setLayout(self.conditionWidgetLayout)
        self.conditionWidget.hide()
        
        # Roi widget
        self.roiWidget = QWidget()
        self.roiWidgetLayout = QHBoxLayout()
        self.roiWidgetLayoutInner = QVBoxLayout()
        
        self.roiXEditLayout = QHBoxLayout()
        self.roiYEditLayout = QHBoxLayout()
        self.roiWEditLayout = QHBoxLayout()
        self.roiHEditLayout = QHBoxLayout()
        
        self.roiXEdit = QLineEdit("0.0")
        self.roiYEdit = QLineEdit("0.0")
        self.roiWEdit = QLineEdit("1.0")
        self.roiHEdit = QLineEdit("1.0")
        
        self.roiXEditLayout.addWidget(QLabel("X:"))
        self.roiXEditLayout.addWidget(self.roiXEdit)
        self.roiYEditLayout.addWidget(QLabel("Y:"))
        self.roiYEditLayout.addWidget(self.roiYEdit)
        self.roiWEditLayout.addWidget(QLabel("W:"))
        self.roiWEditLayout.addWidget(self.roiWEdit)
        self.roiHEditLayout.addWidget(QLabel("H:"))
        self.roiHEditLayout.addWidget(self.roiHEdit)
        
        self.roiWidgetLayoutInner.addWidget(QLabel("Roi:"))
        self.roiWidgetLayoutInner.addLayout(self.roiXEditLayout)
        self.roiWidgetLayoutInner.addLayout(self.roiYEditLayout)
        self.roiWidgetLayoutInner.addLayout(self.roiWEditLayout)
        self.roiWidgetLayoutInner.addLayout(self.roiHEditLayout)
        
        self.roiButtonLayout = QVBoxLayout()
        self.roiButtonLayout.setContentsMargins(0, 0, 0, 0)
        self.roiButton = QPushButton("Select from Image")
        self.roiButton.setFixedSize(150, 150)
        self.roiButtonLayout.addWidget(self.roiButton)
        
        self.roiWidgetLayout.addLayout(self.roiWidgetLayoutInner)
        self.roiWidgetLayout.addLayout(self.roiButtonLayout)
        self.roiButton.setEnabled(False)
        self.roiWidget.setLayout(self.roiWidgetLayout)
        
        self.roiXEdit.setReadOnly(True)
        self.roiYEdit.setReadOnly(True)
        self.roiWEdit.setReadOnly(True)
        self.roiHEdit.setReadOnly(True)
        self.roiWidget.hide()
        
        # Threshold widget
        self.thresholdWidget = QWidget()
        self.thresholdWidgetLayout = QVBoxLayout()
        
        self.thresholdWidgetMatchScoreLayout = QHBoxLayout()
        self.thresholdMatchScoreLabel = QLabel("0.0")
        self.thresholdWidgetMatchScoreLayout.addWidget(QLabel("Match Score:"))
        self.thresholdWidgetMatchScoreLayout.addWidget(self.thresholdMatchScoreLabel)
        
        self.thresholdWidgetMatchScoreBtnLayout = QHBoxLayout()
        self.thresholdMatchScoreCopyButton = QPushButton("↓")
        self.thresholdMatchScoreCopyButton.setFixedWidth(30)
        self.thresholdWidgetMatchScoreBtnLayout.addWidget(self.thresholdMatchScoreCopyButton)
        
        self.thresholdWidgetThresholdLayout = QHBoxLayout()
        self.thresholdWidgetThresholdLayout.addWidget(QLabel("Threshold:"))
        self.thresholdEdit = QLineEdit("0.99")
        self.thresholdWidgetThresholdLayout.addWidget(self.thresholdEdit)
        
        self.thresholdWidgetLayout.addLayout(self.thresholdWidgetMatchScoreLayout)
        self.thresholdWidgetLayout.addLayout(self.thresholdWidgetMatchScoreBtnLayout)
        self.thresholdWidgetLayout.addLayout(self.thresholdWidgetThresholdLayout)
        self.thresholdWidget.setLayout(self.thresholdWidgetLayout)
        self.thresholdEdit.setEnabled(False)
        self.thresholdWidget.hide()
        
        # Trigger Type Specific Widgets
        self.triggerOnThresholdExceedLayout = QHBoxLayout()
        self.triggerOnThresholdExceedWidget = QWidget()
        self.triggerOnThresholdExceedCheckbox = QCheckBox("Trigger When Threshold Exceed")
        self.triggerOnThresholdExceedCheckbox.setEnabled(False)
        self.triggerOnThresholdExceedLayout.addWidget(self.triggerOnThresholdExceedCheckbox)
        self.triggerOnThresholdExceedWidget.setLayout(self.triggerOnThresholdExceedLayout)
        self.triggerOnThresholdExceedWidget.hide()

        # Retrigger Time Widget
        self.retriggerTimeWidget = QWidget()
        self.retriggerTimeLayout = QHBoxLayout()
        self.retriggerTimeLabel = QLabel("Retrigger Time (ms):")
        self.retriggerTimeEdit = QLineEdit("2000.0")
        self.retriggerTimeEdit.setEnabled(False)
        self.retriggerTimeLayout.addWidget(self.retriggerTimeLabel)
        self.retriggerTimeLayout.addWidget(self.retriggerTimeEdit)
        self.retriggerTimeWidget.setLayout(self.retriggerTimeLayout)
        self.retriggerTimeWidget.hide()
        
        # Action Sequence Properties
        self.actionNameLabel = QLabel("<b>Action Sequence</b>")
        
        # The actual list of MacroSteps
        self.macroStepListWidgetLayout = QHBoxLayout()
        self.macroStepListWidget = QListWidget()
        self.macroStepListWidget.setMinimumHeight(200)
        
        self.buttonMoveLayout = QVBoxLayout()
        self.buttonMoveUp = QPushButton("↑")
        self.buttonMoveDown = QPushButton("↓")
        self.buttonMoveUp.setFixedWidth(30)
        self.buttonMoveDown.setFixedWidth(30)
        self.buttonMoveUp.setEnabled(False)
        self.buttonMoveDown.setEnabled(False)
        
        self.macroStepListWidgetLayout.addWidget(self.macroStepListWidget)
        self.buttonMoveLayout.addWidget(self.buttonMoveUp)
        self.buttonMoveLayout.addWidget(self.buttonMoveDown)
        self.macroStepListWidgetLayout.addLayout(self.buttonMoveLayout)
        
        self.stepDropDown = QComboBox()
        self.stepDropDown.addItems([inputType.name for inputType in InputType])
        self.stepDropDown.setEnabled(False)
        
        # Buttons for Step Management
        stepButtonLayout = QHBoxLayout()
        self.addStepButton = QPushButton("Add Step")
        self.deleteStepButton = QPushButton("Remove Step")
        self.addStepButton.setEnabled(False)
        self.deleteStepButton.setEnabled(False)
        
        stepButtonLayout.addWidget(self.addStepButton)
        stepButtonLayout.addWidget(self.deleteStepButton)
        
        # Add to Layout
        layout.addWidget(self.eventSettingsHeader)
        layout.addWidget(QLabel("Event Name:"))
        layout.addWidget(self.eventNameEdit)
        layout.addWidget(QLabel("Trigger Type:"))
        layout.addWidget(self.activationDropdown)
        layout.addWidget(self.activationHotkeyWidget)
        layout.addWidget(self.loopWidget)
        layout.addWidget(self.conditionWidget)
        layout.addWidget(self.roiWidget)
        layout.addWidget(self.thresholdWidget)
        layout.addWidget(self.triggerOnThresholdExceedWidget)
        layout.addWidget(self.retriggerTimeWidget)
        layout.addWidget(self.actionNameLabel)
        layout.addLayout(self.macroStepListWidgetLayout)
        layout.addWidget(self.stepDropDown)
        layout.addLayout(stepButtonLayout)
        layout.addStretch()

    def _wireUpBindings(self) -> None:
        # --- View to ViewModel ---
        self.buttonMoveUp.clicked.connect(lambda: self._moveStep(-1))
        self.buttonMoveDown.clicked.connect(lambda: self._moveStep(1))
        
        self.addStepButton.clicked.connect(self._onAddStepClicked)
        self.deleteStepButton.clicked.connect(self._onRemoveStepClicked)
        
        self.activationHotkeyButton.clicked.connect(self._onCaptureHotkey)
        self.roiButton.clicked.connect(self._onSelectRoi)
        self.conditionDropdown.currentIndexChanged.connect(self._onCommitConditionSelection)
        # Interaction
        self.thresholdMatchScoreCopyButton.clicked.connect(self._onCopyMatchScoreToThreshold)
        
        # Property Editing
        self.eventNameEdit.editingFinished.connect(self._onCommitEventName)
        self.activationDropdown.currentIndexChanged.connect(self._onCommitActivationType)
        
        self.loopCountEdit.editingFinished.connect(self._onCommitLoopCount)
        self.loopIntervalEdit.editingFinished.connect(self._onCommitLoopInterval)
        
        self.thresholdEdit.editingFinished.connect(self._onCommitThreshold)
        self.triggerOnThresholdExceedCheckbox.stateChanged.connect(self._onCommitTriggerOnThresholdExceed)
        self.retriggerTimeEdit.editingFinished.connect(self._onCommitRetriggerTime)

        # --- ViewModel to View ---
        self.ViewModel.EventItemSelectedSignal.connect(self._onEventItemSelectedSignal)
        self.ViewModel.MatchScoreUpdated.connect(self._updateUiEventMatchScore)

    def _moveStep(self, direction: int) -> None:
        currentRow = self.macroStepListWidget.currentRow()
        if currentRow == -1:
            return
            
        targetRow = currentRow + direction
        if targetRow < 0 or targetRow >= self.macroStepListWidget.count():
            return
            
        eventItem = self.ViewModel.SelectedEventItem
        if not eventItem:
            return
            
        self.ViewModel.MoveSelectedStep(currentRow, targetRow)
        
        item = self.macroStepListWidget.takeItem(currentRow)
        self.macroStepListWidget.insertItem(targetRow, item)
        
        self.macroStepListWidget.setCurrentRow(targetRow)

    def _refreshMacroStepList(self, actionObj: ActionItem) -> None:
        """
        Refresh the macro step list UI.
        
        Args:
            actionObj: Action containing the steps
        """
        self.macroStepListWidget.clear()
        for step in actionObj.MacroSteps:
            # Check if it's a dict (raw data) or an object
            description = ""
            if isinstance(step, dict):
                description = cast(Dict[str, Any], step).get("Description", "Unknown Step")
            else:
                description = step.Description
                
            item = QListWidgetItem(description)
            item.setData(Qt.ItemDataRole.UserRole, step)  # Store the step data/object
            self.macroStepListWidget.addItem(item)

    def _onCommitEventName(self) -> None:
        """Commit event name changes."""
        self.ViewModel.UpdateSelectedEventName(self.eventNameEdit.text().strip())

    def _onAddStepClicked(self) -> None:
        """Handle add step button click."""
        eventItem = self.ViewModel.SelectedEventItem
        if not eventItem:
            return
        
        if eventItem.AssignedAction:
            stepTypeName = self.stepDropDown.currentText()
            if stepTypeName in InputType.__members__:
                stepType = InputType[stepTypeName]
                # Create a default step based on type
                if stepType == InputType.Mouse:
                    try:
                        self.ViewModel.AddSelectedMouseStepFromCapturedPosition()
                        self._refreshMacroStepList(eventItem.AssignedAction)
                        return
                    except ValueError:
                        QMessageBox.warning(self, "Error", "No mouse position captured. Please capture a position first.")
                        return
                elif stepType == InputType.Keyboard:
                    dialog = HotkeyCaptureDialog(self)
                    if dialog.exec() == QDialog.DialogCode.Accepted:
                        if dialog.CapturedVirtualKeyCodes:
                            self.ViewModel.AddSelectedKeyboardStep(dialog.CapturedVirtualKeyCodes)
                        else:
                            return
                    else:
                        return
                elif stepType == InputType.Delay:
                    milliseconds, ok = QInputDialog.getInt(self, "Add Delay", "Milliseconds (ms):", 100, 1, 60000, 10)
                    if ok:
                        self.ViewModel.AddSelectedDelayStep(milliseconds)
                    else:
                        return

                self._refreshMacroStepList(eventItem.AssignedAction)

    def _onRemoveStepClicked(self) -> None:
        """Handle remove step button click."""
        currentRow = self.macroStepListWidget.currentRow()
        eventItem = self.ViewModel.SelectedEventItem
        if eventItem and currentRow >= 0 and eventItem.AssignedAction:
            self.ViewModel.RemoveSelectedStep(currentRow)
            self._refreshMacroStepList(eventItem.AssignedAction)

    def _onCaptureHotkey(self) -> None:
        """Handle capture hotkey button click."""
        dialog = HotkeyCaptureDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.ViewModel.UpdateSelectedActivationHotkey(dialog.CapturedVirtualKeyCodes)
            self.activationHotkeyEdit.setText(", ".join(map(self.ViewModel.KeyNameFromVk, dialog.CapturedVirtualKeyCodes)))

    def _onSelectRoi(self) -> None:
        """Handle select ROI button click."""
        lastLiveImage = self.ViewModel.GetLastLiveImage()
        if lastLiveImage is None:
            QMessageBox.warning(self, "Error", "Please start the capture before selecting an ROI.")
            return

        self.cropper = CropperWidget(lastLiveImage, self._handleNewCrop)
        self.cropper.show()

    def _handleNewCrop(
        self,
        cvImage: np.ndarray[Any, Any],
        normalizedX: float,
        normalizedY: float,
        normalizedWidth: float,
        normalizedHeight: float,
    ) -> None:
        self.ViewModel.SetSelectedTemplateAndRoi(
            cvImage,
            RectangleRegion(normalizedX, normalizedY, normalizedWidth, normalizedHeight),
        )

        self._setButtonWithImage(self.roiButton, cvImage)
        self.roiXEdit.setText(f"{normalizedX:.4f}")
        self.roiYEdit.setText(f"{normalizedY:.4f}")
        self.roiWEdit.setText(f"{normalizedWidth:.4f}")
        self.roiHEdit.setText(f"{normalizedHeight:.4f}")

    def _refreshConditionDependentFields(self, eventItem: EventItem) -> None:
        self.roiXEdit.setText(f"{eventItem.Roi.XNormalized:.4f}")
        self.roiYEdit.setText(f"{eventItem.Roi.YNormalized:.4f}")
        self.roiWEdit.setText(f"{eventItem.Roi.WidthNormalized:.4f}")
        self.roiHEdit.setText(f"{eventItem.Roi.HeightNormalized:.4f}")

        if eventItem.TemplateImage is not None:
            self._setButtonWithImage(self.roiButton, eventItem.TemplateImage)
        else:
            self.roiButton.setIcon(QIcon())
            self.roiButton.setText("Select from Image")

    def _setButtonWithImage(self, button: QPushButton, cvImage: np.ndarray[Any, Any]) -> None:
        height, width, _channel = cvImage.shape
        bytesPerLine = 3 * width
        cvRgb = cv2.cvtColor(cvImage, cv2.COLOR_BGR2RGB)
        qImage = QImage(cvRgb.data, width, height, bytesPerLine, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qImage)
        icon = QIcon(pixmap)
        button.setIcon(icon)
        button.setIconSize(button.size())
        button.setText("")

    def _onCopyMatchScoreToThreshold(self) -> None:
        """Handle copy match score to threshold button click."""
        self.thresholdEdit.setText(self.thresholdMatchScoreLabel.text())

    def _updateUiEventMatchScore(self, score: object) -> None:
        """Update the live match score label."""
        displayValue: object = score
        if isinstance(score, (tuple, list)):
            scoreSequence = cast(list[Any], score)
            if len(scoreSequence) >= 2:
                displayValue = scoreSequence[1]
        self.thresholdMatchScoreLabel.setText(f"{displayValue}")

    def _onEventItemSelectedSignal(self, eventItem: Optional[EventItem]) -> None:
        if not eventItem:
            self.eventNameEdit.clear()
            self.macroStepListWidget.clear()

            self.eventNameEdit.setEnabled(False)
            self.activationDropdown.setEnabled(False)
            self.activationHotkeyButton.setEnabled(False)
            self.loopCountEdit.setEnabled(False)
            self.loopIntervalEdit.setEnabled(False)
            self.stepDropDown.setEnabled(False)
            self.addStepButton.setEnabled(False)
            self.deleteStepButton.setEnabled(False)
            self.buttonMoveUp.setEnabled(False)
            self.buttonMoveDown.setEnabled(False)
            self.thresholdEdit.setEnabled(False)
            self.triggerOnThresholdExceedCheckbox.setEnabled(False)
            self.retriggerTimeEdit.setEnabled(False)
            self.roiButton.setEnabled(False)
            self.conditionDropdown.setEnabled(False)

            self.activationHotkeyWidget.hide()
            self.loopWidget.hide()
            self.conditionWidget.hide()
            self.roiWidget.hide()
            self.thresholdWidget.hide()
            self.triggerOnThresholdExceedWidget.hide()
            self.retriggerTimeWidget.hide()
            return

        self.eventNameEdit.setText(eventItem.Name)
        self.eventNameEdit.setEnabled(True)

        activation = eventItem.SelectedActivationType
        typeName = activation.name if hasattr(activation, "name") else str(activation)
        index = self.activationDropdown.findText(typeName)
        if index >= 0:
            self.activationDropdown.setCurrentIndex(index)
        self.activationDropdown.setEnabled(True)

        self.activationHotkeyEdit.setText(", ".join(map(self.ViewModel.KeyNameFromVk, eventItem.ActivationVirtualKeyCodes)))
        self.activationHotkeyButton.setEnabled(True)

        self.loopCountEdit.setText(str(eventItem.LoopCount))
        self.loopIntervalEdit.setText(str(eventItem.IntervalMilliseconds))
        self.loopCountEdit.setEnabled(True)
        self.loopIntervalEdit.setEnabled(True)

        self._refreshConditionDropdown(eventItem)

        self.roiXEdit.setText(f"{eventItem.Roi.XNormalized:.4f}")
        self.roiYEdit.setText(f"{eventItem.Roi.YNormalized:.4f}")
        self.roiWEdit.setText(f"{eventItem.Roi.WidthNormalized:.4f}")
        self.roiHEdit.setText(f"{eventItem.Roi.HeightNormalized:.4f}")

        if eventItem.TemplateImage is not None:
            self._setButtonWithImage(self.roiButton, eventItem.TemplateImage)
        else:
            self.roiButton.setIcon(QIcon())
            self.roiButton.setText("Select from Image")

        self.roiButton.setEnabled(True)

        self.thresholdEdit.setText(f"{eventItem.Threshold}")
        self.thresholdEdit.setEnabled(True)

        self.triggerOnThresholdExceedCheckbox.setChecked(eventItem.TriggerOnThresholdExceed)
        self.triggerOnThresholdExceedCheckbox.setEnabled(True)

        self.retriggerTimeEdit.setText(str(eventItem.RetriggerTimeMilliseconds))
        self.retriggerTimeEdit.setEnabled(True)

        self._updateVisibilityForActivation(eventItem.SelectedActivationType)

        self._refreshMacroStepList(eventItem.AssignedAction)
        self.stepDropDown.setEnabled(True)
        self.addStepButton.setEnabled(True)
        self.deleteStepButton.setEnabled(True)
        self.buttonMoveUp.setEnabled(True)
        self.buttonMoveDown.setEnabled(True)

    def _updateVisibilityForActivation(self, activationType: ActivationType) -> None:
        if activationType == ActivationType.Hotkey:
            self.activationHotkeyWidget.show()
        else:
            self.activationHotkeyWidget.hide()

        if activationType == ActivationType.Loop:
            self.loopWidget.show()
        else:
            self.loopWidget.hide()

        if activationType in (ActivationType.ImageMatchRoi, ActivationType.ProgressBar):
            self.conditionWidget.show()
            self.roiWidget.show()
            self.thresholdWidget.show()
            self.triggerOnThresholdExceedWidget.show()
            self.retriggerTimeWidget.show()
        else:
            self.conditionWidget.hide()
            self.roiWidget.hide()
            self.thresholdWidget.hide()
            self.triggerOnThresholdExceedWidget.hide()
            self.retriggerTimeWidget.hide()

    def _refreshConditionDropdown(self, eventItem: EventItem) -> None:
        self._isUpdatingConditionDropdown = True
        try:
            self.conditionDropdown.clear()

            # First option: create new condition
            self.conditionDropdown.addItem("New…", "__new__")
            self.conditionDropdown.addItem("Rename…", "__rename__")

            library = self.ViewModel.GetConditionLibrary()
            selectedId = str(eventItem.Condition.Uuid)
            selectedIndex = 0

            for condition in library:
                name = condition.Name.strip()
                if not name:
                    name = f"(unnamed) {str(condition.Uuid)[:8]}"
                idx = self.conditionDropdown.count()
                self.conditionDropdown.addItem(name, str(condition.Uuid))
                if str(condition.Uuid) == selectedId:
                    selectedIndex = idx

            self.conditionDropdown.setCurrentIndex(selectedIndex)
            self.conditionDropdown.setEnabled(True)
        finally:
            self._isUpdatingConditionDropdown = False

    def _onCommitConditionSelection(self, index: int) -> None:
        if self._isUpdatingConditionDropdown:
            return

        eventItem = self.ViewModel.SelectedEventItem
        if not eventItem:
            return

        data = self.conditionDropdown.currentData()
        if data == "__new__":
            name, ok = QInputDialog.getText(self, "New Condition", "Condition name:")
            if not ok:
                self._refreshConditionDropdown(eventItem)
                return
            condition = self.ViewModel.CreateCondition(name.strip())
            self.ViewModel.SetSelectedEventCondition(str(condition.Uuid))
            # Update ROI/template UI to match the newly bound condition
            self._refreshConditionDependentFields(eventItem)
            self._refreshConditionDropdown(eventItem)
            return

        if data == "__rename__":
            current = eventItem.Condition
            defaultName = current.Name
            name, ok = QInputDialog.getText(self, "Rename Condition", "Condition name:", text=defaultName)
            if not ok:
                self._refreshConditionDropdown(eventItem)
                return
            self.ViewModel.RenameCondition(str(current.Uuid), name.strip())
            self._refreshConditionDropdown(eventItem)
            return

        if isinstance(data, str):
            self.ViewModel.SetSelectedEventCondition(data)
            # Update ROI/template UI to match the newly bound condition
            self._refreshConditionDependentFields(eventItem)

    def _onCommitActivationType(self, index: int) -> None:
        typeName = self.activationDropdown.currentText()
        activationType = ActivationType[typeName]
        self.ViewModel.UpdateSelectedActivationType(activationType)
        self._updateVisibilityForActivation(activationType)

    def _onCommitLoopCount(self) -> None:
        try:
            self.ViewModel.UpdateSelectedLoopCount(int(self.loopCountEdit.text()))
        except ValueError:
            QMessageBox.warning(self, "Error", "Invalid loop count.")

    def _onCommitLoopInterval(self) -> None:
        try:
            self.ViewModel.UpdateSelectedLoopIntervalMs(int(self.loopIntervalEdit.text()))
        except ValueError:
            QMessageBox.warning(self, "Error", "Invalid interval.")

    def _onCommitThreshold(self) -> None:
        try:
            self.ViewModel.UpdateSelectedThreshold(float(self.thresholdEdit.text()))
        except ValueError:
            QMessageBox.warning(self, "Error", "Invalid threshold.")

    def _onCommitTriggerOnThresholdExceed(self, state: int) -> None:
        self.ViewModel.UpdateSelectedTriggerOnThresholdExceed(state != 0)

    def _onCommitRetriggerTime(self) -> None:
        try:
            self.ViewModel.UpdateSelectedRetriggerTimeMs(float(self.retriggerTimeEdit.text()))
        except ValueError:
            QMessageBox.warning(self, "Error", "Invalid retrigger time.")
