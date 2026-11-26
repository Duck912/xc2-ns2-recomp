// SPDX-License-Identifier: GPL-3.0-or-later
// x2_opus301.cpp - the hardware Opus decoder replaced by the SDK's own software OpusDecoder (HANDOVER 90).
//
// Ported from nxnative's dm/host/hle_codec.c (capibawa/nxnative, branch xc2-ns2-profile; MIT), which is written for this exact
// game (SDK 21.4.4). The game's audio and cutscene tracks are Opus and the SDK's nn::codec::HardwareOpus* entry points would open
// the hwopus service, which no host has (its IHardwareOpusDecoderManager cmd 100 was answered with a stub and the caller then
// faulted on a null object). Every hardware entry point is replaced by a call into the SDK's own software OpusDecoder, which is
// lifted code like the rest: the manager owns the decoders, Enqueue queues a packet, Execute decodes every waiting packet on the
// caller's thread and signals the manager's system event, Dequeue hands the PCM back. A packet is Nintendo's 8-byte header
// (big-endian size and final range) followed by the Opus packet, which is what DecodeOpusInterleaved takes.
#include <windows.h>

#include <atomic>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <unordered_map>
#include <vector>

#include "nxrt/abi.h"
#include "nxrt/dispatch.h"
#include "nxrt/hooks.h"
#include "nxrt/log.h"
#include "nxrt/memory.h"
#include "nxrt/module.h"
#include "nxrt/nxmodule.h"

namespace {
constexpr const char* kTag = "opus";
constexpr size_t kMaxPacket = 0x1800;        // header + packet
constexpr size_t kMaxPcm = 960 * 2 * 2 * 3;  // up to 60 ms, stereo, 16-bit
constexpr size_t kSoftState = 0x200;         // the software OpusDecoderType is smaller than the hardware one

struct Req {
    Req* next = nullptr;
    size_t n = 0;
    int samples = 0;
    uint8_t data[kMaxPacket > kMaxPcm ? kMaxPacket : kMaxPcm] = {};
};
struct Mgr;
struct Dec {
    Mgr* m = nullptr;
    uint64_t soft = 0, work = 0;
    int ch = 0;
    Req *wait = nullptr, *wait_tail = nullptr, *done = nullptr, *done_tail = nullptr;
    int nwait = 0, ndone = 0;
};
struct Mgr {
    std::mutex mu;
    uint64_t event = 0;
    int io_total = 0, io_used = 0, cap = 1;
    std::vector<Dec*> dec;
};
std::mutex g_map_mu;
std::unordered_map<uint64_t, Dec*> g_dec;   // the game's decoder object -> host state
std::mutex g_mgr_mu;
std::unordered_map<uint64_t, Mgr*> g_mgr;   // the game's manager object -> host state

uint64_t sym(const char* name) {
    const uint64_t a = nxrt::nxmodule_find_export(name);
    if (!a) NXLOG_E(kTag, "the sdk does not export %s", name);
    return a;
}

// Calls a guest function with the first n registers set to args and returns its x0; the caller's registers are put back.
uint64_t call(Ctx* c, uint64_t fn, int n, const uint64_t* args) {
    if (!fn) return 0;
    const Ctx saved = *c;
    for (int i = 0; i < n; ++i) c->x[i] = args[i];
    c->x[30] = 0;
    nxrt::dispatch_call(c, fn);
    const uint64_t r = c->x[0];
    *c = saved;
    return r;
}

Dec* dec_of(uint64_t gd) {
    std::lock_guard lk(g_map_mu);
    auto it = g_dec.find(gd);
    return it == g_dec.end() ? nullptr : it->second;
}
Mgr* mgr_of(uint64_t gm) {
    std::lock_guard lk(g_mgr_mu);
    auto it = g_mgr.find(gm);
    return it == g_mgr.end() ? nullptr : it->second;
}

void dec_clear(Dec* d) {   // under the manager's lock: every request dropped, its I/O buffers back to the pool
    if (d->m) d->m->io_used -= d->nwait + d->ndone;
    for (Req* r = d->wait; r;) { Req* n = r->next; delete r; r = n; }
    for (Req* r = d->done; r;) { Req* n = r->next; delete r; r = n; }
    d->wait = d->wait_tail = d->done = d->done_tail = nullptr;
    d->nwait = d->ndone = 0;
}

int dec_count(uint64_t gd, int which) {
    Dec* d = dec_of(gd);
    if (!d || !d->m) return 0;
    std::lock_guard lk(d->m->mu);
    return which == 0 ? d->nwait : which == 2 ? d->ndone : 0;
}
// ---- the manager -----------------------------------------------------------------------------------------------------
void hle_mgr_work_size(Ctx* c) { c->x[0] = 0x1000; }   // the host keeps the manager's state; the work buffer is not used

void hle_mgr_init(Ctx* c) {   // (manager, event, rate, ch, frame_ns, decoders, io, buf, size)
    const uint64_t gm = c->x[0], event = c->x[1];
    const int decoders = static_cast<int>(c->x[5]), io = static_cast<int>(c->x[6]);
    Mgr* m = new Mgr();
    m->event = event;
    m->io_total = io;
    m->cap = decoders > 0 ? decoders : 1;
    { std::lock_guard lk(g_mgr_mu); g_mgr[gm] = m; }
    NXLOG_W(kTag, "manager 0x%llx: %d decoder(s), %d I/O buffer(s), event 0x%llx", static_cast<unsigned long long>(gm), decoders, io,
            static_cast<unsigned long long>(event));
    c->x[0] = 0;
}

void hle_mgr_fini(Ctx* c) {
    const uint64_t gm = c->x[0];
    Mgr* m = nullptr;
    {
        std::lock_guard lk(g_mgr_mu);
        auto it = g_mgr.find(gm);
        if (it != g_mgr.end()) { m = it->second; g_mgr.erase(it); }
    }
    if (!m) { c->x[0] = 0; return; }
    {
        std::lock_guard lk(m->mu);
        for (Dec* d : m->dec) if (d) d->m = nullptr;
    }
    delete m;
    c->x[0] = 0;
}

void hle_mgr_free_io(Ctx* c) {
    Mgr* m = mgr_of(c->x[0]);
    if (!m) { c->x[0] = 0; return; }
    std::lock_guard lk(m->mu);
    c->x[0] = static_cast<uint64_t>(m->io_total - m->io_used);
}

void hle_dec_init_mgr(Ctx* c) {   // (decoder, rate, ch, frame_ns, manager)
    const uint64_t gd = c->x[0], gm = c->x[4];
    const int rate = static_cast<int>(c->x[1]), ch = static_cast<int>(c->x[2]);
    Mgr* m = mgr_of(gm);
    if (!m) { c->x[0] = 0x3a6f; return; }
    Dec* d = new Dec();
    d->m = m;
    d->ch = ch;
    d->soft = reinterpret_cast<uint64_t>(std::calloc(1, kSoftState));
    const uint64_t wsize_fn = sym("_ZN2nn5codec28GetOpusDecoderWorkBufferSizeEii");
    uint64_t a[2] = {static_cast<uint64_t>(rate), static_cast<uint64_t>(ch)};
    const size_t ws = static_cast<size_t>(call(c, wsize_fn, 2, a));
    d->work = reinterpret_cast<uint64_t>(std::calloc(1, ws ? ws : 1));
    const uint64_t init_fn = sym("_ZN2nn5codec21InitializeOpusDecoderEPNS0_15OpusDecoderTypeEiiPvm");
    uint64_t b[5] = {d->soft, static_cast<uint64_t>(rate), static_cast<uint64_t>(ch), d->work, ws};
    const uint64_t r = call(c, init_fn, 5, b);
    if (r) {
        std::free(reinterpret_cast<void*>(d->work));
        std::free(reinterpret_cast<void*>(d->soft));
        delete d;
        c->x[0] = r;
        return;
    }
    {
        std::lock_guard lk(m->mu);
        m->dec.push_back(d);
    }
    { std::lock_guard lk(g_map_mu); g_dec[gd] = d; }
    c->x[0] = 0;
}

void hle_dec_fini(Ctx* c) {   // (decoder)
    const uint64_t gd = c->x[0];
    Dec* d = nullptr;
    {
        std::lock_guard lk(g_map_mu);
        auto it = g_dec.find(gd);
        if (it != g_dec.end()) { d = it->second; g_dec.erase(it); }
    }
    if (!d) { c->x[0] = 0; return; }
    const uint64_t fini_fn = sym("_ZN2nn5codec19FinalizeOpusDecoderEPNS0_15OpusDecoderTypeE");
    Mgr* m = d->m;
    if (m) {
        std::lock_guard lk(m->mu);
        dec_clear(d);
        for (size_t i = 0; i < m->dec.size(); ++i) if (m->dec[i] == d) { m->dec[i] = m->dec.back(); m->dec.pop_back(); break; }
    } else {
        dec_clear(d);
    }
    uint64_t a[1] = {d->soft};
    call(c, fini_fn, 1, a);
    std::free(reinterpret_cast<void*>(d->soft));
    std::free(reinterpret_cast<void*>(d->work));
    delete d;
    c->x[0] = 0;
}

void hle_dec_reset(Ctx* c) {
    Dec* d = dec_of(c->x[0]);
    if (!d) { c->x[0] = 0; return; }
    const uint64_t reset_fn = sym("_ZN2nn5codec16ResetOpusDecoderEPNS0_15OpusDecoderTypeE");
    Mgr* m = d->m;
    if (m) m->mu.lock();
    dec_clear(d);
    uint64_t a[1] = {d->soft};
    call(c, reset_fn, 1, a);
    if (m) m->mu.unlock();
    c->x[0] = 0;
}

void hle_dec_rate(Ctx* c) {
    Dec* d = dec_of(c->x[0]);
    if (!d) { c->x[0] = 0; return; }
    const uint64_t fn = sym("_ZN2nn5codec24GetOpusDecoderSampleRateEPKNS0_15OpusDecoderTypeE");
    uint64_t a[1] = {d->soft};
    c->x[0] = call(c, fn, 1, a);
}

void hle_dec_ch(Ctx* c) {
    Dec* d = dec_of(c->x[0]);
    if (!d) { c->x[0] = 0; return; }
    const uint64_t fn = sym("_ZN2nn5codec26GetOpusDecoderChannelCountEPKNS0_15OpusDecoderTypeE");
    uint64_t a[1] = {d->soft};
    c->x[0] = call(c, fn, 1, a);
}
void hle_enqueue(Ctx* c) {   // (decoder, size_t* consumed, void* in, size_t in_size)
    Dec* d = dec_of(c->x[0]);
    const uint64_t consumed_p = c->x[1], in = c->x[2], in_size = c->x[3];
    if (consumed_p && nxrt::mem::is_mapped(consumed_p, 8)) *reinterpret_cast<uint64_t*>(consumed_p) = 0;
    if (!d || !d->m) { c->x[0] = 0x3a6f; return; }
    Mgr* m = d->m;
    if (in_size < 8 || in_size > kMaxPacket || !nxrt::mem::is_mapped(in, in_size)) { c->x[0] = 0x3a6f; return; }
    Req* r = new Req();
    r->n = static_cast<size_t>(in_size);
    std::memcpy(r->data, reinterpret_cast<const void*>(static_cast<uintptr_t>(in)), r->n);
    {
        std::lock_guard lk(m->mu);
        if (m->io_used >= m->io_total) { delete r; c->x[0] = 0x3a6f; return; }
        ++m->io_used;
        ++d->nwait;
        if (d->wait_tail) d->wait_tail->next = r; else d->wait = r;
        d->wait_tail = r;
    }
    if (consumed_p && nxrt::mem::is_mapped(consumed_p, 8)) *reinterpret_cast<uint64_t*>(consumed_p) = in_size;
    c->x[0] = 0;
}

void hle_execute(Ctx* c) {   // (manager): decode every waiting packet on the caller's thread, then signal the event
    Mgr* m = mgr_of(c->x[0]);
    if (!m) { c->x[0] = 0x3a6f; return; }
    const uint64_t dec_fn = sym("_ZN2nn5codec21DecodeOpusInterleavedEPNS0_15OpusDecoderTypeEPmPiPsmPKvm");
    bool any = false;
    {
        std::lock_guard lk(m->mu);
        for (Dec* d : m->dec) {
            while (d->wait) {
                Req* r = d->wait;
                d->wait = r->next;
                if (!d->wait) d->wait_tail = nullptr;
                --d->nwait;
                size_t used = 0;
                int samples = 0;
                uint64_t a[7] = {d->soft, reinterpret_cast<uint64_t>(&used), reinterpret_cast<uint64_t>(&samples),
                                 reinterpret_cast<uint64_t>(r->data), kMaxPcm, reinterpret_cast<uint64_t>(r->data), r->n};
                const uint64_t res = call(c, dec_fn, 7, a);
                if (res || samples <= 0) {   // a refused frame still completes, as 20 ms of silence, so the stream stays in step
                    static std::atomic<int> nred{0};
                    if (nred.fetch_add(1) < 4)
                        NXLOG_W(kTag, "software decode of a %zu-byte packet failed (0x%llx): silence instead", r->n,
                                static_cast<unsigned long long>(res));
                    samples = 960;
                    std::memset(r->data, 0, static_cast<size_t>(samples) * static_cast<size_t>(d->ch) * 2);
                }
                r->samples = samples;
                r->n = static_cast<size_t>(samples) * static_cast<size_t>(d->ch) * 2;
                r->next = nullptr;
                if (d->done_tail) d->done_tail->next = r; else d->done = r;
                d->done_tail = r;
                ++d->ndone;
                any = true;
            }
        }
    }
    if (any && m->event) {
        const uint64_t sig = sym("_ZN2nn2os17SignalSystemEventEPNS0_15SystemEventTypeE");
        uint64_t a[1] = {m->event};
        call(c, sig, 1, a);
    }
    c->x[0] = 0;
}

void hle_dequeue(Ctx* c) {   // (decoder, int* samples, int16_t* out, size_t out_size)
    Dec* d = dec_of(c->x[0]);
    const uint64_t samples_p = c->x[1], out = c->x[2], out_size = c->x[3];
    if (samples_p && nxrt::mem::is_mapped(samples_p, 4)) *reinterpret_cast<int32_t*>(samples_p) = 0;
    if (!d || !d->m) { c->x[0] = 0x3a6f; return; }
    Mgr* m = d->m;
    Req* r = nullptr;
    {
        std::lock_guard lk(m->mu);
        r = d->done;
        if (!r) { c->x[0] = 0x3a6f; return; }
        if (r->n > out_size || !nxrt::mem::is_mapped(out, r->n)) { c->x[0] = 0x3a6f; return; }
        d->done = r->next;
        if (!d->done) d->done_tail = nullptr;
        --d->ndone;
        --m->io_used;
    }
    std::memcpy(reinterpret_cast<void*>(static_cast<uintptr_t>(out)), r->data, r->n);
    if (samples_p && nxrt::mem::is_mapped(samples_p, 4)) *reinterpret_cast<int32_t*>(samples_p) = r->samples;
    delete r;
    c->x[0] = 0;
}

void hle_waiting(Ctx* c) { c->x[0] = static_cast<uint64_t>(dec_count(c->x[0], 0)); }
void hle_executing(Ctx* c) { c->x[0] = 0; }
void hle_completed(Ctx* c) { c->x[0] = static_cast<uint64_t>(dec_count(c->x[0], 2)); }

// Forces an sdk export to a host handler: module_override_symbol makes the imports of that name land in the host, and
// fn_register replaces the sdk's own definition so calls from inside the sdk are caught too.
void force(const char* name, nxrt::HleFn fn) {
    nxrt::hle_register(name, fn);          // the import thunk: module_override_symbol routes every import of the name to it
    nxrt::module_override_symbol(name);
    const uint64_t def = nxrt::nxmodule_find_export(name);
    if (!def) {
        NXLOG_W(kTag, "sdk export %s not found: the hwopus service stays reachable", name);
        return;
    }
    nxrt::fn_register(def, fn);
}
}  // namespace

// Called from xc2_boot.cpp after the modules are registered (XC2_301_OPUS=1).
extern "C" void xc2_opus301_install() {
    force("_ZN2nn5codec43GetHardwareOpusDecoderManagerWorkBufferSizeEiiNS_8TimeSpanEii", hle_mgr_work_size);
    force("_ZN2nn5codec36InitializeHardwareOpusDecoderManagerEPNS0_30HardwareOpusDecoderManagerTypeEPNS_2os15SystemEventTypeEiiNS_8TimeSpanEiiPvm", hle_mgr_init);
    force("_ZN2nn5codec34FinalizeHardwareOpusDecoderManagerEPNS0_30HardwareOpusDecoderManagerTypeE", hle_mgr_fini);
    force("_ZN2nn5codec46GetHardwareOpusDecoderManagerFreeIoBufferCountEPKNS0_30HardwareOpusDecoderManagerTypeE", hle_mgr_free_io);
    force("_ZN2nn5codec29InitializeHardwareOpusDecoderEPNS0_23HardwareOpusDecoderTypeEiiNS_8TimeSpanEPNS0_30HardwareOpusDecoderManagerTypeE", hle_dec_init_mgr);
    force("_ZN2nn5codec27FinalizeHardwareOpusDecoderEPNS0_23HardwareOpusDecoderTypeE", hle_dec_fini);
    force("_ZN2nn5codec24ResetHardwareOpusDecoderEPNS0_23HardwareOpusDecoderTypeE", hle_dec_reset);
    force("_ZN2nn5codec32GetHardwareOpusDecoderSampleRateEPKNS0_23HardwareOpusDecoderTypeE", hle_dec_rate);
    force("_ZN2nn5codec34GetHardwareOpusDecoderChannelCountEPKNS0_23HardwareOpusDecoderTypeE", hle_dec_ch);
    force("_ZN2nn5codec36EnqueueOpusDataToHardwareOpusDecoderEPNS0_23HardwareOpusDecoderTypeEPmPKvm", hle_enqueue);
    force("_ZN2nn5codec34ExecuteHardwareOpusDecoderDecodingEPNS0_30HardwareOpusDecoderManagerTypeE", hle_execute);
    force("_ZN2nn5codec48DequeuePcmInterleavedDataFromHardwareOpusDecoderEPNS0_23HardwareOpusDecoderTypeEPiPsm", hle_dequeue);
    force("_ZN2nn5codec47GetHardwareOpusDecoderWaitingDecodeRequestCountEPKNS0_23HardwareOpusDecoderTypeE", hle_waiting);
    force("_ZN2nn5codec49GetHardwareOpusDecoderExecutingDecodeRequestCountEPKNS0_23HardwareOpusDecoderTypeE", hle_executing);
    force("_ZN2nn5codec49GetHardwareOpusDecoderCompletedDecodeRequestCountEPKNS0_23HardwareOpusDecoderTypeE", hle_completed);
    NXLOG_W(kTag, "hardware Opus entry points replaced by the SDK software OpusDecoder (XC2_301_OPUS)");
}
