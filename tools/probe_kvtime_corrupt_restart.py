"""Replay original main reset against explicitly synthetic damaged NOR inputs."""
import argparse
import binascii
import json
from pathlib import Path
import struct

from native_replay import IMAGE
from probe_runtime_kv_restart import build, digest
from run_renode_m55_probe import execute
from run_runtime_connection_m55 import pin_capture


def prepare(simulator, source, output, mode):
    build(source, output, simulator, retained=True)
    path = output/'retained-kv-nv.bin'
    original = path.read_bytes()
    value = bytearray(original)
    profile = json.loads((source/'connection-profile.json').read_text())
    record = struct.pack('<IIbB', 3, profile['service']['timestamp'], profile['service']['zone'], 0)
    record += struct.pack('<H', binascii.crc_hqx(record, 0xffff))
    index = original.find(record)
    if index < 30 or original.find(record, index+1) != -1 or original[index-6:index] != b'kvTime':
        raise ValueError('Ambiguous source record')
    header = index-30
    if original[header+4:header+8] != b'KV00':
        raise ValueError('Unknown FlashDB framing')
    expected_crc = binascii.crc32(original[header+16:index+12]) & 0xffffffff
    if struct.unpack_from('<I', original, header+12)[0] != expected_crc:
        raise ValueError('Source FlashDB CRC differs')
    if mode in ('bad-container-crc', 'bad-record-crc'):
        value[index+4] ^= 1
    elif mode in ('future-record-type','future-record-version'):
        value[index] = 4
        struct.pack_into('<H', value, index+10, binascii.crc_hqx(value[index:index+10], 0xffff))
    else:
        raise ValueError('Unknown damage fixture')
    if mode != 'bad-container-crc':
        struct.pack_into('<I', value, header+12, binascii.crc32(value[header+16:index+12]) & 0xffffffff)
    path.write_bytes(value)
    meta = json.loads((output/'restart-source.json').read_text())
    meta['retained_inputs'][path.name] = digest(path)
    meta['synthetic_damage_fixture'] = dict(mode=mode, base_sha256=digest(source/'exports/nor-after-kv-nv.bin'),
        input_sha256=digest(path), record_offset=index, changed_offsets=[i for i,(x,y) in enumerate(zip(original,value)) if x!=y],
        physical_power_cut_simulated=False, previous_sram_imported=False)
    (output/'restart-source.json').write_text(json.dumps(meta,indent=2)+'\n')
    inputs=json.loads((output/'connection-inputs.json').read_text())
    for name in ('retained-kv-nv.bin','restart-source.json'):
        inputs[name]=digest(output/name)
    (output/'connection-inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator',type=Path);p.add_argument('source',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--mode',required=True,choices=('bad-container-crc','bad-record-crc','future-record-type','future-record-version'))
    a=p.parse_args();prepare(a.simulator,a.source,a.output,a.mode)
    execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128',
             '--cap-drop','ALL','--security-opt','no-new-privileges',
             '--mount',f'type=bind,source={a.output},target=/work,readonly',
             '--mount',f'type=bind,source={a.output}/exports,target=/work-output',IMAGE,
             '--disable-gui','--console','-p','-e','quit','/work/probe.resc'],a.output,'renode',timeout=180)
    pin_capture(a.output)
    result=json.loads((a.output/'exports/restart.json').read_text())
    print(json.dumps(dict(mode=a.mode,record=bytes(result['record']).hex(),pc=hex(result['pc']),
                         boot_reached_hold=result['held'],cfsr=result['cfsr'],hfsr=result['hfsr'])))
    # This command reports a preserved boot failure; it does not certify recovery.
    if not result['held']:
        raise SystemExit(1)


if __name__=='__main__':
    main()
