# xcde-ns2-recomp

A planned native Windows PC port of **Xenoblade Chronicles: Definitive Edition – Nintendo Switch 2 Edition**,
made by static recompilation: the game's ARM64 code is translated to C++, compiled into a regular Windows
program, and run on a small runtime that stands in for the console's system software and draws with Vulkan.
It is not an emulator.

Modelled on [xc2-ns2-recomp](https://github.com/weile10000/xc2-ns2-recomp) (Xenoblade Chronicles 2 S2E),
which builds on [fefw-recomp](https://github.com/Goldoire/fefw-recomp) and nxrecomp.

> **No game files are included here.** You need your own legally dumped copy of the game. Everything that
> reads the game happens locally. Not affiliated with or endorsed by Nintendo or Monolith Soft.

**Status:** planning. See [docs/PLAN.md](docs/PLAN.md) and [docs/TARGET.md](docs/TARGET.md).

License: GPL-3.0-or-later (matching the projects it builds on).
