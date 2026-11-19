# Modifications to fefw-recomp

This directory is a **modified fork** of [Goldoire/fefw-recomp](https://github.com/Goldoire/fefw-recomp),
vendored into the Xenoblade Chronicles 2 NS2E recomp project. Upstream base and provenance: [UPSTREAM.md](UPSTREAM.md).

| | |
|---|---|
| upstream | https://github.com/Goldoire/fefw-recomp |
| licence | GPL-3.0-or-later (see [LICENSE](LICENSE) and [LEGAL.md](LEGAL.md)) |
| fork base commit in this repository | `6f1d964` (2026-11-12, baseline: 26 rounds of XC2 NS2 recomp) |
| files changed since the base | 50 |
| generated from | `git diff --name-only 6f1d964..HEAD -- third_party/fefw-recomp` |

> **Why this file and not per-file headers.** GPL-3.0 section 5(a) requires the work to carry prominent notices
> that it was modified, with a relevant date. This file is that notice, and it is authoritative. Per-file
> `// Modified ...` headers are deliberately not added: the project's internal notes cite line numbers of these files
> (for example `nvn_texture_registry.cpp:305`), and a one-line header shifts every reference. If a file is
> later copied out of this fork on its own, add the header to that copy.

## Changed files (date = last change)

| file | date | change |
|---|---|---|
| `UPSTREAM.md` | 2026-11-16 | 3.0.1 bring-up through 2026-11-16: rim audit, cloud shimmer, upscaler chain, FSR version override |
| `runtime/include/nxrt/extras.h` | 2026-11-16 | replay: pipe/fb hot-path audit (round 45, 9.7-15.4 -> 5.3-6.8 ms); fsr_follow_size; fs trace_stack_file off; s |
| `runtime/include/nxrt/gfx.h` | 2026-11-16 | replay: pipe/fb hot-path audit (round 45, 9.7-15.4 -> 5.3-6.8 ms); fsr_follow_size; fs trace_stack_file off; s |
| `runtime/include/nxrt/memory.h` | 2026-11-16 | 3.0.1 bring-up through 2026-11-16: rim audit, cloud shimmer, upscaler chain, FSR version override |
| `runtime/include/nxrt/platform.h` | 2026-11-16 | 3.0.1 bring-up through 2026-11-16: rim audit, cloud shimmer, upscaler chain, FSR version override |
| `runtime/include/nxrt/services_api.h` | 2026-11-16 | 3.0.1 bring-up through 2026-11-16: rim audit, cloud shimmer, upscaler chain, FSR version override |
| `runtime/include/nxrt/svc.h` | 2026-11-16 | 3.0.1 bring-up through 2026-11-16: rim audit, cloud shimmer, upscaler chain, FSR version override |
| `runtime/scripts/gen_earlyz_mask_shaders.py` | 2026-11-13 | nvn: the light list registration mask is derived from the list after every list draw - the black rectangle (HA |
| `runtime/src/core/switch2.cpp` | 2026-11-16 | 3.0.1 bring-up through 2026-11-16: rim audit, cloud shimmer, upscaler chain, FSR version override |
| `runtime/src/diag/crash.cpp` | 2026-11-14 | pkg7 assert: the data is newer than the exefs (HANDOVER 79) |
| `runtime/src/gfx/extras/temporal.cpp` | 2026-11-16 | replay: pipe/fb hot-path audit (round 45, 9.7-15.4 -> 5.3-6.8 ms); fsr_follow_size; fs trace_stack_file off; s |
| `runtime/src/gfx/extras/temporal_ffx.cpp` | 2026-11-16 | replay: pipe/fb hot-path audit (round 45, 9.7-15.4 -> 5.3-6.8 ms); fsr_follow_size; fs trace_stack_file off; s |
| `runtime/src/gfx/nvn/api_dlss_replay.cpp` | 2026-11-16 | replay: pipe/fb hot-path audit (round 45, 9.7-15.4 -> 5.3-6.8 ms); fsr_follow_size; fs trace_stack_file off; s |
| `runtime/src/gfx/nvn/api_program.cpp` | 2026-11-14 | nvn: [nvn] shader_dump writes the code and control of every unresolved block (HANDOVER 74) |
| `runtime/src/gfx/nvn/api_texture.cpp` | 2026-11-16 | 3.0.1 bring-up through 2026-11-16: rim audit, cloud shimmer, upscaler chain, FSR version override |
| `runtime/src/gfx/nvn/earlyz_mask_shaders.inc` | 2026-11-13 | nvn: the light list registration mask is derived from the list after every list draw - the black rectangle (HA |
| `runtime/src/gfx/nvn/nvn_core.h` | 2026-11-16 | 3.0.1 bring-up through 2026-11-16: rim audit, cloud shimmer, upscaler chain, FSR version override |
| `runtime/src/gfx/nvn/nvn_enums.cpp` | 2026-11-16 | 3.0.1 bring-up through 2026-11-16: rim audit, cloud shimmer, upscaler chain, FSR version override |
| `runtime/src/gfx/nvn/nvn_gpu.cpp` | 2026-11-13 | nvn: [nvn] split_draws hands the recorded commands to the GPU at pass boundaries - the GPU stops waiting for t |
| `runtime/src/gfx/nvn/nvn_gpu_internal.h` | 2026-11-16 | 3.0.1 bring-up through 2026-11-16: rim audit, cloud shimmer, upscaler chain, FSR version override |
| `runtime/src/gfx/nvn/nvn_gpu_pool.cpp` | 2026-11-13 | nvn: pool import/mirror granule is a config (default 64 MiB unchanged); 16 MiB does not help; movement overrun |
| `runtime/src/gfx/nvn/nvn_gpu_texture.cpp` | 2026-11-16 | 3.0.1 bring-up through 2026-11-16: rim audit, cloud shimmer, upscaler chain, FSR version override |
| `runtime/src/gfx/nvn/nvn_pipeline.cpp` | 2026-11-16 | 3.0.1 bring-up through 2026-11-16: rim audit, cloud shimmer, upscaler chain, FSR version override |
| `runtime/src/gfx/nvn/nvn_pipeline.h` | 2026-11-14 | nvn: push the uniform buffers as push descriptors ([nvn] push_uniforms, ubo_only_rebind) |
| `runtime/src/gfx/nvn/nvn_replay.cpp` | 2026-11-16 | replay: pipe/fb hot-path audit (round 45, 9.7-15.4 -> 5.3-6.8 ms); fsr_follow_size; fs trace_stack_file off; s |
| `runtime/src/gfx/nvn/nvn_shaders.cpp` | 2026-11-16 | 3.0.1 bring-up through 2026-11-16: rim audit, cloud shimmer, upscaler chain, FSR version override |
| `runtime/src/gfx/nvn/nvn_spirv_patch.cpp` | 2026-11-16 | 3.0.1 bring-up through 2026-11-16: rim audit, cloud shimmer, upscaler chain, FSR version override |
| `runtime/src/gfx/nvn/nvn_spirv_patch.h` | 2026-11-16 | 3.0.1 bring-up through 2026-11-16: rim audit, cloud shimmer, upscaler chain, FSR version override |
| `runtime/src/gfx/platform.cpp` | 2026-11-16 | 3.0.1 bring-up through 2026-11-16: rim audit, cloud shimmer, upscaler chain, FSR version override |
| `runtime/src/gfx/vk_device.cpp` | 2026-11-16 | replay: pipe/fb hot-path audit (round 45, 9.7-15.4 -> 5.3-6.8 ms); fsr_follow_size; fs trace_stack_file off; s |
| `runtime/src/ipc/ipc.cpp` | 2026-11-14 | dlc: the title never asks aoc, so the Torna entry is save driven (HANDOVER 66) |
| `runtime/src/kernel/handles.cpp` | 2026-11-16 | 3.0.1 bring-up through 2026-11-16: rim audit, cloud shimmer, upscaler chain, FSR version override |
| `runtime/src/kernel/svc_info.cpp` | 2026-11-16 | 3.0.1 bring-up through 2026-11-16: rim audit, cloud shimmer, upscaler chain, FSR version override |
| `runtime/src/kernel/svc_memory.cpp` | 2026-11-16 | 3.0.1 bring-up through 2026-11-16: rim audit, cloud shimmer, upscaler chain, FSR version override |
| `runtime/src/kernel/svc_thread.cpp` | 2026-11-16 | 3.0.1 bring-up through 2026-11-16: rim audit, cloud shimmer, upscaler chain, FSR version override |
| `runtime/src/loader/module.cpp` | 2026-11-16 | 3.0.1 bring-up through 2026-11-16: rim audit, cloud shimmer, upscaler chain, FSR version override |
| `runtime/apps/video_codec_probe.cpp` | 2026-11-18 | probe: AV1 on the SDK 3.0.1 nn::codec entry points (video_codec_probe <movie.webm> <out.png> <frame>) |
| `runtime/src/media/movie_vdec.cpp` | 2026-11-18 | movie: [media] video_decoder = library leaves movie::VideoDecoder to the library (it drives nn::codec AV1) and keeps the host AudioDecoder |
| `runtime/src/media/video_codec.cpp` | 2026-11-18 | vcodec: nn::codec AV1 via dav1d and the SDK 3.0.1 names (ByTransferMemory, ImageTilingMode preference, event-returning submission event) - the movie library's VideoDecoder path |
| `runtime/src/mem/memory.cpp` | 2026-11-14 | heap: lazy commit is implemented and measured, but it stays off (crashes at 0.82 s) |
| `runtime/src/services/audren/Server/AudioRenderSystem.h` | 2026-11-12 | nvn: trace the depth/blend state a draw is submitted with, summarize the frame; audren: log every voice the ga |
| `runtime/src/services/common.cpp` | 2026-11-16 | 3.0.1 bring-up through 2026-11-16: rim audit, cloud shimmer, upscaler chain, FSR version override |
| `runtime/src/services/fs.cpp` | 2026-11-16 | replay: pipe/fb hot-path audit (round 45, 9.7-15.4 -> 5.3-6.8 ms); fsr_follow_size; fs trace_stack_file off; s |
| `runtime/src/services/hid.cpp` | 2026-11-16 | 3.0.1 bring-up through 2026-11-16: rim audit, cloud shimmer, upscaler chain, FSR version override |
| `runtime/src/services/misc.cpp` | 2026-11-16 | 3.0.1 bring-up through 2026-11-16: rim audit, cloud shimmer, upscaler chain, FSR version override |
| `tools/shaders/ampere/decoder/SassDecoder.Tensor.cs` | 2026-11-16 | 3.0.1 bring-up through 2026-11-16: rim audit, cloud shimmer, upscaler chain, FSR version override |
| `tools/shaders/ampere/decoder/SassDecoder.Tex.cs` | 2026-11-14 | shaders: SUATOM (0x593/0x595) and the TLD4 PTP modifier - 1529 of 1529 blocks the game asks for translate (HAN |
| `tools/shaders/ampere/decoder/SassDecoder.cs` | 2026-11-16 | 3.0.1 bring-up through 2026-11-16: rim audit, cloud shimmer, upscaler chain, FSR version override |
| `tools/shaders/ampere/frontend/AmpereEmit.cs` | 2026-11-16 | 3.0.1 bring-up through 2026-11-16: rim audit, cloud shimmer, upscaler chain, FSR version override |
| `tools/shaders/ampere/frontend/AmpereTranslator.cs` | 2026-11-14 | shaders: take the NVN2 stage from the control section - 518 to 2813 of 4222 blocks translate (HANDOVER 73) |
| `tools/shaders/harness/Program.cs` | 2026-11-14 | shaders: take the NVN2 stage from the control section - 518 to 2813 of 4222 blocks translate (HANDOVER 73) |
| `tools/shaders/harness/StaticGpuAccessor.cs` | 2026-11-16 | 3.0.1 bring-up through 2026-11-16: rim audit, cloud shimmer, upscaler chain, FSR version override |
| `tools/shaders/harness/translator/Ryujinx.Graphics.Shader.csproj` | 2026-11-14 | shaders: take the NVN2 stage from the control section - 518 to 2813 of 4222 blocks translate (HANDOVER 73) |

## Reproduce

```sh
git diff --name-only 6f1d964..HEAD -- third_party/fefw-recomp
git log --oneline 6f1d964..HEAD -- third_party/fefw-recomp
```

## Areas of change (summary)

- **runtime/src/gfx/nvn** — NVN/NVN2 replay: program keys, pipeline cache, texture registry and uploads, pools,
  SPIR-V patching, the early-Z mask shaders, shader dumping.
- **runtime/src/gfx/extras** — the upscaler chain: TAAU, FSR 3.1/4.1 through the FidelityFX API, per-size FFX contexts.
- **runtime/include/nxrt** — the interfaces those changes expose (extras.h, gfx.h, memory.h, svc.h, ...).
- **runtime/src/{kernel,loader,services,mem,ipc,core,diag}** — Switch 2 bring-up: 128 GiB alias region, svcInfo
  stubs, heap model, nn::audio/opus on the retail 3.0.1 build, fs read tracing, crash dumps.
- **tools/shaders** — the Ampere (NVN2) SASS path: stage from the control section, SUATOM/TLD4, tensor decoder.

- **runtime/src/media/video_codec.cpp** — nn::codec on the host: VP8/VP9 with libvpx, AV1 with dav1d, and the SDK 3.0.1
  entry-point names the movie library in subsdk0 uses (Initialize*DecoderByTransferMemory/ByRemoteMemory, ImageTilingMode
  preference, a Get*DecoderSubmissionReadyEvent that returns the event, SubmitAv1DecoderInputBuffer without the out size).
  This is what the library's own movie::VideoDecoder needs; it never goes through movie::Decoder.
- **runtime/games/xc2ns2** — the title facts registered for this game (program id, Switch 2 platform, save sizes),
  and ``movie_video_decoder``: the DLC openings are AV1 and play through the host movie::VideoDecoder (dav1d).
- **runtime/src/core/runtime.cpp, runtime/src/services/common.cpp** — the startup log names the config file it
  loaded and the language value it read, so a launcher that starts the game elsewhere can be diagnosed.
- **runtime/src/gfx/nvn/nvn_gpu_texture.cpp** - `[nvn] ds_stencil_bits` defaults to 0 on NVIDIA: a float-declared sampler over the stencil plane is undefined there and took the device down (issue #4).
- **runtime/src/services/misc.cpp** - add-on content is discovered from the package folder (and its ids may use either base); before this, a dump with the six add-ons reported zero.
- **runtime/src/gfx/nvn/nvn_replay.cpp** - `[nvn] draw_ring` (default 32): the freeze dump now ends with the last draws the replay submitted, which is what a GPU hang leaves to go on.
- **runtime/src/gfx/nvn/nvn_replay.cpp (2026-11-19)** - the "float sampler over the stencil plane" report (`ds_debug: fs <hash> ...`)
  is now written unconditionally, once per (shader, binding), instead of only under `[nvn] ds_debug`. The patch tool can only
  rewrite modules a log names, and the run that lost the device was the one with nothing recorded in it (issue #10).
