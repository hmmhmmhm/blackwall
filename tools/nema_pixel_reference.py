"""Command-driven pixel reference, deliberately not a Nema GPU implementation.

The sole profile treats A4 as a high-nibble-first coverage mask, white source
as luminance 255, and integer rectangle/clip bounds as half-open. Output is
the original CPU font decoder's 8-bit coverage on black. Hardware sampling,
channel conversion and rounding have not been validated.
"""
import struct

PROFILE = 'white-a4-on-black-reference-v1'
ORDER = [0, 4, 8, 0x110, 0x114, 0x1d0, 0x118, 0x11c, 0x1c, 0x10, 0x14, 0x18,
         0x174, 0x168, 0x160, 0x164, 0x16c, 0x170, 0x104, 0x108, 0xff000100]


def float_word(value):
    return struct.unpack('<I', struct.pack('<f', value))[0]


def xy(word):
    return word & 0xffff, word >> 16


def render_white_a4_reference(words, initial, read_source):
    if (len(words) != 2 * len(ORDER) or list(words[::2]) != ORDER
            or any(type(w) is not int or not 0 <= w <= 0xffffffff for w in words)):
        raise ValueError('Only the reviewed ordered single-glyph command stream is supported')
    state = dict(zip(words[::2], words[1::2]))
    stride = state[4] & 0xffff
    required = {0: 0x2100a000, 4: (9 << 24) | stride, 8: (32 << 16) | 64,
                0x1d0: 0x504, 0x118: 0, 0x11c: 0x141f801f, 0x1c: 0xffffffff,
                0x160: float_word(1), 0x164: 0, 0x16c: 0, 0x170: float_word(1),
                0xff000100: 2}
    if stride not in (64, 80) or any(state[k] != v for k, v in required.items()):
        raise ValueError('Unsupported surface, blend, shader, color or transform')
    if len(initial) != stride * 32 or any(initial):
        raise ValueError('The reference only supports an entirely zero destination')
    x0, y0 = xy(state[0x104])
    x1, y1 = xy(state[0x108])
    cx0, cy0 = xy(state[0x110])
    cx1, cy1 = xy(state[0x114])
    if not (0 <= x0 < x1 <= 64 and 0 <= y0 < y1 <= 32
            and 0 <= cx0 <= cx1 <= 64 and 0 <= cy0 <= cy1 <= 32):
        raise ValueError('Unsupported rectangle or clip bounds')
    if state[0x168] != float_word(-x0) or state[0x174] != float_word(-y0):
        raise ValueError('Only the matching integer source translation is supported')
    width, height = x1 - x0, y1 - y0
    source_stride = width // 2 + 1
    padded_width = width + (2 if width % 2 == 0 else 0)
    if (state[0x14] != (0x34 << 24) | source_stride
            or state[0x18] != (height << 16) | padded_width):
        raise ValueError('Unsupported A4 format, filter, source dimensions or row stride')
    size = source_stride * height
    packed = read_source(state[0x10], size)
    if len(packed) != size:
        raise ValueError('Truncated source texture')
    frame = bytearray(initial)
    samples = 0
    for y in range(max(y0, cy0), min(y1, cy1)):
        for x in range(max(x0, cx0), min(x1, cx1)):
            sx, sy = x - x0, y - y0
            nibble = (packed[sy * source_stride + sx // 2] >> (4 if sx % 2 == 0 else 0)) & 15
            frame[y * stride + x] = nibble * 17
            samples += 1
    return bytes(frame), dict(profile=PROFILE, width=64, height=32, stride=stride,
                             draw=[x0, y0, x1, y1], clip=[cx0, cy0, cx1, cy1],
                             source=state[0x10], source_stride=source_stride, samples=samples,
                             hardware_validated=False, gpu_executed=False)
