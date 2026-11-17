#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""One entry point for a first run of the XC2 NS2 recompilation.

    python xc2_setup.py --repo <checkout> --install <folder> --nup <dump>.nup [--dry-run]

Steps, each skipped when its artifact is already there:
    doctor   tools/bootstrap/doctor.ps1 -Json        what the machine is missing
    sources  nxrecomp tarball (deps.lock.json) + fetch_third_party.ps1
    runtime  the two cmake configures and builds (BUILD.md 4.1)
    lift     xc2/scripts/build.ps1                   the seven modules to .lib
    link     xc2/scripts/build-boot.ps1              the boot exe
    ingest   a .nup, or a folder that already holds the modules
    done     setup_state.tsv, exefs/ and romfs/ under --install

State lives in <install>/setup/status.json (the launcher reads it) and setup/setup.log.
Nothing is written into the dump; the romfs is linked, never copied.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

MODULES = ["main", "sdk", "subsdk0", "subsdk1", "subsdk2", "subsdk3", "rtld"]
STATE_FILE = "status.json"
LOG_FILE = "setup.log"


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Runner:
    def __init__(self, install, dry):
        self.install = install
        self.state_dir = install / "setup"
        self.dry = dry
        self.log_path = self.state_dir / LOG_FILE
        self.status_path = self.state_dir / STATE_FILE
        self.status = {"state": "idle", "step": "", "note": "", "started_at": now(), "steps": []}
        self.live = {"detail": "", "percent": None}
        self.last_write = 0.0
        if not dry:
            self.state_dir.mkdir(parents=True, exist_ok=True)

    def log(self, line):
        stamp = datetime.now().strftime("%H:%M:%S")
        text = "[%s] %s" % (stamp, line)
        print(text, flush=True)
        if not self.dry:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(text + "\n")

    def write_status(self, **kw):
        self.status.update(kw)
        self.status["updated_at"] = now()
        if not self.dry:
            tmp = self.status_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.status, indent=1), encoding="utf-8")
            os.replace(tmp, self.status_path)

    def step(self, name):
        self.live = {"detail": "", "percent": None}
        self.last_write = 0.0
        self.write_status(state="running", step=name, note="", progress=None)
        self.log("@step " + name)
        self.log("STEP: %s" % name)
        return time.time()

    def end_step(self, name, started, ok, note=""):
        seconds = round(time.time() - started, 1)
        row = next((s for s in self.status["steps"] if s["name"] == name), None)
        if row is None:
            row = {"name": name}
            self.status["steps"].append(row)
        row.update(state="done" if ok else "failed", seconds=seconds, note=note)
        self.live = {"detail": "", "percent": None}
        self.write_status(note=note, progress=None)
        self.log("STEP: %s %s %ss %s" % (name, "done" if ok else "FAILED", seconds, note))
        return ok

    def note_progress(self, detail, percent=None):
        """Say what the current step is doing, at most once a second.

        A build step runs for minutes and its completion is the only other signal, so a front end polling
        status.json had nothing to show in between - measured 223.6 s of runtime with the file frozen at
        "runtime". The detail also goes into the step's own note, which is the field the checklist renders.
        """
        self.live = {"detail": detail, "percent": percent}
        t = time.time()
        if t - self.last_write < 1.0:
            return
        self.last_write = t
        row = next((s for s in self.status["steps"] if s["name"] == self.status["step"]), None)
        if row is None:
            # step() does not create the row - end_step() does - so the first progress line has to make it,
            # otherwise the detail has nowhere to go and the checklist still shows a blank step.
            row = {"name": self.status["step"], "state": "running", "seconds": 0, "note": ""}
            self.status["steps"].append(row)
        row["note"] = detail
        self.write_status(progress=dict(self.live))

    def run(self, argv, cwd=None, env=None, on_line=None):
        shown = " ".join(str(a) for a in argv)
        self.log("  $ " + shown)
        if self.dry:
            return 0
        full_env = os.environ.copy()
        if env:
            full_env.update(env)
        with open(self.log_path, "a", encoding="utf-8") as logf:
            logf.write("  $ %s\n" % shown)
            logf.flush()
            # Streamed rather than captured: the log used to appear only when the command exited, so a four
            # minute build looked like a hang to anyone watching setup.log.
            p = subprocess.Popen([str(a) for a in argv], cwd=str(cwd) if cwd else None, env=full_env,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, errors="replace", bufsize=1)
            for line in p.stdout:
                logf.write("    " + line)
                logf.flush()
                if on_line is not None:
                    on_line(line.rstrip("\r\n"))
            return p.wait()


def pwsh(*args):
    return ["pwsh", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", *args]


NINJA_LINE = re.compile(r"^\[(\d+)/(\d+)\]")


def build_progress(r, label):
    """Turn ninja's [done/total] into a percentage, and keep the last other line as the detail.

    cmake drives ninja, so every build step speaks this format; the counter is the only progress a user can
    act on, and without it the status file said "runtime" for four minutes and nothing else.
    """
    def on_line(line):
        s = line.strip()
        m = NINJA_LINE.match(s)
        if m:
            done, total = int(m.group(1)), int(m.group(2))
            r.note_progress("%s %d/%d" % (label, done, total), (done / total) if total else None)
        elif s:
            r.note_progress("%s: %s" % (label, s[:140]))
    return on_line


def import_toolchain(r):
    """Put the toolchain on PATH when XC2_ENV names the script that does it.

    The toolchain lives in a directory that script adds to PATH, so a machine that HAS cmake reports it missing
    unless the script ran first - and the engine then dies on a bare WinError 2 that says nothing useful. This is
    the same failure doctor.ps1 was fixed for; measured 2026-11-17 from a shell that never sourced it.
    """
    script = os.environ.get("XC2_ENV")
    if not script:
        return
    if not Path(script).is_file():
        r.log("  XC2_ENV points at %s, which is not a file; leaving PATH alone" % script)
        return
    try:
        p = subprocess.run(["pwsh", "-NoProfile", "-Command",
                            ". $env:XC2_ENV *> $null; Write-Output $env:PATH"],
                           capture_output=True, text=True, timeout=180)
    except OSError as exc:
        r.log("  could not run pwsh to read XC2_ENV: %s" % exc)
        return
    lines = [ln for ln in (p.stdout or "").splitlines() if ln.strip()]
    if p.returncode != 0 or not lines:
        r.log("  XC2_ENV did not yield a PATH (%s)" % (p.stderr or "").strip()[:200])
        return
    os.environ["PATH"] = lines[-1].strip()
    r.log("  toolchain on PATH, taken from %s" % script)


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def nso_ok(path):
    try:
        with open(path, "rb") as f:
            return f.read(4) == b"NSO0"
    except OSError:
        return False


def have_modules(folder):
    return all((folder / m).is_file() and nso_ok(folder / m) for m in MODULES)


def step_doctor(r, repo):
    started = r.step("doctor")
    rc = r.run(pwsh(repo / "tools" / "bootstrap" / "doctor.ps1", "-Json"))
    return r.end_step("doctor", started, rc == 0, "the machine is ready" if rc == 0 else "missing tools, see the log")


def have_nxrecomp(dest):
    return (dest / "recomp").is_dir() and any(dest.rglob("*.py"))


def fetch_nxrecomp(r, repo, spec, dest):
    cache = repo / "work" / "setup" / spec["url"].rsplit("/", 1)[-1]
    cache.parent.mkdir(parents=True, exist_ok=True)
    if not cache.is_file() or sha256_of(cache) != spec["sha256"]:
        r.log("  downloading %s" % spec["url"])
        if r.dry:
            return 0
        with urllib.request.urlopen(spec["url"], timeout=120) as resp, open(cache, "wb") as f:
            shutil.copyfileobj(resp, f)
        got = sha256_of(cache)
        if got != spec["sha256"]:
            r.log("  sha256 mismatch: %s != %s" % (got, spec["sha256"]))
            return 1
    r.log("  unpacking into %s" % dest)
    if r.dry:
        return 0
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(cache, "r:gz") as tf:
        names = tf.getnames()
        top = names[0].split("/")[0] if names else ""
        strip = 1 if top and all(n == top or n.startswith(top + "/") for n in names) else 0
        for member in tf.getmembers():
            parts = member.name.split("/")[strip:]
            name = "/".join(p for p in parts if p)
            if not name:
                continue
            target = dest / name
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                target.parent.mkdir(parents=True, exist_ok=True)
                with tf.extractfile(member) as src, open(target, "wb") as out:
                    shutil.copyfileobj(src, out)
    return 0


def step_sources(r, repo):
    started = r.step("sources")
    lock = json.loads((repo / "tools" / "bootstrap" / "deps.lock.json").read_text(encoding="utf-8"))
    nx = next((s for s in lock["sources"] if s["name"] == "nxrecomp"), None)
    dest = repo / (nx["dest"] if nx and nx.get("dest") else "third_party/nxrecomp")
    if have_nxrecomp(dest):
        r.log("  nxrecomp already in place")
    elif nx is None:
        return r.end_step("sources", started, False, "deps.lock.json has no nxrecomp entry")
    elif fetch_nxrecomp(r, repo, nx, dest) != 0:
        return r.end_step("sources", started, False, "the recompiler could not be fetched")
    textures = repo / "third_party" / "fefw-recomp" / "tools" / "textures" / "third_party" / "astc-encoder"
    if textures.is_dir():
        r.log("  texture sources already fetched")
    elif r.run(pwsh(repo / "third_party" / "fefw-recomp" / "tools" / "textures" / "scripts" / "fetch_third_party.ps1"), cwd=repo) != 0:
        return r.end_step("sources", started, False, "fetch_third_party.ps1 failed")
    return r.end_step("sources", started, True)


def step_runtime(r, repo):
    started = r.step("runtime")
    runtime = repo / "third_party" / "fefw-recomp" / "runtime"
    gfx = repo / "third_party" / "fefw-recomp" / "build" / "runtime-gfx"
    game = repo / "third_party" / "fefw-recomp" / "build" / "xc2-game-probe"
    cc = ["-DCMAKE_C_COMPILER=clang-cl", "-DCMAKE_CXX_COMPILER=clang-cl"]
    if not (gfx / "build.ninja").is_file():
        if r.run(["cmake", "-S", runtime, "-B", gfx, "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release",
                  "-DNXRT_BUILD_GFX=ON", "-DNXRT_BUILD_GAMES=OFF", "-DNXRT_BUILD_TESTS=OFF", *cc]) != 0:
            return r.end_step("runtime", started, False, "the graphics shell could not be configured")
    if r.run(["cmake", "--build", gfx, "--target", "nxrt", "nxrt_gfx"], on_line=build_progress(r, "runtime")) != 0:
        return r.end_step("runtime", started, False, "nxrt/nxrt_gfx did not build")
    if not (game / "build.ninja").is_file():
        if r.run(["cmake", "-S", runtime, "-B", game, "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release",
                  "-DNXRT_BUILD_GFX=ON", "-DNXRT_BUILD_GAMES=ON", "-DNXRT_GAMES=xc2ns2",
                  "-DNXRT_TEST_GAME=xc2ns2", "-DNXRT_BUILD_TESTS=OFF", *cc]) != 0:
            return r.end_step("runtime", started, False, "the game module could not be configured")
    if r.run(["cmake", "--build", game, "--target", "nxrt_game_xc2ns2_core", "nxrt_game_xc2ns2_data"],
              on_line=build_progress(r, "runtime")) != 0:
        return r.end_step("runtime", started, False, "nxrt_game_xc2ns2_* did not build")
    return r.end_step("runtime", started, True)


def step_lift(r, repo, install, jobs=0):
    started = r.step("lift")
    lib = repo / "xc2" / "build" / "lib-301"
    if all((lib / (m + ".lib")).is_file() for m in MODULES):
        return r.end_step("lift", started, True, "the libraries are already there")
    argv = pwsh(repo / "xc2" / "scripts" / "build.ps1", "-Exefs", install / "exefs", "-Run:$false",
                "-Modules", ",".join(MODULES), "-LiftDir", repo / "xc2" / "build" / "lift-301",
                "-ObjDir", repo / "xc2" / "build" / "obj-301", "-LibDir", lib)
    if jobs > 0:
        # The build script's own default is 10 concurrent clang-cl, which is what it takes to run the largest
        # translation units out of memory on a busy machine: measured 10 failures that each compiled in 2-4 s by
        # hand. A front end that knows the machine can say otherwise.
        r.log("  jobs: %d" % jobs)
        argv += ["-Jobs", str(jobs)]
    rc = r.run(argv, cwd=repo, on_line=build_progress(r, "lift"))
    return r.end_step("lift", started, rc == 0, "" if rc == 0 else "build.ps1 failed (its stub link is expected to fail)")


def step_link(r, repo, install):
    started = r.step("link")
    exe = repo / "xc2" / "build" / "boot-301" / "xc2_boot.exe"
    if exe.is_file():
        return r.end_step("link", started, True, "the boot exe is already there")
    rc = r.run(pwsh(repo / "xc2" / "scripts" / "build-boot.ps1", "-Exefs", install / "exefs",
                    "-OutDir", repo / "xc2" / "build" / "boot-301", "-LibDir", repo / "xc2" / "build" / "lib-301",
                    "-MainLib", repo / "xc2" / "build" / "lib-301" / "main.lib", "-Defines", "XC2_MODULES_7"), cwd=repo,
                on_line=build_progress(r, "link"))
    return r.end_step("link", started, rc == 0, "" if rc == 0 else "build-boot.ps1 failed")


def junction(link, target, r):
    if link.exists() or link.is_symlink():
        return 0
    r.log("  linking %s -> %s" % (link, target))
    if r.dry:
        return 0
    link.parent.mkdir(parents=True, exist_ok=True)
    return subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode


def link_boot_romfs(r, repo, install):
    """Give play-301.cmd the relative romfs path it already looks for.

    That script runs from <repo>/xc2/build/boot and sets NXRT_FS_ROMFS=game/romfs-301 - a path relative to that
    working directory, which is what keeps the tree portable. Nothing created it, so an install finished "ready to
    play" and the first launch died: "fs: RomFS folder 'game/romfs-301' cannot be served" -> svcBreak, exit 4.
    The relative path is the right shape, so the install supplies it rather than the launcher learning a new one.
    """
    romfs = install / "romfs"
    if not romfs.is_dir():
        r.log("  no %s; play-301.cmd will not find a romfs" % romfs)
        return 0
    return junction(repo / "xc2" / "build" / "boot" / "game" / "romfs-301", romfs, r)


def find_romfs(dump, explicit):
    # --romfs wins when it is given. Measured 2026-11-17: a run that passed --romfs looked like it had linked the
    # maintainer tree instead, and had not - Path.resolve() dereferences a junction, and the folder passed in WAS a
    # junction to that one, so the install's link named the real target. Both names reach the same files.
    if explicit:
        return explicit if (explicit / "bf2.ard").is_file() else None
    for candidate in (dump, dump / "romfs", dump.parent, dump.parent / "romfs"):
        if (candidate / "bf2.ard").is_file():
            return candidate
    return None


def step_ingest(r, repo, install, nup, dump, exefs_in, romfs_in):
    started = r.step("ingest")
    exefs = install / "exefs"
    romfs = install / "romfs"
    if have_modules(exefs) and romfs.is_dir():
        return r.end_step("ingest", started, True, "the game files are already installed")
    py = os.environ.get("XC2_PYTHON") or sys.executable
    extract = repo / "tools" / "analysis" / "nup_extract.py"
    if nup:
        if r.run([py, extract, "--nup", nup, "--pkg", "0", "--part", "exefs", "--out", exefs]) != 0:
            return r.end_step("ingest", started, False, "the exefs could not be unpacked (is zstandard installed?)")
        if not (romfs / "bf2.ard").is_file():
            if r.run([py, extract, "--nup", nup, "--pkg", "0", "--part", "romfs", "--out", romfs]) != 0:
                return r.end_step("ingest", started, False, "the romfs could not be unpacked")
    elif exefs_in:
        if not have_modules(exefs_in):
            return r.end_step("ingest", started, False, "no NSO modules in %s" % exefs_in)
        rom = find_romfs(exefs_in, romfs_in)
        if rom is None:
            return r.end_step("ingest", started, False, "no romfs near %s; pass --romfs" % exefs_in)
        if junction(exefs, exefs_in, r) != 0:
            return r.end_step("ingest", started, False, "could not link exefs")
        if junction(romfs, rom, r) != 0:
            return r.end_step("ingest", started, False, "could not link romfs")
    elif dump:
        found = dump if (dump / "main").is_file() else dump / "exefs"
        if not have_modules(found):
            return r.end_step("ingest", started, False, "no NSO modules in %s" % found)
        if junction(exefs, found, r) != 0:
            return r.end_step("ingest", started, False, "could not link exefs")
        rom = find_romfs(dump, romfs_in)
        if rom is None:
            return r.end_step("ingest", started, False,
                              "no romfs found (looked in %s, its romfs/, and its parent); pass --romfs" % dump)
        if junction(romfs, rom, r) != 0:
            return r.end_step("ingest", started, False, "could not link romfs")
    else:
        return r.end_step("ingest", started, False, "give --nup or --dump")
    return r.end_step("ingest", started, True)


def step_done(r, repo, install):
    started = r.step("done")
    link_boot_romfs(r, repo, install)
    if not r.dry:
        (install / "setup_state.tsv").write_text("mprs_setup_state\t1\nmeta\tfinished\t1\n", encoding="utf-8")
    r.write_status(state="done", note="ready to play")
    return r.end_step("done", started, True, "ready to play")


def main():
    ap = argparse.ArgumentParser(description="first run of the XC2 NS2 recompilation")
    ap.add_argument("--repo", required=True)
    ap.add_argument("--install", required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--nup")
    g.add_argument("--dump")
    g.add_argument("--exefs", help="a folder that already holds the modules (romfs given with --romfs)")
    ap.add_argument("--romfs", help="the romfs folder when it is not next to the dump")
    ap.add_argument("--jobs", type=int, default=0,
                    help="parallel compiles for the lift; 0 keeps the build script's own default")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip", default="", help="comma separated steps to skip")
    a = ap.parse_args()

    repo = Path(a.repo).resolve()
    install = Path(a.install).resolve()
    nup = Path(a.nup).resolve() if a.nup else None
    dump = Path(a.dump).resolve() if a.dump else None
    exefs_in = Path(a.exefs).resolve() if a.exefs else None
    romfs_in = Path(a.romfs).resolve() if a.romfs else None
    r = Runner(install, a.dry_run)
    skip = {s.strip() for s in a.skip.split(",") if s.strip()}
    r.log("repo    %s" % repo)
    r.log("install %s" % install)
    r.log("input   %s" % (nup or dump or exefs_in))
    import_toolchain(r)

    steps = [
        ("doctor", lambda: step_doctor(r, repo)),
        ("sources", lambda: step_sources(r, repo)),
        ("runtime", lambda: step_runtime(r, repo)),
        ("ingest", lambda: step_ingest(r, repo, install, nup, dump, exefs_in, romfs_in)),
        ("lift", lambda: step_lift(r, repo, install, a.jobs)),
        ("link", lambda: step_link(r, repo, install)),
        ("done", lambda: step_done(r, repo, install)),
    ]
    for name, fn in steps:
        if name in skip:
            r.end_step(name, time.time(), True, "skipped")
            continue
        if not fn():
            r.write_status(state="error")
            r.log("stopped at %s" % name)
            return 1
    r.write_status(state="done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
