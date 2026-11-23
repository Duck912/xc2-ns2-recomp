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
import arh_index  # noqa: E402
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

    def test_arh1_full_path_decode_resolves_diff_unc_and_raw_entries(self):
        # Build a synthetic arh1 with trie + XOR'd strings mirroring bf2.arh:
        #   0: /bdat/cn/msg.bdat  (flags=2 compressed, a>0 tail)
        #   1: /bdat/gb/msg.bdat  (flags=2 compressed, a>0 tail)
        #   2: /bdat/cn/raw.bdat  (flags=0 uncompressed, unc=0)
        #   3: /event/a.motstm    (flags=2 compressed, edge==0 & a<0 in-trie NUL leaf)
        entries = [
            (b"/bdat/cn/msg.bdat", 0x1000, 30, 50, 2, 0),
            (b"/bdat/gb/msg.bdat", 0x2000, 40, 80, 2, 1),
            (b"/bdat/cn/raw.bdat", 0x3000, 64, 0, 0, 2),
            (b"/event/a.motstm", 0x4000, 50, 90, 2, 3),
        ]
        # Construct deterministic XOR radix trie:
        # Allocate node indices sequentially using unique xor keys per branch (pa = -(next_base + 1)).
        # Node 0 is root. For node parent with branch offset `base`, child = base ^ ch, parent.a = -(base + 1), child.b = -(parent + 1).
        nodes = {0: [0, 0]}
        next_free = 256
        str_buf = bytearray(4)

        def insert_in_trie(path_bytes, entry_idx, tail_bytes=None):
            nonlocal next_free
            # For entries with tail_bytes != None, walk prefix bytes then place leaf at final char node with a = str_off - 1.
            # For tail_bytes is None, walk all path_bytes then add NUL (0x00) edge leaf with a = -(entry_idx + 1).
            walk = path_bytes if tail_bytes is None else path_bytes[:-len(tail_bytes)]
            cur = 0
            for ch in walk:
                pa, pb = nodes[cur]
                if pa == 0:
                    # Pick base that gives unused child indices for likely ASCII/NUL bytes
                    base = next_free
                    next_free += 256
                    nodes[cur][0] = -(base + 1)
                else:
                    base = -pa - 1
                nxt = base ^ ch
                if nxt not in nodes:
                    nodes[nxt] = [0, -(cur + 1)]
                cur = nxt
            if tail_bytes is None:
                pa, _ = nodes[cur]
                if pa == 0:
                    base = next_free
                    next_free += 256
                    nodes[cur][0] = -(base + 1)
                else:
                    base = -pa - 1
                leaf = base ^ 0
                nodes[leaf] = [-(entry_idx + 1), -(cur + 1)]
            else:
                # Split last prefix byte before tail? Match arh1 convention: split at split_pos, leaf has a = tail_pos - 1
                str_buf.extend(b"X")
                tail_pos = len(str_buf)
                str_buf.extend(tail_bytes + b"\x00" + struct.pack("<I", entry_idx))
                nodes[cur][0] = tail_pos - 1

        insert_in_trie(entries[0][0], 0, b"sg.bdat")
        insert_in_trie(entries[1][0], 1, b"sg.bdat")
        insert_in_trie(entries[2][0], 2, b"aw.bdat")
        insert_in_trie(entries[3][0], 3, None)

        max_node = max(nodes) + 1
        plain_trie = bytearray(max_node * 8)
        for n, (a, b) in nodes.items():
            struct.pack_into("<ii", plain_trie, n * 8, a, b)
        struct.pack_into("<I", str_buf, 0, len(str_buf))

        key = 0x12345678
        str_off = 0x28
        trie_off = str_off + len(str_buf)
        ent_off = trie_off + len(plain_trie)
        arh = bytearray(ent_off + len(entries) * 24)
        struct.pack_into(
            "<10I", arh, 0,
            0x31687261, len(str_buf), 0, str_off, len(str_buf), trie_off, len(plain_trie), ent_off, len(entries), key,
        )
        arh[str_off:trie_off] = arh_index._xor4(bytes(str_buf), key ^ arh_index.TRIE_XOR ^ 0xFFFFFFFF)
        arh[trie_off:ent_off] = arh_index._xor4(bytes(plain_trie), key ^ arh_index.TRIE_XOR)
        for i, (_, off, comp, unc, flags, serial) in enumerate(entries):
            struct.pack_into("<QIIII", arh, ent_off + i * 24, off, comp, unc, flags, serial)

        decoded = arh_index.decode_arh_paths(bytes(arh))
        self.assertEqual(decoded[0], "/bdat/cn/msg.bdat")
        self.assertEqual(decoded[1], "/bdat/gb/msg.bdat")
        self.assertEqual(decoded[2], "/bdat/cn/raw.bdat")
        self.assertEqual(decoded[3], "/event/a.motstm")

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            arh_path = tmp / "bf2.arh"
            arh_path.write_bytes(bytes(arh))
            # Deliberately put truncated ambiguous names into assets.tsv (diff_unc!)
            cat = tmp / "assets.tsv"
            cat.write_text(
                "source\tpath\tkind\tsize\tunc\tcomp\toffset\tchecksum\tsha256\n"
                "ard\tmsg.bdat\ttable\t\t50\t30\t4096\t111\t\n"
                "ard\tmsg.bdat\ttable\t\t80\t40\t8192\t222\t\n",
                encoding="utf-8",
            )
            mod_dir = tmp / "bdat_mod"
            (mod_dir / "romfs" / "bdat" / "gb").mkdir(parents=True)
            (mod_dir / "romfs" / "bdat" / "cn").mkdir(parents=True)
            gb_payload = bytes((i * 19) & 0xFF for i in range(512))
            cn_raw = b"raw-replacement-payload"
            (mod_dir / "romfs" / "bdat" / "gb" / "msg.bdat").write_bytes(gb_payload)
            (mod_dir / "romfs" / "bdat" / "cn" / "raw.bdat").write_bytes(cn_raw)

            fake_script = tmp / "tools" / "mods" / "ard_pack.py"
            fake_script.parent.mkdir(parents=True)
            fake_script.write_text("", encoding="utf-8")
            with mock.patch.object(ard_pack, "__file__", str(fake_script)):
                rc = ard_pack.main([
                    "--mod", str(mod_dir),
                    "--catalog", str(cat),
                    "--arh", str(arh_path),
                    "--ard-size", "200000",
                ])
            self.assertEqual(rc, 0)

            rep = {r["file"]: r for r in json.loads((tmp / "work" / "mods" / "ard-pack.json").read_text(encoding="utf-8"))["report"]}
            self.assertEqual(rep["bdat/gb/msg.bdat"]["status"], "appended")
            self.assertEqual(rep["bdat/cn/raw.bdat"]["status"], "appended-raw")
            out_arh = (mod_dir / "romfs" / "bf2.arh").read_bytes()
            # Entry 0 (cn/msg.bdat) must remain untouched; entry 1 (gb/msg.bdat) and entry 2 (cn/raw.bdat) updated.
            self.assertEqual(struct.unpack_from("<QII", out_arh, ent_off)[0], 0x1000)
            self.assertEqual(struct.unpack_from("<QII", out_arh, ent_off + 24)[0], 200000 + len(cn_raw))
            self.assertEqual(struct.unpack_from("<QII", out_arh, ent_off + 48), (200000, len(cn_raw), 0))


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
