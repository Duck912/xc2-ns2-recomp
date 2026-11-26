// SPDX-License-Identifier: GPL-3.0-or-later
// movie::Decoder (the Switch 2 SDK's movie decoder, the MediaCodec wrapper inside subsdk0) on the host: AV1 with dav1d, Vorbis with
// libvorbis. The library above it (movie::VideoDecoder / AudioDecoder) then runs unchanged and keeps its own contract with the player.
//
// Protocol (capibawa/nxnative dm/host/hle_movie.c, same NintendoSDK_movie library): the client registers four nn::os events, takes a
// free input index, has GetInputBuffer point a movie::Buffer at that slot, sends the packet with SendInputBufferForDecode, and later
// takes a finished picture by output index and copies it out with GetOutputBuffer. This file implements that with input slots of its
// own and an output queue of NV12 pictures.
#include <algorithm>
#include <cstdint>
#include <cstring>
#include <deque>
#include <memory>
#include <mutex>
#include <vector>

#include <windows.h>

#include "nxrt/abi.h"
#include "nxrt/config.h"
#include "nxrt/dispatch.h"
#include "nxrt/game.h"
#include "nxrt/kernel.h"
#include "nxrt/log.h"
#include "nxrt/memory.h"
#include "nxrt/module.h"
#include "nxrt/movie_vdec.h"

#if NXRT_HAVE_DAV1D
#include <dav1d/dav1d.h>
#endif

namespace nxrt::media {
namespace {

#define A(i) (c->x[i])
#define RET(v) (c->x[0] = static_cast<uint64_t>(v))

constexpr const char* kTag = "movie.dec";
constexpr uint64_t kSubsdk0 = 0x7600000000ull;
constexpr uint32_t kOk = 0, kNoInput = 0x1011, kNoOutput = 0x100e, kBadArg = 0x100b;
constexpr size_t kInSlots = 4, kInCap = 4u << 20, kOutSlots = 16;
constexpr uint64_t kBufData = 0x00, kBufSize = 0x08, kBufFilled = 0x10, kBufTime = 0x18, kBufFlags = 0x20;

bool g_log = false;

uint64_t gcall(::Ctx* c, uint64_t fn, uint64_t a0, uint64_t a1 = 0, uint64_t a2 = 0, uint64_t a3 = 0) {
    if (!fn) return 0;
    const ::Ctx saved = *c;
    c->x[0] = a0; c->x[1] = a1; c->x[2] = a2; c->x[3] = a3; c->x[30] = 0;
    dispatch_call(c, fn);
    const uint64_t r = c->x[0];
    *c = saved;
    return r;
}

struct Slot { std::vector<uint8_t> data; bool busy = false; int64_t time = 0; uint32_t flags = 0; };
struct Frame { std::vector<uint8_t> nv12; uint32_t w = 0, h = 0; int64_t time = 0; uint32_t flags = 0; };

struct HostDecoder {
    std::mutex mu;
    uint64_t ev[4] = {0, 0, 0, 0};   // input available, output ready, format changed, error
    int type = 0, fmt = 0, mode = 0;
    Slot in[kInSlots];
    std::deque<std::unique_ptr<Frame>> out;   // decoded, not acquired
    std::unique_ptr<Frame> held[kOutSlots];   // acquired by the client, index-addressable
    uint32_t w = 0, h = 0;
    uint64_t packets = 0, pictures = 0, errors = 0;
    bool started = false;
    uint64_t signal_event = 0;
#if NXRT_HAVE_DAV1D
    Dav1dContext* av1 = nullptr;
    Dav1dSettings cfg{};
#endif
};

HostDecoder* dec_of(uint64_t self) { return self ? reinterpret_cast<HostDecoder*>(rd64(self)) : nullptr; }

void fire(::Ctx* c, HostDecoder& d, int which) {
    if (which < 0 || which > 3 || !d.ev[which] || !d.signal_event) return;
    gcall(c, d.signal_event, d.ev[which]);
}
void fire_later(HostDecoder& d, int which) {
    if (which < 0 || which > 3 || !d.ev[which] || !d.signal_event) return;
    kernel::signal_system_event(d.ev[which]);
}

#if NXRT_HAVE_DAV1D
void to_nv12(const Dav1dPicture& pic, Frame& f) {
    f.w = static_cast<uint32_t>(pic.p.w);
    f.h = static_cast<uint32_t>(pic.p.h);
    const uint32_t w = f.w, h = f.h, cw = (w + 1) / 2, ch = (h + 1) / 2;
    f.nv12.resize(static_cast<size_t>(w) * h + static_cast<size_t>(cw) * ch * 2);
    const auto* y = static_cast<const uint8_t*>(pic.data[0]);
    uint8_t* dst = f.nv12.data();
    for (uint32_t r = 0; r < h; ++r) std::memcpy(dst + static_cast<size_t>(r) * w, y + static_cast<size_t>(r) * pic.stride[0], w);
    uint8_t* uv = dst + static_cast<size_t>(w) * h;
    const auto* u = static_cast<const uint8_t*>(pic.data[1]);
    const auto* v = static_cast<const uint8_t*>(pic.data[2]);
    for (uint32_t r = 0; r < ch; ++r) {
        for (uint32_t x = 0; x < cw; ++x) {
            uv[static_cast<size_t>(r) * cw * 2 + x * 2] = u[static_cast<size_t>(r) * pic.stride[1] + x];
            uv[static_cast<size_t>(r) * cw * 2 + x * 2 + 1] = v[static_cast<size_t>(r) * pic.stride[1] + x];
        }
    }
}
#endif

// Configure(MediaData*): the size comes from its width/height, through the library's own accessors.
uint64_t prop_int(::Ctx* c, uint64_t md, const char* key) {
    const uint64_t get = module_find_symbol("_ZNK2nn5movie9MediaData11GetInt32EPiPKc");
    if (!get || !md) return 0;
    alignas(16) int32_t v = 0;
    return gcall(c, get, md, reinterpret_cast<uint64_t>(&v), reinterpret_cast<uint64_t>(key)) == 0 ? static_cast<uint64_t>(static_cast<int64_t>(v)) : 0;
}

void dec_ctor(::Ctx* c) {
    auto* d = new HostDecoder();
    d->type = static_cast<int>(A(1)); d->fmt = static_cast<int>(A(2)); d->mode = static_cast<int>(A(3));
    d->signal_event = module_find_symbol("_ZN2nn2os17SignalSystemEventEPNS0_15SystemEventTypeE");
    wr64(A(0), reinterpret_cast<uint64_t>(d));
    if (g_log) NXLOG_I(kTag, "Decoder: type %d, output format %d, mode %d", d->type, d->fmt, d->mode);
    RET(0);
}

void dec_dtor(::Ctx* c) {
    HostDecoder* d = dec_of(A(0));
    if (d) {
#if NXRT_HAVE_DAV1D
        if (d->av1) dav1d_close(&d->av1);
#endif
        delete d;
    }
    if (A(0)) wr64(A(0), 0);
    RET(0);
}

void dec_configure(::Ctx* c) {
    HostDecoder* d = dec_of(A(0));
    if (!d) { RET(kBadArg); return; }
    const uint64_t md = A(1);
    const uint64_t w = prop_int(c, md, "width"), h = prop_int(c, md, "height");
    if (w && h) { d->w = static_cast<uint32_t>(w); d->h = static_cast<uint32_t>(h); }
    if (g_log) NXLOG_I(kTag, "Decoder: Configure %ux%u", d->w, d->h);
    RET(0);
}

void dec_register_events(::Ctx* c) {
    HostDecoder* d = dec_of(A(0));
    if (d && A(1) && mem::is_mapped(A(1), 32)) {
        for (int i = 0; i < 4; ++i) d->ev[i] = rd64(A(1) + static_cast<uint64_t>(i) * 8);
    }
    if (g_log) NXLOG_I(kTag, "Decoder: client events registered");
    RET(0);
}

void dec_start(::Ctx* c) {
    HostDecoder* d = dec_of(A(0));
    if (!d) { RET(kBadArg); return; }
    std::lock_guard<std::mutex> lk(d->mu);
    d->started = true;
#if NXRT_HAVE_DAV1D
    if (!d->av1 && d->type == 3) {   // DecoderType 3: AV1 in this SDK's numbering
        dav1d_default_settings(&d->cfg);
        d->cfg.n_threads = 4;
        if (dav1d_open(&d->av1, &d->cfg) < 0) { d->av1 = nullptr; d->errors++; }
    }
#endif
    if (g_log) NXLOG_I(kTag, "Decoder: Start (%s)", d->av1 ? "AV1 on dav1d" : "no AV1 decoder");
    RET(0);
}
void dec_stop(::Ctx* c) {
    HostDecoder* d = dec_of(A(0));
    if (d) { std::lock_guard<std::mutex> lk(d->mu); d->started = false; }
    RET(0);
}

void dec_reset(::Ctx* c) {
    HostDecoder* d = dec_of(A(0));
    if (d) {
        std::lock_guard<std::mutex> lk(d->mu);
        d->out.clear();
        for (auto& f : d->held) f.reset();
        for (auto& s : d->in) s.busy = false;
    }
    RET(0);
}

void dec_flush(::Ctx* c) { dec_reset(c); }

// AcquireInputBufferIndex(int* index, int* something): a free slot, or the SDK's "no input".
void dec_acquire_input(::Ctx* c) {
    HostDecoder* d = dec_of(A(0));
    if (!d) { RET(kBadArg); return; }
    std::lock_guard<std::mutex> lk(d->mu);
    for (size_t i = 0; i < kInSlots; ++i) {
        if (d->in[i].busy) continue;
        if (d->in[i].data.empty()) d->in[i].data.resize(kInCap);
        d->in[i].busy = true;
        d->in[i].time = 0;
        d->in[i].flags = 0;
        if (A(1)) wr64(A(1), i);
        RET(0);
    }
    fire(c, *d, 0);   // input available when a slot comes back
    RET(kNoInput);
}

// GetInputBuffer(int index, movie::Buffer*): point the client's buffer at the slot's memory so it writes the packet there.
void dec_get_input(::Ctx* c) {
    HostDecoder* d = dec_of(A(0));
    const int idx = static_cast<int>(A(1));
    const uint64_t buf = A(2);
    if (!d || idx < 0 || idx >= static_cast<int>(kInSlots) || !buf) { RET(kBadArg); return; }
    std::lock_guard<std::mutex> lk(d->mu);
    Slot& s = d->in[static_cast<size_t>(idx)];
    if (s.data.empty()) s.data.resize(kInCap);
    wr64(buf + kBufData, reinterpret_cast<uint64_t>(s.data.data()));
    wr64(buf + kBufSize, s.data.size());
    RET(0);
}

// SendInputBufferForDecode(int index, int, int, long time, unsigned flags)
void dec_send_input(::Ctx* c) {
    HostDecoder* d = dec_of(A(0));
    const int idx = static_cast<int>(A(1));
    const int64_t time = static_cast<int64_t>(A(4));
    const uint32_t flags = static_cast<uint32_t>(A(5));
    if (!d || idx < 0 || idx >= static_cast<int>(kInSlots)) { RET(kBadArg); return; }
    std::unique_lock<std::mutex> lk(d->mu);
    Slot& s = d->in[static_cast<size_t>(idx)];
    const size_t bytes = s.data.size() < kInCap ? s.data.size() : kInCap;
    ++d->packets;
    if (g_log && d->packets < 20) NXLOG_I(kTag, "Decoder: packet %llu, %zu bytes, time %lld, flags %u", static_cast<unsigned long long>(d->packets), bytes,
                                        static_cast<long long>(time), flags);
#if NXRT_HAVE_DAV1D
    if (d->av1 && bytes) {
        Dav1dData in{};
        uint8_t* p = dav1d_data_create(&in, bytes);
        if (p) {
            std::memcpy(p, s.data.data(), bytes);
            in.m.timestamp = time;
            const int r = dav1d_send_data(d->av1, &in);
            if (r < 0 && r != DAV1D_ERR(EAGAIN)) ++d->errors;
            Dav1dPicture pic{};
            while (dav1d_get_picture(d->av1, &pic) == 0) {
                auto f = std::make_unique<Frame>();
                to_nv12(pic, *f);
                f->time = time;
                d->w = f->w; d->h = f->h;
                dav1d_picture_unref(&pic);
                d->out.push_back(std::move(f));
                ++d->pictures;
            }
        }
    }
#endif
    s.busy = false;
    const bool have_out = !d->out.empty();
    lk.unlock();
    fire(c, *d, 0);   // input available again
    if (have_out) fire(c, *d, 1);   // a picture is ready
    RET(0);
}

// AcquireOutputBufferIndex(int* index, long* time, unsigned* flags, int* remaining)
void dec_acquire_output(::Ctx* c) {
    HostDecoder* d = dec_of(A(0));
    if (!d) { RET(kBadArg); return; }
    std::unique_lock<std::mutex> lk(d->mu);
    if (d->out.empty()) { RET(kNoOutput); }
    int slot = -1;
    for (size_t i = 0; i < kOutSlots; ++i)
        if (!d->held[i]) { slot = static_cast<int>(i); break; }
    if (slot < 0) { RET(kNoOutput); }
    d->held[static_cast<size_t>(slot)] = std::move(d->out.front());
    d->out.pop_front();
    const int64_t time = d->held[static_cast<size_t>(slot)]->time;
    const int remaining = static_cast<int>(d->out.size());
    lk.unlock();
    if (A(1)) wr64(A(1), static_cast<uint64_t>(slot));
    if (A(2)) wr64(A(2), static_cast<uint64_t>(time));
    if (A(3)) wr32(A(3), 0);
    if (A(4)) wr32(A(4), static_cast<uint32_t>(remaining));
    RET(0);
}

// GetOutputBuffer(int index, movie::Buffer* out, MediaData* format)
void dec_get_output(::Ctx* c) {
    HostDecoder* d = dec_of(A(0));
    const int idx = static_cast<int>(A(1));
    const uint64_t buf = A(2);
    if (!d || idx < 0 || idx >= static_cast<int>(kOutSlots) || !buf) { RET(kBadArg); return; }
    std::lock_guard<std::mutex> lk(d->mu);
    auto& f = d->held[static_cast<size_t>(idx)];
    if (!f) { RET(kNoOutput); return; }
    const uint64_t dst = rd64(buf + kBufData), cap = rd64(buf + kBufSize);
    const size_t bytes = std::min<size_t>(f->nv12.size(), static_cast<size_t>(cap));
    if (dst && bytes) std::memcpy(reinterpret_cast<void*>(dst), f->nv12.data(), bytes);
    wr64(buf + kBufFilled, bytes);
    wr64(buf + kBufTime, static_cast<uint64_t>(f->time));
    RET(0);
}

// GetOutputBufferFormat(int index, MediaData*): what the client reads to size its frames.
void dec_output_format(::Ctx* c) {
    HostDecoder* d = dec_of(A(0));
    const uint64_t md = A(2);
    if (!d || !md || !d->w) { RET(kBadArg); return; }
    const uint64_t set = module_find_symbol("_ZN2nn5movie9MediaData8SetInt32EPKci");
    const uint64_t setsize = module_find_symbol("_ZN2nn5movie9MediaData7SetSizeEPKcm");
    if (set) {
        gcall(c, set, md, reinterpret_cast<uint64_t>("width"), d->w);
        gcall(c, set, md, reinterpret_cast<uint64_t>("height"), d->h);
    }
    if (setsize) gcall(c, setsize, md, reinterpret_cast<uint64_t>("output-buf-size"), static_cast<uint64_t>(d->w) * d->h * 3 / 2);
    RET(0);
}

void dec_output_size(::Ctx* c) {
    HostDecoder* d = dec_of(A(0));
    if (!d) { RET(kBadArg); return; }
    if (A(1)) wr64(A(1), static_cast<uint64_t>(d->w) * d->h * 3 / 2);
    if (A(2)) wr64(A(2), 0);
    RET(0);
}

void dec_last_error(::Ctx* c) { RET(0); }

struct Addr { uint64_t off; HleFn fn; const char* name; };
const Addr kAddrs[] = {
    {0x002de630ull, dec_ctor, "Decoder::Decoder"},
    {0x002de728ull, dec_configure, "Decoder::Configure"},
    {0x002de73cull, dec_register_events, "Decoder::RegisterClientEvents"},
    {0x002de750ull, dec_start, "Decoder::Start"},
    {0x002de818ull, dec_acquire_input, "Decoder::AcquireInputBufferIndex"},
    {0x002de82cull, dec_get_input, "Decoder::GetInputBuffer"},
    {0x002de854ull, dec_get_output, "Decoder::GetOutputBuffer"},
    {0x002de868ull, dec_output_format, "Decoder::GetOutputBufferFormat"},
    {0x002de840ull, dec_last_error, "Decoder::GetLastError"},
};

}  // namespace

bool install_movie_decoder_layer() {
    static std::once_flag once;
    static bool ok = false;
    std::call_once(once, [] {
        g_log = config_get_bool("media", "video_decoder_log", false);
        for (const Addr& a : kAddrs) fn_register(kSubsdk0 + a.off, a.fn);
        ok = true;
        NXLOG_I(kTag, "movie::Decoder on the host: %zu entry points (%s)", sizeof kAddrs / sizeof kAddrs[0],
                "[media] video_decoder = library");
    });
    return ok;
}

}  // namespace nxrt::media