@echo off
setlocal enabledelayedexpansion

echo ============================================
echo   Gacha Bot - Windows Installer Builder
echo ============================================
echo.

set "ROOT=%~dp0.."
set "BUILD=%~dp0build"
set "DIST=%~dp0dist"
set "PYVER=3.12.8"
set "PYURL=https://www.python.org/ftp/python/%PYVER%/python-%PYVER%-embed-amd64.zip"

:: Clean previous build
if exist "%BUILD%" rmdir /s /q "%BUILD%"
mkdir "%BUILD%"
mkdir "%BUILD%\python"
mkdir "%BUILD%\app"

echo [1/5] Downloading embedded Python %PYVER%...
powershell -Command "Invoke-WebRequest -Uri '%PYURL%' -OutFile '%BUILD%\python-embed.zip'" || (
    echo ERROR: Failed to download Python. Check internet connection.
    exit /b 1
)

echo [2/5] Extracting Python...
powershell -Command "Expand-Archive -Path '%BUILD%\python-embed.zip' -DestinationPath '%BUILD%\python' -Force"
del "%BUILD%\python-embed.zip"

:: Enable pip in embedded Python - uncomment import site in ._pth file
for %%f in ("%BUILD%\python\python*._pth") do (
    powershell -Command "(Get-Content '%%f') -replace '#import site','import site' | Set-Content '%%f'"
)

echo [3/5] Installing pip...
powershell -Command "Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile '%BUILD%\get-pip.py'"
"%BUILD%\python\python.exe" "%BUILD%\get-pip.py" --no-warn-script-location
del "%BUILD%\get-pip.py"

echo [4/5] Installing dependencies...
"%BUILD%\python\python.exe" -m pip install --no-warn-script-location -r "%ROOT%\requirements.txt"

echo [5/5] Copying application files...
copy /Y "%ROOT%\bot.py" "%BUILD%\app\"
copy /Y "%ROOT%\dashboard.py" "%BUILD%\app\"
copy /Y "%ROOT%\database.py" "%BUILD%\app\"
copy /Y "%ROOT%\paths.py" "%BUILD%\app\"
copy /Y "%ROOT%\guild_config.py" "%BUILD%\app\"
copy /Y "%ROOT%\requirements.txt" "%BUILD%\app\"
copy /Y "%ROOT%\config.example.json" "%BUILD%\app\"
xcopy /E /I /Y "%ROOT%\cogs" "%BUILD%\app\cogs\"
xcopy /E /I /Y "%ROOT%\static" "%BUILD%\app\static\"

:: Copy launcher and service scripts
copy /Y "%~dp0launcher.bat" "%BUILD%\app\"
copy /Y "%~dp0stop.bat" "%BUILD%\app\"
copy /Y "%~dp0configure.py" "%BUILD%\app\"
copy /Y "%~dp0run.py" "%BUILD%\app\"

echo.
echo Build complete! Files in: %BUILD%
echo.
echo Now compile the Inno Setup script:
echo   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" "%~dp0setup.iss"
echo.
pause
