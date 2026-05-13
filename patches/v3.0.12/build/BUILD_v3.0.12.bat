@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

echo ============================================================
echo  JWSteel v3.0.12 - 원클릭 빌드
echo  (v3.0.11 설치 폴더에 패치 5개를 입혀 새 인스톨러 생성)
echo ============================================================
echo.

REM ---------- 사용자 환경 ----------
set "SRC_INSTALL=C:\jwsteel-v311-temp"
set "BUILD=C:\jwsteel-v3.0.12-build"
set "DIST=%BUILD%\dist\JWSteel"
set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
set "HERE=%~dp0"
if "%HERE:~-1%"=="\" set "HERE=%HERE:~0,-1%"

REM ---------- 사전 점검 ----------
if not exist "%SRC_INSTALL%\JWSteel.exe" (
    echo [ERROR] v3.0.11 설치 폴더를 찾을 수 없습니다: %SRC_INSTALL%
    echo         먼저 JWSteel_Setup_v3.0.11.exe 를 %SRC_INSTALL% 에 설치하세요.
    pause
    exit /b 1
)
if not exist "%ISCC%" (
    echo [ERROR] Inno Setup 6 컴파일러를 찾을 수 없습니다.
    echo         경로: %ISCC%
    pause
    exit /b 1
)
if not exist "%HERE%\installer.iss" (
    echo [ERROR] installer.iss 가 이 배치파일 옆에 없습니다.
    pause
    exit /b 1
)

REM ---------- 1) 빌드 폴더 초기화 ----------
echo [1/5] 빌드 폴더 초기화: %BUILD%
if exist "%BUILD%" rmdir /S /Q "%BUILD%" 2>nul
mkdir "%DIST%" 2>nul
mkdir "%BUILD%\output" 2>nul

REM ---------- 2) v3.0.11 설치 폴더 복사 ----------
echo [2/5] v3.0.11 설치 폴더 -^> dist\JWSteel\ 복사 중...
xcopy "%SRC_INSTALL%\*" "%DIST%\" /E /I /Q /Y >nul

REM 사용자 데이터/설정/구 인스톨러는 제외
del "%DIST%\unins000.dat" 2>nul
del "%DIST%\unins000.exe" 2>nul
del "%DIST%\_internal\accounting.db" 2>nul
del "%DIST%\_internal\config.json" 2>nul

REM __pycache__ 제거
for /d /r "%DIST%" %%d in (__pycache__) do @if exist "%%d" rmdir /S /Q "%%d" 2>nul

REM ---------- 3) v3.0.12 패치 5개 덮어쓰기 ----------
echo [3/5] v3.0.12 패치 5개 적용...
copy /Y "%HERE%\..\ui\widgets\_filter_bar.py"      "%DIST%\_internal\ui\widgets\_filter_bar.py" >nul
copy /Y "%HERE%\..\ui\widgets\inventory.py"        "%DIST%\_internal\ui\widgets\inventory.py" >nul
copy /Y "%HERE%\..\ui\widgets\inventory_picker.py" "%DIST%\_internal\ui\widgets\inventory_picker.py" >nul
copy /Y "%HERE%\..\updater.py"                     "%DIST%\_internal\updater.py" >nul
copy /Y "%HERE%\..\VERSION.txt"                    "%DIST%\_internal\VERSION.txt" >nul

REM ---------- 4) installer.iss 배치 ----------
echo [4/5] installer.iss 배치 (이미 v3.0.12 로 갱신됨)...
copy /Y "%HERE%\installer.iss" "%BUILD%\installer.iss" >nul

REM ---------- 5) Inno Setup 컴파일 ----------
echo [5/5] Inno Setup 빌드 중 (1~2분 소요)...
echo.
pushd "%BUILD%"
"%ISCC%" installer.iss
set RC=%ERRORLEVEL%
popd
echo.

REM ---------- 결과 ----------
if exist "%BUILD%\output\JWSteel_Setup_v3.0.12.exe" (
    echo ============================================================
    echo  빌드 성공!
    echo.
    echo  파일: %BUILD%\output\JWSteel_Setup_v3.0.12.exe
    echo ============================================================
    explorer "%BUILD%\output"
) else (
    echo ============================================================
    echo  빌드 실패 ^(exit code %RC%^) - 위 로그 확인
    echo ============================================================
)
pause
