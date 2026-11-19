"""Trace original LittleFS config installation and mount-format-remount policy."""
import argparse,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from capstone.arm import ARM_OP_MEM,ARM_REG_PC
from pinned_main import load_pinned_main


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;a.output.mkdir(mode=0o700)
    previous=json.loads((s/'post-nvdb-mspi-read-contract-02/report.json').read_text());checks=[];cases=[]
    def check(n,v):
        if not v:raise ValueError(n)
        checks.append(n)
    check('prior-contract67',previous['passed'] and previous['count']==67)
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS);md.detail=True
    for row,filename in zip(previous['cases'],['stock-2.4.0.24.bin','stock-2.3.0.24.bin','faceclaw-38-research-only.bin']):
        key=row['case'];_,raw=load_pinned_main((s/'inputs/verified-01'/filename).read_bytes())
        def code(addr,size):return {i.address:(i.mnemonic,i.op_str) for i in md.disasm(raw[addr-0x438000:addr+size-0x438000],addr)}
        def literal(addr):
            i=next(md.disasm(raw[addr-0x438000:addr+4-0x438000],addr));mem=next(o.mem for o in i.operands if o.type==ARM_OP_MEM and o.mem.base==ARM_REG_PC)
            return struct.unpack_from('<I',raw,(((addr+4)&~3)+mem.disp)-0x438000)[0]
        def text(addr):
            if not 0x438000<=addr<0x438000+len(raw):raise ValueError('String outside main')
            return raw[addr-0x438000:addr-0x438000+256].split(b'\0')[0].decode('ascii')
        def target(c,addr):
            check(key+'-BL-'+hex(addr),c[addr][0]=='bl');return int(c[addr][1][1:],0)
        callback=int(row['read_callback'],0);entry=callback-0x154;c=code(entry,0x154)
        cfg=literal(entry+6);obj=literal(entry+4)
        check(key+'-app-init-entry',c[entry]==('push','{r3, r4, r5, r6, lr}') and c[entry+2]==('sub','sp, #0x24'))
        check(key+'-same-pinned-config-table',cfg==int(row['config_table_candidate'],0))
        check(key+'-bounded-SRAM-object',obj%4==0 and 0x20000000<=obj<=0x20380000-0x70)
        check(key+'-mount-arguments',c[entry+8]==('movs','r1, r4') and c[entry+10]==('movs','r0, r6'))
        mount=target(c,entry+0xc);format_=target(c,entry+0x1a);remount=target(c,entry+0x22)
        check(key+'-any-nonzero-mount-formats',c[entry+0x10]==('movs','r5, r0') and c[entry+0x12]==('cmp','r5, #0') and c[entry+0x14]==('beq','#'+hex(entry+0x84)))
        check(key+'-format-return-ignored',c[entry+0x1e]==('movs','r1, r4') and c[entry+0x20]==('movs','r0, r6') and remount==mount)
        check(key+'-remount-result-checked',c[entry+0x26]==('movs','r4, r0') and c[entry+0x28]==('cmp','r4, #0') and c[entry+0x2a]==('beq','#'+hex(entry+0x6c)))
        check(key+'-format-diagnostic-and-init-name',text(literal(entry+0x36))=='lfs_format faild: %d\n' and text(literal(entry+0x3e))=='littlefs_init')
        check(key+'-remount-failure-return9',c[entry+0x68]==('movs','r0, #9') and c[entry+0x6a]==('b','#'+hex(entry+0x150)))
        wrapper=code(mount,10);internal=target(wrapper,mount+4)
        check(key+'-mount-wrapper',wrapper[mount]==('push','{r7, lr}') and wrapper[mount+2]==('movs','r2, #0'))
        body=code(internal,16);initialize=target(body,internal+8);init=code(initialize,10)
        check(key+'-config-installed-original-code',init[initialize+4]==('str','r1, [r4, #0x68]') and init[initialize+6]==('ldr','r0, [r1, #0x20]') and init[initialize+8]==('str','r0, [r4, #0x6c]'))
        table=list(struct.unpack_from('<16I',raw,cfg-0x438000))
        check(key+'-original-config-values',table==row['config_candidate_words'] and table[8]==3008 and table[7]==4096)
        check(key+'-volume-adjoins-KVdb',0x1400000+table[7]*table[8]==0x1fc0000)
        cases.append(dict(case=key,app_init=hex(entry),mount=hex(mount),format=hex(format_),config_init=hex(initialize),read_callback=hex(callback),config=hex(cfg),state_object=hex(obj),config_snapshot=hex(obj+0x68),config_words=table,
                          volume_start='0x1400000',block_size=4096,configured_blocks=3008,volume_end='0x1fc0000',policy='any nonzero first mount -> format (return ignored) -> remount; checked failure returns9'))
    result=dict(passed=True,count=len(checks),checks=checks,cases=cases,scope='Original config installation and app policy; live callback config pointer/count still require observation; no backing data, mount completion or hardware execution')
    (a.output/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks))))


if __name__=='__main__':main()
