# Troubleshooting

Symptom first. Each section says what to look at, and what it usually means.

If you are here because the build failed, go to [QUICKSTART.md](QUICKSTART.md#common-failures) instead: that page has
the failures people actually hit.

## Read the log before anything else

Every launch writes one file: `work\logs\play-301-<time>.log`. The first twenty lines are the ones that matter.

`~
runtime: nxrt starting (ABI ...)
gfx: features: geometry 1 float64 1 ... hostMemImport 1 pushDesc 1 uboRobustness 0
gfx: swapchain 2560x1440, 4 images, format 64, color space 1000104008 (hdr10), present mode fifo
nvn: gpu: ... pools imported, shader cache ...
`~

- `gfx: features:` is what the driver says it can do. A `0` where you expect a `1` is a real clue: `hostMemImport`
  missing means the runtime cannot import the guest's memory, and nothing will work.
- `gfx: swapchain` tells you the actual resolution, colour space and present mode. If the window is not what you
  asked for, it is here.
- If the log stops before `swapchain`, the failure is in device creation, not in the game.

Two switches turn the log into a real diagnostic:

`~ini
[gfx] validation = 1     ; the Vulkan validation layer's VUIDs - always the first thing to try
[gfx] log_fps = 1        ; one line per second: frame times, plus the GPU time of the present pass
`~

## Nothing renders: the window is black

Work through these in order; each one eliminates a layer.

**1. Is the GPU doing anything at all?**

With `[gfx] log_fps = 1`, look at the present pass time in the per-second line.

- **Non-zero** (0.02 ms and up): the GPU is executing and the picture is wrong. Go to step 3.
- **Zero, or the line never appears**: the GPU is not executing. Go to step 2.

**2. Was the device lost early?**

Search the log for `device lost`, `VK_ERROR_DEVICE_LOST`, `vkQueueSubmit2` and `vkWaitForFences`. A device that
died at startup makes every later command a no-op: the game keeps running at full speed, audio works, the draw
counts look normal, and every pixel stays black. That combination is the signature.

If you find it, or if you are on a GPU we have never tested, try these in order:

`~ini
[nvn] gpl = 0            ; VK_EXT_graphics_pipeline_library - the newest, least tested path
[nvn] async_submit = 0   ; one submission in flight instead of several
[gfx] present_mode = fifo
`~

Then run with `[gfx] validation = 1` and send the first twenty VUIDs. Without them the next step is guesswork.

**3. The GPU runs, but the image is empty**

Check whether the failure is in the final composite rather than in the scene: if the **video cutscenes** are black
too, it cannot be the 3D pipeline — the two share nothing except the last blit. That points at the composite or at
a device that died silently.

Also useful: `[nvn] fb_debug = 1` explains why a sampler binding is or is not treated as a self-sampled
attachment, and the log warns when a binding gets a **dummy view** because the sampled format does not match what
the shader declares (`R8UI` bound where the shader wants a float sampler, for instance).

## The driver crashes, or the window closes

The event log will show `nvlddmkm` or `amdgpu` errors. A TDR is not a timeout here — raising `TdrDelay` does
not help, because the driver really did fault.

- `[nvn] gpl = 0` first. Pipeline libraries are the newest Vulkan feature this runtime uses.
- `[nvn] async_submit = 0` second.
- If it only happens with the frame-rate trace on, that trace adds a barrier per frame; turn it off.

## The frame rate is wrong

**30 fps instead of 60.** The game paces itself at 30 Hz unless told otherwise: `tools\run\play-301.cmd -60`.

**Well under 60 everywhere.** Check the internal resolution first: the game runs dynamic resolution between 360p
and 720p and the upscaler works from that. `[gfx] log_fps = 1` shows the frame time; `[nvn] replay_stats = 60`
shows whether the cost is on the CPU side (replay) or the GPU side.

**Stutters, not a low average.** Look for the `hitch:` lines. Slow frames during area transitions are texture
uploads and memory-pool imports; slow frames in steady play are worth reporting.

## Graphics look wrong

- **Blue-grey rim** where objects meet the cloud sea, and **shimmer** in the cloud sea in motion: both live inside
  the game's own 640x360 volumetric fog. Known, described in [COMPATIBILITY.md](COMPATIBILITY.md).
- **Two shader patches are not distributed** (they are derived from the game's shaders), so a build from this
  repository alone keeps two fog/UV defects. See [BUILD.md](BUILD.md), section 4.4.
- **Missing or wrong textures**: the ASTC-to-BC7 transcode runs at load time; a broken transcode shows as flat or
  black textures. Check that `fetch_third_party.ps1` ran — see [BUILD.md](BUILD.md), section 4.1.
- **The whole screen is one flat colour**: usually a shader that did not translate. Search the log for
  `no translated shader`.

## No audio

The runtime decodes Opus in software and hands it to the host's audio device. If there is silence:

- check the log for `audio:` lines naming the output device;
- the game's own volume settings are separate, and the title screen starts muted in some saves.

## The game will not start

| what you see | what it means |
|---|---|
| `MapViewOfFileEx error 487` | the previous instance has not released its memory yet. Wait about 25 s after it exits |
| it starts and exits immediately | read the log: a missing `NXRT_FS_ROMFS` path is the usual cause |
| `permission denied` when linking | the game is running; it is single-instance |
| the window opens, 22 s of nothing, then it plays | that is the first-run pipeline compile. It does not happen again |
| `VK_ERROR_INCOMPATIBLE_DRIVER` right after start-up | the GPU driver is older than Vulkan 1.3: update it (see "The setup stops at the prefill step") |

## The setup stops at the prefill step

`the headless prefill named no block` means the short headless run never got as far as drawing. That run is the first
thing that touches Vulkan, so a driver problem shows up here, before the game ever opens a window. The setup prints
the reason it found in the run's own log (`setup\prefill.log` inside the install folder).

`~
prefill: the GPU driver does not offer Vulkan 1.3 and the game needs it: install the newest driver for the card
~

- **`VK_ERROR_INCOMPATIBLE_DRIVER`, or `Vulkan 1.3 is required`** — the GPU driver is older than Vulkan 1.3, and this
  build needs it. Install the newest driver for the card: the Vulkan runtime ships with the driver, so one update fixes
  both. Nothing in the package needs to change.
- **`no Vulkan loader found`** — `vulkan-1.dll` is not on the machine. Same fix; it also means no driver is installed
  for the adapter in use (a VM, or a remote desktop session, does that too).
- **`no usable Vulkan 1.3 GPU`** — Vulkan starts, but every GPU it lists falls short; the line names each one and what
  it is missing.

The same lines appear in the game's own log (`work\logs\play-301-<time>.log`) when it is started directly instead of
from the setup.

## When you report a problem

Open an issue with the log, your GPU and driver, and which build you ran. If you can, say whether it also happens
with `[dlss] upscaler = taau` and with a 1280x720 window — that separates renderer problems from upscaler problems.
