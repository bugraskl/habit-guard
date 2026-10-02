"""The repository's own guard rails: the privacy scan, the model manifest, the fetch script."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

from habit_guard.paths import models_dir
from habit_guard.vision import manifest

ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


privacy = load_script("check_privacy")
fetch = load_script("fetch_models")


# ------------------------------------------------------------------------------ privacy
def test_the_application_code_passes_its_own_privacy_scan() -> None:
    violations = privacy.scan_paths([privacy.DEFAULT_TARGET])
    assert violations == [], "\n".join(str(v) for v in violations)


@pytest.mark.parametrize(
    "snippet",
    [
        "import socket",
        "import requests",
        "from urllib import request",
        "from urllib.request import urlopen",
        "import http.client",
        "from PySide6.QtNetwork import QTcpSocket",
        "import PySide6.QtNetwork",
        "import asyncio",
        "import cv2\ncv2.imwrite('x.png', f)",
        "from cv2 import imwrite",
        "import cv2\nw = cv2.VideoWriter('x.avi', 0, 30, (1, 1))",
        "import cv2\ncv2.imencode('.jpg', f)",
        "widget.grab().save('x.png')",
        "image.save('x.png')",
    ],
)
def test_privacy_scan_flags_networking_and_picture_writing(snippet: str) -> None:
    assert privacy.scan_source(snippet), snippet


@pytest.mark.parametrize(
    "snippet",
    [
        "import subprocess",
        "import urllib.parse",
        "from urllib.parse import quote",
        "import json\njson.dump({}, fh)",
        "settings.save(path)",
        "import cv2\ncv2.resize(f, (1, 1))",
    ],
)
def test_privacy_scan_leaves_harmless_code_alone(snippet: str) -> None:
    assert privacy.scan_source(snippet) == []


def test_privacy_scan_cli_reports_and_exits_nonzero(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    bad = tmp_path / "bad.py"
    bad.write_text("import requests\n", encoding="utf-8")
    assert privacy.main([str(bad)]) == 1
    assert "imports requests" in capsys.readouterr().err
    good = tmp_path / "good.py"
    good.write_text("x = 1\n", encoding="utf-8")
    assert privacy.main([str(good)]) == 0


# ------------------------------------------------------------------------------- models
def test_bundled_models_match_the_manifest() -> None:
    assert manifest.verify(models_dir()) == dict.fromkeys(manifest.MODEL_SHA256, "ok")


def test_every_manifest_entry_has_a_download_source_and_the_other_way_round() -> None:
    assert {s.filename for s in fetch.SOURCES} == set(manifest.MODEL_SHA256)
    for source in fetch.SOURCES:
        assert source.url.startswith("https://github.com/opencv/opencv_zoo/raw/")
        assert fetch.ZOO_COMMIT in source.url  # pinned to a commit, never to a moving branch


def test_fetch_check_mode_reports_missing_models_without_the_network(tmp_path: Path) -> None:
    assert fetch.main(["--check", "--dest", str(tmp_path)]) == 1
    assert fetch.main(["--check", "--dest", str(models_dir())]) == 0


def test_fetch_detects_a_corrupt_model(tmp_path: Path) -> None:
    source = fetch.SOURCES[0]
    (tmp_path / source.filename).write_bytes(b"not a model")
    assert fetch.verify(source, tmp_path) == "mismatch"


def test_model_notice_documents_every_model() -> None:
    notice = (models_dir() / "NOTICE.md").read_text(encoding="utf-8")
    for name, digest in manifest.MODEL_SHA256.items():
        assert name in notice
        assert digest in notice
    for licence in ("LICENSE-APACHE-2.0.txt", "LICENSE-YUNET.txt"):
        assert (models_dir() / "licenses" / licence).is_file()
