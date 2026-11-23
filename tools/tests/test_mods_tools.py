#!/usr/bin/env python3
"""Unit tests for pure-Python mod tooling under tools/mods/ (no game dump required)."""
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "mods"))

import ard_pack  # noqa: E402
import asset_index  # noqa: E402
import mod_check  # noqa: E402


class ArdPackTests(unittest.TestCase):
    def test_build_xbc1_header_layout(self):
        hdr = ard_pack.build_xbc1_header("common/font_binary2.txt", 1024, 512, 0x12345678)
        self.assertEqual(len(hdr), ard_pack.HDR)
        magic, ver, unc, comp, checksum, raw_name = struct.unpack("<4sIIII28s", hdr)
        self.assertEqual(magic, b"xbc1")
        self.assertEqual(ver, 1)
        self.assertEqual(unc, 1024)
        self.assertEqual(comp, 512)
        self.assertEqual(checksum, 0x12345678)
        self.assertEqual(raw_name.split(b"\x00", 1)[0], b"common/font_binary2.txt")

    def test_build_xbc1_header_truncates_long_name_preserving_nul(self):
        hdr = ard_pack.build_xbc1_header("a" * 50, 10, 8, 1)
        self.assertEqual(len(hdr), ard_pack.HDR)
        self.assertEqual(hdr[-1], 0)
        self.assertEqual(hdr[20:].rstrip(b"\x00"), b"a" * 27)

    def test_patch_index_arh1_structured_and_invalid_rejected(self):
        # Construct minimal arh1 header: magic "arh1", then ent_off/ent_count at +0x1C.
        ent_off = 0x30
        arh = bytearray(ent_off + 2 * 24)
        arh[0:4] = b"arh1"
        struct.pack_into("<II", arh, 0x1C, ent_off, 2)
        struct.pack_into("<QII", arh, ent_off, 0x1000, 100, 200)
        struct.pack_into("<QII", arh, ent_off + 24, 0x2000, 300, 150)  # malformed comp > unc

        patched = ard_pack.patch_index(bytes(arh), 0x1000, 0x90000, 120, 400)
        self.assertIsNotNone(patched)
        blob, pos = patched
        self.assertEqual(pos, ent_off)
        self.assertEqual(struct.unpack_from("<QII", blob, ent_off), (0x90000, 120, 400))

        # Entry outside comp <= unc guard or unknown offset returns None
        self.assertIsNone(ard_pack.patch_index(bytes(arh), 0x2000, 0x90000, 120, 400))
        self.assertIsNone(ard_pack.patch_index(bytes(arh), 0x3000, 0x90000, 120, 400))

    def test_main_inline_m2_and_append_m2b_and_multipart_guard(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            mod_dir = tmp / "my_mod"
            romfs = mod_dir / "romfs"
            (romfs / "common").mkdir(parents=True)
            small_payload = b"hello mod world " * 4
            big_payload = bytes((i * 37) & 0xFF for i in range(4096))
            (romfs / "common" / "small.txt").write_bytes(small_payload)
            (romfs / "common" / "big.bin").write_bytes(big_payload)

            cat = tmp / "assets.tsv"
            cat.write_text(
                "source\tpath\tkind\tsize\tunc\tcomp\toffset\tchecksum\tsha256\n"
                "loose\tcommon/ignored.txt\ttext\t10\t\t\t\t\t\n"
                "ard\t//common/small.txt\ttext\t\t64\t128\t4096\t99\t\n"
                "ard\t//common/big.bin\tbinary\t\t4096\t100\t8192\t77\t\n",
                encoding="utf-8",
            )

            arh = bytearray(0x30 + 2 * 24)
            arh[0:4] = b"arh1"
            struct.pack_into("<II", arh, 0x1C, 0x30, 2)
            struct.pack_into("<QII", arh, 0x30, 4096, 128, 64)
            struct.pack_into("<QII", arh, 0x30 + 24, 8192, 100, 4096)
            arh_path = tmp / "bf2.arh"
            arh_path.write_bytes(bytes(arh))

            fake_script = tmp / "tools" / "mods" / "ard_pack.py"
            fake_script.parent.mkdir(parents=True)
            fake_script.write_text("", encoding="utf-8")

            with mock.patch.object(ard_pack, "__file__", str(fake_script)):
                rc = ard_pack.main([
                    "--mod", str(mod_dir),
                    "--catalog", str(cat),
                    "--arh", str(arh_path),
                    "--ard-size", "1000000",
                ])
            self.assertEqual(rc, 0)

            rec = mod_dir / ".ard" / "common" / "small.txt.rec"
            self.assertTrue(rec.is_file())
            self.assertEqual(len(rec.read_bytes()), ard_pack.HDR + 128)

            append_bin = mod_dir / ".ard" / "append.bin"
            patched_arh = mod_dir / "romfs" / "bf2.arh"
            self.assertTrue(append_bin.is_file())
            self.assertTrue(patched_arh.is_file())
            new_off, new_comp, new_unc = struct.unpack_from("<QII", patched_arh.read_bytes(), 0x30 + 24)
            self.assertEqual(new_off, 1000000)
            self.assertEqual(new_unc, len(big_payload))
            self.assertGreater(new_comp, 100)

            rep = json.loads((tmp / "work" / "mods" / "ard-pack.json").read_text(encoding="utf-8"))
            statuses = {r["file"]: r["status"] for r in rep["report"]}
            self.assertEqual(statuses["common/small.txt"], "packed")
            self.assertEqual(statuses["common/big.bin"], "appended")

    def test_load_catalog_keeps_duplicates_and_main_rejects_multipart(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            mod_dir = tmp / "mod" / "romfs"
            mod_dir.mkdir(parents=True)
            (mod_dir / "tex.bin").write_bytes(b"abc")
            cat = tmp / "assets.tsv"
            cat.write_text(
                "source\tpath\tkind\tsize\tunc\tcomp\toffset\tchecksum\tsha256\n"
                "ard\t//tex.bin\ttexture\t\t100\t50\t1000\t1\t\n"
                "ard\t//tex.bin\ttexture\t\t200\t80\t2000\t2\t\n",
                encoding="utf-8",
            )
            fake_script = tmp / "tools" / "mods" / "ard_pack.py"
            fake_script.parent.mkdir(parents=True)
            fake_script.write_text("", encoding="utf-8")
            with mock.patch.object(ard_pack, "__file__", str(fake_script)):
                rc = ard_pack.main(["--mod", str(tmp / "mod"), "--catalog", str(cat)])
            self.assertEqual(rc, 1)


class ModCheckAndIndexTests(unittest.TestCase):
    def test_norm_and_mod_root(self):
        self.assertEqual(mod_check.norm("//Ma61a\\Cache/Texture/RK050"), "ma61a/cache/texture/rk050")
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            ams = tmp / "atmosphere" / "contents" / "0100E95004038000" / "romfs"
            ams.mkdir(parents=True)
            self.assertEqual(mod_check.mod_root(tmp, "0100E95004038000"), ams)

    def test_classify_all_statuses(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            same_f = tmp / "same.txt"
            same_f.write_bytes(b"identical")
            diff_f = tmp / "diff.txt"
            diff_f.write_bytes(b"modified!")
            ard_f = tmp / "ard.bin"
            ard_f.write_bytes(b"xyz")
            abs_f = tmp / "missing.txt"
            abs_f.write_bytes(b"123")

            cat_path = tmp / "assets.tsv"
            same_hash = mod_check.sha256_of(same_f)
            cat_path.write_text(
                "source\tpath\tkind\tsize\tunc\tcomp\toffset\tchecksum\tsha256\n"
                f"loose\tsame.txt\ttext\t9\t\t\t\t\t{same_hash}\n"
                "loose\tdiff.txt\ttext\t9\t\t\t\t\tdeadbeef\n"
                "ard\t//ard.bin\tbinary\t\t3\t2\t4096\t1\t\n",
                encoding="utf-8",
            )
            cat = mod_check.load_catalog(cat_path)
            self.assertEqual(mod_check.classify(same_f, "same.txt", cat)["status"], "same")
            self.assertEqual(mod_check.classify(diff_f, "diff.txt", cat)["status"], "differs")
            self.assertEqual(mod_check.classify(ard_f, "ard.bin", cat)["status"], "only-archive")
            self.assertEqual(mod_check.classify(abs_f, "missing.txt", cat)["status"], "absent")

    def test_asset_index_kind_of(self):
        self.assertEqual(asset_index.kind_of("//ma61a/cache/texture/RK050"), "texture")
        self.assertEqual(asset_index.kind_of("common/bdat/menu.bdat"), "table")
        self.assertEqual(asset_index.kind_of("sound/bgm/title.wem"), "audio")


if __name__ == "__main__":
    unittest.main()
