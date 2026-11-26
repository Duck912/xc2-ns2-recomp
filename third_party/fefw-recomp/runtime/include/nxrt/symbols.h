// SPDX-License-Identifier: GPL-3.0-or-later
// Host-code symbolisation from the MSVC-format linker map (link.exe /MAP) that sits next to the exe.
//   Address         Publics by Value              Rva+Base               Lib:Object
//   0001:00000010       ?name@@YAXXZ              0000000140001010 f   file.obj
// Used by the crash handler and the watchdog to name host frames without a PDB.
#pragma once
#include <cstdint>
#include <string>

namespace nxrt {

struct SymbolInfo {
    std::string module;   // "nxrt_tests.exe" (file name only), or "?" when the address is in no loaded module
    uint64_t offset = 0;  // address - module base
    std::string symbol;   // nearest preceding public symbol (undecorated when possible), empty when unknown
    uint64_t sym_offset = 0;  // address - symbol start
    bool from_map = false;
};

// Loads <exe path>.map's "Publics by Value" section for the main exe. Without an argument looks for the map next to the
// running exe (same name, .map extension). Returns the number of symbols loaded (0 = no map found / unreadable).
// When it is not there, the map in the folder the exe's PDB was written to (the build folder: an exe copied to a play folder without its map) is
// used if its "Timestamp is" line equals the exe's header time stamp, i.e. the map belongs to this build.
size_t symbols_load_map(const char* map_path = nullptr);
std::string symbols_map_path();   // the file the last symbols_load_map read ("" when none)
// Same for any text (tests): `module_base` is the load address the Rva+Base column assumed (preferred base).
size_t symbols_load_map_text(const std::string& text);
size_t symbols_count();
// Resolve a host code address. Never throws, never allocates beyond the returned strings, safe to call from the crash handler
// only when symbols_load_map has run earlier (the lookup itself allocates strings: the crash handler tolerates that).
SymbolInfo symbols_lookup(uint64_t host_addr);
// "module+0xOFFSET (symbol+0xN)" or "module+0xOFFSET" or "0xADDR".
std::string symbols_describe(uint64_t host_addr);

// Guest names for the lifted functions. The linker map names each one "f_<guest VA>" (an address, in hex); the
// sidecar that tools/build/guest-symbols.ps1 writes - one "0x<guest VA> TAB <module> TAB <name>" line per exported
// symbol, ascending - gives the same address the name the lift had, so a thread dump reads
// "subsdk0!movie::MediaDecoder::Stop+0x12". symbols_load_map reads <exe>.names next to the map; a build without it
// keeps the f_ names and nothing else changes.
size_t symbols_load_guest_names(const char* names_path = nullptr);  // empty argument: <map path>.names
size_t symbols_load_guest_names_text(const std::string& text);      // same, for tests
size_t symbols_guest_count();
// The name of a lifted function, by its start address: "module!name" when the sidecar names that exact address,
// otherwise the map's own "f_<VA>". Never empty, never throws.
std::string symbols_describe_guest(uint64_t guest_addr);

}  // namespace nxrt
