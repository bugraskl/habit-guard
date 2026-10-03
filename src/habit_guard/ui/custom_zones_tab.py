"""The "Custom zones" tab of the settings window: draw a zone for a habit not on the list."""

from __future__ import annotations

from dataclasses import asdict

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..config import DEFAULT_CUSTOM_ZONES, NAME_MAX, CustomZone, Settings
from ..i18n import tr
from ..types import CUSTOM_HABITS, Habit
from .preview import HABIT_COLORS
from .zone_editor import ZoneEditor


class CustomZonesTab(QWidget):
    """Edits copies of the three custom zones; :meth:`apply` writes them into a settings object."""

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self._zones = {
            h: CustomZone(**asdict(settings.custom_zones[h.value])) for h in CUSTOM_HABITS
        }
        self._enabled = {h: settings.habit(h).enabled for h in CUSTOM_HABITS}
        self._dwell = {h: settings.habit(h).dwell_s for h in CUSTOM_HABITS}
        self._current = CUSTOM_HABITS[0]

        self.editor = ZoneEditor()
        self.slot = QComboBox()
        for habit in CUSTOM_HABITS:
            self.slot.addItem(self._label(habit))
        self.enabled = QCheckBox(tr("settings.habit.enabled"))
        self.name = QLineEdit()
        self.name.setMaxLength(NAME_MAX)
        self.name.setPlaceholderText(tr("settings.custom.name_hint"))
        self.dwell = QDoubleSpinBox()
        self.dwell.setRange(0.3, 30.0)
        self.dwell.setSingleStep(0.1)
        self.dwell.setDecimals(1)
        self.dwell.setSuffix(tr("settings.unit.seconds", n="").rstrip())
        self.mirror = QCheckBox(tr("settings.custom.mirror"))
        self.reset = QPushButton(tr("settings.custom.reset"))

        form = QFormLayout()
        form.addRow(tr("settings.custom.slot"), self.slot)
        form.addRow(self.enabled)
        form.addRow(tr("settings.custom.name"), self.name)
        form.addRow(tr("settings.habit.dwell"), self.dwell)
        form.addRow(self.mirror)
        form.addRow(self.reset)

        intro = QLabel(tr("settings.custom.intro"))
        intro.setWordWrap(True)
        notes = QLabel(tr("settings.custom.keys") + "\n" + tr("settings.custom.overlap"))
        notes.setWordWrap(True)
        side = QVBoxLayout()
        side.addWidget(intro)
        side.addLayout(form)
        side.addStretch(1)
        side.addWidget(notes)
        layout = QHBoxLayout(self)
        layout.addWidget(self.editor, 3)
        layout.addLayout(side, 2)

        self.slot.currentIndexChanged.connect(self._on_slot)
        self.enabled.toggled.connect(self._on_enabled)
        self.name.textEdited.connect(self._on_name)
        self.dwell.valueChanged.connect(self._on_dwell)
        self.mirror.toggled.connect(self._on_mirror)
        self.reset.clicked.connect(self._on_reset)
        self._load(self._current)

    # ------------------------------------------------------------------------------ model
    def _label(self, habit: Habit) -> str:
        return self._zones[habit].name.strip() or tr(f"habit.{habit.value}")

    def _color(self, habit: Habit) -> QColor:
        return HABIT_COLORS[habit]

    def _load(self, habit: Habit) -> None:
        """Show the controls and the shape of ``habit`` without writing anything back."""
        self._current = habit
        zone = self._zones[habit]
        for widget in (self.enabled, self.name, self.dwell, self.mirror):
            widget.blockSignals(True)
        self.enabled.setChecked(self._enabled[habit])
        self.name.setText(zone.name)
        self.dwell.setValue(self._dwell[habit])
        self.mirror.setChecked(zone.mirror)
        for widget in (self.enabled, self.name, self.dwell, self.mirror):
            widget.blockSignals(False)
        self.editor.set_zone(zone, self._color(habit))

    # ------------------------------------------------------------------------------ events
    def _on_slot(self, index: int) -> None:
        if 0 <= index < len(CUSTOM_HABITS):  # the list is in the order of CUSTOM_HABITS
            self._load(CUSTOM_HABITS[index])

    def _on_enabled(self, checked: bool) -> None:
        self._enabled[self._current] = checked

    def _on_name(self, text: str) -> None:
        self._zones[self._current].name = text
        self.slot.setItemText(self.slot.currentIndex(), self._label(self._current))

    def _on_dwell(self, value: float) -> None:
        self._dwell[self._current] = round(value, 1)

    def _on_mirror(self, checked: bool) -> None:
        self._zones[self._current].mirror = checked
        self.editor.update()

    def _on_reset(self) -> None:
        self.editor.reset_to(DEFAULT_CUSTOM_ZONES[self._current])

    # ------------------------------------------------------------------------------ result
    def apply(self, settings: Settings) -> None:
        for habit in CUSTOM_HABITS:
            zone = self._zones[habit]
            settings.custom_zones[habit.value] = CustomZone(
                **{**asdict(zone), "name": zone.name.strip()}
            )
            cfg = settings.habit(habit)
            cfg.enabled = self._enabled[habit]
            cfg.dwell_s = self._dwell[habit]
