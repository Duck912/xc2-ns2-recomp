#!/usr/bin/env python3
"""Check every relative link in the tracked Markdown files.

Run from the repository root:  python tools/ci/check_links.py
Exit code 1 lists the links that point at a path git does not track.
"""
import re
import subprocess
import sys

LINK = re.compile(r"\]\(([^)#\s]+)")

# GitHub's own tabs: a link to one of these is a page of the repository, not a file in it.
GITHUB_PAGES = {
    "releases", "issues", "pulls", "wiki", "discussions", "actions", "security",
    "pulse", "network", "projects", "sponsors", "graphs", "settings", "tags",
}


def tracked_paths():
    out = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True).stdout
    files = set()
    dirs = set()
    for line in out.splitlines():
        if not line:
            continue
        files.add(line)
        parts = line.split("/")[:-1]
        for i in range(1, len(parts) + 1):
            dirs.add("/".join(parts[:i]))
    return files, dirs


def resolve(base, target):
    """Return the repo-relative path, or None when the target escapes the repo root.

    A link like `../../issues` is a GitHub page link (the repository's Issues tab), not a file: skip it.
    """
    parts = []
    for p in (base + "/" + target if base else target).split("/"):
        if p == "..":
            if not parts:
                return None
            parts.pop()
        elif p not in ("", "."):
            parts.append(p)
    return "/".join(parts)


def main():
    files, dirs = tracked_paths()
    checked = 0
    broken = []
    for md in sorted(f for f in files if f.endswith(".md")):
        base = md.rsplit("/", 1)[0] if "/" in md else ""
        with open(md, encoding="utf-8") as fh:
            text = fh.read()
        for m in LINK.finditer(text):
            target = m.group(1)
            if re.match(r"^[a-z][a-z0-9+.-]*:", target) or target.startswith("#"):
                continue
            path = resolve(base, target)
            if path is None:
                continue      # a link that leaves the repository is a GitHub page, not a file
            if path.split("/")[0] in GITHUB_PAGES:
                continue
            checked += 1
            if path not in files and path not in dirs:
                broken.append((md, target))
    print(f"checked {checked} relative links in {len(files)} tracked files")
    if broken:
        print(f"{len(broken)} broken:")
        for md, target in broken:
            print(f"  {md} -> {target}")
        return 1
    print("no broken links")
    return 0


if __name__ == "__main__":
    sys.exit(main())
