# Third-party notices

This repository contains and links against third-party software. Components that are checked in are listed with
their path; components fetched at build time by CMake (`FetchContent`, see
`third_party/fefw-recomp/runtime/cmake/gfx_deps.cmake`) are listed with their upstream projects.

## Checked into this repository

| component | path | licence |
|---|---|---|
| fefw-recomp runtime (fork of Goldoire/fefw-recomp) | `third_party/fefw-recomp` | **GPL-3.0** (see its `LICENSE` and `MODIFICATIONS.md`) |
| AMD FidelityFX API headers | `third_party/fefw-recomp/runtime/third_party/amd_ffx_api` | MIT (see its `LICENSE.txt`) |
| AMD FidelityFX API, frame generation | `third_party/fefw-recomp/runtime/third_party/amd_ffx_api_fg` | MIT (see its `LICENSE.txt`) |
| AMD FidelityFX FSR 1 | `third_party/fefw-recomp/runtime/third_party/ffx_fsr1` | MIT (see its `LICENSE.txt`) |
| NVIDIA Image Scaling | `third_party/fefw-recomp/runtime/third_party/nvidia_nis` | MIT (see its `LICENSE.txt`) |
| NVIDIA Streamline | `third_party/fefw-recomp/runtime/third_party/nvidia_streamline` | MIT (see its `license.txt`) |
| dav1d (movie decoding) | `third_party/fefw-recomp/runtime/third_party/dav1d` | BSD-2-Clause (see its `COPYING`) |
| DejaVu Sans (fonts) | `third_party/fefw-recomp/runtime/assets/fonts` | Bitstream Vera / public domain additions |
| Kenney input prompts | `third_party/fefw-recomp/runtime/assets/prompts` | CC0 |
| nxnative Opus HLE (ported into `x2_opus301.cpp`) | `xc2/src/x2_opus301.cpp` | **MIT** (see `LICENSE.nxnative.MIT`) |

## Tool sources

The tools under `third_party/fefw-recomp/tools/` keep their licence copies next to the material they cover:

| material | licence file | licence | what it is |
|---|---|---|---|
| Sascha Willems' Vulkan samples (commit `1cbc8d87`) | `tools/shaders/licenses/LICENSE.SaschaWillems-Vulkan.MIT` | MIT | the stand-in shader corpus in `tools/shaders/corpus/sascha_dksh/` is **compiled from** those samples' GLSL |
| Mesa NAK (`src/nouveau/compiler/nak/sm70_encode.rs`) | `tools/shaders/licenses/LICENSE.mesa-nak.MIT` | MIT | used by `tools/shaders/ampere/decoder`: the Volta+ encoders were **inverted into decode rules** (opcodes, field positions, modifier encodings); no source copied |
| Ryujinx / Ryubing | `tools/shaders/licenses/LICENSE.Ryubing.MIT`, `tools/tiling/licenses/LICENSE.Ryubing.MIT` | MIT | the shader translator packages and the tiling tables |
| SuperMarioWonderRecomp (BelmanteGu) | `tools/shaders/licenses/LICENSE.SuperMarioWonderRecomp.MIT`, `tools/tiling/licenses/LICENSE.SuperMarioWonderRecomp.MIT` | MIT | recompilation findings that both tools cross-check against |
| smo-recomp | `tools/shaders/licenses/LICENSE.smo-recomp.GPL-3.0` | GPL-3.0 | reference findings |
| astc-encoder | `tools/textures/licenses/LICENSE.astc-encoder.Apache-2.0` | Apache-2.0 | the ASTC encoder the texture tool drives (also fetched at build time) |
| bc7enc_rdo | `tools/textures/licenses/LICENSE.bc7enc_rdo` | see the file | BC7 encoder; it bundles **bc7e.ispc** (Apache-2.0, Binomial LLC) and **LodePNG** (Lode Vandevenne) |
| ISPC | `tools/textures/licenses/LICENSE.ispc.BSD-3-Clause` | BSD-3-Clause | the ISPC runtime the BC7 encoder is built with |

## Kept outside this repository

| component | where | licence |
|---|---|---|
| fefw-recomp 0.2.0 reference snapshot | `work/ref/fefw-recomp-ref-0.2.0` (git-ignored; 558 files kept because upstream may be deleted — see `UPSTREAM.md`) | **GPL-3.0** |
| Ryujinx shader translator (`Spv.Generator`, `Ryujinx.Graphics.Shader`) | staged by `third_party/fefw-recomp/tools/shaders/scripts/setup_ryujinx.ps1`, not checked in | **MIT** |

## Read for reference only, no code copied

| project | what |
|---|---|
| [AksharDP/xc2-recomp](https://github.com/AksharDP/xc2-recomp) | the Switch 1 recompilation, read to cross-check findings | **MIT** |

## Fetched at build time

| component | fetched by | licence |
|---|---|---|
| SDL3 | `runtime/cmake/gfx_deps.cmake` | Zlib |
| Vulkan-Headers | idem | Apache-2.0 |
| volk | idem | MIT |
| VulkanMemoryAllocator | idem | MIT |
| Dear ImGui | idem | MIT |
| zstd | idem | BSD-3-Clause |
| astc-encoder / bc7enc_rdo | texture transcoder step | Apache-2.0 / MIT |
| Ryujinx packages | `third_party/fefw-recomp/tools/shaders/scripts/setup_ryujinx.ps1` | MIT |

## External tools the build expects on the machine

The Visual Studio Build Tools / MSVC runtime, LLVM (clang-cl, llvm-lib), CMake, Ninja, the .NET SDK, the Vulkan
SDK (spirv-as / spirv-dis / spirv-val / glslc), NASM and Python are used but not redistributed here; each carries
its own licence. [nxrecomp](https://github.com/drakolordx7/nxrecomp) (GPL-3.0) is cloned into
`third_party/nxrecomp` by the user.

## Game code and assets

Not included, not licensed here. The lifted C++ that the build produces from the game's NSO modules is derived
from copyrighted code and is **not** covered by this repository's licence; do not redistribute builds.
