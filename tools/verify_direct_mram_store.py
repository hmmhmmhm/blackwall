"""Execute one synthetic M55 STR against virtual MRAM; no stock binary or hardware."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
from native_replay import IMAGE
from run_renode_m55_probe import execute

ROOT=Path(__file__).resolve().parents[1]
PRIVATE=Path.home()/'Library/Application Support/Blackwall'


def run(output,target,store="word"):
    output=Path(output).resolve()
    if output.exists() or not output.is_relative_to(PRIVATE) or target not in [0x410000,0x438000,0x438010,0x7fe000] or store not in ('byte','half','word'):raise ValueError('Fresh private output and reviewed target required')
    output.mkdir(mode=0o700,parents=True);(output/'exports').mkdir(mode=0o700)
    source=(ROOT/'tools/renode-recovery-writer-fixture.cs').read_bytes();(output/'fixture.cs').write_bytes(source)
    (output/'mram-before.bin').write_bytes(b'\xa5'*0x400000)
    code=bytes.fromhex('01485521'+dict(byte='0170',half='0180',word='0160')[store]+'fee7')+struct.pack('<I',target);(output/'guest.bin').write_bytes(code)
    (output/'board.repl').write_text('cpu: CPU.CortexM @ sysbus\n    cpuType: "cortex-m55"\n    nvic: nvic\nnvic: IRQControllers.NVIC @ sysbus 0xe000e000\n    systickFrequency: 1000000\nmram: Miscellaneous.BlackwallProtectedMram @ sysbus 0x400000\n    size: 0x400000\nsram: Memory.MappedMemory @ sysbus 0x20000000\n    size: 0x80000\nuart: Miscellaneous.BlackwallRecoveryWriterFixture @ sysbus 0x4003b000\n    cpu: cpu\n    nvic: nvic\n    initialTick: 0\n    returnPc: 0x435000\n    writerPc: 0x20010000\n    recvPc: 0x435002\n    sendPc: 0x435004\n    destination: 0x438010\n    length: 512\n')
    runtime='''import time,json
from System import Array,Byte
from System.IO import File
from Antmicro.Renode.Core import EmulationManager
m=monitor.Machine;cpu=m['sysbus.cpu'];b=m.SystemBus;u=m['sysbus.uart']
b.WriteBytes(File.ReadAllBytes('/work/mram-before.bin'),0x400000)
m['sysbus.mram'].Arm()
b.WriteBytes(File.ReadAllBytes('/work/guest.bin'),0x20000100)
u.SeedRegister(13,0x2007f000);u.SeedRegister(15,0x20000101)
EmulationManager.Instance.CurrentEmulation.StartAll();deadline=time.time()+5
while not cpu.IsHalted and not m.IsPaused and u.Violations==0 and time.time()<deadline:time.sleep(0.001)
m.Pause()
File.WriteAllBytes('/work-output/mram-after.bin',b.ReadBytes(0x400000,0x400000,True))
File.WriteAllText('/work-output/result.json',json.dumps(dict(pc=int(cpu.PC.RawValue),violations=int(u.Violations),failure=str(u.Failure),failure_address=int(u.FailureAddress),programmed_bytes=int(u.ProgrammedBytes),rom_calls=int(u.RomCalls),rejected_writes=int(m['sysbus.mram'].RejectedWrites),cfsr=int(b.ReadDoubleWord(0xe000ed28)),hfsr=int(b.ReadDoubleWord(0xe000ed2c)))))
'''
    (output/'run.py').write_text(runtime);(output/'probe.resc').write_text('include @/work/fixture.cs\nmach create "direct-mram-str"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/run.py\nquit\n')
    execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={output},target=/work,readonly','--mount',f'type=bind,source={output/"exports"},target=/work-output',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],output,'native',timeout=45,stream=True)
    d=json.loads((output/'exports/result.json').read_text());data=(output/'exports/mram-after.bin').read_bytes()
    d.update(whole_mram_unchanged=data==b'\xa5'*0x400000,changed_bytes=sum(x!=0xa5 for x in data),target=target,store=store,after_sha256=hashlib.sha256(data).hexdigest(),scope='Synthetic M55 STR, not original firmware execution',hardware_accessed=False)
    (output/'report.json').write_text(json.dumps(d,indent=2)+'\n');(output/'exports/mram-after.bin').unlink();(output/'mram-before.bin').unlink();print(json.dumps(d),flush=True)
    if not (d['whole_mram_unchanged'] and d['rejected_writes']==1 and d['violations']==1 and d['programmed_bytes']==0 and d['rom_calls']==0):raise ValueError('Direct store was not blocked atomically')
    return d


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);p.add_argument('--target',type=lambda s:int(s,0),default=0x410000);p.add_argument('--store',choices=['byte','half','word'],default='word');a=p.parse_args();run(a.output,a.target,a.store)

if __name__=='__main__':main()
