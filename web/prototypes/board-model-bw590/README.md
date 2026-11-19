# G2 temple board model

[g2-temple-board.glb](g2-temple-board.glb) is a two-sided 3D model based on photographs. The PCB substrate, 125 front-side parts, and 163 reverse-side parts can be selected independently. The GLB's positive X axis points toward the flex connector, and positive Z points toward the front. In Three.js GLTFLoader, the side groups are named `Front_components` and `Reverse_components`. GLB units are meters. The substrate outline is approximately 26.3 × 9.45 mm, estimated from the scales in FCC Photos 3 and 5; the 0.62 mm thickness and component heights are visual approximations.

## Comparison with input photographs

| Model render | Reference photographs | Placement checked and remaining differences |
| --- | --- | --- |
| [Horizontal front](front.png) | User photo 2, FCC Photo 4 rotated 180°, FCC Photo 5 | Compared the relative positions of the gold area, vertical socket, and three passive parts on the right near the flex; the large central package and horizontal socket below it; and the rounded left end and circular gold pads. The FCC board has exposed connectors. The user's photo shows a black flex and metal covers; those attachments and the case are outside this model's scope. |
| [Vertical front](front-vertical.png) | User photo 1 | Compared the large central package, elongated socket, and lower pads with the flex end oriented upward. The photo's oblique perspective and surface reflections were not reproduced. |
| [Reverse](reverse.png) | FCC Photos 6 and 3 scale | The photo shows the rounded end and two contacts on the left, a large `AP510BFA` package left of center, and a package marked `GX8002D` on the right. This side is not visible in either user-provided photo. |
| [Oblique](oblique.png) | Three-dimensional inspection of front and outline | Shows the substrate and individual parts separated with thickness. Mounting heights hidden in the photos and exact alignment between sides remain unconfirmed. |

The visible front-side layout corresponds between the FCC board and user photos, but the specific unit, left/right orientation, and board revision are unconfirmed. Visible markings on major packages are preserved in GLB node metadata. Small passive component positions, sizes, and colors are approximate; socket pins, solder, package interiors, and traces have not been established accurately enough for electrical design. Chip-location and marking interpretations follow the [chip-location comparison](../../../docs/research/g2-chip-location-and-3d-preview.md). The original photos and photographic textures are not included in this directory or the GLB. [FCC internal photos](https://fccid.io/2BFKR-G2/Internal-Photos/Internal-photos-8787893.pdf)

## Regeneration and validation

- `python3 build_board.py` generates the GLB. `python3 render_board.py` reads that GLB directly using Pillow and NumPy and renders four views.
- Khronos glTF Validator 2.0.0-dev.3.10 reported zero errors and warnings. Three.js GLTFLoader was used to verify the number of independent parts per group, unique component names, front/reverse positions, substrate dimensions, and the absence of photo assets. The GLB contains 38,540 triangles.

## Assembly based on user photos

[g2-temple-assembly.glb](g2-temple-assembly.glb) adds the visible surround, two screw heads, one large metallic-looking cover, the flex connection and protrusion, and two small covers as independent objects on the same PCB. The [horizontal front](assembly-front.png) is oriented to match user photo 2, and the [vertical front](assembly-front-vertical.png) matches user photo 1. Attachment placement is also visible in the [oblique](assembly-oblique.png) and [reverse](assembly-reverse.png) views.

The structure beneath the large cover, the frame's rear, screw bodies, and flex beyond the photographed area are unconfirmed. Heights, cover metallic appearance, screw-slot shape, and visible flex length are approximate. The reverse render uses the FCC-based rear board and an estimated cross-section of the surround visible on the front. The complete assembly outline is approximately 37.04 × 10.80 × 2.74 mm.

Run `python3 build_board.py --assembled` and `python3 render_board.py --assembled` to create the assembly model and four renders. Khronos validation reported zero errors and warnings, and Three.js GLTFLoader loaded eight attachments in separate groups. The PCB nodes, meshes, materials, and buffer bytes were compared and matched between the original PCB and assembly model. The assembly contains 40,328 triangles.
