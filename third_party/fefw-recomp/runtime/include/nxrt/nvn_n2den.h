// SPDX-License-Identifier: GPL-3.0-or-later
// n2den's NVN-HLE as the NVN implementation (instead of this runtime's own NVN back end): the library
// (n2den_nvnhle_bundle.lib, embed.h) owns the Vulkan device and presents into the game window; this
// adapter hands the game n2den's NVN functions through nvn::set_proc_resolver. Built when the runtime is
// configured with NXRT_N2DEN_DIST (the library's distribution folder); otherwise start() returns false.
#pragma once
#include <cstddef>
#include <cstdint>
#include <string>

namespace nxrt::nvn::n2den {

struct StartDesc {
    void* native_window = nullptr;     // platform::native_hwnd()
    uint32_t width = 0, height = 0;    // client size in pixels
    uint64_t program_id = 0;           // the Switch 2 program (0x0400...)
    const uint8_t* sdk_image = nullptr;  // the loaded sdk module (read for its SDK generation), may be null
    size_t sdk_image_size = 0;
};

bool available();                      // built with the library
bool start(const StartDesc& desc, std::string* error = nullptr);
void stop();
bool active();
void resize(uint32_t width, uint32_t height);
// The guest CPU wrote memory the GPU may read outside NVN calls (decoded movie frames).
void notify_cpu_write(uint64_t address, uint64_t size);

}  // namespace nxrt::nvn::n2den
