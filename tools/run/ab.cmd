@echo off
rem ab.cmd -- a hands-on session at 30 Hz (the same pacing as play.cmd -PresentHz 30, rule 2: 60 Hz flickers) with the live
rem skip switch on. Whatever is written into skip_uvdiv.txt next to this file is applied within half a second, so a draw or a
rem whole fragment shader can be turned off and back on without a restart:
rem
rem   echo 1875d6ca > tools\run\skip_uvdiv.txt     turn off the shader whose hash starts with 1875d6ca
rem   echo #3297 > tools\run\skip_uvdiv.txt         turn off draw 3297 of every frame (the numbers the F11 trace prints)
rem   echo. > tools\run\skip_uvdiv.txt              back to everything on
rem
rem tools\run\probe_menu.ps1 drives the same file with a menu (the fog states from round 26).
setlocal
cd /d "%~dp0..\..\xc2\build\boot"
tasklist /fi "imagename eq xc2_boot.exe" 2>nul | find /i "xc2_boot.exe" >nul && (
  echo xc2_boot is already running - close that window first.
  pause
  exit /b 2
)
set "SKIP=%~dp0skip_uvdiv.txt"
rem keep the switch file present and empty (an empty file = nothing skipped) so a stale hash is not left over
> "%SKIP%" echo.
set "NXRT_NVN_SKIP_FS_FILE=%SKIP%"
set "NXRT_NVN_PRESENT_INTERVAL_HZ=30"
set "XC2_PRESS="
set "XC2_NO_INPUT="
set "NXRT_NVN_SPV_HOT="
set "NXRT_NVN_TRACE_FRAME="
echo   present 30 Hz, skip switch: %SKIP%
echo   F11 traces the next frame, F12 screenshots. Close the window to stop.
xc2_boot.exe --exefs "..\..\game\xc2ns2" --link host --gfx window --log play.log
