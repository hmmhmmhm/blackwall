"""Audit and exercise a pinned Apollo4 RTC as a reuse candidate, not an Apollo510 replacement."""
import argparse, hashlib, json, struct, subprocess
from pathlib import Path
import xml.etree.ElementTree as ET
from run_renode_m55_probe import execute

SOURCE_SHA='dc22ac4df09190011dd70cce0e03b2eabace64246c4118d58e681a26d8623dc9'
HAL_SHA='faccd6d5aa9774f2fd71d1f19b45881d80bc6294dddf4830de53d87179df60f9'
HEADER_SHA='b6ca35dc828ef95825c0a22f06e6ca5ed558a6542dc74310515fdc350051a797'
SVD_SHA='a2390c3366450eaccc9d4531d26dc9d68488ec42de5795ee50ab45a266f28276'
LAYOUT={'RTCCTL':0,'RTCSTAT':4,'CTRLOW':0x20,'CTRUP':0x24,'ALMLOW':0x30,'ALMUP':0x34,'INTEN':0x200,'INTSTAT':0x204,'INTCLR':0x208,'INTSET':0x20c}

def checked(path, expected):
    data=path.read_bytes()
    if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('Pinned source changed: '+path.name)
    return data.decode()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();s=a.simulator.resolve();o=a.output.resolve()
    if o.exists():raise ValueError('Use a fresh evidence directory')
    research=s/'rtc-module-research-01'
    source=checked(research/'AmbiqApollo4_RTC.cs',SOURCE_SHA)
    hal=checked(research/'am_hal_rtc.c',HAL_SHA)
    header=checked(s/'upstream/hal-ambiq-61b293a/apollo510.h',HEADER_SHA)
    svd=checked(s/'apollo-dfp-research-01/apollo510.svd',SVD_SHA)
    root=ET.fromstring(svd);rtc=next(x for x in root.findall('./peripherals/peripheral') if x.findtext('name')=='RTC')
    regs={r.findtext('name'):r for r in rtc.findall('./registers/register')}
    assert {name:int(r.findtext('addressOffset'),0) for name,r in regs.items()}==LAYOUT
    assert int(rtc.findtext('baseAddress'),0)==0x40004800 and rtc.findtext('./interrupt/value')=='2'
    fields={f.findtext('name'):f for f in regs['CTRUP'].findall('./fields/field')}
    cb={e.findtext('name'):int(e.findtext('value'),0) for e in fields['CB'].findall('./enumeratedValues/enumeratedValue')}
    assert cb=={'2100':0,'2000':1}
    assert 'within 1/100 second' in fields['CTERR'].findtext('description')
    busy=regs['RTCSTAT'].find('./fields/field/description').text
    assert 'CTRUP must be written before CTRLOW' in busy
    body=hal[hal.index('am_hal_rtc_time_set(am_hal_rtc_time_t *pTime)'):];body=body[:body.index('return AM_HAL_STATUS_SUCCESS;')]
    assert body.index('RTC->CTRLOW =')<body.index('RTC->CTRUP =')
    assert 'poll_rtc_clksrc_edge_and_wait();' in hal and 'am_hal_stimer_counter_get' in hal and 'TIMERn(AM_HAL_INTERNAL_TIMER_NUM_B)' in hal
    o.mkdir(mode=0o700)
    # Rename only; preserve all behavior and the upstream MIT header.
    if source.count('AmbiqApollo4_RTC')!=2:raise ValueError('Unexpected source rename surface')
    generated=source.replace('AmbiqApollo4_RTC','BlackwallAuditedApollo4Rtc')
    (o/'engine.cs').write_text(generated)
    end=header.index('} RTC_Type;');begin=header.rfind('typedef struct {',0,end)
    layout='#include <stdint.h>\n#include <stddef.h>\n#define __IOM volatile\n#define __IM volatile const\n#define __OM volatile\n'+header[begin:end]+'} RTC_Type;\n'
    for name,offset in LAYOUT.items():layout+=f'_Static_assert(offsetof(RTC_Type,{name})=={offset},"{name}");\n'
    (o/'layout.c').write_text(layout)
    execute(['/opt/homebrew/opt/llvm@21/bin/clang','--target=arm-none-eabi','-mcpu=cortex-m55','-mthumb','-std=c11','-c',str(o/'layout.c'),'-o',str(o/'layout.o')],o,'compiler')
    # A two-byte Thumb spin guest drives virtual time; it is separate from original main evidence.
    (o/'spin.bin').write_bytes(struct.pack('<II',0x20001000,0x10009)+bytes.fromhex('fee7'))
    (o/'board.repl').write_text('cpu: CPU.CortexM @ sysbus\n    cpuType: "cortex-m55"\n    nvic: nvic\n    PerformanceInMips: 1\nnvic: IRQControllers.NVIC @ sysbus 0xe000e000\n    -> cpu@0\nflash: Memory.MappedMemory @ sysbus 0x10000\n    size: 0x1000\nsram: Memory.MappedMemory @ sysbus 0x20000000\n    size: 0x1000\nrtc: Timers.BlackwallAuditedApollo4Rtc @ sysbus 0x40004800\n    -> nvic@2\n')
    scripts={
        'setup':'''import json
from System import Console
m=monitor.Machine;rtc=m['sysbus.rtc'];checks=[];observations={}
def check(name,ok):
    if not ok:raise Exception(name)
    checks.append(name)
rtc.SetDateTime(2000,1,1,0,0,0,0)
upper2000=int(rtc.ReadDoubleWord(0x24))
observations['year2000_cb']=(upper2000>>28)&1
check('source-model-century-mismatch',observations['year2000_cb']==0)
check('initial-running',rtc.ReadDoubleWord(0)==0)
''',
        'stop':'''observations['after_30ms_low']=int(rtc.ReadDoubleWord(0x20))
check('virtual-30ms-three-ticks',observations['after_30ms_low']&255==3)
rtc.WriteDoubleWord(0,16)
frozen=int(rtc.ReadDoubleWord(0x20))
check('stopped-control',rtc.ReadDoubleWord(0)&16!=0)
''',
        'resume':'''check('stopped-50ms-stable',int(rtc.ReadDoubleWord(0x20))==frozen)
rtc.WriteDoubleWord(0,0)
''',
        'split':'''observations['after_resume_low']=int(rtc.ReadDoubleWord(0x20))
check('resumed-two-ticks',observations['after_resume_low']&255==5)
rtc.SetDateTime(2000,1,1,23,59,59,99)
splitLow=int(rtc.ReadDoubleWord(0x20))
check('split-low-before-midnight',splitLow==0x23595999)
''',
        'result':'''splitUpper=int(rtc.ReadDoubleWord(0x24))
observations['late_upper']=splitUpper
observations['late_read_error']=(splitUpper>>31)&1
check('late-upper-without-source-required-error',observations['late_read_error']==0 and splitUpper&63==2)
rtc.WriteDoubleWord(0x20c,1)
check('masked-software-status',rtc.ReadDoubleWord(0x204)==1 and not rtc.IRQ.IsSet)
rtc.WriteDoubleWord(0x200,1)
check('irq2-level-and-pending',rtc.IRQ.IsSet and m.SystemBus.ReadDoubleWord(0xe000e200)&4!=0)
rtc.WriteDoubleWord(0x208,1)
check('clear-level',not rtc.IRQ.IsSet and rtc.ReadDoubleWord(0x204)==0)
rtc.WriteDoubleWord(0,1)
rtc.WriteDoubleWord(0x20,0)
check('lower-write-busy',rtc.ReadDoubleWord(4)==1)
rtc.WriteDoubleWord(0x24,0x06000101)
check('upper-write-commits',rtc.ReadDoubleWord(4)==0)
observations['lower_then_upper_commit_year']=int(rtc.CurrentDateTime.Year)
check('hal-order-model-year',rtc.CurrentDateTime.Year==2000)
rtc.SetDateTime(2100,1,1,0,0,0,0)
observations['year2100_cb']=(int(rtc.ReadDoubleWord(0x24))>>28)&1
check('source-model-2100-century-mismatch',observations['year2100_cb']==1)
Console.WriteLine('BLACKWALL_RTC_REUSE '+json.dumps(dict(probe_completed=True,checks=checks,observations=observations,drop_in_compatible=False,hardware_validated=False,original_main_executed=False)))
'''}
    for name,script in scripts.items():compile(script,name,'exec');(o/(name+'.py')).write_text(script)
    resc='include @/work/engine.cs\nmach create "rtc-reuse-probe"\nmachine LoadPlatformDescription @/work/board.repl\nsysbus LoadBinary @/work/spin.bin 0x10000\ncpu VectorTableOffset 0x10000\ninclude @/work/setup.py\n'
    for elapsed,script in [('030','stop'),('050','resume'),('020','split'),('020','result')]:resc+='emulation RunFor "00:00:00.'+elapsed+'"\ninclude @/work/'+script+'.py\n'
    (o/'probe.resc').write_text(resc+'quit\n')
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly','sha256:e840c2b9a83dbf9be060047839aaaf6d434e7d4c52635191319afc14f4217649','--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode')
    reports=[json.loads(x.split('BLACKWALL_RTC_REUSE ',1)[1]) for x in log.splitlines() if x.startswith('BLACKWALL_RTC_REUSE ')]
    if len(reports)!=1:raise ValueError('Missing RTC reuse probe outcome; inspect preserved log')
    report=reports[0];report.update(source_sha256=SOURCE_SHA,generated_sha256=hashlib.sha256(generated.encode()).hexdigest(),hal_sha256=HAL_SHA,svd_sha256=SVD_SHA,layout=LAYOUT,source_century_values=cb,write_order_source_conflict=True,silicon_erratum_129_verified=False,scope='compiled source-renamed candidate under synthetic virtual time, not Apollo510 hardware or original-main behavior')
    (o/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

if __name__=='__main__':main()
