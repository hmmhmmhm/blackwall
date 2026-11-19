"""Preview verified saved Renode DMA bytes using the original callback's tested pixel layout."""
import argparse
import hashlib
import json
from pathlib import Path
from native_replay import MAIN_LAYOUT
from prepare_vendor_startup_candidate import sha


def matched_payload(frame, snapshot):
    required = dict(source=0x20094400, length=153602, configuration=0x40161,
                    xip_configuration=0x45ec, pio_mixed=5, instruction_configuration=0x630062)
    if any(frame.get(key) != value for key, value in required.items()):
        raise ValueError('Unknown DMA pixel layout/configuration')
    offset = frame['source'] - 0x20000000
    if offset < 0 or offset + frame['length'] > len(snapshot):
        raise ValueError('DMA source outside collected snapshot range')
    payload = snapshot[offset:offset + frame['length']]
    if hashlib.sha256(payload).hexdigest() != frame.get('sha256'):
        raise ValueError('Snapshot changed since DMA consumed this frame; a retained payload capture is required')
    return payload


def export(s, capture, audit, output, frame_index):
    if output.exists() or any(not p.resolve().is_relative_to(s.resolve()) for p in (capture, audit, output)) or frame_index < 0:
        raise ValueError('Fresh private output and private captured evidence required')
    contract = s / 'mspi0-rx-identity-source-02/report.json'
    manifest = json.loads((s / 'mspi0-rx-identity-verification-01/manifest.json').read_text())
    if not manifest['passed'] or sha(contract) != manifest['files'][str(contract.relative_to(s))]:
        raise ValueError('Changed original pixel layout proof')
    proof = json.loads(audit.read_text())
    if not proof.get('passed') or proof.get('hardware_accessed'):
        raise ValueError('Saved semantic audit must pass')
    pins = proof['capture_hashes']
    for name in ['main.bin', 'report.json', 'plan.json', 'exports/sram-full.bin']:
        if name not in pins:
            raise ValueError('Missing captured evidence pin ' + name)
    for name, expected in pins.items():
        if sha(capture / name) != expected:
            raise ValueError('Changed captured evidence ' + name)
    report, plan = (json.loads((capture / n).read_text()) for n in ['report.json', 'plan.json'])
    if not report['execution_passed'] or report['hardware_accessed'] or sha(capture / 'main.bin') != MAIN_LAYOUT[plan['cases'][report['case']]][3]:
        raise ValueError('Not a verified original main execution')
    frames = report['diagnostics']['mspi0_dma_frames']
    if frame_index >= len(frames):
        raise ValueError('No such completed DMA frame')
    frame = frames[frame_index]
    payload = matched_payload(frame, (capture / 'exports/sram-full.bin').read_bytes())
    # Import only for actual PNG creation; validation and refusal tests use stdlib.
    from inspect_mspi0_rx_identity import png
    output.mkdir(mode=0o700)
    (output / 'frame.bin').write_bytes(payload)
    png(output / 'frame.png', payload)
    result = dict(passed=True, capture=str(capture.relative_to(s)), case=report['case'], frame_index=frame_index,
                  capture_report_sha256=sha(capture / 'report.json'), saved_audit_sha256=sha(audit),
                  pixel_contract_sha256=sha(contract), frame=frame, png_sha256=sha(output / 'frame.png'),
                  snapshot_equals_consumed_payload=True, pixel_bytes=153600, trailing_bytes=payload[-2:].hex(),
                  nonzero_pixel_bytes=sum(value != 0 for value in payload[:153600]),
                  scope='Post-stop SRAM proved equal to consumed DMA; grayscale CPU-plane preview, not optical panel or UI validation',
                  hardware_accessed=False, boot_verified=False, display_verified=False)
    (output / 'report.json').write_text(json.dumps(result, indent=2) + '\n')
    (output / 'exporter.py').write_bytes(Path(__file__).read_bytes())
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('capture', type=Path)
    p.add_argument('audit', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--frame', type=int, default=0)
    a = p.parse_args()
    result = export(a.simulator, a.capture, a.audit, a.output, a.frame)
    print(json.dumps({k: result[k] for k in ['passed', 'frame_index', 'nonzero_pixel_bytes', 'snapshot_equals_consumed_payload']}))


if __name__ == '__main__':
    main()
