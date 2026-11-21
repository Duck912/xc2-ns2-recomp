Xenoblade Chronicles 2 - Switch 2 Edition (3.0.1), static recompilation for Windows
==============================================================================

Release 0.1.4 - what changed in this version is in RELEASE-NOTES.md next to this
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
  engine/                     the setup engine (xc2_setup.py) and the shader chain
  tools/python                Python with the lifter inside (nothing to install)
  tools/build/zig             the cross compiler that builds the game
  tools/spirv_harness         translates the game's shaders (self-contained)
  tools/spirv-val             validates every translated shader
  tools/shader-cache          archive scan and cache builder
  licenses/                   our licence and every third-party one, per tool

What is new in 0.1.4
--------------------
  The film decoders run on the GPU: FFmpeg + D3D11VA ships in runtime/ and the 4K
  AV1 openings play at 30 fps where the CPU managed 8-17. A GPU without a hardware
  AV1 decoder falls back to the CPU decoders by itself.

  HDR is off by default: the film overlay has no HDR10 encode yet, so cutscenes
  came out green on an HDR display. Settings -> Video turns it back on.

  A pad answers the Switch positions - B bottom, A right, Y left, X top, where
  the game draws its Arts. Settings -> Pad switches to the letters instead.

  Cutscene sound has its own XAudio2 voice now, so CGs have sound and lip sync.

  A folder that was already set up keeps its xc2_boot.exe, and Set up copies the
  runtime DLLs beside it anyway: upgrading over an older install used to leave the
  film decoders out, and the game then failed to start (0xC0000135).
  See RELEASE-NOTES.md for the full list.

The other file on the release page
----------------------------------
  XC2-package-dist-0.1.4.zip  THIS: what you download to play
  xc2-launcher-0.1.4-src.zip  the launcher's C++/Rust/JS source, for people who
                              want to read or build the launcher. You do NOT need
                              it to play.

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
