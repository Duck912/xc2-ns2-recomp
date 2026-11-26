@echo off
rem tools\run\cap301.cmd - a capture run of the retail 3.0.1 route (play-301.cmd) that also traces one frame.
rem
rem   cap301.cmd <trace_sec> <snap_rt list> <press spec> [play-301 options]
rem
rem   trace_sec  [nvn] trace_sec: trace the first frame presented this many seconds after the first draw
rem   snap_rt    comma list of texture ids whose draws are snapshotted in the traced frame (empty = none)
rem   press      XC2_PRESS spec, e.g. "A@13,A@15,A@17" (seconds since the module start)
rem
rem The switches are set as the environment variables play-301.cmd reads, not through its own -snaprt
rem option: that option calls a label the script does not have (it fails with "cannot find the batch label").
rem ASCII only: cmd reads this file in the console code page.
setlocal
set ROOT=%~dp0..\..
set SEC=%~1
set SNAP=%~2
set PRESS=%~3
shift
shift
shift
set NXRT_NVN_TRACE_SEC=%SEC%
set NXRT_NVN_TRACE_SNAP_RT=%SNAP%
set XC2_PRESS=%PRESS%
call "%ROOT%\tools\run\play-301.cmd" %1 %2 %3 %4 %5
endlocal
