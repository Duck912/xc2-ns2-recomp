# Hook sites

The addresses the lifter turns into hooks, so that the `hook_add_entry` calls in `xc2/src/xc2_boot.cpp` have
somewhere to fire. One file per module.

| file | what it carries |
|---|---|
| `sites-main.txt` | ~65 entry and mid hooks in the game code: the memory manager, the microthread scheduler, the launcher and title screens, the frame clock |
| `sites-sdk.txt` | two, and they matter: the `nn::os` thread manager constructor and the VAMM address-region initialiser read state that the console's boot loader would have set up |
| `sites-rtld.txt` | one: `rtld+0x1470`, a flag-setting helper |

## How they are used

`tools/build/build.ps1` passes `--sites` to the lifter for every module, in this order:

1. `xc2/build/sites-<module>.txt` — yours, if you made one; it wins, so local experiments never touch this folder;
2. `xc2/sites/sites-<module>.txt` — this folder.

Without `--sites` the lifter emits no `nx_hook_entry` at all, and every hook in `xc2_boot.cpp` silently does
nothing — which is why these files ship with the repository instead of living in the git-ignored build tree.

## Format

```
entryhook <address>     # called when the function is entered
midhook   <address>     # called mid-function, where a return address is on the stack
```

Addresses are the guest's virtual addresses (`0x71xxxxxxxx` for `main`, `0x75` for `sdk`, `0x77` for `rtld`).
`tools/analysis/symat.py` turns one into a name.

**ASCII only.** The lifter reads this file with the system's locale encoding; a non-ASCII byte in a comment fails
the lift with a `UnicodeDecodeError`.

## What is deliberately not here

One instruction patch (a `cmp` bound widened for the 3.0.0 add-on content that ships in the pkg7 package) is not
included: a `patch` line carries the original instruction word of the game, and this repository contains no game
bytes. It was a diagnostic for a different route anyway; the 3.0.1 retail route does not need it.

If you need a patch of your own, put it in `xc2/build/sites-<module>.txt`:

```
patch <address> <original-word> <new-word>   # the lifter checks the original before replacing it
```
