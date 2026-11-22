# XC2 NS2 Recomp v0.2.0 — NVIDIA machines play, and there is a settings page

**Tested on a Radeon RX 6800 XT (16 GB).** The NVIDIA path comes from #19, which its author tested on a 5090 and a 4060 Laptop.

This release is the first one an NVIDIA machine can be expected to run, and the first one with a settings page you can
change anything from. Two community pull requests did most of that work: [#19](https://github.com/weile10000/xc2-ns2-recomp/pull/19)
(the NVIDIA fixes and the mirror capture) and [#27](https://github.com/weile10000/xc2-ns2-recomp/pull/27) (the RDNA 2 cloud
sea, native resolutions and the F1 page). On top of them, a film that plays over a live scene now hands the scene back, and
every thread dump names the guest functions it used to print as addresses.

## Which file do I download?

| file | what it is | do I need it? |
|---|---|---|
| `XC2-package-dist-0.2.0.zip` | the player package: launcher, runtime, the lifter and the shader tools | **yes** — this is the one you play from |
| `xc2-launcher-0.2.0-src.zip` | the launcher's source, for people who want to read or build it | no |

## What's new

### NVIDIA machines run (PR #19, @nikolaybutnik)

The GPU now reads a per-submission copy of every pool the game writes from the CPU, so a draw sees the bytes of the frame
it belongs to instead of whatever the CPU wrote next — the flicker, the tearing and the stripes on NVIDIA were all that
race. Measured here: the flicker is gone, the port area is much faster, and a long battle shows one hitch rather than a
regular beat.

The defaults are per machine: `[nvn] mirror_capture = auto` (on when the copies fit, which on a 16 GB card they do; off on
an 8 GB laptop), `present_ahead = auto`, `snapshot_instances = auto`. The clouds coming back was the last piece: occlusion
query results had to be written into the capture's copy too
([#19](https://github.com/weile10000/xc2-ns2-recomp/pull/19#issuecomment-7073852291)).

### The cloud sea, at native resolution (PR #27, @UrsineBear)

The RDNA 2 blue-grey rim where objects meet the cloud sea and the cloud-sea shimmer in motion are gone — both were the
same CPU/GPU byte race above, not a shader bug. On top of that the page brings a native 3D resolution override
(`[xc2] native_res`, `native_w`, `native_h`, `res_class`), 1080p / 1440p / native-4K presets, live FSR switching, a
performance HUD, and add-on content discovery when `indices.txt` is absent.

One known defect stays: in the opening battle background a thin **red edge** along a cloud-sea silhouette. It is one scene,
it does not move and it does not affect play, so it is listed as low priority in `docs/COMPATIBILITY.md`.

### A settings page on F1

Two panes, Chinese and English, every option applying and saving to `controls.ini`: window mode and size, VSync, frame
cap, the upscaler, colour grading, textures, HDR, audio, gamepad, the FPS counter (F10) and fullscreen (F11). Settings that
need a restart say so. `docs/SETTINGS.md` describes the two settings files, who maintains which layer, and the five steps
for adding an option — plus a gate (`tools/ci/check_play_settings.py`) that fails when a key is read but never written, or
the reverse.

### Films hand the scene back

A film that plays *over* a live cutscene (the memory inserts, 7–41 s) used to stop on its last picture, keep the sound
running, and never give the scene back; the scene gave up about 35 s later and dropped into the next scene, skipping the
rest of the cutscene. Three things were wrong at once: the end-of-stream marker was stamped on a picture (players drop such
an output and wait for the picture they counted on), the film's placeholder audio track never reported an end while the
player's finish covers every track, and a fence armed with nothing to pair waited forever. All three are fixed; measured on
the 6800 XT, the player now stops **0.24 s** after the video end of stream instead of 35 s, and the cutscene carries on.

The long standalone cutscenes still play end to end (96 s, 2,833 pictures).

### Guest symbols in every dump

The lift's dynsym tables carry real addresses (subsdk0 1,164 names, sdk 28,475). The build now writes `<exe>.names` from
them and the runtime renames the map's `f_<address>` entries, so a thread dump reads
`subsdk0!movie::MediaDecoder::Stop` and `main!nnMain` instead of a bare address.

### Text languages in the launcher

Settings → Game language now offers every text language the retail 3.0.1 title supports — eleven of them, Chinese as
Simplified and Traditional — plus Automatic (follows the Windows language). It writes `[system] language` and applies at
the next start; the voices stay Japanese and English whatever is chosen, as on the console
([#26](https://github.com/weile10000/xc2-ns2-recomp/issues/26)).

### Setup

- The headless prefill that fills the shader cache tries the run **twice** before reporting a failure, and writes the second
  attempt to `prefill-2.log` ([#25](https://github.com/weile10000/xc2-ns2-recomp/issues/25)).
- Add-on content is found whether `romfs` sits directly under the content id or one level deeper
  ([#20](https://github.com/weile10000/xc2-ns2-recomp/issues/20)).
- Frame generation refuses to start when the FSR 3 upscaler DLL is missing, instead of running on top of the built-in
  upscaler and making the icons and the minimap jitter ([#18](https://github.com/weile10000/xc2-ns2-recomp/issues/18)).
- The launcher reports its real version and the package refuses a launcher built before the version bump
  ([#24](https://github.com/weile10000/xc2-ns2-recomp/issues/24)).

## Issues in this release

| issue | state in 0.2.0 |
|---|---|
| [#17](https://github.com/weile10000/xc2-ns2-recomp/issues/17) flashback freezes while dialogue continues | **fixed** — the film's end of stream now reaches the player; please confirm on your machine |
| [#18](https://github.com/weile10000/xc2-ns2-recomp/issues/18) FSR 3 DLLs together make icons and the minimap jitter | **worked around** — frame generation and the upscaler must both be present; the mix is refused and logged |
| [#20](https://github.com/weile10000/xc2-ns2-recomp/issues/20) add-on content "deleted", F1 does nothing | **fixed** — both romfs layouts are accepted, and F1 opens the settings page |
| [#24](https://github.com/weile10000/xc2-ns2-recomp/issues/24) launcher says 0.1.3, A/B swapped | **closed** — the version is the package's own, and the pad layout follows the Switch positions (`[pad] label_abxy = 1` for letters) |
| [#25](https://github.com/weile10000/xc2-ns2-recomp/issues/25) "always fails to translate shaders" | **mitigated** — the prefill retries; if both attempts break at the same point, attach `prefill-2.log` |
| [#26](https://github.com/weile10000/xc2-ns2-recomp/issues/26) more languages | **done** — all eleven text languages, see above |
| [#2](https://github.com/weile10000/xc2-ns2-recomp/issues/2) black render / TDR | **closed** — fixed by the present change in 0.1.4, confirmed by the reporter |
| [#4](https://github.com/weile10000/xc2-ns2-recomp/issues/4) black screen on an RTX card | **open** — awaiting a retest on the 3070 |
| [#15](https://github.com/weile10000/xc2-ns2-recomp/issues/15) eye and mouth flicker | **open** — it survives the bilinear upscaler, so it is not the temporal path |
| [#22](https://github.com/weile10000/xc2-ns2-recomp/issues/22) ultrawide | **open** — a feature, not a config key; the render path itself is fine at 21:9 |

## Upgrading from v0.1.4

Unzip over the install; saves, settings and the shader cache are kept, and no new Set up is needed. Two things the new
settings page changes on its own:

- an existing `controls.ini` moves to factory revision 3, which turns the stale `F2` for the FPS counter into the advertised
  `F10`. A hotkey you rebound yourself stays;
- the new keys (`[fps]`, `[upscale] mode`, `[latency]`, `[hdr]`) get their defaults if the file does not have them.

`xc2_rt.dll` and the launcher must come from the same package; a launcher from an older package does not know the new keys.

## Known issues

- **Eye and mouth flicker** during blinking and dialogue ([#15](https://github.com/weile10000/xc2-ns2-recomp/issues/15)) — no
  direction yet; it is not the upscaler, the jitter or the temporal history.
- **Add-on content scenes run slower** than the main game, and their 4K openings are the heaviest thing in the title.
- **First run compiles pipelines** — about 22 seconds with no frame, then never again.
- **Ultrawide is not supported** ([#22](https://github.com/weile10000/xc2-ns2-recomp/issues/22)).
- **A red edge** on the cloud sea in the opening battle background; one scene, cosmetic.

## Credits

Pull requests in this release: [#19](https://github.com/weile10000/xc2-ns2-recomp/pull/19) by **@nikolaybutnik** (NVIDIA
fixes, the mirror capture), [#27](https://github.com/weile10000/xc2-ns2-recomp/pull/27) by **@UrsineBear** (RDNA 2 cloud sea,
native resolutions, the bilingual F1 page).

Reports that shaped it: **@Kain2k** (#15, #17, and the traces that pinned the film hand-back), **@TheSeeOHZee** (#4, #25),
**@maioro** (#18, and the DLC and FSR data), **@hy9902** (#20), **@ahmadsultan1990** and **@tyl-beep** (ultrawide),
**@rombat** (#26), **@MorpheusCode117** (Lichii, and the offer to diff the render path).

Upstream: **fefw-recomp** by Goldoire (GPL-3.0, the runtime this fork is built on), **nxrecomp** (the lifter),
**nxnative** (the reference implementation the media work was checked against), AMD **FidelityFX** (FSR), **dav1d**,
**SDL3**, **Dear ImGui**, **libvpx** and **libvorbis**. Licences are in `licenses/` and `THIRD_PARTY_NOTICES.md`.


---

# XC2 NS2 重编译 v0.2.0 —— N 卡能玩了，而且有了设置界面

**在 Radeon RX 6800 XT（16 GB）上实测。** N 卡路径来自 #19，由作者在 5090 与 4060 Laptop 上测过。

这是第一个 N 卡机器能跑的版本，也是第一个有设置界面、什么都能自己改的版本。大部分工作来自两个社区 PR：
[#19](https://github.com/weile10000/xc2-ns2-recomp/pull/19)（N 卡修复与 mirror capture）和
[#27](https://github.com/weile10000/xc2-ns2-recomp/pull/27)（RDNA 2 云海、原生分辨率、F1 设置页）。在这之上，
**叠在实时场景上播放的影片现在会把场景交还**，而且每一份线程转储都会显示客机函数名，而不是一串地址。

## 我该下哪个文件？

| 文件 | 是什么 | 需要吗 |
|---|---|---|
| `XC2-package-dist-0.2.0.zip` | 玩家包：启动器、运行时、提升工具与着色器工具 | **要** —— 直接用它玩 |
| `xc2-launcher-0.2.0-src.zip` | 启动器源码，给想读或想自己编的人 | 不用 |

## 本版变化

### N 卡能跑了（PR #19，@nikolaybutnik）

GPU 现在读的是**每次提交时的一份池拷贝**，所以一次绘制看到的是它自己那一帧的字节，而不是 CPU 之后写进去的内容——
N 卡上的闪烁、撕裂、条纹都是这个竞态。实测：闪烁消失，港口区域明显更快，长时间战斗只抽一下而不是规律地抽。

默认值按机器分流：`[nvn] mirror_capture = auto`（拷贝放得下才开，16 GB 卡放得下，8 GB 笔记本不开）、
`present_ahead = auto`、`snapshot_instances = auto`。云回来的关键是最后一块：**遮挡查询结果也必须写进拷贝**
（[#19 回帖](https://github.com/weile10000/xc2-ns2-recomp/pull/19#issuecomment-7073852291)）。

### 云海，以及原生分辨率（PR #27，@UrsineBear）

RDNA 2 上物体与云海交界处的蓝灰边、以及运动中的云海闪动都消失了——两者其实是上面同一个 CPU/GPU 字节竞态，不是着色器
的错。这一版还带来原生 3D 分辨率覆盖（`[xc2] native_res`、`native_w`、`native_h`、`res_class`）、
1080p / 1440p / 原生 4K 预设、实时切 FSR、性能 HUD，以及 `indices.txt` 缺失时的 DLC 自动发现。

仍有一个已知瑕疵：开场战斗背景的云海有一条**红边**。只在一个场景、不移动、不影响操作，故在
`docs/COMPATIBILITY.md` 里标为低优先级。

### F1 设置界面

双栏、中英双语，每个选项都会**应用并保存到 `controls.ini`**：窗口模式与尺寸、垂直同步、帧率上限、超分器、色调、
贴图、HDR、音频、手柄、帧率监控（F10）与全屏（F11）。需要重启的项目会写明。`docs/SETTINGS.md` 记述两套设置文件、
各自归属、以及“加一个设置项”的五步流程，还有一道闸门（`tools/ci/check_play_settings.py`）：某个键只读不写或只写
不读，直接失败。

### 影片交还场景

**叠在实时过场之上**播放的影片（回忆插入段，7–41 秒）以前会停在最后一帧、声音继续、场景不交还；场景大约 35 秒后
放弃，跳到下一个场景，把剩下的实时过场整段跳过。当时是三处同时错：结束标记被盖在画面上（播放器会把这种输出丢掉，
然后等它“算准”的那张）、占位音轨从不报告结束而播放器的收尾条件覆盖所有轨、以及一把配不上任何画面的 fence 永远在等。
三处都已修；6800 XT 实测，播放器现在在视频 EOS 后 **0.24 秒**收尾，而不是 35 秒，过场接着走。

独立播放的整段过场仍然完整（96 秒、2,833 张）。

### 转储里有客机函数名

提升产物的 dynsym 表带真实地址（subsdk0 1,164 个、sdk 28,475 个）。构建现在据此写出 `<exe>.names`，运行时把 map 里
`f_<地址>` 的条目改名，于是线程转储读出来是 `subsdk0!movie::MediaDecoder::Stop`、`main!nnMain`，不再是一串地址。

### 启动器里的文本语言

“设置 → 游戏语言”现在提供零售 3.0.1 支持的全部文本语言——十一种，中文按简体、繁体各一条——外加“自动（跟随 Windows
语言）”。写入 `[system] language`，**下次启动生效**；语音仍是日/英，和主机一致
（[#26](https://github.com/weile10000/xc2-ns2-recomp/issues/26)）。

### 安装流程

- 填着色器缓存的 headless prefill **最多试两次**才判失败，第二次写到 `prefill-2.log`
  （[#25](https://github.com/weile10000/xc2-ns2-recomp/issues/25)）。
- 附加内容无论 `romfs` 直接挂在内容 id 下、还是多一层目录，都能找到
  （[#20](https://github.com/weile10000/xc2-ns2-recomp/issues/20)）。
- 超分 DLL 缺失时，**帧生成拒绝启动**，而不是叠在内建超分上继续跑、让图标与小地图抖动
  （[#18](https://github.com/weile10000/xc2-ns2-recomp/issues/18)）。
- 启动器报告真实版本号，且打包会拒绝版本号未更新的启动器
  （[#24](https://github.com/weile10000/xc2-ns2-recomp/issues/24)）。

## 本版对应的 issue

| issue | 0.2.0 里的状态 |
|---|---|
| [#17](https://github.com/weile10000/xc2-ns2-recomp/issues/17) 闪回播放时冻结、对白继续 | **已修** —— 结束标记现在能送到播放器；请在你自己机器上确认 |
| [#18](https://github.com/weile10000/xc2-ns2-recomp/issues/18) FSR 3 两个 DLL 同时在场导致图标/小地图抖动 | **已规避** —— 帧生成与超分必须同时在位，混用会被拒绝并记录 |
| [#20](https://github.com/weile10000/xc2-ns2-recomp/issues/20) 附加内容“已删除”、F1 无反应 | **已修** —— 两种 romfs 布局都认，F1 现在打开设置页 |
| [#24](https://github.com/weile10000/xc2-ns2-recomp/issues/24) 启动器显示 0.1.3、A/B 互换 | **已关** —— 版本号来自包本身；手柄按 Switch 位置映射（要字母用 `[pad] label_abxy = 1`） |
| [#25](https://github.com/weile10000/xc2-ns2-recomp/issues/25) “总是翻译着色器失败” | **已缓解** —— prefill 会重试；两次都停在同一处请附 `prefill-2.log` |
| [#26](https://github.com/weile10000/xc2-ns2-recomp/issues/26) 更多语言 | **已完成** —— 十一种文本语言，见上 |
| [#2](https://github.com/weile10000/xc2-ns2-recomp/issues/2) 渲染全黑 / TDR | **已关** —— 0.1.4 的呈现修复解决，报告者已确认 |
| [#4](https://github.com/weile10000/xc2-ns2-recomp/issues/4) RTX 卡黑屏 | **开着** —— 等 3070 复测 |
| [#15](https://github.com/weile10000/xc2-ns2-recomp/issues/15) 眼/嘴闪烁 | **开着** —— 换 bilinear 仍复现，说明不是时间超分那条路 |
| [#22](https://github.com/weile10000/xc2-ns2-recomp/issues/22) 超宽屏 | **开着** —— 是功能不是配置项；渲染路径本身支持 21:9 |

## 从 v0.1.4 升级

覆盖解压即可；存档、设置、着色器缓存都保留，**不需要重新 Set up**。设置页会自己改两件事：

- 已有的 `controls.ini` 升到出厂修订 3，把过期的 `F2` 帧率热键改成界面所写的 `F10`；玩家自己改过的键不动；
- 新键（`[fps]`、`[upscale] mode`、`[latency]`、`[hdr]`）若文件里没有，取默认值。

`xc2_rt.dll` 与启动器必须来自同一个包；旧包的启动器不认识这些新键。

## 已知问题

- **眼/嘴闪烁**（[#15](https://github.com/weile10000/xc2-ns2-recomp/issues/15)）——仍无方向；已排除超分、jitter 与时间历史。
- **附加内容场景比正篇慢**，其 4K 开场是全作最重的内容。
- **首次运行编译管线** —— 约 22 秒无画面，之后不再发生。
- **不支持超宽屏**（[#22](https://github.com/weile10000/xc2-ns2-recomp/issues/22)）。
- **开场战斗背景的云海有一条红边**；单个场景、纯视觉。

## 致谢

本版包含的 PR：[#19](https://github.com/weile10000/xc2-ns2-recomp/pull/19) **@nikolaybutnik**（N 卡修复、mirror
capture）、[#27](https://github.com/weile10000/xc2-ns2-recomp/pull/27) **@UrsineBear**（RDNA 2 云海、原生分辨率、
双语 F1 界面）。

塑造了这一版的报告：**@Kain2k**（#15、#17，以及钉住影片交还的那些 trace）、**@TheSeeOHZee**（#4、#25）、
**@maioro**（#18，以及 DLC 与 FSR 的数据）、**@hy9902**（#20）、**@ahmadsultan1990** 与 **@tyl-beep**（超宽屏）、
**@rombat**（#26）、**@MorpheusCode117**（Lichii，以及愿意对渲染路径做 diff）。

上游：**fefw-recomp**（Goldoire，GPL-3.0，本分支的基础运行时）、**nxrecomp**（提升器）、**nxnative**（媒体部分对照的
参考实现）、AMD **FidelityFX**（FSR）、**dav1d**、**SDL3**、**Dear ImGui**、**libvpx**、**libvorbis**。许可证见
`licenses/` 与 `THIRD_PARTY_NOTICES.md`。
