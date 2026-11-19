"""Exercise repeated GPU preparation/on/off epochs with existing synthetic boot fixture."""
import argparse,json,shutil
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
DRIVER='''import clr,json
from System import Console,Array,Object,UInt32
from Antmicro.Renode.Utilities import TypeManager
setter=TypeManager.Instance.GetTypeByName("Antmicro.Renode.Peripherals.Miscellaneous.BlackwallMemoryRegister").GetProperty("Value").GetSetMethod(True)
m=monitor.Machine;g=m['sysbus.guard'];b=m.SystemBus;checks=[]
def check(name,value):
    if not value:raise Exception(name)
    checks.append(name)
def w(a,v):b.WriteDoubleWord(a,v)
def read(a):return int(b.ReadDoubleWord(a))
def snapshot():return (str(g.GpuPower.Phase),bool(g.GpuPower.EpochRetired),int(g.GpuPreparation.StepsCompleted),int(g.GpuOffSequence.StepsCompleted),int(g.GpuRuntimeWakeCycles),int(g.HalStorage.Registers[0x40020080].Value))
check('synthetic-bootstrap-complete',int(b.ReadDoubleWord(0x20000000))==0x33334444 and int(b.ReadDoubleWord(0x20000004))==17 and g.GpuOffSequence.Complete and str(g.GpuPower.Phase)=='powered-off')
response=RESPONSE
check('explicit-response',int(g.GpuRuntimeWakeResponse)==response)
if response==-1:
    old=snapshot();check('default-still-refuses-rewake',not g.TryBeginGpuRuntimeWake(0x40020080,(old[-1]&~1023)|min((old[-1]&1023)+12,1023)) and old==snapshot())
else:
    prep=[(0x40020080,1023,0),(0x40020088,63,5),(0x40020380,0x20000000,0x20000000),(0x40020380,0x10000000,0x10000000),(0x40020380,0x80000000,0x80000000),(0x40020380,0x40000000,0x40000000),(0x40020344,0x3e000000,6<<25),(0x40020344,0xf800,6<<11),(0x4002034c,0x3e000000,5<<25),(0x4002034c,0xf800,5<<11),(0x40020358,0x1f00,13<<8),(0x40020354,0x3e0000,19<<17),(0x40020380,0x20000000,0),(0x40020380,0x10000000,0),(0x40020380,0x80000000,0),(0x40020380,0x40000000,0),(0x40020080,1023,0),(0x40020088,63,1)]
    off=prep[:10]+[(0x40020358,0x1f00,7<<8),(0x40020354,0x3e0000,10<<17)]+[prep[16],prep[17]]+prep[12:16]
    for cycle,trim in enumerate([0x3cd,0x3fc,0x3ff] if response==1 else [0x3cd]):
        setter.Invoke(g.HalStorage.Registers[0x40020080],Array[Object]([UInt32(0xa5a58000|trim)]))
        saved=int(g.HalStorage.Registers[0x40020080].Value);first=(saved&~1023)|min(trim+12,1023)
        old=snapshot()
        for a,v in [(0x40020380,0x20000000),(0x40020080,first^0x400),(0x40020080,first^1)]:
            check('invalid-first-no-state-'+str(cycle)+'-'+str(a)+'-'+str(v),not g.TryBeginGpuRuntimeWake(a,v) and old==snapshot())
        if cycle==0:
            misc=int(g.McuClock.MiscWord);w(0x40004044,misc&~1);before=snapshot()
            check('clock-not-ready-no-rearm',not g.TryBeginGpuRuntimeWake(0x40020080,first) and before==snapshot())
            w(0x40004044,misc)
        w(0x40020080,first)
        check('new-epoch-'+str(cycle),int(g.GpuRuntimeWakeCycles)==cycle+1 and not g.GpuPower.EpochRetired and int(g.GpuPreparation.StepsCompleted)==1 and int(g.GpuOffSequence.StepsCompleted)==0)
        check('premature-power-rejected-'+str(cycle),not g.GpuPower.TryWrite(0x40000,False) and int(g.GpuPower.RequestWord)==0)
        for index,(a,mask,field) in enumerate(prep[1:],1):
            if index==16:field=saved&1023
            before=read(a);w(a,(before&~mask)|field)
            check('prep-field-preserved-'+str(cycle)+'-'+str(index),read(a)==((before&~mask)|field))
        check('core-restored-'+str(cycle),read(0x40020080)==saved and g.GpuPreparation.Complete)
        w(0x40021004,0x40000);status=read(0x40021008)
        if response==0:
            check('stuck-off-not-ready',status==0 and str(g.GpuPower.Phase)=='stuck-off' and not g.GpuRing.TryWrite(0x400900ec,0x20010006,False))
            before=snapshot();check('stuck-off-not-rearmed',not g.TryBeginGpuRuntimeWake(0x40020080,first) and before==snapshot())
            break
        check('powered-on-'+str(cycle),status==0x40000 and str(g.GpuPower.Phase)=='on')
        before=snapshot();check('no-rearm-while-on-'+str(cycle),not g.TryBeginGpuRuntimeWake(0x40020080,first) and before==snapshot())
        check('gpu-state-requires-reinit-'+str(cycle),g.GpuRing.StepsCompleted==0 and g.GpuReset.StepsCompleted==0 and not g.GpuIdInitialized and not g.GpuRasterInitStored and g.GpuEpochIdentityReads==0 and g.GpuEpochInterruptClears==0)
        check('runtime-id-before-ring-'+str(cycle),read(0x400901ec)==0x86362000 and g.GpuEpochIdentityReads==1)
        w(0x40090148,0);check('completion-latch-initialized-'+str(cycle),read(0x40090148)==0);w(0x400900f8,0);w(0x400900ec,0x20010006);w(0x400900f0,0x20010000);w(0x400900f4,4864)
        check('identity-after-new-ring-'+str(cycle),read(0x400901ec)==0x86362000 and g.GpuEpochIdentityReads==2)
        w(0x400900e8,0);w(0x400900fc,0);w(0x40090388,1)
        check('new-gpu-epoch-initialized-'+str(cycle),g.GpuRing.StepsCompleted==3 and g.GpuReset.StepsCompleted==2 and g.GpuRasterInitStored)
        w(0x40021004,0);check('off-status-'+str(cycle),read(0x40021008)==0 and str(g.GpuPower.Phase)=='powered-off')
        before=snapshot();check('incomplete-off-no-rearm-'+str(cycle),not g.TryBeginGpuRuntimeWake(0x40020080,first) and before==snapshot())
        for index,(a,mask,field) in enumerate(off):
            if index==0:field=min((saved&1023)+12,1023)
            if index==12:field=saved&1023
            before=read(a);w(a,(before&~mask)|field)
            check('off-field-preserved-'+str(cycle)+'-'+str(index),read(a)==((before&~mask)|field))
        check('full-off-restored-'+str(cycle),g.GpuOffSequence.Complete and read(0x40020080)==saved)
    g.Reset();check('global-reset-clears-runtime',g.GpuRuntimeWakeCycles==0 and str(g.GpuPower.Phase)=='off' and g.GpuPreparation.StepsCompleted==0)
Console.WriteLine('BLACKWALL_GPU_RUNTIME_UNIT '+json.dumps(dict(passed=True,count=len(checks),checks=checks,response=response,hardware_accessed=False,scope='synthetic bootstrap and model lifecycle; not main firmware or GPU rendering')))
'''
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--response',type=int,choices=[-1,0,1],default=1);a=p.parse_args();s=a.simulator;o=a.output
    if o.exists():raise ValueError('Preserve existing evidence')
    base=s/'gpu-off-sequence-native-01/gpu-off-sequence-complete';parent=s/'imu-powersave-main-01/stock24';old=(s/'gpu-runtime-wake-research-01/base-renode-strict-mmio.cs').read_bytes();raw=(parent/'strict.cs').read_bytes();assert raw.count(old)==1
    o.mkdir(mode=0o700);(o/'strict.cs').write_bytes(raw.replace(old,(ROOT/'tools/renode-strict-mmio.cs').read_bytes()))
    board=(base/'board.repl').read_text();anchor='    gpuOffSequenceStorage: true\n';assert board.count(anchor)==1
    if a.response!=-1:board=board.replace(anchor,anchor+'    gpuRuntimeWakeResponse: '+str(a.response)+'\n')
    (o/'board.repl').write_text(board);shutil.copyfile(base/'fixture.elf',o/'fixture.elf');shutil.copyfile(base/'fixture.c',o/'fixture.c');(o/'unit.py').write_text(DRIVER.replace('RESPONSE',str(a.response)))
    resc=(base/'probe.resc').read_text().replace('include @/work/result.py','include @/work/unit.py');(o/'probe.resc').write_text(resc);shutil.copyfile(__file__,o/'verifier.py')
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount','type=bind,source='+str(o)+',target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],o,'renode',timeout=90)
    rows=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith('BLACKWALL_GPU_RUNTIME_UNIT ')];assert len(rows)==1,'Missing runtime unit result; inspect saved log'
    (o/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=rows[0]['passed'],checks=rows[0]['count'],response=a.response)))
if __name__=='__main__':main()
