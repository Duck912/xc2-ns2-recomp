@echo off
rem tools\run\play-ns1.cmd - run the 2026 NS1 3.0.0 program (lift-ns1) against the pkg7 (3.0.0) romfs.
rem
rem   tools\run\play-ns1.cmd           30 Hz, pkg7 romfs, 3x memory budgets (HANDOVER 86)
rem   tools\run\play-ns1.cmd -60       60 fps (the [xc2] fps path of HANDOVER 55/56)
rem   tools\run\play-ns1.cmd -probe    also arm the NS1 diagnostics (XC2_NS1_PROBE=1): if the guest asserts while
rem                                    playing, the log then names the region that ran out (HANDOVER 86.2)
rem
rem This route keeps its OWN save folder (work\save-ns1): the playable build's save is shared with the console dump and
rem must not be written by a 3.0.0 test (HANDOVER 41). Delete that folder to start from a clean state.
rem
rem Why a separate launcher: this is the 3.0.0 guest (<game dump>\Xenoblade Chronicles 2\exefs, lifted into
rem xc2\build\lift-ns1) on the 3.0.0 content (game\romfs = pkg7). The playable build (play-log.cmd) is the NS2 program on
rem pkg0 and is untouched by this.
rem
rem The two memory switches are what makes it boot: the 3.0.0 NS1 build's compiled mtl::MemManager budgets fit the NS1 asset
rem set, and pkg7's menu/font data needs about 3x the space. XC2_NS1_ARENA_SCALE scales the three arenas the regions are
rem carved from (2244 + 216 + 512 MiB -> x3 = 8.9 GiB of the 10.6 GiB guest heap), XC2_NS1_SCALE scales every region.
rem Add-on content is served (HANDOVER 87): aoc:u lists the indices whose folder is on disk (game\dlc\indices.txt, only 1 = Torna
rem is installed) and fsp-srv OpenDataStorageByDataId mounts it. -noaoc answers "no add-on content" instead (NXRT_AOC_LIST=0),
rem which is what the 3.0.0 guest booted with before the mount worked.
setlocal
set ROOT=%~dp0..\..
if not exist "%ROOT%\work\logs" mkdir "%ROOT%\work\logs"
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set STAMP=%%i
set HZ=30
set FPS=0
:args
if "%~1"=="" goto run
if /i "%~1"=="-60" set FPS=60
if /i "%~1"=="-60" set HZ=60
if /i "%~1"=="-30" set FPS=0
if /i "%~1"=="-30" set HZ=30
if /i "%~1"=="-probe" set PROBE=1
if /i "%~1"=="-swap" set SWAP=1
if /i "%~1"=="-noaoc" set NOAOC=1
if /i "%~1"=="-jp" set JP=1
shift
goto args
:run
for %%v in (NXRT_NVN_SHOT_FRAMES NXRT_NVN_TRACE_SEC NXRT_NVN_TRACE_DUMP_TEX NXRT_NVN_FRAME_CSV NXRT_NVN_TRACE_FRAME
  NXRT_NVN_SKIP_FS_FILE NXRT_NVN_DUMP_MISSING NXRT_NVN_DEPTH_FUNC_EQUAL NXRT_NVN_CULL_OFF_ALL NXRT_NVN_STENCIL_OFF
  NXRT_NVN_DEPTH_OFF_FS NXRT_NVN_CULL_OFF_FS NXRT_NVN_DEPTH_WRITE_FS NXRT_NVN_SPV_HOT NXRT_NVN_TRACE_UBO_DIR
  XC2_MODEL_PROBE XC2_TRACE_LAUNCHER NXRT_DEBUG_ENTRY NXRT_DEBUG_DUMP_AT NXRT_DEBUG_DUMP_PTRS
  NXRT_MEMORY_HEAP_SECTION NXRT_MEMORY_HEAP_COMMIT_MB XC2_NS1_PROBE XC2_NS1_BUMP XC2_NS1_ROOT_ARENA
  XC2_NS1_DUMP_MIN) do set %%v=
set NXRT_FS_ROMFS=game/romfs
set NXRT_NVN_PRESENT_INTERVAL_HZ=%HZ%
set NXRT_XC2_FPS=%FPS%
set NXRT_AOC_LIST=1
if defined NOAOC set NXRT_AOC_LIST=0
set XC2_NS1_SCALE=3
set XC2_NS1_ARENA_SCALE=3
if not exist "%ROOT%\work\save-ns1" mkdir "%ROOT%\work\save-ns1"
set NXRT_FS_SAVE_DIR=%ROOT%\work\save-ns1
rem -jp: the Japanese 3.0.0 pair (HANDOVER 87.10): JP exefs + the JP RomFS extracted from the NS1 install
rem (game\romfs-jp, 28,181 files) + the JP add-on content (game\dlc\0100f3400332d00N). The JP build's own title ids
rem differ from the US profile (0100E95004038000), so the program id has to follow: [process] program_id is the one
rem that sticks ([title] program_id alone is overridden by it). Own save folder: work\save-jp.
if defined JP set NXRT_FS_ROMFS=game/romfs-jp
if defined JP set NXRT_PROCESS_PROGRAM_ID=0x0100F3400332C000
if defined JP if not exist "%ROOT%\work\save-jp" mkdir "%ROOT%\work\save-jp"
if defined JP set NXRT_FS_SAVE_DIR=%ROOT%\work\save-jp
if defined PROBE set XC2_NS1_PROBE=1
if defined PROBE set XC2_PAD_DEBUG=1
rem -swap: the 3.0.0 guest ignores button bits 0..3 (HANDOVER 86.11), so the face buttons also drive the D-pad:
rem A = up, B = down, X = left, Y = right. Everything else keeps working.
if defined SWAP set XC2_PAD_SWAP=1
if defined JP echo program: JP 3.0.0 (lift-ns1)   romfs: game/romfs-jp (JP NS1 install)   aoc: JP 1..6   presents: %HZ% Hz
if not defined JP echo program: NS1 3.0.0 (lift-ns1)   romfs: game/romfs (pkg7)   presents: %HZ% Hz
if defined NOAOC echo budgets: regions x3, arenas x3   aoc: none (-noaoc)
if not defined NOAOC echo budgets: regions x3, arenas x3   aoc: on (game\dlc\indices.txt, installed only)
if defined JP echo save:    %ROOT%\work\save-jp (own folder; the shared save is not touched)
if not defined JP echo save:    %ROOT%\work\save-ns1 (own folder; the shared save is not touched)
if defined PROBE echo probes:  on (XC2_NS1_PROBE=1)
if defined SWAP echo pad:     face buttons also act as the D-pad (A=up B=down X=left Y=right)
echo log:     %ROOT%\work\logs\ns1-%STAMP%.log
cd /d "%ROOT%\xc2\build\boot"
"%ROOT%\xc2\build\boot-ns1\xc2_boot.exe" --exefs "<game dump>\Xenoblade Chronicles 2\exefs" --link host --gfx window --log "%ROOT%\work\logs\ns1-%STAMP%.log"
echo exit=%ERRORLEVEL%
pause