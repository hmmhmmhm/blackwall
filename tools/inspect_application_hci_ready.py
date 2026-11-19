"""Application HCI callback/ring and original GPIO/dispatch fragments, no I/O."""
import argparse,json,hashlib,struct
from pathlib import Path
import unicorn.arm_const as arm
from inspect_nema_blocking_wait import cpu,WORK
from inspect_keydb_record_load import run
from inspect_ambiq_target import decode
from inspect_em9305_hci_framing import literal,discover

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def inspect(s,case):
    f=s/'ota-marker-cleared-main-01'/case;ap=s/'ota-marker-read-saved-audit-01'/case/'report.json';a=json.loads(ap.read_text());r=json.loads((f/'report.json').read_text())
    if not a['passed']:raise ValueError('Unverified native source')
    for n,h in a['capture_hashes'].items():
        if sha(f/n)!=h:raise ValueError('Changed source '+n)
    raw=(f/'main.bin').read_bytes();ram=(f/'exports/sram-full.bin').read_bytes();regs=r['observed']['register_context'];pc=regs['r15'];c=discover(raw);ring=literal(raw,decode(raw,pc+0x102,2)[0]);fields=struct.unpack_from('<6I',ram,ring-0x20000000)
    stride,head,used,capacity,tail,buffer=fields
    if (stride,head,used,capacity,tail)!=(260,0,260,2080,260) or not 0x20000000<=buffer<=0x20380000-capacity:raise ValueError('Unknown TX ring layout/state')
    entry=buffer+head;n=struct.unpack_from('<I',ram,entry-0x20000000)[0];packet=ram[entry-0x20000000+4:entry-0x20000000+4+n]
    if n!=4 or packet.hex()!='01030c00':raise ValueError('Different actual queued HCI packet')
    readcall=decode(raw,pc+0x36,4)[0];writecall=decode(raw,pc+0x11e,4)[0]
    if readcall.op_str!='#'+hex(c['read']) or writecall.op_str!='#'+hex(c['read']-0x118):raise ValueError('Application driver differs from initial SPI/HCI helpers')
    table,index=struct.unpack_from('<II',ram,regs['r13']-0x20000000+12)
    callback=struct.unpack_from('<I',ram,table-0x20000000+index*4)[0]
    if callback!=pc-0xcd or regs['r2']!=callback:raise ValueError('Different natural scheduler callback')
    rows=[]
    for level in [0,1<<21,0xffffffff^(1<<21),0xffffffff]:
        u=cpu(raw,ram,WORK+0xf000);u.mem_map(0x40010000,4096);u.mem_write(0x40010410,struct.pack('<I',level));u.reg_write(arm.UC_ARM_REG_R0,0x40010410);t=run(u,pc,[pc+10,pc+0x102]);ready=bool(level&(1<<21))
        if t['stop']!=(pc+10 if ready else pc+0x102):raise ValueError('Different original GPIO branch')
        rows.append(dict(kind='gpio-level',word=level,ready=ready,result='RX-path' if ready else 'TX-ring-path',execution=t))
    for available in [False,True]:
        data=bytearray(ram)
        if not available:struct.pack_into('<I',data,ring-0x20000000+8,0)
        u=cpu(raw,bytes(data),WORK+0xf000);t=run(u,pc+0x102,[pc+0x11e,pc+0x13e])
        if t['stop']!=(pc+0x11e if available else pc+0x13e):raise ValueError('Different original queue decision')
        args=None
        if available:
            args=[u.reg_read(getattr(arm,'UC_ARM_REG_R'+str(i))) for i in range(3)]
            if args[1:]!=[entry+4,4]:raise ValueError('Different original write arguments')
        rows.append(dict(kind='tx-ring',available=available,write_arguments=args,execution=t))
    for counter in [0,999,1000]:
        u=cpu(raw,ram,WORK+0xf000);u.reg_write(arm.UC_ARM_REG_R11,counter);t=run(u,pc-18,[pc-4,pc+0x14a])
        if t['stop']!=(pc-4 if counter<1000 else pc+0x14a) or u.reg_read(arm.UC_ARM_REG_R11)!=counter+1:raise ValueError('Different source loop bound')
        rows.append(dict(kind='poll-limit',counter_before=counter,counter_after=counter+1,execution=t))
    return dict(case=case,raw_sha256=sha(f/'main.bin'),audit_sha256=sha(ap),sram_sha256=sha(f/'exports/sram-full.bin'),gpio_pc=pc,gpio_address=0x40010410,gpio_bit=21,scheduler_callback=callback,scheduler_table=table,saved_callback_index=index,tx_ring=ring,ring_words=list(fields),queued_pointer=entry+4,queued_length=n,queued_packet=packet.hex(),original_read=c['read'],original_write=c['read']-0x118,samples=rows)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve prior result')
    rows=[inspect(a.simulator,c) for c in ['stock24','stock23','cfw']];a.output.mkdir(parents=True);(a.output/'inspector.py').write_bytes(Path(__file__).read_bytes());(a.output/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,original_arm_scenarios=27,native_main_rerun=False,hardware_accessed=False,full_irq_lifecycle_or_handler_executed=False,hci_reset_transmitted=False),indent=2)+'\n');print('application HCI source:27 original ARM scenarios passed; queued01030c00 in3 images')
if __name__=='__main__':main()
