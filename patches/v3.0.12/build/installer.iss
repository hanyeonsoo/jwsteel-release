; ============================================================
; JWSteel 통합전산 - Inno Setup 설치 마법사
; ============================================================
; 사용법:
;   1. Inno Setup 설치 (https://jrsoftware.org/isdl.php)
;   2. PyInstaller 빌드 먼저 실행 (python build_exe.py)
;   3. 이 .iss 파일을 더블클릭 → Compile (Ctrl+F9)
;   4. Output\JWSteel_Setup_v3.0.exe 생성됨
; ============================================================

#define MyAppName "JWSteel 통합전산"
#define MyAppNameEN "JWSteel"
#define MyAppVersion "3.0.12"
#define MyAppPublisher "정원철강 · JWSteel"
#define MyAppURL "https://nziqdobyuuhvkknyjusq.supabase.co/storage/v1/object/public/JWSteel/"
#define MyAppExeName "JWSteel.exe"

[Setup]
; 앱 정보
AppId={{8C9F3D4A-7B5E-4F2C-A6D8-1234567890AB}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} v{#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; 설치 기본 경로
DefaultDirName={autopf}\JWSteel
DefaultGroupName=JWSteel 통합전산
DisableProgramGroupPage=no
DisableDirPage=no

; 라이선스/안내 페이지
;LicenseFile=LICENSE.txt
InfoBeforeFile=
InfoAfterFile=

; 출력 파일
OutputDir=output
OutputBaseFilename=JWSteel_Setup_v{#MyAppVersion}
SetupIconFile=
Compression=lzma2/ultra
SolidCompression=yes
WizardStyle=modern

; 권한 - 일반 사용자 폴더에 설치 가능
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; 아키텍처
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; 언어/UI
ShowLanguageDialog=no
WizardImageStretch=no

; 제거 정보
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName} v{#MyAppVersion}

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon"; Description: "바탕화면에 아이콘 만들기"; GroupDescription: "추가 작업:"
Name: "quicklaunchicon"; Description: "빠른 실행 아이콘 만들기"; GroupDescription: "추가 작업:"; Flags: unchecked

[Files]
; PyInstaller 빌드 결과 전체 복사
Source: "dist\JWSteel\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; 시작 메뉴
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\빠른 시작 가이드"; Filename: "{app}\_internal\manual\JWSteel_QuickStart.pdf"
Name: "{group}\상세 매뉴얼"; Filename: "{app}\_internal\manual\JWSteel_Manual.pdf"
Name: "{group}\{#MyAppName} 제거"; Filename: "{uninstallexe}"

; 바탕화면 (선택)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

; 빠른 실행 (선택)
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

[Run]
; 설치 완료 후 실행 옵션
Filename: "{app}\{#MyAppExeName}"; Description: "{#MyAppName} 지금 실행"; Flags: nowait postinstall skipifsilent

; PDF 매뉴얼 열기 옵션
Filename: "{app}\_internal\manual\JWSteel_QuickStart.pdf"; Description: "빠른 시작 가이드 열기"; Flags: nowait postinstall skipifsilent shellexec unchecked

[UninstallDelete]
; 제거 시 추가 정리 (로그, 캐시 등)
Type: filesandordirs; Name: "{app}\_internal\__pycache__"
Type: filesandordirs; Name: "{app}\backups"

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // 설치 후 config.json이 없으면 template 복사
    if not FileExists(ExpandConstant('{app}\_internal\config.json')) then
    begin
      FileCopy(
        ExpandConstant('{app}\_internal\config.json.template'),
        ExpandConstant('{app}\_internal\config.json'),
        False
      );
    end;
  end;
end;
