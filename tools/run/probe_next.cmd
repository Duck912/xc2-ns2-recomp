@echo off
rem probe_next.cmd -- one double-click = the next state of the skip-list sweep (see probe_next.ps1).
pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0probe_next.ps1"
pause
