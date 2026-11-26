#!/usr/bin/env python3
"""The setup keeps an existing xc2_boot.exe only when it still matches the runtime it was linked against.

A release upgrade replaces runtime/xc2_rt.dll and keeps the exe (step_link_package), but the exe carries the lifted
game code: pairing a new runtime with an exe from an older release is a mixed build, and on the 0.2.1 video a player
reported exactly that - rendering faults that went away after a fresh build.
"""

import importlib.util
import json
import pathlib
import tempfile
import time
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]


def load_setup():
    spec = importlib.util.spec_from_file_location("xc2_setup", ROOT / "tools" / "setup" / "xc2_setup.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LinkStampTest(unittest.TestCase):
    def setUp(self):
        self.setup = load_setup()
        self.dir = pathlib.Path(tempfile.mkdtemp())
        self.dll = self.dir / "xc2_rt.dll"
        self.dll.write_bytes(b"x" * 128)
        self.stamp = self.dir / "link-stamp.json"

    def test_missing_stamp_means_relink(self):
        """An install from before the stamp existed has no proof, so it relinks once."""
        self.assertFalse(self.setup.link_stamp_matches(self.stamp, self.setup.runtime_signature(self.dll)))

    def test_matching_stamp_keeps_the_exe(self):
        sig = self.setup.runtime_signature(self.dll)
        self.stamp.write_text(json.dumps(sig), encoding="utf-8")
        self.assertTrue(self.setup.link_stamp_matches(self.stamp, sig))

    def test_replaced_runtime_forces_relink(self):
        sig = self.setup.runtime_signature(self.dll)
        self.stamp.write_text(json.dumps(sig), encoding="utf-8")
        time.sleep(1.1)                      # the file system stamps mtimes to the second on some volumes
        self.dll.write_bytes(b"y" * 256)     # what an upgrade does: new runtime, same exe
        self.assertFalse(self.setup.link_stamp_matches(self.stamp, self.setup.runtime_signature(self.dll)))

    def test_missing_runtime_is_not_a_signature(self):
        self.assertIsNone(self.setup.runtime_signature(self.dir / "nope.dll"))
        self.assertFalse(self.setup.link_stamp_matches(self.stamp, None))


if __name__ == "__main__":
    unittest.main()
