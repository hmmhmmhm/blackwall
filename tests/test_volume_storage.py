import io
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import volume_storage as storage


class VolumeStorageTests(unittest.TestCase):
    def test_stock_profile_publishes_the_pinned_model_components(self):
        profile = json.loads((storage.ROOT / 'docs/data/original-boot-stock24-profile.json').read_text())
        for name in ('strict.cs', 'board.repl', 'input-delay.cs', 'probe.resc'):
            spec = profile['components'][name]
            self.assertEqual(spec['origin'], 'repo')
            self.assertEqual(storage.sha(storage.ROOT / spec['path']), spec['sha256'])

    def test_stock_initial_memory_is_reproducible_without_snapshot_files(self):
        profile = json.loads((storage.ROOT / 'docs/data/original-boot-stock24-profile.json').read_text())
        for name in ('sram', 'itcm'):
            spec = profile['assets'][name]
            data = storage.synthetic_initial_memory(name, spec)
            self.assertEqual(len(data), spec['bytes'])
            self.assertEqual(hashlib.sha256(data).hexdigest(), spec['sha256'])
            self.assertEqual(set(data), {0xa5})

    def test_other_or_modified_memory_profiles_are_not_synthesized(self):
        profile = json.loads((storage.ROOT / 'docs/data/original-boot-stock24-profile.json').read_text())
        self.assertIsNone(storage.synthetic_initial_memory('boot', profile['assets']['boot']))
        spec = dict(profile['assets']['sram'], sha256='0' * 64)
        self.assertIsNone(storage.synthetic_initial_memory('sram', spec))

    def test_setup_input_collection_recreates_only_missing_memory(self):
        profile = json.loads((storage.ROOT / 'docs/data/original-boot-stock24-profile.json').read_text())
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            profile_file = root / 'profile.json'
            profile['components'] = {}
            profile_file.write_text(json.dumps(profile))
            fake_image = root / 'image'
            fake_image.write_bytes(b'image')
            def checked(root_path, spec, override=None):
                if spec in (profile['assets']['sram'], profile['assets']['itcm']):
                    raise FileNotFoundError(spec['path'])
                return fake_image
            with patch.object(storage, 'validate_profile'), patch.object(storage, 'checked_asset', side_effect=checked):
                _, entries = storage.pinned_inputs(root, profile_file)
            for name in ('sram', 'itcm'):
                spec = profile['assets'][name]
                self.assertEqual(hashlib.sha256(entries[spec['path']]).hexdigest(), spec['sha256'])
                self.assertFalse((root / spec['path']).exists())

    def test_corrupt_existing_memory_is_not_silently_replaced(self):
        profile = json.loads((storage.ROOT / 'docs/data/original-boot-stock24-profile.json').read_text())
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            profile_file = root / 'profile.json'
            profile_file.write_text(json.dumps(profile))
            fake_image = root / 'image'
            fake_image.write_bytes(b'image')
            def checked(root_path, spec, override=None):
                if spec == profile['assets']['sram']:
                    raise ValueError('Asset size/hash mismatch')
                return fake_image
            with patch.object(storage, 'validate_profile'), patch.object(storage, 'checked_asset', side_effect=checked):
                with self.assertRaisesRegex(ValueError, 'size/hash mismatch'):
                    storage.pinned_inputs(root, profile_file)

    def test_existing_volume_is_never_overwritten(self):
        with patch.object(storage.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, b'', b'')), \
             patch.object(storage, 'docker') as docker:
            with self.assertRaisesRegex(ValueError, 'already exists'):
                storage.import_volume('existing', {'profile.json': b'{}'})
            docker.assert_not_called()

    def test_volume_creation_race_does_not_modify_other_volume(self):
        missing = subprocess.CompletedProcess([], 1, b'', b'No such volume')
        other_owner = b'[{"Labels":{"io.blackwall.creation-token":"other"}}]'
        with patch.object(storage.subprocess, 'run', return_value=missing), \
             patch.object(storage, 'docker', side_effect=[b'image', b'volume', other_owner]) as docker:
            with self.assertRaisesRegex(RuntimeError, 'raced'):
                storage.import_volume('shared', {'profile.json': b'{}'})
            self.assertEqual(docker.call_count, 3)
            self.assertEqual(docker.call_args_list[2].args[:2], ('volume', 'inspect'))

    def test_missing_image_does_not_create_a_volume_and_explains_pull(self):
        missing = subprocess.CompletedProcess([], 1, b'', b'No such volume')
        with patch.object(storage.subprocess, 'run', return_value=missing), \
             patch.object(storage, 'docker', side_effect=RuntimeError('No such image')) as docker:
            with self.assertRaisesRegex(RuntimeError, 'docker pull'):
                storage.import_volume('fresh', {'profile.json': b'{}'})
            docker.assert_called_once_with('image', 'inspect', storage.IMAGE)

    def test_archive_rejects_traversal_and_symlinks(self):
        for name, symlink in (('../escape', False), ('nested/link', True)):
            raw = io.BytesIO()
            with tarfile.open(fileobj=raw, mode='w') as tar:
                item = tarfile.TarInfo(name)
                if symlink:
                    item.type = tarfile.SYMTYPE
                    item.linkname = '/tmp/elsewhere'
                    tar.addfile(item)
                else:
                    item.size = 1
                    tar.addfile(item, io.BytesIO(b'x'))
            with tempfile.TemporaryDirectory() as folder, patch.object(storage, 'docker', side_effect=[b'[{"Labels":{"io.blackwall.asset-volume":"1"}}]', raw.getvalue()]):
                with self.assertRaisesRegex(ValueError, 'Unsafe volume'):
                    storage.extract_volume('safe-volume', Path(folder))

    def test_missing_volume_is_not_implicitly_created(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(storage, 'docker', side_effect=RuntimeError('No such volume')) as docker:
            with self.assertRaisesRegex(ValueError, 'run blackwall setup'):
                storage.extract_volume('missing-volume', folder)
            docker.assert_called_once_with('volume', 'inspect', 'missing-volume')

    def test_invalid_volume_names_are_rejected(self):
        for name in ('', '../unsafe', 'a/b', '-invalid'):
            with self.assertRaises(ValueError):
                storage.volume_name(name)


if __name__ == '__main__':
    unittest.main()
