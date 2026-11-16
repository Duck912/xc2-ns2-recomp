# Xenoblade Chronicles 2 · Nintendo Switch 2 Edition — static recompilation (PC)

Ahead-of-time ("static") recompilation of the retail **Xenoblade Chronicles 2 – Nintendo Switch 2 Edition**
(title id `0100E95004038000`, game version **3.0.1**) running on Windows x86-64 through Vulkan.

The game's NSO modules are lifted to C++ by [nxrecomp](https://github.com/drakolordx7/nxrecomp) and linked against a small
Switch runtime ([third_party/fefw-recomp](third_party/fefw-recomp)) whose NVN implementation replays the
game's graphics API on Vulkan. Shaders are translated from Maxwell / Ampere SASS to SPIR-V by Ryujinx's
translator, driven by our offline harness.

> **This repository contains no game code and no game assets.**
> It is the toolchain, the runtime and the project's documentation. You need your own legally acquired copy
> of the game — see *What you must supply* below.

## Status (2026-11-16)

| | |
|---|---|
| Boot | ✔ reaches the title screen, loads a 2022 clear save, plays in the field |
| Frame rate | **59–60 fps** in the port and most areas (1080p, 1440p or 4K alike); **43–52 fps** in the open plain, the heaviest area; 1% low ≈ 51 |
| Graphics | NVN 3.5 replay on Vulkan; Maxwell shaders translated offline; Ampere (Switch 2) shaders translated from SASS |
| Upscaling | the game's DLSS/NDSR slot is served by the built-in **TAAU** by default; **FSR 4.1.2** and **FSR 3.1.6** are selectable at run time (`[dlss] upscaler = fsr3`) |
| Audio | Opus (software decoder) + `nn::audio` OutputStream on the host sink |
| Input | keyboard/mouse and gamepad |

### Known issues

* A blue-grey rim around characters and other objects where they meet the cloud sea. Measured to live inside
  the game's 640×360 volumetric-fog layer (the in-scatter ramp across the depth step); the platform-level
  suspects (depth filtering, shadow-map compare, texture gather rounding, upscalers) were each tested and
  excluded, so the fix has to be inside the game's own fog pass.
* Residual shimmer in the cloud sea in-game (the game dithers its volumetric fog at 640×360; the console leans
  on its neural upscaler).
* Slow frames on area transitions are dominated by texture uploads and guest/host lock waits.

## What you must supply

The recompiler needs the game's own files; they are never part of this repository and are never downloaded:

| what | where it goes (default) |
|---|---|
| ExeFS of the 3.0.1 program: `main`, `sdk`, `subsdk0`, `subsdk1`, `subsdk2`, `subsdk3`, `rtld`, `main.npdm` | `xc2/game/xc2ns301/` |
| the 3.0.1 romfs (`bf2.ard`, `bf2.arh`, `stream/`) | referenced by `NXRT_FS_ROMFS` at run time |
| add-on content (optional) | referenced by `NXRT_AOC_DIR` |

The built executable embeds the lifted game code, so **builds are not distributed**: build it locally from
your own dump (see `docs/BUILD.md`).

## How it works

```
ExeFS (NSO) ──nxrecomp lift──▶ C++ ──clang-cl──▶ main.lib ──┐
                                                            ├──▶ xc2_boot.exe
runtime (fefw-recomp: NVN/NVN2, hid, fs, audio, kernel) ────┘
        │
        └─ NVN calls ──▶ Vulkan replay ──▶ SPIR-V shaders (offline harness, Ryujinx translator)
```

The runtime is a general Switch/NVN service layer (not XC2-specific); everything game-specific lives in this
repository: the lift sites, the boot glue, the launcher, and the analysis tools.

## Build

See [docs/BUILD.md](docs/BUILD.md). In short: a Windows toolchain (MSVC + LLVM clang-cl, .NET 10 SDK,
Vulkan SDK, Python 3.12), then

```powershell
# once, after placing your 3.0.1 ExeFS in xc2\game\xc2ns301\
.\xc2\scripts\build.ps1 -Exefs xc2\game\xc2ns301 -Run:$false `
    -Modules 'main,sdk,subsdk0,subsdk1,subsdk2,subsdk3,rtld'
.\xc2\scripts\build-boot.ps1 -Exefs xc2\game\xc2ns301 -OutDir xc2\build\boot-301 `
    -LibDir xc2\build\lib -MainLib xc2\build\lib\main.lib -Defines XC2_MODULES_7
```

## Documentation

* [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — how the lift, the runtime and the shader pipeline fit together
* [docs/COMPATIBILITY.md](docs/COMPATIBILITY.md) — what runs, what does not, and the measured frame rate
* [docs/INVARIANTS.md](docs/INVARIANTS.md) — the three rules the project holds itself to
* [CONTRIBUTING.md](CONTRIBUTING.md) — reporting a problem, building, opening a pull request
* [CHANGELOG.md](CHANGELOG.md) — dated milestones
* `docs/reports/` — the lift and NVN service reports
* The §-numbered working notes (one file per round, with every experiment and dead end) are kept outside this
repository. Code comments and the reports refer to them as `HANDOVER N` or `§N`: those numbers are kept so the
code and the notes stay cross-referenced, but the notes themselves are not published.
* `docs/ENVIRONMENT.md` — toolchain, Python packages, build entries, data layout
* `tools/README.md` — the analysis and run tools

## Credits

* [nxrecomp](https://github.com/drakolordx7/nxrecomp) — the static recompiler used to lift the game
* [fefw-recomp](third_party/fefw-recomp) — the Switch runtime (NVN/NVN2 → Vulkan) this build links against
* Ryujinx (MIT) — the Maxwell shader translator used by the offline shader harness
* SDL3, Vulkan-Headers, VMA, and the other vendored dependencies (see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md))
* [AksharDP/xc2-recomp](https://github.com/AksharDP/xc2-recomp) and the [Lichii](https://github.com/zortos293/Lichii) PRs — read for reference findings, no code copied
* **DeepSeek V4.1 Flash** (build 1017) — pair-programmed this project with its author, from the first lift to this
  release: the runtime work, the replay optimisation, the documentation and the review rounds

## Licence

The project's own code is **GPL-3.0-or-later** — [LICENSE](LICENSE) carries the GPL-3.0 text and the "or later" is
this project's choice. Third-party components keep their own licences, listed in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and in `third_party/fefw-recomp/MODIFICATIONS.md`. **No licence
here grants any right to Nintendo's game.** The lifted code the build produces from your own dump is not covered by
this licence, is not distributed, and remains the property of its rights holders.

## Legal notice

This is an independent, non-commercial fan project. It is not affiliated with, sponsored by, or endorsed by
Nintendo. *Xenoblade Chronicles*, *Xenoblade Chronicles 2*, *Nintendo Switch* and *Nintendo Switch 2* are
trademarks of Nintendo; *Xenoblade Chronicles 2* was developed by MONOLITH SOFT. This repository contains no game
code, no game assets and no keys, and gives no help in obtaining them.

本项目是独立的非商业粉丝项目，与任天堂没有任何关联，也未获得任天堂的认可。《异度之刃 2》、Nintendo Switch
与 Nintendo Switch 2 是任天堂的商标；《异度之刃 2》由 MONOLITH SOFT 开发。仓库中不含任何游戏代码、游戏资源或密钥，
也不提供任何获取途径。

## 中文说明

本项目是《异度神剑 2 决定版（Nintendo Switch 2 Edition）》**3.0.1 零售版**的静态重编译（PC / Windows + Vulkan）：
把游戏的 NSO 模块整体举升成 C++，再链接一个通用 Switch 运行时（自己实现的 NVN → Vulkan 重放层）运行。

* **仓库里没有任何游戏代码、游戏资源或密钥**；需要你自己的游戏 dump（路径见上表），构建产物（含举升后的游戏代码）
  **不随仓库分发**，只能本地构建。
* 当前状态：能启动、读 2022 通关存档、进游戏；港口与多数区域 **59–60 fps**，大平原 43–52 fps，4K 输出几乎零成本。已知问题见 `docs/COMPATIBILITY.md`。
* 构建方法见 `docs/BUILD.md`；工具链见 `docs/ENVIRONMENT.md`；架构见 `docs/ARCHITECTURE.md`。
