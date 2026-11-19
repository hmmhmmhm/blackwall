"""Explicit mock controller-information profiles consumed by original ARM initialization."""
import argparse,json,struct
import unicorn.arm_const as arm
from pathlib import Path
from inspect_application_vendor_address import call,sha
from inspect_nema_blocking_wait import cpu,WORK
from inspect_ambiq_target import decode
from inspect_em9305_hci_framing import literal

PROFILES={'le-basic-27x4':(27,4),'le-large-251x8':(251,8)}
COMMANDS=['01022000','011c2000','010f2000','01032000']
STATES=bytes.fromhex('ff01000000000000')


def inspect(s,case):
    metadata=s/'le-buffer-source-02/report.json';pin=json.loads((s/'le-buffer-verification-01/manifest.json').read_text())['source_sha256']
    if sha(metadata)!=pin:raise ValueError('Changed original buffer contract')
    prior=next(r for r in json.loads(metadata.read_text())['cases'] if r['case']==case);f=s/'standard-hci-main-01'/case
    raw=(f/'main.bin').read_bytes();ram=(f/'exports/sram-full.bin').read_bytes()
    if sha(f/'main.bin')!=prior['raw_sha256'] or sha(f/'exports/sram-full.bin')!=prior['sram_sha256']:raise ValueError('Changed native source')
    p=s/'application-hci-transaction-source-02/report.json';pin=json.loads((s/'application-hci-reset-verification-01/manifest.json').read_text())['retained_source_sha256']
    if sha(p)!=pin:raise ValueError('Changed parser/ring callbacks')
    ctx=next(r for r in json.loads(p.read_text())['cases'] if r['case']==case)
    p=s/'application-hci-source-01/report.json';pin=json.loads((s/'application-hci-idle-verification-01/manifest.json').read_text())['source_report_sha256']
    if sha(p)!=pin:raise ValueError('Changed ring metadata')
    ring=next(r for r in json.loads(p.read_text())['cases'] if r['case']==case)['tx_ring']
    p=s/'vendor-startup-source-01/report.json';pin=json.loads((s/'vendor-startup-verification-01/manifest.json').read_text())['source_sha256']
    if sha(p)!=pin:raise ValueError('Changed feature source')
    feature=bytes.fromhex(next(r for r in json.loads(p.read_text())['cases'] if r['case']==case)['feature_mask'])
    c=prior['contract'];cb,base=c['callback'],c['base'];state_slot=literal(raw,decode(raw,cb+0xf2,4)[0])
    if literal(raw,decode(raw,cb+0x104,4)[0])!=base or decode(raw,cb+0x106,4)[0].op_str!='r0, [r1, #0x84]' or decode(raw,cb+0x11a,4)[0].op_str!='r0, r1, [r2, #0x88]':raise ValueError('Changed filter/features consumers')
    rows=[]
    for name,(length,count) in PROFILES.items():
        u=cpu(raw,ram,WORK+0xf000);replies=[];stages=[]
        for command,returns in zip(COMMANDS,[b'\0'+struct.pack('<H',length)+bytes([count]),b'\0'+STATES,bytes([0,4]),b'\0'+feature]):
            fields=struct.unpack('<6I',bytes(u.mem_read(ring,24)));record=fields[5]+fields[1];n=struct.unpack('<I',bytes(u.mem_read(record,4)))[0];packet=bytes(u.mem_read(record+4,n))
            if packet.hex()!=command:raise ValueError('Different original information command')
            phases=[call(u,ctx['ring_pop'],(ring,0,1))];opcode=int.from_bytes(packet[1:3],'little');reply=bytes([4,14,len(returns)+3,1,opcode&255,opcode>>8])+returns;replies.append(reply.hex());u.mem_write(WORK+0x100,reply)
            phases.append(call(u,ctx['application_parser'],(WORK+0x100,len(reply))));phases.append(call(u,ctx['upper_handler'],(1,0)));stages.append(dict(command=command,reply=reply.hex(),executions=phases))
        if bytes(u.mem_read(state_slot,8))!=STATES or bytes(u.mem_read(base+0x88,8))!=feature or bytes(u.mem_read(base+0x84,1))!=b'\x04':raise ValueError('Information data not stored by original consumers')
        if struct.unpack('<H',bytes(u.mem_read(base+0x7e,2)))[0]!=length or bytes(u.mem_read(base+0x82,2))!=bytes([count,count]):raise ValueError('Buffer profile not retained')
        getter=call(u,c['getter'],())
        if u.reg_read(arm.UC_ARM_REG_R0)!=length:raise ValueError('Original getter disagrees with profile')
        fields=list(struct.unpack('<6I',bytes(u.mem_read(ring,24))));record=fields[5]+fields[1];n=struct.unpack('<I',bytes(u.mem_read(record,4)))[0];packet=bytes(u.mem_read(record+4,n)).hex()
        if fields[:5]!=[1300,1040,260,2080,260] or packet!='012a2000':raise ValueError('Different next privacy capacity query')
        rows.append(dict(profile=name,acl_length=length,acl_packets=count,states=STATES.hex(),filter_accept_list_size=4,features=feature.hex(),replies=replies,stages=stages,getter_execution=getter,next_packet=packet,ring_words=fields))
    return dict(case=case,raw_sha256=prior['raw_sha256'],sram_sha256=prior['sram_sha256'],control_base=base,states_slot=state_slot,buffer_getter=c['getter'],samples=rows)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve previous evidence')
    rows=[inspect(a.simulator,c) for c in ['stock24','stock23','cfw']];a.output.mkdir();(a.output/'inspector.py').write_bytes(Path(__file__).read_bytes());(a.output/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,software_profiles=6,command_completion_stages=24,engine='Original ARM on Unicorn M7; synthetic calls/registers/stack; source-validated full native SRAM; explicit mock information',native_executions=0,actual_acl_transmission_or_credit_consumption_verified=False,physical_controller_data_known=False,hardware_accessed=False,boot_verified=False,display_verified=False),indent=2)+'\n');print('controller information:6 source profiles/24 hypothetical command completions passed')


if __name__=='__main__':main()
