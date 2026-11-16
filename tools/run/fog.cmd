@echo off
rem tools\run\fog.cmd - live draw switch for the fog A/B, in-game list (HANDOVER 90).
rem ASCII only: cmd reads this file in the console code page, so non-ASCII text breaks the parse.
rem The list comes from the in-game whole-frame trace (play-301-20261115-221938): the draws that render into the
rem 640x360 scene, where the fog is actually drawn (the pass that copies it to 1280x720 is a format repack).
setlocal enabledelayedexpansion
set ROOT=%~dp0..\..
set FILE=%ROOT%\work\skip_fs.txt
if not exist "%FILE%" echo.> "%FILE%"
:loop
set CUR=
for /f "usebackq delims=" %%a in ("%FILE%") do if not "%%a"=="" set CUR=%%a
if not defined CUR set CUR=(none)
echo.
echo   fog A/B (in-game)   now: !CUR!
echo     1 = 17cdd28d  #395  2 3D textures + shadow map (volume fog / lighting, prime suspect)
echo     2 = e63faecd  #436  one 3D texture
echo     3 = 68534619  #434  12 draws, one 3D texture
echo     4 = 4f8b7b0f  #397  26 draws, main materials (no 3D)
echo     5 = 4a159453  #407  11 draws (no 3D)
echo     6 = 3f2a21d7  #393  single draw, two 2D textures
echo     7 = 75a4b8b8  #447  producer of the 640x360 coverage buffer
echo     c = clear (every draw back on)
echo     q = quit        (a raw hash prefix or #draw also works)
set N=
set /p N=  pick^> 
if /i "!N!"=="q" goto done
if "!N!"=="" goto loop
if /i "!N!"=="c" goto clear
set W=
if "!N!"=="1" set W=17cdd28d
if "!N!"=="2" set W=e63faecd
if "!N!"=="3" set W=68534619
if "!N!"=="4" set W=4f8b7b0f
if "!N!"=="5" set W=4a159453
if "!N!"=="6" set W=3f2a21d7
if "!N!"=="7" set W=75a4b8b8
if not defined W set W=!N!
> "%FILE%" echo !W!
echo   skipped: !W!   (live in 0.5 s)
goto loop
:clear
echo.> "%FILE%"
echo   cleared: every draw is back
goto loop
:done
echo.
echo   bye.  (the game keeps the last setting: !CUR!)
endlocal
pause
