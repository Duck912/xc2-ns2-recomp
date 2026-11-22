# 异度之刃 2 · Nintendo Switch 2 Edition —— Windows 静态重编译

[English](README.md) · **中文**

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
