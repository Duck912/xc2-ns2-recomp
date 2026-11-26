# Settings: the two files, the two layers, and who maintains what

There are two settings systems in this build, and they are read by different code:

| file | who reads it | what it holds | gate |
|---|---|---|---|
| `nxrt.ini` | the runtime (`src/**`) | behaviour of the runtime: rendering switches, media, memory, fs | `config/keys.tsv` + `tools/ci/config_table.py --check` |
| `controls.ini` | the play layer (`src/gfx/play/**`) | the settings page: window, resolution, upscale, audio, HDR, input, the menu itself | `tools/ci/check_play_settings.py` |

`nxrt.ini` is documented key by key in `third_party/fefw-recomp/runtime/docs/CONFIG.md`. `controls.ini` is written by
the settings page and read back at start; it is not documented per key, which is why the symmetry check exists.

## Who maintains what

The settings page came in from a community pull request (PR #27). It is ours to maintain now; the author stays a
contributor, not a dependency. The split that keeps it maintainable:

| layer | files | owner | notes |
|---|---|---|---|
| settings schema: defaults, parse, save, factory migrations | `play_types.h`, `play_config.cpp` | us | plain C++, no GUI involved |
| settings page: cards, layout, bilingual text | `play_ui.cpp`, `play_ui_about.cpp` | shared, upstream first | new or changed UI is offered to the author as a PR where practical |
| host: apply, window, present, input capture | `play.cpp`, `play_engine.cpp` | us | this layer predates the settings page |
| rendering of the overlay: ImGui + HDR path, CJK font, DPI | `overlay.cpp`, `platform.cpp` | us, but the least proven | the area we would ask the author about first |

## Adding a setting (the five steps)

1. **Default**: the field and its factory value in `play_types.h` (`Settings`, the matching section struct).
2. **Parse**: one branch in `apply_fixed()` in `play_config.cpp` — `if (k == "name") return set_bool(&s->section.name);`.
3. **Save**: one `kv("name", ...)` in the same file's writer.
4. **Card**: one `card_toggle` / `card_choice` / `card_slider_*` in `play_ui.cpp`, with a Chinese and an English label.
   Live settings call `set_*_live(host, ...)`; the rest wait for **Apply & Save**.
5. **Gate**: `python tools/ci/check_play_settings.py` — a key that is parsed but never written (or the reverse) fails
   here, which is exactly the failure that makes a menu silently forget a value.

If the setting changes a default that existing files already hold, add a factory change instead of silently changing the
constant: `kRuntimeFactoryChanges` in `play_config.cpp` plus `kRuntimeFactoryRev`, so an old `controls.ini` moves once
and a value the player picked stays. The F10 counter hotkey was fixed that way (revision 3, `F2` → `F10`).

If the setting is one the *runtime* must see too, it belongs in `nxrt.ini` as well: add the row to `config/keys.tsv`,
run `python tools/ci/config_table.py --emit`, and wire the play layer to it in `play.cpp` (see `upscale.mode`). Two files
holding the same concept is the one thing this design does not protect against; when it happens, say in both places which
one wins.

## Running the gates

```powershell
python tools/ci/check_invariants.py     # repository shape, no private paths and no game data
python tools/ci/check_links.py          # every relative link resolves
python tools/ci/config_table.py --check # nxrt.ini keys: documented, and every key the code reads is in the table
python tools/ci/check_play_settings.py  # controls.ini keys: read and written, never one side only
```

## When the page misbehaves

- **A setting does not stick**: run `check_play_settings.py`; if it passes, the card is not calling `apply`/`set_*_live`.
- **A key none of the cards show**: it is a leftover in `controls.ini`; the parser keeps accepting it (`ALLOW` in the gate).
- **The menu renders but the picture does not change**: check whether the setting only applies at the next start (the
  first four display options do — the game builds its render targets once), then look at `nxrt.log` for the value the
  runtime reports.
- **The overlay is missing entirely**: the game still runs; `--gfx window` plus editing the two files by hand is the way
  back in. The settings page is not a single point of failure.
