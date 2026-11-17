# tools/setup — the first-run engine

One script that takes a checkout and an empty folder to a playable install. The launcher
(`third_party/fefw-recomp/runtime/apps/launcher`) is only the view: it runs this and reads
`<install>/setup/status.json` back to draw its checklist.

```powershell
python tools\setup\xc2_setup.py --repo . --install D:\XC2 --nup D:\dumps\xc2.nup
python tools\setup\xc2_setup.py --repo . --install D:\XC2 --exefs D:\dump\xc2ns301 --romfs D:\dump\romfs
```

## The seven steps

Each one is skipped when its artifact is already there, so a second run is nearly free.

| step | what it does | artifact it looks for |
|---|---|---|
| `doctor` | `tools/bootstrap/doctor.ps1` | exit 0 |
| `sources` | nxrecomp from `deps.lock.json`, then `fetch_third_party.ps1` | `third_party/nxrecomp` |
| `runtime` | the two cmake configures and their builds | `third_party/fefw-recomp/build/*` |
| `ingest` | a `.nup`, or a folder that already holds the modules | `<install>/exefs`, `<install>/romfs` |
| `lift` | `xc2/scripts/build.ps1`, seven modules | `xc2/build/lib-301/*.lib` |
| `link` | `xc2/scripts/build-boot.ps1` | `xc2/build/boot-301/xc2_boot.exe` |
| `done` | `setup_state.tsv` and the romfs link | — |

Measured on a bare export with every build artifact removed: **8 min 13 s**, exit 0
(`runtime` 223.6 s, `lift` 259.6 s, the rest under 7 s). The exe it produced was the same size
as the maintainer build, byte for byte — the chain is deterministic.

## Two things that were bugs and are now load-bearing

**`XC2_ENV`.** The toolchain lives in a directory a script puts on PATH, so `cmake` is not
findable until that script has run. The engine sources it itself when the variable names it,
because the alternative is a first-time user meeting `WinError 2` from `subprocess`.

**The romfs link under `xc2/build/boot/game/romfs-301`.** `tools/run/play-301.cmd` sets
`NXRT_FS_ROMFS=game/romfs-301` relative to that working directory, which is what keeps a
checkout movable. Nothing used to create that path, so an install could report "ready to play"
and the first launch would die in `svcBreak` with exit code 4. The `done` step links it to
`<install>/romfs`; the relative path is the contract and stays as it is.

## Contract

`<install>/setup/status.json` — `state`, `step`, `steps[]` of `{name, state, seconds, note}`,
rewritten atomically on every change. `<install>/setup/setup.log` holds every command and its
output. `<install>/setup_state.tsv` is what the Win32 launcher's own check reads.

Nothing is written into the dump, and the romfs is linked, never copied — 28 GB is not a copy
anyone wants on a first run.

## Related

[../../docs/BUILD.md](../../docs/BUILD.md) is the manual version of these steps.
[../../docs/QUICKSTART.md](../../docs/QUICKSTART.md) is the short one with the failures people hit.
