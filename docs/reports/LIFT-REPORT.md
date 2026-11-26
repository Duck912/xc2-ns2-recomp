# XC2 NS2: lift coverage, measured

> 2026-11-09 · **go/no-go step 1 (the lift) passed.**
> Input: the four NSO modules of the then-current NS2 build; tool: `drakolordx7/nxrecomp @ de23ddc8` (GPL-3.0).
> Verdict: **the generic recompiler handles XC2 completely** — function boundaries, instruction lift, C++
> generation, compilation and symbol closure all green.

> **Status today (2026-11-16)**: these are the numbers of the 2026-11-09 **development build**. The retail 3.0.1
> exefs measures differently (seven modules, `main` 48,965 functions / 3,031,179 instructions) — see
> `docs/ARCHITECTURE.md`. The conclusions below held for both.

## 0. Verdict

| criterion | expected | measured (`main`) | result |
|---|---|---|---|
| function boundaries found | most of them | **49,908 functions**, FDEs cover **99.94%** of `.text`, 0 end/start conflicts | ✅ |
| share of instructions lifted | above 95% | **2,551,511 / 2,551,511 = 100.00%**, `guest_unimpl` **0** | ✅ |
| list of unsupported instructions | enumerable | **empty**; 100% of the module lands on tier 1, tier-2 dependence **0%** | ✅ |
| does the generated C++ compile | most of it | 208/208 shards plus the module descriptor, **0 errors, 0 warnings** | ✅ |
| is every call target implemented | yes | unresolved `f_*` / `u_*` symbols: **0** | ✅ |

In one sentence: the first hurdle was not scraped past, it was simply absent. Lifting stopped being a risk; the risk
moved entirely into the runtime, as predicted.

## 1. The four modules

| module | `.text` | functions | instructions lifted | untranslated | landing pads | jump tables | C++ shards | C++ size | lift time |
|---|---|---|---|---|---|---|---|---|---|
| `main` | 10,212,304 B | **49,908** | **2,551,511** | **0** | 0 | 894 | 208 | 167.7 MB | 9.0 s |
| `sdk` | 4,057,272 B | 27,365 | 989,935 | **0** | **4,556** | 433 | 83 | 69.4 MB | 13.4 s |
| `subsdk0` | 3,098,036 B | 13,378 | 760,392 | **0** | 0 | 468 | 64 | 48.9 MB | 7.7 s |
| `rtld` | 6,048 B | 40 | 1,497 | 1* | 0 | 2 | 1 | 0.1 MB | 1.2 s |
| **total** | — | **90,691** | **4,303,335** | **1** | 4,556 | 1,797 | **356** | **286.1 MB** | ~31 s |

\* the single untranslated word in `rtld` is `ffffffb4` at `0x710000004c`: **data** inside the entry stub, not an
instruction. `rtld` is loaded by the runtime and does not need lifting.

For scale: the Fire Emblem build is 6.5M instructions; XC2 NS2's four modules are **4.3M (66%)**, and the code is
more conventional (see §3).

## 2. Function boundaries: both FDEs and symbols are intact

Output of `python -m nxrecomp.funcs` (`work/functions-main.tsv`, 49,908 rows):

| metric | `main` |
|---|---|
| `.eh_frame` FDEs (exact start and end) | 49,518 |
| FUNC symbols with a size | 48,739 |
| both | 48,739 |
| **end/start conflicts** | **0** |
| heuristic end only ("next function start") | 390 |
| code covered by no function (gap) | **0** |
| `.text` bytes covered by exact functions | 10,206,008 / 10,212,304 = **99.94%** |
| functions with a symbol name | 48,739 (97.7%) |

This is the best case: neither `.eh_frame` nor `.dynsym` was stripped. The build keeps full unwind data and 57,239
dynamic symbols, so boundaries do not have to be guessed and hook/patch sites can be named directly
(`_ZN2gf…`, `_ZN2ui…`).

Function size: median **23 instructions**, 42.5% are 16 instructions or fewer, the largest is 12,465 (only 126 exceed
1,000). The usual heavily inlined C++ shape.

## 3. Instruction lift: 100%, all of it on tier 1

| | |
|---|---|
| `.text` instruction words (including data) | 2,553,076 |
| instruction slots inside functions | 2,553,067 |
| **actually lifted** | **2,551,511 (100.00%)** |
| `guest_unimpl` | **0** |
| `guest_trap` (undefined instructions, i.e. data/UDF) | 7 |

Six of the seven traps are `e7ffdefe` (UDF #0xdefe), the Nintendo SDK's deliberate halt/debug-break path, so lifting
them as traps is the correct semantics; the seventh is `00000000` at `0x71009bbb5c` immediately after a `ret`,
i.e. tail padding. There is no systematic "data treated as code" problem.

**Tier dependence**: counted per instruction over all 2,553,067, tier 1 (`lift/a64.py`, the reference implementation
pinned by 565,061 Unicorn differential cases) covers **100.00%** and tier 2 (the Capstone-driven fallback) **0**.

Meaning: XC2 NS2 uses only the ARMv8.0 baseline — no LSE atomics, no crypto, no exotic AdvSIMD. The lift takes the
most trusted path, so no debugging budget is owed to a tier-2 emulator that might be wrong.

Jump tables: **894**, all resolved into bounded `switch` statements (901 `switch` in the generated code, including
whole-function dispatch for seven unresolved `br`). Indirect call sites: 21,707 (C++ virtual calls), served by the
runtime's `call_indirect`.

## 4. The generated C++ and the compile

| | |
|---|---|
| shards | 208 + 83 + 64 + 1 = **356** `c_*.cpp` (48 KB of guest code per shard) |
| objects | 355 `*.obj`, 102.8 MB |
| **compile failures** | **0** (208/208, 83/83, 64/64) |
| warnings | **0** |
| compiler | clang-cl 23.1.5, `/std:c++20 /O2`, 12 cores |
| time | `main` 83.3 s wall / 810 s CPU; `sdk` 33.4 s / 314 s; `subsdk0` 20.1 s / 194 s; **136.8 s wall in total** |
| slowest shard | 11.5 s (`sdk c_0000.cpp`, heavy EH tables) |
| module descriptor | `module_main.cpp` 14.4 MB (57,239 dynamic symbols), 2.9 s |

At 4.3M instructions / 287 MB of C++ / 137 s on 12 cores, **compilation is a minutes-level cost, not a bottleneck**.
That is also why the Fire Emblem build can do 6.5M instructions → 453 MB of C++ in about two minutes.

Compile only, no link: linking needs the `nxrt` runtime and a game main, which is step 2.

## 5. The link surface: a dozen external symbols

`llvm-nm --undefined-only` over all 208 `main` objects, counted per translation unit. Apart from `f_*` (intra-module
calls), the complete list is:

| symbol | translation units | provided by |
|---|---|---|
| `call_indirect` | 205 | the runtime (indirect call dispatch) |
| `host_import` | 1 | the runtime (PLT / imported symbols) |
| `guest_trap` | 5 | the runtime |
| `stx_diag` | 3 | the runtime (exclusive-store diagnostics) |
| `_fltused`, `__security_cookie`, `__security_check_cookie` | — | the MSVC CRT |
| `sqrt`, `trunc`, `floor`, `ceil` | — | the MSVC CRT |

**`main` references neither `guest_svc` nor `nx_catch_call`** — system calls are wrapped inside `sdk`, and exception
handling is off in `main` (see §7).

`sdk` adds `nx_catch_call` (18 TUs), `guest_svc` (1), `guest_mrs` (1), `fmaf`/`rint` and so on — all of them entry
points the runtime already provides.

**Symbol closure**: the set difference between defined and undefined symbols per module leaves **0** missing `f_*`
and **0** missing `u_*` (landing-pad resume entries). Every call target the lifter found has a body; nothing jumps to
an address that does not exist.

## 6. The service surface: small, and mostly already there

Undefined `nn::` imports, i.e. what the runtime or another module must provide:

| module | imports | by namespace |
|---|---|---|
| `main` | 276 | audio 79, os 63, hid 37, fs 22, oe 18, mem 10, vi 8, diag 7, err 7, time 6, account 5, util 5, codec 5, settings 3, detail 1 |
| `subsdk0` | 75 | sf 23, os 23, audio 14, fgm 6, fs 4, lmem 3, util 1, diag 1 |
| `sdk` | 0 | it *is* the SDK |

Points worth noting:

- **One graphics entry point**: `main` imports only `nvnBootstrapLoader`; the whole NVN2 table is fetched at start
  up. That matches the runtime's front-end design (hook the bootstrap, hand back the proc table) — **no per-symbol
  `nvn*` imports**.
- `subsdk0` imports 108 `Nv*` symbols (the NVIDIA driver layer). `sdk`/`subsdk0` implement them; the runtime only
  has to answer the nvmap/nvhost ioctls.
- Three areas needed confirming: `nn::codec` (5, all `OpusDecoder`), `nn::fgm` (6, `Request::SetAndWait`, looks
  like frequency/performance governance) and `nn::lmem` (3, `ExpHeap` allocation). None of the runtime's 31 service
  files implement them; `codec` decides whether there is voice audio and `fgm` whether the performance mode is
  right, so **this is the only part of the service layer that had to be written** (estimated 1–2 weeks, not months).
- `nn::sf` (23) is the SDK's IPC framework (`hipc::*`), not a game service: exported by `sdk`, called by
  `subsdk0`, i.e. module-to-module symbol resolution rather than a new service.

## 7. Exception handling: off in `main`, on in `sdk`

| module | landing pads | `nx_catch_call` | reading |
|---|---|---|---|
| `main` | **0** | 0 | compiled with `-fno-exceptions` (imports `__cxa_guard_acquire/release` and `__cxa_pure_virtual`, but no `__cxa_throw` / `_Unwind_Resume`) |
| `sdk` | **4,556** | 18 TUs | full C++ EH; the runtime's landing-pad resume path is really used and compiles |
| `subsdk0` | 0 | 0 | like `main` |

Good news and a reminder: **the game logic (`main`) has no C++ exceptions**, so nothing has to be paid for exceptions
crossing lifted code; but **`sdk` has 4,556 landing pads**, so `nx_catch_call` and the resume table must be correct —
work the runtime base already did for its own title, but not free.

## 8. Reproducing it

```powershell
$py = '<python>\python.exe'
$rc = '<repo>\third_party\nxrecomp\recomp'
$env:PYTHONPATH = $rc
Set-Location $rc

# 1) function boundaries
& $py -m nxrecomp.funcs <exefs>\main --base 0x7100000000 --out '<repo>\work\functions-main.tsv'

# 2) per-instruction coverage (no code generated, seconds)
& $py -m nxrecomp cover <exefs>\main --base 0x7100000000

# 3) lift to C++ (the game config is recomp/games/xc2ns2/config.py)
& $py -m nxrecomp lift <exefs>\main '<repo>\work\lift\main' `
      --game xc2ns2 --index 0 --name main --base 0x7100000000 --jobs 10

# 4) compile every shard
. <toolchain>\env.ps1
& '<repo>\work\build-shards.ps1' -Dir '<repo>\work\lift\main' -Throttle 10
```

## 9. What this round did **not** verify

1. **No link, no run.** Compiling is not booting; the link needs the `nxrt` runtime and a game main.
2. **No Unicorn differential run on XC2 functions.** The recompiler ships 565k differential cases, but none were run
   against these functions; semantic correctness rested on the "100% tier 1" argument.
3. **The module base addresses were guessed** (the layout of a sibling project). The lift is module-relative, so the
   conclusion holds, but cross-module call targets would move.
4. **The NVN2 command stream was not tested** — `main` has a single `nvnBootstrapLoader` import; real coverage is a
   question for frame capture.
5. **`bf2.ard` untouched** (a parallel work stream).

## 10. Effect on the estimate

| work stream | before | after | why |
|---|---|---|---|
| lifting the NS2 modules | 2–4 weeks | **3–5 days** (game config polish, base addresses, sites/patches) | 0 unsupported instructions, 0 compile errors |
| kernel/SVCs | 1–2 weeks | unchanged | `sdk` has a single `guest_svc` TU |
| service layer | 6–12 weeks | **5–10 weeks** | 15 namespaces, most already covered; only codec/fgm/lmem are new |
