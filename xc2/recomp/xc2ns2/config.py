# SPDX-License-Identifier: GPL-3.0-or-later
"""Per-game configuration of Xenoblade Chronicles 2 - Nintendo Switch 2 Edition (title 0100E95004038000).

Feasibility-stage config: it only claims what has been verified so far (module list and build id from the extracted
ExeFS). The module bases are the loader's, not the binary's: main is the console's 0x7100000000; sdk/subsdk0/rtld use
the same layout the MPR target uses until an NS2 boot trace confirms them (docs: runtime S1b). Lifting is base-relative
inside one module, so a wrong secondary base changes cross-module call targets, not the code of the module itself.

main is 9.05 MB of NSO0 (flags 0x3f, LZ4 text/rodata/data), text 0x9bd3d0. Its .eh_frame_hdr and .dynsym are intact:
function discovery finds ~49.9k functions, 48,739 of them with both an FDE and a sized FUNC symbol.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from nxrecomp.config import GameConfig, ModuleSpec          # noqa: E402


class Config(GameConfig):
    name = 'xc2ns2'
    title_id = '0100E95004038000'
    version = 'NS2 Edition (NUP v1, v0)'
    build_id = '5087AF2917D85858A0FD49CB4D6EED67'      # of main, from the NSO header
    modules = [
        ModuleSpec('main', 0x7100000000, 'main'),
        ModuleSpec('sdk', 0x7500000000, 'sdk'),
        ModuleSpec('subsdk0', 0x7600000000, 'subsdk0'),
        ModuleSpec('rtld', 0x7700000000, 'rtld'),      # the runtime's loader does rtld's job; lifted for completeness
        # The retail 3.0.1 ExeFS (HANDOVER 89) carries three more modules. They come last so the four above keep indices
        # 0..3: the index only has to be unique per module (it is the top 12 bits of an import id, nxmodule.cpp).
        ModuleSpec('subsdk1', 0x7640000000, 'subsdk1'),
        ModuleSpec('subsdk2', 0x7680000000, 'subsdk2'),
        ModuleSpec('subsdk3', 0x76C0000000, 'subsdk3'),
    ]
    overrides = {}
    # rtld 0x0: the process entry. rtld 0x1470: the PLT0 lazy-resolution stub reached by `br` from the PLT entries; it sits
    # mid-function in the FDE map but the guest calls it as a function entry, so it must be rooted.
    extra_entries = {'rtld': [0x0, 0x1470]}
    patches = None
