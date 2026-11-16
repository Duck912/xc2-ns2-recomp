// SPDX-License-Identifier: GPL-3.0-or-later
// Bring-up introspection of the nn::os fibers the host answers (fiber_hle.cpp). A guest fiber that is suspended in a
// cooperative switch has no host thread to look at, so this is the only way to ask where it stopped: the saved LR is
// the guest address it will resume at.
#pragma once
#include <cstdint>

namespace nxrt {

// state: 0 = created but never started, 1 = suspended (saved context), 2 = finished.
void fiber_dump(void (*cb)(void* user, uint64_t guest, uint64_t fn, uint64_t lr, uint64_t sp, int state), void* user);

}  // namespace nxrt
