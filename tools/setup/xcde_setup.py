#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""One entry point for a first run of the XC:DE NS2 recompilation, on n2den's NVN-HLE renderer.

    python xcde_setup.py --repo <checkout> --install <folder> --nup <dump>.nup [--dry-run]
    python xcde_setup.py --repo <checkout> --install <folder> --exefs <dir> --romfs <dir> [--dlc <dir>]

Steps, each skipped when its result is already there (docs/RELEASE-PLAN.md):
    doctor      tools/setup/doctor.ps1 -Json          what the machine is missing
    sources     nxrecomp tarball + third-party sources (as for XC2)
    nvnhle      the prebuilt NVN-HLE library (n2den_nvnhle_bundle.lib + embed.h) into work/nvnhle-dist
    runtime     the two CMake builds, configured with NXRT_N2DEN_DIST
    ingest      the Switch 2 program's ExeFS, program 0's RomFS (the game data) and the add-on's RomFS
    lift        the seven modules to .lib with xcde/sites
    link        xcde/build/200/boot-n2den/xcde.exe
    streamline  NVIDIA Streamline into the boot folder's user/streamline (the game's DLSS; FSR 1 without it)
    done        launch.env (the start-up switches) and the run profile's game links

This engine reuses xc2_setup.py's runner, status file (<install>/setup/status.json, read by the launcher) and the
doctor/sources steps. Nothing is written into the dump.
"""
import argparse
import hashlib
import os
import shutil
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import xc2_setup as base  # noqa: E402

# ---- XC:DE facts (docs/TARGET.md) -----------------------------------------------------------------------------------
TITLE = "Xenoblade Chronicles: Definitive Edition - Nintendo Switch 2 Edition"
ADDON_ID = "0100ff500e34b001"            # the add-on (upgrade pack): dlcver.bin "2.0.0", 20 GiB of data
BUILD = Path("xcde") / "build" / "200"
EXEFS = Path("xcde") / "game" / "xcde200"
BOOT = BUILD / "boot-n2den"
EXE = "xcde.exe"

# The prebuilt NVN-HLE library this checkout links against (docs/RELEASE-PLAN.md). XCDE_NVNHLE_DIST (a folder with
# lib/n2den_nvnhle_bundle.lib and include/nvnhle/embed.h) wins over the download, for a library built locally.
NVNHLE_VERSION = ""                     # set with the first release of the library
NVNHLE_URL = ""                         # its zip on that release
NVNHLE_SHA256 = ""

# The start-up switches: XC2's (the sdk modules are byte-identical, so its sdk hooks apply) with XC:DE's own title
# facts. config/profiles/xcde.ini repeats the two that differ for a checkout run.
GAME_ENV = dict(base.GAME_ENV)
GAME_ENV.update({
    # main compares nn::oe::GetDisplayVersion with the add-on's dlcver.bin ("2.0.0") and otherwise stops with error
    # 2162-0102 (nn::err::ShowUnacceptableAddOnContentForUpgradeVersionError).
    "NXRT_TITLE_DISPLAY_VERSION": "2.0.0",
    "NXRT_TITLE_SUPPORTED_LANGUAGES": "AmericanEnglish,BritishEnglish,Japanese,French,German,LatinAmericanSpanish,"
                                      "Spanish,Italian,CanadianFrench,Korean,TraditionalChinese,SimplifiedChinese,"
                                      "Chinese,Taiwanese",
    "NXRT_NVN_BACKEND": "n2den",
    "XC2_GAME": "xcde",
})


def romfs_ok(folder):
    return folder.is_dir() and (folder / "bdat").is_dir() and (folder / "menu").is_dir()


def nvnhle_dist(repo):
    env = os.environ.get("XCDE_NVNHLE_DIST", "")
    return Path(env) if env else repo / "work" / "nvnhle-dist"


def nvnhle_ok(dist):
    return (dist / "lib" / "n2den_nvnhle_bundle.lib").is_file() and (dist / "include" / "nvnhle" / "embed.h").is_file()


def step_nvnhle(r, repo):
    started = r.step("nvnhle")
    dist = nvnhle_dist(repo)
    if nvnhle_ok(dist):
        return r.end_step("nvnhle", started, True, "NVN-HLE library in %s" % dist)
    if not NVNHLE_URL:
        return r.end_step("nvnhle", started, False,
                          "no NVN-HLE library release is pinned yet: build it (n2den, target n2den_nvnhle) and set "
                          "XCDE_NVNHLE_DIST to its distribution folder")
    if r.dry:
        return r.end_step("nvnhle", started, True, "would download %s" % NVNHLE_URL)
    work = dist.parent / ".nvnhle-download"
    work.mkdir(parents=True, exist_ok=True)
    zpath = work / "nvnhle.zip"
    r.log("  downloading NVN-HLE %s" % NVNHLE_VERSION)
    try:
        urllib.request.urlretrieve(NVNHLE_URL, zpath)
    except OSError as e:
        return r.end_step("nvnhle", started, False, "the download failed: %s" % e)
    digest = hashlib.sha256(zpath.read_bytes()).hexdigest()
    if digest != NVNHLE_SHA256:
        return r.end_step("nvnhle", started, False, "the download does not match its SHA-256 (%s)" % digest)
    shutil.unpack_archive(str(zpath), str(dist))
    shutil.rmtree(work, ignore_errors=True)
    ok = nvnhle_ok(dist)
    return r.end_step("nvnhle", started, ok, "" if ok else "the zip does not hold lib/ and include/nvnhle/")


def step_runtime(r, repo):
    started = r.step("runtime")
    dist = nvnhle_dist(repo).as_posix()
    runtime = repo / "third_party" / "fefw-recomp" / "runtime"
    gfx = repo / "third_party" / "fefw-recomp" / "build" / "runtime-gfx"
    game = repo / "third_party" / "fefw-recomp" / "build" / "xc2-game-probe"
    cc = ["-DCMAKE_C_COMPILER=clang-cl", "-DCMAKE_CXX_COMPILER=clang-cl", "-DNXRT_N2DEN_DIST=" + dist]
    # Configured every time (cheap when nothing changed): a build folder configured before NVN-HLE existed must pick
    # NXRT_N2DEN_DIST up, or the boot exe links without it.
    if r.run(["cmake", "-S", runtime, "-B", gfx, "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release",
              "-DNXRT_BUILD_GFX=ON", "-DNXRT_BUILD_GAMES=OFF", "-DNXRT_BUILD_TESTS=OFF", *cc]) != 0:
        return r.end_step("runtime", started, False, "the runtime could not be configured")
    if r.run(["cmake", "--build", gfx, "--target", "nxrt", "nxrt_gfx"], on_line=base.build_progress(r, "runtime")) != 0:
        return r.end_step("runtime", started, False, "nxrt/nxrt_gfx did not build")
    if r.run(["cmake", "-S", runtime, "-B", game, "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release",
              "-DNXRT_BUILD_GFX=ON", "-DNXRT_BUILD_GAMES=ON", "-DNXRT_GAMES=xc2ns2",
              "-DNXRT_TEST_GAME=xc2ns2", "-DNXRT_BUILD_TESTS=OFF", *cc]) != 0:
        return r.end_step("runtime", started, False, "the game module could not be configured")
    if r.run(["cmake", "--build", game, "--target", "nxrt_game_xc2ns2_core", "nxrt_game_xc2ns2_data", "nxrt",
              "nxrt_gfx"], on_line=base.build_progress(r, "runtime")) != 0:
        return r.end_step("runtime", started, False, "the game module did not build")
    return r.end_step("runtime", started, True)


def step_ingest(r, repo, install, nup, exefs_in, romfs_in, dlc_in):
    """ExeFS into the checkout (xcde/game/xcde200: small, the lift reads it); RomFS and add-on under --install, linked
    where config/profiles/xcde.ini looks (xcde/build/200/game/romfs and .../dlc)."""
    started = r.step("ingest")
    exefs = repo / EXEFS
    romfs = install / "romfs"
    dlc = install / "dlc" / ADDON_ID / "romfs"
    py = os.environ.get("XC2_PYTHON") or sys.executable
    extract = repo / "tools" / "analysis" / "nup_extract.py"
    if nup:
        # Package 0: the Switch 2 program (its ExeFS is what is recompiled; its RomFS is a 5-byte dummy). Package 1:
        # program index 0, whose RomFS is the game data. Package 2: the add-on.
        if not base.have_modules(exefs) and r.run([py, extract, "--nup", nup, "--pkg", "0", "--part", "exefs",
                                                    "--out", exefs]) != 0:
            return r.end_step("ingest", started, False, "the ExeFS could not be unpacked (is zstandard installed?)")
        if not romfs_ok(romfs) and r.run([py, extract, "--nup", nup, "--pkg", "1", "--part", "romfs",
                                          "--out", romfs]) != 0:
            return r.end_step("ingest", started, False, "the game data (program 0's RomFS) could not be unpacked")
        if not (dlc / "dlcver.bin").is_file() and r.run([py, extract, "--nup", nup, "--pkg", "2", "--part", "romfs",
                                                         "--out", dlc]) != 0:
            return r.end_step("ingest", started, False, "the add-on's RomFS could not be unpacked")
    else:
        if not base.have_modules(exefs_in):
            return r.end_step("ingest", started, False, "no NSO modules in %s" % exefs_in)
        if not base.have_modules(exefs):
            r.log("  copying the ExeFS from %s" % exefs_in)
            if not r.dry:
                shutil.copytree(exefs_in, exefs, dirs_exist_ok=True)
        if not romfs_in or not romfs_ok(romfs_in):
            return r.end_step("ingest", started, False, "--romfs must name program 0's RomFS (bdat/, menu/ ...)")
        if base.junction(romfs, romfs_in, r) != 0:
            return r.end_step("ingest", started, False, "could not link the RomFS")
        if dlc_in:
            if not (Path(dlc_in) / "dlcver.bin").is_file():
                return r.end_step("ingest", started, False, "--dlc must name the add-on's RomFS (it holds dlcver.bin)")
            if base.junction(dlc, Path(dlc_in), r) != 0:
                return r.end_step("ingest", started, False, "could not link the add-on")
    if not r.dry:
        if not base.have_modules(exefs):
            return r.end_step("ingest", started, False, "the ExeFS lacks a module (main, sdk, subsdk0-3, rtld)")
        if not romfs_ok(romfs):
            return r.end_step("ingest", started, False, "the RomFS is not XC:DE's game data")
        if not (dlc / "dlcver.bin").is_file():
            return r.end_step("ingest", started, False,
                              "the add-on (%s) is missing: the Switch 2 Edition needs it to start" % ADDON_ID.upper())
    game = repo / BUILD / "game"
    if base.junction(game / "romfs", romfs, r) != 0 or base.junction(game / "dlc", install / "dlc", r) != 0:
        return r.end_step("ingest", started, False, "could not link the game data into xcde/build/200/game")
    return r.end_step("ingest", started, True)


def step_lift(r, repo, jobs=0):
    started = r.step("lift")
    lib = repo / BUILD / "lib"
    if all((lib / ("%s.lib" % m)).is_file() for m in base.MODULES):
        return r.end_step("lift", started, True, "the lifted modules are already built")
    argv = base.pwsh(repo / "tools" / "build" / "build.ps1", "-Exefs", repo / EXEFS, "-Run:$false",
                     "-Modules", ",".join(base.MODULES), "-SitesDir", repo / "xcde" / "sites",
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
                         "-ExeName", EXE, "-N2denDist", nvnhle_dist(repo)), cwd=repo, on_line=base.build_progress(r, "link"))
    ok = (repo / BOOT / EXE).is_file()
    return r.end_step("link", started, rc == 0 and ok, "" if rc == 0 and ok else "build-boot.ps1 failed")


def step_streamline(r, repo, install):
    """NVN-HLE loads Streamline from <boot>/user/streamline. The launcher downloads NVIDIA's release (verified) into
    <install>/upscalers/streamline; this copies it. Missing is not an error: the game then upscales with FSR 1."""
    started = r.step("streamline")
    dest = repo / BOOT / "user" / "streamline"
    if (dest / "sl.interposer.dll").is_file():
        return r.end_step("streamline", started, True, "already in place")
    for src in (install / "upscalers" / "streamline", Path(os.environ.get("XCDE_STREAMLINE_DIR", "") or "-")):
        if (src / "sl.interposer.dll").is_file():
            r.log("  copying Streamline from %s" % src)
            if not r.dry:
                shutil.copytree(src, dest, dirs_exist_ok=True)
            return r.end_step("streamline", started, True)
    return r.end_step("streamline", started, True,
                      "not downloaded: DLSS falls back to FSR 1 (the launcher's Settings download Streamline)")


def step_done(r, repo, install):
    started = r.step("done")
    if not r.dry:
        path = install / "launch.env"
        text = ("# The start-up switches of XC:DE on NVN-HLE. Written by tools/setup/xcde_setup.py from GAME_ENV on every\n"
                "# setup and read by the launcher (Play).\n")
        for k in sorted(GAME_ENV):
            text += "%s=%s\n" % (k, GAME_ENV[k])
        path.write_text(text, encoding="utf-8", newline="\n")
        (install / "setup_state.tsv").write_text("mprs_setup_state\t1\nmeta\tfinished\t1\n", encoding="utf-8")
    r.write_status(state="done", note="ready to play")
    return r.end_step("done", started, True, "ready to play")


def main():
    if "--emit-env" in sys.argv[1:]:
        for key in sorted(GAME_ENV):
            print("%s=%s" % (key, GAME_ENV[key]))
        return 0
    ap = argparse.ArgumentParser(description="first run of the XC:DE NS2 recompilation")
    ap.add_argument("--repo", required=True)
    ap.add_argument("--install", required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--nup", help="the dump as one .nup")
    g.add_argument("--exefs", help="a folder with the Switch 2 program's modules (then --romfs, and --dlc)")
    ap.add_argument("--romfs", help="program 0's RomFS (the game data)")
    ap.add_argument("--dlc", help="the add-on's RomFS (holds dlcver.bin)")
    ap.add_argument("--jobs", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip", default="", help="comma separated steps to skip")
    a = ap.parse_args()

    repo = Path(a.repo).resolve()
    install = Path(a.install).resolve()
    nup = Path(a.nup).resolve() if a.nup else None
    exefs_in = Path(a.exefs).resolve() if a.exefs else None
    romfs_in = Path(a.romfs).resolve() if a.romfs else None
    dlc_in = Path(a.dlc).resolve() if a.dlc else (Path(os.environ["XC2_AOC_DIR"]) / ADDON_ID / "romfs"
                                                 if os.environ.get("XC2_AOC_DIR") else None)
    r = base.Runner(install, a.dry_run)
    skip = {s.strip() for s in a.skip.split(",") if s.strip()}
    r.log("game    %s" % TITLE)
    r.log("repo    %s" % repo)
    r.log("install %s" % install)
    r.log("input   %s" % (nup or exefs_in))
    base.import_toolchain(r)
    steps = [
        ("doctor", lambda: base.step_doctor(r, repo)),
        ("sources", lambda: base.step_sources(r, repo)),
        ("nvnhle", lambda: step_nvnhle(r, repo)),
        ("runtime", lambda: step_runtime(r, repo)),
        ("ingest", lambda: step_ingest(r, repo, install, nup, exefs_in, romfs_in, dlc_in)),
        ("lift", lambda: step_lift(r, repo, a.jobs)),
        ("link", lambda: step_link(r, repo)),
        ("streamline", lambda: step_streamline(r, repo, install)),
        ("done", lambda: step_done(r, repo, install)),
    ]
    r.total_steps = len(steps)
    r.announce()
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
