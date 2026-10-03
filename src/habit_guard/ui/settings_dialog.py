"""The settings window: habits, alarms and general options."""

from __future__ import annotations

import copy

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..alerts.sound import FILE_DIALOG_FILTER
from ..config import CAMERA_APIS, CURTAIN_STYLES, LANGUAGES, PROFILES, Settings
from ..i18n import habit_name, tr
from ..types import BUILT_IN_HABITS, Habit
from .custom_zones_tab import CustomZonesTab

#: Habits that have a "wider area" option.
WIDE_HABITS = (Habit.MUSTACHE, Habit.HAIR_PULLING)
#: Habits that can also count a hand lying on the mouth when the fingertips are hidden.
HIDDEN_TIPS_HABITS = (Habit.NAIL_BITING,)


def _combo(options: list[tuple[str, str]], current: str) -> QComboBox:
    box = QComboBox()
    for value, label in options:
        box.addItem(label, value)
    index = box.findData(current)
    box.setCurrentIndex(max(0, index))
    return box


class _HabitBox(QGroupBox):
    """The controls of one habit."""

    def __init__(self, habit: Habit, settings: Settings):
        super().__init__(habit_name(habit))
        cfg = settings.habit(habit)
        self.habit = habit
        self.setCheckable(True)
        self.setChecked(cfg.enabled)
        form = QFormLayout(self)
        self.dwell = QDoubleSpinBox()
        self.dwell.setRange(0.3, 30.0)
        self.dwell.setSingleStep(0.1)
        self.dwell.setDecimals(1)
        self.dwell.setSuffix(tr("settings.unit.seconds", n="").rstrip())
        self.dwell.setValue(cfg.dwell_s)
        form.addRow(tr("settings.habit.dwell"), self.dwell)
        self.scale = QSlider(Qt.Orientation.Horizontal)
        self.scale.setRange(50, 200)
        self.scale.setValue(round(cfg.zone_scale * 100))
        self.scale_label = QLabel()
        self.scale.valueChanged.connect(lambda v: self.scale_label.setText(f"{v} %"))
        self.scale_label.setText(f"{self.scale.value()} %")
        row = QHBoxLayout()
        row.addWidget(self.scale, 1)
        row.addWidget(self.scale_label)
        form.addRow(tr("settings.habit.scale"), row)
        self.wide: QCheckBox | None = None
        if habit in WIDE_HABITS:
            self.wide = QCheckBox(tr(f"habit.wide.{habit.value}"))
            self.wide.setChecked(cfg.wide_area)
            form.addRow(self.wide)
        self.hidden_tips: QCheckBox | None = None
        if habit in HIDDEN_TIPS_HABITS:
            self.hidden_tips = QCheckBox(tr("settings.habit.hidden_tips"))
            self.hidden_tips.setChecked(cfg.hidden_tips)
            form.addRow(self.hidden_tips)

    def apply(self, settings: Settings) -> None:
        cfg = settings.habit(self.habit)
        cfg.enabled = self.isChecked()
        cfg.dwell_s = round(self.dwell.value(), 1)
        cfg.zone_scale = self.scale.value() / 100.0
        if self.wide is not None:
            cfg.wide_area = self.wide.isChecked()
        if self.hidden_tips is not None:
            cfg.hidden_tips = self.hidden_tips.isChecked()


class SettingsDialog(QDialog):
    """Edits a copy of the settings; ``applied`` fires with the new ones on Save."""

    applied = Signal(object)
    test_requested = Signal(object)

    def __init__(self, settings: Settings, parent: QWidget | None = None):
        super().__init__(parent)
        self._settings = copy.deepcopy(settings)
        self.setWindowTitle(tr("settings.title"))
        self.setMinimumWidth(480)
        tabs = QTabWidget()
        tabs.addTab(self._habits_tab(), tr("settings.tab.habits"))
        self._custom_tab = CustomZonesTab(self._settings)
        tabs.addTab(self._custom_tab, tr("settings.tab.custom"))
        tabs.addTab(self._alerts_tab(), tr("settings.tab.alerts"))
        tabs.addTab(self._general_tab(), tr("settings.tab.general"))
        save = QPushButton(tr("settings.ok"))
        save.setDefault(True)
        cancel = QPushButton(tr("settings.cancel"))
        save.clicked.connect(self._save)
        cancel.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addLayout(buttons)

    # -------------------------------------------------------------------------------- tabs
    def _habits_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        intro = QLabel(tr("settings.habits.intro"))
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self._habit_boxes = [_HabitBox(h, self._settings) for h in BUILT_IN_HABITS]
        for box in self._habit_boxes:
            layout.addWidget(box)
        layout.addStretch(1)
        return page

    def _alerts_tab(self) -> QWidget:
        a = self._settings.alerts
        page = QWidget()
        form = QFormLayout(page)
        self.sound = QCheckBox(tr("settings.alerts.sound"))
        self.sound.setChecked(a.sound)
        form.addRow(self.sound)
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(round(a.volume * 100))
        form.addRow(tr("settings.alerts.volume"), self.volume)
        self.sound_file = QLineEdit(a.sound_file)
        self.sound_file.setReadOnly(True)
        browse = QPushButton(tr("settings.alerts.browse"))
        browse.clicked.connect(self._browse_sound)
        clear = QPushButton(tr("settings.alerts.clear"))
        clear.clicked.connect(lambda: self.sound_file.setText(""))
        row = QHBoxLayout()
        row.addWidget(self.sound_file, 1)
        row.addWidget(browse)
        row.addWidget(clear)
        form.addRow(tr("settings.alerts.sound_file"), row)

        self.notification = QCheckBox(tr("settings.alerts.notification"))
        self.notification.setChecked(a.notification)
        form.addRow(self.notification)

        self.curtain = QCheckBox(tr("settings.alerts.curtain"))
        self.curtain.setChecked(a.curtain)
        form.addRow(self.curtain)
        self.curtain_style = _combo(
            [(s, tr(f"settings.alerts.style.{s}")) for s in CURTAIN_STYLES], a.curtain_style
        )
        form.addRow(tr("settings.alerts.curtain_style"), self.curtain_style)

        self.speech = QCheckBox(tr("settings.alerts.speech"))
        self.speech.setChecked(a.speech)
        form.addRow(self.speech)
        self.speech_text = QLineEdit(a.speech_text)
        self.speech_text.setPlaceholderText(tr("settings.alerts.speech_hint"))
        self.speech_text.setMaxLength(200)
        form.addRow(tr("settings.alerts.speech_text"), self.speech_text)

        self.escalate = QCheckBox(tr("settings.alerts.escalate"))
        self.escalate.setChecked(a.escalate)
        form.addRow(self.escalate)
        self.repeat = QDoubleSpinBox()
        self.repeat.setRange(1.0, 60.0)
        self.repeat.setDecimals(1)
        self.repeat.setSingleStep(0.5)
        self.repeat.setValue(a.repeat_s)
        form.addRow(tr("settings.alerts.repeat"), self.repeat)

        test = QPushButton(tr("settings.alerts.test"))
        test.clicked.connect(lambda: self.test_requested.emit(self.result_settings()))
        form.addRow(test)
        return page

    def _general_tab(self) -> QWidget:
        s = self._settings
        page = QWidget()
        form = QFormLayout(page)
        self.language = _combo(
            [
                (code, tr("settings.general.language.auto") if code == "auto" else label)
                for code, label in zip(LANGUAGES, ("auto", "English", "Türkçe"), strict=True)
            ],
            s.language,
        )
        form.addRow(tr("settings.general.language"), self.language)
        self.camera = QSpinBox()
        self.camera.setRange(0, 16)
        self.camera.setValue(s.camera_index)
        form.addRow(tr("settings.general.camera"), self.camera)
        self.camera_api = _combo(
            [(a, tr(f"settings.general.camera_api.{a}")) for a in CAMERA_APIS], s.camera_api
        )
        form.addRow(tr("settings.general.camera_api"), self.camera_api)
        camera_hint = QLabel(tr("settings.general.camera_hint"))
        camera_hint.setWordWrap(True)
        form.addRow(camera_hint)
        self.profile = _combo(
            [(p, tr(f"settings.general.profile.{p}")) for p in PROFILES], s.profile
        )
        form.addRow(tr("settings.general.profile"), self.profile)
        note = QLabel(tr("settings.general.privacy"))
        note.setWordWrap(True)
        form.addRow(note)
        return page

    # -------------------------------------------------------------------------------- logic
    def _browse_sound(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, tr("settings.alerts.sound_file"), "", FILE_DIALOG_FILTER
        )
        if path:
            self.sound_file.setText(path)

    def result_settings(self) -> Settings:
        """The settings as the controls show them right now."""
        out = copy.deepcopy(self._settings)
        for box in self._habit_boxes:
            box.apply(out)
        self._custom_tab.apply(out)
        a = out.alerts
        a.sound = self.sound.isChecked()
        a.volume = self.volume.value() / 100.0
        a.sound_file = self.sound_file.text()
        a.notification = self.notification.isChecked()
        a.curtain = self.curtain.isChecked()
        a.curtain_style = str(self.curtain_style.currentData())
        a.speech = self.speech.isChecked()
        a.speech_text = self.speech_text.text().strip()
        a.escalate = self.escalate.isChecked()
        a.repeat_s = round(self.repeat.value(), 1)
        out.language = str(self.language.currentData())
        out.camera_index = self.camera.value()
        out.camera_api = str(self.camera_api.currentData())
        out.profile = str(self.profile.currentData())
        out.onboarded = True
        return out

    def _save(self) -> None:
        self.applied.emit(self.result_settings())
        self.accept()
