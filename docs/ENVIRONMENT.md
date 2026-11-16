# Environment and toolchain

Everything needed to lift, compile and run the game on Windows. Run
`pwsh -NoProfile -File tools\env\check.ps1` first: it reports what is missing and can fill in the Python
packages the lifter needs.

## 1. Host toolchain

Put these on `PATH`, or point `XC2_ENV` at a script that does it (the build scripts dot-source that script):

| tool | used for |
|---|---|
| CMake 3.28+ | configuring `third_party/fefw-recomp/build/runtime-gfx` |
| Ninja | the CMake generator |
| LLVM / `clang-cl` 18+ | compiling the lifted C++ (`llvm-objdump`, `llvm-mc`, `llvm-cxxfilt` come along) |
| MSVC 14.4x + Windows SDK 10.0.2xxxx | headers and libraries `clang-cl` links against |
| Vulkan SDK 1.4+ | `glslc`, `spirv-as`, `spirv-dis`, `spirv-val`, validation layers |
| .NET SDK 10 | the Ampere shader front end |
| Python 3.12 | the lifter and the analysis tools |
| NASM, Rust/cargo | only some upstream pieces |
| Git | obviously |

```powershell
$env:XC2_ENV = '<path to your env script>.ps1'     # optional, if the tools are not on PATH
```

## 2. Python packages

| package | needed by |
|---|---|
| `lz4` | the lifter: NSO LZ4 segments (`nxrecomp/nso.py`) |
| `capstone` 5.0.9 exactly | the lifter: jump-table disassembly (`nxrecomp/jumptables.py`) |
| `unicorn` | the upstream differential oracle (optional) |
| `zstandard` | `tools/analysis/nup_extract.py` (zstd records in a `.nup`) |
| `pyelftools` | only the upstream survey tools (optional) |

`tools\env\check.ps1` installs `lz4`/`capstone`/`unicorn` for you if it can find them locally.
`ModuleNotFoundError: No module named 'lz4'` (from `nso_info`) or `'capstone'` (from `jumptables`) means the
environment is incomplete.

The project's own tools do **not** need them: `nso_seg.py` carries a pure-Python LZ4 block decoder and
`symat.py` reads the NSO header directly.

## 3. Build and run

| what | command | measured |
|---|---|---|
| the runtime | `cmake --build third_party/fefw-recomp/build/runtime-gfx --target nxrt nxrt_gfx` | a few seconds for one file |
| lift + compile | `xc2\scripts\build.ps1 -Exefs xc2\game\xc2ns301 -Run:$false -Modules main,sdk,subsdk0,subsdk1,subsdk2,subsdk3,rtld` | lift 13 s + compile 4 s for `main`; longer for the rest |
| link | `xc2\scripts\build-boot.ps1 -Exefs xc2\game\xc2ns301 -OutDir xc2\build\boot-301 -LibDir xc2\build\lib -MainLib xc2\build\lib\main.lib -Defines XC2_MODULES_7` | ~50 s, 144.5 MB |
| play | `tools\run\play-301.cmd -60` | cold start 2–3 s to the title applet |

The stub link at the end of `build.ps1` always fails; that is by design and does not affect `build-boot.ps1`.

## 4. Data layout (read-only, never committed)

| path | what | size |
|---|---|---|
| `xc2\game\xc2ns301\` | the 3.0.1 ExeFS: `main`, `sdk`, `subsdk0..3`, `rtld`, `main.npdm` | 17 MB |
| `<your romfs 3.0.1>\` | `bf2.ard`, `bf2.arh`, `stream\` — `NXRT_FS_ROMFS` at run time | 25.6 GB |
| `<your dlc>\` | optional add-on content — `NXRT_AOC_DIR` | — |
| `xc2\build\boot\shader_cache\` | the translated shaders (`spirv\<hash>.spv`) | — |
| `%APPDATA%\Xenoblade2NS2RecompPC\save\` | save data | 1.1 MB |
| `work\` | scratch: dumps, logs, analysis output | git-ignored |

## 5. Tools

| task | tool |
|---|---|
| environment check | `tools\env\check.ps1` |
| address → symbol | `tools\analysis\symat.py --dump <module>` |
| disassemble a range | `tools\analysis\dis.py <start> <stop>` |
| NSO → segments | `tools\analysis\nso_seg.py <module>` |
| `.nup` list / verify / unpack | `tools\analysis\nup_extract.py --list / --verify / --pkg N --out DIR` |
| pull a file out of `bf2.ard` | `tools\analysis\ard_get.py` |
| find / read bdat tables | `bdat_scan.py`, `bdat_table.py`, `bdat_cols.py` |
| patch one instruction (diagnostic) | `patch <addr> <orig> <new>` in `xc2\build\sites-<module>.txt`, then delete `.base` and re-lift |
| log a function's arguments | `entryhook` + `NXRT_DEBUG_ENTRY` |
| dump memory at a crash | `[debug] dump_ptrs` / `dump_at` |
| replay phase timings | `[nvn] replay_stats = 60` + `tools\analysis\replay_stats.py` |
| GPU pass timings | `[prof] gpu_passes = 1` |
| launch logs and session census | `work\logs\`, `tools\analysis\session_census.py` |

## 6. Pitfalls

1. `xc2\build\*.txt` must stay **pure ASCII** (the lifter reads those tables as ANSI).
2. After editing `sites-<module>.txt`, delete `xc2\build\lift\<module>\.base`, or the lift is not redone
   (freshness is judged by the ExeFS mtime only).
3. The `link failed` at the end of `build.ps1` is expected; the real link is `build-boot.ps1`.
4. Wait about 25 s after the game exits before starting it again; a fast relaunch hits
   `MapViewOfFileEx error 487` and the game asserts.
5. The game is single-instance: linking while it runs fails with `permission denied`.
6. `snap_d*` files survive across runs — delete them before taking measurements.
7. Do not set `[gfx] present_mode = mailbox`: this HDR surface does not support it and it silently degrades.
8. A `shot_frames` step of 1 drops the frame rate to about 4 fps; use `trace_frame` for per-frame timing.
9. Shader patch installation must also drop `spirv.preload.pack`: the pack is read before loose `.spv` files and
   shadows an edited one.
