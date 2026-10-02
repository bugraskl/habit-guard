#!/usr/bin/env bash
# Sign "Habit Guard.app" and wrap it in a drag-to-install disk image.
#
# Usage (from the repository root, after PyInstaller):
#   bash packaging/macos/make_dmg.sh [--app "dist/Habit Guard.app"] [--out FILE.dmg]
#        [--version X.Y.Z] [--identity NAME] [--keychain PATH]
#
# Defaults: --app dist/Habit Guard.app, --version from the app's Info.plist,
# --out dist/HabitGuard-<version>-macos-<arch>.dmg, --identity "-" (ad hoc) or
# $MACOS_SIGN_IDENTITY, --keychain $MACOS_SIGN_KEYCHAIN (default: the search list).
#
# Why the identity matters: macOS stores the Camera permission against the app's designated
# requirement. An ad-hoc signature ("-") pins that to the exact build (its cdhash), so after
# every update macOS asks for the camera again (one click in the prompt). Signing every release
# with the same certificate keeps the permission: a Developer ID certificate, or a persistent
# self-signed one, e.g. created in Keychain Access > Certificate Assistant > Create a
# Certificate... (Identity Type "Self Signed Root", Certificate Type "Code Signing"), exported as
# .p12 and stored in the repository secrets MACOS_SIGNING_CERT_P12 (base64) and
# MACOS_SIGNING_CERT_PASSWORD; the release workflow imports it when present. Neither kind is
# notarized, so the first launch still needs "Open Anyway" in System Settings > Privacy &
# Security.
set -euo pipefail

die() { echo "make_dmg: $*" >&2; exit 1; }

[[ "$(uname -s)" == "Darwin" ]] || die "this script needs macOS (hdiutil, codesign)"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP="$ROOT/dist/Habit Guard.app"
OUT=""
VERSION=""
VOLUME_NAME="Habit Guard"
IDENTITY="${MACOS_SIGN_IDENTITY:--}"
KEYCHAIN="${MACOS_SIGN_KEYCHAIN:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --app) APP="${2:?--app needs a path}"; shift 2 ;;
    --out) OUT="${2:?--out needs a path}"; shift 2 ;;
    --version) VERSION="${2:?--version needs a value}"; shift 2 ;;
    --identity) IDENTITY="${2:?--identity needs a name (or - for ad hoc)}"; shift 2 ;;
    --keychain) KEYCHAIN="${2:?--keychain needs a path}"; shift 2 ;;
    -h|--help) sed -n '2,23p' "$0"; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

[[ -d "$APP" ]] || die "app bundle not found: $APP (run PyInstaller first)"
PLIST="$APP/Contents/Info.plist"
[[ -f "$PLIST" ]] || die "missing $PLIST"

if [[ -z "$VERSION" ]]; then
  VERSION="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$PLIST")"
fi
ARCH="$(uname -m)"
OUT="${OUT:-$ROOT/dist/HabitGuard-$VERSION-macos-$ARCH.dmg}"
mkdir -p "$(dirname "$OUT")"

# A symbolic link whose target is missing (a library that the spec left out, still
# linked from the top-level folders) makes xattr and codesign fail with messages that
# do not say why. With -L, find reports exactly those links as type l.
echo "==> Checking the symbolic links in $APP"
if ! BROKEN="$(find -L "$APP" -type l)"; then
  die "cannot check the symbolic links in $APP (see find's message above)"
fi
if [[ -n "$BROKEN" ]]; then
  echo "make_dmg: these symbolic links in $APP point at files that do not exist:" >&2
  while IFS= read -r link; do
    echo "  ${link#"$APP"/} -> $(readlink "$link")" >&2
  done <<<"$BROKEN"
  die "the app bundle is incomplete; rebuild it with packaging/pyinstaller/habit-guard.spec"
fi

SIGN_ARGS=(--force --deep --sign "$IDENTITY" --timestamp=none)
if [[ -n "$KEYCHAIN" ]]; then
  SIGN_ARGS+=(--keychain "$KEYCHAIN")
fi
if [[ "$IDENTITY" == "-" ]]; then
  echo "==> Signing $APP (ad hoc)"
  echo "make_dmg: warning: ad-hoc signature: users must re-grant Accessibility after" \
    "every update (pass --identity to sign with a stable certificate)" >&2
else
  echo "==> Signing $APP with \"$IDENTITY\""
fi
# Extended attributes (quarantine, Finder info) make codesign fail with
# "resource fork, Finder information, or similar detritus not allowed".
xattr -cr "$APP"
codesign "${SIGN_ARGS[@]}" "$APP"
codesign --verify --deep --strict --verbose=2 "$APP"
# The designated requirement is what TCC (the Camera permission) remembers.
REQUIREMENT="$(codesign --display --requirements - "$APP" 2>&1 | sed -n 's/^designated => //p')"
echo "    designated requirement: ${REQUIREMENT:-unknown}"
if [[ "$IDENTITY" != "-" && "$REQUIREMENT" == *cdhash* ]]; then
  die "signed with \"$IDENTITY\" but the designated requirement is still build-specific"
fi

STAGING="$(mktemp -d "${TMPDIR:-/tmp}/habit-guard-dmg.XXXXXX")"
trap 'rm -rf "$STAGING"' EXIT

echo "==> Staging disk image contents"
# ditto keeps symlinks, permissions and the code signature intact.
ditto "$APP" "$STAGING/$(basename "$APP")"
ln -s /Applications "$STAGING/Applications"

echo "==> Creating $OUT"
rm -f "$OUT"
# hdiutil occasionally fails with "Resource busy" on CI runners; retry a few times.
for attempt in 1 2 3 4 5; do
  if hdiutil create \
      -volname "$VOLUME_NAME" \
      -srcfolder "$STAGING" \
      -fs HFS+ \
      -format UDZO \
      -imagekey zlib-level=9 \
      -ov \
      "$OUT"; then
    break
  fi
  [[ $attempt -lt 5 ]] || die "hdiutil create failed after $attempt attempts"
  echo "hdiutil create failed (attempt $attempt); retrying in $((attempt * 5)) s" >&2
  sleep $((attempt * 5))
done

hdiutil verify "$OUT"
echo "==> Done: $OUT ($(du -h "$OUT" | cut -f1))"
