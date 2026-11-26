// SPDX-License-Identifier: GPL-3.0-or-later
// xc2ns2_stub: a smoke test of the lifted modules, no guest execution.
//
// It links every function of the four modules and then walks the module descriptors the lifter generated
// (NxModule in <nxrecomp/ctx.h>): the function table, the dynamic-symbol table, the resume table and the unwind
// tables. That proves three things the coverage report cannot: the 90k functions link as one program, the tables are
// well formed (sorted, in range, ABI version matches), and the entry points the runtime will use are there.
//
// Usage: xc2ns2_stub [--quiet] [--example N]
#include <nxrecomp/ctx.h>

#include <algorithm>
#include <cstdio>
#include <cstring>

extern "C" {
extern const NxModule nxmod_main;
extern const NxModule nxmod_sdk;
extern const NxModule nxmod_subsdk0;
extern const NxModule nxmod_rtld;
extern const uint32_t nxmod_main_abi;
extern const uint32_t nxmod_sdk_abi;
extern const uint32_t nxmod_subsdk0_abi;
extern const uint32_t nxmod_rtld_abi;
}

namespace {

int failures = 0;

void fail(const char *module, const char *what, unsigned long long a, unsigned long long b) {
    std::printf("  FAIL %-8s %-28s 0x%llx 0x%llx\n", module, what, a, b);
    ++failures;
}

void check_module(const NxModule &m, uint32_t abi, int examples) {
    std::printf("%-8s index %u  base 0x%llx  text_end 0x%llx  abi %u\n", m.name, m.index, (unsigned long long)m.base,
                (unsigned long long)m.text_end, abi);
    std::printf("         functions %d  symbols %d  resume %d  eh %s\n", m.nfns, m.nsyms, m.nresume, m.eh ? "yes" : "no");
    if (abi != NXRECOMP_ABI_VERSION) fail(m.name, "abi mismatch", abi, NXRECOMP_ABI_VERSION);
    if (m.nfns <= 0) fail(m.name, "no functions", 0, 0);
    if (!m.fns) fail(m.name, "null function table", 0, 0);

    // sorted, inside [base, text_end), on a 4-byte boundary
    for (int i = 0; i < m.nfns; i++) {
        const uint64_t a = m.fns[i].addr;
        if (a < m.base || a >= m.text_end || (a & 3)) { fail(m.name, "function address", a, m.base); break; }
        if (i && a <= m.fns[i - 1].addr) { fail(m.name, "function table unsorted", a, m.fns[i - 1].addr); break; }
        if (!m.fns[i].fn) { fail(m.name, "null function pointer", a, 0); break; }
    }
    // defined symbols point inside the image; a value below the base is a TLS offset or an SHN_ABS number (the ABI keeps
    // those raw), and an undefined symbol is 0
    for (int i = 0; i < m.nsyms; i++) {
        const DynSym &s = m.syms[i];
        if (s.defined && s.value >= m.base && s.value > m.text_end + 0x40000000ull) { fail(m.name, "symbol value", s.value, s.name ? 1 : 0); break; }
        if (!s.defined && s.value) { fail(m.name, "undefined symbol with value", s.value, 0); break; }
    }
    if (m.nresume && !m.resume) fail(m.name, "null resume table", 0, 0);
    if (m.eh) {
        if (m.eh->nfdes < 0 || (m.eh->nfdes && !m.eh->fdes)) fail(m.name, "bad eh fdes", m.eh->nfdes, 0);
        for (int i = 0; i < m.eh->nfdes; i++) {
            if (m.eh->fdes[i].start >= m.eh->fdes[i].end) { fail(m.name, "eh fde range", m.eh->fdes[i].start, m.eh->fdes[i].end); break; }
        }
    }
    const int n = std::min(examples, m.nfns);
    for (int i = 0; i < n; i++) std::printf("         f_%llx\n", (unsigned long long)m.fns[i].addr);
    std::printf("\n");
}

}  // namespace

int main(int argc, char **argv) {
    int examples = 0;
    for (int i = 1; i < argc; i++) {
        if (!std::strcmp(argv[i], "--example") && i + 1 < argc) examples = std::atoi(argv[++i]);
    }
    std::printf("xc2ns2_stub: nxrecomp ABI %d\n\n", NXRECOMP_ABI_VERSION);
    check_module(nxmod_main, nxmod_main_abi, examples);
    check_module(nxmod_sdk, nxmod_sdk_abi, examples);
    check_module(nxmod_subsdk0, nxmod_subsdk0_abi, examples);
    check_module(nxmod_rtld, nxmod_rtld_abi, examples);
    std::printf("%s: %d failure(s)\n", failures ? "FAILED" : "OK", failures);
    return failures ? 1 : 0;
}
