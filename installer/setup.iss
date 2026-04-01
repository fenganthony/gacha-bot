; Gacha Bot - Inno Setup Installer Script
; Requires: build.bat to be run first to populate installer\build\

#define MyAppName "Gacha Bot"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "fenganthony"
#define MyAppURL "https://github.com/fenganthony/gacha-bot"
#define MyAppExeName "launcher.bat"

[Setup]
AppId={{8F3B2A5E-4C7D-4E9F-B6A1-D3E5F7A9C2B4}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={autopf}\GachaBot
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=dist
OutputBaseFilename=GachaBot-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; SetupIconFile= (add .ico path here if desired)

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "chinesetraditional"; MessagesFile: "compiler:Languages\ChineseTraditional.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; Embedded Python
Source: "build\python\*"; DestDir: "{app}\python"; Flags: ignoreversion recursesubdirs createallsubdirs
; Application files
Source: "build\app\*"; DestDir: "{app}\app"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\app\launcher.bat"; WorkingDir: "{app}\app"; Comment: "Start Gacha Bot"
Name: "{group}\Stop {#MyAppName}"; Filename: "{app}\app\stop.bat"; WorkingDir: "{app}\app"; Comment: "Stop Gacha Bot"
Name: "{group}\Open Dashboard"; Filename: "http://localhost:{code:GetDashboardPort}"; Comment: "Open Web Dashboard"
Name: "{group}\Open Data Folder"; Filename: "{code:GetDataDir}"; Comment: "Open data folder"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\app\launcher.bat"; WorkingDir: "{app}\app"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"
Name: "autostart"; Description: "Start Gacha Bot automatically on Windows startup"; GroupDescription: "Startup:"

[Registry]
; Auto-start on login (only if task selected)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "GachaBot"; ValueData: """{app}\app\launcher.bat"""; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\app\launcher.bat"; Description: "Start Gacha Bot now"; WorkingDir: "{app}\app"; Flags: nowait postinstall skipifsilent shellexec

[UninstallRun]
Filename: "{app}\app\stop.bat"; WorkingDir: "{app}\app"; Flags: runhidden

[Code]
var
  EnvPage: TWizardPage;
  BotTokenEdit: TNewEdit;
  DashboardPortEdit: TNewEdit;
  DataDirEdit: TNewEdit;
  DataDirBrowseBtn: TNewButton;

function GetDefaultDataDir: String;
begin
  Result := ExpandConstant('{userappdata}\GachaBot');
end;

function GetDataDir(Param: String): String;
begin
  if (DataDirEdit <> nil) and (Trim(DataDirEdit.Text) <> '') then
    Result := DataDirEdit.Text
  else
    Result := GetDefaultDataDir;
end;

function GetDashboardPort(Param: String): String;
begin
  if DashboardPortEdit <> nil then
    Result := DashboardPortEdit.Text
  else
    Result := '8080';
end;

procedure DataDirBrowseClick(Sender: TObject);
var
  Dir: String;
begin
  Dir := DataDirEdit.Text;
  if BrowseForFolder('Select Data Directory:', Dir, False) then
    DataDirEdit.Text := Dir;
end;

procedure InitializeWizard;
var
  LabelToken, LabelPort, LabelHelp, LabelDataDir: TNewStaticText;
begin
  // Custom page for environment settings
  EnvPage := CreateCustomPage(
    wpSelectDir,
    'Bot Configuration',
    'Enter your Discord Bot Token, Dashboard port, and data directory.'
  );

  // Help text
  LabelHelp := TNewStaticText.Create(EnvPage);
  LabelHelp.Parent := EnvPage.Surface;
  LabelHelp.Caption :=
    'You need a Discord Bot Token to run the bot.' + #13#10 +
    'Get one from: https://discord.com/developers/applications' + #13#10 +
    '' + #13#10 +
    'Data directory stores config, database, and presets (must be writable).';
  LabelHelp.Left := 0;
  LabelHelp.Top := 0;
  LabelHelp.Width := EnvPage.SurfaceWidth;
  LabelHelp.AutoSize := True;
  LabelHelp.WordWrap := True;

  // Bot Token
  LabelToken := TNewStaticText.Create(EnvPage);
  LabelToken.Parent := EnvPage.Surface;
  LabelToken.Caption := 'Discord Bot Token:';
  LabelToken.Left := 0;
  LabelToken.Top := 75;
  LabelToken.Font.Style := [fsBold];

  BotTokenEdit := TNewEdit.Create(EnvPage);
  BotTokenEdit.Parent := EnvPage.Surface;
  BotTokenEdit.Left := 0;
  BotTokenEdit.Top := 95;
  BotTokenEdit.Width := EnvPage.SurfaceWidth;
  BotTokenEdit.PasswordChar := '*';
  BotTokenEdit.Text := '';

  // Dashboard Port
  LabelPort := TNewStaticText.Create(EnvPage);
  LabelPort.Parent := EnvPage.Surface;
  LabelPort.Caption := 'Dashboard Port (default: 8080):';
  LabelPort.Left := 0;
  LabelPort.Top := 135;
  LabelPort.Font.Style := [fsBold];

  DashboardPortEdit := TNewEdit.Create(EnvPage);
  DashboardPortEdit.Parent := EnvPage.Surface;
  DashboardPortEdit.Left := 0;
  DashboardPortEdit.Top := 155;
  DashboardPortEdit.Width := 100;
  DashboardPortEdit.Text := '8080';

  // Data Directory
  LabelDataDir := TNewStaticText.Create(EnvPage);
  LabelDataDir.Parent := EnvPage.Surface;
  LabelDataDir.Caption := 'Data Directory (config, database, presets):';
  LabelDataDir.Left := 0;
  LabelDataDir.Top := 195;
  LabelDataDir.Font.Style := [fsBold];

  DataDirEdit := TNewEdit.Create(EnvPage);
  DataDirEdit.Parent := EnvPage.Surface;
  DataDirEdit.Left := 0;
  DataDirEdit.Top := 215;
  DataDirEdit.Width := EnvPage.SurfaceWidth - 90;
  DataDirEdit.Text := GetDefaultDataDir;

  DataDirBrowseBtn := TNewButton.Create(EnvPage);
  DataDirBrowseBtn.Parent := EnvPage.Surface;
  DataDirBrowseBtn.Caption := 'Browse...';
  DataDirBrowseBtn.Left := EnvPage.SurfaceWidth - 80;
  DataDirBrowseBtn.Top := 213;
  DataDirBrowseBtn.Width := 80;
  DataDirBrowseBtn.Height := 23;
  DataDirBrowseBtn.OnClick := @DataDirBrowseClick;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = EnvPage.ID then
  begin
    if Trim(BotTokenEdit.Text) = '' then
    begin
      MsgBox('Please enter your Discord Bot Token. You can get one from the Discord Developer Portal.', mbError, MB_OK);
      Result := False;
    end;
    if Result and (Trim(DashboardPortEdit.Text) = '') then
    begin
      DashboardPortEdit.Text := '8080';
    end;
    if Result and (Trim(DataDirEdit.Text) = '') then
    begin
      DataDirEdit.Text := GetDefaultDataDir;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  EnvContent: String;
  EnvFile: String;
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    // Create data directory
    ForceDirectories(GetDataDir(''));

    // Write .env file with user's settings
    EnvFile := ExpandConstant('{app}\app\.env');
    EnvContent :=
      'BOT_TOKEN=' + BotTokenEdit.Text + #13#10 +
      'PORT=' + DashboardPortEdit.Text + #13#10 +
      'DATA_DIR=' + GetDataDir('') + #13#10;
    SaveStringToFile(EnvFile, EnvContent, False);

    // Generate config.json in data directory
    Exec(
      ExpandConstant('{app}\python\python.exe'),
      'configure.py',
      ExpandConstant('{app}\app'),
      SW_HIDE, ewWaitUntilTerminated, ResultCode
    );
  end;
end;
