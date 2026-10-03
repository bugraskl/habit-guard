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
    for name in (
        "style.css",
        "site.js",
        "favicon.png",
        "og.png",
        "zones.svg",
        "demo.mp4",
        "demo-poster.jpg",
    ):
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
        assert len(shots) == 10
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
    from habit_guard.types import BUILT_IN_HABITS

    text = (site / "index.html").read_text(encoding="utf-8")
    for habit in BUILT_IN_HABITS:
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


def test_release_assets_fill_the_download_buttons(tmp_path: Path) -> None:
    base = "https://github.com/bugraskl/habit-guard/releases/download/v0.1.0"
    names = {
        "HabitGuard-0.1.0-windows-x64-setup.exe": 52_000_000,
        "HabitGuard-0.1.0-windows-x64-portable.zip": 81_000_000,
        "HabitGuard-0.1.0-macos-arm64.dmg": 75_000_000,
        "HabitGuard-0.1.0-linux-x86_64.AppImage": 90_000_000,
        "HabitGuard-0.1.0-linux-x86_64.tar.gz": 85_000_000,
        "SHA256SUMS.txt": 600,
    }
    release = {
        "tag_name": "v0.1.0",
        "html_url": f"{base.replace('/download/v0.1.0', '/tag/v0.1.0')}",
        "published_at": "2026-10-05T08:00:00Z",
        "assets": [
            {"name": n, "size": s, "browser_download_url": f"{base}/{n}"} for n, s in names.items()
        ],
    }
    builder.build(release, tmp_path / "out")
    for page in ("index.html", "tr/index.html"):
        text = (tmp_path / "out" / page).read_text(encoding="utf-8")
        for name in names:
            assert f"{base}/{name}" in text, (page, name)
        assert "52 MB" in text
        assert "1 kB" in text or "SHA256SUMS" in text
    en = (tmp_path / "out" / "index.html").read_text(encoding="utf-8")
    assert "October 5, 2026" in en


def test_without_a_release_the_buttons_point_at_the_releases_page(site: Path) -> None:
    text = (site / "index.html").read_text(encoding="utf-8")
    assert 'href="https://github.com/bugraskl/habit-guard/releases"' in text
    assert "data-windows-href" in text  # the primary button still picks the visitor's system


def test_human_size() -> None:
    assert builder.human_size(0) == ""
    assert builder.human_size(600) == "1 kB"
    assert builder.human_size(52_400_000) == "52 MB"


def test_the_video_is_local_muted_posted_and_described_on_both_pages(site: Path) -> None:
    for page in (site / "index.html", site / "tr" / "index.html"):
        text = page.read_text(encoding="utf-8")
        video = re.search(r"<video\b[^>]*>", text)
        assert video, page.name
        tag = video.group(0)
        for attribute in ("controls", "muted", "playsinline", "loop", "data-autoplay"):
            assert re.search(rf"\s{attribute}[\s>=]", tag), (page.name, attribute)
        # No bare "autoplay": the script starts it, and not for visitors who prefer less motion.
        assert not re.search(r"\sautoplay[\s>=]", tag), page.name
        assert 'preload="none"' in tag
        prefix = "../" if page.parent.name == "tr" else ""
        assert f'poster="{prefix}assets/demo-poster.jpg"' in tag
        assert 'width="1280"' in tag
        assert 'height="720"' in tag
        assert f'src="{prefix}assets/demo.mp4"' in text
        assert 'aria-describedby="watch-steps"' in tag
        assert text.count("<li><strong>") == 4  # the text description of what the video shows
    js = (site / "assets" / "site.js").read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in js
    assert "saveData" in js


def test_the_video_files_are_small_and_a_real_mp4_with_a_matching_poster(site: Path) -> None:
    video = (site / "assets" / "demo.mp4").read_bytes()
    assert video[4:8] == b"ftyp"  # an MP4
    assert len(video) < 5_000_000  # a visitor on a slow link only pays for it when it plays
    poster = (site / "assets" / "demo-poster.jpg").read_bytes()
    assert poster[:2] == b"\xff\xd8"  # a JPEG
    assert len(poster) < 200_000
    # "faststart": the index (moov) comes before the pictures (mdat), so playback begins at once
    assert video.find(b"moov") < video.find(b"mdat")


def test_the_readmes_show_the_animation_and_link_the_video() -> None:
    for name in ("README.md", "README.tr.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert 'src="assets/video/demo.webp"' in text, name
        # The website serves the MP4 as video/mp4, so a browser plays it where it opens.
        assert 'href="https://bugraskl.github.io/habit-guard/assets/demo.mp4"' in text, name
        assert 'alt="' in text.split("demo.webp")[1].split(">")[0], name
    for name in ("demo.webp", "demo.mp4", "demo-poster.jpg"):
        assert (ROOT / "assets" / "video" / name).is_file(), name
    webp = (ROOT / "assets" / "video" / "demo.webp").read_bytes()
    assert webp[:4] == b"RIFF"
    assert webp[8:12] == b"WEBP"
    assert b"ANIM" in webp  # animated, so GitHub plays it in the README
    assert len(webp) < 2_000_000
