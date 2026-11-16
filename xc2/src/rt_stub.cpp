// SPDX-License-Identifier: GPL-3.0-or-later
// Minimal stand-in for the runtime half of the nxrecomp ABI.
//
// The lifted code references these functions but the scaffold does not run guest code yet, so every one of them is a
// diagnostic abort. Their purpose here is to satisfy the link and to make the next step (running `main`'s entry inside
// a real runtime, or inside the FEFW fork) a matter of replacing this file, not of changing the build.
#include <nxrecomp/ctx.h>

#include <cstdio>
#include <cstdlib>

static void unimplemented(const char *what, unsigned long long a, unsigned long long b) {
    std::fprintf(stderr, "rt-stub: %s called (0x%llx, 0x%llx): no runtime in this build\n", what, a, b);
    std::abort();
}

extern "C" {

void call_indirect(Ctx *c, uint64_t addr) { unimplemented("call_indirect", addr, c ? c->fn : 0); }
void host_import(Ctx *c, uint32_t import_id) { unimplemented("host_import", import_id, c ? c->fn : 0); }
void guest_trap(const char *what, uint64_t addr) {
    std::fprintf(stderr, "rt-stub: guest_trap: %s at 0x%llx\n", what ? what : "?", (unsigned long long)addr);
    std::abort();
}
void guest_unimpl(uint64_t pc, uint32_t insn, const char *what) {
    std::fprintf(stderr, "rt-stub: guest_unimpl: 0x%08x at 0x%llx (%s)\n", insn, (unsigned long long)pc, what ? what : "?");
    std::abort();
}
void guest_svc(Ctx *c, uint32_t number) { unimplemented("guest_svc", number, c ? c->fn : 0); }
uint64_t guest_mrs(Ctx *c, uint32_t sysreg) { unimplemented("guest_mrs", sysreg, c ? c->fn : 0); return 0; }
void guest_msr(Ctx *c, uint32_t sysreg, uint64_t value) { unimplemented("guest_msr", sysreg, value); }
void nx_site_inline(Ctx *c, uint64_t addr) { unimplemented("nx_site_inline", addr, c ? c->fn : 0); }
int nx_site_midhook(Ctx *c, uint64_t addr) { unimplemented("nx_site_midhook", addr, c ? c->fn : 0); return 0; }
int nx_hook_entry(Ctx *c, uint64_t addr) { unimplemented("nx_hook_entry", addr, c ? c->fn : 0); return 0; }
void stx_diag(Ctx *c, uint64_t a, uint64_t expected, uint64_t seen, uint64_t v, int bits) {
    (void)c; (void)a; (void)expected; (void)seen; (void)v; (void)bits;
}
void nx_catch_call(Ctx *c, void (*body)(Ctx *, uint64_t)) { unimplemented("nx_catch_call", (uint64_t)(uintptr_t)body, c ? c->fn : 0); }
// The frame-counter census and the converted counters (xc2_boot.cpp in the real runtime): a lifted main may reference
// them, so the scaffold returns the game's own value and records nothing.
void fps_census(uint64_t site, uint64_t field, uint64_t v, int code) { (void)site; (void)field; (void)v; (void)code; }
uint64_t fps_ci(uint64_t site, uint64_t field, uint64_t v, int k, int sign, int size) {
    (void)site; (void)field; (void)k; (void)sign; (void)size;
    return v;
}
uint32_t fps_cf(uint64_t site, uint64_t field, uint32_t v, int sign) { (void)site; (void)field; (void)sign; return v; }
uint32_t fps_fs(uint64_t site, uint64_t field, uint32_t v) { (void)site; (void)field; return v; }

}  // extern "C"
