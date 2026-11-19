"""Build an original-ARM reference batch: list bind, destination, clip, letter, unbind.

No GPU execution. Uses frozen full-letter inputs, explicit synthetic surface and
original functions in Unicorn M7; exports the same five calls for M55 replay.
"""
import argparse,json,struct,hashlib
from pathlib import Path
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_PROT_READ,UC_PROT_EXEC
import unicorn.arm_const as arm
from inspect_ambiq_commands import discover,SAVED,BASE,WORK,SRAM,STOP
from inspect_ambiq_target import inspect,decode
from pinned_main import load_pinned_main
from native_replay import validate_assets,parse_log


def sha(data):return hashlib.sha256(data).hexdigest()


def batch_calls(raw,registers,stride):
    entries,slot=discover(raw);_,target=inspect(raw)
    body=decode(raw,int(target['entries']['target'],0),0x206)
    stop=next(j for j,i in enumerate(body) if i.mnemonic.startswith('pop') and 'pc' in i.op_str)
    clip=next(i.operands[0].imm for i in reversed(body[:stop]) if i.mnemonic=='bl')
    return [dict(name='list-bind',entry=entries['bind_circular'],args=[WORK+0x2000,2],stack=[]),
        dict(name='destination',entry=entries['texture_binding'],args=[0,WORK+0xa000,64,32],stack=[9,stride,0]),
        dict(name='clip',entry=clip,args=[WORK+0x800,WORK+0x700,0],stack=[]),
        dict(name='letter',entry=registers['entry'],args=[registers['registers']['R'+str(n)] for n in range(4)],stack=None),
        dict(name='list-unbind',entry=entries['unbind'],args=[],stack=[])]


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('captures',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--stride',type=int,choices=[64,80],default=64);a=p.parse_args();out=a.output.resolve()
    if any((v/'.git').exists() for v in [out,*out.parents]):raise ValueError('Private output required')
    out.mkdir(mode=0o700);old=json.loads((a.captures/'report.json').read_text());cases=[];pins={}
    for case,filename in [('stock24','stock-2.4.0.24.bin'),('stock23','stock-2.3.0.24.bin'),('cfw','faceclaw-38-research-only.bin')]:
        source=a.captures/'captures'/case/'full-letter';snapshot=json.loads((source/'snapshot.json').read_text());folder=out/'captures'/case/'full-letter';folder.mkdir(mode=0o700,parents=True)
        for name,digest in snapshot['image_hashes'].items():assert sha((source/name).read_bytes())==digest
        _,raw=load_pinned_main((a.simulator/'inputs/verified-01'/filename).read_bytes());assert sha(raw)==snapshot['raw_sha256']
        from prepare_nema_state_captures import validate_region
        validate_region(a.simulator,case,raw,snapshot,(source/'sram.bin').read_bytes())
        work=bytearray((source/'work.bin').read_bytes());work[0x700:0x710]=struct.pack('<4i',0,0,63,31)
        extent=a.stride*32;work[0x9fe0:0xa000+extent+32]=b'\xa5'*(extent+64);work[0xa000:0xa000+extent]=bytes(extent)
        calls=batch_calls(raw,snapshot,a.stride)
        calls[3]['stack']=list(struct.unpack_from('<2I',work,snapshot['registers']['SP']-WORK))
        u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);u.ctl_set_cpu_model(arm.UC_CPU_ARM_CORTEX_M7)
        u.reg_write(arm.UC_ARM_REG_C1_C0_2,0xf00000);u.reg_write(arm.UC_ARM_REG_FPEXC,0x40000000)
        size=(len(raw)+4095)&~4095;u.mem_map(BASE,size);u.mem_write(BASE,raw);u.mem_protect(BASE,size,UC_PROT_READ|UC_PROT_EXEC)
        u.mem_map(SRAM,0x80000);u.mem_write(SRAM,(source/'sram.bin').read_bytes());u.mem_protect(SRAM,0x80000,UC_PROT_READ)
        u.mem_map(WORK,0x10000);u.mem_write(WORK,bytes(work));u.mem_map(STOP,0x1000,UC_PROT_READ|UC_PROT_EXEC)
        native=a.simulator/'em9305-reset-main-01'/case;itcm=bytearray((native/'itcm-fill.bin').read_bytes());native_report=json.loads((native/'report.json').read_text());assert native_report['passed']
        validate_assets(native,json.loads((native/'derived-inputs.json').read_text())['derived'])
        assert parse_log((native/'renode.log').read_text())==native_report['observed'] and (native/'main.bin').read_bytes()==raw
        itcm[:256]=bytes(native_report['observed']['itcm_prefix']);u.mem_map(0,0x40000);u.mem_write(0,bytes(itcm));u.mem_protect(0,0x40000,UC_PROT_READ)
        for n,value in enumerate(snapshot['float_registers']):u.reg_write(getattr(arm,'UC_ARM_REG_S'+str(n)),value)
        u.reg_write(arm.UC_ARM_REG_FPSCR,snapshot['registers']['FPSCR'])
        phase_results=[];frame_before=bytes(u.mem_read(WORK+0x9fe0,extent+64));sram_before=bytes(u.mem_read(SRAM,0x80000))
        for phase in calls:
            for n in range(13):u.reg_write(getattr(arm,'UC_ARM_REG_R'+str(n)),snapshot['registers']['R'+str(n)])
            for reg,value in zip([arm.UC_ARM_REG_R0,arm.UC_ARM_REG_R1,arm.UC_ARM_REG_R2,arm.UC_ARM_REG_R3],phase['args']):u.reg_write(reg,value)
            u.reg_write(arm.UC_ARM_REG_SP,snapshot['registers']['SP']);u.reg_write(arm.UC_ARM_REG_LR,snapshot['registers']['LR'])
            if phase['stack']:u.mem_write(snapshot['registers']['SP'],struct.pack('<'+'I'*len(phase['stack']),*phase['stack']))
            before=bytes(u.mem_read(WORK,0x10000));u.emu_start(phase['entry']|1,STOP,count=200000)
            assert u.reg_read(arm.UC_ARM_REG_PC)==STOP and u.reg_read(arm.UC_ARM_REG_SP)==snapshot['registers']['SP']
            assert [u.reg_read(reg) for reg in SAVED]==[snapshot['registers']['R'+str(n)] for n in range(4,12)]
            after=bytes(u.mem_read(WORK,0x10000));allowed=[(0x300,0x330),(0x800,0x900),(0x1000,0x1100),(0x1800,0x180c),(0x2000,0x2040),(0x4000,0x5000),(0xfc00,0xff00)]
            assert all(any(x<=i<y for x,y in allowed) for i,(a,b) in enumerate(zip(before,after)) if a!=b)
            used=struct.unpack('<I',u.mem_read(WORK+0x2014,4))[0];phase_results.append(dict(name=phase['name'],used_words=used))
        assert bytes(u.mem_read(SRAM,0x80000))==sram_before and bytes(u.mem_read(WORK+0x9fe0,extent+64))==frame_before
        words=list(struct.unpack('<'+'I'*used,u.mem_read(WORK+0x4000,used*4)));terminator=list(struct.unpack('<2I',u.mem_read(WORK+0x4000+used*4,8)))
        assert words[:6]==[0,WORK+0xa000,4,(9<<24)|a.stride,8,(32<<16)|64]
        # The original clip wrapper passes width/height, and its callee encodes
        # x+width/y+height. Do not assume CLIPMAX is an inclusive pixel index.
        assert words[6:10]==[0x110,0,0x114,(32<<16)|64] and terminator==[0x50000,0]
        assert struct.unpack('<I',u.mem_read(WORK+0x1004,4))[0]==0
        snapshot['batch']=dict(calls=calls,words=words,terminator=terminator,phase_results=phase_results,
            surface=dict(address=WORK+0xa000,width=64,height=32,stride=a.stride,format=9,extent=extent),reference_engine='Unicorn Cortex-M7; original ARM functions')
        snapshot['image_hashes']['work.bin']=sha(work)
        (folder/'work.bin').write_bytes(bytes(work));(folder/'sram.bin').write_bytes((source/'sram.bin').read_bytes());(folder/'snapshot.json').write_text(json.dumps(snapshot,indent=2)+'\n')
        cases.append(next(c for c in old['cases'] if c['case']==case));pins[case]=dict(source_snapshot_sha256=sha((source/'snapshot.json').read_bytes()),prepared_snapshot_sha256=sha((folder/'snapshot.json').read_bytes()),word_count=used)
    (out/'report.json').write_text(json.dumps(dict(passed=True,cases=cases,batch_sources=pins,source_sha256=sha(Path(__file__).read_bytes()),full_main_rendered=False),indent=2)+'\n');(out/'preparer.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps(dict(passed=True,cases=pins)))


if __name__=='__main__':main()
