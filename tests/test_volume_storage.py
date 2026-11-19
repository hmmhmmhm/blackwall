import io
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
             patch.object(storage, 'docker', side_effect=[b'volume', other_owner]) as docker:
            with self.assertRaisesRegex(RuntimeError, 'raced'):
                storage.import_volume('shared', {'profile.json': b'{}'})
            self.assertEqual(docker.call_count, 2)
            self.assertEqual(docker.call_args_list[1].args[:2], ('volume', 'inspect'))

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
