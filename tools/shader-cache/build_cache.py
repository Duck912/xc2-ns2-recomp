#!/usr/bin/env python3
"""Translate the extracted shader blocks and install them into the cache.

    python tools/shader-cache/build_cache.py --blocks <dir> --cache <dir> --harness <spirv_harness>

This is the second half of the pipeline. The first half is:

    ard_index.py --ard <romfs>/bf2.ard --out files.tsv
    extract_embedded.py --ard <romfs>/bf2.ard --tsv files.tsv --out blocks

and then this script takes the blocks, translates the ones the cache is missing, installs the .spv files and
their resource rows, and (optionally) rebuilds the preload pack.

Design notes, because this is meant to be driven by something other than a person:

  * no prompts, no environment assumptions: every path is an argument;
  * --json emits one object per step, so a shell (a GUI, a wrapper script) can show progress without
    parsing prose;
  * exit codes: 0 ok, 2 bad arguments, 3 input does not match, 4 a dependency is missing, 5 a step failed;
  * idempotent: blocks already in the cache are skipped, so re-running after an interruption continues.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

EXIT_OK = 0
EXIT_ARGS = 2
EXIT_INPUT = 3
EXIT_DEP = 4
EXIT_STEP = 5


class Reporter:
    """Prose by default, one JSON object per event with --json."""

    def __init__(self, as_json):
        self.as_json = as_json

    def step(self, name, **fields):
        if self.as_json:
            fields["event"] = "step"
            fields["step"] = name
            print(json.dumps(fields, ensure_ascii=False), flush=True)
        else:
            extra = "  " + " ".join("%s=%s" % (k, v) for k, v in fields.items()) if fields else ""
            print("[%s]%s" % (name, extra), flush=True)

    def say(self, text):
        if not self.as_json:
            print("      " + text, flush=True)

    def done(self, **fields):
        if self.as_json:
            fields["event"] = "done"
            print(json.dumps(fields, ensure_ascii=False), flush=True)
        else:
            print("", flush=True)
            for k, v in fields.items():
                print("  %-18s %s" % (k + ":", v), flush=True)

    def fail(self, code, message):
        if self.as_json:
            print(json.dumps({"event": "error", "code": code, "message": message}, ensure_ascii=False), flush=True)
        else:
            print("ERROR: " + message, file=sys.stderr, flush=True)


def read_manifest(path):
    """The blocks manifest: one row per distinct block, with the hash in column code_sha1_16."""
    rows = []
    with open(path, encoding="utf-8") as f:
        header = f.readline().rstrip("\n").split("\t")
        try:
            i_hash = header.index("code_sha1_16")
            i_code = header.index("code_file")
            i_ctrl = header.index("ctrl_file")
        except ValueError:
            raise SystemExit("the manifest has no code_sha1_16/code_file/ctrl_file column: " + path)
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) > max(i_hash, i_code, i_ctrl):
                rows.append({"hash": p[i_hash], "code": p[i_code], "ctrl": p[i_ctrl], "raw": line.rstrip("\n")})
    return header, rows


def cached(path):
    if not os.path.isdir(path):
        return set()
    return set(os.path.splitext(n)[0] for n in os.listdir(path) if n.endswith(".spv"))


def main(argv):
    ap = argparse.ArgumentParser(description="Translate extracted shader blocks and install them.")
    ap.add_argument("--blocks", required=True, help="folder written by extract_embedded.py")
    ap.add_argument("--cache", required=True, help="the spirv cache folder (xc2/build/boot/shader_cache/spirv)")
    ap.add_argument("--harness", required=True, help="spirv_harness executable")
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--stage", default="", help="scratch folder (default: <blocks>/../build_cache)")
    ap.add_argument("--pack-tool", default="", help="optional pack_full.py; without it the pack is left alone")
    ap.add_argument("--pack", default="", help="the spirv.preload.pack to rebuild (needs --pack-tool)")
    ap.add_argument("--dry-run", action="store_true", help="report what would be translated, change nothing")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    rep = Reporter(a.json)

    manifest = os.path.join(a.blocks, "manifest.tsv")
    if not os.path.exists(manifest):
        rep.fail(EXIT_INPUT, "no manifest.tsv in " + a.blocks)
        return EXIT_INPUT
    if not os.path.exists(a.harness):
        rep.fail(EXIT_DEP, "no shader harness at " + a.harness)
        return EXIT_DEP

    header, rows = read_manifest(manifest)
    if not rows:
        rep.fail(EXIT_INPUT, "the manifest has no rows")
        return EXIT_INPUT
    have = cached(a.cache)
    missing = [r for r in rows if r["hash"] not in have]
    rep.step("plan", blocks=len(rows), cached=len(have), missing=len(missing))
    if not missing:
        rep.done(translated=0, installed=0, note="the cache already covers every block")
        return EXIT_OK
    if a.dry_run:
        rep.done(translated=0, installed=0, would_translate=len(missing), note="dry run")
        return EXIT_OK

    stage = a.stage or os.path.join(os.path.dirname(os.path.abspath(a.blocks)), "build_cache")
    stage_in = os.path.join(stage, "in")
    stage_out = os.path.join(stage, "out")
    for d in (stage_in, stage_out):
        if os.path.isdir(d):
            shutil.rmtree(d)
        os.makedirs(d)

    rep.step("stage", folder=stage_in)
    with open(os.path.join(stage_in, "manifest.tsv"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\t".join(header) + "\n")
        for r in missing:
            for name, src in ((r["code"], os.path.join(a.blocks, r["code"])),
                              (r["ctrl"], os.path.join(a.blocks, r["ctrl"]))):
                if not os.path.exists(src):
                    rep.fail(EXIT_INPUT, "the manifest names a file that is not there: " + src)
                    return EXIT_INPUT
                shutil.copy2(src, os.path.join(stage_in, name))
            f.write(r["raw"] + "\n")

    rep.step("translate", count=len(missing), jobs=a.jobs)
    cmd = [a.harness, "--batch", stage_in, "--out", stage_out, "--jobs", str(a.jobs)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        rep.say((r.stderr or r.stdout or "").strip()[-800:])
        rep.fail(EXIT_STEP, "the shader harness failed with exit %d" % r.returncode)
        return EXIT_STEP

    rep.step("install", cache=a.cache)
    os.makedirs(a.cache, exist_ok=True)
    copied = 0
    for n in sorted(os.listdir(stage_out)):
        if n.endswith(".spv"):
            shutil.copy2(os.path.join(stage_out, n), os.path.join(a.cache, n))
            copied += 1

    # Only the rows of shaders that actually produced a .spv: the harness writes a row for a block it could
    # not translate too, and a row without a .spv would make the runtime resolve a shader that is not there.
    produced = set(os.path.splitext(n)[0] for n in os.listdir(stage_out) if n.endswith(".spv"))
    added = 0
    results = os.path.join(a.cache, "results.tsv")
    new_rows = os.path.join(stage_out, "results.tsv")
    if os.path.exists(new_rows):
        known = set()
        head = "hash\tentry\trec_off\tprog_off\tctrl_off\tcode_len\tstage"
        if os.path.exists(results):
            with open(results, encoding="utf-8") as f:
                head = f.readline().rstrip("\n")
                for line in f:
                    if line.strip():
                        known.add(line.split("\t", 1)[0])
        add = []
        with open(new_rows, encoding="utf-8") as f:
            f.readline()
            for line in f:
                line = line.rstrip("\n")
                if line and line.split("\t", 1)[0] not in known and line.split("\t", 1)[0] in produced:
                    add.append(line)
        if add:
            if os.path.exists(results):
                bak = results + ".bak-before-build"
                if not os.path.exists(bak):
                    shutil.copy2(results, bak)
            else:
                with open(results, "w", encoding="utf-8", newline="\n") as f:
                    f.write(head + "\n")
            with open(results, "a", encoding="utf-8", newline="\n") as f:
                for line in add:
                    f.write(line + "\n")
            added = len(add)

    packed = "left alone"
    if a.pack_tool and a.pack:
        rep.step("pack", tool=a.pack_tool)
        cmd = [sys.executable, a.pack_tool, "--rows", results, "--cache", a.cache,
               "--out", os.path.join(stage, "spirv.preload.pack"), "--install", a.pack]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            rep.say((r.stderr or r.stdout or "").strip()[-800:])
            rep.fail(EXIT_STEP, "the pack tool failed with exit %d" % r.returncode)
            return EXIT_STEP
        packed = a.pack

    after = cached(a.cache)
    # A block the harness could not translate is not a failure of this script: on the retail archive 22 of the
    # 12,126 extracted blocks are misaligned garbage whose hashes the game never asks for. Report them, and only
    # fail when nothing at all came out.
    rejected = sorted(r["hash"] for r in missing if r["hash"] not in after)
    rep.done(translated=len(missing), installed=copied, results_rows=added, pack=packed,
             cache_entries=len(after), rejected=len(rejected))
    if rejected:
        rep.say("rejected by the translator (their hashes are not ones the game requests):")
        for h in rejected[:10]:
            rep.say("  " + h)
        if len(rejected) > 10:
            rep.say("  ... and %d more" % (len(rejected) - 10))
    if copied == 0:
        rep.fail(EXIT_STEP, "not one shader came out of the translator")
        return EXIT_STEP
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
