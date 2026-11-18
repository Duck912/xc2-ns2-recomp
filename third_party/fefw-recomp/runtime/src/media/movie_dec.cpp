// SPDX-License-Identifier: GPL-3.0-or-later
// movie::Decoder (the Switch 2 SDK's movie decoder, the Android MediaCodec wrapper inside subsdk0) on the host.
//
// The game's player imports movie::VideoDecoder / movie::AudioDecoder; those are implemented by the library in subsdk0, which drives
// movie::Decoder underneath. Replacing VideoDecoder directly leaves the player waiting on a contract only the library keeps (see
// work/MOVIE-FREEZE-NOTES.md), so this file replaces the layer below instead: the library runs unchanged and asks this Decoder for
// input and output buffer indices, exactly as it would ask MediaCodec. The protocol (index-based, four client events, output slots)
// is documented by capibawa/nxnative dm/host/hle_movie.c, which does the same for other NintendoSDK_movie titles.
//
// Entry points are hooked by address (subsdk0 is mapped at a fixed base), not by symbol: main never imports them.
#include <cstdint>
#include <cstring>
#include <mutex>
#include <vector>

#include <windows.h>

#include "nxrt/abi.h"
#include "nxrt/config.h"
#include "nxrt/dispatch.h"
#include "nxrt/game.h"
#include "nxrt/memory.h"
#include "nxrt/log.h"
#include "nxrt/movie_vdec.h"

namespace nxrt::media {
namespace {

#define A(i) (c->x[i])
#define RET(v) (c->x[0] = static_cast<uint64_t>(v))

constexpr const char* kTag = "movie.dec";
constexpr uint64_t kSubsdk0Base = 0x7600000000ull;
constexpr uint32_t kNoInput = 0x1011;
constexpr uint32_t kNoOutput = 0x100e;
constexpr uint32_t kOk = 0;

bool g_log = false;

// The library asks for these with movie::Decoder::RegisterClientEvents: four EventType pointers.
struct ClientEvents {
    uint64_t input, output, format, error;
};

struct HostDecoder {
    std::mutex mu;
    ClientEvents ev{};
    int type = 0, fmt = 0, mode = 0;
    bool started = false;
    uint64_t calls = 0;
};

HostDecoder* dec_of(uint64_t self) { return self ? reinterpret_cast<HostDecoder*>(rd64(self)) : nullptr; }

// Every entry point logs once per kind, so a run with [media] video_decoder = library shows how far the library gets and what it asks
// for before it stops: that list is what the decode bodies are written against.
void note(const char* what, uint64_t self) {
    if (!g_log) return;
    static std::mutex m;
    static std::vector<std::string> seen;
    std::lock_guard<std::mutex> lk(m);
    if (seen.size() > 60) return;
    for (const auto& s : seen)
        if (s == what) return;
    seen.push_back(what);
    NXLOG_I(kTag, "%s (self %llx)", what, static_cast<unsigned long long>(self));
}
void dec_ctor(::Ctx* c) {
    // The library constructs the object, then calls the initialisers: a host object hangs off its first word (as the reference does).
    auto* d = new HostDecoder();
    d->type = static_cast<int>(A(1));
    d->fmt = static_cast<int>(A(2));
    d->mode = static_cast<int>(A(3));
    wr64(A(0), reinterpret_cast<uint64_t>(d));
    note("Decoder::Decoder", A(0));
    RET(0);
}

void dec_configure(::Ctx* c) { note("Decoder::Configure", A(0)); RET(0); }
void dec_register_events(::Ctx* c) {
    HostDecoder* d = dec_of(A(0));
    if (d && A(1) && mem::is_mapped(A(1), 32)) {
        d->ev.input = rd64(A(1));
        d->ev.output = rd64(A(1) + 8);
        d->ev.format = rd64(A(1) + 16);
        d->ev.error = rd64(A(1) + 24);
    }
    note("Decoder::RegisterClientEvents", A(0));
    RET(0);
}
void dec_start(::Ctx* c) { HostDecoder* d = dec_of(A(0)); if (d) d->started = true; note("Decoder::Start", A(0)); RET(0); }
void dec_stop(::Ctx* c) { HostDecoder* d = dec_of(A(0)); if (d) d->started = false; note("Decoder::Stop", A(0)); RET(0); }
void dec_reset(::Ctx* c) { note("Decoder::Reset", A(0)); RET(0); }
void dec_flush(::Ctx* c) { note("Decoder::Flush", A(0)); RET(0); }
void dec_acquire_input(::Ctx* c) { note("Decoder::AcquireInputBufferIndex", A(0)); RET(kNoInput); }
void dec_get_input(::Ctx* c) { note("Decoder::GetInputBuffer", A(0)); RET(kNoInput); }
void dec_send_input(::Ctx* c) { note("Decoder::SendInputBufferForDecode", A(0)); RET(0); }
void dec_acquire_output(::Ctx* c) { note("Decoder::AcquireOutputBufferIndex", A(0)); RET(kNoOutput); }
void dec_get_output(::Ctx* c) { note("Decoder::GetOutputBuffer", A(0)); RET(kNoOutput); }
void dec_output_format(::Ctx* c) { note("Decoder::GetOutputBufferFormat", A(0)); RET(0); }
void dec_output_size(::Ctx* c) { note("Decoder::GetOutputBufferSize", A(0)); RET(0); }
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
        for (const Addr& a : kAddrs) {
            fn_register(kSubsdk0Base + a.off, a.fn);
        }
        ok = true;
        NXLOG_I(kTag, "movie::Decoder hooked on the host: %zu entry points", sizeof kAddrs / sizeof kAddrs[0]);
    });
    return ok;
}

}  // namespace nxrt::media
