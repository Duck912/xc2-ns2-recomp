// SPDX-License-Identifier: GPL-3.0-or-later
// The exe half of the release split: xc2_rt.dll holds the runtime and the boot code, and this only hands the
// process to it. The player's build links this against the libraries lifted out of their own dump, so nothing
// lifted is in the DLL and nothing from the runtime is in the exe (upstream: fefw_stub.cpp / fefw_rt.dll).
//
// The module table lives here because the lifted symbols do: xc2_rt.dll must not reference any of them.
#include <cstdint>

#include "xc2_modules.h"

extern "C" int xc2_rt_main(int argc, char **argv);

extern "C" {
extern const NxModule nxmod_main, nxmod_sdk, nxmod_subsdk0, nxmod_rtld;
extern const uint32_t nxmod_main_abi, nxmod_sdk_abi, nxmod_subsdk0_abi, nxmod_rtld_abi;
#ifdef XC2_MODULES_7
extern const NxModule nxmod_subsdk1, nxmod_subsdk2, nxmod_subsdk3;
extern const uint32_t nxmod_subsdk1_abi, nxmod_subsdk2_abi, nxmod_subsdk3_abi;
#endif
}

// The console loader's order: rtld first (it is the entry), then main, the subsdks, sdk.
#ifdef XC2_MODULES_7
static const ModEntry kModules[] = {
    {"rtld", &nxmod_rtld, &nxmod_rtld_abi},
    {"main", &nxmod_main, &nxmod_main_abi},
    {"subsdk0", &nxmod_subsdk0, &nxmod_subsdk0_abi},
    {"subsdk1", &nxmod_subsdk1, &nxmod_subsdk1_abi},
    {"subsdk2", &nxmod_subsdk2, &nxmod_subsdk2_abi},
    {"subsdk3", &nxmod_subsdk3, &nxmod_subsdk3_abi},
    {"sdk", &nxmod_sdk, &nxmod_sdk_abi},
};
#else
static const ModEntry kModules[] = {
    {"rtld", &nxmod_rtld, &nxmod_rtld_abi},
    {"main", &nxmod_main, &nxmod_main_abi},
    {"subsdk0", &nxmod_subsdk0, &nxmod_subsdk0_abi},
    {"sdk", &nxmod_sdk, &nxmod_sdk_abi},
};
#endif

int main(int argc, char **argv) {
    xc2_rt_set_modules(kModules, static_cast<int>(sizeof(kModules) / sizeof(kModules[0])));
    return xc2_rt_main(argc, argv);
}
