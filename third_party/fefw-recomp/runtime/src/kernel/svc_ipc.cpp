// SPDX-License-Identifier: GPL-3.0-or-later
// IPC SVCs: ConnectToNamedPort (0x1F), SendSyncRequest (0x21), SendSyncRequestWithUserBuffer (0x22). Calling convention: svc.h.
#include <windows.h>

#include "nxrt/config.h"
#include "nxrt/ipc.h"
#include "nxrt/kernel.h"
#include "nxrt/log.h"
#include "nxrt/memory.h"
#include "nxrt/svc.h"

namespace nxrt {
namespace {

constexpr uint64_t kTlsMessageBytes = 0x100;   // the message buffer at TPIDRRO_EL0 is 0x100 bytes

// ConnectToNamedPort(const char* name) -> (result, handle in x1). The name is read up to 12 bytes.
void svc_connect_to_named_port(::Ctx* c) {
    uint32_t h = 0;
    const uint32_t rc = ipc::connect_named_port(reinterpret_cast<const char*>(static_cast<uintptr_t>(c->x[1])), &h);
    c->x[1] = h;
    svc_ret(c, rc);
}

// [kernel] ipc_log = 1: every request a guest thread sends, and whether it came back. A request that is logged without its reply
// is where the caller is stuck (the movie player waits for one per frame, measured 2026-11-18).
void log_ipc(const char* what, uint32_t session, uint64_t msg, uint32_t rc, uint32_t thread, int64_t ms) {
    static const bool on = ::nxrt::config_get_bool("kernel", "ipc_log", false);
    if (!on) return;
    uint32_t type = 0, cmd = 0xffffffffu;
    if (msg && ::nxrt::mem::is_mapped(msg, 16)) {
        type = *reinterpret_cast<const uint32_t*>(static_cast<uintptr_t>(msg));
        cmd = *reinterpret_cast<const uint32_t*>(static_cast<uintptr_t>(msg + 8));
    }
    NXLOG_I("ipc", "%s session %x thread %u type %u cmd %u rc 0x%x after %lld ms", what, session, thread, type, cmd, rc,
            static_cast<long long>(ms));
}

// SendSyncRequest(Handle session) with the request in the calling thread's TLS message buffer (TPIDRRO_EL0).
void svc_send_sync_request(::Ctx* c) {
    const uint32_t session = static_cast<uint32_t>(c->x[0]);
    const uint64_t msg = c->tpidrro;
    const int64_t t0 = static_cast<int64_t>(GetTickCount64());
    log_ipc("send", session, msg, 0, 0, 0);
    const uint32_t rc = ipc::send_sync_request(c, session, msg, kTlsMessageBytes);
    log_ipc("done", session, msg, rc, 0, static_cast<int64_t>(GetTickCount64()) - t0);
    svc_ret(c, rc);
}

// SendSyncRequestWithUserBuffer(void* buffer, size_t size, Handle session).
void svc_send_sync_request_with_user_buffer(::Ctx* c) {
    const uint32_t session = static_cast<uint32_t>(c->x[2]);
    svc_ret(c, ipc::send_sync_request(c, session, c->x[0], c->x[1]));
}

}  // namespace

void svc_register_ipc_group() {
    svc_register(0x1F, svc_connect_to_named_port);
    svc_register(0x21, svc_send_sync_request);
    svc_register(0x22, svc_send_sync_request_with_user_buffer);
}

}  // namespace nxrt
