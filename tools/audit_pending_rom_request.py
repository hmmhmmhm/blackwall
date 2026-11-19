"""Audit paused pending-boot ROM requests and the original clear/reset instructions."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_MCLASS

PRIVATE=Path.home()/'Library/Application Support/Blackwall'


def sha(data):return hashlib.sha256(data).hexdigest()
def read(path):return json.loads(path.read_text())


def run(experiment,output):
    experiment,output=Path(experiment).resolve(),Path(output).resolve()
    if not experiment.is_relative_to(PRIVATE) or output.exists() or not output.is_relative_to(PRIVATE):raise ValueError('Private input and fresh output required')
    boot=PRIVATE/'recovery/boot-2-4-analysis/boot-2.4.0.24.bin';data=boot.read_bytes();checks={};rows={}
    checks['original_boot']=sha(data)=='ecb91896234392e2b98ec80b1ac3ebf4aa27726d3cbed10927edf0b44d83d665'
    decoder=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS)
    def decode(address,length):
        return [dict(address=i.address,mnemonic=i.mnemonic,operands=i.op_str,bytes=bytes(i.bytes).hex()) for i in decoder.disasm(data[address-0x410000:address-0x410000+length],address)]
    instructions=decode(0x42e19a,18)
    checks['write_return_discard_then_reset_call']=[(i['mnemonic'],i['operands']) for i in instructions]==[('bl','#0x42e84c'),('movs','r0, r5'),('msr','primask, r0'),('movs','r1, #0'),('movs','r0, #0'),('bl','#0x42e86c')]
    reset=decode(0x42e878,8)
    checks['reset_store']= [(i['mnemonic'],i['operands']) for i in reset]==[('movs','r0, #0xd4'),('ldr','r1, [pc, #0x10]'),('str','r0, [r1]'),('b','#0x42e87e')] and struct.unpack_from('<I',data,0x42e88c-0x410000)[0]==0x40000008
    checks['metadata_and_template_literals']=struct.unpack_from('<III',data,0x42e4d8-0x410000)==(0x7fe000,0x434320,0x12344321) and data[0x434320-0x410000:0x434320-0x410000+16]==b'\xff'*16
    header=PRIVATE/'simulator/upstream/hal-ambiq-61b293a/apollo510.h';header_bytes=header.read_bytes();header_text=header_bytes.decode()
    checks['pinned_public_reset_register']=sha(header_bytes)=='b6ca35dc828ef95825c0a22f06e6ca5ed558a6542dc74310515fdc350051a797' and '__IOM uint32_t SWPOR;' in header_text and '0xD4 generates a software POR reset.' in header_text
    for case,status in [('ready',0xcf),('stuck',0x4f)]:
        folder=experiment/case;manifest=read(folder/'manifest.json');raw=read(folder/'exports/result.json');report=read(folder/'report.json');request=read(folder/'exports/rom-request.json')
        baseline=PRIVATE/f'simulator/boot-validation-pending-rom-{case}-bw556-01'
        checks[case+'_frozen_sources']=all(sha((folder/n).read_bytes())==h for n,h in manifest['components'].items())
        checks[case+'_same_initial_board']=sha((folder/'strict.cs').read_bytes())==sha((baseline/'strict.cs').read_bytes()) and (folder/'board.repl').read_bytes()==(baseline/'board.repl').read_bytes()
        checks[case+'_whole_execution_exact']=raw==read(baseline/'exports/result.json')
        checks[case+'_paused_read_only']=request['observation_after_machine_pause'] and request['hardware_accessed'] is False and request['rom_executed'] is False and request['registers']==raw['registers'] and request['pc']==raw['pc']==0x0200ff20
        checks[case+'_actual_request']=request['seen'] and request['registers'][:4]==[0x12344321,1,0x20022d68,0xff800] and request['registers'][14]==0x42ec11 and request['words']==4 and request['source']==0x20022d68 and request['destination']==0x7fe000 and request['primask']==1
        checks[case+'_source_bytes']=request['source_capture_bounded'] and bytes(request['source_bytes'])==data[0x434320-0x410000:0x434320-0x410000+16]==b'\xff'*16
        checks[case+'_rom_power_status']=request['power_status']==status
        checks[case+'_no_fault_or_guard']=raw['cfsr']==raw['hfsr']==raw['policy']==raw['system_control_violations']==0 and all(g['accesses']==0 for g in raw['guards'])
        checks[case+'_still_unsupported']=report['classification']=='unsupported-rom' and report['main']==report['handoff']==0 and report['images_unchanged'] and report['unsupported_rom_fetch']
        checks[case+'_owner_removed']=read(folder/'native.process.json')['status']=='removed'
        rows[case]=request
    result=dict(passed=all(checks.values()),checks=checks,actual_requests=rows,original_clear_instructions=instructions,original_reset_instructions=reset,original_boot_sha256=sha(data),public_header_sha256=sha(header_bytes),source_supported_write_status_discard=True,source_supported_reset_request=True,reset_executed=False,rom_executed=False,pending_recovery_complete=False,hardware_accessed=False)
    output.mkdir(parents=True,mode=0o700);shutil.copy2(__file__,output/'audit-source.py')
    (output/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=result['passed'],checks=len(checks),failed=[k for k,v in checks.items() if not v])))
    if not result['passed']:raise ValueError('Pending request audit failed')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('experiment',type=Path);p.add_argument('output',type=Path);a=p.parse_args();run(a.experiment,a.output)
