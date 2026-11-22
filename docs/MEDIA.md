# Films and the media path

How the Switch 2 edition's films are played by a recompiled PC build, and the parts that are easy to get wrong. Written
down because a recompilation of any NS2 title with video hits the same three walls: a decoder that opens the GPU driver
directly, an end-of-stream protocol that is easy to invert, and a player that lives in guest code.

## What the edition does differently

| | Switch 1 edition | Switch 2 edition |
|---|---|---|
| codec | H.264/VP9, 720p–1080p | **AV1, up to 3840×2160** |
| player | `movie::Player` in the game | the same shape, in guest code (`subsdk0`), on `nn::codec` |
| inserts | rare | memory films of 7–41 s played **over a live cutscene**, which must be handed back |

The runtime does not decode anything itself: it takes `nn::codec` over and lets the guest player drive it, exactly as the
SDK's own library would.

## The layers

```
guest player (subsdk0, movie::)          <- state machine, owns the scene
  MediaExtractor (guest)                 <- demuxes the file through nn::fs
  MediaDecoder -> VideoDecoder           <- owns the output buffers and fences
    nn::codec  (host, src/media/video_codec.cpp)
      dav1d / Vulkan Video / D3D11VA     <- the actual decoder
    nn::codec audio (host, src/media/movie_adec.cpp)
      Vorbis, placeholder clock
```

## The codec protocol, as the player uses it

- **InitDecoderImagePool**: the guest asks for `w × h`, a format and a count; the pool is the buffer the player reads
  from. Keep the count the guest asked for — a pool that silently holds fewer images stalls the first frame.
- **Acquire**: returns an index and a fence. If the pool has no free buffer the SDK answers `3604` and the client polls;
  returning success there makes the player spin. If a buffer is free but no picture is ready, **decode one packet inline**
  rather than handing out a fence nothing will complete — a client waiting on such a fence makes no further call, so
  nothing ever completes it (this is the "green first frame" bug).
- **Submit**: take every packet. The client never looks at the "queue full" result (`3603`) and does not retry; eight
  queued packets is only the watermark of the "submission ready" event, and that watermark is about the *input* queue.
- **Properties**: `3604` until the buffer holds a picture, then width, height, timestamp and the end-of-stream flag.
- **Release**: returns the buffer to the pool and bumps its generation; fences are generation-tagged.

The end of a stream is **its own output**: every picture goes out unflagged, then one output with no picture (`w=h=0`)
carries the flag. Players drop an output that carries the flag instead of showing it and then wait for the picture they
counted on, so a flag on a real picture never completes. The reference implementation keeps `eos_pending` for exactly
this (`nxnative`, `dm/host/hle_codec_video.c`).

## The audio track is a clock

The film's audio is a placeholder: the real sound belongs to the scene underneath. The player still paces itself on the
frames this decoder hands out, so:

- it must not run ahead of the picture (`time <= last delivered picture pts + 0.5 s`), or the player skips the picture
  forward to catch up with its own clock;
- it must still **report an end**. The player's finish condition covers every track
  (`movie::detail::ExtractorAdapterImpl::AllTracksEndOfStream`, `AudioFrame::GetEndOfStreamState`), so a track that never
  ends keeps the whole film from finishing. A zero-byte packet is that end, and the last frame gets the flag the SDK's own
  `AudioFrame::SetEndOfStreamState` writes (one byte at `frame + 0x10`).

## Why an inserted film is harder than a standalone one

A standalone cutscene owns the screen: when it ends, the player tears itself down. An inserted film plays over a live
scene, and the scene only resumes when the player says "finished" — which it says only when it has seen the end of every
track. Miss any one of those and the picture stops on its last frame while the sound continues, the scene waits, gives up
about 35 s later, and jumps to the next scene, skipping the rest of the cutscene.

Measured after the fixes (RX 6800 XT):

| | before | after |
|---|---|---|
| inserted film, last picture to scene back | ~35 s (forced stop by the scene) | **0.24 s** |
| long cutscene | 96 s, 2,833 pictures, end to end | unchanged |
| first picture after its first packet | 381 ms (fence nobody completed) | 37 ms |

## Debugging it

- `[media] player_trace` and `[media] video_decoder_log` in `nxrt.ini`: the player's messages, timers, fences, the
  decoder's queues, and a thread dump when no picture arrives for a second.
- `<exe>.names` next to the executable (written by the build from the lift's dynsym tables): thread dumps then read
  `subsdk0!movie::MediaDecoder::Stop` instead of `f_760001be70`. Without it, a dump is a list of addresses.
- `docs/COMPATIBILITY.md` for what still looks wrong on which GPU.

A clean install is part of the test: with `[media] player_trace` off (the default) the poke must still be routed, or the
film shows the one-picture-a-second stall with nothing in the log to explain it.

## Mistakes worth not repeating

1. **Flagging a picture with end of stream.** Players drop it and wait for the picture they counted on.
2. **Waiting for the client to read the end.** A client that stops one picture short never reads it; deliver the flag as
   a separate output.
3. **Treating the film's audio as sound.** It is a clock, and it still has to end.
4. **Completing fences only on guest calls.** A client parked in a fence makes no call; complete it at acquire time when
   there is nothing to pair.
5. **Naming frames by the nearest preceding symbol.** The exports are sparse; an address 42 KiB past a name is not that
   function.
6. **Letting a fix depend on a diagnostic flag.** The per-frame timer poke is what makes the player's loop wake at all, and
   it was installed inside the player-trace setup, so every development run (trace on) played and every clean install
   (trace off, the default) read one picture a second and stopped. A default-on setting has to be exercised by a default-off
   machine: test the package, not only the dev profile.
