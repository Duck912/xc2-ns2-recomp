# Project invariants

Three rules the project holds itself to. They are not style preferences: breaking one has cost a session's
work, a corrupted cache or a lost build in the past.

## 1. The game runs in a single instance, owned by the operator

The game runs on the operator's machine, in one instance, and the operator decides when it starts and stops.
Automation must **not** terminate or restart it. Read-only access to logs and snapshots is unrestricted at any
time. Any experiment that needs a different launch configuration is prepared as a command and run by the
operator; after the process exits, the next launch waits about 25 seconds (the runtime releases the mapping
lazily).

## 2. The shader cache is append-only

The translated shader cache is only ever added to. It is not rebuilt or deleted: a rebuild costs the whole
corpus (21,171 programs) and has silently shadowed hand-edited `.spv` files before (`spirv.preload.pack` takes
precedence over loose files). When a shader patch is edited, run `xc2\scripts\patch-shaders.ps1 -Check` and
expect exit code 0.

## 3. No game data, lifted code, shader cache or keys are committed or released

The repository contains tooling, runtime code and documentation only. The game's files, the C++ the lift
produces from them, the shader cache built from them and any key material stay on the machine that owns the
game. Builds are not distributed: the build embeds the lifted game code, so it is built locally from the
player's own dump.
