// SPDX-License-Identifier: GPL-3.0-or-later
// nn::codec hardware video decoders (VP9, VP8) + their fences on the host, decoding with libvpx. See include/nxrt/video_codec.h.
//
// Calling conventions, read off Pokopia's subsdk0 (movie::detail::*, which forwards its registers unchanged to nn::codec) and off the
// mangled names (Mario Kart World's variants differ where noted):
//   MakeDecodeImagePreference(u16 w, u16 h, OutputFormat, CodecMode) -> 64-byte VideoDecoderImagePreference returned through x8
//   CalculateDecoderImagePoolBuffer(size_t* size, size_t* align, const Preference*, u32 count)
//   InitializeDecoderImagePool(Pool*, void* mem, size_t, const Preference*, u32 count, CodecMode)    Pool = 32 bytes
//   ReadDecoderOutputImageNv12(const Pool*, u32 image, u16 x, u16 y, u16 w, u16 h, void* y, size_t y_stride, [sp] size_t y_size,
//                              [sp+8] void* uv, [sp+16] size_t uv_stride, [sp+24] size_t uv_size)
//   ReadDecoderOutputImageRgba(const Pool*, u32 image, u16 x, u16 y, u16 w, u16 h, void* dst, size_t stride, [sp] size_t size)
//   CalculateVp9DecoderWorkBuffer(size_t* size, size_t* align, size_t, u16 w, u16 h)
//   InitializeVp9Decoder(Vp9DecoderType*, void* work, size_t, size_t, u16, u16, u32, InputFormat, [sp] OutputFormat)   (transfer memory)
//   InitializeVp9Decoder(Vp9DecoderType*, size_t, u16, u16, u32, InputFormat, OutputFormat)   (remote memory; MKW: an extra size_t)
//   RegisterVp9DecoderBuffer(Vp9DecoderType*, u32 index, Pool*, u32)
//   GetVp9DecoderSubmissionReadyEvent(os::SystemEventType** out, Vp9DecoderType*)
//   SubmitVp9DecoderInputBuffer(u64* out, Vp9DecoderType*, const void* data, size_t size, TimeSpan pts, bool end_of_stream)
//   AcquireVp9DecoderOutputBuffer(u32* index, gs::NativeSyncHandle* fence, Vp9DecoderType*)
//   ReleaseVp9DecoderOutputBuffer(Vp9DecoderType*, u32 index, gs::NativeSyncHandle pre_fence (x2, x3))
//   GetVp9DecoderOutputBufferProperties(u16* w, u16* h, u16*, u16*, TimeSpan* pts, bool* eos, Vp9DecoderType*, u32 index)
//     (MKW: a movie::ColorSpace* after the four u16*, so the decoder is x7 and the index on the stack)
//   nn::syncpt::sdk::{Create,Destroy,Cancel}SyncPointEvent(SyncPointEventType*), RequestSyncPointEvent(evt, const SyncPointHandle&),
//     InitializeMultiWaitHolder(os::MultiWaitHolderType*, evt), TryWaitSyncPointEvent(const evt*); nn::gs::TryWaitNativeSync(const handle&)
// Every nn::codec call the player makes is checked (a non-zero nn::Result aborts), so these answer 0 unless noted.
//
// Guest objects keep {host pointer, marker} in their first 16 bytes. A SyncPointEventType (128 bytes in the player's event manager) holds a
// guest os::EventType at +0 (40 bytes) that the guest's own MultiWait waits on; a fence handle is {kSyncMarker | decoder id, sequence}.
// Fences of a decoder complete in sequence order, so "done" is sequence <= the decoder's last completed sequence; any handle that is not
// one of ours counts as reached (nxrt has no GPU syncpoints: NVN runs on the host).
#include <windows.h>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <deque>
#include <map>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#include "nxrt/abi.h"
#include "nxrt/config.h"
#include "nxrt/dispatch.h"
#include "nxrt/game.h"
#include "nxrt/gauge.h"
#include "nxrt/log.h"
#include "nxrt/module.h"
#include "nxrt/video_codec.h"
#include "video_nvdec.h"
#include "video_ffmpeg.h"

#if NXRT_HAVE_LIBVPX
#include <vpx/vp8dx.h>
#include <vpx/vpx_decoder.h>
#endif

#if NXRT_HAVE_DAV1D
#include <dav1d/dav1d.h>
#endif

namespace nxrt::media {

#if NXRT_HAVE_LIBVPX
namespace {

#define A(i) (c->x[i])
#define RET(v) (c->x[0] = static_cast<uint64_t>(v))

constexpr uint64_t kDecMarker = 0x4e58524356444543ull;    // "NXRCVDEC"
constexpr uint64_t kPoolMarker = 0x4e585243504f4f4cull;   // "NXRCPOOL"
constexpr uint64_t kPrefMarker = 0x4e58524350524546ull;   // "NXRCPREF"
constexpr uint64_t kEvtMarker = 0x4e58524353594e43ull;    // "NXRCSYNC" at +0x60 of a SyncPointEventType
constexpr uint64_t kSyncMarker = 0x4e58435600000000ull;   // "NXCV" in the high half of a fence handle's first word
constexpr uint32_t kManualClear = 0;                      // nn::os::EventClearMode_ManualClear
constexpr size_t kAhead = 4;        // pictures the worker may keep decoded ahead of the player (4 x 12 MB)
constexpr size_t kPendingMax = 8192;   // packets queued undecoded (~500 MB of AV1 for a film, well past the 2810 of this one). Submits
                                      // only copy; the worker decodes ahead. The queue was 8 for a while and every submit then decoded
                                      // one packet inline (23 ms) on the player's thread, which starved it (frames 60-90 ms late).
constexpr size_t kBacklog = 1;   // decoded pictures waiting for a buffer before input stops being "ready". 3 let the movie library's
                                 // adapter submit ~10 packets per frame, and every Submit decodes 4K AV1 inline on the player's own thread:
                                 // the frame loop fell ~180 ms behind and dropped every frame but the first (GetBuffer once, 2026-11-18).

bool g_log = false;
int g_threads = 4;
thread_local bool t_on_worker = false;   // the decode worker: the only thread allowed to take a hardware decoder
bool g_hwdec = true;   // [media] hwdec: NVDEC for VP8/VP9/AV1 when the GPU is an NVIDIA one (video_nvdec.cpp)
std::atomic<bool> g_enabled{false};
std::atomic<uint64_t> s_created{0}, s_destroyed{0}, s_packets{0}, s_decoded{0}, s_delivered{0}, s_read{0}, s_errors{0};
std::mutex g_err_mu;
std::string g_first_error;   // the first decode error, kept for the stats line

// Records an error: the first one is logged at Error level and kept, later ones only counted (the stats line shows the total).
void note_error(const char* fmt, ...) {
    s_errors++;
    char buf[320];
    va_list ap;
    va_start(ap, fmt);
    std::vsnprintf(buf, sizeof buf, fmt, ap);
    va_end(ap);
    std::lock_guard<std::mutex> lk(g_err_mu);
    if (!g_first_error.empty()) return;
    g_first_error = buf;
    NXLOG_E("vcodec", "first error: %s", buf);
}

// Decode stats, at most every 5 s and only when something moved: packets in, pictures out of libvpx, pictures placed in the player's
// output buffers (fences signalled), pictures the game read back (ReadDecoderOutputImage*), errors.
void stats_tick() {
    static std::atomic<int64_t> last_ns{0};
    static std::atomic<uint64_t> last_sum{0};
    const int64_t now = std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();
    int64_t prev = last_ns.load(std::memory_order_relaxed);
    if (prev && now - prev < 5'000'000'000ll) return;
    const uint64_t sum = s_packets + s_decoded + s_delivered + s_read + s_errors;
    if (sum == last_sum.load(std::memory_order_relaxed)) return;
    if (!last_ns.compare_exchange_strong(prev, now)) return;
    last_sum = sum;
    std::string first;
    {
        std::lock_guard<std::mutex> lk(g_err_mu);
        first = g_first_error;
    }
    NXLOG_I("vcodec", "stats: decoders %llu/%llu live, packets %llu, decoded %llu, placed in output buffers %llu, read by the game %llu, errors %llu%s%s",
            (unsigned long long)(s_created - s_destroyed), (unsigned long long)s_created.load(), (unsigned long long)s_packets.load(),
            (unsigned long long)s_decoded.load(), (unsigned long long)s_delivered.load(), (unsigned long long)s_read.load(),
            (unsigned long long)s_errors.load(), first.empty() ? "" : " (first: ", first.empty() ? "" : (first + ")").c_str());
}

inline uint64_t rd64(uint64_t a) { uint64_t v; std::memcpy(&v, reinterpret_cast<const void*>(a), 8); return v; }
inline void wr64(uint64_t a, uint64_t v) { std::memcpy(reinterpret_cast<void*>(a), &v, 8); }
inline void wr32(uint64_t a, uint32_t v) { std::memcpy(reinterpret_cast<void*>(a), &v, 4); }
inline void wr16(uint64_t a, uint16_t v) { std::memcpy(reinterpret_cast<void*>(a), &v, 2); }

// ---- guest calls ------------------------------------------------------------------------------------------------------------------
// Calls a guest function from inside a handler (on the guest thread that called the import); returns x0.
uint64_t gcall(::Ctx* c, uint64_t fn, uint64_t a0, uint64_t a1 = 0, uint64_t a2 = 0, uint64_t a3 = 0) {
    if (!fn) return 0;
    uint64_t save[9];
    std::memcpy(save, c->x, sizeof save);
    const uint64_t lr = c->x[30], f = c->fn;
    c->x[0] = a0; c->x[1] = a1; c->x[2] = a2; c->x[3] = a3;
    dispatch_call(c, fn);
    const uint64_t r = c->x[0];
    std::memcpy(c->x, save, sizeof save);
    c->x[30] = lr;
    c->fn = f;
    return r;
}
struct OsFns {
    uint64_t init_event, signal_event, clear_event, finalize_event, trywait_event, init_holder_event;
    uint64_t create_sysevent, signal_sysevent, destroy_sysevent;
};
const OsFns& os() {
    static const OsFns f = [] {
        OsFns o{};
        o.init_event = module_find_symbol("_ZN2nn2os15InitializeEventEPNS0_9EventTypeEbNS0_14EventClearModeE");
        o.signal_event = module_find_symbol("_ZN2nn2os11SignalEventEPNS0_9EventTypeE");
        o.clear_event = module_find_symbol("_ZN2nn2os10ClearEventEPNS0_9EventTypeE");
        o.finalize_event = module_find_symbol("_ZN2nn2os13FinalizeEventEPNS0_9EventTypeE");
        o.trywait_event = module_find_symbol("_ZN2nn2os12TryWaitEventEPNS0_9EventTypeE");
        o.init_holder_event = module_find_symbol("_ZN2nn2os25InitializeMultiWaitHolderEPNS0_19MultiWaitHolderTypeEPNS0_9EventTypeE");
        o.create_sysevent = module_find_symbol("_ZN2nn2os17CreateSystemEventEPNS0_15SystemEventTypeENS0_14EventClearModeEb");
        o.signal_sysevent = module_find_symbol("_ZN2nn2os17SignalSystemEventEPNS0_15SystemEventTypeE");
        o.destroy_sysevent = module_find_symbol("_ZN2nn2os18DestroySystemEventEPNS0_15SystemEventTypeE");
        if (!o.init_event || !o.signal_event || !o.clear_event || !o.init_holder_event || !o.create_sysevent || !o.signal_sysevent)
            NXLOG_E("vcodec", "guest nn::os event functions missing: fences and input events will not work");
        return o;
    }();
    return f;
}

// ---- image pools --------------------------------------------------------------------------------------------------------------------
struct Pool {
    uint16_t w = 0, h = 0;      // the image size the pool was made for (even)
    uint32_t format = 0;        // nn::codec VideoDecoderOutputFormat (2 RGBA, 3/6 NV12 as the player reads it)
    std::vector<uint8_t> nv12;  // the picture last placed in it, w*h luma + w*h/2 interleaved chroma
};
Pool* pool_of(uint64_t g) { return g && rd64(g + 8) == kPoolMarker ? reinterpret_cast<Pool*>(rd64(g)) : nullptr; }

// ---- decoders -----------------------------------------------------------------------------------------------------------------------
struct Picture {
    std::vector<uint8_t> nv12;
    uint16_t w = 0, h = 0;
    int64_t pts = 0;
    bool eos = false;
};
struct BufInfo {
    uint16_t w = 0, h = 0;
    int64_t pts = 0;
    bool eos = false;
};
// A submitted packet waiting for its turn to be decoded. The movie library's adapter thread submits four packets back to back
// (its own input buffers) and then services the player; with the decode inside Submit* that thread spent all its time decoding
// 4K AV1 (~26 ms a packet), the player's frames arrived ~85 ms late and its pacing dropped every frame but the first
// (GetBuffer once, 2026-11-18). Submits only queue now; one packet is decoded when the player needs a picture.
struct Pending {
    std::vector<uint8_t> data;
    int64_t pts = 0;
    bool eos = false;
};
struct Decoder {
    ~Decoder();
    // NVDEC: the GPU's own decoder when the GPU is NVIDIA (video_nvdec.cpp). Null while the CPU path decodes or when the
    // hardware path is off or unavailable; every failure falls back to libvpx/dav1d for the rest of the stream.
    NvDec* nv = nullptr;
    bool nv_tried = false;
    FfDec* ff = nullptr;      // FFmpeg's libavcodec + D3D11VA: the path the emulators use
    bool ff_tried = false;
    uint32_t id = 0;
    int codec = 9;   // 8 VP8, 9 VP9, 10 AV1 (dav1d; the SDK 3.0.1 movie library decodes AV1)
    std::mutex mu;
    vpx_codec_ctx_t vpx{};
    bool vpx_ok = false;
#if NXRT_HAVE_DAV1D
    Dav1dContext* av1 = nullptr;
#endif
    std::map<uint32_t, uint64_t> pools;                   // buffer index -> guest pool
    std::map<uint32_t, BufInfo> info;                     // buffer index -> picture properties
    std::deque<uint32_t> free;                            // registered or released, not acquired
    std::deque<std::pair<uint32_t, uint64_t>> waiting;    // acquired buffers without a picture yet (index, fence sequence)
    std::deque<Picture> ready;                            // decoded pictures without a buffer yet
    std::deque<Pending> pending;                          // submitted packets not decoded yet (input order)
    // What the first frame of a film costs, in the log: the moment the first packet arrived and the moment a picture
    // came out. The gap is what used to show up as a 213 ms frame at the start of a cutscene (0.1.4, RTX 5080).
    std::chrono::steady_clock::time_point t_first_packet{};
    long long first_picture_ms = -1;
    std::mutex dec_mu;                                    // the codec context and last picture: the worker decodes, the guest may fall back
    std::thread worker;                                   // decodes pending packets ahead of the player, off its thread
    std::atomic<uint32_t> completed_early{0};             // acquires that completed their fence with no picture to pair (a film's first acquire)
    std::condition_variable cv;
    bool stop = false;
    bool worker_started = false;
    uint64_t next_seq = 1;
    std::atomic<uint64_t> done_seq{0};
    alignas(16) uint8_t submit_event[0x100]{};            // the guest os::SystemEventType handed out as "submission ready"
    bool submit_event_made = false;
    bool want_submit_signal = false;
    bool started = false;                                 // between Start*Decoder and Stop*Decoder: only then is input "ready"
    std::vector<uint8_t> last;                            // last decoded picture (NV12) for the end-of-stream buffer
    uint16_t last_w = 0, last_h = 0;
    uint64_t pictures = 0;
};

void worker_loop(Decoder& d);   // decodes pending packets ahead of the player (defined with the codec handlers below)

std::mutex g_reg_mu;
std::map<uint32_t, std::shared_ptr<Decoder>> g_decoders;
uint32_t g_next_id = 1;

std::shared_ptr<Decoder> dec_of(uint64_t g) {
    if (!g || rd64(g + 8) != kDecMarker) return nullptr;
    const uint32_t id = static_cast<uint32_t>(rd64(g));
    std::lock_guard<std::mutex> lk(g_reg_mu);
    auto it = g_decoders.find(id);
    return it == g_decoders.end() ? nullptr : it->second;
}
bool fence_done(uint64_t w0, uint64_t seq) {
    if ((w0 & 0xffffffff00000000ull) != kSyncMarker) return true;   // not a decoder fence: reached
    std::lock_guard<std::mutex> lk(g_reg_mu);
    auto it = g_decoders.find(static_cast<uint32_t>(w0));
    return it == g_decoders.end() || it->second->done_seq.load() >= seq;
}

bool vpx_open(Decoder& d) {
    vpx_codec_dec_cfg_t cfg{};
    cfg.threads = static_cast<unsigned>(g_threads);
    const vpx_codec_err_t e = vpx_codec_dec_init(&d.vpx, d.codec == 8 ? vpx_codec_vp8_dx() : vpx_codec_vp9_dx(), &cfg, 0);
    d.vpx_ok = e == VPX_CODEC_OK;
    if (!d.vpx_ok) note_error("decoder %u: vpx_codec_dec_init failed: %s", d.id, vpx_codec_err_to_string(e));
    return d.vpx_ok;
}
void vpx_close(Decoder& d) {
    if (d.vpx_ok) vpx_codec_destroy(&d.vpx);
    d.vpx_ok = false;
}
#if NXRT_HAVE_DAV1D
void av1_close(Decoder& d) {
    if (d.av1) dav1d_close(&d.av1);
    d.av1 = nullptr;
}
// Opens dav1d for the codec 10 decoders. max_frame_delay 1: one packet in, one picture out, which is the shape nn::codec's
// Submit/Acquire pair has (the movie library acquires an output buffer per submitted packet).
bool av1_open(Decoder& d) {
    Dav1dSettings s;
    dav1d_default_settings(&s);
    s.n_threads = g_threads;
    s.max_frame_delay = 1;
    if (dav1d_open(&d.av1, &s) < 0) {
        d.av1 = nullptr;
        note_error("decoder %u: dav1d failed to start", d.id);
        return false;
    }
    if (d.codec == 10 && d.pictures == 0) NXLOG_I("vcodec", "decoder %u: AV1 on dav1d %s (%d threads)", d.id, dav1d_version(), g_threads);
    return true;
}
#endif

// ---- sync point events ----------------------------------------------------------------------------------------------------------
struct Armed {
    uint32_t dec = 0;
    uint64_t seq = 0;
};
std::mutex g_evt_mu;
std::map<uint64_t, Armed> g_armed;   // guest SyncPointEventType -> the fence it waits for

// After a decoder completed fences: the armed events whose fence is now reached (disarmed; the caller signals them).
std::vector<uint64_t> take_reached(uint32_t dec, uint64_t done) {
    std::vector<uint64_t> out;
    std::lock_guard<std::mutex> lk(g_evt_mu);
    for (auto it = g_armed.begin(); it != g_armed.end();) {
        if (it->second.dec == dec && it->second.seq <= done) {
            out.push_back(it->first);
            it = g_armed.erase(it);
        } else {
            ++it;
        }
    }
    return out;
}

// ---- picture conversion -----------------------------------------------------------------------------------------------------------
Picture to_nv12(const vpx_image_t* img, int64_t pts) {
    Picture p;
    p.w = static_cast<uint16_t>((img->d_w + 1) & ~1u);
    p.h = static_cast<uint16_t>((img->d_h + 1) & ~1u);
    p.pts = pts;
    const size_t w = p.w, h = p.h;
    p.nv12.assign(w * h + w * h / 2, 0);
    for (size_t y = 0; y < img->d_h; y++) std::memcpy(&p.nv12[y * w], img->planes[0] + y * img->stride[0], img->d_w);
    uint8_t* uv = p.nv12.data() + w * h;
    const size_t cw = (img->d_w + 1) / 2, ch = (img->d_h + 1) / 2;
    for (size_t y = 0; y < ch; y++) {
        const uint8_t* u = img->planes[1] + y * img->stride[1];
        const uint8_t* v = img->planes[2] + y * img->stride[2];
        uint8_t* o = uv + y * w;
        for (size_t x = 0; x < cw; x++) {
            o[2 * x] = u[x];
            o[2 * x + 1] = v[x];
        }
    }
    return p;
}

// Copies `p` into the pool's image. The picture decides the pool's size: the preference the library computed is not needed for
// the copy, and the frame properties reported to it come from the same picture, so a stale or rounded preference cannot crop it.
void place(Pool& pool, const Picture& p) {
    pool.w = p.w;
    pool.h = p.h;
    const size_t pw = pool.w, ph = pool.h;
    pool.nv12.assign(pw * ph + pw * ph / 2, 0);
    std::memset(pool.nv12.data(), 16, pw * ph);
    std::memset(pool.nv12.data() + pw * ph, 128, pw * ph / 2);
    if (p.nv12.empty()) return;
    const size_t cw = std::min<size_t>(pw, p.w), chh = std::min<size_t>(ph, p.h);
    for (size_t y = 0; y < chh; y++) std::memcpy(&pool.nv12[y * pw], &p.nv12[y * p.w], cw);
    for (size_t y = 0; y < chh / 2; y++) std::memcpy(&pool.nv12[pw * ph + y * pw], &p.nv12[size_t(p.w) * p.h + y * p.w], cw);
}

// Pairs decoded pictures with acquired buffers (both first in first out). Caller holds d.mu. Returns true when a fence completed.
bool assign(Decoder& d) {
    bool any = false;
    while (!d.waiting.empty() && !d.ready.empty()) {
        const auto [index, seq] = d.waiting.front();
        d.waiting.pop_front();
        Picture p = std::move(d.ready.front());
        d.ready.pop_front();
        auto it = d.pools.find(index);
        if (Pool* pool = it == d.pools.end() ? nullptr : pool_of(it->second)) place(*pool, p);
        else note_error("decoder %u: buffer %u has no image pool", d.id, index);
        d.info[index] = BufInfo{p.w, p.h, p.pts, p.eos};
        d.done_seq.store(seq);
        any = true;
        s_delivered++;
    }
    return any;
}

// Signals what a decoder state change made due: reached fences, and "submission ready" when the backlog went down. No locks held.
void after_change(::Ctx* c, Decoder& d, bool fences) {
    stats_tick();
    if (fences)
        for (uint64_t evt : take_reached(d.id, d.done_seq.load())) gcall(c, os().signal_event, evt);
    bool signal = false;
    {
        std::lock_guard<std::mutex> lk(d.mu);
        if (d.submit_event_made && d.started && d.ready.size() < kBacklog) {
            signal = d.want_submit_signal;
            d.want_submit_signal = false;
        }
    }
    if (signal) gcall(c, os().signal_sysevent, reinterpret_cast<uint64_t>(d.submit_event));
}

void decode_into(Decoder& d, const uint8_t* data, size_t size, int64_t pts, std::vector<Picture>& out) {
    // [media] hwdec (default on): let the GPU's decoder do VP8/VP9/AV1 when it is an NVIDIA one. It decodes 4K AV1 far
    // faster than dav1d on the CPU, which is what the DLC openings need to play in real time (2026-11-20).
    // Hardware decoding only on the worker thread: a decode in the player's own submit call blocks the player - the
    // 2026-11-18 finding of the dav1d path (52, 155.3) - and the picture then never advances (one frame, then frozen).
    // FFmpeg is used from the worker and from the player's own fallback alike: one decoder per stream. Feeding the same
    // packets to dav1d as well left two decoder states and the picture stopped after a few frames (2026-11-20).
    // Whoever decodes creates the one hardware decoder for this stream, worker or not: a submit only queues, and the one
    // place outside the worker that decodes is Acquire, when the worker is late. Letting that path fall through to dav1d
    // opened a SECOND decoder in the middle of the stream - dav1d cannot start from a non-keyframe, answered -22, and the
    // cutscene came out in blocky garbage (0.1.4 on the 6800 XT, 2026-11-21; the blocks lasted until the worker's decoder
    // took over). Creation runs under dec_mu, which serialises it against the worker.
    if (g_hwdec && data && size && (!d.ff_tried || d.ff)) {
        // No lock of d.mu here: decode_one already runs the decode under dec_mu, and the submit path holds d.mu. Taking both
        // in the other order deadlocked on the first frame (2026-11-21).
        if (!d.ff && !d.ff_tried) {
            d.ff_tried = true;
            std::string why;
            d.ff = ffdec_create(d.codec, &why);
            if (d.ff) NXLOG_I("vcodec", "decoder %u: %s on FFmpeg hardware (%s)", d.id, d.codec == 10 ? "AV1" : d.codec == 9 ? "VP9" : "VP8",
                              ffdec_hw_name());
            else NXLOG_I("vcodec", "decoder %u: no FFmpeg hardware decoder (%s)", d.id, why.c_str());
        }
        if (d.ff) {
            std::vector<FfDecPicture> pics;
            if (ffdec_decode(d.ff, data, size, pts, &pics)) {
                for (FfDecPicture& q : pics) {
                    Picture pic;
                    pic.w = static_cast<uint16_t>(q.w);
                    pic.h = static_cast<uint16_t>(q.h);
                    pic.pts = q.pts;
                    pic.nv12 = std::move(q.nv12);
                    out.push_back(std::move(pic));
                }
                return;
            }
            NXLOG_W("vcodec", "decoder %u: FFmpeg hardware decode failed; falling back", d.id);
            ffdec_destroy(d.ff);
            d.ff = nullptr;
        }
    }
    if (g_hwdec && t_on_worker && data && size) {
        if (!d.nv && !d.nv_tried) {
            d.nv_tried = true;
            std::string why;
            d.nv = nvdec_create(d.codec, 0, 0, &why);
            if (d.nv) NXLOG_I("vcodec", "decoder %u: %s on NVDEC (hardware)", d.id, d.codec == 10 ? "AV1" : d.codec == 9 ? "VP9" : "VP8");
            else NXLOG_I("vcodec", "decoder %u: no NVDEC (%s); the CPU decodes", d.id, why.c_str());
        }
        if (d.nv) {
            std::vector<NvDecPicture> pics;
            if (nvdec_decode(d.nv, data, size, pts, &pics)) {
                for (NvDecPicture& q : pics) {
                    Picture pic;
                    pic.w = static_cast<uint16_t>(q.w);
                    pic.h = static_cast<uint16_t>(q.h);
                    pic.pts = q.pts;
                    pic.nv12 = std::move(q.nv12);
                    out.push_back(std::move(pic));
                }
                return;
            }
            NXLOG_W("vcodec", "decoder %u: NVDEC failed; the CPU takes over for the rest of this stream", d.id);
            nvdec_destroy(d.nv);
            d.nv = nullptr;
        }
    }
#if NXRT_HAVE_DAV1D
    if (d.codec == 10) {   // AV1 (nn::codec's Av1DecoderType): the SDK 3.0.1 movie library's video path
        if (!data || !size) return;   // nothing to drain: max_frame_delay 1 gives a picture per packet
        if (!d.av1 && !av1_open(d)) return;
        Dav1dData in{};
        uint8_t* b = dav1d_data_create(&in, size);
        if (!b) { note_error("decoder %u: out of memory for a %zu-byte packet", d.id, size); return; }
        std::memcpy(b, data, size);
        in.m.timestamp = pts;
        for (int guard = 0; in.sz && guard < 64; ++guard) {
            const int r = dav1d_send_data(d.av1, &in);
            if (r < 0 && r != DAV1D_ERR(EAGAIN)) {
                note_error("decoder %u: dav1d_send_data(%zu bytes, pts %lld) failed: %d", d.id, size, static_cast<long long>(pts), r);
                break;
            }
            for (;;) {
                Dav1dPicture pic{};
                if (dav1d_get_picture(d.av1, &pic) < 0) break;
                if (pic.p.bpc == 8 && pic.p.layout == DAV1D_PIXEL_LAYOUT_I420) {
                    Picture p;
                    p.w = static_cast<uint16_t>((pic.p.w + 1) & ~1u);
                    p.h = static_cast<uint16_t>((pic.p.h + 1) & ~1u);
                    p.pts = pic.m.timestamp;
                    const size_t w = p.w, h = p.h;
                    p.nv12.assign(w * h + w * h / 2, 0);
                    const auto* py = static_cast<const uint8_t*>(pic.data[0]);
                    for (uint32_t y = 0; y < pic.p.h; y++) std::memcpy(&p.nv12[y * w], py + static_cast<size_t>(y) * pic.stride[0], pic.p.w);
                    uint8_t* uv = p.nv12.data() + w * h;
                    const uint32_t cw = (pic.p.w + 1) / 2, ch = (pic.p.h + 1) / 2;
                    const auto* pu = static_cast<const uint8_t*>(pic.data[1]);
                    const auto* pv = static_cast<const uint8_t*>(pic.data[2]);
                    for (uint32_t y = 0; y < ch; y++) {
                        uint8_t* o = uv + static_cast<size_t>(y) * w;
                        for (uint32_t x = 0; x < cw; x++) {
                            o[2 * x] = pu[static_cast<size_t>(y) * pic.stride[1] + x];
                            o[2 * x + 1] = pv[static_cast<size_t>(y) * pic.stride[1] + x];
                        }
                    }
                    if (d.pictures++ == 0) NXLOG_I("vcodec", "decoder %u: first picture %ux%u (AV1, dav1d %s, %d threads)", d.id, p.w, p.h, dav1d_version(), g_threads);
                    d.last = p.nv12;
                    d.last_w = p.w;
                    d.last_h = p.h;
                    out.push_back(std::move(p));
                    s_decoded++;
                } else {
                    note_error("decoder %u: AV1 picture %d bits, layout %d not handled (8-bit 4:2:0 only)", d.id, pic.p.bpc, static_cast<int>(pic.p.layout));
                }
                dav1d_picture_unref(&pic);
            }
        }
        if (in.sz) dav1d_data_unref(&in);
        return;
    }
#endif
    if (!d.vpx_ok && !vpx_open(d)) return;
    const vpx_codec_err_t e = vpx_codec_decode(&d.vpx, data, static_cast<unsigned>(size), nullptr, 0);
    if (e != VPX_CODEC_OK)
        note_error("decoder %u: vpx_codec_decode(%zu bytes, pts %lld) failed: %s (%s)", d.id, size, (long long)pts, vpx_codec_err_to_string(e),
                   vpx_codec_error_detail(&d.vpx) ? vpx_codec_error_detail(&d.vpx) : "");
    vpx_codec_iter_t it = nullptr;
    while (const vpx_image_t* img = vpx_codec_get_frame(&d.vpx, &it)) {
        if (img->fmt != VPX_IMG_FMT_I420) {
            note_error("decoder %u: picture format 0x%x not handled (8-bit 4:2:0 only)", d.id, img->fmt);
            continue;
        }
        Picture p = to_nv12(img, pts);
        if (d.pictures++ == 0) NXLOG_I("vcodec", "decoder %u: first picture %ux%u (VP%d, %d threads)", d.id, img->d_w, img->d_h, d.codec, g_threads);
        d.last = p.nv12;
        d.last_w = p.w;
        d.last_h = p.h;
        out.push_back(std::move(p));
        s_decoded++;
    }
}

// ---- nn::codec handlers -----------------------------------------------------------------------------------------------------------
void make_pref(::Ctx* c) {   // MakeDecodeImagePreference(w, h, format, mode) -> Preference via x8
    const uint64_t out = c->x[8];
    std::memset(reinterpret_cast<void*>(out), 0, 64);
    wr16(out + 0, static_cast<uint16_t>(A(0)));
    wr16(out + 2, static_cast<uint16_t>(A(1)));
    wr32(out + 4, static_cast<uint32_t>(A(2)));
    wr32(out + 8, static_cast<uint32_t>(A(3)));
    wr64(out + 16, kPrefMarker);
    RET(out);
}
void calc_pool(::Ctx* c) {   // CalculateDecoderImagePoolBuffer(size*, align*, pref*, count): the pictures live on the host
    const uint32_t n = std::max<uint32_t>(1, static_cast<uint32_t>(A(3)));
    if (A(0)) wr64(A(0), 0x1000ull * n);
    if (A(1)) wr64(A(1), 0x1000);
    RET(0);
}
void init_pool(::Ctx* c) {   // InitializeDecoderImagePool(pool, mem, size, pref*, count, mode)
    const uint64_t g = A(0), pref = A(3);
    Pool* p = new Pool();
    if (pref && rd64(pref + 16) == kPrefMarker) {
        std::memcpy(&p->w, reinterpret_cast<const void*>(pref), 2);
        std::memcpy(&p->h, reinterpret_cast<const void*>(pref + 2), 2);
        std::memcpy(&p->format, reinterpret_cast<const void*>(pref + 4), 4);
    }
    p->w = static_cast<uint16_t>((p->w + 1) & ~1);
    p->h = static_cast<uint16_t>((p->h + 1) & ~1);
    wr64(g, reinterpret_cast<uint64_t>(p));
    wr64(g + 8, kPoolMarker);
    // The library can read a pool image before the first picture is placed in it (the first acquire happens before any packet is
    // decoded). An all-zero image decodes as bright green, which flashed for the first seconds of the 4K CG (uv0=0 at read #1,
    // 127 from read #2). Start it as limited-range black instead.
    if (p->w && p->h) {
        const size_t n = static_cast<size_t>(p->w) * p->h;
        p->nv12.assign(n + n / 2, 128);
        std::memset(p->nv12.data(), 16, n);
    }
    if (g_log)
        NXLOG_I("vcodec", "InitializeDecoderImagePool %llx: %ux%u format %u (image %zu bytes, uv0 %u)", (unsigned long long)g, p->w, p->h,
                p->format, p->nv12.size(), p->nv12.size() > static_cast<size_t>(p->w) * p->h ? p->nv12[static_cast<size_t>(p->w) * p->h] : 999u);
    RET(0);
}
void fini_pool(::Ctx* c) {
    if (Pool* p = pool_of(A(0))) delete p;
    if (A(0)) { wr64(A(0), 0); wr64(A(0) + 8, 0); }
    RET(0);
}
std::atomic<int64_t> g_last_acquire_ns{0};
int64_t now_ns() { return std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count(); }
void read_nv12(::Ctx* c) {
    const int64_t t0 = now_ns();
    Pool* p = pool_of(A(0));
    const uint64_t sp = c->x[31];
    const uint32_t x0 = static_cast<uint16_t>(A(2)), y0 = static_cast<uint16_t>(A(3));
    const uint32_t w = static_cast<uint16_t>(A(4)), h = static_cast<uint16_t>(A(5));
    uint8_t* ydst = reinterpret_cast<uint8_t*>(A(6));
    const size_t ystride = A(7), ysize = rd64(sp);
    uint8_t* uvdst = reinterpret_cast<uint8_t*>(rd64(sp + 8));
    const size_t uvstride = rd64(sp + 16), uvsize = rd64(sp + 24);
    s_read++;
    stats_tick();
    // Every 150 reads a summary of the whole path: on the AMD machine the film sits on its first picture while the decoder
    // has long finished, and this says whether the player keeps reading (2026-11-21).
    if (g_log && (s_read % 150) == 0)
        NXLOG_I("vcodec", "read tick: %llu reads so far, pool image %zux%zu, y0 %u h %u, ystride %zu ysize %zu, uvsize %zu",
                static_cast<unsigned long long>(s_read.load()), p ? p->w : 0, p ? p->h : 0, y0, h, ystride, ysize, uvsize);
    if (g_log) {
        static std::atomic<uint32_t> n{0};
        if (n.fetch_add(1, std::memory_order_relaxed) < 6)
            NXLOG_I("vcodec", "ReadDecoderOutputImageNv12(index %u, %ux%u at %u,%u) pool %llx", static_cast<uint32_t>(A(1)), w, h, x0, y0,
                    (unsigned long long)A(0));
    }
    if (g_log) {
        static std::atomic<uint32_t> uv_n{0};
        if (uv_n.fetch_add(1, std::memory_order_relaxed) < 300) {
            const size_t pn = p && !p->nv12.empty() ? p->w * p->h : 0;
            NXLOG_I("vcodec", "read #%u: uvdst=0x%llx uvstride=%zu uvsize=%zu uv0=%u | pool 0x%llx %zux%zu image %zu uv0 %u",
                    uv_n.load(), (unsigned long long)uvdst, uvstride, uvsize, uvdst && uvsize > 2 ? static_cast<unsigned>(uvdst[0]) : 999u,
                    (unsigned long long)A(0), p ? p->w : 0, p ? p->h : 0, p ? p->nv12.size() : 0,
                    pn && p->nv12.size() > pn ? p->nv12[pn] : 999u);
        }
    }
    if (!p || p->nv12.empty() || !ydst) { RET(0); return; }
    const size_t pw = p->w, ph = p->h;
    const size_t cw = x0 < pw ? std::min<size_t>(w, pw - x0) : 0;
    for (size_t y = 0; y < h && y0 + y < ph; y++) {
        if ((y + 1) * ystride > ysize && y * ystride + cw > ysize) break;
        std::memcpy(ydst + y * ystride, &p->nv12[(y0 + y) * pw + x0], cw);
    }
    if (uvdst)
        for (size_t y = 0; y < h / 2 && y0 / 2 + y < ph / 2; y++) {
            if (y * uvstride + cw > uvsize) break;
            std::memcpy(uvdst + y * uvstride, &p->nv12[pw * ph + (y0 / 2 + y) * pw + (x0 & ~1u)], cw);
        }
    if (g_log) {
        static std::atomic<uint32_t> stat_n{0};
        if (stat_n.fetch_add(1, std::memory_order_relaxed) < 4 && p && !p->nv12.empty()) {
            const size_t pn = static_cast<size_t>(p->w) * p->h;
            uint64_t ysum = 0, uvsum = 0;
            size_t yn = 0, uvn = 0;
            for (size_t k = 0; k < pn; k += 4096) { ysum += p->nv12[k]; yn++; }
            for (size_t k = pn; k < p->nv12.size() && uvn < 4096; k += 4096) { uvsum += p->nv12[k]; uvn++; }
            NXLOG_I("vcodec", "pool image stats: Y avg %.1f (n=%zu), UV avg %.1f (n=%zu)", yn ? double(ysum) / yn : 0.0, yn,
                    uvn ? double(uvsum) / uvn : 0.0, uvn);
        }
        static std::atomic<uint32_t> n{0};
        const int64_t t1 = now_ns(), since = t0 - g_last_acquire_ns.load(std::memory_order_relaxed);
        if ((since > 40'000'000 || t1 - t0 > 10'000'000) && n.fetch_add(1, std::memory_order_relaxed) < 30)
            NXLOG_I("vcodec", "read timing: %.1f ms after acquire, copy took %.1f ms", since / 1e6, (t1 - t0) / 1e6);
    }
    RET(0);
}
inline uint8_t clamp8(int v) { return static_cast<uint8_t>(v < 0 ? 0 : v > 255 ? 255 : v); }
void read_rgba(::Ctx* c) {   // BT.709 limited range
    Pool* p = pool_of(A(0));
    const uint32_t x0 = static_cast<uint16_t>(A(2)), y0 = static_cast<uint16_t>(A(3));
    const uint32_t w = static_cast<uint16_t>(A(4)), h = static_cast<uint16_t>(A(5));
    uint8_t* dst = reinterpret_cast<uint8_t*>(A(6));
    const size_t stride = A(7), size = rd64(c->x[31]);
    s_read++;
    if (!p || p->nv12.empty() || !dst) { RET(0); return; }
    const size_t pw = p->w, ph = p->h;
    for (size_t y = 0; y < h && y0 + y < ph; y++) {
        if ((y + 1) * stride > size) break;
        uint8_t* o = dst + y * stride;
        const uint8_t* yr = &p->nv12[(y0 + y) * pw];
        const uint8_t* uvr = &p->nv12[pw * ph + ((y0 + y) / 2) * pw];
        for (size_t x = 0; x < w && x0 + x < pw; x++) {
            const size_t sx = x0 + x;
            const int Y = (yr[sx] - 16) * 298, U = uvr[sx & ~size_t(1)] - 128, V = uvr[(sx & ~size_t(1)) + 1] - 128;
            o[4 * x + 0] = clamp8((Y + 459 * V + 128) >> 8);
            o[4 * x + 1] = clamp8((Y - 55 * U - 136 * V + 128) >> 8);
            o[4 * x + 2] = clamp8((Y + 541 * U + 128) >> 8);
            o[4 * x + 3] = 255;
        }
    }
    RET(0);
}
void read_rgba_hdr(::Ctx* c) {   // same pixels as Rgba; the transfer function is applied by the player's shader
    read_rgba(c);
}
void native_image_handle(::Ctx* c) {
    static bool once = false;
    if (!once) {
        once = true;
        NXLOG_W("vcodec", "GetDecoderImagePoolNativeImageHandle: GPU (native texture) output is not implemented; only CPU reads work");
    }
    RET(0);
}

void calc_work(::Ctx* c) {   // Calculate*DecoderWorkBuffer(size*, align*, ...)
    if (A(0)) wr64(A(0), 0x1000);
    if (A(1)) wr64(A(1), 0x1000);
    RET(0);
}
void create_decoder(::Ctx* c, int codec, uint32_t w, uint32_t h) {
    const uint64_t g = A(0);
    auto d = std::make_shared<Decoder>();
    d->codec = codec;
    {
        std::lock_guard<std::mutex> lk(g_reg_mu);
        d->id = g_next_id++;
        g_decoders[d->id] = d;
    }
    if (codec != 10) vpx_open(*d);   // AV1 opens dav1d on its first packet (create_decoder has no configuration record)
    d->worker = std::thread([raw = d.get()] { worker_loop(*raw); });   // joined in ~Decoder, before the decoder dies
    d->worker_started = true;
    wr64(g, d->id);
    wr64(g + 8, kDecMarker);
    s_created++;
#if NXRT_HAVE_DAV1D
    if (codec == 10)
        NXLOG_I("vcodec", "AV1 decoder %u created (%ux%u max) on dav1d %s (%d threads)", d->id, w, h, dav1d_version(), g_threads);
    else
#endif
        NXLOG_I("vcodec", "VP%d decoder %u created (%ux%u max) on libvpx %s", codec, d->id, w, h, vpx_codec_version_str());
    RET(0);
}
void init_vp9_tm(::Ctx* c) { create_decoder(c, 9, static_cast<uint16_t>(A(4)), static_cast<uint16_t>(A(5))); }
void init_vp9_rm(::Ctx* c) { create_decoder(c, 9, static_cast<uint16_t>(A(2)), static_cast<uint16_t>(A(3))); }
void init_vp9_rm2(::Ctx* c) { create_decoder(c, 9, static_cast<uint16_t>(A(3)), static_cast<uint16_t>(A(4))); }
void init_vp8_tm(::Ctx* c) { create_decoder(c, 8, static_cast<uint16_t>(A(4)), static_cast<uint16_t>(A(5))); }
void init_vp8_rm(::Ctx* c) { create_decoder(c, 8, static_cast<uint16_t>(A(2)), static_cast<uint16_t>(A(3))); }
void init_vp8_rm2(::Ctx* c) { create_decoder(c, 8, static_cast<uint16_t>(A(3)), static_cast<uint16_t>(A(4))); }
// SDK 3.0.1's nn::codec adds *DecoderByTransferMemory / ByRemoteMemory: (type, mem, size, size, u16 w, u16 h, u32, in fmt, out fmt,
// mode) / (type, size, u16 w, u16 h, u32, in fmt, out fmt, mode). The height is in the same registers as the older Initialize*Decoder.
void init_av1_tm(::Ctx* c) { create_decoder(c, 10, static_cast<uint16_t>(A(4)), static_cast<uint16_t>(A(5))); }
void init_av1_rm(::Ctx* c) { create_decoder(c, 10, static_cast<uint16_t>(A(2)), static_cast<uint16_t>(A(3))); }

void finalize_decoder(::Ctx* c) {
    const uint64_t g = A(0);
    auto d = dec_of(g);
    if (d) {
        {
            std::lock_guard<std::mutex> lk(g_reg_mu);
            g_decoders.erase(d->id);
        }
        // fences of a finalized decoder count as reached: wake whoever still waits
        for (uint64_t evt : take_reached(d->id, ~0ull)) gcall(c, os().signal_event, evt);
        if (d->submit_event_made && os().destroy_sysevent) gcall(c, os().destroy_sysevent, reinterpret_cast<uint64_t>(d->submit_event));
        {
            std::lock_guard<std::mutex> lk(d->mu);
            vpx_close(*d);
#if NXRT_HAVE_DAV1D
            av1_close(*d);
#endif
        }
        NXLOG_I("vcodec", "decoder %u finalized after %llu pictures", d->id, (unsigned long long)d->pictures);
        s_destroyed++;
        wr64(g, 0);
        wr64(g + 8, 0);
    }
    RET(0);
}
void register_buffer(::Ctx* c) {   // (dec, index, pool, u32)
    auto d = dec_of(A(0));
    if (d) {
        std::lock_guard<std::mutex> lk(d->mu);
        const uint32_t index = static_cast<uint32_t>(A(1));
        d->pools[index] = A(2);
        d->free.push_back(index);
        if (g_log) NXLOG_I("vcodec", "decoder %u: buffer %u registered (pool %llx)", d->id, index, (unsigned long long)A(2));
    }
    RET(0);
}
// Start*Decoder: from here on input is accepted, so the submission-ready event is signalled. It must not be signalled before: subsdk0's
// decoder adapter thread wakes on it, forwards "input available" to the player only while the adapter is started, and clears the event
// either way, so a signal that comes before Start is lost and the player never sends its first packet.
void start_decoder(::Ctx* c) {
    auto d = dec_of(A(0));
    if (d) {
        {
            std::lock_guard<std::mutex> lk(d->mu);
            d->started = true;
            d->want_submit_signal = true;
        }
        NXLOG_I("vcodec", "decoder %u started", d->id);
        after_change(c, *d, false);
    }
    RET(0);
}
void stop_decoder(::Ctx* c) {
    if (auto d = dec_of(A(0))) {
        std::lock_guard<std::mutex> lk(d->mu);
        d->started = false;
    }
    RET(0);
}
void flush_decoder(::Ctx* c) {
    auto d = dec_of(A(0));
    if (!d) { RET(0); return; }
    {
        std::lock_guard<std::mutex> lk(d->mu);
        // the buffers waiting for a picture complete empty, decoded pictures and the decoder's references are dropped
        for (const auto& [index, seq] : d->waiting) d->info[index] = BufInfo{d->last_w, d->last_h, 0, false};
        if (!d->waiting.empty()) d->done_seq.store(d->waiting.back().second);
        d->waiting.clear();
        d->ready.clear();
        vpx_close(*d);
#if NXRT_HAVE_DAV1D
        av1_close(*d);   // the next packet after a flush starts at a key frame and carries the sequence header again
#endif
        d->want_submit_signal = true;
    }
    if (g_log) NXLOG_I("vcodec", "decoder %u flushed", d->id);
    after_change(c, *d, true);
    RET(0);
}
void submission_event(::Ctx* c) {   // (SystemEventType** out, dec)
    auto d = dec_of(A(1));
    if (!d) { if (A(0)) wr64(A(0), 0); RET(0); return; }
    bool make = false;
    {
        std::lock_guard<std::mutex> lk(d->mu);
        make = !d->submit_event_made;
        d->submit_event_made = true;
    }
    const uint64_t ev = reinterpret_cast<uint64_t>(d->submit_event);
    if (make) {
        gcall(c, os().create_sysevent, ev, kManualClear, 0);
        bool started;
        {
            std::lock_guard<std::mutex> lk(d->mu);
            started = d->started;
        }
        if (started) gcall(c, os().signal_sysevent, ev);   // asked for after Start: input is accepted now (else Start signals it)
    }
    if (A(0)) wr64(A(0), ev);
    if (g_log) NXLOG_I("vcodec", "decoder %u: submission ready event at 0x%llx (created %d)", d->id, (unsigned long long)ev, make ? 1 : 0);
    RET(0);
}
// SDK 3.0.1's Get*DecoderSubmissionReadyEvent(type) returns the nn::os::SystemEventType* itself (no out parameter).
void submission_event_ret(::Ctx* c) {   // (dec) -> SystemEventType*
    auto d = dec_of(A(0));
    if (!d) { RET(0); return; }
    bool make = false;
    {
        std::lock_guard<std::mutex> lk(d->mu);
        make = !d->submit_event_made;
        d->submit_event_made = true;
    }
    const uint64_t ev = reinterpret_cast<uint64_t>(d->submit_event);
    if (make) {
        gcall(c, os().create_sysevent, ev, kManualClear, 0);
        bool started;
        {
            std::lock_guard<std::mutex> lk(d->mu);
            started = d->started;
        }
        if (started) gcall(c, os().signal_sysevent, ev);
    }
    if (g_log) NXLOG_I("vcodec", "decoder %u: submission ready event -> 0x%llx (created %d)", d->id, (unsigned long long)ev, make ? 1 : 0);
    RET(ev);
}
// Decodes one queued packet into pictures (no d.mu held while the decode runs, so the player's Acquire never waits on it).
void decode_one(Decoder& d) {
    Pending p;
    {
        std::lock_guard<std::mutex> lk(d.mu);
        if (d.pending.empty()) return;
        p = std::move(d.pending.front());
        d.pending.pop_front();
    }
    std::vector<Picture> out;
    {
        std::lock_guard<std::mutex> dlk(d.dec_mu);   // the codec context and the last picture
        if (!p.data.empty()) decode_into(d, p.data.data(), p.data.size(), p.pts, out);
        if (p.eos) {
            if (d.vpx_ok) decode_into(d, nullptr, 0, p.pts, out);   // drain
            Picture pic;
            pic.nv12 = d.last;
            pic.w = d.last_w;
            pic.h = d.last_h;
            pic.pts = p.pts;
            pic.eos = true;
            out.push_back(std::move(pic));
            NXLOG_I("vcodec", "decoder %u: end of stream after %llu pictures", d.id, (unsigned long long)d.pictures);
            hitch_note_film_end();   // the hitch summaries say how long ago this was, so a slow stretch after a cutscene is visible
        }
    }
    if (out.empty()) return;
    {
        std::lock_guard<std::mutex> lk(d.mu);
        if (d.first_picture_ms < 0 && d.t_first_packet.time_since_epoch().count() != 0) {
            d.first_picture_ms = static_cast<long long>(std::chrono::duration_cast<std::chrono::milliseconds>(
                std::chrono::steady_clock::now() - d.t_first_packet).count());
            NXLOG_I("vcodec", "decoder %u: first picture %lld ms after its first packet", d.id, d.first_picture_ms);
        }
        for (auto& pic : out) d.ready.push_back(std::move(pic));
    }
    d.cv.notify_all();
}
// Decodes ahead of the player, so the decode (4K AV1, ~20 ms) overlaps the library's fill and the player's texture work instead of
// adding to them. It only fills ready: fences are completed on the guest thread (Assign in Acquire / Submit), which is the only
// place a guest event may be signalled.
void worker_loop(Decoder& d) {
    t_on_worker = true;
    // The film starts while the game is still loading, and the player's own thread is what loses the CPU then (frames every
    // 2-8 s for the first ~20 s). Keep the decoders off its way.
    SetThreadPriority(GetCurrentThread(), THREAD_PRIORITY_BELOW_NORMAL);
    std::unique_lock<std::mutex> lk(d.mu);
    for (;;) {
        d.cv.wait(lk, [&] { return d.stop || (!d.pending.empty() && d.ready.size() < kAhead); });
        if (d.stop) return;
        lk.unlock();
        decode_one(d);
        lk.lock();
    }
}
Decoder::~Decoder() {
    {
        std::lock_guard<std::mutex> lk(mu);
        stop = true;
    }
    cv.notify_all();
    if (worker.joinable()) worker.join();
    if (nv) nvdec_destroy(nv);
    if (ff) ffdec_destroy(ff);
}
// The body shared by the two Submit*DecoderInputBuffer shapes: SDK 3.0.1's AV1 one has no size_t* out parameter, the VP8 / VP9 one
// has it first.
void submit_packet(::Ctx* c, uint64_t dec, const uint8_t* data, size_t size, int64_t pts, bool eos) {
    auto d = dec_of(dec);
    if (!d) { RET(0); return; }
    if (d->t_first_packet.time_since_epoch().count() == 0) d->t_first_packet = std::chrono::steady_clock::now();
    s_packets++;
    bool fences = false;
    {
        std::unique_lock<std::mutex> lk(d->mu);
        // Never block: this runs on the player's own thread (the library submits from it), and waiting here froze the player
        // (2026-11-18: one frame read, green picture, no VideoFrame after that). The queue holds the film's packets instead.
        Pending p;
        if (data && size) p.data.assign(data, data + size);
        p.pts = pts;
        p.eos = eos;
        d->pending.push_back(std::move(p));
        // Never decode here: the adapter thread submits the whole movie ahead, and a decode per submit (23 ms) left it no time to
        // service the player (the acquire-to-read gap was 48-69 ms with the copies at 1.1-1.7 ms, 2026-11-18). The worker decodes
        // ahead instead; this only wakes it.
        d->cv.notify_all();
        fences = assign(*d);
        d->want_submit_signal = true;
    }
    static std::atomic<uint32_t> first_submits{0};
    if (g_log || first_submits.fetch_add(1) < 3)
        NXLOG_I("vcodec", "decoder %u: submit %zu bytes pts %lld%s (%llu pictures so far)", d->id, size, (long long)pts, eos ? " eos" : "",
                (unsigned long long)d->pictures);
    after_change(c, *d, fences);
    RET(0);
}
void submit(::Ctx* c) {   // (u64* out, dec, data, size, pts, eos): VP8 / VP9
    if (A(0)) wr64(A(0), 0);
    submit_packet(c, A(1), reinterpret_cast<const uint8_t*>(A(2)), A(3), static_cast<int64_t>(A(4)), (A(5) & 1) != 0);
}
void submit_av1(::Ctx* c) {   // (dec, data, size, pts, eos): SDK 3.0.1
    submit_packet(c, A(0), reinterpret_cast<const uint8_t*>(A(1)), A(2), static_cast<int64_t>(A(3)), (A(4) & 1) != 0);
}
void acquire_output(::Ctx* c) {   // (u32* index, NativeSyncHandle* fence, dec)
    auto d = dec_of(A(2));
    uint32_t index = 0;
    uint64_t seq = 0;
    bool fences = false;
    if (d) {
        std::unique_lock<std::mutex> lk(d->mu);
        if (d->free.empty()) {
            note_error("decoder %u: AcquireOutputBuffer with no free buffer", d->id);
        } else {
            index = d->free.front();
            d->free.pop_front();
            seq = d->next_seq++;
            // Nothing to pair and nothing on the way: complete the fence right away instead of handing out one that nothing
            // can ever complete. Fences are only completed on guest calls, and a player waiting in that fence makes no call,
            // so the film stayed on its empty texture - a green picture with zero reads, one run in three (2026-11-21). It
            // reads the pool's neutral image instead and comes back once packets exist.
            // Always queue it: a buffer that is not queued can never be paired, and the picture then has nowhere to go
            // (placed stayed 0 for a whole film, 2026-11-21). When nothing exists yet, the fence is completed now as well, so
            // the player reads the pool's neutral image and keeps going instead of waiting for a fence no call will complete.
            d->waiting.emplace_back(index, seq);
            if (d->ready.empty() && d->pending.empty()) {
                d->done_seq.store(seq);
                fences = true;
                ++d->completed_early;
            }
            // Usually the worker already has the picture. If it does not within a moment, decode here: the library arms its fence
            // right after this call and waits for it, so handing out an incomplete fence and hoping a later submit completes it
            // stalls the player for as long as that wait takes (3-16 s frames at the film's start, 2026-11-18).
            if (d->ready.empty() && !d->pending.empty() &&
                !d->cv.wait_for(lk, std::chrono::milliseconds(2), [&] { return !d->ready.empty() || d->stop; })) {
                lk.unlock();
                decode_one(*d);
                lk.lock();
            }
            fences = assign(*d);
        }
    }
    g_last_acquire_ns.store(now_ns(), std::memory_order_relaxed);
    if (A(0)) wr32(A(0), index);
    if (A(1)) {
        wr64(A(1), d && seq ? (kSyncMarker | d->id) : 0);
        wr64(A(1) + 8, seq);
    }
    if (g_log && d) {
        static std::atomic<uint32_t> n{0};
        if (n.fetch_add(1, std::memory_order_relaxed) < 24)
            NXLOG_I("vcodec", "decoder %u: acquire -> index %u, fence %llu (ready %zu, pending %zu, waiting %zu, free %zu, early %llu)", d->id,
                    index, (unsigned long long)seq, d->ready.size(), d->pending.size(), d->waiting.size(), d->free.size(),
                    static_cast<unsigned long long>(d->completed_early.load()));
    }
    if (d) after_change(c, *d, fences);
    RET(0);
}
void release_output(::Ctx* c) {   // (dec, index, pre-fence)
    if (auto d = dec_of(A(0))) {
        {
            std::lock_guard<std::mutex> lk(d->mu);
            d->free.push_back(static_cast<uint32_t>(A(1)));
        }
        if (g_log) {
            static std::atomic<uint32_t> n{0};
            if (n.fetch_add(1, std::memory_order_relaxed) < 12) NXLOG_I("vcodec", "decoder %u: release index %u", d->id, static_cast<uint32_t>(A(1)));
        }
    }
    RET(0);
}
int64_t g_pts_shift_ns = 0;      // [media] movie_pts_shift_ms: see the install note
bool g_pts_wallclock = false;   // [media] movie_pts_wallclock: report the frame time as our own elapsed time (diagnostic)
void props_write(uint64_t pw, uint64_t ph, uint64_t pa, uint64_t pb, uint64_t ppts, uint64_t peos, const BufInfo& b) {
    if (pw) wr16(pw, b.w);
    if (ph) wr16(ph, b.h);
    if (pa) wr16(pa, b.w);
    if (pb) wr16(pb, b.h);
    if (ppts) {
        if (g_pts_wallclock) {
            // Diagnostic: the movie's own timestamps run on the movie clock while the player's clock runs on real time, and a 4K AV1
            // decode plus the library's fill put every frame far behind it (it dropped all but the first). Handing out our elapsed
            // time instead keeps the player's "late" check quiet, so the picture should move at whatever rate the pipeline reaches.
            static std::atomic<int64_t> start_ns{0};
            const int64_t now = std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();
            int64_t s0 = start_ns.load(std::memory_order_relaxed);
            if (!s0 && b.pts > 0) { start_ns.compare_exchange_strong(s0, now); s0 = start_ns.load(); }
            wr64(ppts, static_cast<uint64_t>(s0 ? now - s0 : 0));
        } else {
            wr64(ppts, static_cast<uint64_t>(b.pts > 0 ? b.pts + g_pts_shift_ns : b.pts));
        }
    }
    if (peos) *reinterpret_cast<uint8_t*>(peos) = b.eos ? 1 : 0;
    if (g_log) {
        static std::atomic<uint32_t> n{0};
        if (n.fetch_add(1, std::memory_order_relaxed) < 30)
            NXLOG_I("vcodec", "output properties: %ux%u, pts %lld, eos %d", b.w, b.h, static_cast<long long>(b.pts), b.eos ? 1 : 0);
    }
}
BufInfo props_of(uint64_t dec, uint32_t index) {
    BufInfo b;
    if (auto d = dec_of(dec)) {
        std::lock_guard<std::mutex> lk(d->mu);
        auto it = d->info.find(index);
        if (it != d->info.end()) b = it->second;
    }
    return b;
}
void props(::Ctx* c) {   // (u16*, u16*, u16*, u16*, TimeSpan*, bool*, dec, index)
    props_write(A(0), A(1), A(2), A(3), A(4), A(5), props_of(A(6), static_cast<uint32_t>(A(7))));
    RET(0);
}
void props_cs(::Ctx* c) {   // MKW: (u16*, u16*, u16*, u16*, ColorSpace*, TimeSpan*, bool*, dec, [sp] index)
    if (A(4)) wr32(A(4), 0);
    props_write(A(0), A(1), A(2), A(3), A(5), A(6), props_of(A(7), static_cast<uint32_t>(rd64(c->x[31]))));
    RET(0);
}
void unsupported_codec(::Ctx* c) {
    static bool once = false;
    if (!once) {
        once = true;
        NXLOG_E("vcodec", "%s: H.264 / AV1 hardware decoding is not implemented on the host", c->in_import ? c->in_import : "nn::codec");
    }
    RET(0x1a6f);   // a stand-in non-zero nn::Result (codec module)
}

// ---- nn::syncpt::sdk / nn::gs ---------------------------------------------------------------------------------------------------
void sp_create(::Ctx* c) {
    const uint64_t evt = A(0);
    std::memset(reinterpret_cast<void*>(evt), 0, 0x60);
    gcall(c, os().init_event, evt, 0, kManualClear);
    wr64(evt + 0x60, kEvtMarker);
    RET(0);
}
void sp_destroy(::Ctx* c) {
    const uint64_t evt = A(0);
    {
        std::lock_guard<std::mutex> lk(g_evt_mu);
        g_armed.erase(evt);
    }
    if (rd64(evt + 0x60) == kEvtMarker) {
        gcall(c, os().finalize_event, evt);
        wr64(evt + 0x60, 0);
    }
    RET(0);
}
void sp_cancel(::Ctx* c) {
    const uint64_t evt = A(0);
    {
        std::lock_guard<std::mutex> lk(g_evt_mu);
        g_armed.erase(evt);
    }
    gcall(c, os().clear_event, evt);
    RET(0);
}
void sp_request(::Ctx* c) {   // (evt, const SyncPointHandle&)
    const uint64_t evt = A(0), h = A(1);
    const uint64_t w0 = h ? rd64(h) : 0, seq = h ? rd64(h + 8) : 0;
    gcall(c, os().clear_event, evt);
    bool reached;
    {
        std::lock_guard<std::mutex> lk(g_evt_mu);   // held across the check and the arm (see take_reached's caller)
        reached = fence_done(w0, seq);
        if (!reached) g_armed[evt] = Armed{static_cast<uint32_t>(w0), seq};
        else g_armed.erase(evt);
    }
    if (reached) gcall(c, os().signal_event, evt);
    RET(0);
}
void sp_holder(::Ctx* c) {   // (MultiWaitHolderType*, evt)
    gcall(c, os().init_holder_event, A(0), A(1));
    RET(0);
}
void sp_trywait(::Ctx* c) { RET(gcall(c, os().trywait_event, A(0)) & 1); }
void gs_trywait(::Ctx* c) {   // (const NativeSyncHandle&) -> bool
    const uint64_t h = A(0);
    RET(h ? fence_done(rd64(h), rd64(h + 8)) : 1);
}

// ---- nn::movie extractor trace ([media] movie_trace) ------------------------------------------------------------------------------
// Pokopia's movie::Extractor (subsdk0) runs the SDK's nn::movie::MediaExtractor in media source mode: its ExtractorSourceModeThread
// reads the file through the game's ClientStreamReader (8 KiB at a time) and appends it with AppendMediaSourceData; the extractor
// (nandroid MatroskaExtractor for WebM) parses from that. movie::Extractor::SetDataSource then checks the track count and the
// "container-mime" of track 0 against the ContainerType (3 = WebM) and answers 0x4000 when they disagree, which the game's player
// treats as "cannot open". These wrappers log what the SDK answered on that path (rate-limited) and then return its answer unchanged.
uint64_t call_original(::Ctx* c, uint64_t fn) {
    const uint64_t lr = c->x[30], f = c->fn;
    dispatch_call(c, fn);
    c->x[30] = lr;
    c->fn = f;
    return c->x[0];
}
struct Traced {
    const char* name;
    std::atomic<uint64_t> orig{0};
    std::atomic<uint32_t> calls{0};
};
Traced t_init{"_ZN2nn5movie14MediaExtractor10InitializeEPvmm"};
Traced t_msm{"_ZN2nn5movie14MediaExtractor20SetUpMediaSourceModeEv"};
Traced t_size{"_ZN2nn5movie6detail18ExtractorUnwrapper19StreamSourceSetSizeEl"};
Traced t_append{"_ZN2nn5movie14MediaExtractor21AppendMediaSourceDataEPKvm"};
Traced t_seekpos{"_ZN2nn5movie14MediaExtractor30GetMediaSourceModeSeekPositionEPl"};
Traced t_count{"_ZN2nn5movie14MediaExtractor13GetTrackCountEPi"};
Traced t_props{"_ZN2nn5movie14MediaExtractor18GetTrackPropertiesEPNS0_13MediaPropertyEi"};
Traced t_getstr{"_ZNK2nn5movie13MediaProperty9GetStringEPciPKc"};
std::atomic<uint64_t> t_appended{0};

// Calls the SDK's own function; the count of calls so far comes back in *n.
uint64_t traced(::Ctx* c, Traced& t, uint32_t* n) {
    uint64_t fn = t.orig.load(std::memory_order_relaxed);
    if (!fn) {
        fn = module_find_symbol(t.name);   // the defining module's address (the override only redirects the imports)
        t.orig = fn;
    }
    *n = t.calls.fetch_add(1) + 1;
    if (!fn) { RET(0); return 0; }
    return call_original(c, fn);
}
void tr_init(::Ctx* c) {
    const uint64_t cache = A(3);
    uint32_t n;
    const uint32_t r = static_cast<uint32_t>(traced(c, t_init, &n));
    if (n <= 8 || r) NXLOG_I("movie.trace", "MediaExtractor::Initialize(cache %llu) -> 0x%x", (unsigned long long)cache, r);
}
void tr_msm(::Ctx* c) {
    uint32_t n;
    const uint32_t r = static_cast<uint32_t>(traced(c, t_msm, &n));
    if (n <= 8 || r) NXLOG_I("movie.trace", "MediaExtractor::SetUpMediaSourceMode -> 0x%x", r);
}
void tr_size(::Ctx* c) {
    const int64_t size = static_cast<int64_t>(A(1));
    uint32_t n;
    const uint32_t r = static_cast<uint32_t>(traced(c, t_size, &n));
    if (n <= 8 || r) NXLOG_I("movie.trace", "StreamSourceSetSize(%lld) -> 0x%x", (long long)size, r);
}
void tr_append(::Ctx* c) {
    const uint64_t data = A(1), size = A(2);
    uint32_t n;
    const uint32_t r = static_cast<uint32_t>(traced(c, t_append, &n));
    const uint64_t total = t_appended.fetch_add(size) + size;
    static std::atomic<uint32_t> logged{0};
    if ((n <= 3 || size == 0 || r) && logged.fetch_add(1) < 24)
        NXLOG_I("movie.trace", "AppendMediaSourceData #%u: %llu bytes%s (%llu in all) -> 0x%x", n, (unsigned long long)size,
                data ? "" : " (no data: end of stream)", (unsigned long long)total, r);
}
void tr_seekpos(::Ctx* c) {
    const uint64_t out = A(1);
    uint32_t n;
    const uint32_t r = static_cast<uint32_t>(traced(c, t_seekpos, &n));
    if (n <= 16 || r) NXLOG_I("movie.trace", "GetMediaSourceModeSeekPosition -> %lld, 0x%x", out ? (long long)rd64(out) : -1ll, r);
}
void tr_count(::Ctx* c) {
    const uint64_t out = A(1);
    uint32_t n;
    const uint32_t r = static_cast<uint32_t>(traced(c, t_count, &n));
    int32_t k = -1;
    if (out) std::memcpy(&k, reinterpret_cast<const void*>(out), 4);
    if (n <= 8 || r) NXLOG_I("movie.trace", "MediaExtractor::GetTrackCount -> %d tracks, 0x%x", k, r);
}
void tr_props(::Ctx* c) {
    const int32_t track = static_cast<int32_t>(A(2));
    uint32_t n;
    const uint32_t r = static_cast<uint32_t>(traced(c, t_props, &n));
    if (n <= 8 || r) NXLOG_I("movie.trace", "MediaExtractor::GetTrackProperties(track %d) -> 0x%x", track, r);
}
void tr_getstr(::Ctx* c) {   // (const MediaProperty*, char* out, int size, const char* key) -> bool
    const uint64_t out = A(1), key = A(3);
    uint32_t n;
    const uint64_t r = traced(c, t_getstr, &n) & 1;
    const char* k = key ? reinterpret_cast<const char*>(key) : "";
    static std::atomic<uint32_t> logged{0};
    if (std::strstr(k, "mime") && logged.fetch_add(1) < 16)
        NXLOG_I("movie.trace", "MediaProperty::GetString(\"%s\") -> %s \"%.40s\"", k, r ? "found" : "missing",
                r && out ? reinterpret_cast<const char*>(out) : "");
}
struct TraceImport {
    Traced* t;
    HleFn fn;
};
const TraceImport kTraceImports[] = {
    {&t_init, tr_init}, {&t_msm, tr_msm}, {&t_size, tr_size}, {&t_append, tr_append},
    {&t_seekpos, tr_seekpos}, {&t_count, tr_count}, {&t_props, tr_props}, {&t_getstr, tr_getstr},
};

struct Import {
    const char* name;
    HleFn fn;
};
const Import kImports[] = {
    {"_ZN2nn5codec25MakeDecodeImagePreferenceEttNS0_24VideoDecoderOutputFormatENS0_9CodecModeE", make_pref},
    // SDK 3.0.1 (Xenoblade 2's movie library): the fourth argument is the image tiling mode, and InitializeDecoderImagePool has no
    // trailing codec mode. Same handlers: only the picture size and the output format are read back.
    {"_ZN2nn5codec25MakeDecodeImagePreferenceEttNS0_24VideoDecoderOutputFormatENS0_15ImageTilingModeE", make_pref},
    {"_ZN2nn5codec3sdk34MakeDecodeImagePreferenceForCompatEttNS0_24VideoDecoderOutputFormatENS0_9CodecModeE", make_pref},
    {"_ZN2nn5codec31CalculateDecoderImagePoolBufferEPmS1_RKNS0_27VideoDecoderImagePreferenceEj", calc_pool},
    {"_ZN2nn5codec26InitializeDecoderImagePoolEPNS0_25VideoDecoderImagePoolTypeEPvmRKNS0_27VideoDecoderImagePreferenceEjNS0_9CodecModeE", init_pool},
    {"_ZN2nn5codec26InitializeDecoderImagePoolEPNS0_25VideoDecoderImagePoolTypeEPvmRKNS0_27VideoDecoderImagePreferenceEj", init_pool},
    {"_ZN2nn5codec24FinalizeDecoderImagePoolEPNS0_25VideoDecoderImagePoolTypeE", fini_pool},
    {"_ZN2nn5codec26ReadDecoderOutputImageNv12EPKNS0_25VideoDecoderImagePoolTypeEjttttPvmmS4_mm", read_nv12},
    {"_ZN2nn5codec26ReadDecoderOutputImageRgbaEPKNS0_25VideoDecoderImagePoolTypeEjttttPvmm", read_rgba},
    {"_ZN2nn5codec29ReadDecoderOutputImageRgbaHdrEPKNS0_25VideoDecoderImagePoolTypeEjttttPvmm", read_rgba_hdr},
    {"_ZN2nn5codec36GetDecoderImagePoolNativeImageHandleEPKNS0_25VideoDecoderImagePoolTypeEj", native_image_handle},
    // VP9
    {"_ZN2nn5codec29CalculateVp9DecoderWorkBufferEPmS1_mtt", calc_work},
    {"_ZN2nn5codec20InitializeVp9DecoderEPNS0_14Vp9DecoderTypeEPvmmttjNS0_23VideoDecoderInputFormatENS0_24VideoDecoderOutputFormatE", init_vp9_tm},
    {"_ZN2nn5codec20InitializeVp9DecoderEPNS0_14Vp9DecoderTypeEmttjNS0_23VideoDecoderInputFormatENS0_24VideoDecoderOutputFormatE", init_vp9_rm},
    {"_ZN2nn5codec20InitializeVp9DecoderEPNS0_14Vp9DecoderTypeEmmttjNS0_23VideoDecoderInputFormatENS0_24VideoDecoderOutputFormatE", init_vp9_rm2},
    {"_ZN2nn5codec18FinalizeVp9DecoderEPNS0_14Vp9DecoderTypeE", finalize_decoder},
    {"_ZN2nn5codec24RegisterVp9DecoderBufferEPNS0_14Vp9DecoderTypeEjPNS0_25VideoDecoderImagePoolTypeEj", register_buffer},
    {"_ZN2nn5codec15StartVp9DecoderEPNS0_14Vp9DecoderTypeE", start_decoder},
    {"_ZN2nn5codec14StopVp9DecoderEPNS0_14Vp9DecoderTypeE", stop_decoder},
    {"_ZN2nn5codec15FlushVp9DecoderEPNS0_14Vp9DecoderTypeE", flush_decoder},
    {"_ZN2nn5codec33GetVp9DecoderSubmissionReadyEventEPPNS_2os15SystemEventTypeEPNS0_14Vp9DecoderTypeE", submission_event},
    {"_ZN2nn5codec27SubmitVp9DecoderInputBufferEPmPNS0_14Vp9DecoderTypeEPKvmNS_8TimeSpanEb", submit},
    {"_ZN2nn5codec29AcquireVp9DecoderOutputBufferEPjPNS_2gs16NativeSyncHandleEPNS0_14Vp9DecoderTypeE", acquire_output},
    {"_ZN2nn5codec29ReleaseVp9DecoderOutputBufferEPNS0_14Vp9DecoderTypeEjNS_2gs16NativeSyncHandleE", release_output},
    {"_ZN2nn5codec35GetVp9DecoderOutputBufferPropertiesEPtS1_S1_S1_PNS_8TimeSpanEPbPNS0_14Vp9DecoderTypeEj", props},
    {"_ZN2nn5codec35GetVp9DecoderOutputBufferPropertiesEPtS1_S1_S1_PNS_5movie10ColorSpaceEPNS_8TimeSpanEPbPNS0_14Vp9DecoderTypeEj", props_cs},
    // VP8 (same decoder on libvpx's VP8 interface)
    {"_ZN2nn5codec29CalculateVp8DecoderWorkBufferEPmS1_mtt", calc_work},
    {"_ZN2nn5codec20InitializeVp8DecoderEPNS0_14Vp8DecoderTypeEPvmmttjNS0_23VideoDecoderInputFormatENS0_24VideoDecoderOutputFormatE", init_vp8_tm},
    {"_ZN2nn5codec20InitializeVp8DecoderEPNS0_14Vp8DecoderTypeEmttjNS0_23VideoDecoderInputFormatENS0_24VideoDecoderOutputFormatE", init_vp8_rm},
    {"_ZN2nn5codec20InitializeVp8DecoderEPNS0_14Vp8DecoderTypeEmmttjNS0_23VideoDecoderInputFormatENS0_24VideoDecoderOutputFormatE", init_vp8_rm2},
    {"_ZN2nn5codec18FinalizeVp8DecoderEPNS0_14Vp8DecoderTypeE", finalize_decoder},
    {"_ZN2nn5codec24RegisterVp8DecoderBufferEPNS0_14Vp8DecoderTypeEjPNS0_25VideoDecoderImagePoolTypeEj", register_buffer},
    {"_ZN2nn5codec15StartVp8DecoderEPNS0_14Vp8DecoderTypeE", start_decoder},
    {"_ZN2nn5codec14StopVp8DecoderEPNS0_14Vp8DecoderTypeE", stop_decoder},
    {"_ZN2nn5codec15FlushVp8DecoderEPNS0_14Vp8DecoderTypeE", flush_decoder},
    {"_ZN2nn5codec33GetVp8DecoderSubmissionReadyEventEPPNS_2os15SystemEventTypeEPNS0_14Vp8DecoderTypeE", submission_event},
    {"_ZN2nn5codec27SubmitVp8DecoderInputBufferEPmPNS0_14Vp8DecoderTypeEPKvmNS_8TimeSpanEb", submit},
    {"_ZN2nn5codec29AcquireVp8DecoderOutputBufferEPjPNS_2gs16NativeSyncHandleEPNS0_14Vp8DecoderTypeE", acquire_output},
    {"_ZN2nn5codec29ReleaseVp8DecoderOutputBufferEPNS0_14Vp8DecoderTypeEjNS_2gs16NativeSyncHandleE", release_output},
    {"_ZN2nn5codec35GetVp8DecoderOutputBufferPropertiesEPtS1_S1_S1_PNS_8TimeSpanEPbPNS0_14Vp8DecoderTypeEj", props},
    {"_ZN2nn5codec35GetVp8DecoderOutputBufferPropertiesEPtS1_S1_S1_PNS_5movie10ColorSpaceEPNS_8TimeSpanEPbPNS0_14Vp8DecoderTypeEj", props_cs},
    // SDK 3.0.1 (Xenoblade 2's subsdk0): Initialize*DecoderByTransferMemory / ByRemoteMemory with a VideoDecoderOutputMode, and a
    // Get*DecoderSubmissionReadyEvent that returns the event instead of writing it through an out pointer. VP8 / VP9 keep the
    // size_t* out parameter of Submit*DecoderInputBuffer; AV1's was dropped.
    {"_ZN2nn5codec36InitializeVp9DecoderByTransferMemoryEPNS0_14Vp9DecoderTypeEPvmmttjNS0_23VideoDecoderInputFormatENS0_24VideoDecoderOutputFormatENS0_22VideoDecoderOutputModeE", init_vp9_tm},
    {"_ZN2nn5codec34InitializeVp9DecoderByRemoteMemoryEPNS0_14Vp9DecoderTypeEmttjNS0_23VideoDecoderInputFormatENS0_24VideoDecoderOutputFormatENS0_22VideoDecoderOutputModeE", init_vp9_rm},
    {"_ZN2nn5codec33GetVp9DecoderSubmissionReadyEventEPNS0_14Vp9DecoderTypeE", submission_event_ret},
    {"_ZN2nn5codec36InitializeVp8DecoderByTransferMemoryEPNS0_14Vp8DecoderTypeEPvmmttjNS0_23VideoDecoderInputFormatENS0_24VideoDecoderOutputFormatENS0_22VideoDecoderOutputModeE", init_vp8_tm},
    {"_ZN2nn5codec34InitializeVp8DecoderByRemoteMemoryEPNS0_14Vp8DecoderTypeEmttjNS0_23VideoDecoderInputFormatENS0_24VideoDecoderOutputFormatENS0_22VideoDecoderOutputModeE", init_vp8_rm},
    {"_ZN2nn5codec33GetVp8DecoderSubmissionReadyEventEPNS0_14Vp8DecoderTypeE", submission_event_ret},
    // AV1 (dav1d): the codec Xenoblade 2's Switch 2 movies use
    {"_ZN2nn5codec36InitializeAv1DecoderByTransferMemoryEPNS0_14Av1DecoderTypeEPvmmttjNS0_23VideoDecoderInputFormatENS0_24VideoDecoderOutputFormatENS0_22VideoDecoderOutputModeE", init_av1_tm},
    {"_ZN2nn5codec34InitializeAv1DecoderByRemoteMemoryEPNS0_14Av1DecoderTypeEmttjNS0_23VideoDecoderInputFormatENS0_24VideoDecoderOutputFormatENS0_22VideoDecoderOutputModeE", init_av1_rm},
    {"_ZN2nn5codec18FinalizeAv1DecoderEPNS0_14Av1DecoderTypeE", finalize_decoder},
    {"_ZN2nn5codec24RegisterAv1DecoderBufferEPNS0_14Av1DecoderTypeEjPNS0_25VideoDecoderImagePoolTypeEj", register_buffer},
    {"_ZN2nn5codec15StartAv1DecoderEPNS0_14Av1DecoderTypeE", start_decoder},
    {"_ZN2nn5codec14StopAv1DecoderEPNS0_14Av1DecoderTypeE", stop_decoder},
    {"_ZN2nn5codec15FlushAv1DecoderEPNS0_14Av1DecoderTypeE", flush_decoder},
    {"_ZN2nn5codec33GetAv1DecoderSubmissionReadyEventEPNS0_14Av1DecoderTypeE", submission_event_ret},
    {"_ZN2nn5codec27SubmitAv1DecoderInputBufferEPNS0_14Av1DecoderTypeEPKvmNS_8TimeSpanEb", submit_av1},
    // What this SDK actually exports (subsdk0 import 275): the size_t* out parameter is back, so it is the same shape as VP8 / VP9.
    // Without this line the import bound to the SDK's own Submit (its [type+0] is an IPC object there, not our decoder id) and the
    // first submitted packet read address 0x1 (xc2_boot_crash 2026-11-18 20:42).
    {"_ZN2nn5codec27SubmitAv1DecoderInputBufferEPmPNS0_14Av1DecoderTypeEPKvmNS_8TimeSpanEb", submit},
    {"_ZN2nn5codec29AcquireAv1DecoderOutputBufferEPjPNS_2gs16NativeSyncHandleEPNS0_14Av1DecoderTypeE", acquire_output},
    {"_ZN2nn5codec29ReleaseAv1DecoderOutputBufferEPNS0_14Av1DecoderTypeEjNS_2gs16NativeSyncHandleE", release_output},
    {"_ZN2nn5codec35GetAv1DecoderOutputBufferPropertiesEPtS1_S1_S1_PNS_8TimeSpanEPbPNS0_14Av1DecoderTypeEj", props},
    // H.264: not decoded here (a clear error instead of the console driver path)
    {"_ZN2nn5codec21InitializeH264DecoderEPNS0_15H264DecoderTypeEPvmmttjNS0_23VideoDecoderInputFormatENS0_24VideoDecoderOutputFormatEPKvm", unsupported_codec},
    {"_ZN2nn5codec21InitializeH264DecoderEPNS0_15H264DecoderTypeEmttjNS0_23VideoDecoderInputFormatENS0_24VideoDecoderOutputFormatEPKvm", unsupported_codec},
    {"_ZN2nn5codec20InitializeAv1DecoderEPNS0_14Av1DecoderTypeEPvmmttjNS0_23VideoDecoderInputFormatENS0_24VideoDecoderOutputFormatE", unsupported_codec},
    {"_ZN2nn5codec20InitializeAv1DecoderEPNS0_14Av1DecoderTypeEmttjNS0_23VideoDecoderInputFormatENS0_24VideoDecoderOutputFormatE", unsupported_codec},
    // fences
    {"_ZN2nn6syncpt3sdk20CreateSyncPointEventEPNS1_18SyncPointEventTypeE", sp_create},
    {"_ZN2nn6syncpt3sdk21DestroySyncPointEventEPNS1_18SyncPointEventTypeE", sp_destroy},
    {"_ZN2nn6syncpt3sdk20CancelSyncPointEventEPNS1_18SyncPointEventTypeE", sp_cancel},
    {"_ZN2nn6syncpt3sdk21RequestSyncPointEventEPNS1_18SyncPointEventTypeERKNS1_15SyncPointHandleE", sp_request},
    {"_ZN2nn6syncpt3sdk25InitializeMultiWaitHolderEPNS_2os19MultiWaitHolderTypeEPNS1_18SyncPointEventTypeE", sp_holder},
    {"_ZN2nn6syncpt3sdk21TryWaitSyncPointEventEPKNS1_18SyncPointEventTypeE", sp_trywait},
    {"_ZN2nn2gs17TryWaitNativeSyncERKNS0_16NativeSyncHandleE", gs_trywait},
};

}  // namespace

void install_player_trace();   // movie_trace.cpp ([media] player_trace)

bool install_video_codec_hle() {
    static std::once_flag once;
    std::call_once(once, [] {
        if (game::info().platform != game::Platform::Switch2) return;
        const bool mkw = std::strcmp(game::info().id, "mkw") == 0;
        const std::string mode = config_get_str("media", "video_decoder", mkw ? "off" : "library");
        if (mode == "off") {
            NXLOG_I("vcodec", "[media] video_decoder = off: nn::codec video decoders are not on the host (movies are left out)");
            return;
        }
        g_log = config_get_bool("media", "video_decoder_log", false);
        // 4 was the default and is enough for the 1080p films; the retail build's 4K AV1 openings want more, and above 8 a
    // single 3840x2160 frame stops splitting usefully. Half the cores, at least 4, at most 8.
    const int64_t def_threads = std::min<int64_t>(8, std::max<int64_t>(4, static_cast<int64_t>(std::thread::hardware_concurrency()) / 2));
    g_threads = static_cast<int>(std::clamp<int64_t>(config_get_int("media", "video_decoder_threads", def_threads), 1, 16));
    g_hwdec = config_get_bool("media", "hwdec", true);
    if (g_hwdec) {
        // The first film frame used to wait for the D3D11 device to come up (183 ms inside a 213 ms frame on 0.1.4).
        // Build it now, off the game's threads, so that cost lands in the loading screen instead of in the film.
        std::thread([] { ffdec_prewarm(); }).detach();
    }
        // Diagnostic: the player drops a frame whose timestamp is more than a frame or so behind its own movie clock, and a software 4K
        // AV1 decode plus the pool->VideoFrame copies put every frame ~85 ms behind, so it dropped all but the first. Reporting the
        // timestamps this much later makes them look on time (at the cost of that much A/V offset).
        // Default 100 ms: the XAudio2 output queue plus the device buffer, the amount the video has to wait to stay in lip sync.
        // Measured 110-120 ms on the author's machine (1440p window); 100 is the safe default, the launcher can override it.
        // The XAudio2 sink queues 33-40 ms plus the device buffer, so a film that follows its own timestamps runs ahead of its
    // sound; this delays the picture instead of the audio. 110 ms was the value that lined the 4K CG up on the maintainer's
    // device at a 1440p window (2026-11-18/19: 50 too early, 120-180 the sound arrives first). Per-device, so it stays a key.
    // 0 by default since 2026-11-21: the film's audio track is a placeholder (one byte a packet, the sound comes from the game's
    // own stream), so compensating an XAudio2 queue that never carries it only tells the player every picture is 110 ms late -
    // and at the start of the Torna opening film that lost the race often enough to freeze the picture or leave the overlay empty.
    g_pts_shift_ns = config_get_int("media", "movie_pts_shift_ms", 0) * 1000000;
        g_pts_wallclock = config_get_bool("media", "movie_pts_wallclock", false);
        install_player_trace();   // [media] player_trace: the player's message queue and timer, logged as they are called
        for (const Import& im : kImports) {
            hle_register(im.name, im.fn);
            module_override_symbol(im.name);
        }
        g_enabled = true;
#if NXRT_HAVE_DAV1D
        NXLOG_I("vcodec", "nn::codec VP9/VP8 (libvpx %s) and AV1 (dav1d %s) decoders on the host (%d threads): %zu imports routed",
                vpx_codec_version_str(), dav1d_version(), g_threads, sizeof kImports / sizeof kImports[0]);
#else
        NXLOG_I("vcodec", "nn::codec VP9/VP8 decoders on the host (libvpx %s, %d threads): %zu imports routed", vpx_codec_version_str(), g_threads,
                sizeof kImports / sizeof kImports[0]);
#endif
        if (config_get_bool("media", "movie_trace", true)) {
            for (const TraceImport& ti : kTraceImports) {
                hle_register(ti.t->name, ti.fn);
                module_override_symbol(ti.t->name);
            }
            NXLOG_I("vcodec", "[media] movie_trace: %zu nn::movie extractor calls logged (rate-limited)", sizeof kTraceImports / sizeof kTraceImports[0]);
        }
    });
    return g_enabled;
}

VideoCodecStats video_codec_stats() {
    VideoCodecStats s;
    s.decoders_created = s_created;
    s.decoders_destroyed = s_destroyed;
    s.packets_submitted = s_packets;
    s.frames_decoded = s_decoded;
    s.frames_delivered = s_delivered;
    s.frames_read = s_read;
    s.decode_errors = s_errors;
    return s;
}

#else   // built without libvpx

bool install_video_codec_hle() {
    static bool logged = false;
    if (!logged && game::info().platform == game::Platform::Switch2) {
        logged = true;
        NXLOG_W("vcodec", "built without libvpx (NXRT_HAVE_LIBVPX): movies are left out");
    }
    return false;
}
VideoCodecStats video_codec_stats() { return {}; }
namespace {
std::atomic<bool> g_enabled{false};
}

#endif

bool video_codec_enabled() { return g_enabled; }

}  // namespace nxrt::media
