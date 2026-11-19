@echo off
rem tools\run\play-ns2pkg7.cmd - NS2 dev program (game\x2ns2) on the complete pkg7 romfs (3.0.0 content).
rem
rem   tools\run\play-ns2pkg7.cmd           window, the HANDOVER 88 memory layout
rem   tools\run\play-ns2pkg7.cmd -headless no window (frames are still presented)
rem   tools\run\play-ns2pkg7.cmd -noquest  without XC2_NS2_QUEST_SKIP: the run asserts at 7.0 s on the quest vector
rem
rem Why these switches (HANDOVER 88):
rem   NXRT_MEMORY_APP_MEMORY_MB=5120  the guest asks SetHeapSize for 5010 MiB, which leaves room in the 12 GiB heap
rem                                   SECTION for the root arena blocks below.
rem   XC2_NS2_ROOT=MLSYSHANDLE=4488M  the MemManager's root arenas are created with a fixed block the game allocated
rem                                   inside its own heap; those blocks are back to back, so AssetMain x2 ran into the
rem                                   next one. The hook hands in a block of our own instead, taken from above the
rem                                   guest's heap through nxrt::svc_heap_extend (a block outside the heap view is
rem                                   refused by svcMapMemory: 20 x 0xD401, then svcBreak).
rem   XC2_NS2_SIZE=...                absolute sizes for the regions the compiled budgets are too small for. The
rem                                   region that ran out of room for the file read buffers is MenuResource, and its
rem                                   block is carved from its parent GfMenu, so both grow together.
rem   XC2_NS2_QUEST_SKIP=1            DIAGNOSTIC: gf::GfQuestManager::reqistLinkQuest pushes into a
rem                                   mm::fixed_vector<16> whose count field is never initialised with pkg7 data
rem                                   (0x24924924924900ff; the same address reads 0 with pkg0 data), so the first
rem                                   push asserts. Skipping the registrations lets the title applet finish; the
rem                                   order-quest list is then empty. Not a fix.
rem
rem Own save folder: work\save-ns2pkg7 (the playable build's save is not touched).
setlocal
set ROOT=%~dp0..\..
if not exist "%ROOT%\work\logs" mkdir "%ROOT%\work\logs"
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set STAMP=%%i
set GFXMODE=window
set QUEST=1
:args
if "%~1"=="" goto run
if /i "%~1"=="-headless" set GFXMODE=headless
if /i "%~1"=="-noquest" set QUEST=0
shift
goto args
:run
set NXRT_FS_ROMFS=game/romfs
set NXRT_FS_SAVE_DIR=%ROOT%\work\save-ns2pkg7
set NXRT_MEMORY_APP_MEMORY_MB=5120
set NXRT_MEMORY_LIMIT_GB=24
set XC2_NS2_ROOT=MLSYSHANDLE=4488M
set XC2_NS2_SIZE=AssetMain=1180M,GfMenu=640M,MenuResource=600M
set XC2_NS2_SCALE=1
set XC2_NS2_SCALE_NAMES=
if "%QUEST%"=="1" set XC2_NS2_QUEST_SKIP=1
echo program: NS2 dev (game\x2ns2)   romfs: game/romfs (pkg7, 3.0.0)   gfx: %GFXMODE%
echo memory:  heap 5010 MiB + own MLSYSHANDLE block 4488 MiB; AssetMain 1180 / GfMenu 640 / MenuResource 600 MB
if "%QUEST%"=="1" echo quest:   XC2_NS2_QUEST_SKIP=1 (DIAGNOSTIC: order-quest list stays empty)
if "%QUEST%"=="0" echo quest:   untouched (asserts at ~7 s on the fixed_vector of 16 linked quests)
echo save:    %ROOT%\work\save-ns2pkg7
echo log:     %ROOT%\work\logs\ns2pkg7-%STAMP%.log
cd /d "%ROOT%\xc2\build\boot"
if not defined XC2_LEGACY_BUILD set XC2_LEGACY_BUILD=%ROOT%\..\XC2\archive\build-legacy-2026-11-19
"%XC2_LEGACY_BUILD%\boot-ns2pkg7\xc2_boot.exe" --exefs "..\..\game\xc2ns2" --link host --gfx %GFXMODE% --log "%ROOT%\work\logs\ns2pkg7-%STAMP%.log"
echo exit=%ERRORLEVEL%
pause
