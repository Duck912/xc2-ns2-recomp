
"""spv_rename.py -- rename OpName strings in a SPIR-V module, rebuilding the instruction (its word count shrinks).

The NVN meaning of a descriptor comes from the *name* the translator baked in ("fp_c5", "support_buffer"); glslang, recompiling a block whose
struct and instance share a name, names the instance "fp_c5_1". Renaming it back makes a hand-built module a drop-in for the game's own.

  python spv_rename.py <in.spv> <out.spv> old=new [old=new ...]
"""
import struct, sys


def main(argv):
    src, dst = argv[0], argv[1]
    pairs = dict(a.split("=", 1) for a in argv[2:])
    data = open(src, "rb").read()
    words = list(struct.unpack("<%dI" % (len(data) // 4), data))
    out = words[:5]
    i = 5
    renamed = 0
    while i < len(words):
        op = words[i] & 0xFFFF
        n = words[i] >> 16
        if n == 0:
            raise SystemExit("bad instruction at word %d" % i)
        if op == 5:  # OpName: <opcode|count> <target> <string>
            raw = b"".join(struct.pack("<I", w) for w in words[i + 2:i + n])
            name = raw.split(b"\x00", 1)[0].decode("utf-8", "replace")
            if name in pairs:
                new = pairs[name].encode()
                padded = new + b"\x00" * (4 * ((len(new) + 4) // 4) - len(new))
                body = [words[i + 1]] + list(struct.unpack("<%dI" % (len(padded) // 4), padded))
                out.append(((len(body) + 1) << 16) | op)
                out.extend(body)
                renamed += 1
                i += n
                continue
        out.extend(words[i:i + n])
        i += n
    open(dst, "wb").write(struct.pack("<%dI" % len(out), *out))
    print("renamed %d name(s), %d words -> %d" % (renamed, len(words), len(out)))


if __name__ == "__main__":
    main(sys.argv[1:])
