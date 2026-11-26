# xcde-ns2-recomp

A planned native Windows PC port of **Xenoblade Chronicles: Definitive Edition – Nintendo Switch 2 Edition**,
made by static recompilation: the game's ARM64 code is translated to C++, compiled into a regular Windows
program, and run on a small runtime that stands in for the console's system software and draws with Vulkan.
It is not an emulator.

Modelled on [xc2-ns2-recomp](https://github.com/weile10000/xc2-ns2-recomp) (Xenoblade Chronicles 2 S2E),
which builds on [fefw-recomp](https://github.com/Goldoire/fefw-recomp) and nxrecomp.

> **No game files are included here.** You need your own legally dumped copy of the game. Everything that
> reads the game happens locally. Not affiliated with or endorsed by Nintendo or Monolith Soft.

**Status:** xc2-ns2-recomp imported as the base (full history, upstream commit 8f83def); XCDE profile not started. See [docs/PLAN.md](docs/PLAN.md) and [docs/TARGET.md](docs/TARGET.md).

License: GPL-3.0-or-later (matching the projects it builds on).

## Repository layout

This repository started as an import of xc2-ns2-recomp with its full history (remote `xc2-upstream`,
fetch only). Everything under `xc2/`, `third_party/fefw-recomp/`, `launcher/`, `tools/` and the upstream docs
is that project's work, unchanged unless a later commit here says otherwise. Its README is kept as
[README.xc2.md](README.xc2.md); its build guide is [docs/BUILD.md](docs/BUILD.md).

XCDE-specific work goes in `xcde/` (game profile, site tables) and in the docs listed above.

## Credits

xc2-ns2-recomp (weile10000 and contributors), fefw-recomp, nxrecomp, Ryujinx, nxnative, and everyone those
projects credit; see [README.xc2.md](README.xc2.md) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
