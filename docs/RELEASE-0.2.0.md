# XC2 NS2 Recomp v0.2.0 — the NS2 edition's own problems, solved

**Tested on a Radeon RX 6800 XT (16 GB).** The NVIDIA path comes from #19, which its author tested on a 5090 and a
4060 Laptop.

The Switch 2 edition is not the Switch 1 game with a bigger icon. Its cutscenes are 4K AV1, its memory films play *over* a
live scene and have to hand that scene back, and its player is guest code we cannot call into — the runtime only supplies
`nn::codec`. This release is mostly about those three, plus the first settings page and the first NVIDIA support.

> As far as we can tell this is the only public static recompilation of the NS2 edition. The Switch 1 game has its own
> recomp (XC2 Recomp, MIT, a different codebase), and the emulator projects run the game instead of recompiling it; none of
> them publishes a recompiled NS2 runtime.

## Which file do I download?

| file | what it is | do I need it? |
|---|---|---|
| `XC2-package-dist-0.2.0.zip` | the player package: launcher, runtime, the lifter and the shader tools | **yes** — this is the one you play from |
| `xc2-launcher-0.2.0-src.zip` | the launcher's source, for people who want to read or build it | no |

## What's new

### 4K cutscenes, and the films that sit inside a scene

The NS2 edition's films are 3840×2160 AV1, and the SDK's decoder opens the GPU driver directly, which no recompiled PC
build can follow. `nn::codec` is taken over instead: `Acquire` decodes the first picture in place rather than handing out a
fence nothing completes, `Submit` keeps every packet (the client never looks at the "queue full" result), and hardware
decode runs through Vulkan Video / D3D11VA with dav1d behind it.

The end of a stream is its own output, never a flag on a picture — players drop a flagged picture and then wait for the one
they counted on. The film's audio track is a placeholder clock, not sound, and it never reported an end while the player's
finish condition covers every track; it now ends with the picture. Measured on the 6800 XT: a 96-second cutscene plays end
to end (2,833 pictures), and a memory film inserted into a live cutscene hands the scene back **0.24 s** after the video end
of stream instead of 35 s.

Every thread dump now names those functions (`subsdk0!movie::MediaDecoder::Stop`, `main!nnMain`): the lift's dynsym
tables carry real addresses (31,216 names across the modules), the build writes them next to the exe, and the runtime
renames the map's `f_<address>` entries.

### NVIDIA machines run (PR #19, @nikolaybutnik)

The GPU now reads a per-submission copy of every pool the CPU writes, so a draw sees the bytes of the frame it belongs to
instead of whatever the CPU wrote next — the flicker, the tearing and the stripes on NVIDIA were all that race. The
defaults are per machine (`[nvn] mirror_capture = auto`: on when the copies fit, off on an 8 GB laptop), and the clouds
came back once occlusion-query results were written into the capture's copy too.

### The cloud sea, and native resolutions (PR #27, @UrsineBear)

The RDNA 2 blue-grey rim where objects meet the cloud sea, and the cloud-sea shimmer in motion, are gone — the same
CPU/GPU byte race, not a shader bug. The page also brings a native 3D resolution override (`[xc2] native_res`,
`native_w`, `native_h`, `res_class`), 1080p / 1440p / native-4K presets, live FSR switching, a performance HUD and
add-on content discovery when `indices.txt` is absent.

One defect stays: a thin **red edge** along a cloud-sea silhouette in the opening battle background. One scene, does not
move, does not affect play — low priority in `docs/COMPATIBILITY.md`.

### A settings page on F1

Two panes, Chinese and English, every option applying and saving to `controls.ini`: window mode and size, VSync, frame
cap, the upscaler, colour grading, textures, HDR, audio, gamepad, the FPS counter (F10) and fullscreen (F11). Settings
that need a restart say so. `docs/SETTINGS.md` describes the two settings files and who maintains which layer, and a gate
(`tools/ci/check_play_settings.py`) fails when a key is read but never written, or the reverse.

### Text languages in the launcher

Settings → Game language offers every text language the retail 3.0.1 title supports — eleven, Chinese as Simplified and
Traditional — plus Automatic (follows the Windows language). It writes `[system] language` and applies at the next start;
the voices stay Japanese and English, as on the console ([#26](https://github.com/weile10000/xc2-ns2-recomp/issues/26)).

### Setup

- The headless prefill that fills the shader cache tries the run **twice** before reporting a failure, and writes the
  second attempt to `prefill-2.log` ([#25](https://github.com/weile10000/xc2-ns2-recomp/issues/25)).
- Add-on content is found whether `romfs` sits directly under the content id or one level deeper
  ([#20](https://github.com/weile10000/xc2-ns2-recomp/issues/20)).
- Frame generation refuses to start when the FSR 3 upscaler DLL is missing, instead of running on top of the built-in
  upscaler and making the icons and the minimap jitter
  ([#18](https://github.com/weile10000/xc2-ns2-recomp/issues/18)).
- The launcher reports its real version, and the package refuses a launcher built before the version bump
  ([#24](https://github.com/weile10000/xc2-ns2-recomp/issues/24)).

## Issues in this release

| issue | state in 0.2.0 |
|---|---|
| [#17](https://github.com/weile10000/xc2-ns2-recomp/issues/17) flashback freezes while dialogue continues | **fixed** — the end of stream reaches the player; please confirm on your machine |
| [#18](https://github.com/weile10000/xc2-ns2-recomp/issues/18) FSR 3 DLLs together make icons and the minimap jitter | **worked around** — frame generation and the upscaler must both be present; the mix is refused and logged |
| [#20](https://github.com/weile10000/xc2-ns2-recomp/issues/20) add-on content "deleted", F1 does nothing | **fixed** — both romfs layouts are accepted, and F1 opens the settings page |
| [#24](https://github.com/weile10000/xc2-ns2-recomp/issues/24) launcher says 0.1.3, A/B swapped | **closed** — the version is the package's own; the pad follows the Switch positions (`[pad] label_abxy = 1` for letters) |
| [#25](https://github.com/weile10000/xc2-ns2-recomp/issues/25) "always fails to translate shaders" | **mitigated** — the prefill retries; if both attempts break at the same point, attach `prefill-2.log` |
| [#26](https://github.com/weile10000/xc2-ns2-recomp/issues/26) more languages | **done** — all eleven text languages |
| [#2](https://github.com/weile10000/xc2-ns2-recomp/issues/2) black render / TDR | **closed** — fixed by the present change in 0.1.4, confirmed by the reporter |

## Upgrading from v0.1.4

Unzip over the install; saves, settings and the shader cache are kept, and no new Set up is needed. Two things the new
settings page changes on its own:

- an existing `controls.ini` moves to factory revision 3, which turns the stale `F2` FPS hotkey into the advertised
  `F10`; a hotkey you rebound yourself stays;
- the new keys (`[fps]`, `[upscale] mode`, `[latency]`, `[hdr]`) get their defaults if the file does not have them.

`xc2_rt.dll` and the launcher must come from the same package; a launcher from an older package does not know the new keys.

## Known issues

- **Add-on content scenes run slower** than the main game, and their 4K openings are the heaviest thing in the title.
- **First run compiles pipelines** — about 22 seconds with no frame, then never again.
- **Ultrawide is not supported** ([#22](https://github.com/weile10000/xc2-ns2-recomp/issues/22)); the render path is fine at
  21:9, the game's own aspect handling and UI are not.
- **A red edge** on the cloud sea in the opening battle background; one scene, cosmetic.

## Credits

Pull requests: [#19](https://github.com/weile10000/xc2-ns2-recomp/pull/19) by **@nikolaybutnik** (NVIDIA fixes, the mirror
capture), [#27](https://github.com/weile10000/xc2-ns2-recomp/pull/27) by **@UrsineBear** (RDNA 2 cloud sea, native
resolutions, the bilingual F1 page).

Reports that shaped it: **@Kain2k** (#17, and the traces that pinned the film hand-back), **@TheSeeOHZee** (#25),
**@maioro** (#18, and the DLC and FSR data), **@hy9902** (#20), **@ahmadsultan1990** and **@tyl-beep** (ultrawide),
**@rombat** (#26), **@MorpheusCode117** (Lichii, and the offer to diff the render path).

Upstream: **fefw-recomp** by Goldoire (GPL-3.0, the runtime this fork is built on), **nxrecomp** (the lifter),
**nxnative** (the reference implementation the media work was checked against), AMD **FidelityFX** (FSR), **dav1d**,
**SDL3**, **Dear ImGui**, **libvpx**, **libvorbis**. Licences are in `licenses/` and `THIRD_PARTY_NOTICES.md`.


---

# XC2 NS2 重编译 v0.2.0 —— NS2 版自己的问题，自己解决

**在 Radeon RX 6800 XT（16 GB）上实测。** N 卡路径来自 #19，由作者在 5090 与 4060 Laptop 上测过。

NS2 版不是“换了图标的 NS1”。它的过场是 **4K AV1**；它的回忆短片是**叠在实时场景之上**播、播完必须把场景交还；
而它的播放器是客机代码，我们调不进去——运行时只负责 `nn::codec`。这一版主要就是这三件事，加上第一个设置界面和
第一份 N 卡支持。

> 据我们所知，这是**NS2 版目前唯一公开的静态重编译项目**。NS1 版有它自己的重编译（XC2 Recomp，MIT，另一套代码），
> 模拟器项目是“运行”而不是“重编译”，它们都没有发布 NS2 的重编译运行时。

## 我该下哪个文件？

| 文件 | 是什么 | 需要吗 |
|---|---|---|
| `XC2-package-dist-0.2.0.zip` | 玩家包：启动器、运行时、提升工具与着色器工具 | **要** —— 直接用它玩 |
| `xc2-launcher-0.2.0-src.zip` | 启动器源码，给想读或想自己编的人 | 不用 |

## 本版变化

### 4K 过场，以及“插在场景里”的短片

NS2 版的影片是 3840×2160 AV1，而 SDK 的解码器直接打开 GPU 驱动，重编译到 PC 后走不通。于是 `nn::codec` 由我们接管：
`Acquire` 就地解出第一张（而不是交一根没人能完成的 fence）、`Submit` 收下所有包（客户端根本不看“队列满”那个返回值）、
硬件解码走 Vulkan Video / D3D11VA，dav1d 作为后备。

**流的结束是一个独立输出，永远不是画面上的一面旗**——播放器会把带结束标志的画面丢掉，然后一直等它“算准”的那张。
影片的音轨是**占位时钟**、不是声音，而它从不报告结束，播放器的收尾条件却覆盖所有轨；现在它随画面一起收。
6800 XT 实测：96 秒整段过场完整播放（2,833 张）；插入实时过场的回忆短片在视频 EOS 后 **0.24 秒**交还场景，而不是 35 秒。

每一份线程转储现在都能叫出这些函数（`subsdk0!movie::MediaDecoder::Stop`、`main!nnMain`）：提升产物的 dynsym 表
带真实地址（各模块合计 31,216 个名字），构建时写进 exe 旁边，运行时把 map 里 `f_<地址>` 的条目改名。

### N 卡能跑了（PR #19，@nikolaybutnik）

GPU 现在读的是**每次提交时的一份池拷贝**，一次绘制看到的是它那一帧的字节，而不是 CPU 之后写进去的内容——N 卡上的
闪烁、撕裂、条纹都是这个竞态。默认值按机器分流（`[nvn] mirror_capture = auto`：拷贝放得下才开，8 GB 笔记本不开）；
云回来的关键是**遮挡查询结果也写进了拷贝**。

### 云海，以及原生分辨率（PR #27，@UrsineBear）

RDNA 2 上物体与云海交界处的蓝灰边、运动中云海的闪动都消失了——是上面同一个字节竞态，不是着色器的错。这一版还带来
原生 3D 分辨率覆盖（`[xc2] native_res`、`native_w`、`native_h`、`res_class`）、1080p / 1440p / 原生 4K 预设、
实时切 FSR、性能 HUD，以及 `indices.txt` 缺失时的 DLC 自动发现。

仍有一个瑕疵：开场战斗背景的云海有一条**红边**。只在一个场景、不移动、不影响操作，在 `docs/COMPATIBILITY.md` 里
标为低优先级。

### F1 设置界面

双栏、中英双语，每个选项都会**应用并保存到 `controls.ini`**：窗口模式与尺寸、垂直同步、帧率上限、超分器、色调、
贴图、HDR、音频、手柄、帧率监控（F10）与全屏（F11）。需要重启的项目会写明。`docs/SETTINGS.md` 记述两套设置文件、
各自归属，以及“加一个设置项”的五步流程；`tools/ci/check_play_settings.py` 是配套闸门：某个键只读不写或只写不读，
直接失败。

### 启动器里的文本语言

“设置 → 游戏语言”提供零售 3.0.1 支持的全部文本语言——十一种，中文按简体、繁体各一条——外加“自动（跟随 Windows
语言）”。写入 `[system] language`，**下次启动生效**；语音仍是日/英，与主机一致
（[#26](https://github.com/weile10000/xc2-ns2-recomp/issues/26)）。

### 安装流程

- 填着色器缓存的 headless prefill **最多试两次**才判失败，第二次写到 `prefill-2.log`
  （[#25](https://github.com/weile10000/xc2-ns2-recomp/issues/25)）。
- 附加内容无论 `romfs` 直接挂在内容 id 下、还是多一层目录，都能找到
  （[#20](https://github.com/weile10000/xc2-ns2-recomp/issues/20)）。
- 超分 DLL 缺失时**帧生成拒绝启动**，而不是叠在内建超分上继续跑、让图标与小地图抖动
  （[#18](https://github.com/weile10000/xc2-ns2-recomp/issues/18)）。
- 启动器报告真实版本号，打包会拒绝版本号未更新的启动器
  （[#24](https://github.com/weile10000/xc2-ns2-recomp/issues/24)）。

## 本版对应的 issue

| issue | 0.2.0 里的状态 |
|---|---|
| [#17](https://github.com/weile10000/xc2-ns2-recomp/issues/17) 闪回播放时冻结、对白继续 | **已修** —— 结束标记现在能送到播放器；请在你自己机器上确认 |
| [#18](https://github.com/weile10000/xc2-ns2-recomp/issues/18) FSR 3 两个 DLL 同时在场导致图标/小地图抖动 | **已规避** —— 帧生成与超分必须同时在位，混用会被拒绝并记录 |
| [#20](https://github.com/weile10000/xc2-ns2-recomp/issues/20) 附加内容“已删除”、F1 无反应 | **已修** —— 两种 romfs 布局都认，F1 现在打开设置页 |
| [#24](https://github.com/weile10000/xc2-ns2-recomp/issues/24) 启动器显示 0.1.3、A/B 互换 | **已关** —— 版本号来自包本身；手柄按 Switch 位置映射（要字母用 `[pad] label_abxy = 1`） |
| [#25](https://github.com/weile10000/xc2-ns2-recomp/issues/25) “总是翻译着色器失败” | **已缓解** —— prefill 会重试；两次都停在同一处请附 `prefill-2.log` |
| [#26](https://github.com/weile10000/xc2-ns2-recomp/issues/26) 更多语言 | **已完成** —— 十一种文本语言 |
| [#2](https://github.com/weile10000/xc2-ns2-recomp/issues/2) 渲染全黑 / TDR | **已关** —— 0.1.4 的呈现修复解决，报告者已确认 |

## 从 v0.1.4 升级

覆盖解压即可；存档、设置、着色器缓存都保留，**不需要重新 Set up**。设置页会自己改两件事：

- 已有的 `controls.ini` 升到出厂修订 3，把过期的 `F2` 帧率热键改成界面所写的 `F10`；玩家自己改过的键不动；
- 新键（`[fps]`、`[upscale] mode`、`[latency]`、`[hdr]`）若文件里没有，取默认值。

`xc2_rt.dll` 与启动器必须来自同一个包；旧包的启动器不认识这些新键。

## 已知问题

- **附加内容场景比正篇慢**，其 4K 开场是全作最重的内容。
- **首次运行编译管线** —— 约 22 秒无画面，之后不再发生。
- **不支持超宽屏**（[#22](https://github.com/weile10000/xc2-ns2-recomp/issues/22)）；渲染路径本身支持 21:9，
  是游戏自己的宽高比处理与 UI 不支持。
- **开场战斗背景的云海有一条红边**；单个场景、纯视觉。

## 致谢

本版包含的 PR：[#19](https://github.com/weile10000/xc2-ns2-recomp/pull/19) **@nikolaybutnik**（N 卡修复、mirror
capture）、[#27](https://github.com/weile10000/xc2-ns2-recomp/pull/27) **@UrsineBear**（RDNA 2 云海、原生分辨率、
双语 F1 界面）。

塑造了这一版的报告：**@Kain2k**（#17，以及钉住影片交还的那些 trace）、**@TheSeeOHZee**（#25）、**@maioro**（#18，
以及 DLC 与 FSR 的数据）、**@hy9902**（#20）、**@ahmadsultan1990** 与 **@tyl-beep**（超宽屏）、**@rombat**（#26）、
**@MorpheusCode117**（Lichii，以及愿意对渲染路径做 diff）。

上游：**fefw-recomp**（Goldoire，GPL-3.0，本分支的基础运行时）、**nxrecomp**（提升器）、**nxnative**（媒体部分对照的
参考实现）、AMD **FidelityFX**（FSR）、**dav1d**、**SDL3**、**Dear ImGui**、**libvpx**、**libvorbis**。许可证见
`licenses/` 与 `THIRD_PARTY_NOTICES.md`。
