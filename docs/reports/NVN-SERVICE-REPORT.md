# XC2 NS2: NVN2 API surface and service coverage (go/no-go steps 2 and 3)

> 2026-11-09 · **Both passed.**
> Method: static analysis, without running the game. On the NVN side the NVN2 name table inside `sdk` was compared
> against the fork base's implementation table; on the service side the namespaces of the undefined imports and the
> service-name strings were compared against Goldoire's `runtime/src/services`.

> **Status today (2026-11-16)**: both predictions held and both open items are closed. `nn::fgm` was stubbed
> permissively, `hwopus` was replaced by the SDK's own software Opus decoder (ported from nxnative, MIT), and the
> retail 3.0.1 program boots and plays. The census mentioned at the end is what confirmed the NVN behaviour
> questions below.

## 0. Verdict

| criterion | threshold | measured | result |
|---|---|---|---|
| share of NVN2 procs implemented by the fork base | above 30% uncovered would force a re-estimate | **460 / 461 = 99.8%** (the one missing entry is `nvnDeviceGetProcAddress`, which the host answers itself) | ✅ |
| do the service namespaces have implementations | must match | `main` 15 namespaces, `subsdk0` 8 — **all have a corresponding IPC service**, only the Switch 2 `fgm` missing | ✅ |
| services that must be written | fewer is better | **one** (`fgm`), plus one that exists but decodes silence (`hwopus`) | ✅ |

## 1. NVN2: XC2's API table is covered

### 1.1 How the table was found

`nvnDeviceGetProcAddress` binary-searches a **sorted table of short names** (no `nvn` prefix). In the `sdk` image:

| | |
|---|---|
| location | `sdk` RVA **0x7a85b8 – 0x7ab671** |
| entries | **461** (strictly ascending, null-terminated ASCII) |
| first / last | `BlendStateGetAdvancedMode` … `WindowSetPresentInterval` |

### 1.2 The comparison

The fork base (Goldoire/fefw-recomp):

| | |
|---|---|
| its SDK version | `NintendoSDK_NVN-20_5_25-Release` (Pokopia) |
| procs it records | 726 |
| procs it actually registers | **542** (`NVN_REG(...)`, across 13 `api_*.cpp`) |
| XC2's SDK version | `NintendoSDK_NVN-3_5_0-Release` |

| overlap | |
|---|---|
| of XC2's 461 procs, registered by the fork base | **460 (99.8%)** |
| the only one not registered | `nvnDeviceGetProcAddress` — the host's bootstrap answers it, the game side never implements it |

### 1.3 The version drift is additive, not subtractive

XC2 (NVN 3.5.0) is older than Pokopia (NVN 20.5.25). Five of its procs are **not** in Pokopia's 726-entry table, and
the fork base implements them anyway:

| XC2-only (older API) | implemented in |
|---|---|
| `nvnCommandBufferPushDebugGroupStatic` | `api_cmd_work.cpp` |
| `nvnCommandBufferPushDebugGroupDynamic` | `api_cmd_work.cpp` |
| `nvnCommandBufferPopDebugGroupId` | `api_cmd_work.cpp` |
| `nvnDeviceApplyDeferredFinalizes` | `api_device.cpp` |
| `nvnQueueAcquireTexture` | `api_device.cpp` (shared with `nvnWindowAcquireTexture`) |

The 265 newer procs XC2 never asks for are irrelevant. **The base is a superset of what XC2 needs.**

### 1.4 The real risk is behaviour, not presence

99.8% only says the entry points exist. Between NVN 3.5.0 and 20.5.25 these can differ, and static analysis cannot
see it:

- the **170 device-info values** of `nvnDeviceGetInteger` (the base's `nvn_device_info.inc` was recorded from 20.5.25);
- struct sizes and alignment (`nvn2_sizes.inc`, same provenance);
- command encoding and handle semantics (`nvn_cmd.h`).

That was the largest remaining technical risk after step 2, and it can only be settled by running the game: the
runtime's NVN census (the `nvn_procs.c` machinery: record resolve/call, count per proc) reports what XC2 actually
calls and which device-info values it queries.

## 2. Services: 15 + 8 namespaces, one Switch 2 service missing

### 2.1 From the imports

| module | undefined `nn::` imports | by namespace |
|---|---|---|
| `main` | 276 | audio 79, os 63, hid 37, fs 22, oe 18, mem 10, vi 8, diag 7, err 7, time 6, account 5, util 5, **codec 5**, settings 3, detail 1 |
| `subsdk0` | 75 | sf 23, os 23, audio 14, **fgm 6**, fs 4, lmem 3, util 1, diag 1 |
| `sdk` | 0 | the SDK itself |

### 2.2 Namespace → IPC service → implementation

| namespace | service | implementation in `runtime/src/services/` | status |
|---|---|---|---|
| `nn::fs` | `fsp-srv` | `fs.cpp` (+ `fs_romfs.cpp`, `fs_volume.cpp`) | ✅ |
| `nn::hid` | `hid` | `hid.cpp` | ✅ |
| `nn::audio` | `audren:u` / `audout:u` | `audio.cpp`, `audio_out.cpp` | ✅ |
| `nn::oe` | `appletOE` | `am.cpp` | ✅ |
| `nn::vi` | `vi:u` / `vi:m` / `vi:s` | `vi_nv.cpp` | ✅ |
| `nn::account` | `acc:u0` | `acc.cpp` | ✅ |
| `nn::time` | `time:u` / `time:s` | `time.cpp`, `timezone.cpp` | ✅ |
| `nn::settings` | `set:sys` | `settings.cpp` | ✅ |
| `nn::codec` | `hwopus` | `misc.cpp` (`IHardwareOpusDecoder`) | ⚠️ implemented, but it **decodes silence** |
| `nn::diag` / `nn::err` | `lm` / `fatal:u` / `err:u` | `logfault.cpp` | ✅ |
| `nn::fgm` | `fgm` | **none** | ❌ had to be written |
| `nn::mem` / `nn::lmem` / `nn::util` | no service (local heaps and utilities) | the lifted SDK code | ✅ |
| `nn::sf` (subsdk0) | the IPC framework (CMIF/hipc) | `ipc.cpp`, the kernel | ✅ |
| `nvn` / `nvdrv` | `nvdrv` (ioctl) | `vi_nv.cpp` + `nvrm.c` | ✅ |
| `Nv*` (subsdk0, 108) | the NVIDIA driver layer | the lifted sdk/subsdk0; the host only answers ioctls | ✅ |

The service-name strings were confirmed inside `sdk` (`fsp-srv`, `hid`, `audren:u`, `vi:u`, `hwopus`,
`nvdrv`, `fgm`, `fgm:dbg`).

### 2.3 The two open items

1. **`fgm` (new on Switch 2, 6 imports)**: `nn::fgm::Request::Initialize(Module, u32, EventClearMode)` and
   `SetAndWait(u32, u32)` look like **frequency/performance governance** (request a clock for a hardware module,
   wait for the event). The base's `apm` only covers the Switch 1 performance modes. Estimated 3–5 days, starting
   with a permissive stub (connect succeeds, the request completes at once) and refining it once it is clear
   whether it affects the frame rate.
2. **`hwopus` silence**: XC2's voice audio is Opus (`nn::codec::OpusDecoder`, 5 imports) and the base dropped the
   packets. Real audio needs a software Opus decoder, estimated 1–2 weeks, and it does not block reaching the title
   screen.

### 2.4 Protocol-version risk

The CMIF command numbers of `fsp-srv`, `hid` and friends move between SDK versions; XC2 uses an old SDK and the
base implements the newer one. Such differences usually show up at boot (mounting the romfs, initialising `hid`),
which makes them easy to locate.

## 3. Effect on the estimate

| work stream | before | after | why |
|---|---|---|---|
| NVN2 front end + Vulkan backend | 8–16 weeks | **6–12 weeks** | 99.8% of the API surface already exists; the work is behaviour calibration, not writing a front end |
| service layer | 5–10 weeks | **4–8 weeks** | only `fgm` (3–5 days), real Opus decoding (1–2 weeks) and protocol calibration remain |
| shader translation | 3–6 weeks | unchanged | not measured in that round |
| **total** | 6.5–12 months | **6–11 months** (median ≈ 8.5) | |

## 4. What this round did not prove

1. **Which commands a frame actually uses** — static analysis proves the entry points exist, not that each command's
   semantics match. That is what the frame capture in step 2 was for, and it needed a booting runtime.
2. **Device-info and struct differences between NVN 3.5.0 and 20.5.25** — needs disassembling XC2's
   `nvnDeviceGetInteger` switch or reading the census.
3. **Service protocol version differences** — likewise, only visible once it runs.

**The criterion for the next step**: once the stub runtime reaches `main` and the first NVN call, the census log
replaces both static inferences.
