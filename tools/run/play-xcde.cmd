@echo off
rem play-xcde.cmd - start XC:DE (Switch 2 Edition) on NVN-HLE: config\profiles\xcde.ini through play.ps1.
rem The launcher's Play runs this in a checkout. Options: -30 / -60 frame rate, -seconds N stop after N seconds.
rem Anything else: pwsh tools\run\play.ps1 -Profile xcde -?
setlocal
set "HERE=%~dp0"
set ARGS=
:args
if "%~1"=="" goto run
if /i "%~1"=="-30"      (set ARGS=%ARGS% -Fps 30&   shift& goto args)
if /i "%~1"=="-60"      (set ARGS=%ARGS% -Fps 60&   shift& goto args)
if /i "%~1"=="-seconds" (set ARGS=%ARGS% -Seconds %~2& shift& shift& goto args)
echo unknown option %~1
echo see: pwsh tools\run\play.ps1 -Profile xcde -?
exit /b 2
:run
pwsh -NoProfile -ExecutionPolicy Bypass -File "%HERE%play.ps1" -Profile xcde -Retries 0 %ARGS%
exit /b %ERRORLEVEL%
