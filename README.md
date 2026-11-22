<a id="english"></a>

# Xenoblade Chronicles 2 · Nintendo Switch 2 Edition — static recompilation for Windows

**English** · [中文](#中文)

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

---

<a id="中文"></a>

# 异度之刃 2 · Nintendo Switch 2 Edition —— Windows 静态重编译

[English](#english) · **中文**

把《异度之刃 2 – Nintendo Switch 2 Edition》的 **Switch 2 程序**做提前（静态）重编译，在 Windows x86-64 上通过
Vulkan 运行。不是模拟器：游戏自己的模块被举升成 C++，再链接一个很小的 Switch 运行时。

| | |
|---|---|
| application | `0100E95004038000`（与 NS1 版是同一个 title；update 1114112） |
| **我们重编译的** | **program 1**，`0400E95004038001` —— SDK 21.4.4（"Ounce"）、NVN2 231.39、游戏版本 **3.0.1** |
| 附加内容 | `0100E95004039001` … `0100E95004039063`（8 个包，可选） |
| 当前版本 | **v0.2.0**（2026-11-22） |

> **仓库里没有任何游戏代码、资源或密钥。** 这里只有工具链、运行时和文档。你需要自己合法获得的游戏副本——
> 见下面「你需要自备什么」。

> **报 issue 前请先确认版本是 0.2.0 或更新**——更早的版本里有已经修掉的问题（内部 720p 渲染、附加内容的
> `0/romfs` 布局、影片交还、F1 打不开设置页）。

## 状态（v0.2.0）

| | |
|---|---|
| 启动 | 能到标题界面、读既有存档、进野外与过场 |
| 帧率 | 目标 60 fps；3D 渲染是动态分辨率（960×540 → 1440p/4K 输出）。RX 6800 XT 实测：多数区域 59–60 fps，最重的开放区域 43–52 |
| 图形 | NVN 3.5 / NVN2 在 Vulkan 上重放；Maxwell 与 Ampere 的 SASS 离线翻译成 SPIR-V |
| 升采样 | 默认内建 TAAU；可选 FSR 3.1.6、FSR 4.1.2、DLSS，F1 页里还有原生分辨率档位（1080p / 1440p / 4K） |
| 影片 | 4K AV1（3840×2160）硬解，走 FFmpeg 的 Vulkan Video 路径（D3D11VA 兜底，其后还有 NVDEC 与 dav1d）；**叠在实时过场之上的影片播完约 0.2 秒交还场景** |
| 音频 | Opus（软件解码）+ `nn::audio` 输出到宿主 XAudio2；影片音轨是占位时钟 |
| 输入 | 键盘鼠标与手柄，手柄按 Switch 的位置映射（要字母用 `[pad] label_abxy = 1`） |
| 语言 | 零售 3.0.1 支持的全部 11 种文本语言，在启动器里选；语音为日语和英语 |
| 设置 | 游戏内 F1（显示、画质、音频、手柄、按键）；启动器管所有必须启动前定的项 |

在 **Radeon RX 6800 XT（16 GB）** 与 **RTX 4060 Laptop（8 GB）** 上测过，Windows 11。

### 已知问题

* **眨眼与对白闪烁**（[#15](https://github.com/weile10000/xc2-ns2-recomp/issues/15)）：眼睛和嘴会跳一帧。已排除
  超分、jitter 与时间历史，原因未知。
* **开场战斗背景的云海有一条红边**。单个场景，纯视觉。
* **附加内容场景是全作最重的**，其 4K 开场尤其。
* **首次启动编译管线** —— 约 20 秒无画面，每个驱动一次。
* **不支持超宽屏**（[#22](https://github.com/weile10000/xc2-ns2-recomp/issues/22)）：渲染路径本身支持 21:9，
  是游戏自己的宽高比处理与 UI 不支持。
* **8 GB 的 N 卡**：mirror capture（闪烁与云海边界的修复）默认关闭，因为它的整池拷贝需要约 3.5 GiB；日志里会有一行
  `W` 说明。设 `[nvn] mirror_capture = 1` 可强制开启。

## 快速开始（发布包）

发布包是自包含的：不需要 MSVC、Python、.NET 或 Zig。

1. 把发布包解压到任意目录。
2. 运行 `xc2-launcher.exe`，在 **Set up** 里指向你的 dump（一个 `.nup`，或含 `exefs/` 与 `romfs/` 的目录），
   让它跑完——8–15 分钟：举升 537 个翻译单元、链接、翻译约 12,150 个着色器，并补上文件里没有的那几个。
3. **Play**。这之后再首次启动会编译 GPU 管线，约 20 秒，每个驱动一次。

附加内容从 dump 自动识别（`<id>/romfs` 与 `<id>/0/romfs` 两种布局都认）。存档落在启动器旁边的 `save/`；
设置分两处：`nxrt.ini`（运行时）与 `controls.ini`（按键，F1 页会改它）。

**游戏内：** F1 —— 设置页 · F10 —— 帧率计数器 · F11 / Alt+Enter —— 全屏。

## 你需要自备什么

| 需要 | 放在哪 |
|---|---|
| 你自己的 3.0.1 程序 dump —— 一个 `.nup` 包，或 exefs + romfs | 启动器 **Set up** 里选择 |
| 附加内容（可选） | 从同一个 dump 自动发现 |
| `upscalers/…` 下的 DLL（可选） | FSR / DLSS 需要的 FidelityFX / Streamline 文件；TAAU 不需要任何东西 |

构建产物从不分发：可执行文件里嵌着举升后的游戏代码，所以它必须在你的机器上、从你的 dump 现场编出来。

## 出问题时

用启动器：**Play → 录一份报告**（或 **About → 录一份报告**）。它会用诊断模式再跑一次游戏，关掉窗口时把日志、
设置、驱动能力行打包成 `work\reports\report-<时间>.zip`；把这个 zip 附到 issue 里即可。里面没有游戏数据。

## 从源码构建

要求：Windows 10/11 x64、Vulkan 1.3 显卡、16 GB 内存（运行时占用约 10.5 GB）、源码路线需要约 60 GB 空闲磁盘，
以及整套工具链（VS Build Tools、LLVM/clang-cl、CMake + Ninja、.NET 10 SDK、Vulkan SDK、Python 3.12、
PowerShell 7）。详见 [docs/BUILD.md](docs/BUILD.md) 与 [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md)。

```powershell
# 先把 3.0.1 的 exefs 放进 xc2\game\xc2ns301\
.\tools\build\build.ps1 -Exefs xc2\game\xc2ns301 -Run:$false `
    -Modules 'main,sdk,subsdk0,subsdk1,subsdk2,subsdk3,rtld' `
    -LiftDir xc2\build\301\lift -ObjDir xc2\build\301\obj -LibDir xc2\build\301\lib
.\tools\build\build-boot.ps1 -Exefs xc2\game\xc2ns301 -OutDir xc2\build\301\boot `
    -LibDir xc2\build\301\lib -MainLib xc2\build\301\lib\main.lib -Defines XC2_MODULES_7
```

## 工作原理

```
ExeFS (NSO) ──nxrecomp 举升──▶ C++ ──clang-cl──▶ main.lib ──┐
                                                             ├──▶ xc2_boot.exe
运行时（fefw-recomp：NVN/NVN2、hid、fs、audio、kernel）──────┘
        │
        └─ NVN 调用 ──▶ Vulkan 重放 ──▶ SPIR-V（离线 harness，Ryujinx 翻译器）
```

运行时是通用的 Switch/NVN 服务层；所有与这个游戏相关的都在本仓库：举升点、启动胶水、启动器、影片路径与
分析工具。

## 仓库结构

| 路径 | 内容 |
|---|---|
| `xc2/` | 游戏这一侧：举升点、启动胶水、`xc2_boot` 桩 |
| `launcher/` | Windows 启动器（Tauri + 纯 JS 前端） |
| `third_party/fefw-recomp/` | 运行时分支；每处改动都记在它的 `MODIFICATIONS.md` |
| `tools/` | 构建、运行、CI 与分析工具 |
| `config/` | 设置表（`keys.tsv`）与安装模板 |
| `docs/` | 公开文档 |

## 文档

* [docs/QUICKSTART.md](docs/QUICKSTART.md) —— 从干净 clone 到标题界面
* [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) —— 举升、运行时、着色器管线如何拼在一起
* [docs/MEDIA.md](docs/MEDIA.md) —— 影片路径：codec 协议、音频时钟、插入式影片
* [docs/SETTINGS.md](docs/SETTINGS.md) —— 两套设置文件、各自归属、如何加一个设置项
* [docs/COMPATIBILITY.md](docs/COMPATIBILITY.md) —— 什么能跑、什么不能、实测帧率
* [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) —— 按症状查：黑屏、驱动崩溃、帧率不对
* [docs/INVARIANTS.md](docs/INVARIANTS.md) —— 项目自我约束的规则
* [docs/MODS.md](docs/MODS.md) —— MOD 接口（草稿）：目录布局、顺序、冲突、代码补丁
* [CONTRIBUTING.md](CONTRIBUTING.md) · [CHANGELOG.md](CHANGELOG.md)

## 致谢

* [nxrecomp](https://github.com/drakolordx7/nxrecomp) —— 把游戏举升成 C++ 的静态重编译器
* **[Goldoire/fefw-recomp](https://github.com/Goldoire/fefw-recomp)** —— 本项目所基于的 Switch 运行时：NVN/NVN2
  重放、服务层 HLE、着色器管线、exe + DLL 的打包形态都源自那里
* Ryujinx（MIT）—— 离线 harness 背后的 Maxwell 着色器翻译器
* SDL3、Vulkan-Headers、VMA 等 vendored 依赖（[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)）
* [AksharDP/xc2-recomp](https://github.com/AksharDP/xc2-recomp) 与 [Lichii](https://github.com/zortos293/Lichii)
  的 PR —— 作为找地址的参考
* **[@capibawa](https://github.com/capibawa)** —— [nxnative 的 `xc2-ns2-profile` 分支](https://github.com/capibawa/nxnative/tree/xc2-ns2-profile)：
  本项目的启动开关与影片/音频的宿主接管思路来自那里
* **每一位提交过 PR 的人** —— 以 PR 链接署名在其改动落地的那一版发布说明里
  （[releases](https://github.com/weile10000/xc2-ns2-recomp/releases)）。这里的列表刻意保持简短：这一页不应该
  每来一个贡献就多一行
* **DeepSeek V4.1 Flash** —— 与作者结对完成本项目，从第一次举升到这一版

## 许可

项目自身代码为 **GPL-3.0-or-later**（[LICENSE](LICENSE)）。第三方组件各自保留其许可
（[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)、`third_party/fefw-recomp/MODIFICATIONS.md`）。**这里的任何
许可都不授予任天堂游戏的任何权利。** 从你自己的 dump 构建出的举升代码不在此许可范围内、不分发，其权利仍归
权利方。

## 法律声明

本项目是独立的非商业粉丝项目，与任天堂没有任何关联，也未获得任天堂的赞助或认可。《异度之刃 2》、Nintendo Switch
与 Nintendo Switch 2 是任天堂的商标；《异度之刃 2》由 MONOLITH SOFT 开发。仓库中不含任何游戏代码、游戏资源或
密钥，也不提供任何获取途径。
