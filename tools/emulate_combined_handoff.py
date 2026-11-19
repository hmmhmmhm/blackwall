"""Execute the 2.4 patched handoff into pinned main vectors; stop before reset code."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess

from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE, UcError
from unicorn.arm_const import UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_SP
from blackwall_package import validate_main
from emulate_boot_data_init import initialize_machine

BOOT_SHA = '5ac1b02d337b57e0d25886a06296df2d5932af1f31168c416e64b50c5417a91d'
MAINS = {
    'main-cfw.bin': '84bb56c16774e75158adb14b1a5429a24ee005a76b22df5b5f498998b82fb01a',
    'main-stock.bin': '320aa240affe49c2e2a0b65c284b20a05ad64423fe6a275c34b22d99c58310db',
}
APP, SLOT, VTOR = 0x438000, 0x2007cff0, 0xe000ed08


def execute(boot, main, hook, record):
    cpu, _ = initialize_machine(boot, '2.4.0.24')
    cpu.mem_map(0x440000, 0x3c0000)
    cpu.mem_write(APP, main)
    cpu.mem_map(0xe000e000, 0x1000)
    cpu.mem_write(SLOT, struct.pack('<III', *record))
    stack, reset = struct.unpack_from('<II', main)
    visited, mmio = [], []

    def instruction(uc, address, size, _):
        visited.append(address)
        if address == reset & ~1:
            uc.emu_stop()

    def write(uc, access, address, size, value, _):
        if address >= 0xe000e000:
            mmio.append((address, size, value))

    cpu.hook_add(UC_HOOK_CODE, instruction)
    cpu.hook_add(UC_HOOK_MEM_WRITE, write)
    cpu.reg_write(UC_ARM_REG_R0, APP)
    cpu.emu_start(hook | 1, 0, count=1000, timeout=1000000)
    if cpu.reg_read(UC_ARM_REG_PC) != reset & ~1:
        raise ValueError('Did not reach the main reset entry')
    if cpu.reg_read(UC_ARM_REG_SP) != stack:
        raise ValueError('Main initial stack pointer not loaded')
    if list(cpu.mem_read(SLOT, 12)) != list(struct.pack('<III', 0, 0, 0xffffffff)):
        raise ValueError('One-shot selection not cleared')
    if mmio != [(VTOR, 4, APP)] or struct.unpack('<I', cpu.mem_read(VTOR, 4))[0] != APP:
        raise ValueError('Unexpected system register writes or vector table base')
    if 0x434b2c not in visited or 0x42dfe8 not in visited:
        raise ValueError('Expected patched handoff and stock leaf not executed')
    return {'hook': hex(hook), 'record': [hex(n) for n in record],
            'reset_entry_reached': hex(reset & ~1), 'initial_sp': hex(stack),
            'vtor': hex(APP), 'selection_cleared': True,
            'instruction_boundaries': len(visited), 'main_reset_code_executed': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('components', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--virtual-install', action='store_true', help='Install through the virtual web OTA transport before checking stored ARM bytes')
    args = parser.parse_args()
    boot = (args.candidate / 'source/build/bootloader.bin').read_bytes()
    if hashlib.sha256(boot).hexdigest() != BOOT_SHA:
        raise ValueError('Unknown boot candidate')
    records = [(0, 0, 0), (0x544f4231, APP, (~APP) & 0xffffffff),
               (0x544f4231, APP, 0), (0x544f4231, 0x800000, 0xff7fffff)]
    if args.virtual_install:
        verify_virtual_install(args, boot, records)
        return
    results = {}
    rejected_controls = []
    for name, digest in MAINS.items():
        component = (args.components / name).read_bytes()
        if hashlib.sha256(component).hexdigest() != digest:
            raise ValueError('Unknown main component')
        validate_main(component[128:])
        raw = component[160:]
        results[name] = [execute(boot, raw, hook, record)
                         for hook in (0x42e3e4, 0x42e450) for record in records]
        for hook in (0x42e3e4, 0x42e450):
            damaged = bytearray(boot)
            offset = hook - 0x410000
            damaged[offset:offset+4] = b'\x00\xbf\x00\xbf'
            try:
                execute(bytes(damaged), raw, hook, records[0])
            except (ValueError, UcError):
                rejected_controls.append({'main': name, 'removed_hook': hex(hook)})
            else:
                raise ValueError('Removed handoff hook unexpectedly passed')
    report = {'scope': 'patched handoff through stock leaf to main reset boundary',
              'boot_sha256': BOOT_SHA, 'main_component_sha256': MAINS,
              'stubbed_functions': [], 'results': results,
              'removed_hook_controls_rejected': rejected_controls,
              'hardware_validated': False, 'installable': False,
              'limitations': ['Starts at handoff hook with R0 set to main base',
                              'Does not execute full boot manager, scheduler or main startup',
                              'System register write recorded in mapped emulator memory only',
                              'Does not verify peripherals, codec or Faceclaw runtime']}
    with args.output.open('x') as output:
        json.dump(report, output, indent=2)
        output.write('\n')
    print('16 handoff cases passed; 4 removed-hook controls rejected; main startup and hardware unverified')


def verify_virtual_install(args, boot, records):
    root=Path(__file__).resolve().parents[1]
    destination=args.output.parent/(args.output.stem+'-virtual-images')
    if args.output.exists():raise ValueError('Output already exists')
    resolved=destination.resolve()
    if resolved.is_relative_to(root):raise ValueError('Virtual firmware output must stay outside Git')
    result=subprocess.run(['node',str(root/'tools/simulate_web_install.mjs'),str(args.candidate),str(args.components),str(destination)],check=True,capture_output=True,text=True)
    manifest=json.loads((destination/'report.json').read_text())
    if manifest['hardwareAccessed'] or manifest['fullStockRestored'] or not manifest['bootUnchanged'] or not manifest['otherTempleUnchanged']:raise ValueError('Unexpected virtual safety scope')
    images={}
    for item in manifest['snapshots']:
        path=destination/item['file']
        if path.resolve().parent!=destination.resolve():raise ValueError('Snapshot path escapes output')
        data=path.read_bytes()
        if len(data)!=0x7f8000-0x410000 or hashlib.sha256(data).hexdigest()!=item['sha256']:raise ValueError('Virtual MRAM snapshot changed')
        if item['name'] in images:raise ValueError('Duplicate snapshot')
        images[item['name']]=data
    if set(images)!={'cfw','restored-stock','interrupted-stock','interrupted-boot'}:raise ValueError('Missing virtual scenario')
    handoffs={};rejected=[]
    for name,component_name in [('cfw','main-cfw.bin'),('restored-stock','main-stock.bin')]:
        component=(args.components/component_name).read_bytes()
        if hashlib.sha256(component).hexdigest()!=MAINS[component_name]:raise ValueError('Unknown main component')
        validate_main(component[128:]);raw=component[160:];image=images[name]
        stored_boot=image[:len(boot)];stored_main=image[APP-0x410000:APP-0x410000+len(raw)]
        if stored_boot!=boot or stored_main!=raw:raise ValueError('Virtual installed bytes differ from pinned boot/main')
        handoffs[name]=[execute(stored_boot,stored_main,hook,record) for hook in (0x42e3e4,0x42e450) for record in records]
        if name=='restored-stock':
            damaged=images['interrupted-stock'][APP-0x410000:APP-0x410000+len(raw)]
            if damaged==raw:raise ValueError('Interrupted main unexpectedly intact')
            rejected.append(dict(scenario='interrupted-stock',reason='full pinned main bytes differ; not executed',sha256=hashlib.sha256(damaged).hexdigest()))
    if images['interrupted-boot'][:len(boot)]==boot:raise ValueError('Interrupted boot unexpectedly intact')
    rejected.append(dict(scenario='interrupted-boot',reason='full pinned boot bytes differ; not executed'))
    sources={}
    for name in ['tools/simulate_web_install.mjs','web/virtual-ota-storage.mjs','web/component-ota-session.mjs','web/ota-packets.mjs','web/artifact-catalog.mjs',
                 'tools/emulate_combined_handoff.py','tools/emulate_boot_data_init.py','tools/emulate_mram_binding.py','tools/blackwall_package.py']:
        target=args.output.parent/'sources'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((root/name).read_bytes())
        sources[name]=hashlib.sha256(target.read_bytes()).hexdigest()
    report=dict(passed=True,scope='virtual web OTA packets -> modeled MRAM -> pinned original ARM handoff; not full reset or normal boot',
                virtual_storage=manifest,virtual_report_sha256=hashlib.sha256((destination/'report.json').read_bytes()).hexdigest(),
                handoffs=handoffs,rejected_integrity_controls=rejected,source_hashes=sources,driver_stdout=result.stdout.strip(),
                hardware_accessed=False,installable=False,full_stock_restored=False,main_reset_code_executed=False,boot_verified=False,display_verified=False)
    with args.output.open('x') as handle:json.dump(report,handle,indent=2);handle.write('\n')
    print(json.dumps(dict(passed=True,handoffs=sum(map(len,handoffs.values())),rejected_integrity_controls=len(rejected),hardware_accessed=False,full_stock_restored=False)))


if __name__ == '__main__':
    main()
