from __future__ import annotations

from typing import Any, Dict, Protocol, cast
from uuid import UUID

import numpy as np
import cv2

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QDialog, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout

from Src.Models import ConditionItem


class DashboardViewModelProtocol(Protocol):
    MatchScoreUpdated: Any

    def GetConditionLibrary(self) -> list[ConditionItem]: ...


class ConditionStatusWindow(QDialog):
    def __init__(self, viewModel: DashboardViewModelProtocol) -> None:
        super().__init__()
        self.ViewModel = viewModel
        self.setWindowTitle("Condition Status")
        self.setMinimumSize(520, 320)

        self._lastValues: Dict[UUID, object] = {}
        self._lastCrops: Dict[UUID, np.ndarray[Any, Any]] = {}

        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Condition", "Type", "Template", "Crop", "Last"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        # initial
        self._refreshTable()

        # live updates
        self.ViewModel.MatchScoreUpdated.connect(self._onMatchUpdate)

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

    def _refreshTable(self) -> None:
        conditions = self.ViewModel.GetConditionLibrary()
        self.table.setRowCount(len(conditions))

        for row, condition in enumerate(conditions):
            name = condition.Name.strip() or f"(unnamed) {str(condition.Uuid)[:8]}"
            typeName = condition.SelectedConditionType.name if hasattr(condition.SelectedConditionType, "name") else str(condition.SelectedConditionType)
            lastValue = self._lastValues.get(condition.Uuid, "-")

            self._setItem(row, 0, name)
            self._setItem(row, 1, typeName)
            self._setImageCell(row, 2, condition.TemplateImage)
            self._setImageCell(row, 3, self._lastCrops.get(condition.Uuid))
            self._setItem(row, 4, str(lastValue))

        # make image rows readable
        for row in range(self.table.rowCount()):
            self.table.setRowHeight(row, 72)

    def _setItem(self, row: int, col: int, text: str) -> None:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
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
