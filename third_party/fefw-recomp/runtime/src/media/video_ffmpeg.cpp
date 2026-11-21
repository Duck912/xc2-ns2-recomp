// SPDX-License-Identifier: GPL-3.0-or-later
#include "video_ffmpeg.h"

#if NXRT_HAVE_FFMPEG
#include <windows.h>

extern "C" {
#include <libavcodec/avcodec.h>
#include <libavutil/hwcontext.h>
#include <libavutil/imgutils.h>
}

#include <chrono>
#include <cstring>
#include <mutex>

#include "nxrt/log.h"

namespace nxrt::media {
namespace {
constexpr const char* kTag = "ffdec";
unsigned long long s_calls = 0, s_pics = 0;   // for the "packets N, pictures M" line every 30 packets

AVCodecID codec_id(int codec) {
    switch (codec) {
        case 9: return AV_CODEC_ID_VP9;
        case 8: return AV_CODEC_ID_VP8;
        default: return AV_CODEC_ID_AV1;
    }
}
// One D3D11VA device for the whole process. Creating it is the expensive part of the first frame: on 0.1.4 the
// presenting thread sat 183 ms inside a 213 ms frame at the start of a film, waiting for the first picture while the
// worker created the device under the decode. ffdec_prewarm() builds it during the loading screen instead, and every
// stream takes a reference to the same one; an unused device is one COM object and no GPU work.
std::mutex g_dev_mu;
AVBufferRef* g_dev = nullptr;

AVBufferRef* shared_device() {
    std::lock_guard<std::mutex> lk(g_dev_mu);
    if (g_dev) return g_dev;
    AVBufferRef* hw = nullptr;
    const auto t0 = std::chrono::steady_clock::now();
    if (av_hwdevice_ctx_create(&hw, AV_HWDEVICE_TYPE_D3D11VA, nullptr, nullptr, 0) < 0) return nullptr;
    g_dev = hw;   // process lifetime: each decoder holds its own reference to it
    const auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - t0).count();
    NXLOG_I(kTag, "D3D11VA device in %lld ms (shared by every stream)", static_cast<long long>(ms));
    return g_dev;
}

enum AVPixelFormat pick_fmt(AVCodecContext*, const enum AVPixelFormat* fmts) {
    for (const enum AVPixelFormat* p = fmts; *p != AV_PIX_FMT_NONE; ++p)
        if (*p == AV_PIX_FMT_D3D11 || *p == AV_PIX_FMT_VULKAN || *p == AV_PIX_FMT_CUDA) return *p;
    return fmts[0];
}
}  // namespace

struct FfDec {
    AVCodecContext* ctx = nullptr;
    AVBufferRef* hw = nullptr;
    AVFrame* frame = nullptr;
    AVPacket* pkt = nullptr;
    AVFrame* sw = nullptr;
    bool failed = false;
};

bool ffdec_available(std::string* why) {
    if (!avcodec_find_decoder(AV_CODEC_ID_AV1)) { if (why) *why = "avcodec has no AV1 decoder"; return false; }
    if (!shared_device()) { if (why) *why = "no D3D11VA device"; return false; }
    return true;
}

FfDec* ffdec_create(int codec, std::string* why) {
    // By name: avcodec_find_decoder(AV_CODEC_ID_AV1) can answer with libdav1d, which has no hardware decoding at all.
    // The native "av1" decoder is the one with the D3D11VA hwaccel; "vp9"/"vp8" likewise.
    const char* want = codec == 10 ? "av1" : codec == 9 ? "vp9" : "vp8";
    const AVCodec* c = avcodec_find_decoder_by_name(want);
    if (!c) c = avcodec_find_decoder(codec_id(codec));
    if (!c) { if (why) *why = "no decoder for this codec"; return nullptr; }
    auto* d = new FfDec();
    d->ctx = avcodec_alloc_context3(c);
    if (!d->ctx) { delete d; return nullptr; }
    AVBufferRef* shared = shared_device();
    if (!shared) {
        avcodec_free_context(&d->ctx);
        delete d;
        if (why) *why = "D3D11VA device creation failed";
        return nullptr;
    }
    d->hw = av_buffer_ref(shared);
    d->ctx->hw_device_ctx = av_buffer_ref(d->hw);
    d->ctx->get_format = pick_fmt;
    d->ctx->thread_count = 0;
    // One picture per packet is what the movie library's pool expects (the dav1d path decodes with max_frame_delay 1);
    // without this the native decoder holds frames back and the picture never advances.
    d->ctx->flags |= AV_CODEC_FLAG_LOW_DELAY;
    if (avcodec_open2(d->ctx, c, nullptr) < 0) {
        av_buffer_unref(&d->hw);
        avcodec_free_context(&d->ctx);
        delete d;
        if (why) *why = "avcodec_open2 failed";
        return nullptr;
    }
    d->frame = av_frame_alloc();
    d->sw = av_frame_alloc();
    d->pkt = av_packet_alloc();
    NXLOG_I(kTag, "libavcodec %s on D3D11VA", c->name);
    return d;
}

bool ffdec_prewarm() { return shared_device() != nullptr; }

bool ffdec_decode(FfDec* d, const uint8_t* data, size_t size, int64_t pts, std::vector<FfDecPicture>* out) {
    if (!d || d->failed || !out) return false;
    if (av_new_packet(d->pkt, static_cast<int>(size)) < 0) return false;
    std::memcpy(d->pkt->data, data, size);
    d->pkt->pts = pts;
    if (avcodec_send_packet(d->ctx, d->pkt) < 0) { av_packet_unref(d->pkt); d->failed = true; return false; }
    av_packet_unref(d->pkt);
    for (;;) {
        const int r = avcodec_receive_frame(d->ctx, d->frame);
        if (r == AVERROR(EAGAIN) || r == AVERROR_EOF) break;
        if (r < 0) { d->failed = true; return false; }
        AVFrame* f = d->frame;
        if (f->format == AV_PIX_FMT_D3D11 || f->format == AV_PIX_FMT_VULKAN || f->format == AV_PIX_FMT_CUDA) {
            if (av_hwframe_transfer_data(d->sw, f, 0) < 0) { av_frame_unref(d->frame); d->failed = true; return false; }
            f = d->sw;
        }
        if (f->format == AV_PIX_FMT_YUV420P && f->data[0] && f->data[1] && f->data[2]) {
            FfDecPicture p;
            p.w = f->width;
            p.h = f->height;
            p.pts = f->pts != AV_NOPTS_VALUE ? f->pts : pts;
            p.nv12.assign(static_cast<size_t>(p.w) * p.h * 3 / 2, 0);
            for (int y = 0; y < p.h; ++y) std::memcpy(p.nv12.data() + static_cast<size_t>(y) * p.w, f->data[0] + static_cast<size_t>(y) * f->linesize[0], p.w);
            uint8_t* uv = p.nv12.data() + static_cast<size_t>(p.w) * p.h;
            for (int y = 0; y < p.h / 2; ++y) {
                const uint8_t* u = f->data[1] + static_cast<size_t>(y) * f->linesize[1];
                const uint8_t* v = f->data[2] + static_cast<size_t>(y) * f->linesize[2];
                uint8_t* o = uv + static_cast<size_t>(y) * p.w;
                for (int x = 0; x < p.w / 2; ++x) { o[2 * x] = u[x]; o[2 * x + 1] = v[x]; }
            }
            out->push_back(std::move(p));
            ++s_pics;
        } else if (f->format == AV_PIX_FMT_NV12 && f->data[0] && f->data[1]) {
            FfDecPicture p;
            p.w = f->width;
            p.h = f->height;
            p.pts = f->pts != AV_NOPTS_VALUE ? f->pts : pts;
            p.nv12.resize(static_cast<size_t>(p.w) * p.h * 3 / 2);
            for (int y = 0; y < p.h; ++y) std::memcpy(p.nv12.data() + static_cast<size_t>(y) * p.w, f->data[0] + static_cast<size_t>(y) * f->linesize[0], p.w);
            uint8_t* uv = p.nv12.data() + static_cast<size_t>(p.w) * p.h;
            for (int y = 0; y < p.h / 2; ++y) std::memcpy(uv + static_cast<size_t>(y) * p.w, f->data[1] + static_cast<size_t>(y) * f->linesize[1], p.w);
            out->push_back(std::move(p));
            ++s_pics;
        }
        if (out->empty() && f->format != AV_PIX_FMT_NV12 && f->format != AV_PIX_FMT_YUV420P)
            NXLOG_W(kTag, "unexpected frame format %d (%dx%d)", static_cast<int>(f->format), f->width, f->height);
        av_frame_unref(d->frame);
        if (f == d->sw) av_frame_unref(d->sw);
    }
    ++s_calls;
    if (s_calls % 30 == 0) NXLOG_I(kTag, "packets %llu, pictures %llu", (unsigned long long)s_calls, (unsigned long long)s_pics);
    return true;
}

void ffdec_destroy(FfDec* d) {
    if (!d) return;
    if (d->pkt) av_packet_free(&d->pkt);
    if (d->sw) av_frame_free(&d->sw);
    if (d->frame) av_frame_free(&d->frame);
    if (d->ctx) avcodec_free_context(&d->ctx);
    if (d->hw) av_buffer_unref(&d->hw);
    delete d;
}
}  // namespace nxrt::media
#else
namespace nxrt::media {
bool ffdec_prewarm() { return false; }
bool ffdec_available(std::string* why) { if (why) *why = "built without FFmpeg"; return false; }
FfDec* ffdec_create(int, std::string* why) { if (why) *why = "built without FFmpeg"; return nullptr; }
bool ffdec_decode(FfDec*, const uint8_t*, size_t, int64_t, std::vector<FfDecPicture>*) { return false; }
void ffdec_destroy(FfDec*) {}
}
#endif
