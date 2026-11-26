@echo off
rem hot.cmd -- hands-on session with shader hot swap on the fog chain.
rem Edit <hash>.spv in shader_cache\spirv and it is re-read within 250 ms, no restart.
rem Lives in tools\run\; the game still runs from xc2\build\boot (relative paths below).
setlocal
cd /d "%~dp0..\..\xc2\build\boot"
tasklist /fi "imagename eq xc2_boot.exe" 2>nul | find /i "xc2_boot.exe" >nul && (
  echo xc2_boot is already running - close that window first.
  pause
  exit /b 2
)
set "SKIP=%~dp0skip_uvdiv.txt"
> "%SKIP%" echo.
set "NXRT_NVN_SKIP_FS_FILE=%SKIP%"
set "NXRT_NVN_SPV_HOT=2649526f,57bdd1a0,cc3eac68"
set "NXRT_NVN_PRESENT_INTERVAL_HZ=60"
set "NXRT_NVN_TRACE_UBO_DIR=%~dp0..\..\work\_tmp\ubo"
set "NXRT_NVN_TRACE_UBO_BYTES=1024"
set "NXRT_NVN_TRACE_DUMP_TEX=off"
set "XC2_PRESS="
set "XC2_NO_INPUT="
set "NXRT_NVN_TRACE_SEC="
set "NXRT_NVN_TRACE_FRAME="
set "NXRT_NVN_SHOT_FRAMES="
echo.
echo   shader hot swap: 2649526f (froxel fog), 57bdd1a0 (cloud cards), cc3eac68 (fog composite)
echo   edit the .spv in shader_cache\spirv and it is live in 0.25 s.
echo.
xc2_boot.exe --exefs "..\..\game\xc2ns2" --link host --gfx window --log tt_hot.log
