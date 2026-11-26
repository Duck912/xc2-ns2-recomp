#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""One entry point for a first run of the XC2 NS2 recompilation on NVN-HLE (the launcher's engine).

    python xc2_nvnhle_setup.py --repo <checkout> --install <folder> --nup <dump>.nup [--dry-run]
    python xc2_nvnhle_setup.py --repo <checkout> --install <folder> --exefs <dir> --romfs <dir> [--dlc <dir>]

The same steps as tools/setup/xcde_setup.py (XC:DE), with Xenoblade Chronicles 2 - Nintendo Switch 2 Edition's facts:
    doctor      tools/setup/doctor.ps1 -Json          what the machine is missing
    sources     nxrecomp tarball + third-party sources
    nvnhle      the prebuilt NVN-HLE library (n2den_nvnhle_bundle.lib + embed.h) into work/nvnhle-dist
    runtime     the two CMake builds, configured with NXRT_N2DEN_DIST
    ingest      the Switch 2 program's ExeFS and RomFS (one base program: code and data) and the add-ons' RomFS
    lift        the seven modules to .lib with xc2/sites (XC2's main hooks included)
    link        xc2/build/301/boot-n2den/xc2.exe
    streamline  NVIDIA Streamline into the boot folder's user/streamline (the game's DLSS; FSR 1 without it)
    done        launch.env (the start-up switches)

A release package (runtime/xc2_rt.lib + tools/python beside the engine) runs tools, doctor, ingest, lift, link,
streamline and done, building into the run folder. Nothing is written into the dump.
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import xc2_setup as base  # noqa: E402
import xcde_setup as shared  # noqa: E402

# ---- XC2 facts --------------------------------------------------------------------------------------------------------
TITLE = "Xenoblade Chronicles 2 - Nintendo Switch 2 Edition"
PROGRAM_ID = "0400e95004038001"          # the Switch 2 program (program index 1): its ExeFS is the code, its RomFS the data
BUILD = Path("xc2") / "build" / "301"
EXEFS = Path("xc2") / "game" / "xc2ns301"
BOOT = BUILD / "boot-n2den"
EXE = "xc2.exe"
ICON = Path("xc2") / "xc2.ico"

# XC2's start-up switches (xc2_setup.py: the 3.0.1 hooks, title facts, languages) on NVN-HLE. Without XC2_GAME the boot
# program runs XC2 (its default), with XC2's main hooks armed.
#: The prebuilt NVN-HLE library: the same build (and SHA-256) as xcde-ns2-recomp 0.1.0, attached to this repository's
#: own v0.1.0 release. XC2_NVNHLE_DIST (or XCDE_NVNHLE_DIST) still wins for a library built locally.
shared.NVNHLE_URL = "https://github.com/Duck912/xc2-ns2-recomp/releases/download/v0.1.0/n2den-nvnhle-0.1.0-windows-x64.zip"

GAME_ENV = dict(base.GAME_ENV)
GAME_ENV.update({
    "NXRT_NVN_BACKEND": "n2den",
})


def romfs_ok(folder):
    return folder.is_dir() and (folder / "bf2.ard").is_file()


def nup_addons(py, extract, nup):
    """(package index, title id) of every add-on in the .nup, from nup_extract.py --list."""
    out = subprocess.run([str(py), str(extract), "--nup", str(nup), "--list"], capture_output=True, text=True)
    found = []
    for line in out.stdout.splitlines():
        cols = line.split()
        if len(cols) >= 4 and cols[0].isdigit() and cols[1] == "2" and len(cols[2]) == 16:
            found.append((int(cols[0]), cols[2].lower()))
    return found


def addons_in(dlc):
    """The add-on folders (<title id>/romfs) under a dlc folder."""
    if not dlc or not dlc.is_dir():
        return []
    return sorted(p.name.lower() for p in dlc.iterdir() if (p / "romfs").is_dir())


def step_ingest(r, repo, install, nup, exefs_in, romfs_in, dlc_in, package=False):
    """ExeFS into the checkout (xc2/game/xc2ns301, small; the lift reads it) or the run folder (package); RomFS and
    add-ons under --install, linked where config/profiles/xc2nh.ini looks (xc2/build/301/game/romfs and .../dlc)."""
    started = r.step("ingest")
    exefs = install / "exefs" if package else repo / EXEFS
    romfs = install / "romfs"
    dlc = install / "dlc"
    py = os.environ.get("XC2_PYTHON") or sys.executable
    extract = repo / "tools" / "analysis" / "nup_extract.py"
    if nup:
        # Package 0: the Switch 2 program, code (ExeFS) and the full game data (RomFS, bf2.ard ...). Kind-2 packages: the
        # add-ons, each to dlc/<title id>/romfs, where the runtime serves them ([aoc] dir).
        if not base.have_modules(exefs) and r.run([py, extract, "--nup", nup, "--pkg", "0", "--part", "exefs",
                                                    "--out", exefs]) != 0:
            return r.end_step("ingest", started, False, "the ExeFS could not be unpacked (is zstandard installed?)")
        if not romfs_ok(romfs) and r.run([py, extract, "--nup", nup, "--pkg", "0", "--part", "romfs",
                                          "--out", romfs]) != 0:
            return r.end_step("ingest", started, False, "the game data (the RomFS) could not be unpacked")
        for pkg, tid in ([] if r.dry else nup_addons(py, extract, nup)):
            dest = dlc / tid / "romfs"
            if dest.is_dir() and any(dest.iterdir()):
                continue
            if r.run([py, extract, "--nup", nup, "--pkg", str(pkg), "--part", "romfs", "--out", dest]) != 0:
                return r.end_step("ingest", started, False, "the add-on %s could not be unpacked" % tid.upper())
    else:
        if not base.have_modules(exefs_in):
            return r.end_step("ingest", started, False, "no NSO modules in %s" % exefs_in)
        if not base.have_modules(exefs):
            r.log("  copying the ExeFS from %s" % exefs_in)
            if not r.dry:
                shutil.copytree(exefs_in, exefs, dirs_exist_ok=True)
        if not romfs_in or not romfs_ok(romfs_in):
            return r.end_step("ingest", started, False, "--romfs must name the game's RomFS (it holds bf2.ard)")
        if not shared.link_or_use(r, romfs, romfs_in, "the game data"):
            romfs = shared.DATA_PATHS["romfs"] = romfs_in
        if dlc_in:
            if not addons_in(dlc_in):
                r.log("  dlc: no add-ons (<title id>/romfs) in %s; the game runs without add-on content" % dlc_in)
            elif not shared.link_or_use(r, dlc, dlc_in, "the add-ons"):
                dlc = shared.DATA_PATHS["dlc"] = dlc_in
    if not r.dry:
        if not base.have_modules(exefs):
            return r.end_step("ingest", started, False, "the ExeFS lacks a module (main, sdk, subsdk0-3, rtld)")
        if not romfs_ok(romfs):
            return r.end_step("ingest", started, False, "the RomFS is not XC2's game data")
        got = addons_in(dlc)
        r.log("  add-ons: %s" % (", ".join(t.upper() for t in got) if got else "none (the game runs without them)"))
    if package:
        return r.end_step("ingest", started, True)
    game = repo / BUILD / "game"
    if base.junction(game / "romfs", romfs, r) != 0:
        return r.end_step("ingest", started, False, "could not link the game data into xc2/build/301/game")
    if dlc.is_dir() and base.junction(game / "dlc", dlc, r) != 0:
        return r.end_step("ingest", started, False, "could not link the add-ons into xc2/build/301/game")
    return r.end_step("ingest", started, True)


def step_lift(r, repo, jobs=0):
    started = r.step("lift")
    lib = repo / BUILD / "lib"
    if all((lib / ("%s.lib" % m)).is_file() for m in base.MODULES):
        return r.end_step("lift", started, True, "the lifted modules are already built")
    argv = base.pwsh(repo / "tools" / "build" / "build.ps1", "-Exefs", repo / EXEFS, "-Run:$false",
                     "-Modules", ",".join(base.MODULES), "-SitesDir", repo / "xc2" / "sites",
                     "-LiftDir", repo / BUILD / "lift", "-ObjDir", repo / BUILD / "obj", "-LibDir", lib)
    if jobs:
        argv += ["-Jobs", str(jobs)]
    rc = r.run(argv, cwd=repo, on_line=base.build_progress(r, "lift"))
    ok = all((lib / ("%s.lib" % m)).is_file() for m in base.MODULES)
    return r.end_step("lift", started, ok, "" if ok else "build.ps1 did not produce every module's .lib (rc %d)" % rc)


def step_link(r, repo):
    started = r.step("link")
    rc = r.run(base.pwsh(repo / "tools" / "build" / "build-boot.ps1", "-Exefs", repo / EXEFS,
                         "-OutDir", repo / BOOT, "-LibDir", repo / BUILD / "lib",
                         "-MainLib", repo / BUILD / "lib" / "main.lib", "-Defines", "XC2_MODULES_7",
                         "-ExeName", EXE, "-IconFile", repo / ICON,
                         "-N2denDist", shared.nvnhle_dist(repo)), cwd=repo, on_line=base.build_progress(r, "link"))
    ok = (repo / BOOT / EXE).is_file()
    return r.end_step("link", started, rc == 0 and ok, "" if rc == 0 and ok else "build-boot.ps1 failed")


def step_done(r, repo, install):
    return shared.step_done(r, repo, install, env=GAME_ENV, game="XC2", engine="xc2_nvnhle_setup.py")


def main():
    if "--emit-env" in sys.argv[1:]:
        for key in sorted(GAME_ENV):
            print("%s=%s" % (key, GAME_ENV[key]))
        return 0
    ap = argparse.ArgumentParser(description="first run of the XC2 NS2 recompilation on NVN-HLE")
    ap.add_argument("--repo", required=True)
    ap.add_argument("--install", required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--nup", help="the dump as one .nup")
    g.add_argument("--exefs", help="a folder with the Switch 2 program's modules (then --romfs, and --dlc)")
    ap.add_argument("--romfs", help="the game's RomFS (holds bf2.ard)")
    ap.add_argument("--dlc", help="a folder of add-ons, each <title id>/romfs")
    ap.add_argument("--jobs", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-streamline", action="store_true", help="do not download NVIDIA Streamline (DLSS)")
    ap.add_argument("--skip", default="", help="comma separated steps to skip")
    a = ap.parse_args()

    repo = Path(a.repo).resolve()
    install = Path(a.install).resolve()
    nup = Path(a.nup).resolve() if a.nup else None
    exefs_in = Path(a.exefs).resolve() if a.exefs else None
    romfs_in = Path(a.romfs).resolve() if a.romfs else None
    # The launcher hands its unpacked dlc/ folder over as XC2_AOC_DIR.
    dlc_in = Path(a.dlc).resolve() if a.dlc else (Path(os.environ["XC2_AOC_DIR"]) if os.environ.get("XC2_AOC_DIR")
                                                 else None)
    r = base.Runner(install, a.dry_run)
    skip = {s.strip() for s in a.skip.split(",") if s.strip()}
    r.log("game    %s" % TITLE)
    r.log("repo    %s" % repo)
    r.log("install %s" % install)
    r.log("input   %s" % (nup or exefs_in))
    pkg_py = repo / "tools" / "python" / "python.exe"
    pkg_lib = repo / "runtime" / "xc2_rt.lib"
    if pkg_py.is_file() and pkg_lib.is_file():
        # A release package: runtime/xc2_rt.dll with NVN-HLE in it and the bundled Python; Zig comes with step tools.
        tools = (pkg_py, shared.package_zig(repo), pkg_lib)
        py, zig, rtlib = tools
        r.log("mode    package: the runtime, Python and the compiler travel with it")
        steps = [
            ("tools", lambda: shared.step_tools(r, repo)),
            ("doctor", lambda: base.step_doctor_package(r, repo, tools)),
            ("ingest", lambda: step_ingest(r, repo, install, nup, exefs_in, romfs_in, dlc_in, package=True)),
            ("lift", lambda: base.step_lift_package(r, repo, install, py, a.jobs, sites=repo / "xc2" / "sites")),
            ("link", lambda: base.step_link_package(r, repo, install, zig, rtlib, a.jobs, exe_name=EXE,
                                                       icon=repo / ICON)),
            ("streamline", lambda: shared.step_streamline(r, repo, install, package=True, fetch=not a.no_streamline)),
            ("done", lambda: step_done(r, repo, install)),
        ]
        return shared.run_steps(r, steps, skip)
    base.import_toolchain(r)
    steps = [
        ("doctor", lambda: base.step_doctor(r, repo)),
        ("sources", lambda: base.step_sources(r, repo)),
        ("nvnhle", lambda: shared.step_nvnhle(r, repo)),
        ("runtime", lambda: shared.step_runtime(r, repo)),
        ("ingest", lambda: step_ingest(r, repo, install, nup, exefs_in, romfs_in, dlc_in)),
        ("lift", lambda: step_lift(r, repo, a.jobs)),
        ("link", lambda: step_link(r, repo)),
        ("streamline", lambda: shared.step_streamline(r, repo, install, fetch=not a.no_streamline, boot=BOOT)),
        ("done", lambda: step_done(r, repo, install)),
    ]
    return shared.run_steps(r, steps, skip)


if __name__ == "__main__":
    sys.exit(main())
