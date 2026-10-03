# Package managers and code signing

## Installing with a package manager

Two of them work today, straight from this repository. Both are checked by CI after every release
by installing the real release, running `habit-guard selftest` and removing it again.

**Scoop (Windows).** The repository is a Scoop bucket. It installs the portable build, puts a
`habit-guard` command on your PATH and adds a Start menu entry:

```powershell
scoop bucket add habit-guard https://github.com/bugraskl/habit-guard
scoop install habit-guard/habit-guard
```

Update with `scoop update habit-guard`. Settings and statistics live in your profile, not in the
Scoop folder, so they survive updates and uninstalling.

**Homebrew (macOS, Apple silicon, macOS 14 or newer).** The repository is a Homebrew tap:

```bash
brew tap bugraskl/habit-guard https://github.com/bugraskl/habit-guard
brew install --cask bugraskl/habit-guard/habit-guard
```

Update with `brew upgrade --cask habit-guard`, remove with `brew uninstall --cask habit-guard`
(`--zap` also deletes the settings). The app is not signed with an Apple Developer ID, so the first
launch needs *right-click, Open*, as with the disk image.

**Arch Linux.** A `habit-guard-bin` PKGBUILD that installs the release tarball is in
`packaging/aur/habit-guard-bin/`. Until it is on the AUR you can build it from here:

```bash
git clone https://github.com/bugraskl/habit-guard
cd habit-guard/packaging/aur/habit-guard-bin
makepkg -si
```

**winget.** Manifests are made for every release (see below) but are not in the community
repository yet.

## How the manifests are made

`scripts/make_package_manifests.py` writes them from the release's `SHA256SUMS.txt`, so they describe
exactly what was published, from the templates in `packaging/templates/`. The release workflow starts
`.github/workflows/packages.yml`, which

1. commits `bucket/habit-guard.json` (Scoop), `Casks/habit-guard.rb` (Homebrew) and
   `packaging/aur/habit-guard-bin/` (PKGBUILD and `.SRCINFO`) to `main`;
2. keeps the winget manifests as the workflow artifact `winget-manifests-X.Y.Z`;
3. installs the release with Scoop on Windows, with Homebrew on macOS (style, audit, install, run,
   remove), builds and installs the AUR package in an Arch Linux container
   (`packaging/aur/validate.sh`, which also checks that `.SRCINFO` is what `makepkg --printsrcinfo`
   writes), and validates the winget files against the official JSON schemas.

Run it again for any release with *Actions → Packages → Run workflow* (give the tag, for example
`v0.1.0`). Pre-releases are not offered.

## Publishing on winget (by hand)

1. Download the artifact `winget-manifests-X.Y.Z` from the workflow run. It holds the four files in
   the layout of the community repository: `b/BugraSikel/HabitGuard/X.Y.Z/`.
2. Fork [microsoft/winget-pkgs](https://github.com/microsoft/winget-pkgs) and copy that folder to
   `manifests/b/BugraSikel/HabitGuard/X.Y.Z/`.
3. Check it on Windows: `winget validate --manifest <folder>`, then
   `winget settings --enable LocalManifestFiles` and `winget install --manifest <folder>`.
4. Open the pull request. The repository's bot scans the installer; unsigned PyInstaller programs
   are sometimes flagged by antivirus scanners, which is one more reason to sign (below).

For the following versions `wingetcreate update BugraSikel.HabitGuard --version X.Y.Z --urls
<URL of the setup file> --submit` does steps 1 to 4 in one go.

## Publishing on the AUR (by hand)

You need an [AUR account](https://aur.archlinux.org/) with your SSH key added:

```bash
git clone ssh://aur@aur.archlinux.org/habit-guard-bin.git
cp packaging/aur/habit-guard-bin/PKGBUILD packaging/aur/habit-guard-bin/.SRCINFO habit-guard-bin/
cd habit-guard-bin && git add PKGBUILD .SRCINFO && git commit -m "habit-guard-bin X.Y.Z" && git push
```

## Code signing

### Windows: SignPath

[SignPath Foundation](https://signpath.org/) signs open-source projects for free. The release build
already contains the steps; they stay off, and nothing changes, until you set them up:

1. **Apply** at signpath.org (the project is MIT licensed, released and described on its download
   page, which are the conditions). They ask for a *code signing policy* on the project's page
   (below) and for the team roles: here one person is committer, reviewer and approver.
2. **In SignPath**, create the project `habit-guard`, a signing policy `release-signing` (releases
   need your manual approval), connect the *GitHub.com* trusted build system and install the
   SignPath GitHub app on the repository. Add two artifact configurations:

   `programs`, the two program files:

   ```xml
   <artifact-configuration xmlns="http://signpath.io/artifact-configuration/v1">
     <zip-file>
       <pe-file path="HabitGuard.exe">
         <authenticode-sign/>
       </pe-file>
       <pe-file path="habit-guard-cli.exe">
         <authenticode-sign/>
       </pe-file>
     </zip-file>
   </artifact-configuration>
   ```

   `installer`, the setup program:

   ```xml
   <artifact-configuration xmlns="http://signpath.io/artifact-configuration/v1">
     <zip-file>
       <pe-file path="HabitGuard-*-windows-x64-setup.exe">
         <authenticode-sign/>
       </pe-file>
     </zip-file>
   </artifact-configuration>
   ```

3. **In the GitHub repository settings** (*Secrets and variables → Actions*): the variable
   `SIGNPATH_ORGANIZATION_ID` (this one switches signing on) and the secret `SIGNPATH_API_TOKEN`.
   If you named things differently, the variables `SIGNPATH_PROJECT_SLUG`,
   `SIGNPATH_SIGNING_POLICY_SLUG`, `SIGNPATH_PROGRAMS_CONFIGURATION_SLUG` and
   `SIGNPATH_INSTALLER_CONFIGURATION_SLUG` override the defaults above.
4. **Tag a release.** For a release build the workflow signs the two programs before they go into
   the portable ZIP and the installer, builds the installer, signs it too, and refuses to go on
   unless every signature is *Valid*. The installer smoke test then runs on the signed installer.
5. **Add the policy to the README and the website** once SignPath has accepted the project; the
   attribution may only be shown then:

   > **Code signing policy.** Free code signing provided by [SignPath.io](https://signpath.io),
   > certificate by [SignPath Foundation](https://signpath.org). Committer, reviewer and approver:
   > Buğra Şıkel. This program will not transfer any information to other networked systems unless
   > specifically requested by the user or the person installing or operating it. (It contains no
   > networking code at all; see [privacy](privacy.md).)

Signed programs mean no SmartScreen warning once the certificate has built up reputation, fewer
antivirus false positives, and a better chance with winget.

### macOS

Signing with an Apple Developer ID and notarizing needs a paid Apple Developer Program membership,
and is not set up. What exists is the optional stable certificate described in
`packaging/macos/make_dmg.sh`, which keeps the camera permission across updates.

### Linux

AppImage, tarball and AUR package are not signed; every release carries `SHA256SUMS.txt` and GitHub
build-provenance attestations (`gh attestation verify <file> --repo bugraskl/habit-guard`).
