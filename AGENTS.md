# Working on this repository

A note for whoever is reading the code next — a person, or an assistant with no memory of the last session.
It says what the project is, what must not break, and where to look. Everything else is in [docs/](docs/).

## What this is

Static recompilation of *Xenoblade Chronicles 2 — Nintendo Switch 2 Edition* (retail 3.0.1) to native Windows
and Vulkan. The game's NSO modules are lifted to C++ by [nxrecomp](https://github.com/drakolordx7/nxrecomp) and
linked against the runtime in `third_party/fefw-recomp`, which replays the game's NVN/NVN2 command stream on
Vulkan. It is not an emulator: there is no interpretation at run time.

[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) has the picture; [docs/COMPATIBILITY.md](docs/COMPATIBILITY.md) has
the measured frame rates and the known issues.

## Ground rules

These are not style preferences. Each one exists because breaking it cost a session.

1. **No game data, ever.** No NSO modules, no romfs, no keys, no lifted C++, no shader cache, and nothing
   derived from the game's own assets (a hand-edited shader counts — it is still the game's code). The rule of
   thumb: *if it cannot be reconstructed without the game files, it does not belong here.* CI checks the
   obvious cases; `docs/INVARIANTS.md` has the reasoning.
2. **The shader cache is append-only.** Never rebuild or delete it. It holds 21,171 translated programs, and
   `spirv.preload.pack` is read before the loose `.spv` files, so a stale pack silently wins over an edited
   shader. If you change a shader patch, run `xc2\scripts\patch-shaders.ps1 -Check` and expect exit 0.
3. **The game runs in one instance, started by the operator.** Automation must not terminate or restart it.
   Reading logs and snapshots at any time is fine. After it exits, the next launch waits about 25 seconds.
4. **Absolute paths in scripts and commands.** Relative paths break as soon as the working directory moves,
   and several build scripts change directory part-way through.

## Build and run

[docs/QUICKSTART.md](docs/QUICKSTART.md) is the five-step version with the failures people actually hit.
[docs/BUILD.md](docs/BUILD.md) is the full build, including the shader cache.

```powershell
pwsh -File third_party\fefw-recomp\tools\textures\scripts\fetch_third_party.ps1   # once
# two cmake configures, see QUICKSTART section 3
.\xc2\scripts\build.ps1 -Exefs xc2\game\xc2ns301 -Run:$false `
    -Modules 'main,sdk,subsdk0,subsdk1,subsdk2,subsdk3,rtld' `
    -LiftDir xc2\build\lift-301 -ObjDir xc2\build\obj-301 -LibDir xc2\build\lib-301
.\xc2\scripts\build-boot.ps1 -Exefs xc2\game\xc2ns301 -OutDir xc2\build\boot-301 `
    -LibDir xc2\build\lib-301 -MainLib xc2\build\lib-301\main.lib -Defines XC2_MODULES_7
.\tools\run\play-301.cmd -60
```

## Where to look

| question | file |
|---|---|
| how does the lift, the runtime and the shader pipeline fit together | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| what runs, what does not, how fast | [docs/COMPATIBILITY.md](docs/COMPATIBILITY.md) |
| it builds but the screen is wrong, or the driver crashes | [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) |
| the toolchain, and the switches that print diagnostics | [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md) |
| the rules, and why they exist | [docs/INVARIANTS.md](docs/INVARIANTS.md) |
| the hook sites the lifter uses | [xc2/sites/README.md](xc2/sites/README.md) |
| third-party components and their licences | [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) |

## Before you open a pull request

```powershell
python tools/check_links.py          # every relative link resolves
python tools/check_invariants.py     # no private paths, no game data, ASCII build inputs
```

The second one also runs as a git hook (`pwsh -File tools/install-git-hooks.ps1` installs it) and in CI.
If you change a file under `third_party/fefw-recomp/`, add the change to that directory's `MODIFICATIONS.md`
— GPL-3.0 requires a modification notice.

## If you have the maintainer's local tree

This repository is developed alongside git-ignored notes: `docs/internal/` holds the working state, the
decision log and the round-by-round history, and `work/` holds logs and scratch. If `docs/internal/` exists in
your checkout, start with:

```powershell
pwsh -File tools/agent-brief.ps1
```

That prints the current state, the decisions that are already settled, and the recent history — enough to be
useful without reading the 85 MB of notes. `docs/internal/AGENTS.md` is the full protocol.
