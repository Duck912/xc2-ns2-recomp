#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""One table for the runtime's settings: config/keys.tsv, and the reference page built from it.

    python tools/ci/config_table.py --import-page   # bootstrap config/keys.tsv from docs/CONFIG.md (once)
    python tools/ci/config_table.py --emit          # write the key table of docs/CONFIG.md from the tsv
    python tools/ci/config_table.py --check         # the page is current, and every key the code reads is listed

The page stays the readable reference; the tsv is what machines read. --check fails when the two disagree, and when
a config_get_* call in the runtime names a key the table does not carry: that is how a setting becomes invisible.
Only the first table of the page (the one under "## Keys") belongs to this tool; the page has other tables.
"""
import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PAGE = os.path.join(ROOT, "third_party", "fefw-recomp", "runtime", "docs", "CONFIG.md")
TABLE = os.path.join(ROOT, "config", "keys.tsv")
BACKLOG = os.path.join(ROOT, "config", "undocumented.tsv")
RUNTIME = os.path.join(ROOT, "third_party", "fefw-recomp", "runtime", "src")

HEADER = "| Section | Key | Default | Environment variable | Read by | Meaning |"
RULE = "|---|---|---|---|---|---|"


def section_bounds(lines):
    start = next(i for i, l in enumerate(lines) if l.strip() == HEADER)
    rule = next(i for i, l in enumerate(lines) if i > start and l.strip() == RULE)
    end = rule + 1
    while end < len(lines) and lines[end].startswith("|"):
        end += 1
    return rule, end


def read_page():
    with open(PAGE, encoding="utf-8") as fh:
        lines = fh.read().split("\n")
    _rule, end = section_bounds(lines)
    rows = []
    for line in lines[:end]:
        if line.startswith("| ") and line.strip() != HEADER:
            rows.append([c.strip() for c in line.strip().strip("|").split("|")])
    return rows


def write_table(rows):
    os.makedirs(os.path.dirname(TABLE), exist_ok=True)
    with open(TABLE, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("# section\tkey\tdefault\tenv\tread_by\tmeaning\n")
        fh.write("# generated from docs/CONFIG.md by tools/ci/config_table.py --import-page; edit this file, then --emit\n")
        for cells in rows:
            fh.write("\t".join(cells) + "\n")


def read_table():
    rows = []
    with open(TABLE, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            rows.append(line.split("\t"))
    return rows


def emit():
    with open(PAGE, encoding="utf-8") as fh:
        lines = fh.read().split("\n")
    rule, end = section_bounds(lines)
    body = ["| " + " | ".join(cells) + " |" for cells in read_table()]
    out = lines[:rule + 1] + body + lines[end:]
    with open(PAGE, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(out))


KEY_RE = re.compile(r'config_get_(?:str|int|bool|float)\(\s*"([a-z0-9_]+)"\s*,\s*"([a-z0-9_]+)"')


def code_keys():
    found = set()
    for dirpath, _dirnames, names in os.walk(RUNTIME):
        for name in names:
            if not name.endswith((".cpp", ".h")):
                continue
            try:
                text = open(os.path.join(dirpath, name), encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            for m in KEY_RE.finditer(text):
                found.add((m.group(1), m.group(2)))
    return found


def read_backlog():
    """Keys the code reads but the page does not document yet: recorded, so a new one is a failure, not a surprise."""
    rows = {}
    if not os.path.exists(BACKLOG):
        return rows
    with open(BACKLOG, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            rows[(parts[0], parts[1])] = parts[2] if len(parts) > 2 else ""
    return rows


def write_backlog(items):
    with open(BACKLOG, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("# section\tkey\twhere it is read\n")
        fh.write("# Settings the code reads but docs/CONFIG.md does not describe yet. Add a row to the page instead when you\n")
        fh.write("# touch one; a key that is read and absent from both files fails tools/ci/config_table.py --check.\n")
        for s, k, where in sorted(items):
            fh.write("%s\t%s\t%s\n" % (s, k, where))


def check(strict=False):
    bad = 0
    rows = read_table()
    if rows != read_page():
        print("  FAIL  docs/CONFIG.md does not match config/keys.tsv: run --emit")
        bad += 1
    else:
        print("  ok    the reference page matches the table (%d rows)" % len(rows))
    documented = set()
    for cells in rows:
        if len(cells) >= 2 and cells[0].startswith("`") and cells[1].startswith("`"):
            documented.add((cells[0].strip("`").lower(), cells[1].strip("`").lower()))
    read = code_keys()
    missing = sorted(read - documented)
    backlog = read_backlog()
    new = [x for x in missing if x not in backlog]
    stale = [x for x in backlog if x not in read]
    if not missing:
        print("  ok    every key the code reads is in the table (%d read)" % len(read))
    elif new:
        for s, k in new[:20]:
            print("  FAIL  read by the code but in neither the table nor the backlog: [%s] %s" % (s, k))
        bad += 1
    else:
        print("  ok    %d keys are in the backlog and none of them is new" % len(missing))
    if stale:
        print("  note  %d backlog rows are no longer read: prune config/undocumented.tsv" % len(stale))
    if strict and missing:
        print("  FAIL  --strict: %d keys are still undocumented" % len(missing))
        bad += 1
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--import-page", action="store_true")
    g.add_argument("--emit", action="store_true")
    g.add_argument("--check", action="store_true")
    g.add_argument("--backlog", action="store_true", help="record the keys that are read but not documented")
    ap.add_argument("--strict", action="store_true", help="fail on keys the code reads but the table does not carry")
    a = ap.parse_args()
    if a.import_page:
        write_table(read_page())
        print("wrote %s" % TABLE)
        return 0
    if a.backlog:
        documented = set()
        for cells in read_table():
            if len(cells) >= 2 and cells[0].startswith("`") and cells[1].startswith("`"):
                documented.add((cells[0].strip("`").lower(), cells[1].strip("`").lower()))
        rows = []
        for s, k in sorted(code_keys() - documented):
            rows.append((s, k, ""))
        write_backlog(rows)
        print("wrote %s (%d keys)" % (BACKLOG, len(rows)))
        return 0
    if a.emit:
        emit()
        print("wrote %s" % PAGE)
        return 0
    return check(a.strict)


if __name__ == "__main__":
    sys.exit(main())
