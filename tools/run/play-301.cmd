@echo off
rem SHIFT moves %0 too, so the script's own folder is captured before the argument loop.
rem play-301.cmd - start the 3.0.1 development build.
rem The switches live in config\profiles\dev.ini; this file only forwards the few everyday ones to play.ps1.
rem   -headless   no window        -30 / -60   frame rate        -noprefill  skip the first-run cache pass
rem   -dump       collect shaders  -shots N    screenshots at frame N     -seconds N  stop after N seconds
rem Anything else: pwsh tools\run\play.ps1 -Profile dev -?
setlocal
set "HERE=%~dp0"
set ARGS=
:args
if "%~1"=="" goto run
if /i "%~1"=="-headless" (set ARGS=%ARGS% -Headless& shift& goto args)
if /i "%~1"=="-30"       (set ARGS=%ARGS% -Fps 30&   shift& goto args)
if /i "%~1"=="-60"       (set ARGS=%ARGS% -Fps 60&   shift& goto args)
if /i "%~1"=="-noprefill" (set ARGS=%ARGS% -NoPrefill& shift& goto args)
if /i "%~1"=="-dump"     (set ARGS=%ARGS% -Dump&     shift& goto args)
if /i "%~1"=="-shots"    (set ARGS=%ARGS% -Shots %~2& shift& shift& goto args)
if /i "%~1"=="-seconds"  (set ARGS=%ARGS% -Seconds %~2& shift& shift& goto args)
echo unknown option %~1
echo see: pwsh tools\run\play.ps1 -Profile dev -?
exit /b 2
:run
pwsh -NoProfile -ExecutionPolicy Bypass -File "%HERE%play.ps1" -Profile dev %ARGS%
exit /b %ERRORLEVEL%
