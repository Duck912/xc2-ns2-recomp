# Renderer: fefw-recomp's NVN layer or n2den's NVN-HLE?

Assessment of 2026-11-26.

## Both are API-level NVN replacements

- **fefw-recomp / xc2-ns2-recomp** (`runtime/src/gfx/nvn`, ~32k lines): answers `nvnBootstrapLoader` /
  `nvnDeviceGetProcAddress` with its own table of host functions (`NVN_REG` thunks), records the game's
  command buffers and replays them on Vulkan 1.3. Shaders are translated **offline** (Ryujinx's translator
  in C# plus the project's Ampere front end) into a SPIR-V cache keyed by hash, built at setup time.
- **n2den NVN-HLE** (GPL-3.0, ~97k lines): the same idea inside an emulator. Three layers:
  - `src/core/hle/nvn` (~15k): the NVN functions the game calls (bridge, function table, per-family
    `functions_*.cpp`, DLSS layout, SDK impl table).
  - `src/video_core/nvn` (~11k + shader front end ~2k): the Recorder, the `Sink` interface, the native
    Ampere SASS front end (on top of the emulator's `shader_recompiler`).
  - `src/video_core/renderer_vulkan/nvn` (~69k): the Vulkan replay (`Vulkan::Nvn::Context`), pipelines,
    texture layout/untiling, storage cache, DLSS/NDSR replacement, rescaler, frame generation.

Because the game's `sdk` and DLSS modules are byte-identical to XC2 S2E's (docs/TARGET.md), the NVN surface
is exactly the one n2den already runs XC2 S2E on: to gameplay, 60 fps, with XC2-specific fixes (classic GOB
order for non-packaged textures, DLSS optimal/min/max order, NVN2 early-tests control bit, barrier ordering
inside a pass, VRAM release of idle streamed textures, NDSR/DLSS replacement).

## What speaks for n2den's renderer

- It is proven on this exact SDK/NVN/DLSS build, on NVIDIA hardware. xc2-ns2-recomp's README lists an open
  NVIDIA device-lost (TDR) blocker; its main test hardware is AMD.
- Shaders are translated **in process at run time** by the native Ampere front end: no .NET, no offline
  12k-shader cache step, no gaps for shaders first seen in play.
- Clean seam: the Recorder talks to the replay only through `VideoCommon::Nvn::Sink`, and guest memory only
  through `GuestMemory`. In a recomp guest memory is host memory, so `GuestMemory` is close to trivial.
- Same licence (GPL-3.0-or-later), and its authors are on this project.

## What it costs

- `renderer_vulkan/nvn` leans on the emulator's Vulkan renderer: ~216 includes of `renderer_vulkan/*`
  (Device, Scheduler, PresentManager, helpers), ~61 of `vulkan_common`, plus `video_core/textures`,
  `surface`, `upscaler`, `host_shaders`. These come along or get small replacements.
- The shader front end sits on Eden's `shader_recompiler` (front end IR, SPIR-V backend), which must come
  along as a library.
- `core/hle/nvn` reads arguments as an emulated AArch64 call (`aapcs64.h`, `core/arm`) and uses
  `Core::System`, core timing and settings. In the recomp, calls arrive through fefw's thunk ABI, so a
  shim maps one onto the other.
- Present/windowing, input overlay and frame pacing would come from the recomp runtime instead.

## Decision (2026-11-26)

1. **Start on fefw-recomp's renderer** as xc2-ns2-recomp ships it, and bring the game up on it. If it hits
   the NVIDIA device-lost blocker on the dev machine, stop at the first device loss (never retry) and
   raise switching early.
2. **n2den's NVN-HLE becomes a shared library**, built in the Galaxia project as the first step of its
   renderer rebuild (stage 4): extracted from the Galaxia n2den fork with no behaviour change, then used by
   both Galaxia and this recomp. Its boundaries: NVN entry points through a host function table (this
   project adapts fefw's `NVN_REG` thunks to it), a `GuestMemory` interface (host memory here), and a
   host side where the embedding program provides the Vulkan device, queues and present.
3. **Switch** (`nvn_backend = fefw | shared`) once the library is embedded, so both can be compared on the
   same frame; keep one renderer once the shared one matches or beats fefw's in picture and frame rate.
4. Renderer improvements (VRAM residency, parallel recording, bindless pools) happen inside the library
   after the extraction, checked in both projects.
