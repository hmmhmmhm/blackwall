"""Pin vendor startup commands and execute original feature/power constructors."""
import argparse,hashlib,json,struct
from pathlib import Path
import unicorn.arm_const as arm
from inspect_application_vendor_address import call,sha
from inspect_nema_blocking_wait import cpu,WORK,STOP
from inspect_ambiq_target import decode
from inspect_em9305_hci_framing import literal


def inspect(s,case):
    prior_path=s/'application-vendor-address-source-02/report.json'
    pin=json.loads((s/'application-vendor-address-verification-01/manifest.json').read_text())['analysis_sha256']
    if sha(prior_path)!=pin:raise ValueError('Changed address source contract')
    row=next(r for r in json.loads(prior_path.read_text())['cases'] if r['case']==case)
    f=s/('application-hci-reset-main-02' if case=='stock24' else 'application-hci-reset-main-01')/case
    raw=(f/'main.bin').read_bytes();ram=(f/'exports/sram-full.bin').read_bytes()
    if sha(f/'main.bin')!=row['raw_sha256'] or sha(f/'exports/sram-full.bin')!=row['sram_sha256']:raise ValueError('Changed source image/SRAM')
    previous=json.loads((s/'application-hci-transaction-source-02/report.json').read_text());ctx=next(r for r in previous['cases'] if r['case']==case)
    ring=next(r for r in json.loads((s/'application-hci-source-01/report.json').read_text())['cases'] if r['case']==case)['tx_ring']
    feature,power=row['constructor']-0x7e,row['constructor']-0x56
    slot=literal(raw,decode(raw,feature+2,4)[0]);feature_mask=bytes.fromhex('ff7d010fb819' if case=='cfw' else 'ff7c010fb819');samples=[]
    for tail in [b'\0\0',b'\xa5\x5a']:
        u=cpu(raw,ram,WORK+0xf000);u.mem_write(slot,b'\x99'*6+tail);t=call(u,feature,(),[feature+0x22]);args=[u.reg_read(getattr(arm,'UC_ARM_REG_R'+str(n))) for n in range(3)]
        if args!=[0xfff2,8,slot] or bytes(u.mem_read(slot,8))!=feature_mask+tail:raise ValueError('Feature constructor or preserved tail differs')
        samples.append(dict(kind='feature-constructor',tail=tail.hex(),mask=(feature_mask+tail).hex(),execution=t))
    for value in range(256):
        signed=value if value<128 else value-256;valid=-27<=signed<=6
        u=cpu(raw,ram,WORK+0xf000);t=call(u,power,(value,),[power+0x14])
        if t['stop']!=(power+0x14 if valid else STOP):raise ValueError('Power range differs')
        if valid:
            args=[u.reg_read(getattr(arm,'UC_ARM_REG_R'+str(n))) for n in range(3)]
            if args[:2]!=[0xfcc4,1] or bytes(u.mem_read(args[2],1))!=bytes([value]):raise ValueError('Power constructor differs')
        elif u.reg_read(arm.UC_ARM_REG_R0)!=0:raise ValueError('Invalid power accepted')
        samples.append(dict(kind='power-range',input_byte=value,signed=signed,accepted=valid,execution=t))
    u=cpu(raw,ram,WORK+0xf000);commands=[];replies=[];traces=[]
    for opcode,returns in [(0xfc43,b'\0'),(0xfff2,b'\0'),(0xfcc4,bytes([0,6,6]))]:
        fields=struct.unpack('<6I',bytes(u.mem_read(ring,24)));ptr=fields[5]+fields[1];size=struct.unpack('<I',bytes(u.mem_read(ptr,4)))[0];packet=bytes(u.mem_read(ptr+4,size))
        if packet[0]!=1 or int.from_bytes(packet[1:3],'little')!=opcode or packet[3]+4!=size:raise ValueError('Different original startup command')
        commands.append(packet.hex());traces.append(call(u,ctx['ring_pop'],(ring,0,1)))
        event=bytes([4,14,len(returns)+3,1,opcode&255,opcode>>8])+returns;replies.append(event.hex());u.mem_write(WORK+0x100,event)
        traces.append(call(u,ctx['application_parser'],(WORK+0x100,len(event))));traces.append(call(u,ctx['upper_handler'],(1,0)))
    if bytes.fromhex(commands[1])!=bytes.fromhex('01f2ff08')+feature_mask+b'\0\0' or commands[2]!='01c4fc0106':raise ValueError('Different native feature/power data')
    fields=struct.unpack('<6I',bytes(u.mem_read(ring,24)));ptr=fields[5]+fields[1];size=struct.unpack('<I',bytes(u.mem_read(ptr,4)))[0];packet=bytes(u.mem_read(ptr+4,size))
    if fields[:5]!=(1300,1040,260,2080,260) or size!=12 or packet[:4].hex()!='01010c08':raise ValueError('Different post-startup queue')
    samples.append(dict(kind='hypothetical-three-completion-pipeline',executions=traces,next_packet=packet.hex(),controller_execution=False))
    return dict(case=case,raw_sha256=row['raw_sha256'],sram_sha256=row['sram_sha256'],feature_constructor=feature,power_constructor=power,feature_slot=slot,feature_mask=(feature_mask+b'\0\0').hex(),startup_sequence_hex=''.join(commands),startup_replies_hex=replies,next_packet=packet.hex(),samples=samples)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve previous evidence')
    rows=[inspect(a.simulator,c) for c in ['stock24','stock23','cfw']]
    a.output.mkdir();(a.output/'inspector.py').write_bytes(Path(__file__).read_bytes());(a.output/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,original_arm_scenarios=sum(len(r['samples']) for r in rows),native_executions=0,hardware_accessed=False,controller_reset_or_persistence_known=False,boot_verified=False,display_verified=False),indent=2)+'\n');print('vendor startup source:777 original ARM scenarios passed; stock/Faceclaw feature bit differs')


if __name__=='__main__':main()
