// SPDX-License-Identifier: MIT
// Ampere warp-cooperative matrix instructions: HMMA (tensor-core multiply-add), LDSM (matrix fragment from shared memory) and
// MOVM (matrix transpose inside registers). Opcodes and field positions: [NAK] Mesa sm70_encode.rs OpHmma / OpLdsm / OpMovm,
// which is the same source nxnative's Ryujinx fork decodes them with (InstEmitAmpereTensor.cs, MIT); the fragment layouts it
// documents are PTX's mma.m16n8k16 / ldmatrix / movmatrix, i.e. lane L holds row L / 4 (and L / 4 + 8) at columns 2 (L % 4)
// and + 1. Register fields as everywhere else: Rd 16..23, Ra 24..31, Rb 32..39, Rc 64..71.
namespace Nx.Shaders.Ampere
{
    public static partial class SassDecoder
    {
        static void RegisterTensor()
        {
            // HMMA 0x23c: D (16x8) = A (16x16 or 16x8) * B (16x8 or 8x8) + C. Size 75..76 and 78..79 (0 m16n8k8, 1 m16n8k16),
            // F32 accumulator and result 76 (else packed halves), source type 82..84 (0 f16). Rd, Ra, Rb, Rc.
            Op12(0x23c, c =>
            {
                int size = c.I(75, 2) | (c.I(78, 2) << 1);
                bool f32 = c.B(76);
                int src = c.I(82, 3);
                c.Op = "HMMA"; c.Mod(size == 1 ? "16816" : "1688"); c.Mod(f32 ? "F32" : "F16");
                if (src != 0) c.Mod("SRC" + src);
                c.Dst = 1; c.Add(c.R(16), c.R(24), c.R(32), c.R(64));
            });
            // LDSM 0x83b: count 72..74 (1, 2, 4 eight-by-eight matrices of halves), mode 78..80 (1 = transposed), Rd, [Ra + UR + offset]
            Op12(0x83b, c =>
            {
                int count = 1 << c.I(72, 3);
                int mode = c.I(78, 3);
                c.Op = "LDSM"; c.Mod("16"); c.Mod(mode == 1 ? "MT88" : "M88"); c.Mod(count.ToString());
                if (count > 4 || mode > 1) c.Mod("?mode" + mode + "count" + count);
                c.Dst = 1; c.Add(c.R(16), MemOp(c, c.I(24, 8), null, c.B(91) ? c.I(32, 6) : -1, c.S(40, 24)));
            });
            // MOVM 0x23a: the 8x8 matrix the warp holds, transposed into the same layout. Mode 78..80 (0 = MT88). Rd, Ra.
            Op12(0x23a, c =>
            {
                int mode = c.I(78, 3);
                c.Op = "MOVM"; c.Mod("16"); c.Mod(mode == 0 ? "MT88" : "?mode" + mode);
                c.Dst = 1; c.Add(c.R(16), c.R(24));
            });
        }
    }
}
