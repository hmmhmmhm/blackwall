"""Original HAL polling FIFO reads in an explicitly synthetic M55 caller."""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from inspect_ambiq_target import decode
from pinned_main import load_pinned_main
from native_replay import IMAGE
from run_ambiq_glyph_m55 import make_batch_harness
from run_renode_m55_probe import execute

ROOT=Path(__file__).resolve().parents[1]
def sha(data):return hashlib.sha256(data).hexdigest()

def run(simulator,out,parse=False):
    source=simulator/'imu-clock-variation-main-01/stock24'
    raw=(source/'main.bin').read_bytes();ram=(source/'exports/sram-full.bin').read_bytes()
    _,pinned=load_pinned_main((simulator/'inputs/verified-01/stock-2.4.0.24.bin').read_bytes())
    if raw!=pinned or len(ram)!=0x380000 or sha(ram)!='9deeeb437ed26be6b00b0bc2f51f4499050c71b53718524c3d223648201be140':raise ValueError('Pinned original or complete SRAM mismatch')
    instruction=decode(raw,0x551aca,4)[0]
    literal=((instruction.address+4)&~3)+instruction.operands[1].mem.disp
    table=struct.unpack_from('<I',raw,literal-0x438000)[0]
    handle=struct.unpack_from('<I',ram,table+4*16+4-0x20000000)[0]
    if handle!=0x20040b28 or decode(raw,0x551ada,4)[0].operands[0].imm!=0x5820d8:raise ValueError('Changed original HAL caller')
    out.mkdir(mode=0o700)
    work=bytearray(0x10000);calls=[]
    for index,(reg,length,direction,target) in enumerate([(0x12,1,0,0),(0x12,2,1,0x21002000),(0x12,1,0,0),(0x12,2,1,0x21002004),(0x14,1,0,0),(0x14,32,1,0x21002010)]):
        pointer=0x21001000+index*4;struct.pack_into('<I',work,pointer-0x21000000,reg)
        descriptor=[0x69,0,0,0,length,direction,pointer,target,0x10000,0,0,0]
        address=0x21000100+index*0x40
        struct.pack_into('<12I',work,address-0x21000000,*descriptor)
        calls.append(dict(entry=0x5820d8,args=[handle,address],stack=[]))
    if parse:
        initial=bytearray(ram);device=0x20075578;ring=0x20066640
        if struct.unpack_from('<I',ram,device+24-0x20000000)[0]!=0x4c4c6d or ram[device+29-0x20000000]!=0:raise ValueError('Original callback/compression changed')
        initial[device+16-0x20000000]=16;initial[device+17-0x20000000]=0
        initial[ring-0x20000000:ring-0x20000000+2252]=bytes([0xa5])*2252
        struct.pack_into('<III',initial,ring-0x20000000,0x10203040,0,0)
        for n in range(20):initial[ring+12+112*n+4-0x20000000]=0xa0
        ram=bytes(initial)
        calls.append(dict(entry=0x552fa6,args=[device,0x21002010,2],stack=[]))
    (out/'work.bin').write_bytes(work)
    harness=make_batch_harness(out,dict(calls=calls,record_returns=True))
    strict=(simulator/'mspi0-rx-main-01/stock24/strict.cs').read_text()
    for name in ['renode-imu-identity.cs','renode-imu-raw-fifo.cs','renode-imu-fifo-threshold.cs','renode-imu-fifo-transport.cs']:strict+='\n'+(ROOT/'tools'/name).read_text()
    (out/'strict.cs').write_text(strict);(out/'fixture.cs').write_bytes((ROOT/'tools/renode-arm-function-fixture.cs').read_bytes())
    (out/'main.bin').write_bytes(raw);(out/'sram.bin').write_bytes(ram)
    (out/'board.repl').write_text('cpu: CPU.CortexM @ sysbus\n    cpuType: "cortex-m55"\n    nvic: nvic\n    PerformanceInMips: 10\nnvic: IRQControllers.NVIC @ sysbus 0xe000e000\n    systickFrequency: 1000000\nmain: Memory.MappedMemory @ sysbus 0x438000\n    size: 0x400000\nsram: Memory.MappedMemory @ sysbus 0x20000000\n    size: 0x380000\nwork: Memory.MappedMemory @ sysbus 0x21000000\n    size: 0x10000\nstop: Memory.MappedMemory @ sysbus 0x10000000\n    size: 0x1000\nfixture: Miscellaneous.BlackwallArmFunctionFixture @ sysbus 0x10001000\n    cpu: cpu\n    memoryGuard: false\n    mainLength: {length}\n    harnessLength: {harness}\npower: Miscellaneous.BlackwallPeripheralPower\n    mask: 32\n    profile: 1\n    offProfile: 0\niom: Miscellaneous.BlackwallStrictIom @ sysbus 0x40054000\n    power: power\n    module: 4\nstartup: Miscellaneous.BlackwallImuIdentity @ none\n    owner: iom\n    profile: "icm45608-whoami-only"\nraw_fifo: Miscellaneous.BlackwallImuRawFifo @ none\n    enabled: true\nfifo_transport: Miscellaneous.BlackwallImuFifoTransport @ iom 0x69\n    owner: iom\n    startupPeer: startup\n    rawFifo: raw_fifo\n'.format(length=len(raw),harness=harness['bytes']))
    setup="import json,time\nfrom System import Array,Byte,Console\nfrom System.IO import File\nfrom Antmicro.Renode.Core import EmulationManager\nm=monitor.Machine;b=m.SystemBus;cpu=m['sysbus.cpu'];f=m['sysbus.fixture'];i=m['sysbus.iom'];t=m['sysbus.iom.fifo_transport'];q=t.RawFifo\nif not i.Power.TryWrite(32,True) or i.Power.ReadStatus()!=32:raise Exception('IOM power preparation failed')\nfor offset,value in [(0x118,1),(0x11c,0x10),(0x2c0,0x23040),(0x2c4,0x69),(0x200,1)]:b.WriteDoubleWord(0x40054000+offset,value)\nfor seed in [1,20]:\n    if not q.TryEnqueueFrame(Array[Byte]([0x68]+[(seed+k)&255 for k in range(15)])):raise Exception('Cannot enqueue test frame')\nfor n in range(13):f.SeedRegister(n,0x12340000+n if 4<=n<12 else 0)\nf.SeedRegister(13,0x2100ff00);f.SeedRegister(14,0x10000001)\ncpu.FpuEnabled=True\nfor n,v in [(18,4),(19,0),(22,0),(25,0x1000000),(27,0xf00000),(28,0),(30,0),(31,0),(74,0)]:f.SeedRegister(n,v)\nf.BeginCall();f.SeedRegister(15,0x2100e001)\nEmulationManager.Instance.CurrentEmulation.StartAll();deadline=time.time()+5\nwhile not f.Stopped and time.time()<deadline:time.sleep(0.001)\nm.Pause()\nr=dict(boundary=str(f.Boundary),violations=int(f.Violations),registers=[int(cpu.GetRegister(n).RawValue) for n in range(16)],cfsr=int(b.ReadDoubleWord(0xe000ed28)),hfsr=int(b.ReadDoubleWord(0xe000ed2c)),commands=int(i.Commands),selections=int(t.Selections),chunks=int(t.ChunksRead),completed=int(t.TransactionsCompleted),packets=int(q.PacketCount),consumed=int(q.PacketsConsumed),phases=[dict(marker=int(b.ReadDoubleWord(0x2100c000+64*n)),result=int(b.ReadDoubleWord(0x2100c02c+64*n))) for n in range(6)])\nFile.WriteAllBytes('/work-output/final-work.bin',b.ReadBytes(0x21000000,0x10000))\nFile.WriteAllBytes('/work-output/final-sram.bin',b.ReadBytes(0x20000000,0x380000))\nFile.WriteAllBytes('/work-output/final-main.bin',b.ReadBytes(0x438000,MAIN_LENGTH))\nConsole.WriteLine('BLACKWALL_HAL_FIFO '+json.dumps(r))\n".replace('MAIN_LENGTH',str(len(raw))).replace('range(6)])','range('+str(len(calls))+')])')
    (out/'setup.py').write_text(setup)
    (out/'probe.resc').write_text("include @/work/strict.cs\ninclude @/work/fixture.cs\nmach create \"imu-hal-fifo\"\nmachine LoadPlatformDescription @/work/board.repl\nsysbus LoadBinary @/work/main.bin 0x438000\nsysbus LoadBinary @/work/sram.bin 0x20000000\nsysbus LoadBinary @/work/work.bin 0x21000000\npython \"exec(compile(open('/work/setup.py').read(),'/work/setup.py','exec'))\"\n")
    result=out/'result';result.mkdir(mode=0o700)
    log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={out},target=/work,readonly','--mount',f'type=bind,source={result},target=/work-output',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],out,'renode',timeout=90)
    rows=[json.loads(line.split(' ',1)[1]) for line in log.splitlines() if line.startswith('BLACKWALL_HAL_FIFO ')]
    if len(rows)!=1:raise ValueError('No final observation; inspect saved log')
    actual=rows[0];after=(result/'final-work.bin').read_bytes()
    expected=bytes([0x68]+list(range(1,16))+[0x68]+list(range(20,35)))
    checks=dict(returned=actual['boundary']=='return' and actual['violations']==0,no_cpu_fault=actual['cfsr']==actual['hfsr']==0,original_calls=actual['phases']==[dict(marker=n+1,result=0) for n in range(len(calls))],counts=after[0x2000:0x2002]==after[0x2004:0x2006]==b'\x02\x00',fifo_bytes=after[0x2010:0x2030]==expected,consumed=actual['packets']==0 and actual['consumed']==2,commands=actual['commands']==6 and actual['completed']==3,rom_unchanged=(result/'final-main.bin').read_bytes()==raw)
    if parse:
        final=(result/'final-sram.bin').read_bytes();offset=0x66640
        checks['parser_ring_index']=struct.unpack_from('<I',final,offset+8)[0]==2
        checks['parser_raw_axes']=all(final[offset+12+112*n+6:offset+12+112*n+18]==expected[n*16+1:n*16+13] for n in range(2))
        checks['parser_flags']=all(final[offset+12+112*n+4]==0xa3 for n in range(2))
        checks['parser_ring_tail_preserved']=final[offset+12+224:offset+2252]==ram[offset+12+224:offset+2252]
    report=dict(input_sram_sha256=sha((source/'exports/sram-full.bin').read_bytes()),parser_executed=parse,passed=all(checks.values()),checks=checks,actual=actual,main_sha256=sha(raw),source_sram_sha256=sha(ram),handle=handle,synthetic_caller=True,natural_main=False,normal_gaf_supported=False,transient_memory_writes_observed=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--parse',action='store_true');p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if a.output.exists() or not a.output.resolve().is_relative_to(a.simulator.resolve()) or a.output.resolve().is_relative_to(ROOT):p.error('New private simulator output required')
    run(a.simulator,a.output,a.parse)
