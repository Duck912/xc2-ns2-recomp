# STATUS — dated milestones

A short, dated record of what this project reached and when. The detailed evidence for every line lives in
the §-numbered sections named on the right (internal notes).

| date | milestone | evidence |
|---|---|---|
| 2026-11-09 | first static lift of a Switch title (4 modules, 90,691 functions) and the NVN → Vulkan replay rendering a frame | §1–§20 |
| 2026-11-10 | models/materials: block-linear layouts, tile modes, texture formats, the deferred pass | §21–§30 |
| 2026-11-11 | lighting: light lists, probe volumes, the integer render-target logic op | §31–§41 |
| 2026-11-12 | volumetric fog pipeline identified; first 60 Hz experiments | §42–§51 |
| 2026-11-13 | early-Z mask fix, 1080p output, replay phase split, 60/120 Hz pacing | §44–§56 |
| 2026-11-14 | frame-rate census, pkg7 (Switch 2 add-on) analysis, DLC chain | §58–§88 |
| 2026-11-15 | **retail 3.0.1 route boots**: 128 GiB alias region (VAMM), Opus + `nn::audio` HLE, the tensor-core upscaler translated (Ampere SASS), in-game at **30.0 fps**; full shader cache **21,171**; `earlyz_mask`; the logic-op "read your own output" fix; **quad_split** (cloud-sea shimmer on the title screen) | §89–§90 |
| 2026-11-16 | rim audit — depth filter, shadow map, gather rounding, upscalers each tested and excluded (§91); cloud-shimmer quantified and the fog-composite dither ruled out (§92); **the game's three DLSS networks decoded**, FSR 4.1.2 / 3.1 selectable through one DLL, 1440p identified as the only fully 1:1 chain (§93) | §91–§93 |
| 2026-11-16 | **the amdvlk crash is solved**: a FidelityFX context must never be reused across input sizes — the game's dynamic resolution (960x540 .. 1280x720) changes the size every few dozen frames and amdvlk dies on the barrier a few milliseconds later. One context per size (up to six, LRU) gives FSR 4.1.2 for 122 s over 24 size changes with no crash, 30.0 fps and a 1% low of 24.8-27.5 | §95.19 |
| 2026-11-16 | **the replay is cut from 9.7-15.4 ms to 5.3-6.8 ms**: four diagnostic `std::getenv` calls inside `build_key()` cost 1.2 us/draw (the pipe phase went 1.46 to 0.29 us/draw), and a `config_get_bool("fb_debug")` that `feedback_prepare` ran once per sampler binding cost the rest of that phase (1.0-1.9 to 0.06 us/draw). `hot_int` twice a draw, a clock read per draw in `skip_fs_draw`, the leftover per-read `trace_stack_file` hook and a shader dump that rewrote 7,600 files per session are gone too. A memo written independently after reading xc2-recomp's `feedback_scan` (no code copied) never disagreed with a fresh scan (0 mismatches) but hardly ever hits, because this engine rebinds its textures for every draw. The remaining slow frames (59-69 ms) are texture uploads and lock waits, not the replay | §96 |
| 2026-11-16 | **60 fps at 1080p, and FSR 4.1.2 proven safe under dynamic resolution**: `play-301.cmd -60` (the old `play60.cmd` only ever started the early NS2 dev build). The port holds **59.7 fps, 1% low 51.3** on TAAU and **59.7 / 50.8** on FSR 4.1.2 hot-switched inside the same session, so FSR 4 is not the cost. Six FidelityFX contexts over the game's resolution steps with **0 crashes** close §95.19. The heaviest open plain is **~4,400 draws/frame**, where the replay is **9 ms** and the game holds **43-52 fps** (it was 16 ms and 34-40 before the two upstream replay switches below) | §97 |
| 2026-11-16 | **the amdvlk crash is pinned to one instruction**: the ICD is Adrenalin's own `amdvlk64.dll` (the only one registered), RADV does not exist on Windows, and the fault lands in `vkCmdPipelineBarrier` on the barrier list FSR 4.1.2's `ffxDispatch` records — 4 crashes in 21 min of FSR 4.1.2 against 0 in 236 min of FSR 3.1.6 / TAAU, and the FidelityFX barrier list itself proven clean — so the default upscaler is back to FSR 3.1.6 (`[upscale] fsr_version = 3.1`), with a FidelityFX barrier watchdog (`[upscale] barrier_check`) kept for the record. **Superseded the same day**: one FidelityFX context per input size fixed it (see the row above). The default upscaler stays **TAAU**; FSR 4.1.2 is selectable and measured no slower here | §95 |

## Current limits

* The window defaults to 2560×1440 so the chain is 1:1 (720p → 1440p → present). A 1080p window adds a second
  full-screen resample with no image-quality gain, so it is a low-end option, not the default (§97.12).
* The game's internal chain tops out at 2560×1440; 4K output is an upscale of that.
* The 3D DLSS network is fixed at 1280×720 → 2560×1440 in every mode and cannot be lowered from configuration.
* The blue-grey rim where objects meet the cloud sea and the residual cloud-sea shimmer are both properties of the
  game's 640×360 volumetric fog; the platform-level suspects were tested and excluded (§91, §92).
* Slow frames come from texture uploads and guest/host lock waits (§90.21).
* The open plain reaches about 4,400 draws/frame with a replay of 9 ms and 43-52 fps; the frame time there is
  18-23 ms against a 16.7 ms budget, so a solid 60 fps needs 1.5-6 ms more depending on the spot — the 2 ms
  figure quoted above was the best case only (the 5,200 draw / 16 ms numbers are the superseded measurement, §97).
* The window is 2560x1440 by default; 4K costs nothing extra because the internal chain is fixed at 1440p and the
  last step is a blit.
