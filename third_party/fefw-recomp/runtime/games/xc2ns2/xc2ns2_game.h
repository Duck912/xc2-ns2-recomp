// SPDX-License-Identifier: GPL-3.0-or-later
// Xenoblade Chronicles 2 - Nintendo Switch 2 Edition: the game boundary (docs/GAME_BOUNDARY.md).
//
// Two libraries, both subsets of what the FEFW base does:
//   nxrt_game_xc2ns2_data   identity and file names (pure data; the launcher can link it alone)
//   nxrt_game_xc2ns2_core   + title facts read from main.npdm (links nxrt)
// Play mode, menus and prompts are not here yet: they come once the game boots.
#pragma once

#include <cstdint>

#include "nxrt/game.h"

void nxrt_register_game_xc2ns2();
void nxrt_register_game_xc2ns2_core();
void nxrt_register_game_xc2ns2_data();

namespace nxrt::games::xc2ns2 {
const game::Info& data_info();     // xc2ns2_data.cpp
const game::Info& core_info();     // xc2ns2_core.cpp
}  // namespace nxrt::games::xc2ns2
