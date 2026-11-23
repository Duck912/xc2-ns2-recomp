# XC2 NS2 Recomp v0.2.1 — Quality Presets, Official DLSS/FSR Downloaders & 8 GB VRAM Support

This maintenance & community-PR update integrates **PR #30** (@UrsineBear) and **PR #36** (@nikolaybutnik) together with targeted startup, VRAM, and UI fixes. Unzip over your existing `0.2.0` install; saves, settings, and your shader cache are preserved.

## Which file do I download?

| file | what it is | do I need it? |
|---|---|---|
| `XC2-package-dist-0.2.1.zip` | player package: launcher, runtime, lifter and shader tools | **yes** — play from this one |
| `xc2-launcher-0.2.1-src.zip` | launcher source code | no |

## What's new

### Configurable render quality, output resolution & DLSS support (PR #36, @nikolaybutnik)

- **Display vs Graphics split in the F1 menu**: **Display** now selects the **Output resolution** (`1080p` / `1440p` / `4K`, `[am] resolution`) and windowed size (default `auto`, following your display up to 1440p); **Graphics** puts **Upscaler** (`DLSS`, `FSR 3.1.6`, `FSR 4.1.2`, `FSR 2.3.4`, `TAAU`, `Off`), **Mode / Render Quality** (`DLAA` / `Native AA` through `Ultra Performance` and `Console`), the live render -> output readout, and **DLSS Model** (`Default`, `K`, `J`) in one group.
- **Intent-based scaling (`[upscale] render_quality`, `[gfx] output_scale`)**: scene scales are computed at start-up from `[am] resolution`, and `[nvn] acquire_wait = auto` skips redundant acquire waits while `mirror_capture` is active.
- **Event Theater fix**: removed `AmericanEnglish` and `LatinAmericanSpanish` from `NXRT_TITLE_SUPPORTED_LANGUAGES` in setup / boot configuration.

### Optional official NVIDIA DLSS & AMD FSR downloaders in Launcher

- **Settings → Upscaler** lets players optionally download official prebuilt files directly onto their PC from **NVIDIA Streamline (`v2.14.16`)** (PR #36) or **AMD GPUOpen FidelityFX SDK (`v2.4.0` + `v1.1.4`)** into `upscalers/streamline/` or `upscalers/fsr3/`.
- Every download verifies exact byte size and SHA-256, places the upstream licence texts alongside the DLLs, and requires **explicit user confirmation of the upstream licence terms** beforehand. Neither this repository nor the release zip ships proprietary vendor DLLs.

### 8 GB VRAM support, live VRAM telemetry & menu ergonomics

- **Lower `mirror_capture = auto` floor (`3584 -> 1536 MiB`)**: 8 GB GPUs now enable frame pipelining automatically instead of falling back off.
- **Live VRAM visibility**: enabled `VK_EXT_memory_budget` when supported, added a `vram:` summary line to `nxrt.log` every 60 seconds, and surfaced live VRAM / pool-copy usage inside the F1 status card. Also added `[nvn] mirror_capture` (`auto` / `on` / `off`) to the F1 Experimental section.
- **F1 menu navigation & safe exit**: opening F1 or switching tabs focuses the first option card with clean D-pad Left/Right ownership ([#18](https://github.com/weile10000/xc2-ns2-recomp/issues/18)); the top-right **Quit game** button opens a confirmation dialog to avoid accidental exits.

### Renderer optimizations, audio fix & startup reliability (PR #30, @UrsineBear + fixes)

- **Audio crackling / static fix since v0.1.2 ([#37](https://github.com/weile10000/xc2-ns2-recomp/issues/37))**: fixed `xc2/src/x2_audio301.cpp` creating `nn::audio::OutputStream`'s release `SystemEvent` as `ManualClear` (`0`) instead of `EventClearMode_AutoClear` (`1`), and synced `watch_loop`'s queued water mark on writes — stopping the `guest-132` audio thread from busy-spinning on `GetOutputStreamFreeFrameCount` / `XAudio2Sink::GetState()` and eliminating audio lock contention / static crackling.
- Added `VK_AMD_shader_early_and_late_fragment_tests` (`early_fragment_tests = auto`), zero-copy colour feedback via `VK_EXT_attachment_feedback_loop_layout` (`[nvn] fb_reuse`), fixed a use-after-free in `nvn_pipeline.cpp`, tuned `nvn-texprep` priority, and auto-hid idle cursor in fullscreen/borderless modes.
- **Startup & DLC path fixes**: `mem::alias_base()` probes a free 128 GiB host region when `0x2000000000` is occupied (`VammManager` `0xD401`, [#33](https://github.com/weile10000/xc2-ns2-recomp/issues/33)); `aoc_indices()` uses UTF-8 paths for non-ASCII DLC folders on Windows ([#25](https://github.com/weile10000/xc2-ns2-recomp/issues/25)).
- **CI hygiene**: removed a hardcoded user path from `tools/run/route.ps1` and scoped PR personal-path checks to changed files.

## Upgrading from v0.2.0

Unzip over your existing folder — saves, `nxrt.ini`, `controls.ini`, and `shader_cache/` are preserved without re-running Set up. Make sure `xc2-launcher.exe` and `runtime/xc2_rt.dll` come from the same package.

## Known issues

- **Blinking / dialogue flicker** ([#15](https://github.com/weile10000/xc2-ns2-recomp/issues/15)): remains open. Opt-in `[nvn] view_reinterpret = 1` was tested and confirmed not to fix it (kept `0` by default).
- **Add-on scenes & first-run pipeline compile**: Torna / add-on scenes remain heavier than base game areas; first launch compiles Vulkan pipelines (~20 s pause).
- **Red edge** on the cloud sea silhouette in the opening battle background (cosmetic, single scene).

## Credits

Pull requests: [#30](https://github.com/weile10000/xc2-ns2-recomp/pull/30) (**@UrsineBear**), [#36](https://github.com/weile10000/xc2-ns2-recomp/pull/36) (**@nikolaybutnik**).
Issue reports that shaped this release: **@gao950912** ([#37](https://github.com/weile10000/xc2-ns2-recomp/issues/37) bisect + report).
Upstream: **fefw-recomp**, **nxrecomp**, **nxnative**, AMD **FidelityFX**, NVIDIA **Streamline**, **dav1d**, **SDL3**, **Dear ImGui**, **libvpx**, **libvorbis**, **FFmpeg**. Licences in `licenses/` and `THIRD_PARTY_NOTICES.md`.

---

# XC2 NS2 重编译 v0.2.1 —— 渲染质量预设、官方 DLSS/FSR 下载器与 8 GB 显存适配

本次更新整合了社区 **PR #30**（@UrsineBear）与 **PR #36**（@nikolaybutnik），并合入启动 `0xD401` 规避、非 ASCII DLC 路径修复、8 GB 显存适配以及 F1 交互优化。**从 v0.2.0 覆盖解压即可**，存档、配置与着色器缓存全部保留。

## 我该下哪个文件？

| 文件 | 是什么 | 需要吗 |
|---|---|---|
| `XC2-package-dist-0.2.1.zip` | 玩家包：启动器、运行时、提升工具与着色器工具 | **要** —— 直接用它玩 |
| `xc2-launcher-0.2.1-src.zip` | 启动器源码 | 不用 |

## 本版变化

### 1. 可调 3D 渲染质量、输出分辨率与 DLSS 支持（PR #36，@nikolaybutnik）

- **F1 设置页分工重排**：「显示」页控制 **输出分辨率**（`1080p` / `1440p` / `4K`，`[am] resolution`）和 **窗口大小**（默认 `auto` 跟随显示器，上限 1440p）；「画质」页将 **超分器**（`DLSS`、`FSR 3.1.6`、`FSR 4.1.2`、`FSR 2.3.4`、`TAAU`、`关闭`）、**超分/渲染质量档位**（`DLAA / 原生抗锯齿` 到 `超级性能` 及 `主机原版`）、实时 `渲染 -> 输出` 尺寸预览与 **DLSS 模型**（`默认` / `K` / `J`）整合在同一分组。
- **意图驱动缩放（`[upscale] render_quality`、`[gfx] output_scale`）**：启动时按输出分辨率自动推算缩放倍率；同时引入 `[nvn] acquire_wait = auto`，在开启 `mirror_capture` 时跳过冗余等待。
- **修复过场剧场崩溃**：从语言白名单中移除引发崩溃的 `AmericanEnglish` 与 `LatinAmericanSpanish`。

### 2. 启动器内置官方 NVIDIA DLSS & AMD FSR 一键下载器

- 在「设置 → 超分」提供两家厂商的**官方直链可选下载**：NVIDIA Streamline / DLSS（`v2.14.16`，PR #36）以及 AMD GPUOpen FidelityFX SDK（`v2.4.0` + `v1.1.4`，自动安装到 `upscalers/fsr3/`）。
- 下载前必须由玩家**确认对应的上游厂商许可条款**，下载全程校对字节数与 SHA-256 哈希，并将上游许可文件一并保存至 DLL 同目录；**本仓库和发行包本身均不夹带任何厂商预编译 DLL**。

### 3. 8 GB 显存支持、显存占用监控与 F1 交互优化

- **下调 `mirror_capture = auto` 阈值（`3584 -> 1536 MiB`）**：8 GB 显卡现在也会默认自动开启帧流水线保护。
- **显存状态可见**：启用 `VK_EXT_memory_budget`，日志每 60 秒输出一次实际 `vram:` 用量，F1 右侧状态栏同步显示显存及池拷贝占用；画质页底部「实验性功能」可手动切换帧流水线（自动 / 开启 / 关闭）。
- **F1 手柄焦点与安全退出**：打开 F1 或切换标签页时自动聚焦首项、方向键左右稳定归属当前选项栏（[#18](https://github.com/weile10000/xc2-ns2-recomp/issues/18)）；顶部右上角 **退出游戏** 按钮带二次确认弹窗，防止误触直接关掉进程。

### 4. 渲染优化、音频爆音修复与启动修复（PR #30 @UrsineBear 及其他修复）

- **修复 v0.1.2 以来的音频带电爆音问题（[#37](https://github.com/weile10000/xc2-ns2-recomp/issues/37)）**：修正了 `xc2/src/x2_audio301.cpp` 将 `nn::audio::OutputStream` 释放事件误创建为 `ManualClear`（`0`）而非 `EventClearMode_AutoClear`（`1`）的问题，并在写入时同步唤醒线程的队列水位，彻底消除音频线程 100% 空转抢占 XAudio2 引擎锁引起的电流爆音与降速。
- 新增 `VK_AMD_shader_early_and_late_fragment_tests`（`early_fragment_tests = auto`）、`VK_EXT_attachment_feedback_loop_layout` 零拷贝色彩反馈（`[nvn] fb_reuse`）、修复 `nvn_pipeline.cpp` UAF、优化 `nvn-texprep` 线程优先级，以及全屏/无边框空闲鼠标自动隐藏。
- **启动与 DLC 路径**：`mem::alias_base()` 在默认 `0x2000000000` 被占用时自动探测空闲 128 GiB 窗口（[#33](https://github.com/weile10000/xc2-ns2-recomp/issues/33)）；`aoc_indices()` 改用 UTF-8 路径，修复中文等非 ASCII DLC 目录崩溃（[#25](https://github.com/weile10000/xc2-ns2-recomp/issues/25)）。
- **CI 检查**：清理 `tools/run/route.ps1` 硬编码本机路径，并将 PR 个人路径检查限定在改动文件范围内。

## 从 v0.2.0 升级

直接覆盖解压到原目录即可；存档、`nxrt.ini`、`controls.ini` 与着色器缓存均会保留，**无需重新 Set up**。请保持 `xc2-launcher.exe` 与 `runtime/xc2_rt.dll` 来自同一发布包。

## 已知问题

- **眨眼 / 对白眼嘴闪烁**（[#15](https://github.com/weile10000/xc2-ns2-recomp/issues/15)）：继续挂起排查（已实机验证 `[nvn] view_reinterpret = 1` 并非根因，默认保持关闭）。
- **附加内容重场景负载较高**，以及首次运行约 20 秒管线编译提示。
- 开场战斗背景云海红边（单场景纯视觉）。

## 致谢

本版合入 PR：[#30](https://github.com/weile10000/xc2-ns2-recomp/pull/30)（**@UrsineBear**）、[#36](https://github.com/weile10000/xc2-ns2-recomp/pull/36)（**@nikolaybutnik**）。
协助定位本次修复的反馈：**@gao950912**（[#37](https://github.com/weile10000/xc2-ns2-recomp/issues/37) 版本二分与报告）。
上游与依赖：**fefw-recomp**、**nxrecomp**、**nxnative**、AMD **FidelityFX**、NVIDIA **Streamline**、**dav1d**、**SDL3**、**Dear ImGui**、**libvpx**、**libvorbis**、**FFmpeg**，许可详见 `licenses/` 与 `THIRD_PARTY_NOTICES.md`。
