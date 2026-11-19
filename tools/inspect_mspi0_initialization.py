"""Bound original uLED MSPI0 clock/configuration calls on declared register fixtures."""
import argparse
import hashlib
import json
import re
import struct
import xml.etree.ElementTree as ET
from pathlib import Path
import unicorn.arm_const as arm
from inspect_mspi1_config_contract import collect
from inspect_mspi0_power_profiles import inspect as verify_capture
from inspect_ambiq_target import decode
from inspect_em9305_hci_framing import literal
from inspect_nema_blocking_wait import cpu,WORK,STOP
from inspect_application_vendor_address import call
from prepare_vendor_startup_candidate import sha


class Registers:
    def __init__(self,spec,misc,mode,clock=0xa4211):
        self.spec=spec;self.values={a:r['reset'] for a,r in spec.items()}
        self.clock={0x110:clock,0x44:misc};self.mode=mode;self.events=[];self.unknown=[]

    def fail(self,u,operation,offset,size,value=None):
        self.unknown.append(dict(operation=operation,offset=offset,size=size,value=value))
        u.emu_stop()
        return 0xffffffff

    def mread(self,u,offset,size,user):
        if size!=4 or offset not in self.spec:return self.fail(u,'mspi-read',offset,size)
        value=self.values[offset];self.events.append(dict(operation='mspi-read',offset=offset,value=value));return value

    def mwrite(self,u,offset,size,value,user):
        if size!=4 or offset not in self.spec:self.fail(u,'mspi-write',offset,size,value);return
        self.events.append(dict(operation='mspi-write',offset=offset,value=value));self.values[offset]=value

    def cread(self,u,offset,size,user):
        if size!=4:return self.fail(u,'clock-read',offset,size)
        if offset==0x30:
            enabled=bool(self.clock[0x44]&32) or (self.mode>>3)&3==2
            value=(0x81000000 if enabled else 0)|(0x40000000 if self.clock[0x44]&1 else 0)
        elif offset in self.clock:value=self.clock[offset]
        else:return self.fail(u,'clock-read',offset,size)
        self.events.append(dict(operation='clock-read',offset=offset,value=value));return value

    def cwrite(self,u,offset,size,value,user):
        if size!=4 or offset not in self.clock:self.fail(u,'clock-write',offset,size,value);return
        self.events.append(dict(operation='clock-write',offset=offset,value=value));self.clock[offset]=value

    def attach(self,u):
        u.mmio_map(0x40060000,0x1000,self.mread,None,self.mwrite,None)
        u.mmio_map(0x40004000,0x1000,self.cread,None,self.cwrite,None)


def state(u,ram_length):
    return (bytes(u.mem_read(0x20000000,ram_length)),bytes(u.mem_read(WORK,0x10000)),
            [u.reg_read(getattr(arm,'UC_ARM_REG_R'+str(n))) for n in range(16)],u.reg_read(arm.UC_ARM_REG_XPSR),u.reg_read(arm.UC_ARM_REG_PRIMASK))


def inspect(s,case,spec):
    verify_capture(s,case,'mspi0-power-main-01',case,'active');folder=s/'mspi0-power-main-01'/case
    raw=(folder/'main.bin').read_bytes();ram=(folder/'exports/sram-full.bin').read_bytes();v=json.loads((folder/'report.json').read_text())['observed']
    frame=struct.unpack_from('<14I',ram,v['register_context']['r13']-0x20000000)
    instance,tcb,descriptor,parent=frame[1],frame[7],frame[8],frame[9]&~1
    if frame[3]!=0 or struct.unpack_from('<II',ram,instance-0x20000000)!=(0x1bebebe,0):raise ValueError('Different original module0 frame')
    clock=v['pc']-0x3c;delay=clock+0x54
    if [(i.mnemonic,i.op_str) for i in decode(raw,clock,2)]!=[('push','{r3, r4, r5, r6, r7, lr}')]:raise ValueError('Different clock prologue')
    if decode(raw,delay,4)[0].mnemonic!='bl':raise ValueError('Different clock delay boundary')
    targets={}
    for name,offset in [('configure',0x5c),('device-configure',0xa8),('enable',0xf2)]:
        i=decode(raw,parent+offset,4)[0]
        if i.mnemonic!='bl':raise ValueError('Different uLED initialization call')
        targets[name]=i.operands[0].imm
    logsite=decode(raw,parent+0xc4,4)[0];text_pointer=literal(raw,logsite)
    text=raw[text_pointer-0x438000:text_pointer-0x438000+200].split(b'\0')[0].decode('ascii')
    if not text.endswith('driver\\uled\\drv_mspi_uled_common.c'):raise ValueError('Different original uLED diagnostic source')
    response=v['mcu_clock_response']
    if response['profile']!='nominal' or response['mode_word']!=22 or not response['hfrc2_ready'] or not response['hfrc_forced']:
        raise ValueError('Unverified existing nominal clock fixture')
    misc=response['misc_word'];rows=[]
    defaults=literal(raw,decode(raw,parent+0x46,4)[0])
    if 0x20000000<=defaults<=0x20000000+len(ram)-12:default_words=struct.unpack_from('<3I',ram,defaults-0x20000000)
    elif 0x438000<=defaults<=0x438000+len(raw)-12:default_words=struct.unpack_from('<3I',raw,defaults-0x438000)
    else:raise ValueError('Original configuration template outside validated snapshot')
    alternate_clock=default_words[2]&255
    if alternate_clock not in (0,1):raise ValueError('Different original alternate-clock flag')
    power_call=decode(raw,parent-4,4)[0];sleep=decode(raw,parent+0x1b2,10)
    if [(i.mnemonic,i.op_str) for i in sleep[:2]]!=[('movs','r2, #1'),('movs','r1, #2')] or sleep[-1].mnemonic!='bl' or sleep[-1].operands[0].imm!=power_call.operands[0].imm:
        raise ValueError('Different retained power-state request')
    for initial in [0xa4214,(0xa4214&~0x3e0)|(7<<6)|0x20]:
        for selection in [7,8,9,10]:
            bank=Registers(spec,misc,22,initial);u=cpu(raw,ram,WORK+0xf000);bank.attach(u)
            t=call(u,clock,(0,1,1,selection),[delay]);expected=(initial&~0x1e)|(selection<<1)|1
            writes=[x['value'] for x in bank.events if x['operation']=='clock-write']
            if bank.unknown or bank.clock[0x110]!=expected or writes!=[expected&~1,expected]:raise ValueError('Different original two-stage clock writes')
            rows.append(dict(kind='clock-select-enable',initial=initial,selection=selection,writes=writes,execution=t))
    for enabled,change in [(1,0),(0,1)]:
        bank=Registers(spec,misc,22,0xa4215);u=cpu(raw,ram,WORK+0xf000);bank.attach(u)
        t=call(u,clock,(0,enabled,change,8),[delay] if enabled else [])
        expected=0xa4215 if enabled else 0xa4214
        if bank.unknown or bank.clock[0x110]!=expected:raise ValueError('Different original clock gate update')
        rows.append(dict(kind='clock-gate',enabled=enabled,change_selection=change,value=expected,execution=t))
    bank=Registers(spec,misc,22);u=cpu(raw,ram,WORK+0xf000);bank.attach(u)
    config=struct.pack('<IIB3x',0x100,tcb,alternate_clock);u.mem_write(WORK+0x100,config)
    t=call(u,targets['configure'],(instance,WORK+0x100))
    if t['stop']!=STOP or u.reg_read(arm.UC_ARM_REG_R0)!=0 or bank.unknown:raise ValueError('Original TCB configuration failed')
    if [(e['offset'],e['value']) for e in bank.events if e['operation']=='mspi-write']!=[(0x90,0),(0x9c,0),(0x80,0)]:
        raise ValueError('Different initial configuration writes')
    # The callback backend observes only MMIO, never SRAM memset/STM writes.
    # Compare the complete guest state against ordinary memory for this bounded function.
    plain=cpu(raw,ram,WORK+0xf000);plain.mem_map(0x40060000,0x1000)
    for offset,r in spec.items():plain.mem_write(0x40060000+offset,struct.pack('<I',r['reset']))
    plain.mem_write(WORK+0x100,config);off=call(plain,targets['configure'],(instance,WORK+0x100))
    if off!=t or state(plain,len(ram))!=state(u,len(ram)):raise ValueError('MMIO callback changed original configuration state/path')
    rows.append(dict(kind='tcb-configure',result=0,alternate_clock=alternate_clock,events=list(bank.events),callback_plain_state_path_equal=True,execution=t))
    next_ram=bytes(u.mem_read(0x20000000,len(ram)));bank.events=[]
    u=cpu(raw,next_ram,WORK+0xf000);bank.attach(u)
    t=call(u,targets['device-configure'],(instance,descriptor),[delay])
    if t['stop']!=delay or bank.unknown or bank.clock[0x110]!=0xa4215 or bank.clock[0x44]!=(misc|32):
        raise ValueError('Different device clock/HFRC2 frontier')
    writes=[(e['offset'],e['value']) for e in bank.events if e['operation']=='clock-write']
    if writes!=[(0x110,0xa4210),(0x44,misc|32),(0x110,0xa4214),(0x110,0xa4215)]:raise ValueError('Different device clock sequence')
    rows.append(dict(kind='device-configure-to-clock-delay',returned=False,events=list(bank.events),execution=t))
    return dict(case=case,main_sha256=sha(folder/'main.bin'),sram_sha256=sha(folder/'exports/sram-full.bin'),
                clock_entry=clock,delay_boundary=delay,instance=instance,tcb=tcb,device_descriptor=descriptor,
                parent_return=parent,targets=targets,diagnostic_basename='drv_mspi_uled_common.c',
                retained_state_request=dict(state_argument=2,retain_argument=1,callee=power_call.operands[0].imm,executed=False),samples=rows)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator
    if a.output.exists() or a.output.resolve().is_relative_to(Path(__file__).resolve().parents[1]):raise ValueError('Preserve private evidence')
    _,metadata=collect(s);spec={r['offset']:r for r in metadata if r['selected']}
    root=ET.parse(s/'apollo-dfp-research-01/apollo510.svd').getroot();clk=next(x for x in root.findall('./peripherals/peripheral') if x.findtext('name')=='CLKGEN')
    reg=next(x for x in clk.findall('./registers/register') if x.findtext('name')=='MSPIIOCLKCTRL');fields={x.findtext('name'):x for x in reg.findall('./fields/field')}
    if fields['MSPI0IOCLKSEL'].findtext('bitRange')!='[4:1]' or fields['MSPI0IOCLKEN'].findtext('bitRange')!='[0:0]':raise ValueError('Different module0 clock fields')
    enums={x.findtext('name'):int(x.findtext('value'),0) for x in fields['MSPI0IOCLKSEL'].findall('./enumeratedValues/enumeratedValue')}
    if sorted(enums.values())!=[7,8,9,10]:raise ValueError('Different module0 clock selections')
    manifest=json.loads((s/'mspi1-source-research-01/sources.json').read_text());sdk={}
    if manifest['commit']!='61b293a49db34030c545f99101f7ebf6a3050314':raise ValueError('Changed SDK commit')
    for name in ['am_hal_mspi.c','am_hal_mspi.h']:
        file=s/'mspi1-source-research-01'/name;pin=next(x for x in manifest['files'] if x['path'].endswith('/'+name))
        if sha(file)!=pin['sha256']:raise ValueError('Changed MSPI source')
        sdk[name]=sha(file)
    component=Path(__file__).resolve().parent/'renode-mspi1-config.cs'
    # Frozen analysis keeps the C# inputs alongside the verification root's tools directory.
    if not component.is_file():component=Path(__file__).resolve().parent.parent/'tools/renode-mspi1-config.cs'
    definitions=re.findall(r'new Spec\(0x([0-9a-f]+)u,0x([0-9a-f]+)u,0x([0-9a-f]+)u\)',component.read_text())
    if {int(o,16):(int(v,16),int(m,16)) for o,v,m in definitions}!={o:(r['reset'],r['mask']) for o,r in spec.items()}:raise ValueError('Existing configuration bank differs from MSPI0 metadata')
    rows=[inspect(s,c,spec) for c in ['stock24','stock23','cfw']]
    a.output.mkdir();(a.output/'inspector.py').write_bytes(Path(__file__).read_bytes())
    report=dict(passed=True,cases=rows,sdk_files=sdk,clock_enums=enums,shared_configuration_registers=len(spec),
                original_arm_scenarios=sum(len(c['samples']) for c in rows),callback_plain_equivalence_cases=3,
                engine='Unicorn M7 original ARM; synthetic function entry/stack and passive register fixtures, not native boot',
                native_main_rerun=False,model_changed=False,device_configure_returned=False,clock_delay_executed=False,
                irq_dma_pio_completion_generated=False,hardware_accessed=False,boot_verified=False,display_verified=False)
    (a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('Verified uLED MSPI0 source scenarios',report['original_arm_scenarios'],'shared config registers',len(spec))


if __name__=='__main__':main()
