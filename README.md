# Xenoblade Chronicles 2 · Nintendo Switch 2 Edition — static recompilation for Windows

**English** · [中文](README.zh-CN.md)

Ahead-of-time ("static") recompilation of the **Switch 2 program of Xenoblade Chronicles 2 – Nintendo Switch 2
Edition**, running on Windows x86-64 through Vulkan. No emulator: the game's own modules are lifted to C++ and
linked against a small Switch runtime.

| | |
|---|---|
| application | `0100E95004038000` (the same title as the Switch 1 release; update 1114112) |
| what we recompile | **program 1**, `0400E95004038001` — SDK 21.4.4 ("Ounce"), NVN2 231.39, game version **3.0.1** |
| add-on content | `0100E95004039001` … `0100E95004039063` (8 packs, optional) |
| current release | **v0.2.0** (2026-11-22) |

> **This repository contains no game code and no game assets.** It is the toolchain, the runtime and the
> documentation. You need your own legally acquired copy of the game — see *What you must supply*.

> **Before reporting anything, update to 0.2.0 or newer** — earlier builds carry problems that are already fixed
> (the 720p internal render, the add-on `0/romfs` layout, the film hand-back, F1 not opening the settings page).

## Status (v0.2.0)

| | |
|---|---|
| Boot | reaches the title screen, loads an existing save, plays the field and the cutscenes |
| Frame rate | 60 fps target; the 3D render is dynamic (960×540 → 1440p/4K output). Measured on an RX 6800 XT: 59–60 fps in most areas, 43–52 in the heaviest open areas |
| Graphics | NVN 3.5 / NVN2 replay on Vulkan; Maxwell and Ampere SASS translated to SPIR-V offline |
| Upscaling | built-in TAAU by default; FSR 3.1.6, FSR 4.1.2 and DLSS selectable, plus native-resolution presets (1080p / 1440p / 4K) in the F1 page |
| Movies | 4K AV1 (3840×2160) hardware decode through FFmpeg's Vulkan Video path (D3D11VA fallback, NVDEC and dav1d behind it); a film that plays *over* a live cutscene hands the scene back in ~0.2 s |
| Audio | Opus (software) + `nn::audio` on a host XAudio2 sink; the film's track is a placeholder clock |
| Input | keyboard/mouse and gamepad, Switch button positions (`[pad] label_abxy = 1` for letters) |
| Languages | all 11 text languages the retail 3.0.1 title lists, selectable in the launcher; voices are Japanese and English |
| Settings | F1 in game (display, quality, audio, pad, keys), launcher for everything that has to be set before a launch |

Tested on a **Radeon RX 6800 XT (16 GB)** and an **RTX 4060 Laptop (8 GB)**, Windows 11.

### Known issues

* **Blinking and dialogue flicker** ([#15](https://github.com/weile10000/xc2-ns2-recomp/issues/15)): the eyes and mouth
  jump for a frame. Not the upscaler, the jitter or the temporal history — the cause is unknown.
* **A red edge** on a cloud-sea silhouette in the opening battle background. One scene, cosmetic.
* **Add-on content scenes are the heaviest** in the title; 4K openings included.
* **First launch compiles pipelines** — about 20 seconds with no frame, once per driver.
* **Ultrawide is not supported** ([#22](https://github.com/weile10000/xc2-ns2-recomp/issues/22)): the render path is
  fine at 21:9, the game's own aspect handling and UI are not.
* **8 GB NVIDIA cards**: the mirror capture (the fix for the flicker and the cloud-sea rim) is off by default because
  its whole-pool copies need about 3.5 GiB; the log says so with a `W` line. `[nvn] mirror_capture = 1` forces it.

## Quick start (the release package)

The release is self-contained: no MSVC, no Python, no .NET, no Zig.

1. Unzip the release package anywhere.
2. Run `xc2-launcher.exe`, point **Set up** at your dump (a `.nup`, or a folder with `exefs/` and `romfs/`), and let it
   run — 8–15 minutes: it lifts the 537 translation units, links them, translates ~12,150 shaders and collects the few
   that exist in no file.
3. **Play**. The first launch after that compiles GPU pipelines for about 20 seconds, once per driver.

Add-on content is picked up from the dump (both `<id>/romfs` and `<id>/0/romfs` layouts). Saves land in `save/` next to
the launcher; settings in `nxrt.ini` (runtime) and `controls.ini` (keys, opened by F1).

**In game:** F1 — settings page · F10 — FPS counter · F11 / Alt+Enter — fullscreen.

## What you must supply

| what | where it goes |
|---|---|
| your own dump of the 3.0.1 program — a `.nup` package, or the exefs + romfs | picked in the launcher's **Set up** |
| add-on content (optional) | discovered from the same dump |
| `upscalers/…` DLLs (optional) | FidelityFX / Streamline files for FSR or DLSS; TAAU needs nothing |

Builds are never distributed: the executable embeds the game's lifted code, so it is built on your machine from your
own dump.

## Reporting a problem

Use the launcher: **Play → Record a report** (or **About → Record a report**). It starts the game once more with the
diagnostics on and writes `work\reports\report-<stamp>.zip` when you close the window; attach that zip to the issue.
It holds the log, your settings and the driver's capability lines, and no game data.

## Build from source

Requirements: Windows 10/11 x64, a Vulkan 1.3 GPU, 16 GB of RAM (the runtime's footprint is ~10.5 GB), ~60 GB of free
disk for the source path, and the toolchain (VS Build Tools, LLVM/clang-cl, CMake + Ninja, .NET 10 SDK, Vulkan SDK,
Python 3.12, PowerShell 7). See [docs/BUILD.md](docs/BUILD.md) and [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md).

```powershell
# once, after placing the 3.0.1 exefs in xc2\game\xc2ns301\
.\tools\build\build.ps1 -Exefs xc2\game\xc2ns301 -Run:$false `
    -Modules 'main,sdk,subsdk0,subsdk1,subsdk2,subsdk3,rtld' `
    -LiftDir xc2\build\301\lift -ObjDir xc2\build\301\obj -LibDir xc2\build\301\lib
.\tools\build\build-boot.ps1 -Exefs xc2\game\xc2ns301 -OutDir xc2\build\301\boot `
    -LibDir xc2\build\301\lib -MainLib xc2\build\301\lib\main.lib -Defines XC2_MODULES_7
```

## How it works

```
ExeFS (NSO) ──nxrecomp lift──▶ C++ ──clang-cl──▶ main.lib ──┐
                                                            ├──▶ xc2_boot.exe
runtime (fefw-recomp: NVN/NVN2, hid, fs, audio, kernel) ────┘
        │
        └─ NVN calls ──▶ Vulkan replay ──▶ SPIR-V (offline harness, Ryujinx translator)
```

The runtime is a general Switch/NVN service layer; everything game-specific lives here: the lift sites, the boot
glue, the launcher, the film path and the analysis tools.

## Repository layout

| path | what |
|---|---|
| `xc2/` | the game's side: lift sites, boot glue, the `xc2_boot` stub |
| `launcher/` | the Windows launcher (Tauri + a plain JS front end) |
| `third_party/fefw-recomp/` | the runtime fork; every change is listed in its `MODIFICATIONS.md` |
| `tools/` | build, run, CI and analysis tools |
| `config/` | the settings schema (`keys.tsv`) and the install template |
| `docs/` | the public documentation |

## Documentation

* [docs/QUICKSTART.md](docs/QUICKSTART.md) — from a clean clone to the title screen
* [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — how the lift, the runtime and the shader pipeline fit together
* [docs/MEDIA.md](docs/MEDIA.md) — the film path: the codec protocol, the audio clock, inserted films
* [docs/SETTINGS.md](docs/SETTINGS.md) — the two settings files, who maintains what, how to add an option
* [docs/COMPATIBILITY.md](docs/COMPATIBILITY.md) — what runs, what does not, measured frame rates
* [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) — symptom first: black screen, driver crashes, wrong frame rate
* [docs/INVARIANTS.md](docs/INVARIANTS.md) — the rules the project holds itself to
* [docs/MODS.md](docs/MODS.md) — the mod interface (draft): folder layout, order, conflicts, code patches
* [CONTRIBUTING.md](CONTRIBUTING.md) · [CHANGELOG.md](CHANGELOG.md)

## Credits

* [nxrecomp](https://github.com/drakolordx7/nxrecomp) — the static recompiler that lifts the game
* **[Goldoire/fefw-recomp](https://github.com/Goldoire/fefw-recomp)** — the Switch runtime this project is built on:
  NVN/NVN2 replay, the service HLE, the shader pipeline and the exe + DLL packaging all started there
* Ryujinx (MIT) — the Maxwell shader translator behind the offline harness
* SDL3, Vulkan-Headers, VMA and the other vendored dependencies ([THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md))
* [AksharDP/xc2-recomp](https://github.com/AksharDP/xc2-recomp) and the [Lichii](https://github.com/zortos293/Lichii)
  PRs — read for reference finding
* **[@capibawa](https://github.com/capibawa)** — [nxnative, branch `xc2-ns2-profile`](https://github.com/capibawa/nxnative/tree/xc2-ns2-profile):
  the launch switches and the host-side movie/audio takeover this project's film path follows
* **Everyone who sent a pull request** — credited by name in the release notes of the version their work landed
  in ([releases](https://github.com/weile10000/xc2-ns2-recomp/releases)). The list here stays short on purpose:
  this page should not grow one line per contribution.
* **DeepSeek V4.1 Flash** — pair-programmed this project with its author, from the first lift to this release

## Licence

The project's own code is **GPL-3.0-or-later** ([LICENSE](LICENSE)). Third-party components keep their own licences
([THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), `third_party/fefw-recomp/MODIFICATIONS.md`). **No licence here
grants any right to Nintendo's game.** The lifted code a build produces from your own dump is not covered by this
licence, is not distributed, and remains the property of its rights holders.

## Legal notice

This is an independent, non-commercial fan project. It is not affiliated with, sponsored by, or endorsed by Nintendo.
*Xenoblade Chronicles*, *Xenoblade Chronicles 2*, *Nintendo Switch* and *Nintendo Switch 2* are trademarks of Nintendo;
*Xenoblade Chronicles 2* was developed by MONOLITH SOFT. This repository contains no game code, no game assets and no
keys, and gives no help in obtaining them.


