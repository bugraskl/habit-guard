"""The tray icon and its menu: the app's home, since it has no main window."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from ..i18n import tr
from .icons import IconState, icon


class Tray(QObject):
    pause_toggled = Signal()
    pause_for_requested = Signal(int)  # minutes
    settings_requested = Signal()
    wizard_requested = Signal()
    preview_requested = Signal()
    stats_requested = Signal()
    test_requested = Signal()
    quit_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._state = IconState.ACTIVE
        self._status = ""
        self._today = 0
        self._paused = False
        self._tray = QSystemTrayIcon(icon(self._state))
        self._menu = QMenu()
        self._status_action = QAction(self._menu)
        self._status_action.setEnabled(False)
        self._today_action = QAction(self._menu)
        self._today_action.setEnabled(False)
        self._pause_action = QAction(self._menu)
        self._pause_for_menu = QMenu(self._menu)
        self._pause_for_actions = [
            (minutes, QAction(self._pause_for_menu), key)
            for minutes, key in (
                (15, "tray.pause_15m"),
                (60, "tray.pause_1h"),
                (180, "tray.pause_3h"),
            )
        ]
        self._preview_action = QAction(self._menu)
        self._stats_action = QAction(self._menu)
        self._settings_action = QAction(self._menu)
        self._wizard_action = QAction(self._menu)
        self._test_action = QAction(self._menu)
        self._quit_action = QAction(self._menu)
        for action in (
            self._status_action,
            self._today_action,
            None,
            self._pause_action,
            self._pause_for_menu,
            self._preview_action,
            self._stats_action,
            self._settings_action,
            self._wizard_action,
            self._test_action,
            None,
            self._quit_action,
        ):
            if action is None:
                self._menu.addSeparator()
            elif isinstance(action, QMenu):
                self._menu.addMenu(action)
            else:
                self._menu.addAction(action)
        for minutes, action, _ in self._pause_for_actions:
            self._pause_for_menu.addAction(action)
            action.triggered.connect(
                lambda _checked=False, m=minutes: self.pause_for_requested.emit(m)
            )
        self._pause_action.triggered.connect(self.pause_toggled)
        self._preview_action.triggered.connect(self.preview_requested)
        self._stats_action.triggered.connect(self.stats_requested)
        self._settings_action.triggered.connect(self.settings_requested)
        self._wizard_action.triggered.connect(self.wizard_requested)
        self._test_action.triggered.connect(self.test_requested)
        self._quit_action.triggered.connect(self.quit_requested)
        self._tray.setContextMenu(self._menu)
        self._tray.activated.connect(self._on_activated)
        self.retranslate()

    @property
    def available(self) -> bool:
        return QSystemTrayIcon.isSystemTrayAvailable()

    def show(self) -> None:
        self._tray.show()

    def hide(self) -> None:
        self._tray.hide()

    def retranslate(self) -> None:
        """Set every text again, after a language change."""
        self._pause_for_menu.setTitle(tr("tray.pause_for"))
        for _, action, key in self._pause_for_actions:
            action.setText(tr(key))
        self._preview_action.setText(tr("tray.preview"))
        self._stats_action.setText(tr("tray.stats"))
        self._settings_action.setText(tr("tray.settings"))
        self._wizard_action.setText(tr("tray.wizard"))
        self._test_action.setText(tr("tray.test"))
        self._quit_action.setText(tr("tray.quit"))
        self.set_paused(self._paused)
        self.set_today(self._today)
        self.set_status(self._status)

    def set_paused(self, paused: bool) -> None:
        self._paused = paused
        self._pause_action.setText(tr("tray.resume") if paused else tr("tray.pause"))

    def set_status(self, text: str) -> None:
        self._status = text
        self._status_action.setText(text)
        self._tray.setToolTip(tr("tray.tooltip", status=text))

    def set_today(self, count: int) -> None:
        self._today = count
        self._today_action.setText(tr("tray.today", n=count))

    def set_state(self, state: IconState) -> None:
        if state is not self._state:
            self._state = state
            self._tray.setIcon(icon(state))

    def notify(self, title: str, body: str) -> None:
        if QSystemTrayIcon.supportsMessages():
            self._tray.showMessage(title, body, icon(IconState.ALERT), 4000)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:  # a plain click
            self.settings_requested.emit()
