# XC2 NS2 Recomp v0.1.4 — the frame on screen is the frame the game finished

**Tested on a Radeon RX 6800 XT and an RTX 4060 Laptop** (thank you PJ my friend).

This release closes the three NVIDIA reports — stripes and flicker, tearing, and a black screen after a few seconds — and
gives cutscenes their sound back, in sync with the picture. The three reports turned out to be separate faults, and the
cutscene's silence was a fourth: its audio and the game's own were fighting over one device. The 4K openings now decode on
the GPU by default, and the pad's face buttons follow the Switch's positions. Unzip over your install; saves, settings and
the shader cache are kept.

> **Early version.** Set up and Play are the paths that work end to end; the launcher around them is still being built.

## Which file do I download?

| file | what it is | do I need it? |
|---|---|---|
| `XC2-package-dist-0.1.4.zip` | the player package: launcher, runtime, the lifter and the shader tools | **yes** — this is the one you play from |
| `xc2-launcher-0.1.4-src.zip` | the launcher's source, for people who want to read or build it | no |

## What's new

- **Presenting no longer copies a frame the game is still drawing.** The window texture is copied into the swapchain image on
  present, and that copy waited on the swapchain's acquire semaphore only. The game's draws are a separate submission, so at
  full frame rate the copy could be ordered ahead of them and the display received a partially written frame — grey and
  yellow stripes, a white or a black flash. On a 4060 Laptop the GPU then fell seconds behind and the device was lost.
  `SubmitPrefix` now carries the draw timeline of the frame being presented and the copy waits on it, and
  `[gfx] frames_in_flight` defaults to 1 on NVIDIA. Measured on the 4060 Laptop: 2 and 3 frames in flight corrupt within
  20–90 s, 1 is clean over long runs. [#10](https://github.com/weile10000/xc2-ns2-recomp/issues/10) @Kain2k,
  [#4](https://github.com/weile10000/xc2-ns2-recomp/issues/4) @TheSeeOHZee and
  [#2](https://github.com/weile10000/xc2-ns2-recomp/issues/2) @ffhome may all be this fault; #2 and #4 stay open until their
  reporters confirm.
- **The present mode the launcher writes is the one that is used.** The renderer read `[gfx] present_mode`, and 115 ms later
  the value derived from `[display] vsync` replaced it, so choosing FIFO produced Immediate — and tearing.
  `[gfx] present_mode` is the only key that decides now
  ([#12](https://github.com/weile10000/xc2-ns2-recomp/issues/12) @Kain2k).
- **A `controls.ini` written before factory revision 1 no longer presents in Immediate.** Such a file still carried
  `vsync = 0`, and the install therefore never used FIFO. Factory revision 2 moves it to 1, once; a value the player set
  stays (#12).
- **A cutscene's audio has a voice of its own.** audout (the film player's PCM stream) and the game's `nn::audio`
  OutputStream shared one XAudio2 sink. The game reports its free space as its buffer size minus that queue, so a film that
  kept the queue deep left the game with 0 free frames and it stopped writing — a silent cutscene; with the queue kept
  shallow the film's writes pushed the game's frames out and its timeline skipped ahead — the sound ran fast. audout now
  opens its own sink, and `x2_audio301` is back to the 0.1.3 code, unchanged.
- **The 4K openings decode on the GPU by default.** `[media] hwdec` is on: 30 fps on a 4060 Laptop where the CPU decoders
  managed 8–17. A GPU without the hardware decoder falls back to the CPU path by itself, and `hwdec = off` still disables
  it.
- **The pad's face buttons answer the Switch's positions.** The game lays its Arts out like the Switch pad, so the default
  layout is the Switch one: **B at the bottom, A on the right, Y on the left, X at the top.** On an Xbox pad the bottom
  button is therefore B and its printed A sits on the right, and a Switch pad maps the same either way. `[pad] label_abxy = 1`
  in `controls.ini` switches to the printed letters instead (an Xbox A answers a prompt that says A); the launcher's pad page
  has the same switch ([#14](https://github.com/weile10000/xc2-ns2-recomp/issues/14) @Kain2k). Factory revision 2 moves an
  existing install to the positional default once, and a layout the player chose stays.
- **A lost device reports the driver's own fault.** `VK_EXT_device_fault` is enabled where the driver offers it; the first
  failed submit logs the driver's fault description and address next to the `-4` (issue #10).
- **A `0xD401` at start is retried.** The 60 GiB VAMM setup fails on a rare launch; that launch is started again, and each
  attempt gets its own line in the log.
- **Source users**: `[nvn] fb_debug_hash` aims `[nvn] fb_debug` at one fragment shader (empty reports every binding that
  becomes a self-sampled attachment, capped at 500 lines), and the development link finds libvorbis on its own, so a dev
  build decodes a film's track like the shipped DLL.

## Upgrading from v0.1.3

- Replace the folder; `save/` and `shader_cache/` can be copied over, and no new Set up is needed.
- Two defaults change: hardware film decoding is on, and the pad layout is by position. A value the player set is kept.
- The launcher and the runtime now come from the same commit, and every exe records which one in `build.json`.

## Known issues

- **NVIDIA, the long-session device loss in
  [#10](https://github.com/weile10000/xc2-ns2-recomp/issues/10)** (@Kain2k, reporting from an RTX 5080): still open. Its
  fault shape differs from the one fixed here; the log carries the driver's own description now, which is what the next
  report needs.
- **Eyes and mouth flicker while a character blinks or speaks**
  ([#15](https://github.com/weile10000/xc2-ns2-recomp/issues/15) @Kain2k): under investigation. This build carries the
  diagnostic for it (`[nvn] fb_debug`, `[nvn] fb_debug_hash`), and the issue says what to send.
- The first frame of a 4K cutscene can flash green and break up for a moment before it settles.
- The picture still reads softer than the first game's recompilation
  ([#9](https://github.com/weile10000/xc2-ns2-recomp/issues/9) @UrsineBear): the internal scene is 1280×720, and TAAU is the
  default upscaler because it needs no extra DLL. FSR and DLSS are in the launcher.
- Cloud-sea shimmer and the blue-grey rim where geometry meets the cloud sea remain, on AMD GPUs only (inside the game's
  own volumetric fog).
- **On a display that Windows reports as HDR**, a cutscene's frames can come out with a green cast: the film's frame does
  not go through the HDR10 encode yet. Setting `[hdr] mode = off` in `nxrt.ini` (the launcher's video page has the same
  setting) brings the colours back.

## Before you press Play

**Set up takes 8–15 minutes and it is not hung.** It recompiles the game's translation units from your dump, links them,
then translates about 12,150 shader programs; the step list moves the whole time. The first launch after that compiles GPU
pipelines for about 20 seconds (once per driver).

## Package

| file | size | sha256 |
|---|---|---|
| `XC2-package-dist-0.1.4.zip` | 216.7 MB (643.4 MB unpacked) | `742DC8D9F9FA40AD764CC6ACC211DB67193C0E3023B9009FE8DD06FFE5424F4C` |
| `xc2-launcher-0.1.4-src.zip` | 0.5 MB | `F3DCA4DFDC4D1FBBBFFFFA7A466ED253DE91C9B3192A2E4B0D20632FBF2D7B44` |

The package contains no game files: the executable is built on your machine from your own dump and the shaders are
translated from it. Installation: [README](https://github.com/weile10000/xc2-ns2-recomp#readme).

It does carry FFmpeg (a shared GPL build) for the film's hardware decoders; it is loaded as a library, unmodified, and its
licence text and the source offer are in `licenses/FFMPEG-LICENSE.txt` and `THIRD_PARTY_NOTICES.md`.

## Credits

- **[Goldoire/fefw-recomp](https://github.com/Goldoire/fefw-recomp)** — the Switch runtime this project is built on: NVN/NVN2 replay,
  service HLE, the shader pipeline and the exe + DLL split all started there.
- [nxrecomp](https://github.com/drakolordx7/nxrecomp) — the static recompiler that lifts the game's code.
- Ryujinx (MIT) — the shader translator in the offline harness; SDL3, Vulkan-Headers, VMA and the other vendored
  dependencies are listed in `licenses/` in the package.
- [dav1d](https://code.videolan.org/videolan/dav1d) — the film's video decoder; [libvorbis](https://github.com/xiph/vorbis) — its sound.
- **[@capibawa](https://github.com/capibawa)** — [nxnative, branch `xc2-ns2-profile`](https://github.com/capibawa/nxnative/tree/xc2-ns2-profile): the
  four launch switches and the host-side movie/audio takeover this project follows (`dm/host/hle_movie.c`, `hle_audio.c`).
- The reports that shaped this release: @Kain2k ([#10](https://github.com/weile10000/xc2-ns2-recomp/issues/10),
  [#12](https://github.com/weile10000/xc2-ns2-recomp/issues/12), [#14](https://github.com/weile10000/xc2-ns2-recomp/issues/14),
  [#15](https://github.com/weile10000/xc2-ns2-recomp/issues/15)); and the ones still open — @TheSeeOHZee
  ([#4](https://github.com/weile10000/xc2-ns2-recomp/issues/4)), @ffhome ([#2](https://github.com/weile10000/xc2-ns2-recomp/issues/2)),
  @UrsineBear ([#9](https://github.com/weile10000/xc2-ns2-recomp/issues/9)).

---

# XC2 NS2 Recomp v0.1.4 —— 屏幕上的那一帧，是游戏画完的那一帧

**本版在 Radeon RX 6800 XT 与 RTX 4060 Laptop 上测试**（谢谢你我的朋友 PJ）。

这一版收掉三份 NVIDIA 报告——横条闪烁、撕裂、进游戏几秒后黑屏——并把过场的声音还了回来、与画面对齐。三份报告查下来是
三个不同的故障，而 CG 无声是第四个：影片的音频和游戏自己的音频在抢同一个设备。此外，4K 开场默认交给显卡解码，手柄面板
按键改为按 Switch 的位置对应。解压覆盖安装即可，存档、设置、着色器缓存都保留。

> **早期版本。** 端到端可用的是 Set up 与 Play 两条路径；围绕它们的启动器仍在完善。

## 我该下哪个文件？

| 文件 | 是什么 | 需要吗 |
|---|---|---|
| `XC2-package-dist-0.1.4.zip` | 玩家包：启动器、运行时、重编译器和着色器工具 | **要** —— 玩的就是这个 |
| `xc2-launcher-0.1.4-src.zip` | 启动器源码，想读或想自己编的人用 | 不用 |

## 本版变化

- **呈现不再拷贝一张游戏还在画的帧。** 呈现时把游戏的窗口纹理拷进 swapchain image，而这次拷贝只等 swapchain 的
  acquire 信号量；游戏的绘制是另一条提交，满帧率时拷贝可能排在它前面，送显的就是一张写了一半的帧——黄灰横条、白闪或
  黑闪。在 4060 Laptop 上，GPU 随后被拖到秒级落后，设备丢失。现在 `SubmitPrefix` 带出被呈现那一帧的绘制时间线，拷贝
  等它；`[gfx] frames_in_flight` 在 NVIDIA 上默认 1。同一台机器上实测：2 帧与 3 帧在飞 20–90 秒内必花屏，1 帧长跑
  干净。[#10](https://github.com/weile10000/xc2-ns2-recomp/issues/10) @Kain2k、
  [#4](https://github.com/weile10000/xc2-ns2-recomp/issues/4) @TheSeeOHZee、
  [#2](https://github.com/weile10000/xc2-ns2-recomp/issues/2) @ffhome 可能都是同一个故障；#2 与 #4 等报告者确认后再关。
- **启动器写下的呈现模式就是实际使用的那个。** 渲染器读 `[gfx] present_mode`，115 ms 后又被 `[display] vsync` 推导
  出的值覆盖，于是选 FIFO 得到的是 Immediate，画面撕裂。现在只有 `[gfx] present_mode` 说了算
  ([#12](https://github.com/weile10000/xc2-ns2-recomp/issues/12) @Kain2k)。
- **工厂修订 1 之前写的 `controls.ini` 不再走 Immediate。** 这类文件仍带着 `vsync = 0`，安装因此从未使用 FIFO。
  工厂修订 2 会把它改成 1，只改一次；玩家自己设过的值保持（#12）。
- **过场的音频有了自己的 voice。** audout（影片播放器的 PCM 流）与游戏的 `nn::audio` OutputStream 共用同一个
  XAudio2 sink。游戏用它自己的缓冲区大小减去该队列来报告可用帧数，所以影片把队列压深时游戏看到 0 帧可写、干脆不再写
  ——CG 静音；把队列压低时反过来，影片的写入把游戏的帧挤出去，游戏的时间线往前跳——声音变快。现在 audout 自己开一个
  sink，`x2_audio301` 回到 0.1.3 的代码，未改动。
- **4K 开场默认用显卡解码。** `[media] hwdec` 打开：4060 Laptop 上 30 fps，CPU 解码器只有 8–17。没有硬解能力的显卡
  会自动退回 CPU 路径；`hwdec = off` 仍可关闭。
- **手柄面板按键按 Switch 的位置对应。** 游戏的战技是按 Switch 手柄的位置排布的，所以默认布局就是 Switch 的位置：
  **B 在下、A 在右、Y 在左、X 在上。** 于是 Xbox 手柄最下面那颗是 B、它印着 A 的那颗在右边；Switch 手柄两种映射结果相同。
  想让按键按印着的字母来（提示 A 就按手柄上的 A），把 `controls.ini` 里的 `[pad] label_abxy` 改成 1，启动器手柄页也有同一个开关
  ([#14](https://github.com/weile10000/xc2-ns2-recomp/issues/14) @Kain2k)。工厂修订 2 会把老安装迁移到“按位置”一次；
  玩家自己改过的布局不会被动。
- **设备丢失会报驱动自己的 fault。** 驱动支持时启用 `VK_EXT_device_fault`；第一次提交失败会把驱动的 fault 描述与
  地址写在 `-4` 旁边（#10）。
- **启动时的 `0xD401` 会重试。** 60 GiB VAMM 在偶发的启动中失败；现在会重新启动那次运行，每次尝试各记一行。
- **源码用户**：`[nvn] fb_debug_hash` 让 `[nvn] fb_debug` 只盯一个 fragment shader（留空则报告所有最终成为自采样
  附件的绑定，上限 500 行）；开发链接会自己找到 libvorbis，开发版的影片解码因此与发布的 DLL 一致。

## 从 v0.1.3 升级

- 解压覆盖即可；`save/` 与 `shader_cache/` 可以拷过去，不需要重新 Set up。
- 两个默认值变了：影片硬解打开、手柄布局按位置。玩家自己设过的值都保留。
- 启动器与运行时现在来自同一个提交，每个 exe 在 `build.json` 里记录是哪一个。

## 已知问题

- **NVIDIA，[#10](https://github.com/weile10000/xc2-ns2-recomp/issues/10) 里那种长时游玩后的设备丢失**（@Kain2k，
  报告来自 RTX 5080）：仍未解决，其形态与这次修掉的不同；日志现在带驱动自己的描述，下一次报告可以直接用。
- **角色眨眼、说话时眼与嘴周围闪烁**（[#15](https://github.com/weile10000/xc2-ns2-recomp/issues/15) @Kain2k）：仍在查。
  本版带有对应诊断（`[nvn] fb_debug`、`[nvn] fb_debug_hash`），issue 里写了需要提供哪些数据。
- 4K 过场的第一帧可能闪一帧绿并短暂破碎，随后恢复。
- 画面仍比 1 代重编译版柔（[#9](https://github.com/weile10000/xc2-ns2-recomp/issues/9) @UrsineBear）：内部场景是 1280×720，
  默认 TAAU 是因为它不需要额外 DLL；FSR 与 DLSS 在启动器里可选。
- 云海闪烁、以及几何体与云海交界的蓝灰边仍然存在，**仅限 AMD 显卡**（位于游戏自己的体积雾内部）。
- **在 Windows 报告为 HDR 的显示器上**，过场画面可能整片发绿：影片帧还没有进入 HDR10 的编码链路。把 `nxrt.ini` 里的
  `[hdr] mode` 设为 `off`（启动器的视频页有同一个开关）即可恢复正常颜色。

## 开始之前

**Set up 要 8–15 分钟，它没有卡死。** 它先用你的 dump 重编译游戏的翻译单元、链接，然后翻译约 12,150 个着色器程序，
步骤列表全程都在动。之后第一次启动会编译 GPU 管线，约 20 秒（每个驱动一次）。

## 包内容

| 文件 | 大小 | sha256 |
|---|---|---|
| `XC2-package-dist-0.1.4.zip` | 216.7 MB（解压 643.4 MB） | `742DC8D9F9FA40AD764CC6ACC211DB67193C0E3023B9009FE8DD06FFE5424F4C` |
| `xc2-launcher-0.1.4-src.zip` | 0.5 MB | `F3DCA4DFDC4D1FBBBFFFFA7A466ED253DE91C9B3192A2E4B0D20632FBF2D7B44` |

包里不含任何游戏文件：exe 用你自己的 dump 在你机器上编出来，着色器也从它翻译。安装说明见
[README](https://github.com/weile10000/xc2-ns2-recomp#readme)。

包里带了 FFmpeg（GPL 共享构建），供影片的硬件解码器使用：它作为库被加载、未做修改，许可证与源码获取说明见
`licenses/FFMPEG-LICENSE.txt` 与 `THIRD_PARTY_NOTICES.md`。

## 致谢

- **[Goldoire/fefw-recomp](https://github.com/Goldoire/fefw-recomp)** —— 本项目的运行时来源：NVN/NVN2 重放、服务 HLE、
  着色器管线、exe + DLL 拆分都从这里起。
- [nxrecomp](https://github.com/drakolordx7/nxrecomp) —— 把游戏代码 lift 出来的静态重编译器。
- Ryujinx（MIT）—— 离线 harness 里的着色器翻译器；SDL3、Vulkan-Headers、VMA 等随包依赖列在包的 `licenses/` 里。
- [dav1d](https://code.videolan.org/videolan/dav1d) —— 影片视频解码；[libvorbis](https://github.com/xiph/vorbis) —— 影片声音。
- **[@capibawa](https://github.com/capibawa)** —— [nxnative 的 `xc2-ns2-profile` 分支](https://github.com/capibawa/nxnative/tree/xc2-ns2-profile)：
  四个启动开关，以及本项目沿用的宿主端影片/音频接管（`dm/host/hle_movie.c`、`hle_audio.c`）。
- 塑造了这一版的报告：@Kain2k（[#10](https://github.com/weile10000/xc2-ns2-recomp/issues/10)、
  [#12](https://github.com/weile10000/xc2-ns2-recomp/issues/12)、[#14](https://github.com/weile10000/xc2-ns2-recomp/issues/14)、
  [#15](https://github.com/weile10000/xc2-ns2-recomp/issues/15)）；仍未关闭的——@TheSeeOHZee
  （[#4](https://github.com/weile10000/xc2-ns2-recomp/issues/4)）、@ffhome（[#2](https://github.com/weile10000/xc2-ns2-recomp/issues/2)）、
  @UrsineBear（[#9](https://github.com/weile10000/xc2-ns2-recomp/issues/9)）。
