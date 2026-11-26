@echo off
rem tools\run\play-log.cmd - launch with a TIMESTAMPED log so a crash report survives the next launch.
rem
rem   tools\run\play-log.cmd            30 Hz presents, base romfs (the 1:1 pacing, HANDOVER -1)
rem   tools\run\play-log.cmd -60        60 fps: [xc2] fps = 60, the game's own step runs at 60 (HANDOVER 55/56)
rem   tools\run\play-log.cmd -pkg7      pkg7 romfs (the 3.0.0 content)
rem   tools\run\play-log.cmd -60 -pkg7
rem
rem Why a timestamped log: play.cmd writes play.log and every launch overwrites it, so a crash that happens in
rem one session is gone by the next. This writes work\logs\play-<date>-<time>.log and leaves it there.
rem NOTE the log is buffered: while the game runs the file can still be 0 bytes, it fills on flush/exit.
setlocal
set ROOT=%~dp0..\..
if not exist "%ROOT%\work\logs" mkdir "%ROOT%\work\logs"
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set STAMP=%%i
set ROMFS=game/romfs-pkg0
set FPS=0
set HZ=30
:args
if "%~1"=="" goto run
if /i "%~1"=="-pkg7" set ROMFS=game/romfs
if /i "%~1"=="-60" set FPS=60
if /i "%~1"=="-60" set HZ=60
if /i "%~1"=="-30" set FPS=0
if /i "%~1"=="-30" set HZ=30
shift
goto args
:run
rem the diagnostic switches of earlier rounds change what a frame looks like: start from a clean environment
for %%v in (NXRT_NVN_SHOT_FRAMES NXRT_NVN_TRACE_SEC NXRT_NVN_TRACE_DUMP_TEX NXRT_NVN_FRAME_CSV NXRT_NVN_TRACE_FRAME
  NXRT_NVN_SKIP_FS_FILE NXRT_NVN_DUMP_MISSING NXRT_NVN_DEPTH_FUNC_EQUAL NXRT_NVN_CULL_OFF_ALL NXRT_NVN_STENCIL_OFF
  NXRT_NVN_DEPTH_OFF_FS NXRT_NVN_CULL_OFF_FS NXRT_NVN_DEPTH_WRITE_FS NXRT_NVN_SPV_HOT NXRT_NVN_TRACE_UBO_DIR
  XC2_MODEL_PROBE XC2_TRACE_LAUNCHER NXRT_DEBUG_ENTRY NXRT_DEBUG_DUMP_AT NXRT_DEBUG_DUMP_PTRS
  NXRT_MEMORY_HEAP_SECTION NXRT_MEMORY_HEAP_COMMIT_MB) do set %%v=
set NXRT_FS_ROMFS=%ROMFS%
set NXRT_NVN_PRESENT_INTERVAL_HZ=%HZ%
set NXRT_XC2_FPS=%FPS%
echo romfs:    %ROMFS%
echo presents: %HZ% Hz   [xc2] fps = %FPS%
echo log:      %ROOT%\work\logs\play-%STAMP%.log
cd /d "%ROOT%\xc2\build\boot"
xc2_boot.exe --exefs ..\..\game\xc2ns2 --link host --gfx window --log "%ROOT%\work\logs\play-%STAMP%.log"
echo exit=%ERRORLEVEL%
pause
