// SPDX-License-Identifier: GPL-3.0-or-later
// nn::os fibers on the host: Monolith's job system runs its workers as cooperative fibers, and the SDK's own
// context switch (nn::os::detail::DispatchFiberContext) saves and restores the guest stack and registers inside guest
// code, which a statically recompiled function cannot do (the restored x30 would return into lifted C++ frames).
//
// So the four fiber entry points are replaced by host implementations on Windows fibers (ConvertThreadToFiber /
// CreateFiber / SwitchToFiber). Each guest FiberType* owns one host fiber with its own stack and a saved Ctx; a switch
// copies the guest context out of the current fiber and back in when that fiber is resumed. The guest's own stack
// buffer is used as the SP of the fiber function (the game passes it to InitializeFiber), so guest pushes and calls
// behave as they would on the console.
#include "nxrt/abi.h"
#include "nxrt/dispatch.h"
#include "nxrt/kernel.h"
#include "nxrt/log.h"
#include "nxrt/memory.h"
#include "nxrt/module.h"

#include <windows.h>

#include <atomic>
#include <cstdlib>
#include <mutex>
#include <unordered_map>

namespace nxrt {
namespace {

using FiberStart = void* (*)(void*);

struct HostFiber {
    void* win = nullptr;      // the Windows fiber
    uint64_t guest = 0;       // the guest FiberType* this fiber answers to
    uint64_t fn = 0;          // guest entry (InitializeFiber's function pointer)
    uint64_t arg = 0;
    uint64_t stack_top = 0;   // guest stack the entry runs on
    Ctx ctx{};                // guest context saved while another fiber runs
    HostFiber* caller = nullptr;   // fiber that switched here (returned to when the entry ends)
    bool started = false;
    bool done = false;
};

std::mutex g_lock;
std::unordered_map<uint64_t, HostFiber*> g_by_guest;   // guest FiberType* -> host fiber
thread_local HostFiber* t_current = nullptr;           // the fiber running on this host thread
thread_local HostFiber* t_root = nullptr;              // the thread's original fiber (SwitchToFiber(nullptr) target)

VOID CALLBACK fiber_entry(void* param);

HostFiber* create_host_fiber(HostFiber* self) {
    self->win = ::CreateFiber(0, fiber_entry, self);
    return self;
}

// The thread's current fiber. The first fiber operation of a guest thread converts the host thread into a fiber and
// gives it a guest FiberType* of its own (the game gets it from GetCurrentFiber and switches back to it).
HostFiber* current_or_convert(Ctx* c) {
    if (t_current) return t_current;
    auto* f = new HostFiber();
    f->win = ::ConvertThreadToFiber(nullptr);
    if (!f->win) f->win = ::GetCurrentFiber();
    f->started = true;
    f->ctx = *c;
    // A fake FiberType object in guest memory, so the pointer the game stores and passes back is a guest address.
    const uint64_t box = mem::alloc_kernel(0x100, 16);
    if (box) {
        *reinterpret_cast<uint64_t*>(static_cast<uintptr_t>(box)) = box;   // self pointer, harmless
        f->guest = box;
    } else {
        f->guest = 0xF1BE000000000000ull | static_cast<uint64_t>(GetCurrentThreadId() & 0xffff);
    }
    {
        std::lock_guard<std::mutex> lk(g_lock);
        g_by_guest[f->guest] = f;
    }
    t_current = f;
    if (!t_root) t_root = f;
    return f;
}

VOID CALLBACK fiber_entry(void* param) {
    auto* f = static_cast<HostFiber*>(param);
    t_current = f;
    Ctx* c = kernel::current_ctx();
    *c = f->ctx;
    c->x[0] = f->arg;
    c->x[31] = f->stack_top;
    c->x[30] = 0;
    c->ex_addr = ~0ull;
    NXLOG_I("fiber", "fiber 0x%llx starts (entry 0x%llx, arg 0x%llx, sp 0x%llx)", (unsigned long long)f->guest,
            (unsigned long long)f->fn, (unsigned long long)f->arg, (unsigned long long)f->stack_top);
    dispatch_call(c, f->fn);
    // The entry returned: the guest value is the next fiber to switch to (null: back to the caller and finish).
    const uint64_t next = c->x[0];
    f->done = true;
    f->ctx = *c;
    NXLOG_I("fiber", "fiber 0x%llx returned 0x%llx", (unsigned long long)f->guest, (unsigned long long)next);
    HostFiber* back = f->caller;
    if (next) {
        HostFiber* tgt = nullptr;
        {
            std::lock_guard<std::mutex> lk(g_lock);
            auto it = g_by_guest.find(next);
            if (it != g_by_guest.end()) tgt = it->second;
        }
        if (tgt && tgt->win) {
            tgt->caller = back;
            ::SwitchToFiber(tgt->win);
        }
    }
    if (back && back->win) ::SwitchToFiber(back->win);
    for (;;) ::SwitchToFiber(::GetCurrentFiber());   // nothing left to run here
}

// nn::os::InitializeFiber(FiberType* fiber, FiberType* (*fn)(void*), void* arg, void* stack, size_t size, int prio)
void hle_initialize_fiber(Ctx* c) {
    const uint64_t guest = c->x[0], fn = c->x[1], arg = c->x[2], stack = c->x[3], size = c->x[4];
    auto* f = new HostFiber();
    f->guest = guest;
    f->fn = fn;
    f->arg = arg;
    f->stack_top = (stack + size) & ~static_cast<uint64_t>(15);
    f->ctx = *c;                       // the same thread: TPIDRRO/TPIDR and FPCR come from the creating thread
    f->ctx.x[30] = 0;
    f->ctx.ex_addr = ~0ull;
    create_host_fiber(f);
    {
        std::lock_guard<std::mutex> lk(g_lock);
        g_by_guest[guest] = f;
    }
    NXLOG_I("fiber", "InitializeFiber(0x%llx, entry 0x%llx, stack 0x%llx+0x%llx)", (unsigned long long)guest,
            (unsigned long long)fn, (unsigned long long)stack, (unsigned long long)size);
    c->x[0] = 0;
}

// nn::os::FinalizeFiber(FiberType* fiber)
void hle_finalize_fiber(Ctx* c) {
    HostFiber* f = nullptr;
    {
        std::lock_guard<std::mutex> lk(g_lock);
        auto it = g_by_guest.find(c->x[0]);
        if (it != g_by_guest.end()) {
            f = it->second;
            g_by_guest.erase(it);
        }
    }
    if (f && f->win && !f->started && f != t_current) ::DeleteFiber(f->win);
    c->x[0] = 0;
}

// nn::os::SwitchToFiber(FiberType* fiber)
void hle_switch_to_fiber(Ctx* c) {
    HostFiber* cur = current_or_convert(c);
    HostFiber* tgt = nullptr;
    if (c->x[0] == 0) {
        tgt = t_root;                    // SwitchToFiber(nullptr): back to the thread's root fiber
    } else {
        std::lock_guard<std::mutex> lk(g_lock);
        auto it = g_by_guest.find(c->x[0]);
        if (it != g_by_guest.end()) tgt = it->second;
    }
    if (!tgt) {
        NXLOG_W("fiber", "SwitchToFiber(0x%llx): unknown fiber", (unsigned long long)c->x[0]);
        c->x[0] = 0;
        return;
    }
    cur->ctx = *c;
    if (tgt == cur) { c->x[0] = 0; return; }
    tgt->caller = cur;
    NXLOG_D("fiber", "switch 0x%llx -> 0x%llx", (unsigned long long)cur->guest, (unsigned long long)tgt->guest);
    // t_current must follow the switch: GetCurrentFiber reads it, and the game skips a switch whose target is the fiber it
    // thinks it is on. Leaving it on the fiber we switched to made every later switch a no-op (the build microthread
    // never ran again, so the launcher never built its applet).
    t_current = tgt;
    ::SwitchToFiber(tgt->win);
    t_current = cur;                 // resumed here: this fiber is current again
    *c = cur->ctx;
    c->x[0] = 0;
}

// nn::os::GetCurrentFiber()
void hle_get_current_fiber(Ctx* c) {
    HostFiber* cur = current_or_convert(c);
    c->x[0] = cur ? cur->guest : 0;
    if (std::getenv("NXRT_FIBER_TRACE")) {
        static std::atomic<unsigned> n{0};
        const unsigned k = ++n;
        if (k <= 20 || (k % 5000) == 0)
            NXLOG_I("fiber", "GetCurrentFiber #%u -> 0x%llx (this fiber 0x%llx)", k, (unsigned long long)c->x[0],
                    (unsigned long long)(cur ? cur->guest : 0));
    }
}

}  // namespace

void install_fiber_hle() {
    struct { const char* name; HleFn fn; } const items[] = {
        {"_ZN2nn2os15InitializeFiberEPNS0_9FiberTypeEPFS2_PvES3_S3_mi", hle_initialize_fiber},
        {"_ZN2nn2os13FinalizeFiberEPNS0_9FiberTypeE", hle_finalize_fiber},
        {"_ZN2nn2os13SwitchToFiberEPNS0_9FiberTypeE", hle_switch_to_fiber},
        {"_ZN2nn2os15GetCurrentFiberEv", hle_get_current_fiber},
    };
    for (auto& it : items) {
        hle_register(it.name, it.fn);
        module_override_symbol(it.name);
    }
    NXLOG_I("fiber", "nn::os fibers answered on the host (%zu entry points)", sizeof items / sizeof items[0]);
}

// Bring-up: every guest fiber the host knows, with the LR/SP it will resume at (a suspended fiber's LR is the guest
// address it stopped in). Answers "which fiber is asleep and where" without a debugger.
void fiber_dump(void (*cb)(void* user, uint64_t guest, uint64_t fn, uint64_t lr, uint64_t sp, int state), void* user) {
    std::lock_guard<std::mutex> lk(g_lock);
    for (auto& [guest, f] : g_by_guest) {
        if (!f) continue;
        const int state = f->done ? 2 : f->started ? 1 : 0;   // 0 not started, 1 suspended, 2 finished
        cb(user, guest, f->fn, f->ctx.x[30], f->ctx.x[31], state);
    }
}

}  // namespace nxrt



