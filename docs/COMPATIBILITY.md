# Compatibility

**Xenoblade Chronicles 2 – Nintendo Switch 2 Edition**, retail **3.0.1** — title id `0100E95004038000`,
program id `0400E95004038001`.
You need your own dump: the ExeFS of the 3.0.1 program and its romfs. No game data is distributed here.

## Requirements

- Windows 10 or later, x86-64 with AVX2
- a GPU with Vulkan 1.3 (`VK_EXT_external_memory_host`); tested on an AMD RDNA 2 card only (the development
  machine has one), NVIDIA and Intel untested
- 16 GB of RAM; the 3.0.1 romfs alone is 25.6 GB, and the build needs roughly as much again for the generated
  C++ and objects, so keep about 60 GB free during the build
- your own copy of the game and its 3.0.1 update

## Measured frame rate

Ryzen 7 5800X + Radeon RX 6800 XT, Adrenalin 26.10.1, 1440p window:

| area | fps | note |
|---|---:|---|
| port and most areas | **59–60** | the game's own 60 Hz step |
| the open plain (heaviest) | **43–52** | ~4,400 draws/frame, frame time 18–23 ms |

4K output costs no more than 1440p: the internal chain is fixed at 720p → 1440p and the last step is a blit.

## What works

- boots to the title screen, loads a 2022 clear save, plays in the field
- 60 fps target (`tools\run\play-301.cmd -60`); the game's logic, timers and animations follow it
- the upscaler slot is served by the built-in **TAAU** by default; **FSR 4.1.2** and **FSR 3.1.6** are selectable
  at run time (`[dlss] upscaler = fsr3` + `[upscale] fsr_version`), and FSR 4.1.2 measured no slower than TAAU here
- dynamic resolution is handled: one FidelityFX context per input size (6 in a long session, 0 crashes)
- 1080p / 1440p / 4K window sizes; **HDR10 output**, verified on an HDR display
- **VRR opt-in**: `[gfx] present_mode = fifo_relaxed` — a late frame is presented at once instead of being
  quantised to the next vblank, which turns 43–52 fps into even pacing. Needs VRR on the display and in the
  driver; the default stays `fifo` because most players have no VRR.
- keyboard/mouse and gamepad, with remapping
- add-on content through `NXRT_AOC_DIR` (the 3.0.1 launcher points it at `game/dlc-301`; the files are yours)
- mods through the emulator layout: a `mods` folder next to the executable

## What does not work

| | why |
|---|---|
| **add-on content shipped inside the game** | the retail 3.0.1 program links no `nn::aoc` symbols of its own; add-ons are served by the runtime's `aoc:u` from the directory in `NXRT_AOC_DIR` (the 3.0.1 launcher points it at `game/dlc-301`), and the DLC files themselves are not distributed |
| **internal rendering above 1440p** | the game's own chain tops out at 2560×1440 in docked mode |

## Known issues

- **Red edge on the cloud sea in the opening battle background**: one thin red line along a cloud-sea silhouette,
  in the same 640×360 volumetric-fog layer the blue-grey rim came from. Low priority - it is one scene, it does not
  move, and it does not affect play.
- The **RDNA 2 blue-grey rim** where objects meet the cloud sea and the **cloud-sea shimmer** in motion are fixed:
  both came from the runtime letting the GPU read pool bytes the CPU had already rewritten, which the mirror-capture
  work in pull requests 19 and 27 captures per submission (verified on an RX 6800 XT, 2026-11-22).
- **First run compiles pipelines**: about 22 seconds with no frame, then it never happens again.
- **Slow frames on area transitions** (texture uploads and memory-pool imports), not in steady play.
- **Two shader patches are not distributed** (they are derived from the game's own shaders), so a build made from
  this repository alone keeps two fog/UV defects that the maintainer's build fixes. The fog-probe templates and the
  generators written against them are the same kind of material and are kept out of the repository too.
