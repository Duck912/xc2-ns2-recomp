@echo off
rem tools\run\up.cmd - hot switch for the host upscaler and its tuning (HANDOVER 90). ASCII only.
rem Writes work\dlss_hot.txt; the runtime re-reads it four times a second, so no restart.
setlocal enabledelayedexpansion
set ROOT=%~dp0..\..
set FILE=%ROOT%\work\dlss_hot.txt
if not exist "%FILE%" ( > "%FILE%" echo upscaler = taau )
:loop
set UP=
set W=
set J=
set M=
for /f "usebackq tokens=1,2 delims==" %%a in ("%FILE%") do (
  set K=%%a
  set K=!K: =!
  set V=%%b
  set V=!V: =!
  if /i "!K!"=="upscaler" set UP=!V!
  if /i "!K!"=="history_weight" set W=!V!
  if /i "!K!"=="jitter_sign" set J=!V!
  if /i "!K!"=="mv_sign" set M=!V!
)
if not defined UP set UP=taau
if not defined W set W=12
if not defined J set J=0
if not defined M set M=0
echo.
echo   upscaler !UP!   history_weight !W!   jitter_sign !J!   mv_sign !M!
echo     1 = taau (temporal, default)   2 = spatial (no history)   3 = bilinear   4 = fsr3
echo     w = history_weight 12/24/32/48    j = jitter_sign 0..3    m = mv_sign 0..3
echo     c = back to the ini    q = quit
set N=
set /p N=  pick^> 
if /i "!N!"=="q" goto done
if "!N!"=="" goto loop
if /i "!N!"=="c" goto clear
if "!N!"=="1" set UP=taau
if "!N!"=="2" set UP=spatial
if "!N!"=="3" set UP=bilinear
if "!N!"=="4" set UP=fsr3
if /i "!N!"=="w" call :cyclew
if /i "!N!"=="j" call :cyclej
if /i "!N!"=="m" call :cyclem
> "%FILE%" echo upscaler = !UP!
>> "%FILE%" echo history_weight = !W!
>> "%FILE%" echo jitter_sign = !J!
>> "%FILE%" echo mv_sign = !M!
echo   applied: upscaler !UP!  weight !W!  jitter !J!  mv !M!
goto loop
:cyclew
set /a WI=W+0
if %WI% GEQ 48 (set W=12) else (if %WI% GEQ 32 (set W=48) else (if %WI% GEQ 24 (set W=32) else (set W=24)))
goto :eof
:cyclej
set /a JI=J+1
if %JI% GEQ 4 set JI=0
set J=%JI%
goto :eof
:cyclem
set /a MI=M+1
if %MI% GEQ 4 set MI=0
set M=%MI%
goto :eof
:clear
del /q "%FILE%" 2>nul
echo   cleared: the ini decides again (upscaler = taau)
goto loop
:done
echo.
echo   bye.  (the game keeps: upscaler !UP!, weight !W!)
endlocal
pause
