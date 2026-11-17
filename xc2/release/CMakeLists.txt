# SPDX-License-Identifier: GPL-3.0-or-later
# The release split: xc2_rt.dll holds the runtime and the boot code, and the player's exe is only a stub linked
# against the libraries lifted from their own dump. Upstream builds it the same way (game-build/fefw/CMakeLists.txt
# with FEFW_RT_DLL=ON); the point is that the exe can then be built by Zig with no MSVC and no Windows SDK.
#
#   pwsh xc2\scripts\build-release.ps1          # configure + build the DLL, compile the lift, link the exe
#
# Nothing here is derived from the game: the DLL is our own code plus the runtime, and the lifted libraries are
# imported from the work folder by the build script, never by this project.
cmake_minimum_required(VERSION 3.25)
project(xc2_rt CXX)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
# Static MSVC runtime (/MT), as build-boot.ps1 uses for the exe.
if(NOT DEFINED CMAKE_MSVC_RUNTIME_LIBRARY)
    set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
endif()

get_filename_component(XC2_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../.." ABSOLUTE)
set(FEFW "${XC2_ROOT}/third_party/fefw-recomp")
# The headers of the pinned third-party libraries live in the runtime's own build tree (FetchContent).
set(GFX "${FEFW}/build/runtime-gfx")

set(NXRT_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(NXRT_BUILD_GFX ON CACHE BOOL "" FORCE)
set(NXRT_BUILD_GAMES ON CACHE BOOL "" FORCE)
set(NXRT_GAMES "xc2ns2" CACHE STRING "" FORCE)
set(NXRT_TEST_GAME "xc2ns2" CACHE STRING "" FORCE)
set(NXRT_RECOMP_INCLUDE "${XC2_ROOT}/third_party/nxrecomp/recomp/include" CACHE PATH "")

add_subdirectory("${FEFW}/runtime" runtime)

add_library(xc2_rt SHARED
    "${XC2_ROOT}/xc2/src/xc2_boot.cpp"
    "${XC2_ROOT}/xc2/src/x2_opus301.cpp"
    "${XC2_ROOT}/xc2/src/x2_audio301.cpp"
    src/xc2_rt.def)
target_include_directories(xc2_rt PRIVATE
    "${XC2_ROOT}/third_party/nxrecomp/recomp/include"
    "${FEFW}/runtime/include"
    "${FEFW}/runtime/games"
    "${GFX}/_deps/volk-src"
    "${GFX}/_deps/vulkan_headers-src/include"
    "${GFX}/_deps/vma-src/include"
    "${GFX}/_deps/sdl3-src/include")
target_compile_definitions(xc2_rt PRIVATE XC2_RT_DLL=1 XC2_MODULES_7=1)
target_link_libraries(xc2_rt PRIVATE
    nxrt_game_xc2ns2_core nxrt_gfx nxrt
    kernel32 user32 gdi32 winmm imm32 ole32 oleaut32 version uuid advapi32 setupapi shell32 dinput8 psapi)
# No /DEBUG: a release DLL should not carry a PDB path. /HIGHENTROPYVA:NO keeps the guest ranges at 0x71_0000_0000
# free, which is what the runtime needs to map the game's address space.
target_link_options(xc2_rt PRIVATE /HIGHENTROPYVA:NO /DEBUG:NONE /Brepro)
