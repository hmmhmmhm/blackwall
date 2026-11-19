"""Original mask/identity initialization with explicit hypothetical controller replies."""
import argparse,json,struct
from pathlib import Path
from inspect_application_vendor_address import call,sha
from inspect_nema_blocking_wait import cpu,WORK

COMMANDS=['01010c089088000200800020','01012008ffff7f0000000000','01630c080000800000000000','01091000']


def inspect(s,case):
    f=s/'vendor-startup-main-01'/case;ap=s/'vendor-startup-saved-audit-01'/case/'report.json';audit=json.loads(ap.read_text());report=json.loads((f/'report.json').read_text())
    if not audit['passed'] or not report['execution_passed'] or report['hardware_accessed']:raise ValueError('Unverified native source')
    for n,digest in audit['capture_hashes'].items():
        if sha(f/n)!=digest:raise ValueError('Changed native source '+n)
    previous=s/'application-hci-transaction-source-02/report.json';pin=json.loads((s/'application-hci-reset-verification-01/manifest.json').read_text())['retained_source_sha256']
    if sha(previous)!=pin:raise ValueError('Changed original parser/ring source')
    ctx=next(r for r in json.loads(previous.read_text())['cases'] if r['case']==case)
    ring_path=s/'application-hci-source-01/report.json';pin=json.loads((s/'application-hci-idle-verification-01/manifest.json').read_text())['source_report_sha256']
    if sha(ring_path)!=pin:raise ValueError('Changed original ring source')
    ring=next(r for r in json.loads(ring_path.read_text())['cases'] if r['case']==case)['tx_ring']
    startup_path=s/'vendor-startup-source-01/report.json';pin=json.loads((s/'vendor-startup-verification-01/manifest.json').read_text())['source_sha256']
    if sha(startup_path)!=pin:raise ValueError('Changed address/feature contract')
    startup=next(r for r in json.loads(startup_path.read_text())['cases'] if r['case']==case);address=bytes.fromhex(startup['startup_sequence_hex'])[4:10]
    raw=(f/'main.bin').read_bytes();ram=(f/'exports/sram-full.bin').read_bytes();rows=[]
    for profile in ['normal','mask-error-status','mask-wrong-opcode','no-first-event']:
        u=cpu(raw,ram,WORK+0xf000);stages=[]
        for index,expected in enumerate(COMMANDS):
            fields=struct.unpack('<6I',bytes(u.mem_read(ring,24)));record=fields[5]+fields[1];length=struct.unpack('<I',bytes(u.mem_read(record,4)))[0];packet=bytes(u.mem_read(record+4,length))
            if packet.hex()!=expected:raise ValueError('Different original initialization command '+case+'/'+profile+'/'+str(index)+': '+packet.hex()+' expected '+expected)
            traces=[call(u,ctx['ring_pop'],(ring,0,1))]
            if profile=='no-first-event':
                traces.append(call(u,ctx['upper_handler'],(1,0)));fields=struct.unpack('<6I',bytes(u.mem_read(ring,24)))
                if fields[:5]!=(1300,1300,0,2080,260):raise ValueError('No-event control advanced')
                stages.append(dict(command=expected,event=None,executions=traces));break
            opcode=int.from_bytes(packet[1:3],'little');status=1 if profile=='mask-error-status' and index==0 else 0
            response_opcode=0x0c02 if profile=='mask-wrong-opcode' and index==0 else opcode
            returns=bytes([status])+(address if opcode==0x1009 else b'')
            event=bytes([4,14,3+len(returns),1,response_opcode&255,response_opcode>>8])+returns;u.mem_write(WORK+0x100,event)
            traces.append(call(u,ctx['application_parser'],(WORK+0x100,len(event))));traces.append(call(u,ctx['upper_handler'],(1,0)))
            stages.append(dict(command=expected,event=event.hex(),executions=traces))
            if profile=='mask-wrong-opcode' and index==0:
                fields=struct.unpack('<6I',bytes(u.mem_read(ring,24)))
                if fields[:5]!=(1300,1300,0,2080,260):raise ValueError('Wrong standard opcode unexpectedly advanced')
                break
        fields=struct.unpack('<6I',bytes(u.mem_read(ring,24)));next_packet=None
        if profile in ['normal','mask-error-status']:
            record=fields[5]+fields[1];length=struct.unpack('<I',bytes(u.mem_read(record,4)))[0];next_packet=bytes(u.mem_read(record+4,length)).hex()
            if fields[:5]!=(260,0,260,2080,260) or next_packet!='01022000':raise ValueError('Different next information command')
        rows.append(dict(profile=profile,stages=stages,ring_words=list(fields),next_packet=next_packet))
    return dict(case=case,raw_sha256=sha(f/'main.bin'),sram_sha256=sha(f/'exports/sram-full.bin'),audit_sha256=sha(ap),commands=COMMANDS,identity_readback_sha256=__import__('hashlib').sha256(address).hexdigest(),samples=rows)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve prior evidence')
    rows=[inspect(a.simulator,c) for c in ['stock24','stock23','cfw']];completions=sum(stage['event'] is not None for row in rows for sample in row['samples'] for stage in sample['stages']);a.output.mkdir();(a.output/'inspector.py').write_bytes(Path(__file__).read_bytes());(a.output/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,original_software_scenarios=12,original_command_completion_stages=completions,no_event_controls=3,engine='Original ARM on Unicorn M7, synthetic calls/registers/stack, validated full native SRAM; explicit hypothetical replies',native_executions=0,physical_controller_data_known=False,hardware_accessed=False,boot_verified=False,display_verified=False),indent=2)+'\n');print('standard HCI source:12 software scenarios/'+str(completions)+' hypothetical command completions and3 no-event controls passed')


if __name__=='__main__':main()
