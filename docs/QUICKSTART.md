# Quickstart

Ten minutes from a clean clone to the title screen. If a step fails, see [Common failures](#common-failures).

## Before you start

| you need | why |
|---|---|
| **your own dump of the 3.0.1 program** (ExeFS + romfs) | nothing is distributed with this repository |
| Windows 10/11 x64, a Vulkan 1.3 GPU, 16 GB of RAM | the runtime renders through Vulkan |
| about 60 GB of free disk | 25.6 GB of romfs, the rest for the build |
| the toolchain | VS Build Tools, LLVM/clang-cl, CMake + Ninja, .NET 10 SDK, Vulkan SDK, Python 3.12, **PowerShell 7** |

Put the tools on `PATH`, or write a script that does and point `XC2_ENV` at it.

## 1. Clone, and get the recompiler

```powershell
git clone https://github.com/weile10000/xc2-ns2-recomp.git
cd xc2-ns2-recomp
git clone https://github.com/drakolordx7/nxrecomp.git third_party/nxrecomp
```

## 2. Drop your dump in place

```
xc2\game\xc2ns301\   main, sdk, subsdk0, subsdk1, subsdk2, subsdk3, rtld, main.npdm
```

The romfs stays wherever you keep it; the launcher reads it from `NXRT_FS_ROMFS`.

## 3. Build the runtime (once)

Two source dependencies first (the graphics shell links an ASTC transcoder):

```powershell
pwsh -File third_party\fefw-recomp\tools\textures\scripts\fetch_third_party.ps1
```

Then the two builds. Pass the compilers explicitly, or a `clang.exe` on `PATH` wins over `clang-cl` and the build
dies on MSVC-only flags.

```powershell
cmake -S third_party/fefw-recomp/runtime -B third_party/fefw-recomp/build/runtime-gfx `
      -G Ninja -DCMAKE_BUILD_TYPE=Release -DNXRT_BUILD_GFX=ON -DNXRT_BUILD_GAMES=OFF -DNXRT_BUILD_TESTS=OFF `
      -DCMAKE_C_COMPILER=clang-cl -DCMAKE_CXX_COMPILER=clang-cl
cmake --build third_party/fefw-recomp/build/runtime-gfx --target nxrt nxrt_gfx

cmake -S third_party/fefw-recomp/runtime -B third_party/fefw-recomp/build/xc2-game-probe `
      -G Ninja -DCMAKE_BUILD_TYPE=Release -DNXRT_BUILD_GFX=ON -DNXRT_BUILD_GAMES=ON `
      -DNXRT_TEST_GAME=xc2ns2 -DNXRT_BUILD_TESTS=OFF `
      -DCMAKE_C_COMPILER=clang-cl -DCMAKE_CXX_COMPILER=clang-cl
cmake --build third_party/fefw-recomp/build/xc2-game-probe `
      --target nxrt_game_xc2ns2_core nxrt_game_xc2ns2_data
```

`-DNXRT_BUILD_GAMES=ON` is required for the second configure: without it CMake builds only the built-in test game
and `build-boot.ps1` finds no `nxrt_game_xc2ns2_core.lib`.

## 4. Lift, compile, link

```powershell
.\xc2\scripts\build.ps1 -Exefs xc2\game\xc2ns301 -Run:$false `
    -Modules 'main,sdk,subsdk0,subsdk1,subsdk2,subsdk3,rtld' `
    -LiftDir xc2\build\lift-301 -ObjDir xc2\build\obj-301 -LibDir xc2\build\lib-301
.\xc2\scripts\build-boot.ps1 -Exefs xc2\game\xc2ns301 -OutDir xc2\build\boot-301 `
    -LibDir xc2\build\lib-301 -MainLib xc2\build\lib-301\main.lib -Defines XC2_MODULES_7
```

The `link failed` at the end of `build.ps1` is expected: that is the stub link, `build-boot.ps1` does the real one.

## 5. Play

```powershell
.\tools\run\play-301.cmd -60
```

The first launch compiles pipelines: about 22 seconds with no frame, then it never happens again. Logs land in
`work\logs\play-301-<time>.log`.

## Common failures

| symptom | cause |
|---|---|
| `missing module: ...\main` | the dump is not in `xc2\game\xc2ns301\`, or you passed a relative `-Exefs` from another directory |
| `no python` | Python is not on `PATH` and `XC2_PYTHON` is unset |
| `ForEach-Object : ... -Parallel` | you are on Windows PowerShell 5.1; use `pwsh` (PowerShell 7) |
| `missing ...\nxrt_game_xc2ns2_core.lib` | step 3's second `cmake` block was skipped |
| the log has no `hook` lines at all | `xc2/sites/` is missing (it ships with the repository) |
| `ExeFS not found` | same as the first row |
| the window opens and closes | read the log: a missing romfs path (`NXRT_FS_ROMFS`) is the usual cause |
| 30 fps | add `-60`; the default is the game's 30 Hz step |

## Where to go next

- [docs/BUILD.md](BUILD.md) — the full build, including how to rebuild the shader cache
- [docs/COMPATIBILITY.md](COMPATIBILITY.md) — measured frame rates and the known issues
- [docs/ENVIRONMENT.md](ENVIRONMENT.md) — the toolchain in detail, and the pitfalls
