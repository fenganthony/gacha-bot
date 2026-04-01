@echo off
echo Stopping Gacha Bot...
taskkill /f /im python.exe /fi "WINDOWTITLE eq Gacha Bot*" 2>nul
echo Done.
timeout /t 2
