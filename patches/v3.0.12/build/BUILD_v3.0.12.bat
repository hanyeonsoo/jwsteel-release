@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo  JWSteel v3.0.12 - one-click build
echo ============================================================
echo.

REM ---- locations ----
set "SRC_INSTALL=C:\jwsteel-v311-temp"
set "BUILD=C:\jwsteel-v3.0.12-build"
set "DIST=!BUILD!\dist\JWSteel"
set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
set "HERE=%~dp0"
if "!HERE:~-1!"=="\" set "HERE=!HERE:~0,-1!"

REM ---- preflight (use goto, not if-blocks, to avoid paren-in-path parser bug) ----
if not exist "!SRC_INSTALL!\JWSteel.exe" goto err_src
if not exist "!ISCC!" goto err_iscc
if not exist "!HERE!\installer.iss" goto err_iss

REM ---- 1. clean build folder ----
echo [1/5] Cleaning build folder: !BUILD!
if exist "!BUILD!" rmdir /S /Q "!BUILD!" 2>nul
mkdir "!DIST!" 2>nul
mkdir "!BUILD!\output" 2>nul

REM ---- 2. copy v3.0.11 install folder ----
echo [2/5] Copying v3.0.11 install to dist\JWSteel\ ...
xcopy "!SRC_INSTALL!\*" "!DIST!\" /E /I /Q /Y >nul

REM exclude user data, settings, old uninstaller
del "!DIST!\unins000.dat" 2>nul
del "!DIST!\unins000.exe" 2>nul
del "!DIST!\_internal\accounting.db" 2>nul
del "!DIST!\_internal\config.json" 2>nul

REM remove __pycache__
for /d /r "!DIST!" %%d in (__pycache__) do @if exist "%%d" rmdir /S /Q "%%d" 2>nul

REM ---- 3. apply 5 v3.0.12 patches ----
echo [3/5] Applying 5 v3.0.12 patches...
copy /Y "!HERE!\..\ui\widgets\_filter_bar.py"      "!DIST!\_internal\ui\widgets\_filter_bar.py" >nul
copy /Y "!HERE!\..\ui\widgets\inventory.py"        "!DIST!\_internal\ui\widgets\inventory.py" >nul
copy /Y "!HERE!\..\ui\widgets\inventory_picker.py" "!DIST!\_internal\ui\widgets\inventory_picker.py" >nul
copy /Y "!HERE!\..\updater.py"                     "!DIST!\_internal\updater.py" >nul
copy /Y "!HERE!\..\VERSION.txt"                    "!DIST!\_internal\VERSION.txt" >nul

REM ---- 4. stage installer.iss (already bumped to 3.0.12) ----
echo [4/5] Staging installer.iss ...
copy /Y "!HERE!\installer.iss" "!BUILD!\installer.iss" >nul

REM ---- 5. compile with Inno Setup ----
echo [5/5] Compiling installer with Inno Setup (1-2 min)...
echo.
pushd "!BUILD!"
"!ISCC!" installer.iss
set RC=!ERRORLEVEL!
popd
echo.

REM ---- result ----
if exist "!BUILD!\output\JWSteel_Setup_v3.0.12.exe" goto ok
goto fail

:ok
echo ============================================================
echo  BUILD SUCCESS
echo.
echo  Output: !BUILD!\output\JWSteel_Setup_v3.0.12.exe
echo ============================================================
explorer "!BUILD!\output"
pause
exit /b 0

:fail
echo ============================================================
echo  BUILD FAILED (exit code !RC!) - check log above
echo ============================================================
pause
exit /b !RC!

:err_src
echo [ERROR] v3.0.11 install folder not found:
echo         !SRC_INSTALL!
echo         Install JWSteel_Setup_v3.0.11.exe to that path first.
pause
exit /b 1

:err_iscc
echo [ERROR] Inno Setup 6 compiler not found at:
echo         !ISCC!
pause
exit /b 1

:err_iss
echo [ERROR] installer.iss not next to this batch file.
echo         Expected at: !HERE!\installer.iss
pause
exit /b 1
