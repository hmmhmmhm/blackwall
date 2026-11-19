"""Bounded declarative scenes compiled into calls to the pinned CFW primitives."""
import json


def compile_scene(scene):
    if not isinstance(scene, dict) or set(scene) != {'frames'}:
        raise ValueError('Scene must contain only frames')
    frames = scene['frames']
    if not isinstance(frames, list) or not 1 <= len(frames) <= 60:
        raise ValueError('Expected 1..60 frames')
    lines = ['#include <stdint.h>', '#include "draw.c"',
             'void render(uint8_t *fb, uint32_t frame) { switch(frame) {']
    def number(value, low, high):
        if type(value) is not int or not low <= value <= high:
            raise ValueError('Scene integer outside bounds')
        return value
    for index, operations in enumerate(frames):
        if not isinstance(operations, list) or len(operations) > 64:
            raise ValueError('Expected at most 64 operations per frame')
        lines.append(f'case {index}:')
        for op in operations:
            if not isinstance(op, dict):
                raise ValueError('Operation must be an object')
            if op.get('type') == 'text' and set(op) == {'type', 'x', 'y', 'text', 'color'}:
                text = op['text']
                if not isinstance(text, str) or len(text) > 80 or any(not 32 <= ord(c) <= 126 for c in text):
                    raise ValueError('Text must be at most 80 printable ASCII characters')
                x, y = number(op['x'], -576, 576), number(op['y'], -288, 288)
                color = number(op['color'], 0, 15)
                lines.append(f'draw_string(fb,576,288,{x},{y},{json.dumps(text)},{color},-1);')
            elif op.get('type') == 'rect' and set(op) == {'type', 'x', 'y', 'width', 'height', 'color'}:
                x, y = number(op['x'], 0, 575), number(op['y'], 0, 287)
                w, h = number(op['width'], 1, 576-x), number(op['height'], 1, 288-y)
                color = number(op['color'], 0, 15)
                lines.append(f'for(unsigned y={y};y<{y+h};y++) for(unsigned x={x};x<{x+w};x++) set_pixel4(fb,576,x,y,{color});')
            else:
                raise ValueError('Unsupported operation or fields')
        lines.append('break;')
    lines.append('default: break; } }')
    return '\n'.join(lines)+'\n'
