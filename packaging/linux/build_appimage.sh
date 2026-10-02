#!/usr/bin/env bash
# Package the Linux PyInstaller build as an AppImage and a tarball.
#
# Usage (from the repository root, after PyInstaller):
#   bash packaging/linux/build_appimage.sh [--version X.Y.Z] [--dist DIR]
#        [--appimagetool PATH] [--runtime-file PATH] [--allow-unpinned]
#
# Writes to DIST (default: dist/):
#   HabitGuard-<version>-linux-<arch>.AppImage
#   HabitGuard-<version>-linux-<arch>.tar.gz   (habit-guard/ with desktop file, icon, licence)
#
# appimagetool is taken from --appimagetool, $APPIMAGETOOL or PATH; if none is
# found, the pinned release below is downloaded into build/tools/ and verified
# against its SHA-256. The AppImage runtime (the ELF header users execute first)
# is pinned the same way and passed with --runtime-file, so appimagetool never
# embeds whatever its "continuous" channel serves at build time. Override with
# --runtime-file / $APPIMAGE_RUNTIME (a local file, checked if
# $APPIMAGE_RUNTIME_SHA256 is set) or $APPIMAGETOOL_URL + $APPIMAGETOOL_SHA256.
# A download without a checksum is refused unless --allow-unpinned is given.
# Where FUSE is unavailable (containers, CI) export APPIMAGE_EXTRACT_AND_RUN=1.
# Set UPDATE_INFORMATION to embed AppImage update information; a .zsync file is
# written next to the AppImage when appimagetool can produce one.
#
# Qt's X11 (xcb) platform plugin needs libxcb-cursor.so.0, which several
# distributions do not install by default; it is copied into both packages from
# the build machine if PyInstaller did not already collect it
# (install it with: sudo apt install libxcb-cursor0).
set -euo pipefail

die() { echo "build_appimage: $*" >&2; exit 1; }

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
DIST="$ROOT/dist"
VERSION=""
APPIMAGETOOL="${APPIMAGETOOL:-}"
RUNTIME_FILE="${APPIMAGE_RUNTIME:-}"
ALLOW_UNPINNED=0

# Pinned third-party build tools. To update: pick a tagged release, and copy the
# SHA-256 of each asset from the release page (or `sha256sum` a downloaded copy).
APPIMAGETOOL_VERSION="1.9.1"        # https://github.com/AppImage/appimagetool/releases
APPIMAGE_RUNTIME_VERSION="20251108" # https://github.com/AppImage/type2-runtime/releases

pinned_sha256() {
  case "$1:$2" in
    appimagetool:x86_64) echo "ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0" ;;
    appimagetool:aarch64) echo "f0837e7448a0c1e4e650a93bb3e85802546e60654ef287576f46c71c126a9158" ;;
    runtime:x86_64) echo "2fca8b443c92510f1483a883f60061ad09b46b978b2631c807cd873a47ec260d" ;;
    runtime:aarch64) echo "00cbdfcf917cc6c0ff6d3347d59e0ca1f7f45a6df1a428a0d6d8a78664d87444" ;;
    *) return 1 ;;
  esac
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version) VERSION="${2:?--version needs a value}"; shift 2 ;;
    --dist) DIST="${2:?--dist needs a path}"; shift 2 ;;
    --appimagetool) APPIMAGETOOL="${2:?--appimagetool needs a path}"; shift 2 ;;
    --runtime-file) RUNTIME_FILE="${2:?--runtime-file needs a path}"; shift 2 ;;
    --allow-unpinned) ALLOW_UNPINNED=1; shift ;;
    -h|--help) sed -n '2,27p' "$0"; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

[[ "$(uname -s)" == "Linux" ]] || die "this script builds Linux packages; run it on Linux"

if [[ -z "$VERSION" ]]; then
  VERSION="$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' "$ROOT/src/habit_guard/__init__.py")"
  [[ -n "$VERSION" ]] || die "cannot read __version__ from src/habit_guard/__init__.py"
fi
ARCH="${ARCH:-$(uname -m)}"
DIST="$(mkdir -p "$DIST" && cd "$DIST" && pwd)"

BUNDLE="$DIST/habit-guard"
DESKTOP="$HERE/habit-guard.desktop"
ICON="$HERE/habit-guard.png"
[[ -x "$BUNDLE/habit-guard" ]] || die "PyInstaller output not found: $BUNDLE/habit-guard"
[[ -f "$ICON" ]] || die "missing $ICON; run: uv run python scripts/make_icons.py"

BASENAME="HabitGuard-$VERSION-linux-$ARCH"
TARBALL="$DIST/$BASENAME.tar.gz"
APPIMAGE="$DIST/$BASENAME.AppImage"

# ------------------------------------------------------------------ build tools
is_verified() {
  local file="$1" sha256="$2"
  [[ -f "$file" ]] && echo "$sha256  $file" | sha256sum --check --status
}

# Download URL to DEST (atomically) unless a copy with the expected checksum is
# already there. An empty checksum is refused unless --allow-unpinned was given.
fetch_verified() {
  local url="$1" dest="$2" sha256="$3"
  if [[ -n "$sha256" ]] && is_verified "$dest" "$sha256"; then
    return 0
  fi
  if [[ -z "$sha256" ]]; then
    [[ "$ALLOW_UNPINNED" == 1 ]]       || die "refusing to download $url without a SHA-256 (set one, or pass --allow-unpinned)"
    echo "build_appimage: warning: $url is not verified (--allow-unpinned)" >&2
  fi
  command -v curl >/dev/null 2>&1 || die "curl is needed to download $url"
  echo "==> Downloading $url"
  mkdir -p "$(dirname "$dest")"
  curl --fail --location --silent --show-error --retry 3 --output "$dest.part" "$url"
  if [[ -n "$sha256" ]] && ! is_verified "$dest.part" "$sha256"; then
    rm -f "$dest.part"
    die "checksum mismatch for $url (expected $sha256)"
  fi
  mv "$dest.part" "$dest"
}

find_appimagetool() {
  if [[ -n "$APPIMAGETOOL" ]]; then
    if [[ -x "$APPIMAGETOOL" ]]; then return 0; fi
    if command -v "$APPIMAGETOOL" >/dev/null 2>&1; then
      APPIMAGETOOL="$(command -v "$APPIMAGETOOL")"
      return 0
    fi
    die "appimagetool not found: $APPIMAGETOOL"
  fi
  if command -v appimagetool >/dev/null 2>&1; then
    APPIMAGETOOL="$(command -v appimagetool)"
    return 0
  fi

  local url sha256 name
  if [[ -n "${APPIMAGETOOL_URL:-}" ]]; then
    url="$APPIMAGETOOL_URL"
    sha256="${APPIMAGETOOL_SHA256:-}"
    name="appimagetool-custom-$ARCH.AppImage"
  else
    url="https://github.com/AppImage/appimagetool/releases/download/$APPIMAGETOOL_VERSION/appimagetool-$ARCH.AppImage"
    sha256="${APPIMAGETOOL_SHA256:-$(pinned_sha256 appimagetool "$ARCH" || true)}"
    name="appimagetool-$APPIMAGETOOL_VERSION-$ARCH.AppImage"
  fi
  APPIMAGETOOL="$ROOT/build/tools/$name"
  fetch_verified "$url" "$APPIMAGETOOL" "$sha256"
  chmod 755 "$APPIMAGETOOL"
}

find_runtime() {
  if [[ -n "$RUNTIME_FILE" ]]; then
    [[ -f "$RUNTIME_FILE" ]] || die "AppImage runtime not found: $RUNTIME_FILE"
    if [[ -n "${APPIMAGE_RUNTIME_SHA256:-}" ]]; then
      is_verified "$RUNTIME_FILE" "$APPIMAGE_RUNTIME_SHA256"         || die "checksum mismatch for $RUNTIME_FILE (expected $APPIMAGE_RUNTIME_SHA256)"
    fi
    return 0
  fi
  local sha256
  sha256="${APPIMAGE_RUNTIME_SHA256:-$(pinned_sha256 runtime "$ARCH" || true)}"
  RUNTIME_FILE="$ROOT/build/tools/runtime-$APPIMAGE_RUNTIME_VERSION-$ARCH"
  fetch_verified     "https://github.com/AppImage/type2-runtime/releases/download/$APPIMAGE_RUNTIME_VERSION/runtime-$ARCH"     "$RUNTIME_FILE" "$sha256"
}

# ------------------------------------------------------------------ libxcb-cursor
# Path of a system library for this architecture, from the dynamic linker cache.
system_library() {
  local soname="$1" tag="" listing="" path="" candidate
  case "$ARCH" in
    x86_64) tag="x86-64" ;;
    aarch64) tag="AArch64" ;;
  esac
  # Lines look like: "libxcb-cursor.so.0 (libc6,x86-64) => /lib/x86_64-linux-gnu/libxcb-cursor.so.0"
  listing="$(ldconfig -p 2>/dev/null || /sbin/ldconfig -p 2>/dev/null || true)"
  path="$(awk -v lib="$soname" -v tag="$tag" \
    '$1 == lib && (tag == "" || index($0, tag)) { print $NF; exit }' <<<"$listing")"
  if [[ -z "$path" ]]; then
    for candidate in /usr/lib/*-linux-gnu/"$soname" /usr/lib64/"$soname" /usr/lib/"$soname"; do
      if [[ -f "$candidate" ]]; then path="$candidate"; break; fi
    done
  fi
  [[ -n "$path" && -f "$path" ]] && echo "$path"
}

# Make sure a copy of the onedir bundle contains libxcb-cursor.so.0.
ensure_xcb_cursor() {
  local bundle="$1" lib
  if [[ -n "$(find "$bundle" -name 'libxcb-cursor.so.0*' -print -quit)" ]]; then
    return 0
  fi
  lib="$(system_library libxcb-cursor.so.0 || true)"
  [[ -n "$lib" ]] || die "libxcb-cursor.so.0 is neither bundled nor installed (sudo apt install libxcb-cursor0)"
  echo "    adding $lib"
  # _internal/ is on LD_LIBRARY_PATH at run time (set by the PyInstaller bootloader).
  install -m 644 "$lib" "$bundle/_internal/libxcb-cursor.so.0"
}

find_appimagetool
find_runtime

WORK="$(mktemp -d "${TMPDIR:-/tmp}/habit-guard-appimage.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

# ------------------------------------------------------------------------ tarball
echo "==> Creating $TARBALL"
mkdir -p "$WORK/tar"
cp -a "$BUNDLE" "$WORK/tar/habit-guard"
ensure_xcb_cursor "$WORK/tar/habit-guard"
install -m 644 "$DESKTOP" "$WORK/tar/habit-guard/habit-guard.desktop"
install -m 644 "$ICON" "$WORK/tar/habit-guard/habit-guard.png"
install -m 644 "$ROOT/LICENSE" "$WORK/tar/habit-guard/LICENSE"
rm -f "$TARBALL"
tar -C "$WORK/tar" --sort=name --owner=0 --group=0 --numeric-owner -czf "$TARBALL" habit-guard

# ------------------------------------------------------------------------ AppImage
echo "==> Assembling AppDir"
APPDIR="$WORK/HabitGuard.AppDir"
mkdir -p \
  "$APPDIR/usr/bin" \
  "$APPDIR/usr/lib" \
  "$APPDIR/usr/share/applications" \
  "$APPDIR/usr/share/icons/hicolor/512x512/apps"
cp -a "$BUNDLE" "$APPDIR/usr/lib/habit-guard"
ensure_xcb_cursor "$APPDIR/usr/lib/habit-guard"
ln -s ../lib/habit-guard/habit-guard "$APPDIR/usr/bin/habit-guard"
install -m 755 "$HERE/AppRun" "$APPDIR/AppRun"
install -m 644 "$DESKTOP" "$APPDIR/habit-guard.desktop"
install -m 644 "$DESKTOP" "$APPDIR/usr/share/applications/habit-guard.desktop"
install -m 644 "$ICON" "$APPDIR/habit-guard.png"
install -m 644 "$ICON" "$APPDIR/usr/share/icons/hicolor/512x512/apps/habit-guard.png"
install -m 644 "$ROOT/LICENSE" "$APPDIR/usr/lib/habit-guard/LICENSE"
ln -s habit-guard.png "$APPDIR/.DirIcon"

echo "==> Running appimagetool ($APPIMAGETOOL)"
# The pinned runtime becomes the AppImage's entry point.
TOOL_ARGS=(--no-appstream --runtime-file "$RUNTIME_FILE")
if [[ -n "${UPDATE_INFORMATION:-}" ]]; then
  TOOL_ARGS+=(--updateinformation "$UPDATE_INFORMATION")
fi
rm -f "$APPIMAGE" "$APPIMAGE.zsync"
# appimagetool writes the .zsync file into the working directory.
(cd "$DIST" && ARCH="$ARCH" VERSION="$VERSION" "$APPIMAGETOOL" "${TOOL_ARGS[@]}" "$APPDIR" "$APPIMAGE")
chmod 755 "$APPIMAGE"

echo "==> Done"
ls -lh "$TARBALL" "$APPIMAGE"
if [[ -f "$APPIMAGE.zsync" ]]; then ls -lh "$APPIMAGE.zsync"; fi
