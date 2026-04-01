@echo off
chcp 65001 >nul 2>&1
title Gacha Bot + Dashboard
cd /d "%~dp0"

echo ============================================
echo   Gacha Bot - Starting...
echo ============================================
echo.

:: Check Python exists
if not exist "..\python\python.exe" (
    echo ERROR: Python not found at ..\python\python.exe
    echo Current directory: %cd%
    pause
    exit /b 1
)

echo Starting Bot + Dashboard...
echo Press Ctrl+C to stop.
echo.
"..\python\python.exe" run.py

echo.
echo ============================================
echo   Bot has stopped. Exit code: %errorlevel%
echo ============================================
pause
