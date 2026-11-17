# shader-cache

The tools that build the shader cache from **your own** game files.

The cache cannot be shipped. Every entry in it is SPIR-V translated from the game's own shaders, so it is a
derivative work; this repository carries the tools and nothing else. You run them against your own dump and
the result stays on your machine, in `xc2/build/boot/shader_cache`.

## Why two steps

| step | tool | what it does | measured here |
|---|---|---|---|
| 1 | `ard_index.py` | scans `bf2.ard` for the record magic and writes the record index | 10.2 GB in 7 s (52,409 records); 14.1 GB in 10 s (75,646) |
| 2 | `extract_embedded.py` | decodes the shader groups embedded inside those records | 13,059 groups, 78,793 blocks, 12,126 distinct, 84 s |

One command runs all of it:

```powershell
python tools/shader-cache/build_cache.py --ard <romfs>\bf2.ard `
    --cache xc2\build\boot\shader_cache\spirv `
    --harness third_party\fefw-recomp\tools\shaders\build\bin\Release\net10.0\spirv_harness.exe `
    --pack  xc2\build\boot\shader_cache\spirv.preload.pack --jobs 10
```

Measured on the retail 3.0.1 archive from an empty cache: **4.7 minutes**, ending with 12,104 shaders,
12,104 resource rows and a 53.9 MB pack, exit 0.

The three stages are also usable on their own:

```powershell
python tools/shader-cache/ard_index.py       --ard <romfs>\bf2.ard --out work\files.tsv
python tools/shader-cache/extract_embedded.py --ard <romfs>\bf2.ard --tsv work\files.tsv --out work\blocks
```

Then translate and install:

```powershell
python tools/shader-cache/build_cache.py --blocks work\blocks --cache xc2\build\boot\shader_cache\spirv `
    --harness third_party\fefw-recomp\tools\shaders\build\bin\Release\net10.0\spirv_harness.exe --jobs 10
```

It translates only what the cache is missing, installs the `.spv` files and their `results.tsv` rows, and can
rebuild the preload pack if you pass `--pack-tool` and `--pack`. `--dry-run` reports the plan, `--json` emits
one object per step, and the exit codes are 0 ok / 2 bad arguments / 3 input mismatch / 4 missing dependency /
5 a step failed — so a GUI or a wrapper can drive it without parsing prose.

## The record format

```
bf2.ard record
  0x00  "xbc1"          magic
  0x08  u32             uncompressed size
  0x0c  u32             compressed size
  0x14  name            NUL-terminated, padded to 0x30
  0x30  zlib payload
```

The records are **not contiguous**: their offsets are scattered with gaps of up to ~11 KB, so the index
cannot be produced by walking. Scanning for the magic and validating each candidate by inflating it is both
simpler and safe — on the retail archive 2 of 75,648 candidates are coincidences inside compressed data and
are dropped.

## The embedded group format

```
control sections first, contiguous, 0xd8 apart
code areas follow at  code_base = round_up(last control + 0xd8, 0x1000)
each block at the previous one rounded up to 0x100
```

A block is identified by the first 16 hex digits of the SHA-1 of its code — the same hash the runtime looks a
shader up by. Pass `--known` with a `manifest.tsv` from a `-dump` run and the summary reports how many of the
extracted blocks the game is actually known to ask for; without it the extraction still works, you just lose
that check.

## What the numbers mean

Of the 12,126 distinct blocks, **12,104 are real shaders** and 22 are misaligned garbage (their hashes do not
match anything the game requests, so they never reach the cache). With the 9,067 blocks already collected by
playing, that is the 21,171-entry cache this project runs with.

## Reproducing it

From a clean room — a pristine checkout, the player's own dump and romfs, and an empty cache — the result is
byte-identical to a cache built by hand:

| check | result |
|---|---|
| shaders the rebuild produces that are not in a hand-built cache | 0 of 12,104 |
| `.spv` byte-identical on a 50-file sample | 50 of 50 |
| rows carrying a non-empty `resources` field | 12,081 of 12,104 |
| pack entries whose hash is in the cache | 12,104 of 12,104 |

The header must come from the harness, never from a hardcoded string: the runtime locates the resource records
by looking for a column literally named `resources` (`parse_results_tsv` in `nvn_shaders.cpp`), so a cache
written under any other header silently loses every shader's descriptor bindings and the scene renders flat.

## Still missing

Nothing in this folder. The preload pack is now `pack.py`; pass `--pack <path>` and the chain rebuilds it.

## Platform

The three tools here are plain Python with no Windows calls, and the shader harness is .NET 10 with explicit
`OperatingSystem.IsWindows()` branches, so the whole shader pipeline runs on Linux and macOS as well. Only the
*runtime* build is Windows-bound today (clang-cl and the MSVC headers).
