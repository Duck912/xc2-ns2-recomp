@echo off
rem tools\run\play-301.cmd - the retail 3.0.1 program (game\xc2ns301) on the 3.0.1 romfs (HANDOVER 90).
rem
rem   tools\run\play-301.cmd            window
rem   tools\run\play-301.cmd -headless  no window (frames are still presented)
rem   tools\run\play-301.cmd -60        [xc2] fps = 60 + 60 Hz presents (HANDOVER 55/56); default is 30 Hz
rem
rem Why these switches:
rem   XC2_301_BOOTPARAM=1             the sdk reads its main thread handle out of a boot parameter block nobody
rem                                   fills here; without it the thread manager aborts (HANDOVER 90.5).
rem   XC2_301_VAMM=1                  call VammManager::InitializeIfEnabled before the first AllocateAddressRegion.
rem   NXRT_PROCESS_SYSTEM_RESOURCE_SIZE=0x6000000   the NPDM declares 96 MB; VAMM only needs it non-zero.
rem   NXRT_TITLE_DISPLAY_VERSION=3.0.1  the game compares it with the DLC's dlcver.bin and shows the add-on
rem                                   content error (which needs an applet we do not run) when they differ.
rem   NXRT_IPC_STUB_RESULT=0          bring-up probe: nn::hid cmd 3150 has no implementation yet.
rem   XC2_301_OPUS=1 / _AUDIO=1       the hardware Opus decoder and nn::audio's OutputStream, replaced by the sdk's
rem                                   own software OpusDecoder and the runtime's audio sink.
rem
rem Own save folder: work\save-301 (the playable build's save is not touched).
rem First frame after the tensor shaders landed takes about 20 s: the driver compiles the emulated
rem HMMA/LDSM/MOVM compute shaders once (4.5 MB of SPIR-V each).
setlocal
set ARGS=%*
set ROOT=%~dp0..\..
if not exist "%ROOT%\work\logs" mkdir "%ROOT%\work\logs"
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set STAMP=%%i
set GFXMODE=window
rem Frame rate: 60 is the default. FPS=60 makes the game step its own 60 Hz loop (native, no interpolation) and
rem HZ=60 sets the present interval to match, so the pacing comes from the game rather than from a host timer.
rem -30 falls back to the console's 30 Hz step.
set FPS=60
set HZ=60
rem Front-face convention (HANDOVER 03 section 26): the deferred lighting pass is one full-screen triangle with cull BACK, so the
rem wrong convention removes a whole layer (characters, eyes). 2 = the default used here; -ff0 / -ff1 / -ff2 / -ff3 for the A/B.
rem Cloud-sea quad subdivision (HANDOVER 90.20): 16 is the smallest n that cleans the title screen; 0 disables it.
set QSPLIT=16
set FFMODE=2
rem zh-Hans (Simplified) is the default; -en / -ja / -zh (Traditional) switch it. Both work: the game follows the console's
rem desired language, which is the Switch code here (zh-CN, a Windows locale, does NOT work - it falls back to English).
set LANGCODE=zh-Hans
:args
if "%~1"=="" goto run
if /i "%~1"=="-headless" (set GFXMODE=headless& shift& goto args)
if /i "%~1"=="-60" (set FPS=60& set HZ=60& shift& goto args)
if /i "%~1"=="-30" (set FPS=0& set HZ=30& shift& goto args)
if /i "%~1"=="-depthd32" (set DEPTHD32=1& shift& goto args)
if /i "%~1"=="-depthnearest" (set DEPTHNEAREST=1& shift& goto args)
if /i "%~1"=="-wrapclamp" (set WRAPCLAMP=1& shift& goto args)
if /i "%~1"=="-shadowalways" (set SHADOWALWAYS=1& shift& goto args)
if /i "%~1"=="-qsplit" (set QSPLIT=%~2& shift& shift& goto args)
if /i "%~1"=="-fbdebug" (set FBDEBUG=1& shift& goto args)
if /i "%~1"=="-dry" (set DRYRUN=1& shift& goto args)
if /i "%~1"=="-noprefill" (set XC2_NOPREFILL=1& shift& goto args)
if /i "%~1"=="-shots" (set SHOTS=1& set SHOTRANGE=%~2& shift& shift& goto args)
if /i "%~1"=="-texdump" (set TEXDUMP=1& shift& goto args)
if /i "%~1"=="-dump" (set DUMP=1& shift& goto args)
if /i "%~1"=="-snapfs" (set SNAPSHOT=1& set SNAPFS=%~2& shift& shift& goto args)
if /i "%~1"=="-snaprt" (set "SNAPRT=%~2"& call :commas& shift& shift& goto args)
if /i "%~1"=="-ff0" (set FFMODE=0& shift& goto args)
if /i "%~1"=="-ff1" (set FFMODE=1& shift& goto args)
if /i "%~1"=="-ff2" (set FFMODE=2& shift& goto args)
if /i "%~1"=="-ff3" (set FFMODE=3& shift& goto args)
if /i "%~1"=="-en" (set LANGCODE=en-US& shift& goto args)
if /i "%~1"=="-zh" (set LANGCODE=zh-Hant& shift& goto args)
if /i "%~1"=="-zhs" (set LANGCODE=zh-Hans& shift& goto args)
if /i "%~1"=="-ja" (set LANGCODE=ja& shift& goto args)
echo unknown option %~1& exit /b 2
:run
if not defined NXRT_FS_ROMFS set NXRT_FS_ROMFS=game/romfs-301
set NXRT_FS_SAVE_DIR=%ROOT%\work\save-301
set NXRT_AOC_DIR=game/dlc-301
set NXRT_MEMORY_LIMIT_GB=24
set XC2_301_BOOTPARAM=1
set XC2_301_VAMM=1
set XC2_301_OPUS=1
set XC2_301_AUDIO=1
set NXRT_PROCESS_SYSTEM_RESOURCE_SIZE=0x6000000
set NXRT_TITLE_DISPLAY_VERSION=3.0.1
set NXRT_IPC_STUB_RESULT=0
rem Language (HANDOVER 90): the game follows the console's desired language, and it only offers the ones the title profile
rem says it supports, so both have to name it. The NS1 recomp sets lang = zh-CN in xc2.ini; this is the same pick. Use
rem -en / -ja to switch back.
rem Shader collection ([nvn] dump_missing / dump_all, extended - then two files per block, for EVERY block the game asks for,
rem on every launch; after ~57 sessions the folder held 7,645 files / 44 MB and the manifest 219k rows). Off by default since the
rem round-45 audit - add -dump when the corpus has to be refreshed.
if defined DUMP set NXRT_NVN_DUMP_MISSING=%ROOT%\work\shader_dump-301-live
if defined DUMP set NXRT_NVN_DUMP_ALL=1
if defined DUMP if not exist "%ROOT%\work\shader_dump-301-live" mkdir "%ROOT%\work\shader_dump-301-live"
rem Trace helpers (F11): -texdump dumps the CPU-prepared data of every sampled texture,
rem -snaprt 514,435,516 snapshots every draw that renders into those texture ids,
rem -snapfs f55686de snapshots every draw of that fragment shader.
if defined SHOTS if not exist "%ROOT%\work\shots-301" mkdir "%ROOT%\work\shots-301"
rem -qsplit N: subdivide the cloud sea's huge quads into an N x N grid (0 = off; xc2-recomp calls this XC2_QUAD_SPLIT).
if defined SHADOWALWAYS set NXRT_NVN_SHADOW_ALWAYS=1
if defined QSPLIT set NXRT_NVN_QUAD_SPLIT=%QSPLIT%
if defined FBDEBUG set NXRT_NVN_FB_DEBUG=1
if defined DEPTHD32 set NXRT_NVN_DEPTH_FORMAT_D32=1
if defined DEPTHNEAREST set NXRT_NVN_DEPTH_SAMPLER_NEAREST=1
if defined WRAPCLAMP set NXRT_NVN_WRAP_REPEAT_CLAMP=1
if defined SHOTS set NXRT_NVN_SHOT_FRAMES=%SHOTRANGE%
if defined SHOTS set NXRT_NVN_SHOT_DIR=%ROOT%\work\shots-301
if defined TEXDUMP set NXRT_NVN_TRACE_DUMP_TEX=%ROOT%\work\texdump-301
if defined SNAPRT set NXRT_NVN_TRACE_SNAP_RT=%SNAPRT%
if defined TEXDUMP echo   trace options: texdump
if defined SNAPRT echo   trace options: snap rt %SNAPRT%
if defined SHOTS echo   shots: frames %SHOTRANGE% -> work\shots-301
if defined DRYRUN echo.& echo   front face %FFMODE%   language %LANGCODE%   gfx %GFXMODE%& echo   snap rt [%SNAPRT%]  snap fs [%SNAPFS%]  shots [%SHOTRANGE%]  texdump [%TEXDUMP%]& echo   depth: d32 [%DEPTHD32%]  nearest [%DEPTHNEAREST%]  wrapclamp [%WRAPCLAMP%]& echo   cloud sea quad_split [%QSPLIT%]& echo   (dry run: nothing started)& exit /b 0
if defined SNAPFS echo   trace options: snap fs %SNAPFS%
if defined SNAPFS set NXRT_NVN_TRACE_SNAP_FS=%SNAPFS%
set NXRT_NVN_FRONT_FACE_MODE=%FFMODE%
rem Frame rate: the ini's [xc2] fps / present interval are the defaults; these two override them (NXRT_* wins).
set NXRT_XC2_FPS=%FPS%
set NXRT_NVN_PRESENT_INTERVAL_HZ=%HZ%
rem Live draw switch (same idea as tools\run\ab.cmd): whatever is written into work\skip_fs.txt is applied within 0.5 s.
rem   a hash prefix  -> that fragment shader's draws are skipped
rem   #198 or #198-210 -> those draw numbers of the frame
rem   empty -> everything drawn again
set NXRT_NVN_SKIP_FS_FILE=%ROOT%\work\skip_fs.txt
if not exist "%NXRT_NVN_SKIP_FS_FILE%" (echo.> "%NXRT_NVN_SKIP_FS_FILE%")
rem Live state switch: whatever is written into this file is applied within 0.25 s, no restart (toolsunf.cmd writes it).
rem Upscaler / tuning hot switch ([dlss] hot_file): tools\run\up.cmd writes it, the runtime re-reads it 4x a second.
rem It OVERRIDES the ini, and it used to persist across runs: a session left on fsr3 kept fsr3 even after the ini said
rem taau, which cost an afternoon of chasing a shimmer that the upscaler was causing. Start every run from the ini.
set NXRT_DLSS_HOT_FILE=%ROOT%\work\dlss_hot.txt
if exist "%NXRT_DLSS_HOT_FILE%" del /q "%NXRT_DLSS_HOT_FILE%"
rem The preload pack is read BEFORE the loose .spv files, so a pack built before a shader was replaced hides that
rem replacement: the change looks like it did nothing. It is dropped on every launch, unconditionally, because the
rem mtime heuristic that used to guard it is wrong exactly when it matters - Copy-Item keeps the source's timestamp,
rem so restoring a backup makes the module look older than the pack. Measured cost: 0.6 s of preload against 0.4 s
rem from the pack.
rem The cache can be pointed elsewhere (NXRT_NVN_SHADER_CACHE), and then %ROOT% is the wrong place to look: the pack
rem sits next to the directory that is actually in use, not next to this checkout.
powershell -NoProfile -Command "$d=$env:NXRT_NVN_SHADER_CACHE; if (-not $d) { $d=Join-Path '%ROOT%' 'xc2\build\boot\shader_cache\spirv' }; $c=Split-Path $d -Parent; foreach ($n in 'spirv.preload.pack','spirv.preload.pack.new') { $p=Join-Path $c $n; if (Test-Path $p) { Remove-Item $p -Force -ErrorAction SilentlyContinue } }" >NUL 2>&1
set NXRT_NVN_HOT_STATE_FILE=%ROOT%\work\hot_state.txt
if not exist "%NXRT_NVN_HOT_STATE_FILE%" (echo front_face=%FFMODE%> "%NXRT_NVN_HOT_STATE_FILE%")
set NXRT_SYSTEM_LANGUAGE=%LANGCODE%
set NXRT_TITLE_SUPPORTED_LANGUAGES=Japanese,AmericanEnglish,BritishEnglish,French,German,Italian,Spanish,LatinAmericanSpanish,Chinese,Taiwanese,Korean,SimplifiedChinese,TraditionalChinese
set LOG=%ROOT%\work\logs\play-301-%STAMP%.log
echo log: %LOG%
rem Persistent record of how this launch was configured: a double-click or an old command line drops the arguments,
rem and then the console line above has already scrolled away.
> "%ROOT%\work\logs\last-301-launch.txt" echo %DATE% %TIME% args=[%ARGS%] fps=%FPS% hz=%HZ%
rem Self-documenting: a launch that shows 30 here did not get -60 (a double-click or an old command line drops the argument).
echo   frame rate: [xc2] fps = %FPS%, presents %HZ% Hz
rem The working directory is where the runtime keeps its shader cache and resolves the default romfs path, so it has
rem to exist even on a first run: the retail build only creates boot-301.
if not exist "%ROOT%\xc2\build\boot" mkdir "%ROOT%\xc2\build\boot"
cd /d "%ROOT%\xc2\build\boot"
if errorlevel 1 (echo cannot enter "%ROOT%\xc2\build\boot"& exit /b 1)
rem XC2_EXE runs a different build with the same environment: the point of a clean-room build is to compare it with
rem this one, and comparing means launching both the same way.
if not defined XC2_EXE set XC2_EXE=%ROOT%\xc2\build\boot-301\xc2_boot.exe
rem A fresh cache renders with gaps - the title screen is black - until the game has been run once and the blocks it
rem asked for are translated. Do that collection headless here, so the FIRST launch is already complete. Once per
rem cache (work\.prefilled); -noprefill skips it.
if not defined XC2_NOPREFILL (
    if not defined NXRT_NVN_SHADER_CACHE set NXRT_NVN_SHADER_CACHE=%ROOT%\xc2\build\boot\shader_cache\spirv
    powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\tools\run\prefill.ps1" -Exe "%XC2_EXE%" -Exefs "%ROOT%\xc2\game\xc2ns301" -Cache "%NXRT_NVN_SHADER_CACHE%" -Work "%ROOT%\work"
)
rem Every block the game asks for and the cache lacks is written to work\missing-301, and ds_debug records which
rem samplers need their type corrected (format-07753). After the game exits, fill-cache translates and installs both,
rem so the NEXT launch is complete - including the shaders that only appear when a new area is entered.
if not defined NXRT_NVN_DUMP_MISSING set NXRT_NVN_DUMP_MISSING=%ROOT%\work\missing-301
if not defined NXRT_NVN_DS_DEBUG set NXRT_NVN_DS_DEBUG=1
"%XC2_EXE%" --exefs "%ROOT%\xc2\game\xc2ns301" --link host --gfx %GFXMODE% --log "%LOG%"
set XC2_RC=%ERRORLEVEL%
if not defined NXRT_NVN_SHADER_CACHE set NXRT_NVN_SHADER_CACHE=%ROOT%\xc2\build\boot\shader_cache\spirv
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\tools\run\fill-cache.ps1" -Cache "%NXRT_NVN_SHADER_CACHE%" -Missing "%ROOT%\work\missing-301" -DsLog "%LOG%"
set ERRORLEVEL=%XC2_RC%
echo exit code %ERRORLEVEL%
endlocal
rem -snaprt takes its ids joined with '+', because a comma is also an argument separator for shift.
:commas
set "SNAPRT=%SNAPRT:+=,%"
exit /b 0
