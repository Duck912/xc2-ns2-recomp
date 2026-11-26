# Plan

## Approach

Start from xc2-ns2-recomp rather than from scratch. Both targets are Monolith titles on SDK 21.4.4 with
NVN2, in-game DLSS, NDSR (the S2 upscaling network) and CUDA, so the runtime (kernel, services, NVN2 command
replay to Vulkan, audio, movies), the Ampere SASS -> SPIR-V shader path and most of the lifter profile apply
as they are. The XCDE-specific work is the game profile: function/site tables for this `main`, boot addresses,
and any services or NVN features XC2 never used.

## Steps

1. **Base import.** (Imported 2026-11-26, upstream 8f83def; build not yet tried.) Bring in xc2-ns2-recomp (GPL-3.0, keep its history, notices and credits) and pin the
   nxrecomp revision it uses. Build it once unchanged to prove the toolchain.
2. **Dump tooling.** ExeFS extraction from `.nup` for program index 1, RomFS from program 0, add-on RomFS.
   Hash-check the modules against docs/TARGET.md.
3. **Module diff vs XC2.** Compare `sdk`, `subsdk0-3`, `rtld` hashes and symbol tables with XC2 S2E. Reuse
   identical modules' profiles directly; list what differs.
4. **Lift.** Add an `xcde` game profile to the lifter; lift all seven modules; drive untranslated
   instruction count to 0 (`main` first).
5. **Boot.** Add `NXRT_GAMES=xcde` to the runtime; title ID / program index plumbing, RomFS from program 0,
   add-on content. Goal: logo -> title screen.
6. **Shaders.** Offline shader cache from the game's shader archives (locate XCDE's equivalent of XC2's
   `bf2.ard` packing).
7. **Picture, audio, input, saves**, then PC features (resolution, frame rate, upscaler choice).

## Reuse from n2den

n2den runs XC2 S2E to gameplay under NVN-HLE, and several fixes there are general knowledge about this engine
and SDK that a recomp runtime needs too (check each against what xc2-ns2-recomp already does):

- `.nup` container reader (`nup_container.cpp`, loader `nup.cpp`).
- 39-bit alias region of 128 GiB when heap > 8 GiB (the game reserves 2 x 60 GiB at static init).
- `OpenDataStorageWithProgramIndex(0)` falling back to the current process RomFS.
- `nvnDlssNetworkBuilderGetOptimalSettings` output order is optimal, min, max; the game skips EvaluateDlss
  if the order is wrong (no 4K picture).
- Classic GOB order (not the Switch 2 bit-swapped order) for non-packaged 3D textures and XC2's
  non-packaged 2D textures (colour-grading LUTs, UI fonts).
- Fragment shader early-tests flag in the NVN2 control section (byte +0xa3 bit 0); without it,
  reflection-probe assignment goes wrong.
- A barrier between a draw that reads an SSBO and a point draw that writes it must end the render pass.
- NDSR / DLSS replacement and host-upscaler wiring.

n2den itself is an emulator; its JIT and HLE layers are not used directly.
