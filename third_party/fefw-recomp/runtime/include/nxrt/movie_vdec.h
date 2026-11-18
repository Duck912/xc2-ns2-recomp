// SPDX-License-Identifier: GPL-3.0-or-later
// movie::VideoDecoder of the Switch 2 movie library on the host (src/media/movie_vdec.cpp): AV1 through dav1d into the player's CPU frames,
// for a title with game::Info::movie_video_decoder. [media] movies = host (default) | skip (every movie fails to open, core/switch2.cpp).
#pragma once

namespace nxrt::media {

// Registers the host decoder and forces main's imports to it. False when off, not such a title, or built without dav1d (NXRT_HAVE_DAV1D).
// Call before the modules are linked; safe to call more than once.
bool install_movie_decoder_hle();

// True once install_movie_decoder_hle() routed the decoder to the host: the game module then puts its player on the CPU-frame path.
bool movie_decoder_enabled();

// Called once per presented frame. Decoded pictures are handed to the player here as well as in its own calls, so a player that waits
// on the output event is woken by the game's frame loop and not only by its previous call (the Switch 1 port, MacNativeGames
// xc2-recomp ov_movie.c movie_tick, does the same). Also reports a decoder that has stopped being called while it still holds work.
void movie_tick();

}  // namespace nxrt::media
