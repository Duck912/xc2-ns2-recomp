#!/usr/bin/env python3
"""Check the rules that must not break: nothing private is tracked, no game data, no non-ASCII build inputs.

    python tools/check_invariants.py            # everything
    python tools/check_invariants.py --hook     # only the checks that must pass before a commit

Exit code 0 when every check passes. Run it before committing and after pulling; the CI runs the same
checks that can run without the game files.
"""
import os
import subprocess
import sys

# Paths that must never be tracked. docs/internal holds the working notes, work/ the build scratch,
# xc2/game the player's own dump, xc2/build the build output.
PRIVATE_PREFIXES = ("docs/internal/", "work/", "xc2/game/", "xc2/build/")

GAME_EXTENSIONS = (
    ".nsp", ".xci", ".nca", ".nup", ".ard", ".arh", ".nro", ".nso",
    ".kef", ".kips", ".keys", ".pack",
)

# The lifter reads the site tables with the system locale encoding: one non-ASCII byte and the lift dies
# with a UnicodeDecodeError. The .cmd files must stay ASCII so cmd.exe never mangles them.
ASCII_GLOBS = ("xc2/sites/", "xc2/build/")


def tracked():
    out = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True).stdout
    return [line for line in out.splitlines() if line]


def check_private_not_tracked(files):
    bad = [f for f in files if f.startswith(PRIVATE_PREFIXES)]
    return (not bad, bad)


def check_game_data(files):
    bad = []
    for f in files:
        low = f.lower()
        if low.endswith(GAME_EXTENSIONS) or "/romfs/" in low or low.endswith("/main.npdm"):
            bad.append(f)
    return (not bad, bad)


def check_no_extension_exefs(files):
    """The ExeFS modules have no extension, so the list above cannot see them."""
    names = {"main", "sdk", "subsdk0", "subsdk1", "subsdk2", "subsdk3", "rtld"}
    bad = [f for f in files if f.startswith("xc2/game/") and f.rsplit("/", 1)[-1] in names]
    return (not bad, bad)


def check_ascii_inputs(files):
    bad = []
    candidates = [f for f in files if f.startswith(ASCII_GLOBS) and f.endswith(".txt")]
    for f in candidates:
        if not os.path.exists(f):
            continue
        with open(f, "rb") as fh:
            data = fh.read()
        if any(b > 127 for b in data):
            bad.append(f)
    # .cmd files, tracked or not, in the directories we ship
    for root, _dirs, names in os.walk("."):
        if "/.git" in root or root.startswith("./.git"):
            continue
        for n in names:
            if not n.endswith(".cmd"):
                continue
            p = os.path.join(root, n).replace("\\", "/").lstrip("./")
            if not p.startswith(("xc2/", "tools/")):
                continue
            if p.startswith("third_party/"):
                continue
            with open(p, "rb") as fh:
                data = fh.read()
            if any(b > 127 for b in data):
                bad.append(p)
    return (not bad, bad)


def check_cmd_crlf(files):
    """Our own .cmd files only: the vendored runtime keeps its own line endings."""
    bad = []
    for f in files:
        if not f.endswith(".cmd") or f.startswith("third_party/") or not os.path.exists(f):
            continue
        with open(f, "rb") as fh:
            data = fh.read()
        lone_lf = data.replace(b"\r\n", b"").count(b"\n")
        if lone_lf:
            bad.append("%s (%d lone LF)" % (f, lone_lf))
    return (not bad, bad)


CHECKS = [
    ("nothing private is tracked", check_private_not_tracked),
    ("no game data is tracked", check_game_data),
    ("no ExeFS module is tracked", check_no_extension_exefs),
]

HOOK_CHECKS = CHECKS  # the fast ones are also the critical ones

FULL_ONLY = [
    ("build inputs are ASCII", check_ascii_inputs),
    ("cmd files use CRLF", check_cmd_crlf),
]


def main():
    hook = "--hook" in sys.argv
    files = tracked()
    checks = HOOK_CHECKS if hook else CHECKS + FULL_ONLY
    failed = 0
    for name, fn in checks:
        ok, detail = fn(files)
        print(("  ok    " if ok else "  FAIL  ") + name)
        if not ok:
            failed += 1
            for d in detail[:20]:
                print("          " + str(d))
            if len(detail) > 20:
                print("          ... and %d more" % (len(detail) - 20))
    if failed:
        print("\n%d check(s) failed" % failed)
        return 1
    print("\nall invariants hold (%d tracked files)" % len(files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
