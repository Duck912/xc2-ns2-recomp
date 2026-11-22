# tools/mods — the mod path's own tools

Everything the mod work needs lives here, so a future round finds it in one place instead of across
`tools/analysis` and `tools/shader`.

| file | what | state |
|---|---|---|
| `asset_index.py` | **M0**: one table of every file the game can read — romfs, `bf2.ard`, add-on content | works |
| `mod_check.py` | which files of a mod exist in a dump, which are missing, which differ (needs M0) | not started |
| `mod_pack.py` | validates and packs a mod folder (manifest, path escapes, no game data) | not started |

## What it reads

```
<dump>/base/romfs/            bf2.ard, bf2.arh, stream/, sound/
<dump>/dlc/<id>/romfs/        or <id>/0/romfs — both layouts the runtime accepts
```

## What it writes (never committed — derived from the player's own dump)

```
work/mods/assets.tsv           source, path, kind, size, unc, comp, offset, checksum, sha256
work/mods/assets-summary.json  counts, bytes, per-kind totals, what was skipped and why, timings
```

`source` is `romfs`, `ard` (inside the archive) or `dlc:<16-hex id>`. A loose file's `sha256` is filled up to
`--hash-limit-mb`; an archive record carries the archive's own `checksum` and its offsets instead.

```powershell
tools\python\python.exe tools\mods\asset_index.py --romfs "<dump>\base\romfs" --out work\mods
tools\python\python.exe tools\mods\asset_index.py --romfs "<dump>\base\romfs" --no-archive   # fast, loose files only
```

## The contract the later milestones rely on

* **M1/M2** resolve a mod path by looking it up in `assets.tsv`: a path found under `ard` needs the archive
  override, a path found under `romfs` or `dlc:<id>` is a plain file.
* **mod_check** reports, per file: `found` / `missing` / `size differs` / `sha256 differs` — which is what a
  player needs when an NS1 mod is offered for the NS2 edition.
* The catalog holds **paths, sizes and hashes only** — never file contents, and never anything from the archive's
  payload.
