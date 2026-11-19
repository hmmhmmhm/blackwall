"""Bind native SRAM patch-key consumer and execute its original loader with ABI stubs."""
import argparse,hashlib,json,re,struct
from pathlib import Path
from unicorn import UC_HOOK_CODE
import unicorn.arm_const as arm
from inspect_ambiq_target import decode
from inspect_imu_power import body
from inspect_em9305_hci_framing import literal
from inspect_nema_blocking_wait import cpu,WORK,STOP
from prepare_vendor_startup_candidate import sha


def exercise(raw,ram,entry,read,write,key,marker,read_status,write_status,payloads):
    u=cpu(raw,ram,WORK+0xf000);out=WORK+0x200
    u.mem_write(out,b'\xa5'*4);u.reg_write(arm.UC_ARM_REG_R0,WORK+0x100);u.reg_write(arm.UC_ARM_REG_R1,out)
    requests=[];trace=[]
    def code(c,pc,size,user):
        trace.append(pc)
        if pc not in [read,write]:return
        args=[c.reg_read(getattr(arm,'UC_ARM_REG_R'+str(k))) for k in range(4)]
        assert args[0]==WORK+0x100
        _,address,length,pointer=args
        if pc==read:
            assert not requests and address==0x48 and length==4
            data=struct.pack('<I',marker);c.mem_write(pointer,data);status=read_status
        else:
            data=bytes(c.mem_read(pointer,length));status=write_status
            assert (address,length) in [(0x1580,25),(0x48,4),(0x1600,375)]
            expected=struct.pack('<I',key) if address==0x48 else payloads[address]
            assert data==expected
        requests.append(dict(kind='read' if pc==read else 'write',address=address,length=length,data_sha256=hashlib.sha256(data).hexdigest(),status=status))
        c.reg_write(arm.UC_ARM_REG_R0,status);c.reg_write(arm.UC_ARM_REG_PC,c.reg_read(arm.UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE,code);u.emu_start(entry|1,STOP,count=10000)
    assert u.reg_read(arm.UC_ARM_REG_PC)==STOP and u.reg_read(arm.UC_ARM_REG_SP)==WORK+0xf000
    expected=[(0x1580,25),(0x48,4),(0x1600,375)] if marker==0 else [(0x1600,375)]
    assert [(q['address'],q['length']) for q in requests[1:]]==expected
    status=0xffffffff if marker not in [0,key] else read_status|write_status
    assert u.reg_read(arm.UC_ARM_REG_R0)==status and bytes(u.mem_read(out,4))==b'\x00\xa5\xa5\xa5'
    return dict(marker=marker,read_status=read_status,write_status=write_status,returned_status=status,
                usecase_output=0,requests=requests,instructions=len(trace),trace_sha256=hashlib.sha256(struct.pack('<'+'I'*len(trace),*trace)).hexdigest())


def inspect(s,case,public_dispatch,public_b2s):
    manifest=json.loads((s/'imu-edmp-service-verification-01/manifest.json').read_text());assert manifest['passed']
    ap=s/'imu-edmp-service-saved-audit-01'/case/'report.json';assert sha(ap)==manifest['files'][str(ap.relative_to(s))]
    audit=json.loads(ap.read_text());f=Path(audit['capture'])
    for name,pin in audit['capture_hashes'].items():assert sha(f/name)==pin
    r=json.loads((f/'report.json').read_text());raw=(f/'main.bin').read_bytes();ram=(f/'exports/sram-full.bin').read_bytes();sp=r['observed']['register_context']['r13']
    ret=lambda off:struct.unpack_from('<I',ram,sp+off-0x20000000)[0]&~1
    call=decode(raw,ret(0x11c)-4,4)[0];assert call.mnemonic=='bl';entry=call.operands[0].imm
    b=body(raw,entry);calls=[i for i in b if i.mnemonic=='bl'];assert len(calls)==4 and ret(0xfc)==calls[0].address+4
    read=calls[0].operands[0].imm;write=calls[1].operands[0].imm;assert all(i.operands[0].imm==write for i in calls[1:])
    assert any(i.op_str=='r1, #0x48' for i in b) and any(i.op_str=='r1, #0x1580' for i in b) and any(i.op_str=='r1, #0x1600' for i in b)
    loads=[i for i in b if i.mnemonic in ['ldr','ldr.w'] and '[pc,' in i.op_str];assert len(loads)==3
    key=literal(raw,loads[0]);assert key==0x801570f1
    payloads={}
    for i,address,length in zip(loads[1:],[0x1580,0x1600],[25,375]):
        p=literal(raw,i);assert 0x20000000<=p<=0x20380000-length;payloads[address]=ram[p-0x20000000:p-0x20000000+length]
    assert payloads[0x1580]==public_dispatch and len(public_b2s)==1310 and payloads[0x1600]!=public_b2s
    samples=[exercise(raw,ram,entry,read,write,key,marker,rs,ws,payloads)
             for marker in [0,key,1,0xffffffff] for rs in [0,0xfffffffd] for ws in [0,0xfffffffd]]
    return dict(case=case,source_audit_sha256=sha(ap),entry=entry,read_sram=read,write_sram=write,
                patch_key=key,patch_key_address=0x48,dispatcher_address=0x1580,dispatcher_bytes=25,
                dispatcher_sha256=hashlib.sha256(payloads[0x1580]).hexdigest(),public_dispatcher_exact=True,
                feature_address=0x1600,feature_bytes=375,feature_sha256=hashlib.sha256(payloads[0x1600]).hexdigest(),
                public_feature_bytes=1310,public_feature_address=0x1000,public_feature_exact=False,samples=samples)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    assert not a.output.exists() and a.output.resolve().is_relative_to(a.simulator.resolve())
    public=a.simulator/'imu-edmp-patch-research-01'
    source=json.loads((public/'source-manifest.json').read_text())
    tree=json.loads((a.simulator/'iom4-command-source-research-01/tdk-canonical-tree.json').read_text())['tree']
    assert source['commit']=='646f55a6ec119b59d9ebce47af660842b53e5506'
    for e in source['files']:
        f=public/Path(e['path']).name;b=f.read_bytes();assert sha(f)==e['sha256']
        assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==e['blob']==next(x['sha'] for x in tree if x['path']==e['path'])
    get=lambda name:bytes(int(x,16) for x in re.findall(r'0x([0-9a-fA-F]{2})',(public/name).read_text()))
    rows=[inspect(a.simulator,c,get('edmp_prgm_ram_dispatch.h'),get('edmp_ram_b2s_image.h')) for c in ['stock24','stock23','cfw']]
    assert len({x['feature_sha256'] for x in rows})==len({x['dispatcher_sha256'] for x in rows})==1
    a.output.mkdir(mode=0o700);(a.output/'inspector.py').write_bytes(Path(__file__).read_bytes())
    (a.output/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,original_arm_wrapper_scenarios=sum(len(x['samples']) for x in rows),
        sram_read_write_callees_stubbed=True,physical_edmp_execution=False,native_main_rerun=False,hardware_accessed=False,boot_verified=False,display_verified=False),indent=2)+'\n')
    print('Original patch loader scenarios',sum(len(x['samples']) for x in rows),'three original feature payloads identical; public version differs')
if __name__=='__main__':main()
