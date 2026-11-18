# XC2 NS2 Recomp v0.1.2 — the 4K cutscenes play

Since v0.1.1 the film path is finished: the 4K openings play at 30 fps with lip sync, and the retail build's sound comes
out. A small update: unzip over your install, saves and settings are kept.

> **Early version.** Set up and Play are the paths that work end to end; the launcher around them is still being built.
> The film now waits for the game while the game is still loading (see Known issues).

## Which file do I download?

| file | what it is | do I need it? |
|---|---|---|
| `XC2-package-dist.zip` | the player package: launcher, runtime, the lifter and the shader tools | **yes** — this is the one you play from |
| `xc2-launcher-0.1.1-src.zip` | the launcher's source; unchanged in 0.1.2 | no |

## What's new

- **The 4K cutscenes play.** The Golden Country opening and the other 4K films (AV1 3840×2160, 30 fps) used to freeze at
  1.3 s with the sound continuing; they now play at 30 fps with lip sync, at full resolution.
- **The film's sound is decoded on the host** (libvorbis). The picture no longer stops the moment the audio track opens,
  and the films have their sound back.
- **Retail 3.0.1 sound output**: the game's BGM, effects and voices now play through a host output path (XAudio2), and Opus
  voice is decoded in software instead of waiting for a hardware Opus the port does not have.
- **Set up says why a shader step failed**, printing the lines that failed instead of one word (reported in [#5](https://github.com/weile10000/xc2-ns2-recomp/issues/5) by @bobbymalaysia).
- **One-command reports**: `tools\python.exe tools\report.py` needs no PowerShell 7 and no .NET; it packs the log, the
  validation output and your settings into one zip.
- **A frozen game can be stopped with its report kept** from the launcher.
- **Game language follows the setting** (Simplified Chinese by default) and is handed to the game at start.
- **DLC is found in the package you extracted**, not in a list only a developer machine had ([#7](https://github.com/weile10000/xc2-ns2-recomp/issues/7), @Lhw-Arthas).
- **Package and launcher hardening**: the package ships only the run scripts a player may be asked to run, and the launcher
  refuses to run when it is older than its frontend (the build that opened to ERR_CONNECTION_REFUSED).
- **Fixes**: on NVIDIA the stencil plane is no longer offered to a float sampler, the black screen and lost device of [#4](https://github.com/weile10000/xc2-ns2-recomp/issues/4) (@TheSeeOHZee) and [#2](https://github.com/weile10000/xc2-ns2-recomp/issues/2) (@ffhome) (undefined behaviour in Vulkan, which AMD
  happens to tolerate); the freeze dump now ends with the last draws the replay submitted; the log says which config file
  was read and where each language value came from.
- **Source users**: libvpx is found through VCPKG_ROOT first, then the two known installs.

## Upgrading from v0.1.1

- Package users: replace the folder; `save/` and `shader_cache/` can be copied over. No new Set up is needed — only the
  runtime changed.
- Three film settings are now defaults: `[media] video_decoder = library`, `movie_timer_poke = 1`, `movie_pts_shift_ms = 100`.
  If lips are visibly off on your audio device, tune `movie_pts_shift_ms` in `nxrt.ini` (lower = video earlier).

## Known issues

- **The film waits while the game is still loading**: 1–20 s of stalls at the start of a CG, and an occasional audio drop
  in that window. The film itself is fine once the game has finished loading.
- The first frame can flash green for a moment on some runs.
- The A/V delay defaults to 100 ms; if lips are visibly off, tune `[media] movie_pts_shift_ms` in `nxrt.ini`.
- [#9](https://github.com/weile10000/xc2-ns2-recomp/issues/9) (@UrsineBear): the picture reads softer than the first game's recomp; under investigation.
- **Tested on AMD only.** NVIDIA and Intel are untested; the NVIDIA stencil fix above came from [#2](https://github.com/weile10000/xc2-ns2-recomp/issues/2) and [#4](https://github.com/weile10000/xc2-ns2-recomp/issues/4), and more reports
  help.
- Internal rendering is capped at 1440p by the game's own chain.
- Cloud-sea shimmer and the blue-grey rim where geometry meets the cloud sea remain (inside the game's own volumetric fog).

## Before you press Play

**Set up takes 8–15 minutes and it is not hung.** It recompiles the game's translation units from your dump, links them,
then translates about 12,150 shader programs; the step list moves the whole time. The first launch after that compiles GPU
pipelines for about 20 seconds (once per driver).

## Package

| file | size | sha256 |
|---|---|---|
| `XC2-package-dist.zip` | 158.9 MB (498.8 MB unpacked) | `499CF92E502983FDB929C76A630E623F77E7FECB18C68E0BB74BAEB929A33514` |
| `xc2-launcher-0.1.1-src.zip` | 0.5 MB | `14D9C1A122B4C70988D4373B64EBC67762689CEAF524F5D3B84E0C2A791E46DE` (unchanged) |

The package contains no game files: the executable is built on your machine from your own dump and the shaders are
translated from it. Installation: [README](https://github.com/weile10000/xc2-ns2-recomp#readme).

## Credits

- **[@capibawa](https://github.com/capibawa)** — [nxnative, branch `xc2-ns2-profile`](https://github.com/capibawa/nxnative/tree/xc2-ns2-profile): the
  four launch switches and the host-side movie/audio takeover that this release follows (`dm/host/hle_movie.c`, `hle_audio.c`).
- **[Goldoire/fefw-recomp](https://github.com/Goldoire/fefw-recomp)** — the Switch runtime this project is built on: NVN/NVN2 replay,
  service HLE, the shader pipeline and the exe + DLL split all started there.
- [nxrecomp](https://github.com/drakolordx7/nxrecomp) — the static recompiler that lifts the game's code.
- [dav1d](https://code.videolan.org/videolan/dav1d) — the film's video decoder; [libvorbis](https://github.com/xiph/vorbis) — its sound.
- The reporters whose issues shaped this release: @TheSeeOHZee ([#4](https://github.com/weile10000/xc2-ns2-recomp/issues/4)), @ffhome ([#2](https://github.com/weile10000/xc2-ns2-recomp/issues/2)), @bobbymalaysia ([#5](https://github.com/weile10000/xc2-ns2-recomp/issues/5)), @Lhw-Arthas ([#7](https://github.com/weile10000/xc2-ns2-recomp/issues/7)) and @UrsineBear ([#9](https://github.com/weile10000/xc2-ns2-recomp/issues/9)).
- Ryujinx (MIT) — the Maxwell shader translator in the offline harness; SDL3, Vulkan-Headers, VMA and the other vendored
  dependencies are listed in `licenses/` in the package.

---

# XC2 NS2 Recomp v0.1.2 —— 4K 过场动画能播了

自 v0.1.1 以来，影片这条链路补齐了：4K 开场 CG 以 30fps 正常播放、音画同步，零售版的游戏声音也能正常出来。
小更新：覆盖安装目录即可，存档与设置保留。

> **早期版本。** Set up 和 Play 是能端到端跑通的两条路；启动器周边还在建设中。
> CG 起播时如果游戏还在加载，影片会等加载（见“已知问题”）。

## 我该下哪个文件？

| 文件 | 是什么 | 需要吗 |
|---|---|---|
| `XC2-package-dist.zip` | 玩家包：启动器、运行时、举升器和着色器工具 | **需要** —— 就用它玩 |
| `xc2-launcher-0.1.1-src.zip` | 启动器源码；0.1.2 未改动 | 不需要 |

## 本版变化

- **4K 过场动画能播了**：黄金之国开场等 4K 影片（AV1 3840×2160，30fps）以前会在 1.3 秒冻住、声音继续走；
  现在 30fps 正常播放、音画同步，保持全分辨率。
- **影片声音由本机解码**（libvorbis）：音频轨打开时画面不再停住，影片恢复声音。
- **零售 3.0.1 版的声音输出**：BGM、音效、语音现在能正常出来（宿主 XAudio2 输出）；Opus 语音改用软件解码，
  不再等待移植版没有的硬件 Opus。
- **Set up 失败会说原因**：着色器步骤出错时直接打印失败的那几行（[#5](https://github.com/weile10000/xc2-ns2-recomp/issues/5)，@bobbymalaysia）。
- **一键报告**：`tools\python.exe tools\report.py` 不需要 PowerShell 7、不需要 .NET，把日志、校验输出和设置打成一个 zip。
- **卡死的游戏可以停下并保留报告**（启动器里）。
- **游戏语言跟随设置**（默认简体中文），启动时交给游戏。
- **DLC 从你自己提取的安装包里找**，不再依赖只有开发机才有的列表（[#7](https://github.com/weile10000/xc2-ns2-recomp/issues/7)，@Lhw-Arthas）。
- **包与启动器加固**：发布包只带玩家可能用到的运行脚本；启动器比自己的前端旧时拒绝运行（就是打开后
  ERR_CONNECTION_REFUSED 的那版）。
- **修复**：NVIDIA 上不再把 stencil 平面提供给浮点采样器，[#4](https://github.com/weile10000/xc2-ns2-recomp/issues/4)（@TheSeeOHZee）与 [#2](https://github.com/weile10000/xc2-ns2-recomp/issues/2)（@ffhome）的黑屏/设备丢失（Vulkan 里的未定义行为，A 卡恰好容忍）；
  冻结转储现在会以最后提交给 GPU 的 draws 结尾；日志会说明读的是哪个配置文件、语言值从哪来。
- **源码用户**：libvpx 先按 VCPKG_ROOT 找，再找两个已知安装位置。

## 从 v0.1.1 升级

- 包用户：替换目录即可，`save/` 和 `shader_cache/` 可以拷过去；只有运行时变了，**不需要重新 Set up**。
- 三项影片设置已成为默认值：`[media] video_decoder = library`、`movie_timer_poke = 1`、`movie_pts_shift_ms = 100`。
  如果你的声卡上明显不同步，改 `nxrt.ini` 里的 `movie_pts_shift_ms`（数值越小视频越早）。

## 已知问题

- **游戏还在加载时，影片会等加载**：CG 开头约 1–20 秒的停顿，这段时间偶发丢一点声音。加载结束后影片本身正常。
- 个别运行首帧会闪一下绿色（不到 1 秒）。
- 音画补偿默认 100ms；明显不同步时改 `[media] movie_pts_shift_ms`。
- [#9](https://github.com/weile10000/xc2-ns2-recomp/issues/9)（@UrsineBear）：画面比 1 代重编译版偏软，仍在排查。
- **目前只在 AMD 上测过**：N 卡、I 卡未验证；上面那条 N 卡修复来自 [#2](https://github.com/weile10000/xc2-ns2-recomp/issues/2) 与 [#4](https://github.com/weile10000/xc2-ns2-recomp/issues/4) 的报告，更多反馈很有帮助。
- 游戏自身链路把内部渲染上限锁在 1440p。
- 云海闪烁、几何与云海交界的蓝灰描边仍在（在游戏自己的体积雾里）。

## 开始之前

**Set up 要 8–15 分钟，它没有卡死。** 它用你的 dump 重编游戏的翻译单元、链接，再翻译约 12,150 个着色器程序；
页面上的步骤表一直在动。之后第一次启动还要编译 GPU 管线，约 20 秒，每个驱动一次。

## 包内容

| 文件 | 大小 | sha256 |
|---|---|---|
| `XC2-package-dist.zip` | 158.9 MB（解压 498.8 MB） | `499CF92E502983FDB929C76A630E623F77E7FECB18C68E0BB74BAEB929A33514` |
| `xc2-launcher-0.1.1-src.zip` | 0.5 MB | `14D9C1A122B4C70988D4373B64EBC67762689CEAF524F5D3B84E0C2A791E46DE`（未改动） |

包里不含游戏文件：exe 在你的机器上从你的 dump 构建，着色器从它翻译。安装见
[README](https://github.com/weile10000/xc2-ns2-recomp#readme)。

## 致谢

- **[@capibawa](https://github.com/capibawa)** —— [nxnative 的 `xc2-ns2-profile` 分支](https://github.com/capibawa/nxnative/tree/xc2-ns2-profile)：
  本版沿用的四个启动参数与宿主端影片/音频接管（`dm/host/hle_movie.c`、`hle_audio.c`）。
- **[Goldoire/fefw-recomp](https://github.com/Goldoire/fefw-recomp)** —— 本项目的运行时基座：NVN/NVN2 重放、服务层 HLE、
  着色器管线、exe + DLL 的拆分都源自那里。没有那个项目，就没有这次重编译。
- [nxrecomp](https://github.com/drakolordx7/nxrecomp) —— 把游戏代码举升出来的静态重编译器。
- [dav1d](https://code.videolan.org/videolan/dav1d) —— 影片视频解码；[libvorbis](https://github.com/xiph/vorbis) —— 影片声音。
- 本版修复对应的 issue 报告者：@TheSeeOHZee（[#4](https://github.com/weile10000/xc2-ns2-recomp/issues/4)）、@ffhome（[#2](https://github.com/weile10000/xc2-ns2-recomp/issues/2)）、@bobbymalaysia（[#5](https://github.com/weile10000/xc2-ns2-recomp/issues/5)）、@Lhw-Arthas（[#7](https://github.com/weile10000/xc2-ns2-recomp/issues/7)）、@UrsineBear（[#9](https://github.com/weile10000/xc2-ns2-recomp/issues/9)）。
- Ryujinx（MIT）—— 离线 harness 里的 Maxwell 着色器翻译器；SDL3、Vulkan-Headers、VMA 等 vendored 依赖见包里的 `licenses/`。

