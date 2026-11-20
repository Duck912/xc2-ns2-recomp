# XC2 NS2 Recomp v0.1.4 — cutscenes play, with their sound

**XC2 NS2 Recomp** runs *Xenoblade Chronicles 2 — Nintendo Switch 2 Edition* (retail 3.0.1) natively on Windows and Vulkan.
It is a static recompilation: the game's modules are lifted to C++ and the runtime replays their NVN/NVN2 command stream on
Vulkan. It is not an emulator, and the package contains no game file — the executable is built on your PC from your own dump.

## Which file do I download?

| file | what it is | do I need it? |
|---|---|---|
| `XC2-package-dist-0.1.4.zip` | the player package: launcher, runtime, the lifter and the shader tools | **yes** — this is the game |
| `xc2-launcher-0.1.4-src.zip` | the launcher's source, for people who want to read or build it | no |

## What's new

- **A cutscene now keeps its sound, and the sound stays in sync.** The film player and the game's own audio used to play
  through one XAudio2 voice. During a cutscene one of them always lost: when the film's queue was deep the game found no room
  and stopped writing (a silent cutscene), and without that the film's writes pushed the game's frames out and its music
  skipped ahead (the sound ran fast). The film player now opens a voice of its own; the game's audio path is unchanged.
- **The face buttons follow their position on the pad, not the letter printed on it** (issue 14). An Xbox pad's A is the
  bottom button, and it used to press the Switch button that sits on the right, so the Arts prompts answered the neighbouring
  slot. By position the bottom button is the bottom prompt on every pad; a Switch pad maps the same either way. Existing
  installs are moved to the new default once by the runtime's factory revision 2 — a layout you picked yourself stays.
- The host film-audio decoder is off (`[media] movie_audio`, 0): in these containers the film's own audio track is a
  placeholder of one byte per packet, and a cutscene's sound comes from the game's own audio system.

## Upgrading from v0.1.3

Unpack over the old folder. Your `controls.ini` is kept; the pad layout is the only default that changes, and only if you
never changed it. Shader caches stay valid.

## Known issues

- **The first second of a 4K cutscene can flash a green frame and break up briefly** before it settles. The film is 4K and
  starts playing immediately; a preload would hide it.
- NVIDIA device-lost on the 50-series (#2/#4/#10) is still open.
- `[media] hwdec` still defaults off: hardware AV1/VP9 decoding works (4K at 30 fps) but is opt-in.
- The 60 GiB VAMM setup can still fail with `0xD401` on a rare start (#171).
- The first visit to a new area runs at ~20 fps while pipelines compile; it settles once the cache is warm.

## Before you press Play

You need your own dump of the retail game (`main`, `sdk`, `subsdk0`…`subsdk3`, `rtld` plus the romfs). The launcher's
**Set up** builds the executable and the shader cache once (8–15 minutes); after that **Play** starts in seconds. Nothing here
ships a game file, and CI checks that it never does.

## Package

| file | size | sha256 |
|---|---|---|
| `XC2-package-dist-0.1.4.zip` | see the release page | see the release page |
| `xc2-launcher-0.1.4-src.zip` | see the release page | see the release page |

## Credits

This stands on other people's work: [nxrecomp](https://github.com/drakolordx7/nxrecomp) (the lifter),
[fefw-recomp](https://github.com/Goldoire/fefw-recomp) (the runtime this forks), [dav1d](https://code.videolan.org/videolan/dav1d)
(film video), [libvorbis](https://github.com/xiph/vorbis) and libvpx (film and video decoding), and
[Ryujinx](https://ryujinx.app/) (service behaviour and shader translation). Thanks also to
[@capibawa](https://github.com/capibawa) for the Switch 2 profile in nxnative. Bug reports from @Kain2k, @ffhome,
@TheSeeOHZee, @UrsineBear, @Nolaye and @Goldoire shaped this release.

---

# XC2 NS2 Recomp v0.1.4 —— 过场能播，而且有声音

**XC2 NS2 Recomp** 把《异度之刃 2 — Nintendo Switch 2 Edition》（零售 3.0.1）静态重编译到 Windows + Vulkan：
把游戏的模块 lift 成 C++，由运行时在 Vulkan 上重放它们的 NVN/NVN2 命令流。它不是模拟器；包里没有任何游戏文件，
exe 是在你自己的电脑上、用你自己的 dump 编出来的。

## 我该下哪个文件？

| 文件 | 是什么 | 需要吗 |
|---|---|---|
| `XC2-package-dist-0.1.4.zip` | 玩家包：启动器、运行时、重编译器和着色器工具 | **要** —— 玩的就是这个 |
| `xc2-launcher-0.1.4-src.zip` | 启动器源码，想读或想自己编的人用 | 不用 |

## 本版变化

- **过场（CG）既保住了声音，音画也对得上了。** 影片播放器和游戏自己的音频原来共用一个 XAudio2 voice，过场期间总有
  一方吃亏：影片把队列占深时游戏问不到空位、干脆不写（CG 静音）；反过来影片的写入把游戏的帧挤掉，游戏的时间线往前跳
  （声音听起来变快）。现在影片播放器用独立的 voice，游戏那条音频路径一行未改。
- **手柄面板按键按“位置”对应，而不是按印在上面的字母**（issue 14）。Xbox 手柄的 A 在最下面，原来它按下的是 Switch
  右侧那颗键，于是战技（Arts）提示答到了旁边一格。按位置对应后，最下面的按键就是最下面那个提示；Switch 手柄两种映射
  结果相同。老安装由运行时的工厂修订 2 自动迁移一次；**你自己改过的布局不会被覆盖**。
- 影片自带的音轨在宿主上解码默认关闭（`[media] movie_audio` = 0）：这些容器里那条音轨是每包 1 字节的占位，
  过场的声音来自游戏自己的音频系统。

## 从 v0.1.3 升级

直接解压覆盖旧目录。`controls.ini` 会保留；默认值里只有手柄布局变了，而且只在你从未改过它时生效。着色器缓存继续可用。

## 已知问题

- **4K 过场的头一秒可能闪一帧绿、并短暂破碎**，然后恢复正常。影片是 4K 且立即开始播放，预加载能盖住这一段。
- NVIDIA 50 系（#2/#4/#10）的 device lost 仍未解决。
- `[media] hwdec` 仍默认关闭：硬解 AV1/VP9 可用（4K 30 fps），但需要手动打开。
- 60 GiB 的 VAMM 偶发 `0xD401`（#171）。
- 首次进入新区域约 20 fps（管线编译），缓存热了恢复。

## 开始之前

你需要自己的零售版 dump（`main`、`sdk`、`subsdk0`…`subsdk3`、`rtld` 与 romfs）。启动器的 **Set up** 会一次性
编出 exe 与着色器缓存（8–15 分钟），之后 **Play** 秒进。这里不含任何游戏文件，CI 会检查这一点。

## 包内容

| 文件 | 大小 | sha256 |
|---|---|---|
| `XC2-package-dist-0.1.4.zip` | 见发布页 | 见发布页 |
| `xc2-launcher-0.1.4-src.zip` | 见发布页 | 见发布页 |

## 致谢

站在别人的工作上：[nxrecomp](https://github.com/drakolordx7/nxrecomp)（lifter）、
[fefw-recomp](https://github.com/Goldoire/fefw-recomp)（本项目的运行时来源）、[dav1d](https://code.videolan.org/videolan/dav1d)
（影片视频）、[libvorbis](https://github.com/xiph/vorbis) 与 libvpx（影片与视频解码）、
[Ryujinx](https://ryujinx.app/)（服务行为与着色器翻译）。也感谢 [@capibawa](https://github.com/capibawa) 在 nxnative
里的 Switch 2 profile。本版的 bug 报告来自 @Kain2k、@ffhome、@TheSeeOHZee、@UrsineBear、@Nolaye 与 @Goldoire。
