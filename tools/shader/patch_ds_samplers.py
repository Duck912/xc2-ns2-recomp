#!/usr/bin/env python3
"""Rewrite the samplers that read a depth-stencil texture's stencil plane so the descriptor is legal.

    python tools/shader/patch_ds_samplers.py --cache <dir> --log <play-301-*.log> [--dry-run]

Why this exists: the console lets a FLOAT sampler read the stencil plane, and the 8-bit value lands in the float
register with its bits unchanged (the deferred lighting's class mask reads it back with floatBitsToInt(x) & 24).
Vulkan has no such format, so the runtime binds an S8_UINT view, and the shader's declared float sampler no longer
matches the descriptor - VUID-vkCmdDrawIndexed-format-07753, undefined behaviour. AMD tolerates it; NVIDIA does not.

The fix is to declare the sampler as uint and bitcast the fetched value back to float, which keeps the bits exactly
and makes the descriptor legal. Doing it here rather than shipping patched modules keeps the project free of game
data: this tool rewrites the player's own cache.

Which samplers need it is not knowable statically (it depends on what the game binds at draw time), so the runtime
reports it, one line per (shader, binding):

    ds_debug: fs <hash> samples the stencil plane of texture <id> through a float sampler (s<set>b<binding>)

The prefix is a leftover: the report is no longer a debug switch. Builds up to 0.1.2 only wrote it when [nvn] ds_debug
was 1, which left the one run that actually lost the device with nothing to patch from (issue #10); the runtime now
always writes it. This tool reads any play log and rewrites those modules.

The transform, per sampled image type:
    OpTypeImage %float ...            ->  OpTypeImage %uint ...
    %r = OpImageSample* %v4float ...  ->  %r = OpImageSample* %v4uint ...
                                          %f = OpBitcast %v4float %r     (new, and every use of %r now uses %f)

Downstream code is untouched: it still sees a v4float whose bits are the stencil byte.
"""
import argparse
import os
import re
import struct
import sys

# opcodes used here
OP_TYPE_VECTOR = 23
OP_TYPE_IMAGE = 25
OP_TYPE_SAMPLED_IMAGE = 27
OP_TYPE_POINTER = 32
OP_VARIABLE = 59
OP_LOAD = 61
OP_BITCAST = 124
OP_DECORATE = 71
OP_NAME = 5
OP_MEMBER_NAME = 6
OP_ENTRY_POINT = 15
OP_TYPE_INT = 21
OP_TYPE_FLOAT = 22
OP_CONSTANT = 43
OP_COMPOSITE_EXTRACT = 81
OP_SAMPLED_IMAGE = 86
OP_IMAGE = 100

DEC_DESCRIPTOR_SET = 34
DEC_BINDING = 33

# every instruction whose result type becomes v4uint when the image's sampled type becomes uint
SAMPLE_OPS = {87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 305, 306, 307, 308, 309, 310, 311, 312, 313, 314}


class Mod:
    def __init__(self, data):
        self.words = list(struct.unpack("<%dI" % (len(data) // 4), data))
        if self.words[0] != 0x07230203:
            raise SystemExit("not a SPIR-V module")
        self.insts = []          # (offset, opcode, wordcount)
        i = 5
        while i < len(self.words):
            wc = self.words[i] >> 16
            if wc == 0 or i + wc > len(self.words):
                raise SystemExit("malformed instruction stream at word %d" % i)
            self.insts.append((i, self.words[i] & 0xFFFF, wc))
            i += wc

    def find(self, op):
        return [n for n in self.insts if n[1] == op]

    def type_of(self, result_id):
        """The result type of the instruction that defines result_id, or None."""
        for at, op, wc in self.insts:
            if op in (OP_VARIABLE, OP_LOAD, OP_BITCAST, OP_COMPOSITE_EXTRACT, OP_SAMPLED_IMAGE, OP_IMAGE) or op in SAMPLE_OPS:
                if wc >= 3 and self.words[at + 2] == result_id:
                    return self.words[at + 1]
        return None

    def result_id(self, at):
        return self.words[at + 2] if (self.words[at] >> 16) >= 3 else None


def scalar_of(mod, type_id):
    """The scalar type behind a scalar or vector type id."""
    for at, op, wc in mod.find(OP_TYPE_VECTOR):
        if mod.words[at + 1] == type_id:
            return mod.words[at + 2]
    return type_id


def find_type(mod, op, predicate):
    for at, o, wc in mod.find(op):
        if predicate(mod.words, at):
            return mod.words[at + 1]
    return None


def main(argv):
    ap = argparse.ArgumentParser(description="Declare the stencil-plane samplers as uint so the descriptor is legal.")
    ap.add_argument("--cache", required=True, help="the spirv cache folder")
    ap.add_argument("--log", default="", help="a play-301 log with [nvn] ds_debug = 1")
    ap.add_argument("--list", default="", help="hash:s<set>b<binding>,... instead of --log")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    wanted = {}
    if a.log:
        if not os.path.exists(a.log):
            print("ERROR: no log at " + a.log, file=sys.stderr)
            return 3
        pat = re.compile(r"ds_debug: fs ([0-9a-f]{16}) .*?\(s(\d+)b(\d+)\)")
        pat_r8ui = re.compile(r"sampled texture \d+ \(R8UI,.*?shader ([0-9a-f]{16}) binding \S+ \(NVN slot \d+, set (\d+) binding (\d+)\)")
        with open(a.log, encoding="utf-8", errors="replace") as f:
            for line in f:
                m = pat.search(line) or pat_r8ui.search(line)
                if m:
                    wanted.setdefault(m.group(1), set()).add((int(m.group(2)), int(m.group(3))))
    if a.list:
        for item in a.list.split(","):
            item = item.strip()
            if not item:
                continue
            h, sb = item.split(":")
            m = re.match(r"s(\d+)b(\d+)$", sb)
            wanted.setdefault(h, set()).add((int(m.group(1)), int(m.group(2))))
    if not wanted:
        print("ERROR: no ds_debug line found; run once with [nvn] ds_debug = 1", file=sys.stderr)
        return 3

    print("shaders to patch: %d" % len(wanted))
    for h in sorted(wanted):
        print("  %s  %s" % (h, ", ".join("s%db%d" % t for t in sorted(wanted[h]))))
    if a.dry_run:
        return 0

    done = failed = 0
    for h in sorted(wanted):
        path = os.path.join(a.cache, h + ".spv")
        if not os.path.exists(path):
            print("  %s: no module in the cache" % h, file=sys.stderr)
            failed += 1
            continue
        with open(path, "rb") as f:
            mod = Mod(f.read())

        # the variables at the requested set/bindings
        sets, bindings = {}, {}
        for at, op, wc in mod.find(OP_DECORATE):
            if wc < 4:
                continue
            if mod.words[at + 2] == DEC_DESCRIPTOR_SET:
                sets[mod.words[at + 1]] = mod.words[at + 3]
            elif mod.words[at + 2] == DEC_BINDING:
                bindings[mod.words[at + 1]] = mod.words[at + 3]
        targets = set()
        for vid, b in bindings.items():
            if (sets.get(vid), b) in wanted[h]:
                targets.add(vid)
        if not targets:
            print("  %s: no variable at the recorded set/binding" % h, file=sys.stderr)
            failed += 1
            continue

        f32 = find_type(mod, OP_TYPE_FLOAT, lambda w, at: w[at + 2] == 32)
        if f32 is None:
            print("  %s: the module has no 32-bit float type" % h, file=sys.stderr)
            failed += 1
            continue
        # the uint types the transform needs, declared if the module does not have them yet
        uint32 = find_type(mod, OP_TYPE_INT, lambda w, at: w[at + 2] == 32 and w[at + 3] == 0)
        pre_types = []
        if uint32 is None:
            uint32 = mod.words[3]
            mod.words[3] += 1
            pre_types.append([OP_TYPE_INT | (4 << 16), uint32, 32, 0])
        v4uint = find_type(mod, OP_TYPE_VECTOR, lambda w, at: w[at + 2] == uint32 and w[at + 3] == 4)
        if v4uint is None:
            v4uint = mod.words[3]
            mod.words[3] += 1
            pre_types.append([OP_TYPE_VECTOR | (4 << 16), v4uint, uint32, 4])
        # (the declarations are inserted at the end: inserting here would invalidate every offset below)

        # Every sampler of the same kind shares one OpTypeImage/OpTypeSampledImage, so the patched binding needs its
        # own copy of that chain - otherwise the sibling samplers would change too.
        def pointee_of(ptr_id):
            for at, op, wc in mod.find(OP_TYPE_POINTER):
                if mod.words[at + 1] == ptr_id:
                    return mod.words[at + 2], mod.words[at + 3]     # storage class, pointee
            return None, None

        added = []
        created_images = {}
        created_sampled = {}
        created_ptrs = {}
        first_img_pos = None
        sampled_types = set()
        ok = True
        for vid in sorted(targets):
            ptr = mod.type_of(vid)
            storage, pointee = pointee_of(ptr)
            if pointee is None:
                ok = False
                break
            old_image = None
            sampled = False
            for at, op, wc in mod.find(OP_TYPE_SAMPLED_IMAGE):
                if mod.words[at + 1] == pointee:
                    old_image = mod.words[at + 2]
                    sampled = True
            if old_image is None:
                for at, op, wc in mod.find(OP_TYPE_IMAGE):
                    if mod.words[at + 1] == pointee:
                        old_image = pointee
            if old_image is None:
                ok = False
                break
            img_at = [at for at, op, wc in mod.find(OP_TYPE_IMAGE) if mod.words[at + 1] == old_image][0]
            if first_img_pos is None:
                first_img_pos = img_at + (mod.words[img_at] >> 16)
            img_tail = tuple(mod.words[img_at + 3:img_at + (mod.words[img_at] >> 16)])
            group = []
            # Reuse an existing identical uint OpTypeImage / OpTypeSampledImage / OpTypePointer if the module
            # (or an earlier target in this pass) already declared one, because SPIR-V forbids duplicate
            # non-aggregate type declarations.
            new_image = created_images.get(img_tail)
            if new_image is None:
                new_image = find_type(
                    mod, OP_TYPE_IMAGE,
                    lambda w, at: w[at + 2] == uint32 and tuple(w[at + 3:at + (w[at] >> 16)]) == img_tail,
                )
            if new_image is None:
                new_image = mod.words[3]
                mod.words[3] += 1
                decl = list(mod.words[img_at:img_at + (mod.words[img_at] >> 16)])
                decl[1] = new_image
                decl[2] = uint32
                group.append(decl)
                created_images[img_tail] = new_image
            if sampled:
                new_sampled = created_sampled.get(new_image)
                if new_sampled is None:
                    new_sampled = find_type(mod, OP_TYPE_SAMPLED_IMAGE, lambda w, at: w[at + 2] == new_image)
                if new_sampled is None:
                    new_sampled = mod.words[3]
                    mod.words[3] += 1
                    group.append([OP_TYPE_SAMPLED_IMAGE | (3 << 16), new_sampled, new_image])
                    created_sampled[new_image] = new_sampled
                new_ptr = created_ptrs.get((storage, new_sampled))
                if new_ptr is None:
                    new_ptr = find_type(
                        mod, OP_TYPE_POINTER,
                        lambda w, at: w[at + 2] == storage and w[at + 3] == new_sampled,
                    )
                if new_ptr is None:
                    new_ptr = mod.words[3]
                    mod.words[3] += 1
                    group.append([OP_TYPE_POINTER | (4 << 16), new_ptr, storage, new_sampled])
                    created_ptrs[(storage, new_sampled)] = new_ptr
                sampled_types.add(new_sampled)
            else:
                new_sampled = None
                new_ptr = created_ptrs.get((storage, new_image))
                if new_ptr is None:
                    new_ptr = find_type(
                        mod, OP_TYPE_POINTER,
                        lambda w, at: w[at + 2] == storage and w[at + 3] == new_image,
                    )
                if new_ptr is None:
                    new_ptr = mod.words[3]
                    mod.words[3] += 1
                    group.append([OP_TYPE_POINTER | (4 << 16), new_ptr, storage, new_image])
                    created_ptrs[(storage, new_image)] = new_ptr
            if group:
                added.append([img_at + (mod.words[img_at] >> 16), group])
            # the variable, the load that reads it and the OpSampledImage built from that load all move to the copy
            for at, op, wc in mod.find(OP_VARIABLE):
                if mod.words[at + 2] == vid:
                    mod.words[at + 1] = new_ptr
            if new_sampled is not None:
                loads = []
                for at, op, wc in mod.find(OP_LOAD):
                    if wc >= 4 and mod.words[at + 3] == vid:
                        mod.words[at + 1] = new_sampled
                        loads.append(mod.words[at + 2])
                built = []
                for at, op, wc in mod.find(OP_SAMPLED_IMAGE):
                    if wc >= 4 and mod.words[at + 3] in loads:
                        mod.words[at + 1] = new_sampled
                        built.append(mod.words[at + 2])
                # texelFetch goes through OpImage, which takes the load directly (no OpSampledImage in between)
                for at, op, wc in mod.find(OP_IMAGE):
                    if wc >= 4 and mod.words[at + 3] in built + loads:
                        mod.words[at + 1] = new_image
                        sampled_types.add(new_image)
        if not ok or not sampled_types:
            print("  %s: the binding is not a sampled image" % h, file=sys.stderr)
            failed += 1
            continue
        # every sample through the copied chain returns v4uint, then bitcasts back to the float vector it had
        inserts = []
        retyped = 0
        for at, op, wc in mod.insts:
            if op not in SAMPLE_OPS or wc < 4:
                continue
            res_type = mod.words[at + 1]
            if scalar_of(mod, res_type) != f32:
                continue
            if mod.type_of(mod.words[at + 3]) not in sampled_types:
                continue
            mod.words[at + 1] = v4uint
            retyped += 1
            inserts.append((at + wc, mod.words[at + 2], res_type))   # after this instruction: bitcast back

        if not retyped:
            print("  %s: no sample instruction found for those images" % h, file=sys.stderr)
            failed += 1
            continue

        bound = mod.words[3]
        new_ids = []
        for pos, old_id, back_type in inserts:
            new_ids.append((pos, old_id, back_type, bound))
            bound += 1
        mod.words[3] = bound
        # every later use of the sample result is the float bitcast
        remap = {old: nid for (_p, old, _t, nid) in new_ids}
        for at, op, wc in mod.insts:
            for k in range(3, wc):          # 1 is the result type and 2 the result id: never rename those
                v = mod.words[at + k]
                if v in remap:
                    mod.words[at + k] = remap[v]
        # one insertion pass, last position first, so no offset moves under us
        plan = [(pos, [OP_BITCAST | (4 << 16), back_type, nid, old]) for (pos, old, back_type, nid) in new_ids]
        # the cloned type declarations go right after the image type they copy: still in the type section, and
        # always before the variable that now uses them
        if pre_types:
            if added:
                added[0][1] = pre_types + added[0][1]  # the uint types go with the first clone
            elif first_img_pos is not None:
                added.append([first_img_pos, pre_types])
        for pos, group in added:
            plan.append((pos, [w for decl in group for w in decl]))
        for pos, words in sorted(plan, key=lambda x: x[0], reverse=True):
            mod.words[pos:pos] = words

        data = struct.pack("<%dI" % len(mod.words), *mod.words)
        out = path
        if not a.dry_run:
            bak = path + ".orig"
            if not os.path.exists(bak):
                with open(path, "rb") as f:
                    orig = f.read()
                with open(bak, "wb") as f:
                    f.write(orig)
            with open(out, "wb") as f:
                f.write(data)
        print("  %s: %d sample instruction(s) retyped" % (h, retyped))
        done += 1

    print("patched %d, skipped %d" % (done, failed))
    return 0 if failed == 0 else 5


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
