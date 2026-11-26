@echo off
rem tools\run\play60.cmd - 60 fps for the EARLY NS2 dev build (xc2\build\boot, game\xc2ns2), not the retail 3.0.1 build.
rem For retail 3.0.1 use: tools\run\play-301.cmd -60
rem
rem   [xc2] fps = 60 (the game's own step runs at 60, HANDOVER 55/56) + 60 Hz presents, base romfs, timestamped log.
rem Same as: tools\run\play-log.cmd -60
call "%~dp0play-log.cmd" -60 %*
