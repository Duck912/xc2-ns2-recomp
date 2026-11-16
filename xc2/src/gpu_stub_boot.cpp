// SPDX-License-Identifier: GPL-3.0-or-later
// No-graphics boot shim: the parts of the NVN back end / gfx shell that nxrt.lib references unconditionally (the movie decoder
// asks the GPU queue for serials, switch2.cpp notes HDR luminance, the test tools wait for screenshot writes). With
// [boot] nvn = 0 nothing reaches them; they exist so the boot harness links without nxrt_gfx. Replace this file with the real
// nxrt_gfx link once the boot reaches NVN.
#include <cstdint>

namespace nxrt::nvn::be::gpu {

static uint64_t g_serial = 0;

bool active() { return false; }
uint64_t last_serial() { return g_serial; }
bool serial_done(uint64_t) { return true; }
uint64_t submit(const void *) { return ++g_serial; }

}  // namespace nxrt::nvn::be::gpu

namespace nxrt::extras {

void hdr_note_layer_luminance(bool, unsigned int, unsigned int) {}

}  // namespace nxrt::extras

namespace nxrt::gfx {

void wait_screenshot_writes(void) {}

}  // namespace nxrt::gfx
