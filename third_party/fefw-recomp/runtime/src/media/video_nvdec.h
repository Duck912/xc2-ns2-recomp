// SPDX-License-Identifier: GPL-3.0-or-later
// NVDEC decoding for the movie library's videos, through the driver's nvcuvid.dll.
//
// The Switch 2 movie library hands one temporal unit to nn::codec and the picture comes back on a later call, so a
// decoder here is: feed the unit, take the pictures it showed. nvcuvid's parser understands VP8, VP9 and AV1 itself, so
// one backend serves every format the game ships (the NS1 films are VP9, the DLC openings AV1).
//
// It is offered only when the GPU is NVIDIA and nvcuvid.dll loads; every failure falls back to libvpx/dav1d on the CPU.
#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace nxrt::media {

struct NvDecPicture {
    std::vector<uint8_t> nv12;
    int w = 0, h = 0;
    int64_t pts = 0;
};

struct NvDec;

// codec: 8 VP8, 9 VP9, 10 AV1 (the same numbers video_codec.cpp uses).
bool nvdec_available(std::string* why);
NvDec* nvdec_create(int codec, int max_w, int max_h, std::string* why);
bool nvdec_decode(NvDec* d, const uint8_t* data, size_t size, int64_t pts, std::vector<NvDecPicture>* out);
void nvdec_destroy(NvDec* d);

}  // namespace nxrt::media
