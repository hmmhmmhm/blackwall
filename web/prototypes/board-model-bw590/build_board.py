"""Build a photo-referenced PCB mesh in glTF 2.0, with dimensions in metres."""

from collections import defaultdict
import json
import math
from pathlib import Path
import struct
import sys


OUT = Path(__file__).resolve().parent
THICKNESS = 0.62  # Estimated millimetres.
MATERIALS = {
    "Solder mask": ("222327", 0.05, 0.82),
    "Laminate edge": ("382f24", 0.04, 0.87),
    "Black mould compound": ("35363a", 0.03, 0.87),
    "Slate mould compound": ("44566b", 0.05, 0.78),
    "Connector polymer": ("262823", 0.04, 0.77),
    "Silver plating": ("b5afb0", 0.67, 0.34),
    "Contact gold": ("bc954b", 0.68, 0.36),
    "Ceramic": ("a88552", 0.07, 0.65),
    "Dark SMD": ("3d3935", 0.04, 0.72),
    "Metal cap": ("aaa7a1", 0.58, 0.41),
}
nodes, meshes, accessors, views = [], [], [], []
binary = bytearray()


def color(hex_rgb):
    def linear(channel):
        return channel / 12.92 if channel <= .04045 else ((channel + .055) / 1.055) ** 2.4
    return [linear(int(hex_rgb[i:i + 2], 16) / 255) for i in (0, 2, 4)] + [1]


def view(data, target):
    binary.extend(bytes(-len(binary) % 4))
    views.append(dict(buffer=0, byteOffset=len(binary), byteLength=len(data), target=target))
    binary.extend(data)
    return len(views) - 1


def accessor(points, target, bounds=False):
    width = len(points[0])
    values = [v for point in points for v in point]
    data_type, packed, shape = (5126, "f", "VEC3") if width == 3 else (5123, "H", "SCALAR")
    definition = dict(bufferView=view(struct.pack(f"<{len(values)}{packed}", *values), target),
                      count=len(points), componentType=data_type, type=shape)
    if bounds:
        definition["min"] = [min(p[i] for p in points) for i in range(width)]
        definition["max"] = [max(p[i] for p in points) for i in range(width)]
    accessors.append(definition)
    return len(accessors) - 1


def outward_normal(points):
    a, b, c = points[:3]
    u = [b[i] - a[i] for i in range(3)]
    v = [c[i] - a[i] for i in range(3)]
    cross = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
    norm = math.sqrt(sum(n * n for n in cross))
    return [n / norm for n in cross]


def add_mesh(name, surfaces, extras, origin=(0, 0, 0)):
    primitives = []
    for material, polygons in surfaces.items():
        positions, normals, indices = [], [], []
        for polygon in polygons:
            local = [tuple((v - origin[i]) / 1000 for i, v in enumerate(p)) for p in polygon]
            normal = outward_normal(local)
            start = len(positions)
            positions.extend(local)
            normals.extend([normal] * len(local))
            indices.extend((start + j,) for i in range(1, len(local) - 1) for j in (0, i, i + 1))
        primitives.append(dict(
            attributes=dict(POSITION=accessor(positions, 34962, True), NORMAL=accessor(normals, 34962)),
            indices=accessor(indices, 34963),
            material=list(MATERIALS).index(material),
        ))
    meshes.append(dict(name=name, primitives=primitives))
    nodes.append(dict(name=name, mesh=len(meshes) - 1, extras=extras,
                      translation=[v / 1000 for v in origin]))
    return len(nodes) - 1


def chamfered_rect(x, y, width, depth, chamfer):
    half_w, half_d = width / 2, depth / 2
    c = min(chamfer, half_w * .6, half_d * .6)
    return [(x + a, y + b) for a, b in [
        (-half_w + c, -half_d), (half_w - c, -half_d),
        (half_w, -half_d + c), (half_w, half_d - c),
        (half_w - c, half_d), (-half_w + c, half_d),
        (-half_w, half_d - c), (-half_w, -half_d + c),
    ]]


def cap_triangles(points):
    remaining = list(range(len(points)))

    def turn(a, b, c):
        return (b[0]-a[0]) * (c[1]-a[1]) - (b[1]-a[1]) * (c[0]-a[0])

    while len(remaining) > 3:
        for offset, current in enumerate(remaining):
            indices = (remaining[offset-1], current, remaining[(offset+1) % len(remaining)])
            a, b, c = (points[i] for i in indices)
            if turn(a, b, c) <= 1e-9:
                continue
            if any(i not in indices and min(turn(a,b,points[i]), turn(b,c,points[i]),
                                              turn(c,a,points[i])) >= -1e-9 for i in remaining):
                continue
            yield [a, b, c]
            remaining.pop(offset)
            break
        else:
            raise ValueError("Could not triangulate PCB outline")
    yield [points[i] for i in remaining]


def extrude(surfaces, outline, bottom, top, material, edge=None, bevel=0):
    area = sum(a[0] * b[1] - a[1] * b[0] for a, b in zip(outline, outline[1:] + outline[:1]))
    if area < 0:
        outline = list(reversed(outline))
    lower = [(x, y, bottom) for x, y in outline]
    upper = [(x, y, top - bevel) for x, y in outline]
    if bevel:
        cx = sum(x for x, _ in outline) / len(outline)
        cy = sum(y for _, y in outline) / len(outline)
        radius = max(math.hypot(x-cx, y-cy) for x, y in outline)
        inset = 1 - min(bevel / radius * 1.5, .25)
        cap = [(cx + (x - cx) * inset, cy + (y - cy) * inset, top) for x, y in outline]
    else:
        cap = upper
    surfaces[material].extend(cap_triangles(cap))
    surfaces[material].extend(tri[::-1] for tri in cap_triangles(lower))
    for i in range(len(outline)):
        j = (i + 1) % len(outline)
        surfaces[edge or material].append([lower[i], lower[j], upper[j], upper[i]])
        if bevel:
            surfaces[material].append([upper[i], upper[j], cap[j], cap[i]])


def photo_position(side, x, y):
    if side == "front":
        return (x - 492) * 26.3 / 970, (180 - y + (x - 492) * .023) * 9.1 / 310
    return (x - 456) * 26.3 / 900, (y - 152 + (x - 456) * .024) * 9.1 / 274


def component(side, name, x, y, w, d, height, kind, marking=None):
    cx, cy = photo_position(side, x, y)
    width, depth = abs(photo_position(side, w, d)[0] - photo_position(side, 0, 0)[0]), d * (
        9.1 / (310 if side == "front" else 274))
    end = THICKNESS / 2
    surfaces = defaultdict(list)

    def part(dx, dy, pw, pd, base, h, material, chamfer=.05, bevel=.03):
        low, high = end + base, end + base + h
        extrude(surfaces, chamfered_rect(cx + dx, cy + dy, pw, pd, chamfer),
                low, high, material, bevel=min(bevel, h * .3))

    if kind in ("connector", "spring"):
        style = "Connector polymer" if kind == "connector" else "Silver plating"
        part(0, 0, width, depth, 0, .14, style)
        long_vertical = depth > width
        pitch_axis, cross_axis = (depth, width) if long_vertical else (width, depth)
        count = 16 if long_vertical else (8 if pitch_axis > 3.8 else 4)

        def strip(p, q, pw, qw, base, h, material):
            if long_vertical:
                part(q, p, qw, pw, base, h, material, .025, .02)
            else:
                part(p, q, pw, qw, base, h, material, .025, .02)

        if kind == "connector":
            strip(0, 0, pitch_axis * .84, cross_axis * .28, .13, height * .49, "Connector polymer")
            for sign in (-1, 1):
                strip(sign * pitch_axis * .445, 0, pitch_axis * .11, cross_axis, .12, height * .74, "Silver plating")
                strip(0, sign * cross_axis * .43, pitch_axis * .85, cross_axis * .12, .13, height * .52, "Connector polymer")
                for i in range(count):
                    position = (i - (count - 1) / 2) * pitch_axis * .74 / count
                    strip(position, sign * cross_axis * .21, pitch_axis * .45 / count,
                          cross_axis * .29, .13, height * .48, "Contact gold")
        else:
            part(width * .06, 0, width * .78, depth * .79, .1, height * .75, "Contact gold")
            part(0, 0, width * .43, depth * .48, .18, height * .78, "Silver plating")
    elif kind in ("ceramic", "dark", "large-passive"):
        material = "Ceramic" if kind == "ceramic" else "Dark SMD"
        part(0, 0, width, depth, 0, height, material)
        vertical = depth > width
        for sign in (-1, 1):
            if vertical:
                part(0, sign * depth * .405, width * 1.04, depth * .23, 0, height * 1.12, "Silver plating")
            else:
                part(sign * width * .405, 0, width * .23, depth * 1.04, 0, height * 1.12, "Silver plating")
    elif kind == "can":
        part(0, 0, width, depth, 0, .12, "Silver plating")
        part(0, 0, width * .83, depth * .82, .1, height, "Metal cap", .13, .06)
    elif kind == "pad":
        points = [(cx + width / 2 * math.cos(i * math.tau / 24),
                   cy + depth / 2 * math.sin(i * math.tau / 24)) for i in range(24)]
        low, high = end, end + height
        extrude(surfaces, points, low, high, "Contact gold")
    elif kind == "land":
        part(0, 0, width, depth, 0, height, "Contact gold")
    else:
        part(0, 0, width, depth, 0, height,
             "Slate mould compound" if kind == "slate" else "Black mould compound", .12, .08)
    if side == "reverse":
        surfaces = {material: [[(x, y, -z) for x, y, z in reversed(face)] for face in faces]
                    for material, faces in surfaces.items()}
    metadata = dict(side=side, category=kind, reference="FCC Photo 4" if side == "front" else "FCC Photo 6",
                    photoCropPx=[x, y], heightEstimated=True)
    if marking:
        metadata["observedMarking"] = marking
    return add_mesh(name, surfaces, metadata, (cx, cy, end if side == "front" else -end))


outline_px = [(13, 106), (24, 56), (63, 20), (100, 8), (225, 8), (248, 17), (292, 13),
              (299, 7), (326, 18), (938, 28), (944, 43), (960, 48), (971, 59), (977, 288),
              (960, 301), (956, 322), (938, 343), (610, 336), (602, 328), (573, 327),
              (564, 334), (344, 329), (333, 319), (311, 326), (94, 322), (56, 314),
              (18, 288), (7, 270), (7, 194), (20, 178), (21, 158), (11, 153)]
board_surfaces = defaultdict(list)
extrude(board_surfaces, [photo_position("front", *p) for p in outline_px],
        -THICKNESS / 2, THICKNESS / 2, "Solder mask", "Laminate edge")
board_index = add_mesh("PCB substrate", board_surfaces,
                       dict(source="FCC Photos 3–6", dimensionsEstimated=True,
                            nominalMillimetres=[26.3, 9.1, THICKNESS]))


# FCC Photo 4, rotated 180 degrees to put the temple flex end at right.
front = [
    ("U25643 package", 391, 123, 128, 137, .80, "slate", "U25643"),
    ("CY8C40 package", 488, 208, 66, 66, .60, "ic", "CY8C40 / 46FNI"),
    ("Rounded-end package", 138, 66, 117, 84, .69, "ic", None),
    ("Inner square package", 583, 103, 73, 71, .63, "ic", None),
    ("Dark auxiliary package near round end", 121, 169, 35, 34, .34, "slate", None),
    ("Flex-end vertical socket", 833, 177, 72, 211, .75, "connector", None),
    ("Centre horizontal socket", 315, 249, 171, 76, .77, "connector", None),
    ("Rounded-end small socket", 116, 243, 88, 54, .65, "connector", None),
    ("Rectangular metal-capped part", 202, 156, 88, 58, .67, "can", None),
    ("Flex-side spring contact", 676, 68, 43, 66, .65, "spring", None),
    ("Flex-side passive upper", 685, 137, 72, 43, .67, "large-passive", None),
    ("Flex-side passive middle", 684, 198, 72, 46, .67, "large-passive", None),
    ("Flex-side passive lower", 683, 260, 76, 46, .67, "large-passive", None),
    ("Centre upright passive", 291, 155, 44, 70, .65, "large-passive", None),
    ("Flex-end land upper", 909, 56, 66, 35, .04, "land", None),
    ("Flex-end land lower", 922, 305, 59, 34, .04, "land", None),
]
front_nodes = [component("front", *item) for item in front]
front_pads = [(43,148,36),(34,205,37),(35,249,24),
              (85,298,36),(132,300,36),(177,301,39),(222,306,24),(264,307,24),
              (305,308,24),(345,309,24),(386,311,24),(428,313,24),(469,312,24),(511,313,24),
              (509,40,23),(549,41,23),(588,43,23),(628,44,23),
              (955,110,23),(955,143,23),(957,178,23),(958,212,24),(959,249,24)]
for i, (x, y, size) in enumerate(front_pads, 1):
    front_nodes.append(component("front", f"Front gold pad {i:02}", x, y, size, size, .038, "pad"))

front_smd = [
    (32,112,10,19),(63,99,11,21),(64,81,11,19),(82,122,13,23),
    (84,148,14,20),(83,180,17,14),(119,126,21,16),(124,147,21,16),
    (221,114,21,16),(218,41,14,18),(217,60,14,18),(217,83,15,16),
    (264,62,13,18),(291,63,31,22),(265,94,12,18),(283,94,11,19),(305,93,15,19),
    (197,201,24,15),(201,229,29,17),(204,250,27,16),(201,269,25,14),
    (334,40,13,24),(356,40,13,22),(381,39,15,24),(405,40,12,21),
    (476,75,15,20),(495,73,15,19),(518,74,15,20),(475,101,16,20),
    (502,101,21,17),(517,126,24,17),(472,151,15,22),(496,151,13,20),
    (513,156,15,19),(537,145,13,21),(555,143,13,20),(580,144,14,20),
    (604,146,14,23),(539,168,12,19),(560,172,13,28),(582,172,13,27),
    (605,173,13,21),(630,173,12,20),
    (434,272,13,23),(457,270,15,29),(480,269,15,26),(504,268,15,26),
    (549,212,33,13),(549,233,32,15),(549,256,32,14),(587,207,13,24),
    (586,253,12,35),(621,211,31,14),(621,235,30,14),(620,257,29,14),
    (547,304,12,29),(572,307,12,24),(615,294,38,24),(661,300,21,16),
    (712,306,15,16),(733,308,14,16),(756,308,17,17),(797,311,23,19),
    (848,310,16,19),(865,308,15,16),
    (724,67,21,30),(749,90,20,17),(768,61,14,23),(809,51,24,12),
    (834,53,23,15),(857,54,15,16),(903,88,29,14),
    (761,114,30,16),(761,142,28,17),(762,165,27,17),(761,192,27,17),
    (761,215,29,16),(761,241,30,16),(756,266,26,17),
    (908,110,30,14),(907,137,30,14),(906,164,30,14),(907,190,29,14),
    (907,216,29,14),(909,241,31,15),(911,271,44,20),
]
for i, (x, y, w, d) in enumerate(front_smd, 1):
    front_nodes.append(component("front", f"Front surface-mount part {i:02}", x, y, w, d,
                                 .25 if max(w, d) > 21 else .17,
                                 "ceramic" if i in {6,9,19,24,31,42,43,44,57,59,63,65,67,70,76} else "dark"))

# FCC Photo 6, viewed with the rounded end on the left. Reverse projection flips Y.
reverse = [
    ("AP510BFA package", 302, 127, 192, 168, .80, "ic", "AP510BFA"),
    ("GX8002D marking package", 822, 169, 96, 98, .66, "ic", "GX8002D"),
    ("Reverse upper middle package", 539, 101, 73, 86, .61, "ic", None),
    ("Reverse compact upper package", 668, 81, 45, 60, .51, "ic", None),
    ("Reverse compact lower package", 567, 188, 48, 38, .49, "ic", None),
    ("Reverse rounded-end small package", 77, 80, 27, 40, .43, "ic", None),
    ("Rounded-end upper metal can", 133, 63, 47, 67, .65, "can", None),
    ("Lower metal can", 301, 248, 65, 46, .67, "can", None),
    ("Rounded-end upper spring", 49, 189, 65, 43, .64, "spring", None),
    ("Rounded-end lower spring", 47, 234, 65, 43, .64, "spring", None),
    ("Reverse land 1", 103, 291, 31, 18, .035, "land", None),
    ("Reverse land 2", 158, 287, 34, 19, .035, "land", None),
    ("Reverse land 3", 235, 278, 63, 27, .035, "land", None),
]
reverse_nodes = [component("reverse", *item) for item in reverse]
reverse_capacitors = [
    (594,29,36,25),(594,68,25,37),(626,64,24,38),(697,29,27,33),
    (726,29,26,32),(774,71,37,26),(799,28,30,37),(825,27,26,35),
    (859,97,33,27),(532,151,36,25),(586,151,37,26),(642,142,37,23),
    (643,169,35,24),(487,176,24,41),(550,242,25,39),
]
for i, (x, y, w, d) in enumerate(reverse_capacitors, 1):
    reverse_nodes.append(component("reverse", f"Reverse ceramic package {i:02}", x, y, w, d,
                                   .44, "ceramic"))

reverse_rows = [
    (37,(69,88)),(56,(178,197,217,239,258,276,299,324,335,355,377,397,429,452,479,508,530,556,650,674,748,770)),
    (89,(78,112,145,182,409,440,479,695,732,762,792,830)),
    (110,(29,45,76,111,143,183,409,442,479,652,702,738,775,799,869)),
    (132,(36,78,112,145,182,411,445,480,662,690,725,765,790,824)),
    (154,(79,113,146,183,410,444,481,685,722,752,767)),
    (178,(112,148,184,412,446,512,539,664,694,730,768)),
    (200,(114,147,185,408,446,503,535,612,646,676,715,755)),
    (222,(112,186,230,362,387,408,448,471,514,585,613,645,682,712,748,785)),
    (242,(85,111,143,168,187,358,388,443,471,505,577,612,640,688,720,751)),
    (264,(76,107,129,164,186,362,389,415,442,477,504,577,611,717,749,793,819,845,875)),
]
# Adjust the dense rows to the photographed board's small clockwise skew.
for row, (y, xs) in enumerate(reverse_rows, 1):
    for col, x in enumerate(xs, 1):
        observed_y = y - (x - 456) * .019
        if x > 150 and y < 70:
            observed_y -= 17
        if any(abs(x - cx) < w / 2 + 1 and abs(observed_y - cy) < d / 2 + 1
               for _, cx, cy, w, d, *_ in reverse) or any(
                   abs(x - cx) < w / 2 + 3 and abs(observed_y - cy) < d / 2 + 2
                   for cx, cy, w, d in reverse_capacitors):
            continue
        ceramic = (row * 3 + col) % 4 == 0
        reverse_nodes.append(component("reverse", f"Reverse surface-mount part {row:02}.{col:02}",
                                       x, observed_y, 11 if ceramic else 13,
                                       16 if ceramic else 10, .21 if ceramic else .14,
                                       "ceramic" if ceramic else "dark"))

nodes.append(dict(name="Front components", children=front_nodes))
front_index = len(nodes) - 1
nodes.append(dict(name="Reverse components", children=reverse_nodes))
reverse_index = len(nodes) - 1
assembled = "--assembled" in sys.argv[1:]
scene_roots = [board_index, front_index, reverse_index]
if assembled:
    MATERIALS.update({
        "Black frame polymer": ("242427", .04, .59),
        "Black flex ribbon": ("383538", .16, .58),
        "Screw head metal": ("3a393b", .63, .46),
        "Screw recess": ("161619", .23, .67),
        "Cover metal": ("898482", .62, .53),
        "Dark foil": ("646163", .49, .64),
    })
    accessory_nodes = []

    def overlay(name, shapes, note, origin):
        faces = defaultdict(list)
        for outline, bottom, top, material, bevel in shapes:
            extrude(faces, outline, bottom, top, material, bevel=bevel)
        accessory_nodes.append(add_mesh(name, faces, dict(
            side="front", reference="User photos 1 and 2", heightEstimated=True,
            interpretation=note), origin))

    def rounded_end(x, y, length, depth, left_radius, right_radius):
        outline = []
        for sx, sy, radius, start in [(1, 1, right_radius, 0), (-1, 1, left_radius, 90),
                                      (-1, -1, left_radius, 180), (1, -1, right_radius, 270)]:
            cx = x + sx * (length / 2 - radius)
            cy = y + sy * (depth / 2 - radius)
            for i in range(11):
                angle = math.radians(start + i * 9)
                outline.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
        return outline

    # Ring surfaces only. The references show the lip, but the unseen rear carrier is unspecified.
    ring_outer = rounded_end(.4, .03, 30.5, 10.8, 3.4, 3.5)
    ring_inner = rounded_end(.38, .03, 29.4, 9.84, 3.0, 3.0)
    faces = defaultdict(list)
    for i in range(len(ring_outer)):
        j = (i + 1) % len(ring_outer)
        a, b = ring_outer[i], ring_outer[j]
        c, d = ring_inner[i], ring_inner[j]
        bottom, top = -.74, 1.22
        faces["Black frame polymer"].extend([
            [(*a, bottom), (*b, bottom), (*b, top), (*a, top)],
            [(*c, top), (*d, top), (*d, bottom), (*c, bottom)],
            [(*a, top), (*b, top), (*d, top), (*c, top)],
            [(*a, bottom), (*c, bottom), (*d, bottom), (*b, bottom)],
        ])
    accessory_nodes.append(add_mesh("Visible temple perimeter rim", faces, dict(
        side="front", reference="User photos 1 and 2", heightEstimated=True,
        interpretation="Approximate lip profile and thickness; unseen rear carrier omitted")))

    def circle(x, y, radius):
        return [(x + radius * math.cos(i * math.tau / 24),
                 y + radius * math.sin(i * math.tau / 24)) for i in range(24)]

    for index, y in enumerate((3.23, -3.12), 1):
        x = 13.18
        overlay(f"Visible screw head {index}", [
            (circle(x, y, .97), .53, 1.26, "Screw head metal", .12),
            (chamfered_rect(x, y, .86, .20, .05), 1.245, 1.262, "Screw recess", 0),
            (chamfered_rect(x, y, .20, .86, .05), 1.245, 1.263, "Screw recess", 0),
        ], "Visible head; recess profile and hidden shaft are unverified", (x, y, 1.12))

    x, y = 8.32, -.18
    overlay("Large metal-looking cover", [
        (rounded_end(x, y, 4.19, 7.51, .46, .46), 1.15, 1.63, "Cover metal", .13),
    ], "Contoured to the visible cover outline; attachment and material unknown", (x, y, 1.40))

    x, y = 12.14, -.07
    overlay("Dark flex bridge", [
        (chamfered_rect(x, y, 3.6, 4.35, .55), .79, 1.32, "Black flex ribbon", .10),
        (chamfered_rect(13.68, y, .9, 4.42, .16), 1.15, 1.55, "Black frame polymer", .06),
    ], "Visible black bridge between the cover and projecting flex segment", (x, y, 1.20))

    x, y = 18.12, -.07
    overlay("Projecting flex segment", [
        (chamfered_rect(x, y, 8.13, 4.27, .09), .87, 1.20, "Black flex ribbon", .03),
        (chamfered_rect(14.66, y, .36, 4.28, .07), 1.18, 1.41, "Screw head metal", .04),
        (chamfered_rect(x+.12, y-2.01, 7.74, .13, .04), 1.19, 1.25, "Black frame polymer", .02),
        (chamfered_rect(x+.12, y+2.01, 7.74, .13, .04), 1.19, 1.25, "Black frame polymer", .02),
    ], "Approximate length of exposed segment, cropped by the user photographs", (x, y, 1.1))

    for name, x, y, w, d in [
        ("Central connector foil", -4.18, -2.72, 4.56, 2.42),
        ("Round-end connector foil", -9.89, -2.79, 3.30, 2.32),
    ]:
        overlay(name, [(rounded_end(x, y, w, d, .40, .38), .94, 1.47, "Dark foil", .09)],
                "Photographed opaque overlay; composition and exact attachment unconfirmed", (x, y, 1.25))

    scene_roots.append(len(nodes))
    nodes.append(dict(name="User photo assembly accessories", children=accessory_nodes))

binary.extend(bytes(-len(binary) % 4))
gltf = dict(
    asset=dict(version="2.0", generator="Blackwall photo-referenced board model"),
    scenes=[dict(name="G2 temple assembly" if assembled else "G2 temple PCB", nodes=scene_roots)],
    scene=0, nodes=nodes, meshes=meshes, accessors=accessors, bufferViews=views,
    buffers=[dict(byteLength=len(binary))],
    materials=[dict(name=name, pbrMetallicRoughness=dict(
        baseColorFactor=color(rgb), metallicFactor=metal, roughnessFactor=rough))
        for name, (rgb, metal, rough) in MATERIALS.items()],
)
doc = json.dumps(gltf, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
doc += b" " * (-len(doc) % 4)
filename = "g2-temple-assembly.glb" if assembled else "g2-temple-board.glb"
with (OUT / filename).open("wb") as output:
    output.write(struct.pack("<4sII", b"glTF", 2, 28 + len(doc) + len(binary)))
    output.write(struct.pack("<I4s", len(doc), b"JSON"))
    output.write(doc)
    output.write(struct.pack("<I4s", len(binary), b"BIN\0"))
    output.write(binary)
print(f"{len(front_nodes)} front parts, {len(reverse_nodes)} reverse parts and 1 substrate")
if assembled:
    print(f"{len(accessory_nodes)} accessory objects")
