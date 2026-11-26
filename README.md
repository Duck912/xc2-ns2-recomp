# xcde-ns2-recomp

A native Windows PC port of **Xenoblade Chronicles: Definitive Edition – Nintendo Switch 2 Edition**, made by
static recompilation: the game's ARM64 code is translated to C++ and compiled into a regular Windows program,
which runs on a small runtime standing in for the console's system software. The picture is drawn by n2den's
**NVN-HLE** (the game's NVN graphics calls replayed on Vulkan), built as a library. It is not an emulator.

> **No game files are included here.** You need your own legally dumped copy of the game, including its add-on
> (the Switch 2 Edition upgrade pack). Everything that reads the game happens on your PC, and nothing is written
> into your dump. Not affiliated with or endorsed by Nintendo or Monolith Soft.

## Status

The game plays from the title screen into the story at 60 fps.

| | |
|---|---|
| Picture | NVN-HLE on Vulkan; the game's own DLSS runs on real NVIDIA DLSS (FSR 1 without Streamline or on other GPUs) |
| Movies | the opening and story movies play (the game's own player, decoded on the PC) |
| Sound | yes |
| Saves | yes, in the run folder (`work/save-xcde`) |
| Window | windowed, borderless fullscreen (F11), any size; the picture follows the window |
| Overlay | F1 settings menu (English or Chinese), F10 frame-rate counter, F12 screenshots (PNG, no overlay in them) |
| Settings | upscaler (the game's DLSS, DLSS for every upscaler, FSR 1, off), DLSS model, window scaler, VSync |

Testing so far has been narrow, so expect rough edges (AMD and Intel GPUs are untried); see
[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) and open an issue with the log (`work/logs`).

## What you need

- **Windows 10 or 11, x64**, and a GPU with Vulkan 1.3. DLSS needs an NVIDIA RTX GPU.
- **Your dump** of XC:DE Switch 2 Edition 2.0.0: the Switch 2 program, the game data (program 0) and the add-on
  `0100FF500E34B001`. One `.nup` holding all three works, or three folders (ExeFS, RomFS, add-on RomFS).
- **The build tools** (the game is compiled on your PC):

| tool | version | used for |
|---|---|---|
| Visual Studio Build Tools (MSVC + Windows SDK) | 2022+ | headers and import libraries for clang-cl |
| LLVM | 22+ | `clang-cl`, `llvm-lib` |
| CMake + Ninja | 3.25+ | the runtime |
| Python | 3.12 with `lz4`, `capstone`, `zstandard` | the recompiler and the dump reader |
| PowerShell | 7+ (`pwsh`) | the build scripts |

Either put them on `PATH`, or set `XC2_ENV` to a PowerShell script that does ([docs/BUILD.md](docs/BUILD.md)).
The .NET and Vulkan SDKs that the XC2 build lists are not needed: NVN-HLE translates shaders itself.

## Set up and play

**With the launcher** (`launcher/`, build it with `npm install` then `npm run tauri build -- --no-bundle`):
pick your dump, press **Set up**, then **Play**. Download Streamline from the launcher's Settings first if you
want DLSS. Setup takes a while the first time (it compiles the whole game) and continues where it stopped.

**From a terminal:**

```powershell
python tools\setup\xcde_setup.py --repo . --install work\play --nup "D:\dumps\XC DE.nup"
tools\run\play-xcde.cmd
```

The setup steps, each skipped once done: check the machine, fetch the recompiler, get the NVN-HLE library, build
the runtime, read the game files, recompile the game, link it, copy Streamline, finish
([docs/RELEASE-PLAN.md](docs/RELEASE-PLAN.md)). With folders instead of a `.nup`: `--exefs <dir> --romfs <dir>
--dlc <dir>`.

**Keys:** F1 menu · F10 frame-rate counter · F11 fullscreen · F12 screenshot (`xcde/build/200/boot-n2den/shots_manual`).
A gamepad works out of the box; keyboard and mouse bindings are on the menu's Controls page.

## Repository layout

This repository started as an import of [xc2-ns2-recomp](https://github.com/weile10000/xc2-ns2-recomp) with its
full history; XC:DE S2E shares its `sdk`, `subsdk0-3` and `rtld` byte for byte ([docs/TARGET.md](docs/TARGET.md)).

| | |
|---|---|
| `xcde/` | XC:DE's game folder, hook site lists and supported build |
| `xc2/src/xc2_boot.cpp` | the boot program (`--game xcde`, `--nvn n2den`) |
| `third_party/fefw-recomp/` | the runtime (system services, input, audio, movies, the overlay, the NVN-HLE adapter) |
| `tools/setup/xcde_setup.py` | the setup engine (the launcher runs it) |
| `config/profiles/xcde.ini` | the run profile `play-xcde.cmd` uses |
| `launcher/` | the Tauri launcher |

The NVN-HLE library comes prebuilt from its own release (source: n2den, `src/nvnhle`); set `XCDE_NVNHLE_DIST`
to use one you built. The XC2 project's own README is kept as [README.xc2.md](README.xc2.md).

## Credits

- [xc2-ns2-recomp](https://github.com/weile10000/xc2-ns2-recomp) (weile10000 and contributors): the base this
  port is built on, including the settings menu and the launcher.
- [fefw-recomp](https://github.com/Goldoire/fefw-recomp) and nxrecomp: the runtime and the recompiler.
- n2den and the Eglantine Community: NVN-HLE, the renderer.
- Ryujinx, nxnative and everyone those projects credit; see [README.xc2.md](README.xc2.md) and
  [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

License: GPL-3.0-or-later (matching the projects it builds on).
