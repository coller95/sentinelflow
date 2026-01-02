from typing import Any, Dict, Optional, Protocol, cast
from functools import partial
from PySide6.QtCore import Qt
 
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QListWidget, QListWidgetItem, QCheckBox, QInputDialog, QMessageBox, 
    QDialog
)
from Src.Models import (
    ActivationType,
    CriteriaLogic,
    ConditionCriterion,
    InputType,
    ActionItem,
    ConditionItem,
    EventItem,
    RectangleRegion,
)
from Src.Ui.UiShared import (
    HotkeyCaptureDialog,
)

class DashboardViewModelProtocol(Protocol):
    EventItemSelectedSignal: Any
    MatchScoreUpdated: Any
    ConditionsChangedSignal: Any

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
    def GetConditionLibrary(self) -> list[ConditionItem]: ...
    def SetConditionTemplateAndRoi(self, conditionUuid: str, templateImage: Any, roi: RectangleRegion) -> None: ...
    def SetSelectedEventCondition(self, conditionUuid: str) -> None: ...

    # CriteriaMet editing
    def GetSelectedCriteria(self) -> list[ConditionCriterion]: ...
    def GetSelectedCriteriaLogic(self) -> CriteriaLogic: ...
    def SetSelectedCriteriaLogic(self, logicName: str) -> None: ...
    def AddSelectedCriterion(self) -> None: ...
    def RemoveSelectedCriterion(self, index: int) -> None: ...
    def UpdateSelectedCriterionCondition(self, index: int, conditionUuid: str) -> None: ...
    def UpdateSelectedCriterionThreshold(self, index: int, threshold: float) -> None: ...
    def UpdateSelectedCriterionTriggerOnThresholdExceed(self, index: int, isEnabled: bool) -> None: ...
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
        self._isUpdatingCriteriaUi = False
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
        
        # Threshold widget
        self.thresholdWidget = QWidget()
        self.thresholdWidgetLayout = QVBoxLayout()
        
        self.thresholdWidgetThresholdLayout = QHBoxLayout()
        self.thresholdWidgetThresholdLayout.addWidget(QLabel("Threshold:"))
        self.thresholdEdit = QLineEdit("0.99")
        self.thresholdWidgetThresholdLayout.addWidget(self.thresholdEdit)

        self.thresholdWidgetLayout.addLayout(self.thresholdWidgetThresholdLayout)
        self.thresholdWidget.setLayout(self.thresholdWidgetLayout)
        self.thresholdEdit.setEnabled(False)
        self.thresholdWidget.hide()
        
        # Trigger Type Specific Widgets
        self.triggerOnThresholdExceedLayout = QHBoxLayout()
        self.triggerOnThresholdExceedWidget = QWidget()
        self.triggerOnThresholdExceedCheckbox = QCheckBox(">")
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

        # CriteriaMet widget (multi-condition criteria editor)
        self.criteriaMetWidget = QWidget()
        self.criteriaMetLayout = QVBoxLayout()
        self.criteriaMetLayout.setContentsMargins(0, 0, 0, 0)

        self.criteriaMetHeaderLayout = QHBoxLayout()
        self.criteriaMetHeaderLayout.setContentsMargins(0, 0, 0, 0)
        self.criteriaMetHeaderLayout.addWidget(QLabel("Criteria:"))

        self.criteriaLogicDropdown = QComboBox()
        self.criteriaLogicDropdown.addItems([logic.name for logic in CriteriaLogic])
        self.criteriaMetHeaderLayout.addWidget(self.criteriaLogicDropdown)

        self.addCriterionButton = QPushButton("+")
        self.criteriaMetHeaderLayout.addWidget(self.addCriterionButton)

        self.criteriaMetLayout.addLayout(self.criteriaMetHeaderLayout)

        self.criteriaRowsWidget = QWidget()
        self.criteriaRowsLayout = QVBoxLayout()
        self.criteriaRowsLayout.setContentsMargins(0, 0, 0, 0)
        self.criteriaRowsWidget.setLayout(self.criteriaRowsLayout)
        self.criteriaMetLayout.addWidget(self.criteriaRowsWidget)

        self.criteriaMetWidget.setLayout(self.criteriaMetLayout)
        self.criteriaMetWidget.hide()
        
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
        layout.addWidget(self.thresholdWidget)
        layout.addWidget(self.triggerOnThresholdExceedWidget)
        layout.addWidget(self.criteriaMetWidget)
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
        self.conditionDropdown.currentIndexChanged.connect(self._onCommitConditionSelection)
        
        # Property Editing
        self.eventNameEdit.editingFinished.connect(self._onCommitEventName)
        self.activationDropdown.currentIndexChanged.connect(self._onCommitActivationType)
        
        self.loopCountEdit.editingFinished.connect(self._onCommitLoopCount)
        self.loopIntervalEdit.editingFinished.connect(self._onCommitLoopInterval)
        
        self.thresholdEdit.editingFinished.connect(self._onCommitThreshold)
        self.triggerOnThresholdExceedCheckbox.stateChanged.connect(self._onCommitTriggerOnThresholdExceed)
        self.retriggerTimeEdit.editingFinished.connect(self._onCommitRetriggerTime)

        # CriteriaMet editing
        self.criteriaLogicDropdown.currentIndexChanged.connect(self._onCommitCriteriaLogic)
        self.addCriterionButton.clicked.connect(self._onAddCriterionClicked)

        # --- ViewModel to View ---
        self.ViewModel.EventItemSelectedSignal.connect(self._onEventItemSelectedSignal)
        self.ViewModel.ConditionsChangedSignal.connect(self._onConditionsChanged)

    def _onConditionsChanged(self) -> None:
        eventItem = self.ViewModel.SelectedEventItem
        if not eventItem:
            return
        if eventItem.SelectedActivationType == ActivationType.CriteriaMet:
            self._refreshCriteriaMetEditor(eventItem)
        else:
            self._refreshConditionDropdown(eventItem)

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
            self.conditionDropdown.setEnabled(False)
            self.criteriaLogicDropdown.setEnabled(False)
            self.addCriterionButton.setEnabled(False)

            self.activationHotkeyWidget.hide()
            self.loopWidget.hide()
            self.conditionWidget.hide()
            self.thresholdWidget.hide()
            self.triggerOnThresholdExceedWidget.hide()
            self.criteriaMetWidget.hide()
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

        self.thresholdEdit.setText(f"{eventItem.Threshold}")
        self.thresholdEdit.setEnabled(True)

        self.triggerOnThresholdExceedCheckbox.setChecked(eventItem.TriggerOnThresholdExceed)
        self._syncComparatorCheckboxText(self.triggerOnThresholdExceedCheckbox)
        self.triggerOnThresholdExceedCheckbox.setEnabled(True)

        self.retriggerTimeEdit.setText(str(eventItem.RetriggerTimeMilliseconds))
        self.retriggerTimeEdit.setEnabled(True)

        self._updateVisibilityForActivation(eventItem.SelectedActivationType)

        if eventItem.SelectedActivationType == ActivationType.CriteriaMet:
            self._refreshCriteriaMetEditor(eventItem)

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
            self.thresholdWidget.show()
            self.triggerOnThresholdExceedWidget.show()
            self.criteriaMetWidget.hide()
            self.retriggerTimeWidget.show()
        elif activationType == ActivationType.CriteriaMet:
            self.conditionWidget.hide()
            self.thresholdWidget.hide()
            self.triggerOnThresholdExceedWidget.hide()
            self.criteriaMetWidget.show()
            self.retriggerTimeWidget.show()
        else:
            self.conditionWidget.hide()
            self.thresholdWidget.hide()
            self.triggerOnThresholdExceedWidget.hide()
            self.criteriaMetWidget.hide()
            self.retriggerTimeWidget.hide()

    def _clearCriteriaRows(self) -> None:
        while self.criteriaRowsLayout.count():
            item = self.criteriaRowsLayout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _refreshCriteriaMetEditor(self, eventItem: EventItem) -> None:
        self._isUpdatingCriteriaUi = True
        try:
            # Logic dropdown
            logic = getattr(eventItem, "CriteriaLogic", CriteriaLogic.All)
            logicName = logic.name if hasattr(logic, "name") else str(logic)
            idx = self.criteriaLogicDropdown.findText(logicName)
            if idx >= 0:
                self.criteriaLogicDropdown.setCurrentIndex(idx)

            self.criteriaLogicDropdown.setEnabled(True)
            self.addCriterionButton.setEnabled(True)

            criteria = self.ViewModel.GetSelectedCriteria()
            library = self.ViewModel.GetConditionLibrary()

            self._clearCriteriaRows()
            for rowIndex, criterion in enumerate(criteria):
                rowWidget = QWidget()
                rowLayout = QHBoxLayout()
                rowLayout.setContentsMargins(0, 0, 0, 0)

                conditionDropdown = QComboBox()

                selectedId = str(criterion.ConditionUuid)
                items: list[tuple[str, str]] = []
                if not any(str(c.Uuid) == selectedId for c in library):
                    items.append((selectedId, f"(missing) {selectedId[:8]}"))

                for condition in library:
                    name = condition.Name.strip()
                    if not name:
                        name = f"(unnamed) {str(condition.Uuid)[:8]}"
                    items.append((str(condition.Uuid), name))

                selectedIndex = 0
                for uuidStr, name in items:
                    idx2 = conditionDropdown.count()
                    conditionDropdown.addItem(name, uuidStr)
                    if uuidStr == selectedId:
                        selectedIndex = idx2
                conditionDropdown.setCurrentIndex(selectedIndex)

                thresholdEdit = QLineEdit(str(criterion.Threshold))
                thresholdEdit.setFixedWidth(70)

                exceedCheckbox = QCheckBox("Exceed")
                exceedCheckbox.setChecked(bool(criterion.TriggerOnThresholdExceed))
                self._syncComparatorCheckboxText(exceedCheckbox)

                removeButton = QPushButton("-")
                removeButton.setFixedWidth(26)

                # Wire commits
                conditionDropdown.currentIndexChanged.connect(partial(self._onCommitCriterionCondition, rowIndex, conditionDropdown))
                thresholdEdit.editingFinished.connect(partial(self._onCommitCriterionThreshold, rowIndex, thresholdEdit))
                exceedCheckbox.stateChanged.connect(partial(self._onCommitCriterionExceed, rowIndex, exceedCheckbox))
                removeButton.clicked.connect(partial(self._onRemoveSpecificCriterionClicked, rowIndex))

                rowLayout.addWidget(QLabel("C:"))
                rowLayout.addWidget(conditionDropdown)
                rowLayout.addWidget(QLabel("T:"))
                rowLayout.addWidget(thresholdEdit)
                rowLayout.addWidget(exceedCheckbox)
                rowLayout.addWidget(removeButton)
                rowWidget.setLayout(rowLayout)
                self.criteriaRowsLayout.addWidget(rowWidget)
        finally:
            self._isUpdatingCriteriaUi = False

    def _syncComparatorCheckboxText(self, checkbox: QCheckBox) -> None:
        checkbox.setText(">" if checkbox.isChecked() else "<")

    def _refreshConditionDropdown(self, eventItem: EventItem) -> None:
        self._isUpdatingConditionDropdown = True
        try:
            self.conditionDropdown.clear()

            library = self.ViewModel.GetConditionLibrary()
            selectedId = str(eventItem.Condition.Uuid)
            selectedIndex = 0

            # Ensure the event's current condition is always present in the list.
            if not any(str(c.Uuid) == selectedId for c in library):
                library = [eventItem.Condition] + library

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
        if isinstance(data, str):
            self.ViewModel.SetSelectedEventCondition(data)

    def _onCommitActivationType(self, index: int) -> None:
        typeName = self.activationDropdown.currentText()
        activationType = ActivationType[typeName]
        self.ViewModel.UpdateSelectedActivationType(activationType)
        self._updateVisibilityForActivation(activationType)
        eventItem = self.ViewModel.SelectedEventItem
        if eventItem and activationType == ActivationType.CriteriaMet:
            self._refreshCriteriaMetEditor(eventItem)

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
        self._syncComparatorCheckboxText(self.triggerOnThresholdExceedCheckbox)
        self.ViewModel.UpdateSelectedTriggerOnThresholdExceed(state != 0)

    def _onCommitRetriggerTime(self) -> None:
        try:
            self.ViewModel.UpdateSelectedRetriggerTimeMs(float(self.retriggerTimeEdit.text()))
        except ValueError:
            QMessageBox.warning(self, "Error", "Invalid retrigger time.")

    def _onCommitCriteriaLogic(self, index: int) -> None:
        if self._isUpdatingCriteriaUi:
            return
        logicName = self.criteriaLogicDropdown.currentText()
        self.ViewModel.SetSelectedCriteriaLogic(logicName)

    def _onAddCriterionClicked(self) -> None:
        self.ViewModel.AddSelectedCriterion()
        eventItem = self.ViewModel.SelectedEventItem
        if eventItem and eventItem.SelectedActivationType == ActivationType.CriteriaMet:
            self._refreshCriteriaMetEditor(eventItem)

    def _onRemoveCriterionClicked(self) -> None:
        # Minimal behavior: remove last criterion.
        criteria = self.ViewModel.GetSelectedCriteria()
        if len(criteria) == 0:
            return
        self.ViewModel.RemoveSelectedCriterion(len(criteria) - 1)
        eventItem = self.ViewModel.SelectedEventItem
        if eventItem and eventItem.SelectedActivationType == ActivationType.CriteriaMet:
            self._refreshCriteriaMetEditor(eventItem)

    def _onRemoveSpecificCriterionClicked(self, rowIndex: int) -> None:
        self.ViewModel.RemoveSelectedCriterion(rowIndex)
        eventItem = self.ViewModel.SelectedEventItem
        if eventItem and eventItem.SelectedActivationType == ActivationType.CriteriaMet:
            self._refreshCriteriaMetEditor(eventItem)

    def _onCommitCriterionCondition(self, rowIndex: int, dropdown: QComboBox, _: int) -> None:
        if self._isUpdatingCriteriaUi:
            return
        data = dropdown.currentData()
        if isinstance(data, str):
            self.ViewModel.UpdateSelectedCriterionCondition(rowIndex, data)

    def _onCommitCriterionThreshold(self, rowIndex: int, edit: QLineEdit) -> None:
        if self._isUpdatingCriteriaUi:
            return
        try:
            value = float(edit.text())
        except ValueError:
            QMessageBox.warning(self, "Error", "Invalid threshold.")
            return
        self.ViewModel.UpdateSelectedCriterionThreshold(rowIndex, value)

    def _onCommitCriterionExceed(self, rowIndex: int, checkbox: QCheckBox, state: int) -> None:
        if self._isUpdatingCriteriaUi:
            return
        self._syncComparatorCheckboxText(checkbox)
        self.ViewModel.UpdateSelectedCriterionTriggerOnThresholdExceed(rowIndex, state != 0)
