# Changelog

Dated milestones. The §-numbered evidence sections named on the right are part of the project's internal
notes, which are not published with this repository.

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
