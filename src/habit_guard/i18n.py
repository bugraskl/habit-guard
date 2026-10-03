"""Interface text in English and Turkish.

Plain dictionaries keep this free of Qt's translation tooling: a test checks
that every string exists in every language, and a missing one falls back to
English instead of showing a key.
"""

from __future__ import annotations

import locale

from .types import Habit

LANGUAGES = ("en", "tr")

_STRINGS: dict[str, dict[str, str]] = {
    "app.name": {"en": "Habit Guard", "tr": "Habit Guard"},
    # --- habits
    "habit.nail_biting": {"en": "Nail and finger biting", "tr": "Tırnak ve parmak yeme"},
    "habit.mustache": {
        "en": "Mustache, beard and lip picking",
        "tr": "Bıyık, sakal ve dudak koparma",
    },
    "habit.hair_pulling": {"en": "Brow, lash and hair pulling", "tr": "Kaş, kirpik ve saç yolma"},
    "habit.face_touch": {
        "en": "Face touching and skin picking",
        "tr": "Yüze dokunma ve cilt kaşıma",
    },
    "habit.nail_biting.short": {"en": "nail biting", "tr": "tırnak yeme"},
    "habit.mustache.short": {"en": "mustache pulling", "tr": "bıyık koparma"},
    "habit.hair_pulling.short": {"en": "hair pulling", "tr": "kıl yolma"},
    "habit.face_touch.short": {"en": "face touching", "tr": "yüze dokunma"},
    "habit.custom_1": {"en": "Custom zone 1", "tr": "Özel bölge 1"},
    "habit.custom_2": {"en": "Custom zone 2", "tr": "Özel bölge 2"},
    "habit.custom_3": {"en": "Custom zone 3", "tr": "Özel bölge 3"},
    "habit.custom_1.short": {"en": "custom zone 1", "tr": "özel bölge 1"},
    "habit.custom_2.short": {"en": "custom zone 2", "tr": "özel bölge 2"},
    "habit.custom_3.short": {"en": "custom zone 3", "tr": "özel bölge 3"},
    "habit.wide.mustache": {
        "en": "Also the chin and beard line",
        "tr": "Çene ve sakal bölgesini de kapsa",
    },
    "habit.wide.hair_pulling": {"en": "Also the scalp", "tr": "Saçlı deriyi de kapsa"},
    # --- alerts
    "alert.title": {"en": "Hands down!", "tr": "Elini indir!"},
    "alert.body": {"en": "{habit} detected", "tr": "{habit} fark edildi"},
    "alert.speech": {"en": "Hands down.", "tr": "Elini indir."},
    # --- tray
    "tray.status.running": {"en": "Watching", "tr": "İzliyor"},
    "tray.status.paused": {"en": "Paused", "tr": "Duraklatıldı"},
    "tray.status.starting": {"en": "Starting…", "tr": "Başlıyor…"},
    "tray.status.no_camera": {
        "en": "Camera unavailable, trying again",
        "tr": "Kamera kullanılamıyor, tekrar deneniyor",
    },
    "tray.status.error": {"en": "Cannot start: {detail}", "tr": "Başlatılamadı: {detail}"},
    "tray.status.nothing": {
        "en": "No habit selected: open Settings",
        "tr": "Hiç alışkanlık seçilmedi: Ayarlar'ı açın",
    },
    "tray.status.paused_until": {
        "en": "Paused until {time}",
        "tr": "{time} saatine kadar duraklatıldı",
    },
    "tray.pause": {"en": "Pause tracking", "tr": "İzlemeyi duraklat"},
    "tray.pause_for": {"en": "Pause for…", "tr": "Şu süre duraklat…"},
    "tray.pause_15m": {"en": "15 minutes", "tr": "15 dakika"},
    "tray.pause_1h": {"en": "1 hour", "tr": "1 saat"},
    "tray.pause_3h": {"en": "3 hours", "tr": "3 saat"},
    "tray.resume": {"en": "Resume tracking", "tr": "İzlemeyi sürdür"},
    "tray.settings": {"en": "Settings…", "tr": "Ayarlar…"},
    "tray.preview": {"en": "Camera preview…", "tr": "Kamera önizleme…"},
    "tray.stats": {"en": "Statistics…", "tr": "İstatistikler…"},
    "tray.test": {"en": "Test the alarm", "tr": "Alarmı dene"},
    "tray.quit": {"en": "Quit Habit Guard", "tr": "Habit Guard'dan çık"},
    "tray.today": {"en": "Today: {n} alarms", "tr": "Bugün: {n} alarm"},
    "tray.tooltip": {"en": "Habit Guard: {status}", "tr": "Habit Guard: {status}"},
    "tray.first_run": {
        "en": "Pick the habits to watch in Settings. Nothing leaves your computer.",
        "tr": "Ayarlar'dan izlenecek alışkanlıkları seçin. Hiçbir veri bilgisayarınızdan çıkmaz.",
    },
    # --- settings
    "settings.title": {"en": "Habit Guard settings", "tr": "Habit Guard ayarları"},
    "settings.tab.habits": {"en": "Habits", "tr": "Alışkanlıklar"},
    "settings.tab.alerts": {"en": "Alarms", "tr": "Uyarılar"},
    "settings.tab.general": {"en": "General", "tr": "Genel"},
    "settings.tab.custom": {"en": "Custom zones", "tr": "Özel bölgeler"},
    "settings.custom.intro": {
        "en": "A habit that is not on the list? Draw its zone on the face: drag the shape to "
        "move it and its square handles to resize it.",
        "tr": "Listede olmayan bir alışkanlık mı var? Bölgesini yüzün üzerine çizin: şekli "
        "sürükleyerek taşıyın, kare tutamaçlarından çekerek boyutlandırın.",
    },
    "settings.custom.slot": {"en": "Zone", "tr": "Bölge"},
    "settings.custom.name": {"en": "Name", "tr": "Ad"},
    "settings.custom.name_hint": {"en": "e.g. ear picking", "tr": "örneğin kulak karıştırma"},
    "settings.custom.mirror": {
        "en": "Also on the other side of the face",
        "tr": "Yüzün öbür tarafında da",
    },
    "settings.custom.reset": {"en": "Reset the shape", "tr": "Şekli sıfırla"},
    "settings.custom.keys": {
        "en": "The arrow keys move the zone; Shift with the arrow keys resizes it.",
        "tr": "Ok tuşları bölgeyi taşır; Shift ile ok tuşları boyutunu değiştirir.",
    },
    "settings.custom.overlap": {
        "en": "Where zones overlap, your zone wins over the built-in ones (dashed lines).",
        "tr": "Bölgeler çakışırsa sizin çizdiğiniz bölge, yerleşik olanların (kesikli çizgiler) "
        "önüne geçer.",
    },
    "settings.habits.intro": {
        "en": "Choose what to watch for. A hand has to stay in the zone for the dwell time "
        "before the alarm goes off, so a quick scratch or a sip of water is ignored.",
        "tr": "Neyin izleneceğini seçin. Alarm, elin bölgede bekleme süresi kadar "
        "kalmasından sonra çalar; kısa bir kaşıma veya bir yudum su yok sayılır.",
    },
    "settings.habit.enabled": {"en": "Watch for this", "tr": "Bunu izle"},
    "settings.habit.dwell": {"en": "Alarm after", "tr": "Alarm süresi"},
    "settings.habit.scale": {"en": "Zone size", "tr": "Bölge boyutu"},
    "settings.unit.seconds": {"en": "{n} s", "tr": "{n} sn"},
    "settings.alerts.sound": {"en": "Play an alarm sound", "tr": "Alarm sesi çal"},
    "settings.alerts.volume": {"en": "Volume", "tr": "Ses düzeyi"},
    "settings.alerts.sound_file": {"en": "Own sound (WAV, MP3)", "tr": "Kendi sesiniz (WAV, MP3)"},
    "settings.alerts.browse": {"en": "Choose…", "tr": "Seç…"},
    "settings.alerts.clear": {"en": "Use built-in", "tr": "Yerleşiği kullan"},
    "settings.alerts.notification": {"en": "Show a notification", "tr": "Bildirim göster"},
    "settings.alerts.curtain": {
        "en": "Cover the screen until the hand is down",
        "tr": "El inene kadar ekranı kapat",
    },
    "settings.alerts.curtain_style": {"en": "Screen style", "tr": "Ekran biçimi"},
    "settings.alerts.style.dim": {"en": "Dim the screen", "tr": "Ekranı karart"},
    "settings.alerts.style.flash": {"en": "Pulsing red frame", "tr": "Yanıp sönen kırmızı çerçeve"},
    "settings.alerts.speech": {"en": "Say it out loud", "tr": "Sesli uyarı söyle"},
    "settings.alerts.speech_text": {"en": "Phrase", "tr": "Cümle"},
    "settings.alerts.speech_hint": {"en": "empty: default phrase", "tr": "boşsa: varsayılan cümle"},
    "settings.alerts.escalate": {
        "en": "Get louder and stronger while the hand stays",
        "tr": "El kaldıkça alarmı güçlendir",
    },
    "settings.alerts.repeat": {"en": "Step up every", "tr": "Güçlenme aralığı"},
    "settings.alerts.test": {"en": "Test the alarm", "tr": "Alarmı dene"},
    "settings.general.language": {"en": "Language", "tr": "Dil"},
    "settings.general.language.auto": {"en": "Automatic", "tr": "Otomatik"},
    "settings.general.camera": {"en": "Camera number", "tr": "Kamera numarası"},
    "settings.general.camera_api": {"en": "Camera interface", "tr": "Kamera arayüzü"},
    "settings.general.camera_api.auto": {"en": "Automatic", "tr": "Otomatik"},
    "settings.general.camera_api.dshow": {
        "en": "DirectShow (Windows)",
        "tr": "DirectShow (Windows)",
    },
    "settings.general.camera_api.msmf": {
        "en": "Media Foundation (Windows)",
        "tr": "Media Foundation (Windows)",
    },
    "settings.general.camera_api.any": {
        "en": "Operating system default",
        "tr": "Sistem varsayılanı",
    },
    "settings.general.camera_hint": {
        "en": "Most webcams can be used by one program at a time. If another app holds the "
        "camera, Habit Guard waits and tries again. Changing the interface sometimes lets two "
        "programs share it.",
        "tr": "Çoğu kamera aynı anda tek programca kullanılabilir. Kamerayı başka bir uygulama "
        "tutuyorsa Habit Guard bekler ve yeniden dener. Arayüzü değiştirmek bazen iki "
        "programın paylaşmasını sağlar.",
    },
    "settings.general.profile": {"en": "Performance", "tr": "Performans"},
    "settings.general.profile.eco": {"en": "Eco: lowest CPU use", "tr": "Eko: en düşük işlemci"},
    "settings.general.profile.balanced": {"en": "Balanced", "tr": "Dengeli"},
    "settings.general.profile.responsive": {
        "en": "Responsive: fastest alarm",
        "tr": "Hızlı: en çabuk alarm",
    },
    "settings.general.privacy": {
        "en": "Camera pictures are analysed in memory and never saved or sent anywhere.",
        "tr": "Kamera görüntüleri bellekte işlenir; hiçbir zaman kaydedilmez ya da gönderilmez.",
    },
    "settings.ok": {"en": "Save", "tr": "Kaydet"},
    "settings.cancel": {"en": "Cancel", "tr": "Vazgeç"},
    # --- preview
    "preview.title": {"en": "Camera preview", "tr": "Kamera önizleme"},
    "preview.hint": {
        "en": "Zones are drawn on your face. Move a hand to your mouth to see them react. "
        "Nothing here is recorded.",
        "tr": "Bölgeler yüzünüzün üzerine çizilir. Tepkilerini görmek için elinizi "
        "ağzınıza götürün. Buradaki hiçbir şey kaydedilmez.",
    },
    "preview.no_face": {"en": "No face in view", "tr": "Yüz görünmüyor"},
    "preview.face": {"en": "Face found", "tr": "Yüz bulundu"},
    "preview.hands": {"en": "Hands: {n}", "tr": "El: {n}"},
    "preview.waiting": {"en": "Waiting for the camera…", "tr": "Kamera bekleniyor…"},
    # --- statistics
    "stats.title": {"en": "Statistics", "tr": "İstatistikler"},
    "stats.today": {"en": "Today", "tr": "Bugün"},
    "stats.total": {"en": "All time", "tr": "Toplam"},
    "stats.clean": {"en": "Clean for", "tr": "Temiz süre"},
    "stats.best": {"en": "Best stretch", "tr": "En iyi süre"},
    "stats.week": {"en": "Last 7 days", "tr": "Son 7 gün"},
    "stats.by_habit": {"en": "By habit", "tr": "Alışkanlığa göre"},
    "stats.watched": {"en": "Watched time: {t}", "tr": "İzlenen süre: {t}"},
    "stats.reset": {"en": "Reset statistics", "tr": "İstatistikleri sıfırla"},
    "stats.reset_confirm": {
        "en": "Delete all counters and streaks?",
        "tr": "Tüm sayaçlar ve seriler silinsin mi?",
    },
    "duration.hm": {"en": "{h} h {m} min", "tr": "{h} sa {m} dk"},
    "duration.m": {"en": "{m} min", "tr": "{m} dk"},
    "duration.s": {"en": "{s} s", "tr": "{s} sn"},
}

_state = {"language": "en"}
#: What the user called their custom zones; set from the settings (see ``set_custom_names``).
_custom_names: dict[Habit, str] = {}


def detect_language() -> str:
    """The system's language, narrowed to one of ours."""
    try:
        code = (locale.getlocale()[0] or "").lower()
    except (ValueError, TypeError):  # pragma: no cover - exotic locale settings
        code = ""
    return "tr" if code.startswith(("tr", "turkish")) else "en"


def set_language(choice: str) -> str:
    """Select the interface language (``"auto"``, ``"en"`` or ``"tr"``); returns the one in use."""
    if choice == "auto":
        _state["language"] = detect_language()
    else:
        _state["language"] = choice if choice in LANGUAGES else "en"
    return _state["language"]


def current_language() -> str:
    return _state["language"]


def tr(key: str, **values: object) -> str:
    """The text for ``key`` in the current language, with ``{placeholders}`` filled in."""
    entry = _STRINGS.get(key)
    if entry is None:
        return key
    text = entry.get(_state["language"]) or entry["en"]
    return text.format(**values) if values else text


def set_custom_names(names: dict[Habit, str]) -> None:
    """Remember the names the user gave their custom zones; an empty name keeps the default."""
    _custom_names.clear()
    _custom_names.update({h: n for h, n in names.items() if n.strip()})


def upper_first(text: str) -> str:
    """``text`` with its first letter in capitals (the Turkish dotted and dotless i included)."""
    if not text:
        return text
    first = text[0]
    if _state["language"] == "tr":
        first = {"i": "İ", "ı": "I"}.get(first, first.upper())
    else:
        first = first.upper()
    return first + text[1:]


def habit_name(habit: Habit) -> str:
    name = _custom_names.get(habit)
    if name:
        return upper_first(name)
    return tr(f"habit.{habit.value}")


def habit_short(habit: Habit) -> str:
    name = _custom_names.get(habit)
    if name:
        return name
    return tr(f"habit.{habit.value}.short")


def format_duration(seconds: float) -> str:
    """``"2 h 05 min"``, ``"12 min"`` or ``"30 s"``."""
    total = int(seconds)
    if total >= 3600:
        return tr("duration.hm", h=total // 3600, m=f"{total % 3600 // 60:02d}")
    if total >= 60:
        return tr("duration.m", m=total // 60)
    return tr("duration.s", s=total)


def all_keys() -> list[str]:
    return list(_STRINGS)


def missing_translations() -> list[tuple[str, str]]:
    """``(key, language)`` pairs that have no text; a test keeps this empty."""
    return [(k, lang) for k, entry in _STRINGS.items() for lang in LANGUAGES if not entry.get(lang)]
