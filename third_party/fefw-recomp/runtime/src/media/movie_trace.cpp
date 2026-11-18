// SPDX-License-Identifier: GPL-3.0-or-later
// [media] player_trace = 1: pass-through logging of the nn::os calls the movie player's frame loop is built from.
//
// The player is four main threads (created at 36.9 s: MoviePlayerThread, MovieEventHandler, AudioHandler, RenderThread):
// RenderThread is the per-frame state machine (main f_7100722460). It blocks in nn::os::ReceiveMessageQueue(player+0x1E0),
// takes a frame when the decoder's output-ready handler posts message 2, and starts the per-frame periodic timer
// (player+0x888, StartPeriodicTimerEvent) when something posts message 8. MovieEventHandler runs a MultiWait loop
// (nn::os::WaitAny, f_7100724c20) with that timer linked into it; the timer's handler clears it and posts message 9, which is
// how the state machine processes and releases a frame.
//
// With the library's own VideoDecoder the codec side is healthy (997 packets decoded, EOS) yet the player reads one picture and
// stops, and no ClearTimerEvent is ever called. These wrappers answer where that chain stops: each import is redirected here and
// then calls the SDK's own function. Message lines are capped per (queue, value) so the audio handler's burst cannot hide the
// video queue's later messages; timer lines come from the player only (the game's own 5 ms timer is in main's data, not the heap).

#include <atomic>
#include <cstdint>
#include <cstring>
#include <mutex>
#include <unordered_map>
#include <vector>

#include "nxrt/abi.h"
#include "nxrt/config.h"
#include "nxrt/dispatch.h"
#include "nxrt/log.h"
#include "nxrt/memory.h"
#include "nxrt/module.h"

namespace nxrt::media {
namespace {

#define A(i) (c->x[i])

constexpr const char* kTag = "player";

constexpr const char* kSend = "_ZN2nn2os16SendMessageQueueEPNS0_16MessageQueueTypeEm";
constexpr const char* kRecv = "_ZN2nn2os19ReceiveMessageQueueEPmPNS0_16MessageQueueTypeE";
constexpr const char* kStartTimer = "_ZN2nn2os23StartPeriodicTimerEventEPNS0_14TimerEventTypeENS_8TimeSpanES3_";
constexpr const char* kStopTimer = "_ZN2nn2os14StopTimerEventEPNS0_14TimerEventTypeE";
constexpr const char* kWaitTimer = "_ZN2nn2os14WaitTimerEventEPNS0_14TimerEventTypeE";
constexpr const char* kClearTimer = "_ZN2nn2os15ClearTimerEventEPNS0_14TimerEventTypeE";
constexpr const char* kWaitAny = "_ZN2nn2os7WaitAnyEPNS0_13MultiWaitTypeE";
constexpr const char* kHolderTimer = "_ZN2nn2os25InitializeMultiWaitHolderEPNS0_19MultiWaitHolderTypeEPNS0_14TimerEventTypeE";

bool g_on = false;
std::mutex g_seen_mu;
std::unordered_map<uint64_t, uint32_t> g_send_seen, g_recv_seen, g_any_seen, g_holder_seen;

// Logs at most `cap` lines per key (a queue and message value, a holder, a timer), so a busy queue cannot use the budget of
// the one that matters.
bool seen(std::unordered_map<uint64_t, uint32_t>& m, uint64_t key, uint32_t cap) {
    std::lock_guard<std::mutex> lk(g_seen_mu);
    uint32_t& n = m[key];
    if (n >= cap) return false;
    ++n;
    return true;
}

// Calls the SDK's own function and puts back the two guest fields the dispatcher keeps (the function entered, the return address).
uint64_t call_original(::Ctx* c, uint64_t fn) {
    const uint64_t lr = c->x[30], f = c->fn;
    dispatch_call(c, fn);
    const uint64_t r = c->x[0];
    c->x[30] = lr;
    c->fn = f;
    return r;
}

bool from_main(uint64_t lr) { return lr >= 0x7100000000ull && lr < 0x7180000000ull; }
// main's own data lives at 0x7100...-0x7102...: its 5 ms timer is there and would otherwise log twice per tick. The player's
// timer events are guest heap objects.
bool heap_address(uint64_t a) { return a >= 0x2c00000000ull && a < 0x4000000000ull; }

uint64_t fn_send() { static const uint64_t f = module_find_symbol(kSend); return f; }
uint64_t fn_recv() { static const uint64_t f = module_find_symbol(kRecv); return f; }
uint64_t fn_start() { static const uint64_t f = module_find_symbol(kStartTimer); return f; }
uint64_t fn_stop() { static const uint64_t f = module_find_symbol(kStopTimer); return f; }
uint64_t fn_wait() { static const uint64_t f = module_find_symbol(kWaitTimer); return f; }
uint64_t fn_clear() { static const uint64_t f = module_find_symbol(kClearTimer); return f; }
uint64_t fn_wait_any() { static const uint64_t f = module_find_symbol(kWaitAny); return f; }
uint64_t fn_holder_timer() { static const uint64_t f = module_find_symbol(kHolderTimer); return f; }

void send_msg(::Ctx* c) {   // (nn::os::MessageQueueType*, u64 value) -> nn::Result
    const uint64_t q = A(0), v = A(1), lr = c->x[30];
    const uint64_t fn = fn_send();
    if (!fn) { NXLOG_E(kTag, "[media] player_trace: nn::os::SendMessageQueue not found"); A(0) = 0; return; }
    const uint64_t r = call_original(c, fn);
    if (g_on && seen(g_send_seen, (q << 8) ^ (v & 0xff), 40))
        NXLOG_I(kTag, "msg send: queue 0x%llx <- %llu, lr 0x%llx, -> 0x%llx", q, v, lr, r);
    A(0) = r;
}
void recv_msg(::Ctx* c) {   // (u64* out, nn::os::MessageQueueType*) -> nn::Result (blocks)
    const uint64_t out = A(0), q = A(1), lr = c->x[30];
    const uint64_t fn = fn_recv();
    if (!fn) { NXLOG_E(kTag, "[media] player_trace: nn::os::ReceiveMessageQueue not found"); A(0) = 0; return; }
    const uint64_t r = call_original(c, fn);
    if (g_on) {
        uint64_t v = 0;
        if (out && mem::is_mapped(out, 8)) std::memcpy(&v, reinterpret_cast<const void*>(out), 8);
        if (seen(g_recv_seen, (q << 8) ^ (v & 0xff), 40))
            NXLOG_I(kTag, "msg recv: queue 0x%llx -> %llu, lr 0x%llx, result 0x%llx", q, v, lr, r);
    }
    A(0) = r;
}
void start_timer(::Ctx* c) {   // (TimerEventType*, TimeSpan first, TimeSpan period)
    const uint64_t t = A(0), i1 = A(1), i2 = A(2), lr = c->x[30];
    const uint64_t fn = fn_start();
    if (!fn) { A(0) = 0; return; }
    const uint64_t r = call_original(c, fn);
    if (g_on && (from_main(lr) || heap_address(t)) && seen(g_holder_seen, t, 20))
        NXLOG_I(kTag, "timer start: 0x%llx, first %lld ns, period %lld ns, lr 0x%llx, -> 0x%llx", t, (long long)i1, (long long)i2, lr, r);
    A(0) = r;
}
void stop_timer(::Ctx* c) {
    const uint64_t t = A(0), lr = c->x[30];
    const uint64_t fn = fn_stop();
    if (!fn) { A(0) = 0; return; }
    const uint64_t r = call_original(c, fn);
    if (g_on && seen(g_holder_seen, t ^ 1, 20)) NXLOG_I(kTag, "timer stop: 0x%llx, lr 0x%llx", t, lr);
    A(0) = r;
}
void wait_timer(::Ctx* c) {   // (TimerEventType*): blocks until the timer fires
    const uint64_t t = A(0), lr = c->x[30];
    const uint64_t fn = fn_wait();
    if (!fn) return;
    const bool log = g_on && !(t >= 0x7100000000ull && t < 0x7200000000ull) && seen(g_holder_seen, t ^ 2, 20);
    if (log) NXLOG_I(kTag, "timer wait: 0x%llx, lr 0x%llx", t, lr);
    call_original(c, fn);
    if (log) NXLOG_I(kTag, "timer wait: 0x%llx returned", t);
}
void clear_timer(::Ctx* c) {
    const uint64_t t = A(0), lr = c->x[30];
    const uint64_t fn = fn_clear();
    if (!fn) { A(0) = 0; return; }
    const uint64_t r = call_original(c, fn);
    if (g_on && seen(g_holder_seen, t ^ 3, 20)) NXLOG_I(kTag, "timer clear: 0x%llx, lr 0x%llx", t, lr);
    A(0) = r;
}
void holder_timer(::Ctx* c) {   // (MultiWaitHolderType*, TimerEventType*)
    const uint64_t h = A(0), t = A(1), lr = c->x[30];
    const uint64_t fn = fn_holder_timer();
    if (!fn) { A(0) = 0; return; }
    const uint64_t r = call_original(c, fn);
    if (g_on && seen(g_holder_seen, (h << 8) ^ (t & 0xff), 20))
        NXLOG_I(kTag, "MultiWaitHolder(timer): holder 0x%llx <- timer 0x%llx, lr 0x%llx", h, t, lr);
    A(0) = r;
}
void wait_any(::Ctx* c) {   // (MultiWaitType*) -> MultiWaitHolder*
    const uint64_t m = A(0), lr = c->x[30];
    const uint64_t fn = fn_wait_any();
    if (!fn) { A(0) = 0; return; }
    const uint64_t r = call_original(c, fn);
    if (g_on && seen(g_any_seen, r, 20))
        NXLOG_I(kTag, "WaitAny: multi 0x%llx -> holder 0x%llx, lr 0x%llx", m, r, lr);
    A(0) = r;
}

struct Entry {
    const char* name;
    HleFn fn;
};
const Entry kEntries[] = {
    {kSend, send_msg},        {kRecv, recv_msg},           {kStartTimer, start_timer},   {kStopTimer, stop_timer},
    {kWaitTimer, wait_timer}, {kClearTimer, clear_timer},  {kWaitAny, wait_any},         {kHolderTimer, holder_timer},
};

}  // namespace

// Called from install_video_codec_hle before the modules are linked: every import of these names then lands here.
void install_player_trace() {
    static std::once_flag once;
    std::call_once(once, [] {
        g_on = config_get_bool("media", "player_trace", false);
        if (!g_on) return;
        for (const Entry& e : kEntries) {
            hle_register(e.name, e.fn);
            module_override_symbol(e.name);
        }
        NXLOG_I(kTag, "[media] player_trace: %zu nn::os message-queue / timer / MultiWait entry points logged",
                sizeof kEntries / sizeof kEntries[0]);
    });
}

}  // namespace nxrt::media
