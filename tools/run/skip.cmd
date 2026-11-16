@echo off
rem tools\run\skip.cmd - live draw switch for a RUNNING 3.0.1 game (same file as tools\run\ab.cmd).
rem
rem   tools\run\skip.cmd cc3eac68      skip the fragment shader whose hash starts with cc3eac68
rem   tools\run\skip.cmd #198          skip draw 198 of every frame (the numbers the F11 trace prints)
rem   tools\run\skip.cmd               everything drawn again
rem
rem Applied within 0.5 s. Useful fog candidates in 3.0.1:
rem   cc3eac68 (screen-space fog composite)   2649526f (froxel)   57bdd1a0    f9d7097a   6958e1f8
setlocal
set ROOT=%~dp0..\..
set FILE=%ROOT%\work\skip_fs.txt
if "%~1"=="" ( echo.> "%FILE%"& echo skip list cleared& exit /b 0 )
> "%FILE%" echo %~1
echo skipped: %~1   (work\skip_fs.txt, live in 0.5 s)
endlocal
