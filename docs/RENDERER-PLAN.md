# Plan: n2den's NVN-HLE as the recomp's renderer (for XC:DE)

Written 2026-11-26. Decision record: [RENDERER.md](RENDERER.md).

## Decisions (user, 2026-11-26)

- The library is also where the Galaxia renderer rebuild lands: extracted first with no behaviour change,
  then improved in place (residency, parallel recording, bindless pools), each change checked in both
  Galaxia and the recomp.
- **DLSS:** the game's native path first (its own `nvnCommandBufferEvaluateDlss` on NVIDIA DLSS, then its
  own NDSR network: n2den's "Console native"). PC DLSS (host DLSS replacing the game's upscale chain) later.
- **Movies:** either n2den's or the XC2 recomp's decoders, whichever plugs in more easily.
- **Settings:** follow the XC2 recomp's ini/profile style (`config/profiles/*.ini`, `[nvn]` keys); n2den
  switches the recomp needs get ini keys there, the rest keep their defaults.

## Why now

fefw-recomp's renderer runs XC2 (same `sdk`/NVN/DLSS/CUDA modules as XC:DE) but stalls on NVIDIA: about
30 s per frame inside the driver's compiler for compute pipelines, and the saved pipeline cache does not
help, so it never reaches the title screen. n2den's NVN-HLE runs **XC:DE itself** to 3D gameplay at 60 fps
with the game's own DLSS network and a correct picture (classic GOB order for its UI, n2den 63ddb5c). That
makes n2den's NVN-HLE the renderer and n2den's XC:DE the reference picture.

## What we found

### The recomp side (fefw-recomp runtime)

- Lifted code calls host functions as `void(*)(Ctx*)`; `Ctx` holds `x[32]` (x31 = SP) and `v[32]`. Indirect
  calls go `call_indirect` → `dispatch_call`; HLE thunks live at `kHleBase` (0x7400000000), 16 bytes each.
- NVN entry points come from `nvn::install()`: `bootstrap_loader` and `device_get_proc_address` both resolve
  names through `proc_address()` to registered thunks (`register_impl`, `register_extra_impl`). The sdk's own
  NVN driver is bypassed (`xc2_boot.cpp` overrides `nvnBootstrapLoader`, `switch2.cpp` skips GPU init).
- **Guest memory is host memory** (identity map below 2^39). Write watching exists (`mem::ww`).
- Each guest thread is a Win32 thread; NVN sync uses Vulkan timeline semaphores, not kernel waits. Only the
  vsync event is a kernel `ServiceEvent`.
- Vulkan instance, device, single queue + `queue_mutex`, VMA: `gfx::Device`. Swapchain, `begin_frame` /
  `end_frame`, overlay hook: `gfx::Renderer`. SDL3 window in `platform.cpp`.
- Per present the layer also drives: frame limiter, `diag_frame_tick`, movie ticks, cheats tick.
- Other code calls into the current layer: `nvn_backend.h` (play, overlay, boot), `be::gpu::serial_done` /
  `last_serial` and texture hooks from `media/` (movies).
- No swap mechanism today: `src/gfx/**` is one glob'd library, and the boot exe calls `install` /
  `install_backend` unconditionally. The runtime builds with the static CRT (`/MT`) and clang-cl.

### The n2den side (NVN-HLE, public main)

- Three layers: `core/hle/nvn` (~15k lines, the NVN functions), `video_core/nvn` (~15k, Recorder, `Sink`,
  shader front end), `renderer_vulkan/nvn` (~72k, the Vulkan replay).
- NVN functions are `void(Call&)`; `Call` carries `Runtime&`, `Core::System*` (already allowed to be null in
  tests), a `ThreadContext&` (registers `r[]`/`v[]`), `GuestMemory&`, `Recorder&` and an AAPCS64 argument
  cursor. Example: `nvnSyncInitialize(Call& c)`.
- The game's NVN memory callback is only stored, never called back into the guest.
- Seams already designed in: `GuestMemory` (only `Read`/`Write`/`Pointer` required), `Runtime` without a
  kernel (`SetWaitHook`, host-polling fallback), a fake-able `GuestPort`, and a **headless
  `Vulkan::Nvn::Context(const Device&, std::mutex& submit_mutex, std::unique_ptr<PresentTarget>,
  ContextOptions)`** with a `PresentTarget` interface.
- Emulator ties to replace with an interface: `Core::System` (~40 uses: sink lookup, memory, program ID, GPU
  ticks, exit, speed limiter/perf stats), kernel waits/sleep (~34, hook exists), `core_timing` clock (~9),
  file_sys (package shaders, RomFS, add-ons), native-image directory, debug tools.
- No emulated-GPU dependency (only `GPU().GetTicks()` as a clock and `ShaderNotify`).
- Deep dependencies that come along: `vulkan_common` `Device` (~330 uses), VMA, `video_core/upscaler`
  (Streamline/DLSS), `VideoCore::Surface`, texture decoders (ASTC/BC), ~13 host compute shaders, and
  `shader_recompiler` (ir, maxwell, ampere, ir_opt, spirv: ~52k lines; links only common, fmt, sirit).
- ~245 `EDEN_NX2_*` / `EDEN_NVN_*` environment switches read ad hoc, and ~140 `Settings::` uses.
- n2den builds with the DLL CRT (`/MD`).

## Design

```
lifted game code ── BLR ──> fefw dispatch ──> kHleBase thunk
                                                 │  (adapter: Ctx -> ThreadContext, call, write x0/v0)
                                                 v
                          n2den core/hle/nvn  void(Call&)   ── GuestMemory (identity) ──> host memory
                                                 │
                                         video_core/nvn Recorder ──> Sink
                                                 │
                              renderer_vulkan/nvn Context (headless ctor)
                                                 │  PresentTarget (adapter)
                                                 v
                              fefw gfx::Renderer begin_frame / end_frame, overlay, limiter
```

- **Library.** n2den's NVN-HLE is built as a static library (`n2den_nvnhle`) in the Galaxia n2den fork
  (`Duck912/galaxia-n2den`), per the Galaxia rewrite plan: extracted with no behaviour change, then embedded
  in both Galaxia and this recomp. Never in n2den main. The fork's `galaxia/stage1` already contains public
  main `aef02f2`; cherry-pick `63ddb5c` (XC:DE classic GOB).
- **Host interface (`HostServices`).** One struct the embedder fills: guest clock, program ID, wait/sleep
  (or the existing wait hook), pacing / speed limit, shader-package and RomFS source, native-image directory,
  exit request, settings source. The emulator fills it from `Core::System`; the recomp from its runtime.
- **Calls.** One generic recomp thunk per n2den handler: copy `Ctx` registers into a `ThreadContext`, build
  the `Call`, run the handler, copy x0/v0 back. (A register view instead of a copy is a later optimisation
  if profiles show the copy.) Registered through fefw's `register_impl` / `register_extra_impl` so the
  existing loader hands out their addresses.
- **Memory.** `GuestMemory` with `Pointer(va) = va`. Write tracking (`Track`/`Arm`/`TakeWritten`) on top
  of `mem::ww`, because n2den's mirrors and caches rely on it.
- **Vulkan device.** One `VkDevice` for both. n2den's `Vulkan::Device` needs its own feature and extension
  set, so it creates the device and fefw's `gfx::Device` adopts it (to be checked; the alternative is
  n2den's `Device` wrapping fefw's). One queue, one submit mutex.
- **Present.** A `PresentTarget` over `gfx::Renderer`: acquire = `begin_frame`, present = hand the finished
  image to the output pass, then `end_frame`, keeping the overlay, frame limiter and per-present ticks.
- **Shaders.** n2den translates shaders at run time from guest memory with its native Ampere front end: no
  offline cache, no .NET harness, no RomFS scan.
- **Build.** A runtime option `NXRT_NVN_BACKEND=fefw|n2den` drops `src/gfx/nvn/**` from `nxrt_gfx` and
  links the adapter plus `n2den_nvnhle`. The library is built with `/MT` and clang-cl to match the runtime.

## Steps

1. **Library builds standalone** (fork). New CMake target for the three layers plus the needed
   `vulkan_common`, upscaler, surface, texture decoders, host shaders and the `shader_recompiler` subset,
   `/MT`, clang-cl. A small test program creates the headless `Context` with a fake `GuestMemory` and a
   null present target and replays a recorded submission. Gate: compiles, links, the test passes.
2. **`HostServices` in the fork, no behaviour change.** Route the `Core::System` / kernel / core_timing /
   file_sys uses through it; the emulator fills it. Gate: the fork's boot checks (OoT Kokiri fps, Kirby,
   Fast Fusion, XC2, **XC:DE**) match before and after.
3. **Recomp adapter** (this repo): the thunk adapter, identity `GuestMemory` with `mem::ww` tracking,
   `HostServices` from the runtime, `PresentTarget` over `gfx::Renderer`, shared device, stand-ins for the
   `nvn_backend.h` calls and the movie hooks (movies black at first). Gate: XC2 boots to its title screen on
   n2den's renderer (it already has a working profile here).
4. **XC:DE boot target**: `xcde_boot.cpp` from `xc2_boot.cpp` without XC2's address hooks; program index 1
   with RomFS from program 0 and the add-on; a `xcde` runtime game entry. Gate: XC:DE reaches the title
   screen; frames compared with n2den's XC:DE.
5. **Gameplay**: XC:DE hook sites where needed (vsync period, native resolution, DLSS viewport), saves,
   input, audio, movies on n2den's texture path.
6. **Settle**: performance pass (call copy, pacing), settings page, drop the fefw NVN layer once n2den's is
   at least as good everywhere it matters.

## Open questions

- Can `gfx::Device` adopt an externally created `VkDevice`, or must n2den's `Device` wrap fefw's?
- How much of n2den's ~245 environment switches and `Settings::values` to keep; a settings source the
  recomp can fill from its ini.
- Streamline/DLSS: both sides load it; only one may own it.
- Movies: fefw's VP9 path writes textures through fefw-layer hooks; needs a small texture-upload API on the
  n2den side.
- XC:DE program-index plumbing in fefw's `fsp-srv` (n2den has the RomFS fallback; check fefw).

## Progress (2026-11-26, overnight)

Done and verified without launching a game:

- **Step 1** (fork `Duck912/galaxia-n2den`, branch `galaxia/nvnhle-lib`): `n2den_nvnhle` builds standalone
  with clang-cl and `/MT`. `nvnhle_smoke` records and replays a clear + copy in a host-memory pool on
  the GPU (0 wrong words).
- **Step 2 (code)**: the NVN API layer is in the library. The emulator glue moved to
  `hle_runtime_emu.cpp` / `bridge_emu.cpp`, `HostServices` replaces the handlers' `Core::System` uses,
  `Bridge::AnalyzeSdk` is factored out. The emulator still builds and links. **Not boot-checked.**
- **Embedding API** `nvnhle/embed.h`: n2den owns instance, device, swapchain and present on the
  embedder's window; NVN calls by id with guest registers. `nvnhle_embed_smoke` passes (650 functions).
  The library carries a private VMA and renamed Streamline helpers (`nvnhle_prefix.h`), and
  `make_dist.sh` packs one bundle `.lib` (no zstd; clang builtins in).
- **Step 3 (code)**: this runtime gets `nvn::set_proc_resolver` and `nvn_n2den` (trampolines into
  `embed.h`). `xc2_boot --nvn n2den` skips this runtime's renderer and back end. Both XC2 and XC:DE boot
  executables link with the bundle. **Not run.**
- **Step 4 (code)**: `--game xcde` skips XC2's `main` hooks. XC:DE's `main` lifted (0 untranslated) and
  compiled without XC2's site list; `config/profiles/xcde.ini`.

To run (needs a person at the machine; RAM/VRAM guard for `xc2_boot.exe` in `C:/re/xcde-work`):

1. n2den emulator boot checks for step 2: `C:/re/play/galaxia-fork/check6-{oot,kirby,ui,xc2,xcde}.bat`.
2. XC2 on n2den in the recomp: `play.ps1 -Profile n2den -Seconds 100`.
3. XC:DE in the recomp: `play.ps1 -Profile xcde -Seconds 100`.

Known gaps: movies (no texture hookup yet), the F1 overlay and F12 screenshots (this runtime's
renderer is off in n2den mode), guest pool write tracking (`GuestMemory::Track` is not implemented
for identity memory: fine for host-imported pools, untested for device-local copies), and
`vi::ListFrameHistory` display ticks use 19.2 MHz while this runtime's Switch 2 tick is 31.25 MHz.

