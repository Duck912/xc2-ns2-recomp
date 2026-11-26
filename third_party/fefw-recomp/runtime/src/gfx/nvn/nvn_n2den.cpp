// SPDX-License-Identifier: GPL-3.0-or-later
// nvn_n2den.h: n2den's NVN-HLE (embed.h) behind nvn::proc_address. Each NVN function the game fetches by
// name gets one of a fixed table of trampolines; a trampoline copies the guest registers into
// N2denNvnhle::GuestRegisters, runs the n2den function and copies the results back.
#include "nxrt/nvn_n2den.h"

#ifdef NXRT_HAVE_N2DEN

#include <algorithm>
#include <array>
#include <atomic>
#include <cstring>
#include <mutex>
#include <string>
#include <unordered_map>
#include <utility>

#include <windows.h>

#include "nvnhle/embed.h"
#include "nxrt/abi.h"
#include "nxrt/dispatch.h"
#include "nxrt/kernel.h"
#include "nxrt/log.h"
#include "nxrt/memory.h"
#include "nxrt/nvn.h"

namespace nxrt::nvn::n2den {
namespace {

constexpr const char* kTag = "nvn.n2den";
constexpr size_t kSlots = 1024;  // more than the NVN2 function table (n2den implements ~650)

std::array<std::atomic<int32_t>, kSlots> g_ids{};
std::atomic<bool> g_active{false};
std::mutex g_mu;
std::unordered_map<std::string, uint64_t> g_addresses;  // name -> thunk address
size_t g_next_slot = 0;

template <size_t I>
void Trampoline(::Ctx* c) {
    N2denNvnhle::GuestRegisters r;
    static_assert(sizeof(r.x) == sizeof(c->x) && sizeof(r.v) == sizeof(c->v));
    std::memcpy(r.x, c->x, sizeof(r.x));
    std::memcpy(r.v, c->v, sizeof(r.v));
    N2denNvnhle::Call(g_ids[I].load(std::memory_order_relaxed), r);
    std::memcpy(c->x, r.x, sizeof(uint64_t) * 31);  // x0..x30; sp (x[31]) is the caller's
    std::memcpy(c->v, r.v, sizeof(r.v));
}

template <size_t... I>
constexpr std::array<HleFn, sizeof...(I)> MakeTable(std::index_sequence<I...>) {
    return {&Trampoline<I>...};
}
const std::array<HleFn, kSlots> g_table = MakeTable(std::make_index_sequence<kSlots>{});

uint64_t Resolve(const char* name) {
    if (!g_active.load(std::memory_order_acquire) || name == nullptr) return 0;
    std::lock_guard<std::mutex> lk(g_mu);
    if (auto it = g_addresses.find(name); it != g_addresses.end()) return it->second;
    const int32_t id = N2denNvnhle::FindFunction(name);
    if (id < 0) {
        NXLOG_W(kTag, "n2den has no %s: the runtime's own answer is used", name);
        g_addresses.emplace(name, 0);
        return 0;
    }
    if (g_next_slot >= kSlots) {
        NXLOG_E(kTag, "out of trampolines at %s", name);
        return 0;
    }
    const size_t slot = g_next_slot++;
    g_ids[slot].store(id, std::memory_order_relaxed);
    const std::string thunk_name = std::string{"n2den/"} + name;
    const uint64_t address = hle_register(thunk_name.c_str(), g_table[slot]);
    g_addresses.emplace(name, address);
    return address;
}

uint64_t ClockTicks(void*) { return kernel::system_tick(); }
uint64_t TimeNs(void*) {
    const uint64_t t = kernel::system_tick(), hz = kernel::tick_hz();
    return (t / hz) * 1'000'000'000ull + (t % hz) * 1'000'000'000ull / hz;
}
void SleepNs(void*, int64_t ns) { kernel::sleep_ns(ns); }

// A small private view of heap pages (mem::heap_private_view, as this runtime's own pool import does): the
// driver then walks only that mapping when n2den imports a pool (EDEN_NVN_ALIAS_IMPORT=1).
void* MapView(void*, uint64_t address, uint64_t size, void** view) {
    if (!mem::heap_has_section() || address < mem::kHeapBase) return nullptr;
    const uint64_t soff = address - mem::kHeapBase;
    if (soff + size > mem::heap_reserved()) return nullptr;
    const uint64_t voff = soff & ~(mem::kAllocGranularity - 1);
    const uint64_t delta = soff - voff;
    const uint64_t vsize = (delta + size + mem::kAllocGranularity - 1) & ~(mem::kAllocGranularity - 1);
    void* v = mem::heap_private_view(voff, std::min<uint64_t>(vsize, mem::heap_reserved() - voff));
    if (!v) return nullptr;
    *view = v;
    return static_cast<uint8_t*>(v) + delta;
}
void UnmapView(void*, void* view) { mem::heap_private_view_unmap(view); }

}  // namespace

bool available() { return true; }

bool start(const StartDesc& desc, std::string* error) {
    N2denNvnhle::StartInfo info;
    info.native_window = desc.native_window;
    info.width = desc.width;
    info.height = desc.height;
    info.program_id = desc.program_id;
    info.sdk_image = desc.sdk_image;
    info.sdk_image_size = desc.sdk_image_size;
    // Never n2den's own %APPDATA% folder: its settings, caches and log stay with this executable.
    std::string data_dir = desc.data_directory;
    if (data_dir.empty()) {
        char exe[MAX_PATH] = {};
        const DWORD n = ::GetModuleFileNameA(nullptr, exe, MAX_PATH);
        std::string dir(exe, n);
        const size_t slash = dir.find_last_of("\\/");
        data_dir = (slash == std::string::npos ? std::string{"."} : dir.substr(0, slash)) + "\\user";
    }
    info.data_directory = data_dir.c_str();
    info.host.guest_clock_ticks = ClockTicks;
    info.host.guest_time_ns = TimeNs;
    info.host.sleep_guest_ns = SleepNs;
    info.host.map_view = MapView;
    info.host.unmap_view = UnmapView;
    std::string err;
    if (!N2denNvnhle::Start(info, &err)) {
        NXLOG_E(kTag, "n2den NVN-HLE failed to start: %s", err.c_str());
        if (error) *error = err;
        return false;
    }
    g_active.store(true, std::memory_order_release);
    set_proc_resolver(&Resolve);
    NXLOG_I(kTag, "n2den NVN-HLE started: %zu NVN functions, %ux%u", N2denNvnhle::FunctionCount(), desc.width, desc.height);
    return true;
}

void stop() {
    if (!g_active.exchange(false)) return;
    set_proc_resolver(nullptr);
    N2denNvnhle::Stop();
}

bool active() { return g_active.load(std::memory_order_acquire); }

void resize(uint32_t width, uint32_t height) {
    if (active()) N2denNvnhle::Resize(width, height);
}

void notify_cpu_write(uint64_t address, uint64_t size) {
    if (active()) N2denNvnhle::NotifyCpuWrite(address, size);
}

}  // namespace nxrt::nvn::n2den

#else  // NXRT_HAVE_N2DEN

namespace nxrt::nvn::n2den {
bool available() { return false; }
bool start(const StartDesc&, std::string* error) {
    if (error) *error = "this runtime was built without n2den's NVN-HLE (configure with NXRT_N2DEN_DIST)";
    return false;
}
void stop() {}
bool active() { return false; }
void resize(uint32_t, uint32_t) {}
void notify_cpu_write(uint64_t, uint64_t) {}
}  // namespace nxrt::nvn::n2den

#endif  // NXRT_HAVE_N2DEN
