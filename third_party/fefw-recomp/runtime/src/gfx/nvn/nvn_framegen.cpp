// SPDX-License-Identifier: GPL-3.0-or-later
// HUD-less colour for DLSS Frame Generation (nvn_framegen.h).
#include "nvn_framegen.h"

#include <string>
#include <vector>

#include "extras/framegen.h"
#include "nxrt/config.h"
#include "nxrt/extras.h"
#include "nxrt/game.h"
#include "nxrt/log.h"

namespace nxrt::nvn::be::gpu {
namespace {

constexpr const char* kTag = "framegen";

struct Img {
    gfx::Image img;
    VkImageLayout layout = VK_IMAGE_LAYOUT_UNDEFINED;
};

struct State {
    bool after_eval = false;
    Texture* captured = nullptr;     // this frame's copy is of this texture
    std::vector<Texture*> window;    // the textures of the window last presented
    Img copy[2], bb[2];
    uint32_t cur = 0;
    uint64_t frames = 0, captures = 0, whole = 0;
    bool split = false;              // [hdr] ui_split is in use: capture every frame, not only after a DLSS evaluation
    bool copy_failed = false;        // the copy image could not be made: no more captures (logged once)
    Img* shown = nullptr;            // the copy the last present used for the HDR UI split (kept for repeated presents)
    uint64_t split_frames = 0, split_used = 0;
};
State& st() {
    static State s;
    return s;
}

VkFormat unorm_of(VkFormat f) {
    switch (f) {
        case VK_FORMAT_R8G8B8A8_SRGB: return VK_FORMAT_R8G8B8A8_UNORM;
        case VK_FORMAT_B8G8R8A8_SRGB: return VK_FORMAT_B8G8R8A8_UNORM;
        case VK_FORMAT_A8B8G8R8_SRGB_PACK32: return VK_FORMAT_A8B8G8R8_UNORM_PACK32;
        default: return f;
    }
}

VkFormat srgb_of(VkFormat f) {
    switch (f) {
        case VK_FORMAT_R8G8B8A8_UNORM: return VK_FORMAT_R8G8B8A8_SRGB;
        case VK_FORMAT_B8G8R8A8_UNORM: return VK_FORMAT_B8G8R8A8_SRGB;
        case VK_FORMAT_A8B8G8R8_UNORM_PACK32: return VK_FORMAT_A8B8G8R8_SRGB_PACK32;
        default: return f;
    }
}

bool ensure(Img& i, VkExtent2D e, VkFormat fmt, VkImageUsageFlags usage, const char* name) {
    if (i.img.image && i.img.extent.width == e.width && i.img.extent.height == e.height && i.img.format == fmt) return true;
    if (i.img.image) {
        gfx::Image old = i.img;
        defer_destroy([old]() mutable { device().destroy_image(old); });
    }
    i = Img();
    gfx::ImageDesc d;
    d.format = fmt;
    d.width = e.width;
    d.height = e.height;
    d.usage = usage;
    d.name = name;
    std::string why;
    if (device().create_image(d, &i.img, &why) != VK_SUCCESS) {
        NXLOG_E(kTag, "%s %ux%u: not made (%s)", name, e.width, e.height, why.c_str());
        i = Img();
        return false;
    }
    return true;
}

void to(VkCommandBuffer cb, Img& i, VkImageLayout l) {
    image_barrier(cb, i.img.image, i.layout, l, VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1);
    i.layout = l;
}

bool is_window_texture(const State& s, Texture* t) {
    for (Texture* w : s.window)
        if (w == t) return true;
    return false;
}

// The texture's level 0 into copy[cur] (TRANSFER_DST layout afterwards). No pass open.
bool copy_texture(State& s, Frame& f, Texture* t) {
    if (!tex_gpu(t) || tex_is_depth(t) || !tex_copy_source_ok(t)) return false;
    const VkExtent3D e = tex_image_extent(t, 0);
    const VkFormat fmt = hudless_copy_format(tex_vk_format(t), extras::hdr_state().scene_hdr);
    Img& c = s.copy[s.cur];
    if (!ensure(c, VkExtent2D{e.width, e.height}, fmt,
                VK_IMAGE_USAGE_TRANSFER_DST_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT | VK_IMAGE_USAGE_SAMPLED_BIT, "framegen hudless copy")) {
        s.copy_failed = true;
        return false;
    }
    tex_transition(t, f, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL);
    to(f.cb, c, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL);
    VkImageCopy r = {};
    r.srcSubresource = r.dstSubresource = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 0, 1};
    r.extent = e;
    vkCmdCopyImage(f.cb, tex_image(t), VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL, c.img.image, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, 1, &r);
    memory_barrier(f.cb);
    return true;
}

}  // namespace

VkFormat hudless_copy_format(VkFormat tex_fmt, bool scene_hdr) {
    // Match nvn_present's view choice: SDR passes UNORM bytes as-is; HDR output decodes 8-bit display-referred buffers through their sRGB view.
    return scene_hdr ? srgb_of(tex_fmt) : unorm_of(tex_fmt);
}

bool fg_hudless_on() {
    static const bool v = extras::framegen_requested() &&
                          config_get_bool("dlss", "frame_gen_hudless", nxrt::game::info().frame_gen_hudless_default);
    return v;
}

void fg_note_eval() {
    if (fg_hudless_on()) st().after_eval = true;
}

bool fg_hudless_candidate(Texture* t, bool blended) {
    State& s = st();
    return blended && !s.copy_failed && (s.after_eval || (s.split && !fg_hudless_on())) && !s.captured && t && is_window_texture(s, t);
}

void fg_hudless_capture(Frame& f, Texture* t) {
    State& s = st();
    if (copy_texture(s, f, t)) {
        s.captured = t;
        ++s.captures;
    } else {
        s.after_eval = false;
    }
}

VkImageView hdr_scene_view(Texture* presented, Frame& f, bool again) {
    State& s = st();
    static const bool on = config_get_bool("hdr", "ui_split", true);
    const extras::HdrState hs = extras::hdr_state();
    s.split = on && hs.scene_hdr && hs.output != extras::OutputKind::Sdr8 && hs.peak_ratio > 1.001f;
    if (!again) {
        s.shown = (s.split && presented && s.captured == presented) ? &s.copy[s.cur] : nullptr;
        if (s.split) {
            s.split_used += s.shown ? 1 : 0;
            if (s.split_frames++ % 3600 == 0)
                NXLOG_I(kTag, "HDR UI split: %llu of %llu frames had a copy before the UI (the others expand the whole picture)",
                        static_cast<unsigned long long>(s.split_used), static_cast<unsigned long long>(s.split_frames));
        }
    }
    if (!s.split || !s.shown || !s.shown->img.image) return VK_NULL_HANDLE;
    to(f.cb, *s.shown, VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL);
    return s.shown->img.view;
}

void fg_hudless_present(Window* w, Texture* presented, Frame& f, VkExtent2D bb, VkFormat bb_format, bool again,
                        const std::function<void(VkImageView, VkImageView)>& draw) {
    State& s = st();
    if (!fg_hudless_on() && !s.split) return;
    if (w) {
        s.window.clear();
        for (const auto& t : w->textures) s.window.push_back(t.get());
    }
    const bool eval = s.after_eval;
    Texture* cap = s.captured;
    s.after_eval = false;
    s.captured = nullptr;
    if (!fg_hudless_on()) {
        if (cap && !again) s.cur ^= 1u;   // keep the copy just presented while the next frame fills the other one
        return;
    }
    if (again || !eval || !presented || !extras::framegen_running()) return;
    if (cap != presented) {   // no blended draw into the window texture after the scene: nothing known about the UI
        ++s.whole;
        return;
    }
    Img& c = s.copy[s.cur];
    Img& b = s.bb[s.cur];
    s.cur ^= 1u;
    if (!ensure(b, bb, bb_format, VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT | VK_IMAGE_USAGE_SAMPLED_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT,
                "framegen hudless"))
        return;
    to(f.cb, c, VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL);
    b.layout = VK_IMAGE_LAYOUT_UNDEFINED;
    to(f.cb, b, VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL);
    draw(c.img.view, b.img.view);
    to(f.cb, b, VK_IMAGE_LAYOUT_GENERAL);
    extras::framegen_hudless(f.cb, b.img.image, b.img.view, bb_format, bb);
    if (s.frames++ == 0 || s.frames % 1800 == 0)
        NXLOG_I(kTag, "HUD-less colour: %llu frames, %llu captured before the UI, %llu with no capture", static_cast<unsigned long long>(s.frames),
                static_cast<unsigned long long>(s.captures), static_cast<unsigned long long>(s.whole));
}

}  // namespace nxrt::nvn::be::gpu
