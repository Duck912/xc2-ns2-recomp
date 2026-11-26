# SPDX-License-Identifier: GPL-3.0-or-later
# The Xenoblade Chronicles 2 (Switch 2 Edition) game module (docs/GAME_BOUNDARY.md, xc2ns2_game.h).
#   nxrt_game_xc2ns2_data   identity, file names (pure data; the launcher links it)
#   nxrt_game_xc2ns2_core   + title facts from main.npdm (links nxrt)
# The play-mode library comes once the game boots.
set(_g "${CMAKE_CURRENT_SOURCE_DIR}")
set(_rt "${PROJECT_SOURCE_DIR}")

add_library(nxrt_game_xc2ns2_data STATIC "${_g}/xc2ns2_data.cpp")
target_include_directories(nxrt_game_xc2ns2_data PUBLIC "${_rt}/include" "${_rt}/games" "${_g}")
target_compile_features(nxrt_game_xc2ns2_data PUBLIC cxx_std_20)

add_library(nxrt_game_xc2ns2_core STATIC "${_g}/xc2ns2_core.cpp")
target_link_libraries(nxrt_game_xc2ns2_core PUBLIC nxrt_game_xc2ns2_data nxrt)
