# XC2 NS2 Recomp v0.1.3 — the picture stops going in and out of focus

A small update with one setting people asked for, and three fixes that make a failed Set up say what is wrong instead of
an error code. Unzip over your install; saves, settings and the shader cache are kept.

> **Early version.** Set up and Play are the paths that work end to end; the launcher around them is still being built.

## Which file do I download?

| file | what it is | do I need it? |
|---|---|---|
| `XC2-package-dist-0.1.3.zip` | the player package: launcher, runtime, the lifter and the shader tools | **yes** — this is the one you play from |
| `xc2-launcher-0.1.3-src.zip` | the launcher's source, for people who want to read or build it | no |

## What's new

- **Lock render resolution** (Settings → Upscaler). The game lowers its internal resolution by itself when a frame gets
  expensive, which is why the picture slides in and out of focus on the same spot. This holds it at 1280×720, so the
  upscaler always gets the same input. Cost: about 1–2 fps in heavy scenes, and some metal surfaces shimmer slightly.
  Default off.
- **The 4K films play without freezing.** A second or two in, the picture used to stop for 7–8 seconds at a time while
  the game itself kept running. The player's per-frame timer was being marked due by a helper thread that gave up the
  first time the timer looked stopped, and never came back. One ticker keeps it due now: no stall above 0.13 s for the
  rest of the film, and the 2.2 s at the start is the game still loading (unchanged).
- **Film sound and picture line up by default**: the picture is delayed 110 ms, which is what the console-to-PC audio
  path costs on this device (tune `[media] movie_pts_shift_ms` if lips are off), and the host AV1 decoder now uses half
  the cores (4–8) for the 4K openings.
- **Set up says why a shader step failed.** A headless run that never got as far as drawing used to reach the page as
  "exited with code 1". It now names the reason — most often a GPU driver older than Vulkan 1.3 — and what to do, from
  the run's own log.
- **A run that never drew is no longer recorded as a finished Set up.** That is what left a cache of 12,132 programs and
  a black title screen on a machine whose driver was too old; the cache stays as the archive left it, and the step says
  so instead of passing.
- **Start-up failures name the GPU driver and the Vulkan version it reports**, for example
  `NVIDIA GeForce RTX 3050 reports Vulkan 1.2.175 (driver 576.02): this build needs Vulkan 1.3`. No more guessing from a
  bare `-9`.
- **Set up translates 563 shader programs on the fast path again.** The shader translator lost a call-argument patch, so
  those programs fell back to a slower mode (up to six times larger, and much slower to compile). They are back to
  normal size; the same patch also stops an atomic operation from running twice where its result is used once.
- **Source users**: the development link finds libvpx on its own (it was missing from `build-boot.ps1`), and
  `[nvn] rt_size_bt` prints the game's dynamic-resolution ladder while it moves.

## Upgrading from v0.1.2

- Package users: replace the folder; `save/` and `shader_cache/` can be copied over. No new Set up is needed.
- The new cache entries the translator fix produces only arrive on a fresh Set up; an existing cache keeps working as it
  is, so there is no reason to rebuild one.
- If you had `[upscale] lock_render_size` in `nxrt.ini` by hand, the new setting writes the same key.

## Known issues

- **The film waits while the game is still loading**: 1–20 s of stalls at the start of a CG. Unchanged.
- The first frame can flash green for a moment on some runs.
- [#9](https://github.com/weile10000/xc2-ns2-recomp/issues/9) (@UrsineBear): the picture reads softer than the first
  game's recomp. The internal scene is still 1280×720; "Lock render resolution" makes that steady, it does not raise it.
- **NVIDIA**: [#2](https://github.com/weile10000/xc2-ns2-recomp/issues/2) (RTX 4060 Ti) and
  [#4](https://github.com/weile10000/xc2-ns2-recomp/issues/4) (RTX 3070) stay open; a test pass on a 4060 laptop is
  planned. `#10` (RTX 5080, "stuck loading") is a lost device caused by a stencil sampler the driver does not accept —
  the report line for it is now always on, which is how the next occurrence can be diagnosed.
- Cloud-sea shimmer and the blue-grey rim where geometry meets the cloud sea remain (inside the game's own volumetric
  fog).
- **Tested on AMD only.**

## Before you press Play

**Set up takes 8–15 minutes and it is not hung.** It recompiles the game's translation units from your dump, links them,
then translates about 12,150 shader programs; the step list moves the whole time. The first launch after that compiles GPU
pipelines for about 20 seconds (once per driver).

## Package

| file | size | sha256 |
|---|---|---|
| `XC2-package-dist-0.1.3.zip` | 158.8 MB (498.8 MB unpacked) | `823C036621950441E5BB345F948512A7C136B380C32D1151D57216C495A497D1` |
| `xc2-launcher-0.1.3-src.zip` | 0.5 MB | `0D96BF4F5BE959CCB1FCA2E5ECCC243081CEB95CA6FB062F27B2BDE2FD8877B8` |

The package contains no game files: the executable is built on your machine from your own dump and the shaders are
translated from it. Installation: [README](https://github.com/weile10000/xc2-ns2-recomp#readme).

## Credits

- **[@capibawa](https://github.com/capibawa)** — [nxnative, branch `xc2-ns2-profile`](https://github.com/capibawa/nxnative/tree/xc2-ns2-profile): the
  four launch switches and the host-side movie/audio takeover this project follows (`dm/host/hle_movie.c`, `hle_audio.c`).
- **[Goldoire/fefw-recomp](https://github.com/Goldoire/fefw-recomp)** — the Switch runtime this project is built on: NVN/NVN2 replay,
  service HLE, the shader pipeline and the exe + DLL split all started there.
- [nxrecomp](https://github.com/drakolordx7/nxrecomp) — the static recompiler that lifts the game's code.
- [dav1d](https://code.videolan.org/videolan/dav1d) — the film's video decoder; [libvorbis](https://github.com/xiph/vorbis) — its sound.
- The reports that shaped this release: @Kain2k ([#10](https://github.com/weile10000/xc2-ns2-recomp/issues/10)),
  @fmalust ([#11](https://github.com/weile10000/xc2-ns2-recomp/issues/11)); and the ones still open — @TheSeeOHZee
  ([#4](https://github.com/weile10000/xc2-ns2-recomp/issues/4)), @ffhome ([#2](https://github.com/weile10000/xc2-ns2-recomp/issues/2)),
  @UrsineBear ([#9](https://github.com/weile10000/xc2-ns2-recomp/issues/9)).
- Ryujinx (MIT) — the shader translator in the offline harness; SDL3, Vulkan-Headers, VMA and the other vendored
  dependencies are listed in `licenses/` in the package.

---

# XC2 NS2 Recomp v0.1.3 —— 画面不再忽清忽糊

一次小更新：一个大家要的开关，外加三处"出错时说人话"的修复。解压覆盖安装即可，存档、设置、着色器缓存都保留。

> **早期版本。** Set up 和 Play 是能完整走通的路径，围绕它们的启动器还在做。

## 我该下哪个文件？

| 文件 | 是什么 | 需要吗 |
|---|---|---|
| `XC2-package-dist-0.1.3.zip` | 玩家包：启动器、运行时、重编译器和着色器工具 | **要** —— 玩的就是这个 |
| `xc2-launcher-0.1.3-src.zip` | 启动器源码，想读或想自己编的人用 | 不用 |

## 本版变化

- **锁定渲染分辨率**（设置 → 升采样）。游戏会在某帧变贵时自己降内部分辨率，所以同一个位置看起来会忽清忽糊。这个
  开关把它钉在 1280×720，升采样器的输入就恒定了。代价：重场景约低 1–2 帧，部分金属表面轻微闪烁。默认关。
- **4K 过场不再卡住**。以前放一两秒后画面会停 7–8 秒，游戏本体照常在跑。原因是播放器的逐帧定时器由一个辅助线程从宿主"推"到期，
  而那个线程第一次看到定时器"已停"就退出了，再也没回来。现在改成一个常驻 ticker：整段片子里最长间隔 0.13 秒，开头那 2.2 秒是
  游戏还在加载（老问题，未变）。
- **音画默认对上了**：画面整体延后 110 ms（这是这台机器上 XAudio2 队列加设备缓冲的代价；口型不对就调
  `[media] movie_pts_shift_ms`），4K 过场的宿主 AV1 解码线程改成"核数一半、4–8 个"。
- **Set up 会说清 shader 那步为什么失败**。一次"连画面都没画出来"的无窗口运行，过去在页面上只是一句
  "exited with code 1"；现在它会从那次运行自己的日志里读出原因（最常见是显卡驱动老于 Vulkan 1.3）和该怎么办。
- **没画出东西的运行不会再被记成"装好了"**。就是这一条让驱动过旧的机器留下 12,132 个程序的缓存和黑屏标题；
  现在缓存保持档案翻译的那一半，步骤直接报失败。
- **启动失败会点名显卡和它报的 Vulkan 版本**，例如
  `NVIDIA GeForce RTX 3050 reports Vulkan 1.2.175 (driver 576.02): this build needs Vulkan 1.3`，不用再从一个光秃秃的
  `-9` 猜。
- **Set up 重新把 563 个着色器程序放回快速路径**。着色器翻译器丢了一个 call-argument 补丁，这些程序退回到慢速模式
  （最大到 6 倍体积、编译也慢得多）。现在体积恢复正常；同一个补丁还修掉了"结果只用一次时原子操作被执行两遍"。
- **源码用户**：开发链接自己会找 libvpx（`build-boot.ps1` 之前漏了）；`[nvn] rt_size_bt` 会打出游戏动态分辨率的
  档位跳动。

## 从 v0.1.2 升级

- 包用户：替换文件夹即可，`save/` 和 `shader_cache/` 可以拷过去。不需要重新 Set up。
- 翻译器修复带来的新缓存条目只会在全新 Set up 时出现；已有缓存照常能用，没有理由重建。
- 如果你之前在 `nxrt.ini` 里手写过 `[upscale] lock_render_size`，新开关写的是同一个键。

## 已知问题

- **过场动画开始时游戏还在加载**：CG 开头 1–20 秒的停顿，未变。
- 某些运行第一帧会闪一下绿色。
- [#9](https://github.com/weile10000/xc2-ns2-recomp/issues/9)（@UrsineBear）：画面比一代重编译软。内部场景仍然是
  1280×720；"锁定渲染分辨率"只是让它稳定，并没有提高它。
- **N 卡**：[#2](https://github.com/weile10000/xc2-ns2-recomp/issues/2)（4060 Ti）和
  [#4](https://github.com/weile10000/xc2-ns2-recomp/issues/4)（3070）仍开着，计划用 4060 笔记本集中测一次。
  `#10`（5080，"卡在 Loading"）是设备丢失，起因是一个驱动不接受的模板采样器 —— 那行报告现在默认记录，
  下一次出现就能定位。
- 云海闪烁、几何与云海交界处的蓝灰边仍然存在（在游戏自己的体积雾里）。
- **只在 AMD 上测过。**

## 开始之前

**Set up 要 8–15 分钟，它没有卡死。** 它会用你自己的 dump 重编译游戏的编译单元、链接，然后翻译约 12,150 个着色器
程序；步骤列表一直在动。之后第一次启动会编译 GPU 管线，约 20 秒（每个驱动一次）。

## 包内容

| 文件 | 大小 | sha256 |
|---|---|---|
| `XC2-package-dist-0.1.3.zip` | 158.8 MB (498.8 MB unpacked) | `823C036621950441E5BB345F948512A7C136B380C32D1151D57216C495A497D1` |
| `xc2-launcher-0.1.3-src.zip` | 0.5 MB | `0D96BF4F5BE959CCB1FCA2E5ECCC243081CEB95CA6FB062F27B2BDE2FD8877B8` |

包里没有任何游戏文件：可执行文件是在你的机器上用你自己的 dump 编出来的，着色器也是从它翻译的。安装见
[README](https://github.com/weile10000/xc2-ns2-recomp#readme)。

## 致谢

- **[@capibawa](https://github.com/capibawa)** —— [nxnative 的 `xc2-ns2-profile` 分支](https://github.com/capibawa/nxnative/tree/xc2-ns2-profile)：
  本项目沿用的四个启动参数与宿主端影片/音频接管（`dm/host/hle_movie.c`、`hle_audio.c`）。
- **[Goldoire/fefw-recomp](https://github.com/Goldoire/fefw-recomp)** —— 本项目的运行时基座：NVN/NVN2 重放、服务层 HLE、
  着色器管线、exe + DLL 的拆分都源自那里。没有那个项目，就没有这次重编译。
- [nxrecomp](https://github.com/drakolordx7/nxrecomp) —— 把游戏代码举升出来的静态重编译器。
- [dav1d](https://code.videolan.org/videolan/dav1d) —— 影片视频解码；[libvorbis](https://github.com/xiph/vorbis) —— 影片声音。
- 本版修复对应的报告者：@Kain2k（[#10](https://github.com/weile10000/xc2-ns2-recomp/issues/10)）、
  @fmalust（[#11](https://github.com/weile10000/xc2-ns2-recomp/issues/11)）；尚未解决的
  @TheSeeOHZee（[#4](https://github.com/weile10000/xc2-ns2-recomp/issues/4)）、
  @ffhome（[#2](https://github.com/weile10000/xc2-ns2-recomp/issues/2)）、
  @UrsineBear（[#9](https://github.com/weile10000/xc2-ns2-recomp/issues/9)）。
- Ryujinx（MIT）—— 离线 harness 里的着色器翻译器；SDL3、Vulkan-Headers、VMA 等 vendored 依赖见包里的 `licenses/`。
