@echo off
rem tools\run\ff.cmd - interactive live switch for the front-face convention (HANDOVER 90 / 03 section 26).
rem
rem Run it WHILE the game is running: type a number, the picture changes within 0.25 s (the runtime re-reads
rem work\hot_state.txt four times a second), so one spot of one scene can be compared without a restart.
rem
rem   0 = flip with the lower-left origin (the old, inverted choice)
rem   1 = flip with the flipped viewport (the runtime default)
rem   2 = never flip
rem   3 = always flip
rem   q = quit
setlocal enabledelayedexpansion
set ROOT=%~dp0..\..
set FILE=%ROOT%\work\hot_state.txt
if not exist "%FILE%" (echo front_face=1> "%FILE%")
:loop
set CUR=?
for /f "usebackq tokens=2 delims==" %%a in ("%FILE%") do set CUR=%%a
echo.
echo   front-face mode   (now: !CUR!)
echo     0 = flip with the lower-left origin   (old, inverted)
echo     1 = flip with the flipped viewport   (runtime default)
echo     2 = never flip
echo     3 = always flip
echo     q = quit
set N=
set /p N=  mode^> 
if /i "!N!"=="q" goto done
if "!N!"=="" (
  set /a EMPTY+=1
  if !EMPTY! GEQ 2 goto done
  goto loop
)
set /a EMPTY=0
if not "!N!"=="0" if not "!N!"=="1" if not "!N!"=="2" if not "!N!"=="3" (
  echo   !N! is not one of 0 1 2 3 - nothing written.
  goto loop
)
echo front_face=!N!> "%FILE%
echo   applied front_face=!N!   (work\hot_state.txt, live in 0.25 s)
goto loop
:done
endlocal
