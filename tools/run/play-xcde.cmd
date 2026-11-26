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
rem Started by the launcher (it sets NXRT_LAUNCHER_DIR and runs this in its run folder): the game reads the run folder's
rem nxrt.ini, the file the launcher's Settings page and the in-game F1 page write, and Streamline downloaded there after
rem setup is copied where NVN-HLE looks for it (the boot folder's user\streamline).
set "BOOT=%HERE%..\..\xcde\build\200\boot-n2den"
if defined NXRT_LAUNCHER_DIR if exist "%CD%\nxrt.ini" set "NXRT_INI=%CD%\nxrt.ini"
if exist "%CD%\upscalers\streamline\sl.interposer.dll" if not exist "%BOOT%\user\streamline\sl.interposer.dll" xcopy /e /i /q /y "%CD%\upscalers\streamline" "%BOOT%\user\streamline\" >nul
pwsh -NoProfile -ExecutionPolicy Bypass -File "%HERE%play.ps1" -Profile xcde -Retries 0 %ARGS%
exit /b %ERRORLEVEL%
