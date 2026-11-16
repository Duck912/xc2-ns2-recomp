@echo off
rem Hands-on launch at a normal frame rate (60 Hz presents, no diagnostic switches).
rem Double-click this file, or:  tools\run\play.cmd -PresentHz 30   /   tools\run\play.cmd -PresentHz 0
rem See xc2\scripts\play.ps1 for the options and the keyboard map.
setlocal
pwsh -NoProfile -NoExit -ExecutionPolicy Bypass -File "%~dp0..\..\xc2\scripts\play.ps1" %*
