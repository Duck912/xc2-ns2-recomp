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

```powershell
python tools/shader-cache/ard_index.py       --ard <romfs>\bf2.ard --out work\files.tsv
python tools/shader-cache/extract_embedded.py --ard <romfs>\bf2.ard --tsv work\files.tsv --out work\blocks
```

Then translate and install: `spirv_harness --batch work\blocks` produces the `.spv` files and the
`results.tsv` rows, and `tools/shader/install_shaders.ps1` puts them in the cache. That half is not ported
yet; see the note at the end.

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

## Not ported yet

The translate + install + repack half lives in a private driver that also contains the 3.0.0-only paths.
Porting it is the next step; until then, `spirv_harness --batch` plus `install_shaders.ps1` does the same
thing by hand.
