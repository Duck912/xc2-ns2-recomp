@echo off
rem tools\run\ab-mode.cmd <docked|handheld> [-dry] - A/B the operation mode the game is told (HANDOVER 39).
rem
rem   operation_mode changes what nn::vi and nn::am report as the display (1920x1080 docked / 1280x720
rem   handheld), the performance mode and the controller style. It does NOT change the window: that is
rem   [gfx] window_width/height in nxrt.ini. The mode goes in as NXRT_AM_OPERATION_MODE so the ini stays put.
rem
rem   The UI and DLSS output sizes are printed in the log in the first seconds after boot, so a run that
rem   only reaches the title screen is enough to compare them.
setlocal
set ROOT=%~dp0..\..
set MODE=%~1
if /i "%MODE%"=="docked" goto ok
if /i "%MODE%"=="handheld" goto ok
echo usage: ab-mode.cmd docked^|handheld [-dry]
exit /b 2
:ok
shift
set NXRT_AM_OPERATION_MODE=%MODE%
echo   operation_mode = %MODE%   (window from [gfx] window_width/height)
call "%ROOT%\tools\run\play-301.cmd" %1 %2 %3
endlocal
