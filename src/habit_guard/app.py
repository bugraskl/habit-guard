"""The application: wires the camera thread, the decision engine, the alarms and the windows."""

from __future__ import annotations

import logging
from datetime import date

from PySide6.QtCore import QLockFile, QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication

from . import i18n, paths
from .alerts.curtain import Curtain
from .alerts.manager import AlertManager
from .alerts.sound import SoundPlayer
from .alerts.speech import Speaker
from .config import Settings
from .engine.decision import HabitEngine, Release, Trigger
from .stats import Stats
from .types import Habit, Observation
from .ui.icons import IconState, icon
from .ui.preview import PreviewWindow
from .ui.settings_dialog import SettingsDialog
from .ui.stats_dialog import StatsDialog
from .ui.tray import Tray
from .vision.pipeline import Pipeline, Status
from .zones import FaceFrame, Zone, build_zones, evaluate

log = logging.getLogger(__name__)

STATS_SAVE_MS = 60_000
TEST_ALARM_MS = 2500


class _Bridge(QObject):
    """Carries the camera thread's results to the Qt thread."""

    observation = Signal(object)
    status = Signal(object, str)


class Controller(QObject):
    def __init__(self, settings: Settings, source: int | str | None = None):
        super().__init__()
        self.settings = settings
        i18n.set_language(settings.language)
        self.stats = Stats.load(paths.stats_path())
        self.engine = HabitEngine(settings.dwell_map(), settings.engine_settings())
        self.tray = Tray()
        self._sound = SoundPlayer(paths.sounds_dir())
        self._speech = Speaker()
        self._curtain = Curtain()
        self.alerts = self._make_alerts(settings)
        self._bridge = _Bridge()
        self._bridge.observation.connect(self._on_observation)
        self._bridge.status.connect(self._on_status)
        self.pipeline = Pipeline(
            settings, self._bridge.observation.emit, self._bridge.status.emit, source=source
        )
        self._status = Status.STARTING
        self._detail = ""
        self._user_paused = False
        self._last_ts: float | None = None
        self._stats_dirty = False
        self._settings_dialog: SettingsDialog | None = None
        self._preview: PreviewWindow | None = None
        self._stats_window: StatsDialog | None = None

        self._save_timer = QTimer(self)
        self._save_timer.timeout.connect(self._save_stats)
        self._save_timer.start(STATS_SAVE_MS)

        self.tray.pause_toggled.connect(self.toggle_pause)
        self.tray.settings_requested.connect(self.open_settings)
        self.tray.preview_requested.connect(self.open_preview)
        self.tray.stats_requested.connect(self.open_stats)
        self.tray.test_requested.connect(lambda: self.test_alarm(self.settings))
        self.tray.quit_requested.connect(self.quit)

    # ------------------------------------------------------------------------------- setup
    def _make_alerts(self, settings: Settings) -> AlertManager:
        return AlertManager(
            settings,
            sound=self._sound,
            speech=self._speech,
            curtain=self._curtain,
            notify=self.tray.notify,
        )

    def start(self) -> None:
        self.tray.show()
        self._refresh_tray()
        if not self.settings.onboarded:
            self.tray.notify(i18n.tr("app.name"), i18n.tr("tray.first_run"))
            QTimer.singleShot(400, self.open_settings)
        self.pipeline.start(paused=not self.settings.any_habit_enabled())

    # ----------------------------------------------------------------------------- tracking
    def _on_status(self, status: Status, detail: str) -> None:
        self._status, self._detail = status, detail
        self._refresh_tray()

    def _on_observation(self, obs: Observation) -> None:
        if self._last_ts is not None and obs.face is not None:
            self.stats.add_watched(obs.ts - self._last_ts)
        self._last_ts = obs.ts

        frame: FaceFrame | None = None
        zones: list[Zone] = []
        counts: dict[Habit, int] = {}
        if obs.face is not None:
            frame = FaceFrame.from_face(obs.face)
        if frame is not None and self.settings.any_habit_enabled():
            zones = build_zones(frame, self.settings.zone_specs())
            counts = evaluate(frame, zones, obs.hands)

        for event in self.engine.update(obs.ts, counts):
            self._handle(event)
        if self._preview is not None and self._preview.isVisible():
            self._preview.show_observation(obs, frame, zones, counts)

    def _handle(self, event: Trigger | Release) -> None:
        if isinstance(event, Trigger):
            if event.first:
                self.stats.record(event.habit, date.today())
                self._stats_dirty = True
                self._refresh_stats()
            self.alerts.fire(event.habit, event.level, event.first)
        else:
            self.alerts.clear(event.habit)
        self._refresh_tray()

    def _calm_down(self) -> None:
        """Release every raised alarm (paused, camera lost, settings changed)."""
        for event in self.engine.reset():
            self._handle(event)
        self.alerts.clear()
        self._last_ts = None

    def toggle_pause(self) -> None:
        self._user_paused = not self._user_paused
        self._sync_pipeline()

    def _sync_pipeline(self) -> None:
        previewing = self._preview is not None and self._preview.isVisible()
        if previewing or (not self._user_paused and self.settings.any_habit_enabled()):
            self.pipeline.resume()
        else:
            self.pipeline.pause()
            self._calm_down()
        self.tray.set_paused(self._user_paused)
        self._refresh_tray()

    # ------------------------------------------------------------------------------ windows
    def open_settings(self) -> None:
        if self._settings_dialog is not None:
            self._settings_dialog.raise_()
            self._settings_dialog.activateWindow()
            return
        dialog = SettingsDialog(self.settings)
        dialog.applied.connect(self.apply_settings)
        dialog.test_requested.connect(self.test_alarm)
        dialog.finished.connect(lambda _: self._forget_settings_dialog())
        self._settings_dialog = dialog
        dialog.setWindowIcon(icon(IconState.ACTIVE))
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _forget_settings_dialog(self) -> None:
        if self._settings_dialog is not None:
            self._settings_dialog.deleteLater()
            self._settings_dialog = None

    def apply_settings(self, new: Settings) -> None:
        language_changed = new.language != self.settings.language
        self.settings = new
        try:
            new.save(paths.settings_path())
        except OSError:
            log.exception("could not save the settings")
        i18n.set_language(new.language)
        self.engine.dwell = new.dwell_map()
        self.engine.settings = new.engine_settings()
        self.alerts.settings = new
        self.pipeline.apply_settings(new)
        self._calm_down()
        self._sync_pipeline()
        if language_changed:
            self.tray.retranslate()
            for window in (self._preview, self._stats_window):
                if window is not None:
                    window.close()
            self._preview = None
            self._stats_window = None
        self._refresh_tray()

    def open_preview(self) -> None:
        if self._preview is None:
            self._preview = PreviewWindow()
            self._preview.setWindowIcon(icon(IconState.ACTIVE))
            self._preview.closed.connect(self._on_preview_closed)
        self.pipeline.set_preview(True)
        self._preview.show()
        self._preview.raise_()
        self._sync_pipeline()  # the preview works even while paused

    def _on_preview_closed(self) -> None:
        self.pipeline.set_preview(False)
        self._sync_pipeline()

    def open_stats(self) -> None:
        if self._stats_window is None:
            self._stats_window = StatsDialog()
            self._stats_window.setWindowIcon(icon(IconState.ACTIVE))
            self._stats_window.reset_requested.connect(self._reset_stats)
        self._refresh_stats()
        self._stats_window.show()
        self._stats_window.raise_()

    def _reset_stats(self) -> None:
        self.stats = Stats()
        self._stats_dirty = True
        self._save_stats()
        self._refresh_stats()
        self._refresh_tray()

    def test_alarm(self, settings: Settings) -> None:
        """Play the alarm the way ``settings`` have it, then calm it down again."""
        manager = self._make_alerts(settings)
        manager.test(2)
        # Calm it down again, unless a real alarm has started in the meantime.
        QTimer.singleShot(
            TEST_ALARM_MS, lambda: None if self.engine.active_habits() else manager.clear()
        )

    # ------------------------------------------------------------------------------ display
    def _refresh_stats(self) -> None:
        if self._stats_window is not None:
            self._stats_window.refresh(self.stats, date.today())

    def _refresh_tray(self) -> None:
        self.tray.set_today(self.stats.count(date.today()))
        if self._status is Status.ERROR:
            text = i18n.tr("tray.status.error", detail=self._detail)
            state = IconState.PROBLEM
        elif self._status is Status.NO_CAMERA:
            text, state = i18n.tr("tray.status.no_camera"), IconState.PROBLEM
        elif not self.settings.any_habit_enabled():
            text, state = i18n.tr("tray.status.nothing"), IconState.PAUSED
        elif self._user_paused or self._status is Status.PAUSED:
            text, state = i18n.tr("tray.status.paused"), IconState.PAUSED
        elif self._status is Status.STARTING:
            text, state = i18n.tr("tray.status.starting"), IconState.ACTIVE
        else:
            text, state = i18n.tr("tray.status.running"), IconState.ACTIVE
        if self.engine.active_habits():
            state = IconState.ALERT
        self.tray.set_status(text)
        self.tray.set_state(state)

    def _save_stats(self) -> None:
        if not self._stats_dirty and self.stats.watched_s == 0:
            return
        try:
            self.stats.save(paths.stats_path())
            self._stats_dirty = False
        except OSError:
            log.exception("could not save the statistics")

    # ------------------------------------------------------------------------------ shutdown
    def quit(self) -> None:
        self.pipeline.stop()
        self._calm_down()
        self._speech.stop()
        self._curtain.close()
        self._save_stats()
        self.tray.hide()
        app = QApplication.instance()
        if app is not None:
            app.quit()


def acquire_lock() -> QLockFile | None:
    """Take the single-instance lock; ``None`` if another Habit Guard is running."""
    paths.config_dir().mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(paths.lock_path()))
    lock.setStaleLockTime(0)  # a lock left by a crashed process is taken over at once
    return lock if lock.tryLock(200) else None


def run(settings: Settings, source: int | str | None = None) -> int:
    """Start the tray app and run until quit. Returns the process exit code."""
    import sys

    existing = QApplication.instance()
    app = existing if isinstance(existing, QApplication) else QApplication(sys.argv[:1])
    app.setApplicationName("Habit Guard")
    app.setQuitOnLastWindowClosed(False)
    lock = acquire_lock()
    if lock is None:
        print("Habit Guard is already running (look for its icon in the tray).", file=sys.stderr)
        return 1
    controller = Controller(settings, source)
    if not controller.tray.available:
        log.warning("no system tray here: the settings window opens instead")
        controller.open_settings()
    controller.start()
    app.aboutToQuit.connect(controller.pipeline.stop)
    code = app.exec()
    lock.unlock()
    return int(code)
