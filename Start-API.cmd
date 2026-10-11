@echo off
cd /d "%~dp0"
powershell -NoProfile -File "%~dp0scripts\run-component.ps1" api
pause
