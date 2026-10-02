; Inno Setup 6 script for Habit Guard.
;
; Per-user install into %LOCALAPPDATA%\Programs\Habit Guard: no administrator rights, no UAC
; prompt, nothing written outside the user's profile.
;
; Tasks: start at sign-in (off by default), a desktop icon (off), and "addtopath" (on), which
; installs the command-line program a second time as habit-guard.exe and adds the folder to the
; user's PATH, so the documented "habit-guard <command>" works in a new terminal; uninstalling
; (or unticking the task in an upgrade) removes the PATH entry again.
;
; Build from the repository root after PyInstaller has produced dist\HabitGuard:
;
;   iscc /DAppVersion=0.1.0 packaging\windows\installer.iss
;
; Optional defines:
;   /DAppVersionNumeric=0.1.0   purely numeric version for the file properties
;   /DBundleDir=<dir>           PyInstaller output folder (default: dist\HabitGuard)
;   /DOutputDir=<dir>           where the setup program is written (default: dist)
;
; Keep this file UTF-8 *with* a byte order mark: without it Inno Setup reads the publisher name
; and the Turkish messages in the ANSI code page.

#ifndef AppVersion
  #error Pass the version, for example: iscc /DAppVersion=0.1.0 packaging\windows\installer.iss
#endif
#ifndef AppVersionNumeric
  #define AppVersionNumeric AppVersion
#endif
#ifndef BundleDir
  #define BundleDir AddBackslash(SourcePath) + "..\..\dist\HabitGuard"
#endif
#ifndef OutputDir
  #define OutputDir AddBackslash(SourcePath) + "..\..\dist"
#endif

#define AppName "Habit Guard"
; AppId identifies the installation for upgrades and uninstall. Never change it.
#define AppGuid "E04FC592-7BE2-49D0-B7A0-BAA64A24938E"
#define AppExeName "HabitGuard.exe"
#define CliExeName "habit-guard-cli.exe"
; The same console program under the name the documentation uses ("habit-guard doctor"), found
; through PATH. Start-at-sign-in keeps using the windowed AppExeName.
#define CliCommandExeName "habit-guard.exe"
; Same ID the app sets at run time (SetCurrentProcessExplicitAppUserModelID), so notifications
; and the taskbar group with the Start menu shortcut.
#define AppUserModelID "io.github.bugraskl.habitguard"
#define RepoUrl "https://github.com/bugraskl/habit-guard"
; Value name shared with habit_guard.autostart, so the app and the installer manage the same
; "start at sign-in" entry.
#define RunValueName "HabitGuard"
#define RunKey "Software\Microsoft\Windows\CurrentVersion\Run"
; Where Inno Setup records this per-user installation (used to detect upgrades).
#define UninstallKey "Software\Microsoft\Windows\CurrentVersion\Uninstall\{" + AppGuid + "}_is1"

#if !FileExists(AddBackslash(BundleDir) + AppExeName)
  #error PyInstaller output not found; build it first (see packaging/pyinstaller/habit-guard.spec)
#endif

[Setup]
AppId={{{#AppGuid}}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Buğra Şıkel
AppPublisherURL={#RepoUrl}
AppSupportURL={#RepoUrl}/issues
AppUpdatesURL={#RepoUrl}/releases
AppCopyright=Copyright (c) 2026 Buğra Şıkel. MIT License.
AppComments=Catches nail biting, mustache pulling, hair pulling and face touching through your webcam.
VersionInfoVersion={#AppVersionNumeric}
VersionInfoProductVersion={#AppVersionNumeric}
VersionInfoProductTextVersion={#AppVersion}
VersionInfoDescription={#AppName} Setup

; Per-user only: {userpf} is %LOCALAPPDATA%\Programs.
PrivilegesRequired=lowest
DefaultDirName={userpf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableDirPage=auto
DisableReadyPage=yes
UsePreviousAppDir=yes
UsePreviousTasks=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763

LicenseFile=..\..\LICENSE
SetupIconFile=habit-guard.ico
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}
WizardStyle=modern
ShowLanguageDialog=auto

OutputDir={#OutputDir}
OutputBaseFilename=HabitGuard-{#AppVersion}-windows-x64-setup
Compression=lzma2/max
SolidCompression=yes
; A running app is asked to quit through "habit-guard-cli ctl quit" (see PrepareToInstall);
; anything still holding our files afterwards is released through the Restart Manager.
CloseApplications=yes
RestartApplications=no
; The "addtopath" task edits the user's PATH: tell Explorer (and new terminals) afterwards.
ChangesEnvironment=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[CustomMessages]
english.StartAtLogin=Start {#AppName} when I sign in to Windows
turkish.StartAtLogin=Windows'a oturum açtığımda {#AppName} uygulamasını başlat
english.AutostartGroup=Startup:
turkish.AutostartGroup=Başlangıç:
english.ShortcutComment=Catches the hand on its way to your mouth, mustache, brows or hair
turkish.ShortcutComment=Elinizin ağzınıza, bıyığınıza, kaşınıza ya da saçınıza gidişini yakalar
english.RemoveUserData=Also delete your {#AppName} settings, statistics and logs?%n%nChoose No to keep them for a future installation.
turkish.RemoveUserData={#AppName} ayarlarınız, istatistikleriniz ve günlük dosyalarınız da silinsin mi?%n%nİleride yeniden kurmak üzere saklamak için Hayır'ı seçin.
english.CommandLineGroup=Command line:
turkish.CommandLineGroup=Komut satırı:
english.AddToPath=Add the "habit-guard" command to PATH (for diagnostics and keyboard shortcuts)
turkish.AddToPath="habit-guard" komutunu PATH'e ekle (tanılama ve klavye kısayolları için)

[Tasks]
Name: "startup"; Description: "{cm:StartAtLogin}"; GroupDescription: "{cm:AutostartGroup}"; Flags: unchecked
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "addtopath"; Description: "{cm:AddToPath}"; GroupDescription: "{cm:CommandLineGroup}"

[InstallDelete]
; One-folder builds change file names between releases; start from a clean runtime folder so no
; stale libraries are left behind after an upgrade.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "{#BundleDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Always installed, so "habit-guard.exe" has one documented place even without the PATH entry.
; It must sit next to _internal, which a one-folder build loads from.
Source: "{#BundleDir}\{#CliExeName}"; DestDir: "{app}"; DestName: "{#CliCommandExeName}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; AppUserModelID: "{#AppUserModelID}"; Comment: "{cm:ShortcutComment}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; AppUserModelID: "{#AppUserModelID}"; Comment: "{cm:ShortcutComment}"; Tasks: desktopicon

[Registry]
; The same entry "habit-guard autostart enable" writes. A new installation and an upgrade with
; the wizard (where the box is on screen) write it as chosen; a silent upgrade never turns
; start-at-sign-in back on by itself, because the user may have turned it off in the meantime.
Root: HKCU; Subkey: "{#RunKey}"; ValueType: string; ValueName: "{#RunValueName}"; ValueData: """{app}\{#AppExeName}"""; Flags: uninsdeletevalue; Tasks: startup; Check: ShouldWriteAutostart

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
; Silent upgrades (winget, /VERYSILENT) skip the checkbox above: start the app again if
; PrepareToInstall had to close it, so tracking does not stay off until the next sign-in.
Filename: "{app}\{#AppExeName}"; Flags: nowait runasoriginaluser; Check: RelaunchAfterSilentUpgrade

[UninstallDelete]
Type: dirifempty; Name: "{app}"

[Code]
const
  { platformdirs location of the settings (no author folder, app name "habit-guard"). }
  UserDataDir = '{localappdata}\habit-guard';
  { "habit-guard ctl" exit code when no instance is running. }
  CtlNotRunning = 3;
  { Where Windows keeps the user's own environment variables. }
  EnvironmentKey = 'Environment';

var
  { An earlier version is installed for this user. }
  IsUpgrade: Boolean;
  { This setup asked a running Habit Guard to quit (see RelaunchAfterSilentUpgrade). }
  AppWasRunning: Boolean;

function InitializeSetup: Boolean;
begin
  IsUpgrade := RegKeyExists(HKCU, '{#UninstallKey}');
  Result := True;
end;

{ Check for the [Registry] autostart entry: written as chosen, except in a silent upgrade,
  where the earlier choice (which the user may have changed since) is left alone. }
function ShouldWriteAutostart: Boolean;
begin
  Result := (not IsUpgrade) or (not WizardSilent);
end;

{ Ask a running Habit Guard to quit through its control folder; "ctl quit" waits (up to about
  10 s) until the app has stopped. Does nothing if it is not running. }
procedure QuitRunningApp;
var
  Cli: String;
  ResultCode: Integer;
begin
  Cli := ExpandConstant('{app}\{#CliExeName}');
  if not FileExists(Cli) then
    Exit;
  if (not Exec(Cli, 'ctl quit', '', SW_HIDE, ewWaitUntilTerminated, ResultCode)) or
     (ResultCode <> 0) then
    Exit;
  AppWasRunning := True;
  { Give it a moment to release the camera and its files. }
  Sleep(1000);
end;

{ Before files are replaced during an upgrade. }
function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  QuitRunningApp;
end;

{ Check for the [Run] entry that starts the app again after a silent upgrade: an interactive
  setup offers the "Launch" checkbox instead, and an app that was not running stays closed. }
function RelaunchAfterSilentUpgrade: Boolean;
begin
  Result := WizardSilent and AppWasRunning;
end;

{ Whether two PATH entries name the same folder (any case, quotes and trailing backslash
  ignored). Entries using %VARIABLES% are compared as written. }
function SameFolder(const Entry, Folder: String): Boolean;
begin
  Result := CompareText(RemoveBackslashUnlessRoot(RemoveQuotes(Trim(Entry))),
                        RemoveBackslashUnlessRoot(Folder)) = 0;
end;

{ PathList without its entries for Folder (Found says whether there were any). Every other
  entry, empty ones included, is kept as written. }
function PathWithout(const PathList, Folder: String; var Found: Boolean): String;
var
  Rest, Entry: String;
  Separator: Integer;
  First: Boolean;
begin
  Result := '';
  Found := False;
  First := True;
  Rest := PathList + ';';
  while Rest <> '' do
  begin
    Separator := Pos(';', Rest);
    Entry := Copy(Rest, 1, Separator - 1);
    Delete(Rest, 1, Separator);
    if (Trim(Entry) <> '') and SameFolder(Entry, Folder) then
      Found := True
    else
    begin
      if not First then
        Result := Result + ';';
      Result := Result + Entry;
      First := False;
    end;
  end;
end;

{ Append the installation folder to the user's PATH unless it is already there. The value is
  read and written unexpanded, so %VARIABLES% in it survive. A Path value that exists but is not
  a string (REG_MULTI_SZ or REG_BINARY, written by some other tool) cannot be read: it is left
  alone rather than replaced by a value holding only this folder, which would lose every other
  entry. }
procedure AddAppToPath;
var
  PathList, Folder: String;
  Found: Boolean;
begin
  Folder := ExpandConstant('{app}');
  if not RegQueryStringValue(HKCU, EnvironmentKey, 'Path', PathList) then
  begin
    if RegValueExists(HKCU, EnvironmentKey, 'Path') then
    begin
      Log('The user PATH is not a string value; not adding ' + Folder + ' to it');
      Exit;
    end;
    PathList := '';
  end;
  PathWithout(PathList, Folder, Found);
  if Found then
    Exit;
  if (PathList <> '') and (PathList[Length(PathList)] <> ';') then
    PathList := PathList + ';';
  if not RegWriteExpandStringValue(HKCU, EnvironmentKey, 'Path', PathList + Folder) then
    Log('Could not add ' + Folder + ' to the user PATH');
end;

{ Remove the installation folder from the user's PATH, leaving the rest as it is (a Path value
  that is not a string is never touched: the read fails). }
procedure RemoveAppFromPath;
var
  PathList, Kept, Folder: String;
  Found: Boolean;
begin
  Folder := ExpandConstant('{app}');
  if not RegQueryStringValue(HKCU, EnvironmentKey, 'Path', PathList) then
    Exit;
  Kept := PathWithout(PathList, Folder, Found);
  if not Found then
    Exit;
  if Kept = '' then
    RegDeleteValue(HKCU, EnvironmentKey, 'Path')
  else if not RegWriteExpandStringValue(HKCU, EnvironmentKey, 'Path', Kept) then
    Log('Could not remove ' + Folder + ' from the user PATH');
end;

{ Remove the "start at sign-in" entry if it belongs to this installation. A Run value pointing
  somewhere else (a portable copy) is left alone. }
procedure RemoveAutostartIfOurs;
var
  Command: String;
begin
  if RegQueryStringValue(HKCU, '{#RunKey}', '{#RunValueName}', Command) then
  begin
    if Pos(Lowercase(ExpandConstant('{app}')), Lowercase(Command)) = 0 then
      Exit;
    RegDeleteValue(HKCU, '{#RunKey}', '{#RunValueName}');
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    { Upgrades restore the earlier choice (UsePreviousTasks); unticking the task removes the
      entry an earlier installation added. }
    if WizardIsTaskSelected('addtopath') then
      AddAppToPath
    else
      RemoveAppFromPath;
    { The start-at-sign-in box was unticked in an upgrade wizard. }
    if IsUpgrade and (not WizardSilent) and (not WizardIsTaskSelected('startup')) then
      RemoveAutostartIfOurs;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
  begin
    QuitRunningApp;
    RemoveAutostartIfOurs;
    RemoveAppFromPath;
  end;

  if (CurUninstallStep = usPostUninstall) and (not UninstallSilent) and
     DirExists(ExpandConstant(UserDataDir)) then
  begin
    if MsgBox(CustomMessage('RemoveUserData'), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      DelTree(ExpandConstant(UserDataDir), True, True, True);
  end;
end;
