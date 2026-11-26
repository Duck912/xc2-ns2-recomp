# First public release: plan

What has to be true before this repository is published, and how a player gets from a dump to the game.

## Decisions

- **Renderer:** n2den's NVN-HLE, built as a library (`n2den_nvnhle_bundle.lib` + `embed.h`). The library's
  source is published (GPL-3.0-or-later) and a prebuilt copy is attached to a release; setup downloads it, so a
  player does not need n2den's toolchain. The runtime's own NVN back end stays in the tree but is not what
  XC:DE runs on.
- **Launcher:** XC:DE only. The launcher and setup engine inherited from xc2-ns2-recomp are retargeted to
  XC:DE on NVN-HLE. XC2 gets the same treatment in its own port later.

## The setup a player runs (checkout mode)

`tools/setup/xcde_setup.py` (the launcher's engine; reuses `xc2_setup.py`'s runner and status file):

| step | what it does |
|---|---|
| doctor | the machine's toolchain (as for XC2) |
| sources | nxrecomp tarball and third-party sources (as for XC2) |
| nvnhle | downloads the prebuilt NVN-HLE library (pinned version and SHA-256) into `work/nvnhle-dist` |
| runtime | the two CMake builds, configured with `NXRT_N2DEN_DIST` |
| ingest | from the `.nup`: package 0 ExeFS (the Switch 2 program) to `xcde/game/xcde200`, package 1 RomFS (program 0, the game data), package 2 RomFS (add-on `0100FF500E34B001`) |
| lift | the seven modules with `xcde/sites` (XC2's `sdk`/`rtld` lists: those modules are byte-identical; no `main` hooks) |
| link | `build-boot.ps1 -N2denDist` into `xcde/build/200/boot-n2den` |
| streamline | NVIDIA Streamline into the boot folder's `user/streamline` (without it the game's DLSS falls back to FSR 1) |
| done | run profile `config/profiles/xcde.ini` |

No shader step: NVN-HLE translates shaders at run time and keeps its own cache.

## Before publishing

1. NVN-HLE library: source public, release with the bundle and its SHA-256.
2. `xcde_setup.py` and the launcher retargeted; a from-zero setup on a clean checkout reaches the title.
3. README: what works, what is needed (dump, toolchain, NVIDIA GPU for DLSS), how to set up and play, credits.
4. The repository's own checks (`tools/ci/check_invariants.py`, `check_links.py`, `check_play_settings.py`).
5. Release package mode (no toolchain) is later: the first release is checkout-only.
