"""Render review images from the exported GLB. Requires Pillow and NumPy."""

import json
from pathlib import Path
import struct
import sys

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent
ASSEMBLED = "--assembled" in sys.argv[1:]
GLB = ROOT / ("g2-temple-assembly.glb" if ASSEMBLED else "g2-temple-board.glb")


def read_glb():
    data = GLB.read_bytes()
    magic, version, total, json_bytes, json_tag = struct.unpack_from("<4sIII4s", data)
    assert (magic, version, total, json_tag) == (b"glTF", 2, len(data), b"JSON")
    head = 20 + json_bytes
    count, tag = struct.unpack_from("<I4s", data, head)
    assert tag == b"BIN\0" and head + 8 + count == len(data)
    return json.loads(data[20:head]), memoryview(data)[head + 8:]


def geometry():
    gltf, binary = read_glb()

    def decode(index, fmt, width):
        item = gltf["accessors"][index]
        view = gltf["bufferViews"][item["bufferView"]]
        return np.frombuffer(binary, dtype=fmt, count=item["count"] * (3 if item["type"] == "VEC3" else 1),
                             offset=view["byteOffset"]).reshape(-1, width)

    def material(index):
        pbr = gltf["materials"][index]["pbrMetallicRoughness"]
        return np.array(pbr["baseColorFactor"][:3]), pbr["metallicFactor"]

    def visit(index, translation):
        node = gltf["nodes"][index]
        translation = translation + node.get("translation", [0, 0, 0])
        if "mesh" in node:
            for primitive in gltf["meshes"][node["mesh"]]["primitives"]:
                points = decode(primitive["attributes"]["POSITION"], "<f4", 3) + translation
                normals = decode(primitive["attributes"]["NORMAL"], "<f4", 3)
                triangles = decode(primitive["indices"], "<u2", 3)
                rgb, metal = material(primitive["material"])
                yield points[triangles] * 1000, normals[triangles[:, 0]], rgb, metal
        for child in node.get("children", []):
            yield from visit(child, translation)

    roots = gltf["scenes"][gltf["scene"]]["nodes"]
    result = [entry for index in roots for entry in visit(index, np.zeros(3))]
    return result


def unit(v):
    return v / np.linalg.norm(v)


def render(parts, name, towards_camera, camera_right, size):
    supersample = 2
    width, height = (x * supersample for x in size)
    forward = unit(np.array(towards_camera))
    right = unit(np.array(camera_right))
    up = unit(np.cross(forward, right))
    assert abs(np.dot(forward, right)) < .001
    scale = (width if size[0] >= size[1] else height) * .88 / (37.1 if ASSEMBLED else 26.3)
    center = np.array([3.7 if ASSEMBLED else 0.0, 0, 0])
    light = unit(-right * .48 + up * .65 + forward * .67)
    image_buffer = np.empty((height, width, 3), dtype="uint8")
    image_buffer[:] = (46, 54, 64)
    depth_buffer = np.full((height, width), -np.inf)
    triangle_count = 0
    for xyz, normals, rgb, metal in parts:
        visible = normals @ forward > .001
        points = xyz[visible]
        normals = normals[visible]
        if not len(points):
            continue
        triangle_count += len(points)
        intensity = .77 + np.maximum(normals @ light, 0) * .44
        specular = np.maximum(normals @ unit(light + forward), 0) ** 12 * metal * .34
        linear = rgb[np.newaxis, :] * intensity[:, np.newaxis] + specular[:, np.newaxis]
        srgb = np.where(linear <= .0031308, linear * 12.92, 1.055 * linear ** (1 / 2.4) - .055)
        colors = (np.clip(srgb, 0, 1) * 255 + .5).astype("uint8")
        depths = points @ forward
        xs = (points - center) @ right * scale + width / 2
        ys = height / 2 - (points - center) @ up * scale
        for z, x, y, color in zip(depths, xs, ys, colors):
            left, right_bound = max(0, int(x.min())), min(width, int(x.max()) + 1)
            top, bottom = max(0, int(y.min())), min(height, int(y.max()) + 1)
            px = np.arange(left, right_bound)[None, :] + .5
            py = np.arange(top, bottom)[:, None] + .5
            denominator = (y[1]-y[2])*(x[0]-x[2]) + (x[2]-x[1])*(y[0]-y[2])
            if abs(denominator) < 1e-9:
                continue
            a = ((y[1]-y[2])*(px-x[2]) + (x[2]-x[1])*(py-y[2])) / denominator
            b = ((y[2]-y[0])*(px-x[2]) + (x[0]-x[2])*(py-y[2])) / denominator
            c = 1 - a - b
            depth = a*z[0] + b*z[1] + c*z[2]
            depth_view = depth_buffer[top:bottom, left:right_bound]
            draw = (a >= -1e-9) & (b >= -1e-9) & (c >= -1e-9) & (depth > depth_view)
            depth_view[draw] = depth[draw]
            image_buffer[top:bottom, left:right_bound][draw] = color

    result = Image.fromarray(image_buffer)
    prefix = "assembly-" if ASSEMBLED else ""
    result.resize(size, Image.Resampling.LANCZOS).save(ROOT / f"{prefix}{name}.png")
    print(f"{name}: {triangle_count:,} visible triangles")


parts = geometry()
render(parts, "front", (0, 0, 1), (1, 0, 0), (1300, 580))
render(parts, "reverse", (0, 0, -1), (1, 0, 0), (1300, 580))
render(parts, "oblique", (0.24, -0.67, .72), (.949, 0, -.3163333333), (1300, 655))
render(parts, "front-vertical", (0, 0, 1), (0, -1, 0), (540, 1050))
