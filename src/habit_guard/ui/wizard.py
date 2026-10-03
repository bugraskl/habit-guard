"""The first-run setup: check the camera, choose what to watch, choose how to be told.

Five short pages. The camera page shows the live picture with a checklist (face, light, distance,
room for the hands, a hand raised) and says in words what to change when something is off, so a
first-time user is not left wondering why nothing is detected. While the wizard is open the app
raises no real alarms and keeps every picture only for the preview; the wizard edits a copy of the
settings and hands the result over with ``applied`` when it ends. Closing it counts as skipping.
"""

from __future__ import annotations

import copy

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..config import Settings
from ..i18n import habit_name, tr
from ..types import BUILT_IN_HABITS, Habit, Observation
from ..vision.quality import (
    DISTANCE_ISSUES,
    LIGHT_ISSUES,
    ROOM_ISSUES,
    QualityTracker,
    Report,
)
from ..zones import FaceFrame, build_zones, evaluate
from .preview import PreviewCanvas

PAGE_WELCOME, PAGE_CAMERA, PAGE_HABITS, PAGE_ALERTS, PAGE_DONE = range(5)
PAGES = 5
#: Seconds after which a camera that has shown no picture gets a hint.
NO_PICTURE_AFTER_S = 6.0

OK, BAD, PENDING = "ok", "bad", "pending"
_MARKS = {OK: ("✓", "#2e9e4f"), BAD: ("✗", "#d6453d"), PENDING: ("…", "#8a8f98")}


class _CheckRow(QWidget):
    """One line of the checklist: a mark and a label."""

    def __init__(self, text: str) -> None:
        super().__init__()
        self._mark = QLabel()
        self._mark.setFixedWidth(18)
        self._text = QLabel(text)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self._mark)
        row.addWidget(self._text, 1)
        self.state = PENDING
        self.set_state(PENDING)

    def set_state(self, state: str) -> None:
        self.state = state
        mark, color = _MARKS[state]
        self._mark.setText(mark)
        self._mark.setStyleSheet(f"color: {color}; font-weight: 700;")


def _title(text: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet("font-size: 18px; font-weight: 600;")
    label.setWordWrap(True)
    return label


def _paragraph(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    return label


class SetupWizard(QDialog):
    """Edits a copy of the settings; ``applied`` fires once, with the result, when it ends."""

    applied = Signal(object)
    test_requested = Signal(object)
    #: The camera number was changed on the camera page: ``(index, api)``.
    camera_requested = Signal(int, str)

    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._start = copy.deepcopy(settings)
        self._settings = copy.deepcopy(settings)
        self._tracker = QualityTracker()
        self._got_picture = False
        self._hands_seen = False
        self._finished = False
        self.setWindowTitle(tr("wizard.title"))
        self.setMinimumSize(660, 520)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._welcome_page())
        self._stack.addWidget(self._camera_page())
        self._stack.addWidget(self._habits_page())
        self._stack.addWidget(self._alerts_page())
        self._stack.addWidget(self._done_page())

        self.step_label = QLabel()
        self.back = QPushButton(tr("wizard.back"))
        self.next = QPushButton(tr("wizard.next"))
        self.next.setDefault(True)
        self.finish = QPushButton(tr("wizard.finish"))
        self.finish.setDefault(True)
        self.skip = QPushButton(tr("wizard.skip"))
        self.back.clicked.connect(self._go_back)
        self.next.clicked.connect(self._go_next)
        self.finish.clicked.connect(self._finish)
        self.skip.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        buttons.addWidget(self.skip)
        buttons.addWidget(self.step_label, 1, Qt.AlignmentFlag.AlignCenter)
        buttons.addWidget(self.back)
        buttons.addWidget(self.next)
        buttons.addWidget(self.finish)
        layout = QVBoxLayout(self)
        layout.addWidget(self._stack, 1)
        layout.addLayout(buttons)
        self._show_page(PAGE_WELCOME)

    # ------------------------------------------------------------------------------- pages
    def _welcome_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(_title(tr("wizard.welcome.title")))
        layout.addWidget(_paragraph(tr("wizard.welcome.text")))
        layout.addWidget(_paragraph(tr("wizard.welcome.privacy")))
        layout.addStretch(1)
        return page

    def _camera_page(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.addWidget(_title(tr("wizard.camera.title")))
        outer.addWidget(_paragraph(tr("wizard.camera.text")))
        row = QHBoxLayout()
        self.canvas = PreviewCanvas()
        self.canvas.setMinimumSize(360, 270)
        row.addWidget(self.canvas, 3)

        side = QVBoxLayout()
        self.checks = {
            "face": _CheckRow(tr("wizard.check.face")),
            "light": _CheckRow(tr("wizard.check.light")),
            "distance": _CheckRow(tr("wizard.check.distance")),
            "room": _CheckRow(tr("wizard.check.room")),
            "hands": _CheckRow(tr("wizard.check.hands")),
        }
        for check in self.checks.values():
            side.addWidget(check)
        self.advice = _paragraph("")
        self.advice.setMinimumHeight(70)
        side.addWidget(self.advice)
        camera_row = QHBoxLayout()
        camera_row.addWidget(QLabel(tr("settings.general.camera")))
        self.camera = QSpinBox()
        self.camera.setRange(0, 16)
        self.camera.setValue(self._settings.camera_index)
        self.camera.valueChanged.connect(self._on_camera_changed)
        camera_row.addWidget(self.camera)
        camera_row.addStretch(1)
        side.addLayout(camera_row)
        side.addStretch(1)
        row.addLayout(side, 2)
        outer.addLayout(row, 1)
        self._no_picture_timer = QTimer(self)
        self._no_picture_timer.setSingleShot(True)
        self._no_picture_timer.timeout.connect(self._hint_no_picture)
        return page

    def _habits_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(_title(tr("wizard.habits.title")))
        layout.addWidget(_paragraph(tr("wizard.habits.text")))
        self.habit_boxes: dict[Habit, QCheckBox] = {}
        for habit in BUILT_IN_HABITS:
            box = QCheckBox(habit_name(habit))
            box.setChecked(self._settings.habit(habit).enabled)
            hint = _paragraph(tr(f"wizard.habit.{habit.value}"))
            hint.setContentsMargins(24, 0, 0, 6)
            layout.addWidget(box)
            layout.addWidget(hint)
            self.habit_boxes[habit] = box
        layout.addStretch(1)
        return page

    def _alerts_page(self) -> QWidget:
        a = self._settings.alerts
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(_title(tr("wizard.alerts.title")))
        layout.addWidget(_paragraph(tr("wizard.alerts.text")))
        self.sound = QCheckBox(tr("settings.alerts.sound"))
        self.sound.setChecked(a.sound)
        self.notification = QCheckBox(tr("settings.alerts.notification"))
        self.notification.setChecked(a.notification)
        self.curtain = QCheckBox(tr("settings.alerts.curtain"))
        self.curtain.setChecked(a.curtain)
        self.speech = QCheckBox(tr("settings.alerts.speech"))
        self.speech.setChecked(a.speech)
        for box in (self.sound, self.notification, self.curtain, self.speech):
            layout.addWidget(box)
        volume_row = QHBoxLayout()
        volume_row.addWidget(QLabel(tr("settings.alerts.volume")))
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(round(a.volume * 100))
        volume_row.addWidget(self.volume, 1)
        layout.addLayout(volume_row)
        test = QPushButton(tr("settings.alerts.test"))
        test.clicked.connect(lambda: self.test_requested.emit(self.result_settings()))
        layout.addWidget(test, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)
        return page

    def _done_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(_title(tr("wizard.done.title")))
        self.summary = _paragraph("")
        layout.addWidget(self.summary)
        layout.addWidget(_paragraph(tr("wizard.done.text")))
        layout.addStretch(1)
        return page

    # ------------------------------------------------------------------------- navigation
    def page(self) -> int:
        return self._stack.currentIndex()

    def _show_page(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        self.back.setEnabled(index > PAGE_WELCOME)
        last = index == PAGE_DONE
        self.next.setVisible(not last)
        self.finish.setVisible(last)
        self.skip.setVisible(not last)
        self.step_label.setText(tr("wizard.step", n=index + 1, total=PAGES))
        if index == PAGE_CAMERA:
            self._enter_camera_page()
        else:
            self._no_picture_timer.stop()
        if last:
            self.summary.setText(self._summary_text())

    def _go_next(self) -> None:
        if self.page() < PAGE_DONE:
            self._show_page(self.page() + 1)

    def _go_back(self) -> None:
        if self.page() > PAGE_WELCOME:
            self._show_page(self.page() - 1)

    # ------------------------------------------------------------------------- the camera
    def _enter_camera_page(self) -> None:
        self._tracker.reset()
        self._got_picture = False
        self._no_picture_timer.start(int(NO_PICTURE_AFTER_S * 1000))
        self.advice.setText("")

    def _on_camera_changed(self, index: int) -> None:
        self._settings.camera_index = index
        self._got_picture = False
        self._tracker.reset()
        self.canvas.clear()
        self._no_picture_timer.start(int(NO_PICTURE_AFTER_S * 1000))
        self.advice.setText("")
        for check in self.checks.values():
            check.set_state(PENDING)
        self.camera_requested.emit(index, self._settings.camera_api)

    def _hint_no_picture(self) -> None:
        if not self._got_picture and self.page() == PAGE_CAMERA:
            self.advice.setText(tr("wizard.camera.busy"))

    def show_observation(self, obs: Observation) -> None:
        """A new camera observation; only the camera page looks at it."""
        if self.page() != PAGE_CAMERA:
            return
        self._got_picture = True
        self._no_picture_timer.stop()
        frame = FaceFrame.from_face(obs.face) if obs.face is not None else None
        zones = build_zones(frame, self._settings.zone_specs()) if frame is not None else []
        hits = evaluate(frame, zones, obs.hands) if frame is not None else {}
        self.canvas.show_observation(obs, frame, zones, hits)
        self.update_checks(self._tracker.update(obs))

    def update_checks(self, report: Report) -> None:
        """Show ``report`` in the checklist and say what to fix first."""
        self._hands_seen = self._hands_seen or report.hands > 0

        def state(bad: bool) -> str:
            return PENDING if not report.face_found else (BAD if bad else OK)

        self.checks["face"].set_state(OK if report.face_found else BAD)
        self.checks["light"].set_state(state(bool(report.issues & LIGHT_ISSUES)))
        self.checks["distance"].set_state(state(bool(report.issues & DISTANCE_ISSUES)))
        self.checks["room"].set_state(state(bool(report.issues & ROOM_ISSUES)))
        self.checks["hands"].set_state(OK if self._hands_seen else PENDING)
        issue = report.first_issue()
        if issue is not None:
            self.advice.setText(tr(f"quality.{issue.value}"))
        elif self._hands_seen:
            self.advice.setText(tr("wizard.camera.all_good"))
        else:
            self.advice.setText(tr("wizard.camera.raise_hand"))

    # --------------------------------------------------------------------------- the result
    def _summary_text(self) -> str:
        chosen = [habit_name(h) for h, box in self.habit_boxes.items() if box.isChecked()]
        if not chosen:
            return tr("wizard.done.none")
        return tr("wizard.done.watching", habits=", ".join(chosen))

    def result_settings(self) -> Settings:
        """The settings as the wizard has them right now."""
        out = copy.deepcopy(self._settings)
        for habit, box in self.habit_boxes.items():
            out.habit(habit).enabled = box.isChecked()
        a = out.alerts
        a.sound = self.sound.isChecked()
        a.notification = self.notification.isChecked()
        a.curtain = self.curtain.isChecked()
        a.speech = self.speech.isChecked()
        a.volume = self.volume.value() / 100.0
        out.camera_index = self.camera.value()
        out.onboarded = True
        return out

    def _finish(self) -> None:
        self._finished = True
        self.applied.emit(self.result_settings())
        self.accept()

    def reject(self) -> None:
        """Skip: keep the settings as they were (only remember that setup was shown)."""
        if not self._finished:
            self._finished = True
            skipped = copy.deepcopy(self._start)
            skipped.onboarded = True
            self.applied.emit(skipped)
        super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._finished:
            self.reject()
        super().closeEvent(event)
