# Changelog

Dated milestones. The §-numbered evidence sections named on the right are part of the project's internal
notes, which are not published with this repository.

## 2026-11-18 · 0.1.2 (small update)

- **The 4K openings play.** The Golden Country CG (`stream/movie/mv11010100.webm`: AV1 3840x2160 30 fps + Vorbis 48 kHz)
  used to freeze at 1.3 s with the sound continuing; it now runs at 30 fps with lip sync. Four causes: the movie library
  submits the whole film from the player's own thread and a synchronous 4K AV1 decode per packet left it no time to hand
  frames over, so the player dropped every frame as late (`VideoFrame::GetBuffer` was called once); the fence it arms
  after `AcquireOutputBuffer` has to be complete by the time the call returns, or it waits out its own timeout for
  seconds; the image pool is read before the first picture is placed in it, and an all-zero NV12 image is bright green;
  and the audio output runs ~100 ms behind, so the picture has to wait as well.
- **The film's sound is decoded on the host** (`movie::AudioDecoder` on libvorbis). Before this the library waited for
  audio frames its MediaCodec path never produced, which is what stopped the picture the moment the audio track opened.
- **Host audio for the retail build**: SDK 21's `nn::audio::OutputStream` writes straight into the runtime's XAudio2
  sink, and hwopus is answered by the SDK's own software Opus decoder.
- **Defaults that make the film work out of the box**: `[media] video_decoder = library`, `movie_timer_poke = 1` (the
  SDK's periodic timer never comes due inside the player's MultiWait, so the host marks it), `movie_pts_shift_ms = 100`
  (video delay for the audio output latency; the launcher's audio-latency setting can override it).
- **Credits**: the four launch switches and the host-side movie/audio replacement follow **@capibawa**'s
  [nxnative, branch `xc2-ns2-profile`](https://github.com/capibawa/nxnative/tree/xc2-ns2-profile) (`dm/host/hle_movie.c`,
  `dm/host/hle_audio.c`); the runtime is built on **@Goldoire**'s
  [fefw-recomp](https://github.com/Goldoire/fefw-recomp), and the recompiler is **@drakolordx7**'s
  [nxrecomp](https://github.com/drakolordx7/nxrecomp). Video decodes with [dav1d](https://code.videolan.org/videolan/dav1d),
  sound with [libvorbis](https://github.com/xiph/vorbis).
- **Known**: while the game is still loading, the film waits for it (1-20 s of stalls and an occasional audio drop at the
  start); the first frame can flash green for a moment on some runs.

## 2026-11-18

- **A release can be installed from your own dump**: point the launcher at it — a `.nup` package or a folder of
  `exefs/ + romfs/` — and it is unpacked into `base/{exefs,romfs}`, `updates/` and `dlc/<title id>/romfs`; setup
  reads the game's own files from there and nothing is shipped with them. Packages are still built from the
  player's dump.
- **The package carries `spirv-val.exe`** (SPIRV-Tools, Apache-2.0): the shader harness spawns it once per
  translated block, and without it Set up failed on any machine that had no Vulkan SDK installed.
- **Play starts the game from the install itself.** No more `tools\run\play-301.cmd` looked up above the exe:
  the launcher spawns `xc2_boot.exe` with the switches from `<install>\launch.env` (one list, written by the
  setup engine), and a package always uses its own Python.
- **DLC loads, and its openings play.** `ingest` links the dump's `dlc/` to `game\dlc-301` (all seven add-ons
  served), and `game::Info::movie_video_decoder` is on, so the 4K AV1 `.webm` openings decode through dav1d
  (53 packets / 14 ms each, 59.9 fps).
- **Three picture fixes**: the deferred lighting pass now gets the front-face convention it is drawn with
  (without it the whole frame stays at the G-buffer's albedo, which reads as black textures); the light-list
  registration mask is derived for every shader, not the built-in eleven (the black rectangle at the stairs);
  and `present_ahead = 0`, so the guest no longer runs a frame ahead of the replay.
- **The shader cache is complete for the dump and grows while playing**: the archive scan installs 12,132
  programs, the container pass adds 12 compute ones, the first headless run names the 5 that exist in no file
  (12,149), and after every session the launcher translates whatever the game asked for and the cache lacked.
- **Game language is a setting** (zh-Hans default, zh-Hant / en-US / ja), written to `[system] language`.
- **Logs no longer carry the account name**: the home folder is `%USERPROFILE%` and commands are logged by
  program name.
## 2026-11-16

- **60 fps at 1080p, 1440p and 4K** on the port and most areas (59–60); the open plain runs 43–52 with a
  frame time of 18–23 ms. 4K costs no more than 1440p — the internal chain is fixed at 720p → 1440p and the
  last step is a blit. (§97)
- **VRR is opt-in** (`[gfx] present_mode = fifo_relaxed`): a late frame is presented at once instead of being
  quantised to the next vblank. The default stays `fifo` because most players have no VRR. (§97.15)
- **FSR 4.1.2 is safe under dynamic resolution**: one FidelityFX context per input size, 6 contexts and 0
  crashes over a session that stepped the resolution repeatedly. FSR 4.1.2 is no slower than TAAU. (§95.19, §97.4)
- **Replay cost cut from 9.7–15.4 ms to 5.3–6.8 ms** (later 8.4–11 ms at higher draw counts): four `getenv`
  calls per draw inside `build_key`, a per-binding config lookup in `feedback_prepare`, and a handful of
  per-draw clocks and hooks. (§96)
- **Two upstream 0.2.0 wins ported**: `push_uniforms` + `ubo_only_rebind` (their defaults) cut the open plain's
  replay by 32% (`sets` 0.67 → 0.40 µs/draw), and the sampled-view format memo plus `gfx_ssbo_readonly`
  (SPIR-V reflection: `DescriptorBinding::written`) cut it a further 14% at matched draw counts. (§97.11, §98.9)
- **The GPU measured at 7.28 ms**, not the 14 ms the frame-minus-replay estimate suggested: render passes
  4.4 ms, feedback copy 1.54 ms, gaps 0.79 ms. (`[prof] gpu_passes`, §97.13)
- **Closed as dead ends**: `split_draws` (rendering errors), off-screen draw culling (the census is 0 — the game
  already culls), the feedback copy (its cost is the pass break, not bandwidth). (§97.10, §97.14, §97.15)

## 2026-11-15

- **The retail 3.0.1 route boots**: 128 GiB alias region, Opus and `nn::audio` on the host, the tensor-core
  upscaler translated from Ampere SASS, in-game at 30.0 fps with a full cache of 21,171 shaders. (§89–§90)

## 2026-11-14

- Frame-rate census (164 frame-locked counters), the pkg7 (Switch 2 add-on) analysis and the DLC chain. (§58–§88)

## 2026-11-13

- Early-Z mask fix, 1080p output, the replay phase split, 60/120 Hz pacing. (§44–§56)

## 2026-11-12

- The volumetric-fog pipeline identified; the first 60 Hz experiments. (§42–§51)

## 2026-11-11

- Lighting: light lists, probe volumes, and the integer render-target logic op. (§31–§41)

## 2026-11-10

- Models and materials: block-linear layouts, tile modes, texture formats, the deferred pass. (§21–§30)

## 2026-11-09

- First static lift of a Switch title (4 modules, 90,691 functions) and the NVN → Vulkan replay rendering a
  frame. (§1–§20)
