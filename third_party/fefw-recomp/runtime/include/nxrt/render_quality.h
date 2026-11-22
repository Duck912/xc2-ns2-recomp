// SPDX-License-Identifier: GPL-3.0-or-later
// [upscale] render_quality: the 3D render quality the F1 page and the launcher store as intent. The runtime derives the scales from it
// at start-up (the scene set's [gfx] render_scale, the output side's [gfx] output_scale, the dynamic-resolution lock), so nothing that
// depends on the output resolution ([am] resolution) is stored and can go stale when another tool changes that resolution.
//
// XC2 NS2 renders its 3D scene into a 1280x720 set and upscales into a 1920x1080 set: the output side scales to the output height
// (out_h / 1080), the scene to that height times the mode's share (out_h * share / 720), and the upscaler picks its mode from the ratio.
#pragma once

#include <cstring>

namespace nxrt {

struct RenderQualityMode {
    const char* key;   // the [upscale] render_quality value
    double share;      // the upscaler's input as a share of the output height; 0: the console's own dynamic resolution
};

inline constexpr RenderQualityMode kRenderQualityModes[] = {
    {"native", 1.0}, {"quality", 2.0 / 3.0}, {"balanced", 0.58}, {"performance", 0.5}, {"ultra_performance", 1.0 / 3.0}, {"console", 0.0},
};
inline constexpr int kRenderQualityModeCount = static_cast<int>(sizeof kRenderQualityModes / sizeof kRenderQualityModes[0]);

// The mode named `key`, or null (not set / not known).
inline const RenderQualityMode* render_quality_mode(const char* key) {
    if (!key || !*key) return nullptr;
    for (const RenderQualityMode& m : kRenderQualityModes)
        if (std::strcmp(m.key, key) == 0) return &m;
    return nullptr;
}

// The scales a mode implies at output height out_h. False for the console mode (no scaling, no lock).
inline bool render_quality_scales(const RenderQualityMode& m, int out_h, double* scene, double* out) {
    if (m.share <= 0.0 || out_h <= 0) return false;
    *scene = out_h * m.share / 720.0;
    *out = out_h / 1080.0;
    return true;
}

}  // namespace nxrt
