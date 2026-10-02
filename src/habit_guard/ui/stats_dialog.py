"""The statistics window: today, the streak, the last week and the totals by habit."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..i18n import format_duration, habit_name, tr
from ..stats import Stats
from ..types import Habit


class WeekChart(QWidget):
    """Seven bars, one per day, with the count above each."""

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumHeight(140)
        self._days: list[tuple[date, int]] = []

    def set_days(self, days: list[tuple[date, int]]) -> None:
        self._days = days
        self.update()

    def paintEvent(self, event: object) -> None:
        if not self._days:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        peak = max([1, *(n for _, n in self._days)])
        slot = self.width() / len(self._days)
        label_h, count_h = 18.0, 16.0
        area = self.height() - label_h - count_h
        text = self.palette().text().color()
        for i, (day, n) in enumerate(self._days):
            height = area * n / peak
            x = i * slot + slot * 0.2
            bar = QRectF(x, count_h + area - height, slot * 0.6, max(height, 2.0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#0f9d8a") if n else QColor(128, 128, 128, 90))
            painter.drawRoundedRect(bar, 3, 3)
            painter.setPen(text)
            painter.drawText(
                QRectF(i * slot, 0, slot, count_h), int(Qt.AlignmentFlag.AlignCenter), str(n)
            )
            painter.drawText(
                QRectF(i * slot, self.height() - label_h, slot, label_h),
                int(Qt.AlignmentFlag.AlignCenter),
                day.strftime("%a"),
            )


class StatsDialog(QWidget):
    reset_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(tr("stats.title"))
        self.setMinimumWidth(420)
        self._summary = QFormLayout()
        self._today = QLabel()
        self._total = QLabel()
        self._clean = QLabel()
        self._best = QLabel()
        self._watched = QLabel()
        self._summary.addRow(tr("stats.today"), self._today)
        self._summary.addRow(tr("stats.total"), self._total)
        self._summary.addRow(tr("stats.clean"), self._clean)
        self._summary.addRow(tr("stats.best"), self._best)
        self._chart = WeekChart()
        self._by_habit = QFormLayout()
        self._habit_labels = {h: QLabel() for h in Habit}
        for habit, label in self._habit_labels.items():
            self._by_habit.addRow(habit_name(habit), label)
        reset = QPushButton(tr("stats.reset"))
        reset.clicked.connect(self._confirm_reset)
        layout = QVBoxLayout(self)
        layout.addLayout(self._summary)
        layout.addWidget(QLabel(tr("stats.week")))
        layout.addWidget(self._chart)
        layout.addWidget(QLabel(tr("stats.by_habit")))
        layout.addLayout(self._by_habit)
        layout.addWidget(self._watched)
        layout.addWidget(reset, alignment=Qt.AlignmentFlag.AlignRight)

    def refresh(self, stats: Stats, today: date) -> None:
        self._today.setText(str(stats.count(today)))
        self._total.setText(str(stats.total()))
        self._clean.setText(format_duration(stats.clean_s))
        self._best.setText(format_duration(stats.best_clean_s))
        self._chart.set_days(stats.last_days(today, 7))
        for habit, label in self._habit_labels.items():
            label.setText(
                f"{stats.total(habit)}  ({tr('stats.today').lower()}: {stats.count(today, habit)})"
            )
        self._watched.setText(tr("stats.watched", t=format_duration(stats.watched_s)))

    def _confirm_reset(self) -> None:
        answer = QMessageBox.question(self, tr("stats.title"), tr("stats.reset_confirm"))
        if answer == QMessageBox.StandardButton.Yes:
            self.reset_requested.emit()
