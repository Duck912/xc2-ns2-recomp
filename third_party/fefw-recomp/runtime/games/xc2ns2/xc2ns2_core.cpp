// SPDX-License-Identifier: GPL-3.0-or-later
// Xenoblade Chronicles 2 - Switch 2 Edition, the core part of the game module: the data part plus the title facts.
// Needs the runtime library, not the graphics one.
#include "xc2ns2_game.h"

#include "nxrt/services.h"

namespace nxrt::games::xc2ns2 {

namespace {

// Read from the dump's main.npdm (1476 bytes): process "Application", main thread stack 0x100000 (1 MiB, at 0x1C),
// main thread priority 0x2C = 44 on core 0, SystemResourceSize 0 (so the SDK takes the non-VAMM path: heap section).
// Save sizes are placeholders until control.nacp is dumped; the boot log shows what the game asks for.
void title_defaults(services::TitleProfile& p) {
    p.program_id = data_info().program_id;
    p.name = data_info().title;
    p.display_version = data_info().version;
    p.supported_languages = data_info().languages;
    p.account_save_size = 0x4000000;
    p.account_save_journal = 0x4000000;
    p.device_save_size = 0x4000000;
    p.device_save_journal = 0x4000000;
    p.main_thread_stack = 0x100000;
    p.main_thread_priority = 44;
    p.main_thread_core = 0;
    p.system_resource_size = 0;
    p.firmware = "20.0.0";                     // TODO: confirm from the SDK tags / boot log
    p.user_nickname = "Player";
    p.user_uid_hi = 0x0000000000000001ull;
    p.user_uid_lo = 0x5843324e53325263ull;     // "XC2NS2Rc"
}

}  // namespace

const game::Info& core_info() {
    static const game::Info info = [] {
        game::Info g = data_info();
        g.title_defaults = &title_defaults;
        return g;
    }();
    return info;
}

}  // namespace nxrt::games::xc2ns2

void nxrt_register_game_xc2ns2_core() { nxrt::game::set_current(&nxrt::games::xc2ns2::core_info()); }
