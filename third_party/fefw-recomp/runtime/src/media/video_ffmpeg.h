// SPDX-License-Identifier: GPL-3.0-or-later
// FFmpeg's libavcodec as the hardware movie decoder, the way the Switch emulators do it (Eglantine/Eden/Yuzu): the
// demuxed packet goes in, a decoded picture comes out, and the GPU does the work (D3D11VA on NVIDIA, Vulkan elsewhere).
#pragma once
#include <cstdint>
#include <string>
#include <vector>

namespace nxrt::media {
struct FfDecPicture { std::vector<uint8_t> nv12; int w = 0, h = 0; int64_t pts = 0; };
struct FfDec;
bool ffdec_available(std::string* why);
bool ffdec_prewarm();                               // create the shared hardware device now; safe to call from any thread
const char* ffdec_hw_name();                        // "D3D11VA" or "Vulkan Video", for the logs
FfDec* ffdec_create(int codec, std::string* why);   // 8 VP8, 9 VP9, 10 AV1
bool ffdec_decode(FfDec* d, const uint8_t* data, size_t size, int64_t pts, std::vector<FfDecPicture>* out);
void ffdec_destroy(FfDec* d);
}
