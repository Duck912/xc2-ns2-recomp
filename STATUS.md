# STATUS — dated milestones

A dated record of verified milestones and active limits. Detailed public records live in
[CHANGELOG.md](CHANGELOG.md), [docs/RELEASE-0.2.1.md](docs/RELEASE-0.2.1.md), [docs/COMPATIBILITY.md](docs/COMPATIBILITY.md),
and [docs/reports/](docs/reports/).

| date | milestone | public reference |
|---|---|---|
| 2026-11-09 | First static lift of a Switch title (4 modules, 90,691 functions) and NVN → Vulkan replay rendering a frame | [LIFT-REPORT.md](docs/reports/LIFT-REPORT.md) · [ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| 2026-11-10 | Models & materials: block-linear layouts, tile modes, texture formats, deferred pass | [ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| 2026-11-11 | Lighting pipeline: light lists, probe volumes, integer render-target logic op | [ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| 2026-11-12 | Volumetric fog pipeline identified; initial 60 Hz pacing experiments | [PATCHES.md](tools/shader/PATCHES.md) |
| 2026-11-13 | Early-Z mask fix, 1080p output, replay phase split, 60/120 Hz pacing | [MODIFICATIONS.md](third_party/fefw-recomp/MODIFICATIONS.md) |
| 2026-11-14 | Frame-rate census, Switch 2 add-on (`pkg7`) analysis, DLC mount chain | [COMPATIBILITY.md](docs/COMPATIBILITY.md) |
| 2026-11-15 | **Retail 3.0.1 route boots**: 128 GiB alias region (`VammManager`), Opus + `nn::audio` HLE, tensor-core upscaler translated (Ampere SASS), 30.0 fps in-game; shader cache 21,171; `earlyz_mask`, logic-op fix, `quad_split` | [LIFT-REPORT.md](docs/reports/LIFT-REPORT.md) · [BUILD.md](docs/BUILD.md) |
| 2026-11-16 | **Dynamic resolution FidelityFX fix & replay hot-path optimization**: one LRU FidelityFX context per input size (6 contexts across `960x540`..`1280x720`, 0 crashes), replay trimmed from `9.7–15.4 ms` to `5.3–6.8 ms`; 1080p/1440p **60 Hz** (`59.7 fps`, 1% low `51.3` on TAAU, `59.7 / 50.8` on FSR 4.1.2; heaviest open plain ~4,400 draws at `43–52 fps`) | [COMPATIBILITY.md](docs/COMPATIBILITY.md) · [BENCHMARK-301.md](docs/reports/BENCHMARK-301.md) |
| 2026-11-17 – 2026-11-22 | **Portable releases (`v0.1.0`–`v0.2.1`)**: Tauri launcher, self-contained setup, official DLSS & FSR downloaders, 4K AV1 hardware video, RDNA 2 cloud-sea rim & shimmer fix, 8 GB VRAM `mirror_capture`, #37 audio crackling fix | [CHANGELOG.md](CHANGELOG.md) · [RELEASE-0.2.1.md](docs/RELEASE-0.2.1.md) · [#30](https://github.com/weile10000/xc2-ns2-recomp/pull/30) · [#36](https://github.com/weile10000/xc2-ns2-recomp/pull/36) |
| 2026-11-23 | **Mod support M2/M2b verified**: RomFS file overlay, `bf2.ard` inline record patching, and `ard_tail` appended replacement with patched `bf2.arh` (`xbc1` 48-byte headers) | [MODS.md](docs/MODS.md) |

## Current limits

* **Default window (`2560×1440`)**: matches the game's native `720p → 1440p` docked chain 1:1. Lower `1080p` and higher `4K` output modes scale from that internal chain.
* **Open plain GPU/CPU load**: reaches ~4,400 draws/frame (`~9 ms` replay CPU time, `18–23 ms` total frame time = `43–52 fps` on RX 6800 XT); VRR (`fifo_relaxed`) or future draw-batching optimizations target closing the `1.5–6 ms` gap to locked 60 fps.
* **Texture uploads & pool imports**: area transitions can still introduce occasional hitch frames while streaming pools import and pipelines warm.
* **GPU vendor coverage**: primary verification is on AMD RDNA 2; NVIDIA has open device-hang reports (such as Kurodil fight [#32](https://github.com/weile10000/xc2-ns2-recomp/issues/32)). See [COMPATIBILITY.md](docs/COMPATIBILITY.md).
