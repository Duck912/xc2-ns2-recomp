// SPDX-License-Identifier: GPL-3.0-or-later
// [media] player_trace = 1: pass-through logging of the nn::os calls the movie player's frame loop is built from.
//
// The player's per-frame state machine (main f_7100722460) blocks in nn::os::ReceiveMessageQueue(player+0x1E0). A frame is
// acquired when the decoder's output-ready handler posts message 2, and processed/released when the per-frame periodic timer
// (player+0x888) posts message 9 (f_7100722ff0: ClearTimerEvent then SendMessageQueue). With the library's own VideoDecoder the
// codec side is healthy (876 packets decoded, 0 errors) yet the player reads exactly four pictures and stops, so the question is
// whether message 9 ever arrives, and whether the timer fires at all.
//
// The wrappers replace the imports (module_override_symbol, set before the modules are linked) and call the SDK's own function;
// then they log one line: queue and message value with the guest return address, or the timer with its interval. A receive is
// logged once its queue has been seen carrying a message, so unrelated queues do not drown the movie's.

#include <atomic>
#include <cstdint>
#include <cstring>
#include <mutex>
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
// main is lifted at 0x7100000000; the player's timer thread and state machine live there, while the SDK's own timer use has an
// LR in the sdk (0x7500...). Timer lines are noise unless they come from the player.
bool from_main(uint64_t lr) { return lr >= 0x7100000000ull && lr < 0x7180000000ull; }

constexpr const char* kSend = "_ZN2nn2os16SendMessageQueueEPNS0_16MessageQueueTypeEm";
constexpr const char* kRecv = "_ZN2nn2os19ReceiveMessageQueueEPmPNS0_16MessageQueueTypeE";
constexpr const char* kStartTimer = "_ZN2nn2os23StartPeriodicTimerEventEPNS0_14TimerEventTypeENS_8TimeSpanES3_";
constexpr const char* kStopTimer = "_ZN2nn2os14StopTimerEventEPNS0_14TimerEventTypeE";
constexpr const char* kWaitTimer = "_ZN2nn2os14WaitTimerEventEPNS0_14TimerEventTypeE";
constexpr const char* kClearTimer = "_ZN2nn2os15ClearTimerEventEPNS0_14TimerEventTypeE";

bool g_on = false;
std::atomic<uint32_t> g_send_n{0}, g_recv_n{0}, g_timer_n{0};
std::mutex g_q_mu;
std::vector<uint64_t> g_queues;   // queues that have carried a message

// Calls the SDK's own function and puts back the two guest fields the dispatcher keeps (the function entered, the return address).
uint64_t call_original(::Ctx* c, uint64_t fn) {
    const uint64_t lr = c->x[30], f = c->fn;
    dispatch_call(c, fn);
    const uint64_t r = c->x[0];
    c->x[30] = lr;
    c->fn = f;
    return r;
}

bool interesting_queue(uint64_t q) {
    std::lock_guard<std::mutex> lk(g_q_mu);
    for (uint64_t v : g_queues)
        if (v == q) return true;
    return false;
}
void note_queue(uint64_t q) {
    std::lock_guard<std::mutex> lk(g_q_mu);
    for (uint64_t v : g_queues)
        if (v == q) return;
    if (g_queues.size() < 16) g_queues.push_back(q);
}

uint64_t fn_send() { static const uint64_t f = module_find_symbol(kSend); return f; }
uint64_t fn_recv() { static const uint64_t f = module_find_symbol(kRecv); return f; }
uint64_t fn_start() { static const uint64_t f = module_find_symbol(kStartTimer); return f; }
uint64_t fn_stop() { static const uint64_t f = module_find_symbol(kStopTimer); return f; }
uint64_t fn_wait() { static const uint64_t f = module_find_symbol(kWaitTimer); return f; }
uint64_t fn_clear() { static const uint64_t f = module_find_symbol(kClearTimer); return f; }

void send_msg(::Ctx* c) {   // (nn::os::MessageQueueType*, u64 value) -> nn::Result
    const uint64_t q = A(0), v = A(1), lr = c->x[30];
    const uint64_t fn = fn_send();
    if (!fn) { NXLOG_E(kTag, "[media] player_trace: nn::os::SendMessageQueue not found"); A(0) = 0; return; }
    const uint64_t r = call_original(c, fn);
    if (g_on) {
        note_queue(q);
        const uint32_t n = g_send_n.fetch_add(1, std::memory_order_relaxed);
        // The player's messages are its state codes (0..11): log those, plus the first few of anything else.
        if (n < 6 || (v <= 32 && n < 240)) NXLOG_I(kTag, "msg send: queue 0x%llx <- %llu, lr 0x%llx, -> 0x%llx", q, v, lr, r);
    }
    A(0) = r;
}
void recv_msg(::Ctx* c) {   // (u64* out, nn::os::MessageQueueType*) -> nn::Result (blocks)
    const uint64_t out = A(0), q = A(1), lr = c->x[30];
    const uint64_t fn = fn_recv();
    if (!fn) { NXLOG_E(kTag, "[media] player_trace: nn::os::ReceiveMessageQueue not found"); A(0) = 0; return; }
    const uint64_t r = call_original(c, fn);
    if (g_on && interesting_queue(q)) {
        uint64_t v = 0;
        if (out && mem::is_mapped(out, 8)) std::memcpy(&v, reinterpret_cast<const void*>(out), 8);
        const uint32_t n = g_recv_n.fetch_add(1, std::memory_order_relaxed);
        if (n < 200) NXLOG_I(kTag, "msg recv: queue 0x%llx -> %llu, lr 0x%llx, result 0x%llx", q, v, lr, r);
    }
    A(0) = r;
}
void start_timer(::Ctx* c) {   // (TimerEventType*, TimeSpan first, TimeSpan period)
    const uint64_t t = A(0), i1 = A(1), i2 = A(2), lr = c->x[30];
    const uint64_t fn = fn_start();
    if (!fn) { A(0) = 0; return; }
    const uint64_t r = call_original(c, fn);
    const uint32_t n = g_timer_n.fetch_add(1, std::memory_order_relaxed);
    if (g_on && (from_main(lr) || n < 6))
        NXLOG_I(kTag, "timer start: 0x%llx, first %lld ns, period %lld ns, lr 0x%llx, -> 0x%llx", t, (long long)i1, (long long)i2, lr, r);
    A(0) = r;
}
void stop_timer(::Ctx* c) {
    const uint64_t t = A(0), lr = c->x[30];
    const uint64_t fn = fn_stop();
    if (!fn) { A(0) = 0; return; }
    const uint64_t r = call_original(c, fn);
    const uint32_t n = g_timer_n.fetch_add(1, std::memory_order_relaxed);
    if (g_on && (from_main(lr) || n < 6)) NXLOG_I(kTag, "timer stop: 0x%llx, lr 0x%llx", t, lr);
    A(0) = r;
}
void wait_timer(::Ctx* c) {   // (TimerEventType*): blocks until the timer fires
    const uint64_t t = A(0), lr = c->x[30];
    const uint64_t fn = fn_wait();
    if (!fn) return;
    const uint32_t n = g_on ? g_timer_n.fetch_add(1, std::memory_order_relaxed) : ~0u;
    const bool log = g_on && (from_main(lr) || n < 6);
    if (log) NXLOG_I(kTag, "timer wait: 0x%llx, lr 0x%llx", t, lr);
    call_original(c, fn);
    if (log) NXLOG_I(kTag, "timer wait: 0x%llx returned", t);
}
void clear_timer(::Ctx* c) {
    const uint64_t t = A(0), lr = c->x[30];
    const uint64_t fn = fn_clear();
    if (!fn) { A(0) = 0; return; }
    const uint64_t r = call_original(c, fn);
    const uint32_t n = g_timer_n.fetch_add(1, std::memory_order_relaxed);
    if (g_on && (from_main(lr) || n < 6)) NXLOG_I(kTag, "timer clear: 0x%llx, lr 0x%llx", t, lr);
    A(0) = r;
}

struct Entry {
    const char* name;
    HleFn fn;
};
const Entry kEntries[] = {
    {kSend, send_msg},       {kRecv, recv_msg},     {kStartTimer, start_timer},
    {kStopTimer, stop_timer}, {kWaitTimer, wait_timer}, {kClearTimer, clear_timer},
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
        NXLOG_I(kTag, "[media] player_trace: %zu nn::os message-queue / timer entry points logged", sizeof kEntries / sizeof kEntries[0]);
    });
}

}  // namespace nxrt::media
