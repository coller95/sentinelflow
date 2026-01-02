from __future__ import annotations

from typing import Any, Dict, Optional, Protocol, cast
from uuid import UUID

import numpy as np
import cv2

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QInputDialog,
    QMessageBox,
    QPushButton,
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from Src.Models import ConditionItem, ConditionType, RectangleRegion
from Src.Ui.UiShared import CropperWidget


class DashboardViewModelProtocol(Protocol):
    MatchScoreUpdated: Any
    ConditionsChangedSignal: Any

    def GetConditionLibrary(self) -> list[ConditionItem]: ...
    def GetLastLiveImage(self) -> Optional[Any]: ...
    def CreateCondition(self, name: str) -> ConditionItem: ...
    def DeleteCondition(self, conditionUuid: str) -> None: ...
    def RenameCondition(self, conditionUuid: str, name: str) -> None: ...
    def SetConditionType(self, conditionUuid: str, conditionTypeName: str) -> None: ...
    def SetConditionTemplateAndRoi(self, conditionUuid: str, templateImage: Any, roi: RectangleRegion) -> None: ...
    def MoveCondition(self, fromIndex: int, toIndex: int) -> None: ...


class ConditionStatusWindow(QDialog):
    def __init__(self, viewModel: DashboardViewModelProtocol, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.ViewModel = viewModel
        self.setWindowTitle("Condition Status")
        self.setMinimumSize(520, 320)

        self._activeCropper: Optional[CropperWidget] = None
        self._isUpdatingEditorFields: bool = False

        self._lastValues: Dict[UUID, object] = {}
        self._lastCrops: Dict[UUID, np.ndarray[Any, Any]] = {}

        layout = QVBoxLayout(self)

        # Top toolbar: add/remove conditions
        toolbarRow = QWidget()
        toolbarLayout = QHBoxLayout(toolbarRow)
        toolbarLayout.setContentsMargins(0, 0, 0, 0)
        self.newButton = QPushButton("+")
        self.newButton.setFixedWidth(30)
        self.newButton.setToolTip("New condition")
        toolbarLayout.addWidget(self.newButton)
        self.deleteButton = QPushButton("-")
        self.deleteButton.setFixedWidth(30)
        self.deleteButton.setToolTip("Delete selected condition")
        toolbarLayout.addWidget(self.deleteButton)

        self.moveUpButton = QPushButton("↑")
        self.moveUpButton.setFixedWidth(30)
        self.moveUpButton.setToolTip("Move selected condition up")
        toolbarLayout.addWidget(self.moveUpButton)

        self.moveDownButton = QPushButton("↓")
        self.moveDownButton.setFixedWidth(30)
        self.moveDownButton.setToolTip("Move selected condition down")
        toolbarLayout.addWidget(self.moveDownButton)

        toolbarLayout.addStretch()
        layout.addWidget(toolbarRow)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Condition", "Type", "Template", "Crop", "Last"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        editorRow = QWidget()
        editorLayout = QHBoxLayout(editorRow)
        editorLayout.setContentsMargins(0, 0, 0, 0)
        editorLayout.addWidget(QLabel("Name:"))
        self.nameEdit = QLineEdit("")
        editorLayout.addWidget(self.nameEdit)

        editorLayout.addWidget(QLabel("Type:"))
        self.typeDropdown = QComboBox()
        self.typeDropdown.addItems([t.name for t in ConditionType])
        editorLayout.addWidget(self.typeDropdown)
        self.setRoiButton = QPushButton("Set ROI/Template from Live")
        editorLayout.addWidget(self.setRoiButton)
        layout.addWidget(editorRow)

        # initial
        self._refreshTable()

        self.table.itemSelectionChanged.connect(self._onSelectionChanged)
        self.nameEdit.editingFinished.connect(self._onNameEdited)
        self.typeDropdown.currentIndexChanged.connect(self._onTypeEdited)
        self.newButton.clicked.connect(self._onNewCondition)
        self.deleteButton.clicked.connect(self._onDeleteCondition)
        self.setRoiButton.clicked.connect(self._onSetRoiFromLive)
        self.moveUpButton.clicked.connect(lambda: self._onMoveSelected(-1))
        self.moveDownButton.clicked.connect(lambda: self._onMoveSelected(1))

        # live updates
        self.ViewModel.MatchScoreUpdated.connect(self._onMatchUpdate)
        self.ViewModel.ConditionsChangedSignal.connect(self._onConditionsChanged)

        self._updateMoveButtonsEnabled()

    def _onConditionsChanged(self) -> None:
        self._refreshTable()
        self._updateMoveButtonsEnabled()

    def _updateMoveButtonsEnabled(self) -> None:
        row = self.table.currentRow()
        count = self.table.rowCount()
        hasSelection = row >= 0 and count > 0
        self.moveUpButton.setEnabled(hasSelection and row > 0)
        self.moveDownButton.setEnabled(hasSelection and row < (count - 1))

    def _onMatchUpdate(self, payload: object) -> None:
        # Expected payload: (uuid.UUID, value, cropImage?)
        if not isinstance(payload, (tuple, list)):
            return
        seq = cast(list[Any], payload)
        if len(seq) < 2:
            return

        cid = seq[0]
        value = seq[1]
        if not isinstance(cid, UUID):
            # best-effort: try parse string
            try:
                cid = UUID(str(cid))
            except Exception:
                return

        self._lastValues[cid] = value
        if len(seq) >= 3:
            crop = seq[2]
            if isinstance(crop, np.ndarray):
                self._lastCrops[cid] = crop
        self._refreshTable()

    def _getSelectedConditionUuid(self) -> Optional[UUID]:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        raw = item.data(Qt.ItemDataRole.UserRole)
        if raw is None:
            return None
        try:
            return UUID(str(raw))
        except Exception:
            return None

    def _selectRowByUuid(self, conditionUuid: UUID) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is None:
                continue
            raw = item.data(Qt.ItemDataRole.UserRole)
            if raw is None:
                continue
            if str(raw) == str(conditionUuid):
                self.table.setCurrentCell(row, 0)
                return

    def _onSelectionChanged(self) -> None:
        self._updateMoveButtonsEnabled()
        cid = self._getSelectedConditionUuid()
        self._isUpdatingEditorFields = True
        try:
            if cid is None:
                self.nameEdit.setText("")
                idx = self.typeDropdown.findText(ConditionType.NotSet.name)
                if idx >= 0:
                    self.typeDropdown.setCurrentIndex(idx)
                return

            condition = next((c for c in self.ViewModel.GetConditionLibrary() if c.Uuid == cid), None)
            if condition is None:
                self.nameEdit.setText("")
                idx = self.typeDropdown.findText(ConditionType.NotSet.name)
                if idx >= 0:
                    self.typeDropdown.setCurrentIndex(idx)
                return

            self.nameEdit.setText(condition.Name)

            typeName = condition.SelectedConditionType.name if hasattr(condition.SelectedConditionType, "name") else str(condition.SelectedConditionType)
            idx = self.typeDropdown.findText(typeName)
            if idx >= 0:
                self.typeDropdown.setCurrentIndex(idx)
        finally:
            self._isUpdatingEditorFields = False

    def _onMoveSelected(self, direction: int) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        target = row + direction
        if target < 0 or target >= self.table.rowCount():
            return
        selected = self._getSelectedConditionUuid()
        self.ViewModel.MoveCondition(row, target)
        self._refreshTable()
        if selected is not None:
            self._selectRowByUuid(selected)
        self._updateMoveButtonsEnabled()

    def _onNameEdited(self) -> None:
        if self._isUpdatingEditorFields:
            return
        cid = self._getSelectedConditionUuid()
        if cid is None:
            return
        self.ViewModel.RenameCondition(str(cid), self.nameEdit.text().strip())
        self._refreshTable()
        self._selectRowByUuid(cid)

    def _onTypeEdited(self) -> None:
        if self._isUpdatingEditorFields:
            return
        cid = self._getSelectedConditionUuid()
        if cid is None:
            return
        typeName = self.typeDropdown.currentText()
        if typeName in ConditionType.__members__:
            self.ViewModel.SetConditionType(str(cid), typeName)
            self._refreshTable()
            self._selectRowByUuid(cid)

    def _onNewCondition(self) -> None:
        name, ok = QInputDialog.getText(self, "New Condition", "Condition name:")
        if not ok:
            return
        condition = self.ViewModel.CreateCondition(name.strip())
        self._refreshTable()
        self._selectRowByUuid(condition.Uuid)

    def _onDeleteCondition(self) -> None:
        cid = self._getSelectedConditionUuid()
        if cid is None:
            return

        result = QMessageBox.question(
            self,
            "Delete Condition",
            "Delete selected condition? Events using it will be reassigned.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if result != QMessageBox.StandardButton.Yes:
            return

        self.ViewModel.DeleteCondition(str(cid))
        self._refreshTable()

    def _onSetRoiFromLive(self) -> None:
        cid = self._getSelectedConditionUuid()
        if cid is None:
            return

        lastLiveImage = self.ViewModel.GetLastLiveImage()
        if lastLiveImage is None:
            QMessageBox.warning(self, "Error", "Please start the capture before selecting an ROI.")
            return

        def onCrop(
            cvImage: np.ndarray[Any, Any],
            normalizedX: float,
            normalizedY: float,
            normalizedWidth: float,
            normalizedHeight: float,
        ) -> None:
            self.ViewModel.SetConditionTemplateAndRoi(
                str(cid),
                cvImage,
                RectangleRegion(normalizedX, normalizedY, normalizedWidth, normalizedHeight),
            )
            self._refreshTable()
            self._selectRowByUuid(cid)

        if self._activeCropper is not None:
            self._activeCropper.close()

        cropper = CropperWidget(cast(np.ndarray[Any, Any], lastLiveImage), onCrop)
        self._activeCropper = cropper
        cropper.destroyed.connect(self._onCropperDestroyed)
        cropper.show()

    def _onCropperDestroyed(self, _obj: object = None) -> None:
        self._activeCropper = None

    def _refreshTable(self) -> None:
        selected = self._getSelectedConditionUuid()
        conditions = self.ViewModel.GetConditionLibrary()
        self.table.setRowCount(len(conditions))

        for row, condition in enumerate(conditions):
            name = condition.Name.strip() or f"(unnamed) {str(condition.Uuid)[:8]}"
            typeName = condition.SelectedConditionType.name if hasattr(condition.SelectedConditionType, "name") else str(condition.SelectedConditionType)
            lastValue = self._lastValues.get(condition.Uuid, "-")

            self._setItem(row, 0, name, str(condition.Uuid))
            self._setItem(row, 1, typeName)
            self._setImageCell(row, 2, condition.TemplateImage)
            self._setImageCell(row, 3, self._lastCrops.get(condition.Uuid))
            self._setItem(row, 4, str(lastValue))

        # make image rows readable
        for row in range(self.table.rowCount()):
            self.table.setRowHeight(row, 72)

        if selected is not None:
            self._selectRowByUuid(selected)

        self._updateMoveButtonsEnabled()

    def _setItem(self, row: int, col: int, text: str, userData: Optional[str] = None) -> None:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        if userData is not None:
            item.setData(Qt.ItemDataRole.UserRole, userData)
        self.table.setItem(row, col, item)

    def _setImageCell(self, row: int, col: int, cvImage: object) -> None:
        label = QLabel()
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setMinimumSize(64, 64)

        if isinstance(cvImage, np.ndarray):
            pixmap = self._ndarrayToPixmap(cast(np.ndarray[Any, Any], cvImage))
            if pixmap is not None:
                label.setPixmap(pixmap.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

        self.table.setCellWidget(row, col, label)

    def _ndarrayToPixmap(self, cvImage: np.ndarray[Any, Any]) -> QPixmap | None:
        try:
            if cvImage.ndim != 3:
                return None
            height, width, channels = cvImage.shape
            if channels < 3:
                return None
            bgr = cvImage[:, :, :3]
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            bytesPerLine = 3 * width
            qImage = QImage(rgb.data, width, height, bytesPerLine, QImage.Format.Format_RGB888)
            return QPixmap.fromImage(qImage)
        except Exception:
            return None
