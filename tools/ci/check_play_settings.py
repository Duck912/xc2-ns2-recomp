#!/usr/bin/env python3
"""Every key controls.ini can hold must both be read and written by play_config.cpp.

The play settings page (gfx/play) keeps its own file, controls.ini, next to the runtime's nxrt.ini. nxrt.ini has
config/keys.tsv and tools/ci/config_table.py; controls.ini had nothing, and a setting that a card writes but the parser
never reads (or the other way round) fails silently: the menu looks fine, the value never comes back.

This gate compares the two sides of play_config.cpp. It is a set comparison, not a section-aware one: a key parsed in one
place and saved in another is fine, a key that exists on only one side is not. Keys that are deliberately one-sided go in
ALLOW so the reason is written down.

  python tools/ci/check_play_settings.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "third_party/fefw-recomp/runtime/src/gfx/play/play_config.cpp"

# Accepted one-sided keys, with the reason. Keep this short.
ALLOW = {
    "menu_touch": "legacy key, accepted and ignored since it never did anything",
    "preset": "read-only: fills view_distance and the rest, which are the keys written back",
    "fps_cap": "older spelling of fps_limit, still accepted so an old controls.ini keeps working",
    "yaw_source": "older mouse scale, converted to yaw/pitch on read; the writer emits yaw/pitch",
    "pitch_source": "older mouse scale, converted to yaw/pitch on read; the writer emits yaw/pitch",
}

SAVE_RE = re.compile(r'kv\("([^"]+)"')
PARSE_RE = re.compile(r'k == "([^"]+)"')


def main() -> int:
    text = SRC.read_text(encoding="utf-8", errors="replace")
    saved = set(SAVE_RE.findall(text))
    parsed = set(PARSE_RE.findall(text))
    only_saved = sorted(saved - parsed - set(ALLOW))
    only_parsed = sorted(parsed - saved - set(ALLOW))
    print(f"  {len(saved)} keys written, {len(parsed)} keys read, {len(ALLOW)} allowed one-sided")
    bad = 0
    for k in only_saved:
        print(f"  FAIL  written but never read back: {k} (the menu would forget it)")
        bad += 1
    for k in only_parsed:
        print(f"  FAIL  read but never written: {k} (the file would never gain it)")
        bad += 1
    if bad:
        print(f"\n{bad} key(s) exist on one side only. Add the other side, or add the key to ALLOW with a reason.")
        return 1
    print("  ok    every controls.ini key is read and written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
