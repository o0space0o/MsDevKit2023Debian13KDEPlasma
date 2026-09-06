@echo off
title DevKit2023CustomLinux
powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -File "%~dp0windows\Start-DevKit2023CustomLinux.ps1"
if errorlevel 1 pause
