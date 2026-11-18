Xenoblade Chronicles 2 - Switch 2 Edition (3.0.1), static recompilation for Windows
==============================================================================

Release 0.1.2 - what changed in this version is in RELEASE-NOTES.md next to this
file (English and Chinese).

This folder is the *player package*. It contains no game files: the executable is
built on your machine from your own dump, and the shaders are translated from it.

Start here
----------
1. Run  xc2-launcher.exe
2. "Game files": pick the folder that holds exefs/ and romfs/, or press .nup and
   pick a package you made; then press "Use these game files".
3. Press "Set up". It takes 8-15 minutes (537 translation units, then about
   12,150 shader programs). The step list and the log move the whole time; it is
   not hung.
4. Press "Play".

What is in here
---------------
  xc2-launcher.exe            the launcher: game files, set up, play, settings
  xc2_boot.exe                built by Set up (the recompiled game)
  runtime/xc2_rt.dll          the recompiler runtime (NVN/NVN2 -> Vulkan)
  engine/                     the setup engine (xi2_setup.py) and the shader chain
  tools/python                Python with the lifter inside (nothing to install)
  tools/build/zig             the cross compiler that builds the game
  tools/spirv_harness         translates the game's shaders (self-contained)
  tools/spirv-val             validates every translated shader
  tools/shader-cache          archive scan and cache builder
  licenses/                   our licence and every third-party one, per tool

What is new in 0.1.2
--------------------
  4K cutscenes play: the Golden Country opening and the other 4K films used to
  freeze at 1.3 s with the sound continuing; they now run at 30 fps with lip
  sync. The retail build's BGM, effects and voices come out through a new host
  output path. See RELEASE-NOTES.md for the full list.

The other file on the release page
----------------------------------
  XC2-package-dist.zip        THIS: what you download to play
  xc2-launcher-0.1.1-src.zip  the launcher's C++/Rust/JS source, for people who
                              want to read or build the launcher (unchanged in
                              0.1.2). You do NOT need it to play.

If something goes wrong
-----------------------
Run this and attach the zip it prints to the issue:

  tools\python\python.exe tools\report.py

It starts the game once with the diagnostics on, then packs the log, the
validation output and your settings into work\reports\report-<stamp>.zip.
No PowerShell 7, no .NET: the Python in this folder runs it.

Saves, logs, cache
------------------
  save/                       your save data
  shader_cache/               translated shaders (rebuilt from your dump)
  work/logs/                  play logs, one per session
  nxrt.log                    the runtime log of the last session
  setup.log                   the log of the last Set up
