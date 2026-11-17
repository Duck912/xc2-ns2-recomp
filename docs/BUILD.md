# Building

Windows x86-64 only. The build has three parts: the runtime libraries (C++/Vulkan), the lifted game code
(the NSO modules translated to C++), and the boot executable that links them.

The reference toolchain is described in [docs/ENVIRONMENT.md](ENVIRONMENT.md); this page is the shortest path.

> In a hurry? [QUICKSTART.md](QUICKSTART.md) has the five steps and the common failures. This page is the full
> build, including the shader cache.

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
| Ryujinx's shader translator | `pwsh -File third_party/fefw-recomp/tools/shaders/scripts/setup_ryujinx.ps1`, then `dotnet build third_party/fefw-recomp/tools/shaders/harness/SpirvHarness.csproj -c Release` |

The translator script needs no arguments. It stages the three projects it uses (Ryujinx.Common, Spv.Generator,
Ryujinx.Graphics.Shader) from a local checkout if you have one at `third_party/fefw-recomp/refs/ryubing`, and
otherwise downloads the Ryubing fork's own archive — `git.ryujinx.app/projects/Ryubing`, commit `a82350bb77`,
MIT, 12.2 MB, no account. That archive is the only external source besides the recompiler and CMake's deps; pass
`-Ryubing <checkout>` to use a different one.

Verified from an empty tree: the script downloads 12.2 MB in about 5 s and the harness then builds in about 15 s
with 0 errors.

## 3. Your game files

The recompiler reads the game's own ExeFS; nothing is downloaded by this repository.

```
xc2/game/xc2ns301/       main, sdk, subsdk0, subsdk1, subsdk2, subsdk3, rtld, main.npdm   (the 3.0.1 program)
<your romfs 3.0.1>/      bf2.ard, bf2.arh, stream/            (NXRT_FS_ROMFS at run time)
<your dlc>/              optional                               (NXRT_AOC_DIR at run time)
```

That is the **folder** layout. If your dump is a single `.nup` package instead — the format a55uka's tool writes —
unpack it first; the two parts land exactly where the paths above expect them:

```powershell
# the program (exefs): main, main.npdm, sdk, subsdk0..3, rtld
python tools\analysis\nup_extract.py --nup <your dump>.nup --pkg 0 --part exefs --out xc2\game\xc2ns301

# the romfs: bf2.ard, bf2.arh, stream/
python tools\analysis\nup_extract.py --nup <your dump>.nup --pkg 0 --part romfs --out <your romfs 3.0.1>

# the add-on content, if you have it (package 7)
python tools\analysis\nup_extract.py --nup <your dump>.nup --pkg 7 --out <your dlc>
```

`--list` prints the packages a `.nup` holds and `--verify` checks every extent and SHA-256 first, which is
worth doing once: it catches a truncated dump before the build blames itself. It needs `zstandard`
(`pip install zstandard`) only for packages that are actually compressed.

## 4. Build

### 4.1 the runtime (once, and after changing `third_party/fefw-recomp/runtime/**`)

The graphics shell links an ASTC-to-BC7 transcoder, so its two source dependencies have to be present first. This
fetches astc-encoder 5.7.0, bc7enc_rdo and the ISPC compiler into `tools/textures/third_party` (git-ignored):

```powershell
pwsh -File third_party\fefw-recomp\tools\textures\scripts\fetch_third_party.ps1
```

Then the two builds. Pass the compilers explicitly: a `clang.exe` on `PATH` otherwise wins over `clang-cl` and the
build dies on MSVC-only flags.

```powershell
# the graphics shell
cmake -S third_party/fefw-recomp/runtime -B third_party/fefw-recomp/build/runtime-gfx `
      -G Ninja -DCMAKE_BUILD_TYPE=Release -DNXRT_BUILD_GFX=ON -DNXRT_BUILD_GAMES=OFF -DNXRT_BUILD_TESTS=OFF `
      -DCMAKE_C_COMPILER=clang-cl -DCMAKE_CXX_COMPILER=clang-cl
cmake --build third_party/fefw-recomp/build/runtime-gfx --target nxrt nxrt_gfx

# the game module the boot executable links against (nxrt_game_xc2ns2_core / _data)
cmake -S third_party/fefw-recomp/runtime -B third_party/fefw-recomp/build/xc2-game-probe `
      -G Ninja -DCMAKE_BUILD_TYPE=Release -DNXRT_BUILD_GFX=ON -DNXRT_BUILD_GAMES=ON `
      -DNXRT_TEST_GAME=xc2ns2 -DNXRT_BUILD_TESTS=OFF `
      -DCMAKE_C_COMPILER=clang-cl -DCMAKE_CXX_COMPILER=clang-cl
cmake --build third_party/fefw-recomp/build/xc2-game-probe `
      --target nxrt_game_xc2ns2_core nxrt_game_xc2ns2_data
```

The second configure is what `build-boot.ps1` expects: it links `build/xc2-game-probe/games/xc2ns2/*.lib`. It is a
separate build directory because the game module needs the runtime built with `NXRT_BUILD_GAMES=ON`, which the
graphics shell above deliberately turns off.

### 4.2 lift and compile the guest modules (13 s + 4 s for `main`, longer for the rest)

The lifter also needs the hook sites: `xc2/sites/sites-<module>.txt` ship with the repository and are picked up
automatically. Put your own additions in `xc2/build/sites-<module>.txt`, which takes precedence — see
[xc2/sites/README.md](../xc2/sites/README.md).

`-LiftDir`, `-ObjDir` and `-LibDir` choose where the lift, the objects and the per-module libraries go. The
defaults (`build\lift`, `build\obj`, `build\lib`) are the four-module development route; the retail command above
keeps its own `-301` directories so the two never overwrite each other.

```powershell
.\xc2\scripts\build.ps1 -Exefs xc2\game\xc2ns301 -Run:$false `
    -Modules 'main,sdk,subsdk0,subsdk1,subsdk2,subsdk3,rtld' `
    -LiftDir xc2\build\lift-301 -ObjDir xc2\build\obj-301 -LibDir xc2\build\lib-301
```

The stub link at the end of `build.ps1` always fails — that is expected, `build-boot.ps1` does the real link.

### 4.3 the boot executable (~50 s)

```powershell
.\xc2\scripts\build-boot.ps1 -Exefs xc2\game\xc2ns301 -OutDir xc2\build\boot-301 `
    -LibDir xc2\build\lib-301 -MainLib xc2\build\lib-301\main.lib -Defines XC2_MODULES_7
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
