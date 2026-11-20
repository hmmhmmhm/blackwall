"""Run the reviewed Faceclaw 38 main-reset profile on the virtual board."""
import hashlib
import html
import json
from pathlib import Path
import struct
import zlib

from run_renode_m55_probe import execute

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / 'models/faceclaw38'
IMAGE = 'sha256:e840c2b9a83dbf9be060047839aaaf6d434e7d4c52635191319afc14f4217649'
MAIN_SIZE = 3829832
MAIN_SHA256 = '4118af85ebb8e634493a61a3ce4a62ae37451e17cea6d0b8b08465f29538dd8f'
COMPONENTS = {
    'activation.cs': '3dea34f8c0be5bcc9e3b5ea548a1be5a80d74dc6942f92bad8c06c9f3e6140f5',
    'board.repl': 'a49cff74fa410454ce274bd8d05f5b392f26128a1541fce501fe35015db7207c',
    'probe.resc': 'ba1f50bac7f8f4db9897db79df22184b1588b0bf8ea43986595c0c8c53817feb',
    'run.py': 'd852a1390bf6d2e2f1b967ae88654a6d540a70adf9b02053f5529ea41e595908',
    'strict.cs': '45f01e572d6076b1d14b982e44937e7bde45b35fc981de4f7208f23dc7b67598',
    'touch-profile.json': '5b90c0397ebdaf8dbbae1730260c645a00065c7cd690bcd3a28f6a623ae64fcf',
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def validate_main(path):
    data = Path(path).read_bytes()
    if len(data) != MAIN_SIZE or digest(data) != MAIN_SHA256:
        raise ValueError('Expected the pinned Faceclaw 38 main image; other firmware is not supported by this profile')
    if struct.unpack_from('<II', data) != (0x2007fb00, 0x601a3f):
        raise ValueError('Faceclaw 38 main vectors do not match the reviewed profile')
    return data


def valid_result(boot, touch, frame):
    return (len(frame) == 576 * 288 and bool(frame) and max(frame) <= 15
            and boot.get('frame') is True and boot.get('nonzero') == sum(v != 0 for v in frame)
            and boot.get('nonzero', 0) > 0 and boot.get('instructions', 0) > 0
            and boot.get('gpu_rejections') == 0 and boot.get('gpu_fault') == ''
            and all(touch.get(k) == 0 for k in ('cfsr', 'hfsr', 'memory_violations'))
            and bool(touch.get('guards')) and all(g.get('accesses') == 0 for g in touch['guards']))


def frame_png(frame):
    if len(frame) != 576 * 288 or max(frame) > 15:
        raise ValueError('Invalid 576 x 288 grayscale frame')
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    raw = b''.join(b'\x00' + bytes(value * 17 for value in frame[y:y + 576]) for y in range(0, len(frame), 576))
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 576, 288, 8, 0, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')


def run(main_image, output):
    main = validate_main(main_image)
    output = Path(output).expanduser().resolve()
    if output.exists() or output.is_relative_to(ROOT):
        raise ValueError('Output must be a new directory outside the repository')
    components = {}
    for name, expected in COMPONENTS.items():
        data = (MODEL / name).read_bytes()
        if digest(data) != expected:
            raise ValueError('Faceclaw model hash mismatch: ' + name)
        components[name] = data
    output.mkdir(mode=0o700, parents=True)
    (output / 'exports').mkdir(mode=0o700)
    for name, data in components.items():
        (output / name).write_bytes(data)
    (output / 'main.bin').write_bytes(main)
    (output / 'sram-fill.bin').write_bytes(b'\xa5' * 3670016)
    (output / 'itcm-fill.bin').write_bytes(b'\xa5' * 262144)
    command = ['docker', 'run', '--rm', '--network', 'none', '--memory', '768m', '--cpus', '1', '--pids-limit', '128', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--mount', f'type=bind,source={output},target=/work,readonly', '--mount', f'type=bind,source={output / "exports"},target=/work-output', IMAGE, '--disable-gui', '--console', '-p', '-e', 'quit', '/work/probe.resc']
    execute(command, output, 'renode', timeout=420, stream=True)
    exports = output / 'exports'
    boot = json.loads((exports / 'family-boot.json').read_text())
    touch = json.loads((exports / 'touch.json').read_text())
    frame = (exports / 'family-screen.bin').read_bytes()
    if not valid_result(boot, touch, frame):
        raise ValueError('Faceclaw main execution did not meet the frame and fault checks; inspect the output logs')
    if digest((output / 'main.bin').read_bytes()) != MAIN_SHA256:
        raise ValueError('Faceclaw main image changed during execution')
    (output / 'screen.png').write_bytes(frame_png(frame))
    info = html.escape(json.dumps({'main_sha256': MAIN_SHA256, 'instructions': boot['instructions'], 'virtual_ticks': boot['ticks'], 'nonzero_pixels': boot['nonzero'], 'gpu_rejections': boot['gpu_rejections']}, indent=2))
    (output / 'index.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Blackwall Faceclaw 38 main-reset report</title><body style="background:#101113;color:#eee;font:16px system-ui;max-width:960px;margin:40px auto;padding:0 20px"><h1>Faceclaw 38 — main-reset report</h1><p>Reviewed virtual main-reset execution. This does not start at the bootloader or validate physical hardware.</p><img src="screen.png" alt="Captured guest display frame" style="width:100%;max-width:576px;image-rendering:pixelated;background:black"><h2>Observed checks</h2><pre style="overflow:auto">' + info + '</pre><p><a href="renode.log">Execution log</a></p><p>The output directory contains a copy of the firmware; do not share it.</p></body></html>', encoding='utf-8')
    return output / 'index.html'
