# Target build

Read from a `.nup` dump (3 packages). Module hashes are SHA-256 of the files as stored in ExeFS (NSO, LZ4).

| Package | Title ID | Kind | Contents |
|---|---|---|---|
| 0 | 0400FF500E34A001 | program index 1 | **Switch 2 program** (the recomp target), display version 2.0.0; RomFS is a 5-byte `dummy.bin` |
| 1 | 0400FF500E34A000 | program index 0 | Switch 1 program (SDK 9.3.1) + full game RomFS, 13.6 GiB |
| 2 | 0100FF500E34B001 | add-on | RomFS, 20.0 GiB (bdat, chr, cs, eff, map, menu, monolib, ... ; has `dlcver.bin`) |

The S2 program reads its data from program 0's RomFS (same arrangement as XC2 S2E), so the runtime's
`fsp-srv` must serve program 0's RomFS for `OpenDataStorageWithProgramIndex(0)`.

## Switch 2 program modules (0400FF500E34A001)

| Module | Size (decompressed) | SDK string | SHA-256 (prefix) |
|---|---|---|---|
| main | 12.5 MB | `bfsw.nss`, NintendoSDK 21_4_4, SMAA_For_NDSR 2_1_0 | cae58fa98679 |
| sdk | 15.3 MB | nnSdk Generic 21_4_4, NVN 21_4_4 | f306d21b0507 |
| subsdk0 | 0.8 MB | multimedia_compat_nx (movie 21_4_4) | ab06fd16da99 |
| subsdk1 | 45.6 MB | DLSS 21_4_4 | 517e7eb922bb |
| subsdk2 | 21.2 MB | NVIDIA CUDA 12090 (21_2_0) | 409ed2912dda |
| subsdk3 | 0.8 MB | movie 21_4_4 | 976e2076159e |
| rtld | – | – | 87c39fd59d4d |

## Comparison with XC2 S2E (0400E95004038001, 3.0.1)

Checked 2026-11-26 by SHA-256 of the ExeFS files: **six of the seven modules are byte-identical** to XC2 S2E's.

| Module | Same as XC2? |
|---|---|
| main | **no** (7.19 MB vs 8.86 MB compressed) |
| sdk (nnSdk + NVN driver) | yes |
| subsdk0, subsdk3 (movie) | yes |
| subsdk1 (DLSS) | yes |
| subsdk2 (CUDA) | yes |
| rtld | yes |

So the lift profiles, hook/site tables and runtime behaviour that xc2-ns2-recomp has for `sdk`, `subsdk0-3` and
`rtld` apply unchanged, and the NVN2 / DLSS / CUDA API surface the game sees is exactly XC2's. Only `main`
(the game itself, engine `bfsw.nss`) needs new work.
