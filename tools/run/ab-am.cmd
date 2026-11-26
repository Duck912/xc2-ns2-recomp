@echo off
rem tools\run\ab-am.cmd <resolution|default> <graphics_scale|default> [-dry] - the two [am] knobs the game sizes its
rem DLSS networks from (HANDOVER 39).
rem
rem   resolution      [am] resolution = WxH: what ICommonStateGetter::GetDefaultDisplayResolution answers (the applet
rem                   display). The game's UI/composite DLSS networks may follow it.
rem   graphics_scale  [am] graphics_scale = 10|20|30: the Switch 2 graphics scale level (10 = level 0, full quality).
rem                   May change the 3D network's output size (currently 2560x1440 in both modes).
rem
rem   Both go in as NXRT_AM_* so nxrt.ini stays put; the window stays [gfx] window_width/height.
setlocal
set ROOT=%~dp0..\..
set RES=%~1
set SCALE=%~2
shift
shift
if /i not "%RES%"=="default" set NXRT_AM_RESOLUTION=%RES%
if /i not "%SCALE%"=="default" set NXRT_AM_GRAPHICS_SCALE=%SCALE%
echo   [am] resolution = %RES%   [am] graphics_scale = %SCALE%   (window from [gfx], mode from the environment)
call "%ROOT%\tools\run\play-301.cmd" %1 %2 %3
endlocal
