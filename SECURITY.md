# Security policy

## Reporting

Please report a security problem **privately**, through GitHub's *Security → Report a vulnerability* on this
repository. Do not open a public issue for anything that could be abused before it is fixed.

Useful in a report: the build, the steps, and what an attacker could do with it. Crash logs from `work\logs\`
are welcome but check them first — they can contain absolute paths.

## Scope

This project is a recompilation toolchain and a runtime. In scope:

- memory-safety bugs in the runtime or the tools that a malicious game file or mod could trigger,
- path traversal in the archive, romfs and mod loaders,
- anything that could execute code outside the intended directory.

Out of scope: the game itself, and anything that requires the attacker to already have your game dump.

## What this repository does not contain

No game code, no game assets, no keys, no firmware. If you find any of those committed by accident, report it
as a security issue so it can be removed.
