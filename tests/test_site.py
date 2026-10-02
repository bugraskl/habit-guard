"""The website: it builds, both languages match, nothing is loaded from other sites."""

from __future__ import annotations

import importlib.util
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_builder():  # type: ignore[no-untyped-def]
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("build_site", ROOT / "scripts" / "build_site.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["build_site"] = module
    spec.loader.exec_module(module)
    return module


builder = _load_builder()
pytest.importorskip("PIL")


@pytest.fixture(scope="module")
def site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("site")
    builder.build({}, out)
    return out


class Collector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.links: list[tuple[str, str, str]] = []  # tag, attribute, value
        self.images: list[dict[str, str | None]] = []
        self.lang = ""
        self.headings: list[str] = []
        self._tag = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        self._tag = tag
        if tag == "html":
            self.lang = a.get("lang") or ""
        if a.get("id"):
            self.ids.append(str(a["id"]))
        for attr in ("href", "src"):
            if a.get(attr):
                self.links.append((tag, attr, str(a[attr])))
        if tag == "img":
            self.images.append(a)

    def handle_data(self, data: str) -> None:
        if self._tag in {"h1", "h2"} and data.strip():
            self.headings.append(data.strip())


def parse(path: Path) -> Collector:
    collector = Collector()
    collector.feed(path.read_text(encoding="utf-8"))
    return collector


def test_the_site_builds_both_languages(site: Path) -> None:
    assert (site / "index.html").is_file()
    assert (site / "tr" / "index.html").is_file()
    assert (site / ".nojekyll").is_file()
    for name in ("style.css", "site.js", "favicon.png", "og.png", "zones.svg"):
        assert (site / "assets" / name).is_file(), name


def test_no_placeholder_is_left_over(site: Path) -> None:
    for page in (site / "index.html", site / "tr" / "index.html"):
        text = page.read_text(encoding="utf-8")
        assert re.findall(r"\{\{[A-Z_:a-z0-9/.\-]+\}\}", text) == [], page


def test_languages_are_declared_and_the_pages_have_the_same_structure(site: Path) -> None:
    en, tr = parse(site / "index.html"), parse(site / "tr" / "index.html")
    assert (en.lang, tr.lang) == ("en", "tr")
    assert en.ids == tr.ids  # the same sections and elements, in the same order
    assert len(en.headings) == len(tr.headings)
    assert len(en.images) == len(tr.images)
    assert len(en.links) == len(tr.links)


def test_every_local_link_and_image_exists(site: Path) -> None:
    for page in (site / "index.html", site / "tr" / "index.html"):
        collected = parse(page)
        for _tag, _attr, value in collected.links:
            if value.startswith(("http://", "https://", "mailto:", "#", "data:")):
                continue
            target = (page.parent / value.split("#", 1)[0]).resolve()
            if target.is_dir():
                target = target / "index.html"
            assert target.exists(), f"{page.name}: {value}"
        for anchor in (v for _t, a, v in collected.links if v.startswith("#") and len(v) > 1):
            assert anchor[1:] in collected.ids, f"{page.name}: {anchor}"


def test_screenshots_match_the_page_language_and_have_sizes_and_alt_text(site: Path) -> None:
    for lang, page in (("en", site / "index.html"), ("tr", site / "tr" / "index.html")):
        shots = [i for i in parse(page).images if "screenshots" in str(i.get("src"))]
        assert len(shots) == 8
        for image in shots:
            assert f"/screenshots/{lang}/" in str(image["src"])
            assert image.get("width")
            assert image.get("height")
            assert len(str(image.get("alt"))) > 20


def test_nothing_is_loaded_from_other_sites(site: Path) -> None:
    for page in (site / "index.html", site / "tr" / "index.html"):
        for tag, attr, value in parse(page).links:
            if tag in {"script", "img", "link", "iframe", "source"} and attr == "src":
                assert not value.startswith(("http", "//")), (page.name, tag, value)
        text = page.read_text(encoding="utf-8")
        assert not re.search(r'<link[^>]+rel="stylesheet"[^>]+href="https?:', text)
        assert "fonts.googleapis" not in text
    css = (site / "assets" / "style.css").read_text(encoding="utf-8")
    assert "url(http" not in css
    assert "@import" not in css
    js = (site / "assets" / "site.js").read_text(encoding="utf-8")
    for forbidden in ("fetch(", "XMLHttpRequest", "localStorage", "document.cookie", "sendBeacon"):
        assert forbidden not in js


def test_the_demo_zones_come_from_the_real_geometry(site: Path) -> None:
    from habit_guard.types import Habit

    text = (site / "index.html").read_text(encoding="utf-8")
    for habit in Habit:
        assert f'data-habit="{habit.value}"' in text
        assert f"data-{habit.value.replace('_', '-')}=" in text  # a fingertip target for each
    assert text.count('class="zone zone-') == 4


def test_release_data_fills_the_version_and_the_date(tmp_path: Path) -> None:
    release = {
        "tag_name": "v9.9.9",
        "html_url": "https://github.com/bugraskl/habit-guard/releases/tag/v9.9.9",
        "published_at": "2026-10-05T08:00:00Z",
    }
    builder.build(release, tmp_path / "out")
    en = (tmp_path / "out" / "index.html").read_text(encoding="utf-8")
    assert "Version 9.9.9" in en
    assert release["html_url"] in en
    assert builder.human_date(release["published_at"], "tr") == "5 Ekim 2026"
    assert builder.human_date(release["published_at"], "en") == "October 5, 2026"
    assert builder.human_date("garbage", "en") == ""


def test_unknown_placeholders_stop_the_build(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        builder.render("{{NO_SUCH_THING}}", {"VERSION": "1"}, tmp_path / "x.html")
