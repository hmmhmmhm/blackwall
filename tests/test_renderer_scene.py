import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from renderer_scene import compile_scene


class SceneTests(unittest.TestCase):
    def test_c_text_escaping(self):
        source = compile_scene({'frames': [[{'type': 'text', 'x': 0, 'y': 0, 'text': '"\\ hello', 'color': 15}]]})
        self.assertIn('"\\"\\\\ hello"', source)

    def test_rejects_bounds_and_non_ascii(self):
        for op in [
            {'type': 'rect', 'x': 575, 'y': 0, 'width': 2, 'height': 1, 'color': 15},
            {'type': 'text', 'x': 0, 'y': 0, 'text': '\n', 'color': 15},
            {'type': 'text', 'x': True, 'y': 0, 'text': 'a', 'color': 15},
            {'type': 'execute', 'code': 'anything'},
        ]:
            with self.assertRaises(ValueError):
                compile_scene({'frames': [[op]]})

    def test_scene_and_frame_limits(self):
        for value in [{'frames': []}, {'frames': [[]]*61}, {'frames': [[]], 'code': 'x'}]:
            with self.assertRaises(ValueError):
                compile_scene(value)
