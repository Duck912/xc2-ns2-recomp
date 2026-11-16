# Building

Windows x86-64 only. The build has three parts: the runtime libraries (C++/Vulkan), the lifted game code
(the NSO modules translated to C++), and the boot executable that links them.

The reference toolchain is described in [docs/ENVIRONMENT.md](ENVIRONMENT.md); this page is the shortest path.

## 1. Toolchain

| what | version used here | why |
|---|---|---|
| Visual Studio Build Tools (MSVC + Windows SDK) | 2022+, MSVC 14.44, SDK 10.0.26100 | clang-cl takes its headers and import libraries |
| LLVM | 23.1.5 | `clang-cl`, `llvm-lib`, `llvm-objdump`, `llvm-cxxfilt` |
| CMake + Ninja | 3.25+ | the runtime build |
| .NET SDK | 10 | the shader harness (Ryujinx's translator) |
| Vulkan SDK | 1.4.363+ | `spirv-as`, `spirv-dis`, `spirv-val`, `glslc` |
| Python | 3.12, with `lz4` and `capstone` | the lifter (`third_party/nxrecomp`) |
| Git | any | |
| PowerShell | **7+** (`pwsh`) | the build uses `ForEach-Object -Parallel`, which Windows PowerShell 5.1 does not have; run the scripts with `pwsh`, not `powershell.exe` |

Either put all of them on `PATH`, or set **`XC2_ENV`** to a PowerShell script that does; the build scripts
dot-source it when it is set. **`XC2_PYTHON`** names the interpreter if `python` on `PATH` is not the one
with `lz4`/`capstone`.

```powershell
$env:XC2_ENV    = 'C:\path\to\toolchain\env.ps1'
$env:XC2_PYTHON = 'C:\path\to\python.exe'
```

## 2. Sources that are not checked in

| what | how |
|---|---|
| `third_party/nxrecomp` (the recompiler) | from the repository root: `git clone https://github.com/drakolordx7/nxrecomp.git third_party/nxrecomp` — the version this build used is commit `e7a5a54` (2026-11-14) |
| `third_party/deps` (SDL3, Vulkan-Headers, volk, VMA, ImGui, zstd, dav1d) | fetched by CMake's `FetchContent` on the first configure (`runtime/cmake/gfx_deps.cmake`) |
| Ryujinx's shader translator | `pwsh -File third_party/fefw-recomp/tools/shaders/scripts/setup_ryujinx.ps1 -Ryubing <checkout>`, then `dotnet build third_party/fefw-recomp/tools/shaders/harness/SpirvHarness.csproj -c Release` |

## 3. Your game files

The recompiler reads the game's own ExeFS; nothing is downloaded by this repository.

```
xc2/game/xc2ns301/       main, sdk, subsdk0, subsdk1, subsdk2, subsdk3, rtld, main.npdm   (the 3.0.1 program)
<your romfs 3.0.1>/      bf2.ard, bf2.arh, stream/            (NXRT_FS_ROMFS at run time)
<your dlc>/              optional                               (NXRT_AOC_DIR at run time)
```

## 4. Build

### 4.1 the runtime (once, and after changing `third_party/fefw-recomp/runtime/**`)

```powershell
# the graphics shell
cmake -S third_party/fefw-recomp/runtime -B third_party/fefw-recomp/build/runtime-gfx `
      -G Ninja -DCMAKE_BUILD_TYPE=Release -DNXRT_BUILD_GFX=ON -DNXRT_BUILD_GAMES=OFF -DNXRT_BUILD_TESTS=OFF
cmake --build third_party/fefw-recomp/build/runtime-gfx --target nxrt nxrt_gfx

# the game module the boot executable links against (nxrt_game_xc2ns2_core / _data)
cmake -S third_party/fefw-recomp/runtime -B third_party/fefw-recomp/build/xc2-game-probe `
      -G Ninja -DCMAKE_BUILD_TYPE=Release -DNXRT_BUILD_GFX=ON -DNXRT_BUILD_GAMES=ON `
      -DNXRT_TEST_GAME=xc2ns2 -DNXRT_BUILD_TESTS=OFF
cmake --build third_party/fefw-recomp/build/xc2-game-probe `
      --target nxrt_game_xc2ns2_core nxrt_game_xc2ns2_data
```

The second configure is what `build-boot.ps1` expects: it links `build/xc2-game-probe/games/xc2ns2/*.lib`. It is a
separate build directory because the game module needs the runtime built with `NXRT_BUILD_GAMES=ON`, which the
graphics shell above deliberately turns off.

### 4.2 lift and compile the guest modules (13 s + 4 s for `main`, longer for the rest)

```powershell
.\xc2\scripts\build.ps1 -Exefs xc2\game\xc2ns301 -Run:$false `
    -Modules 'main,sdk,subsdk0,subsdk1,subsdk2,subsdk3,rtld'    # quoted or bare, both parse to the seven names
```

The stub link at the end of `build.ps1` always fails — that is expected, `build-boot.ps1` does the real link.

### 4.3 the boot executable (~50 s)

```powershell
.\xc2\scripts\build-boot.ps1 -Exefs xc2\game\xc2ns301 -OutDir xc2\build\boot-301 `
    -LibDir xc2\build\lib -MainLib xc2\build\lib\main.lib -Defines XC2_MODULES_7
```

Produces `xc2\build\boot-301\xc2_boot.exe`, which is what `tools\run\play-301.cmd` runs. Without the flags the
script links the older four-module route into `xc2\build\boot\`.

### 4.4 shaders

Shaders are translated offline into `xc2\build\boot\shader_cache\spirv` (SPIR-V keyed by the shader hash).
The incremental path needs nothing from this repository:

1. run the game **with `-dump`** — `tools\run\play-301.cmd -dump`; collection is off by default, and every
   shader the game asks for that the cache lacks is written to `work/shader_dump-*/`;
2. after the game exits, `pwsh -File tools\shader\install_shaders.ps1 -Dump work\shader_dump-*` translates that
   dump and installs it into the cache. It stops if the translator fails, replaces the `results.tsv` rows of hashes
   it re-translated, and drops `spirv.preload.pack` when a shader's bytes changed — the pack is read before the
   loose `.spv` files, so without that the old entry would keep winning.

Two shaders carry hand-made fixes (a fog-layer correction and a UV-divide correction). They are **derived from the
game's own shaders and are therefore not distributed**: the folder xc2\patches\ is yours to create, and
xc2\scripts\patch-shaders.ps1 installs whatever is in it (or exits cleanly when the folder is absent). Without
them the game runs, with those two visual defects.

A *complete* cache (21,171 shaders for 3.0.1) also scans the resource archives for shader blocks embedded in
resource records and in the ExeFS `.rodata`. That driver lives in the private work tree
(`work/oracle/build_shaders.py`) and is not part of this repository yet — with it the cache can be rebuilt in
one pass; without it the incremental path above fills it in as you play.

## 5. Run

```powershell
.\tools\run\play-301.cmd            # the 3.0.1 route; see the header of that file for every switch
```

Logs go to `work/logs/play-301-<time>.log`.

## 6. Notes

* Never commit `xc2/game/**`, `xc2/build/**` or `work/**`: they hold game data and multi-GB build products
  (`.gitignore` already covers them).
* The shader cache is keyed by shader hash: do not delete it. If a translation changes, translate the affected
  hashes and let `install_shaders.ps1` replace those entries.
* The single-instance rule: `xc2_boot.exe` maps its data files exclusively — after killing it, wait ~25 s before
  starting it again, and close the game before linking.
