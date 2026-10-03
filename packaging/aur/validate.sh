#!/usr/bin/env bash
# Build and test packaging/aur/habit-guard-bin the way an Arch user would.
#
# Runs inside an Arch Linux container (the packages workflow starts one), as root:
#
#   docker run --rm -v "$PWD:/work" archlinux:base-devel bash /work/packaging/aur/validate.sh
#
# It checks that .SRCINFO is what `makepkg --printsrcinfo` writes for the PKGBUILD, downloads
# the release the PKGBUILD names (the checksum is verified), builds and installs the package, and
# runs the installed program's self-test. namcap's findings are printed, not enforced.
set -euo pipefail

WORK="${WORK:-/work}"
SRC="$WORK/packaging/aur/habit-guard-bin"
[[ -f "$SRC/PKGBUILD" ]] || { echo "validate: no PKGBUILD in $SRC" >&2; exit 1; }

pacman -Syu --noconfirm --needed sudo namcap >/dev/null
# makepkg refuses to run as root.
id builder >/dev/null 2>&1 || useradd --create-home builder
echo 'builder ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/builder
BUILD="/home/builder/habit-guard-bin"
rm -rf "$BUILD"
cp -r "$SRC" "$BUILD"
chown -R builder:builder "$BUILD"

as_builder() { sudo -u builder -H bash -c "cd '$BUILD' && $*"; }

echo "==> .SRCINFO matches the PKGBUILD"
as_builder "makepkg --printsrcinfo > /tmp/srcinfo"
diff -u "$SRC/.SRCINFO" /tmp/srcinfo

echo "==> Build the package (the download is checked against the sha256sums)"
as_builder "makepkg --syncdeps --noconfirm --force"
package="$(find "$BUILD" -maxdepth 1 -name 'habit-guard-bin-*.pkg.tar.zst' -print -quit)"
[[ -n "$package" ]] || { echo "validate: makepkg built no package" >&2; exit 1; }
echo "built $package"

echo "==> namcap (information only)"
namcap "$BUILD/PKGBUILD" || true
namcap "$package" || true

echo "==> Install and run"
pacman -U --noconfirm "$package"
command -v habit-guard
habit-guard --version
QT_QPA_PLATFORM=offscreen habit-guard selftest
test -f /usr/share/applications/habit-guard.desktop
test -f /usr/share/icons/hicolor/512x512/apps/habit-guard.png
test -f /usr/share/licenses/habit-guard-bin/LICENSE
pacman -Qi habit-guard-bin

echo "==> Remove"
pacman -R --noconfirm habit-guard-bin
test ! -e /opt/habit-guard
echo "validate: the AUR package builds, installs and removes cleanly"
