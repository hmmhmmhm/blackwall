"""Execute stock24 main write/compare functions with a synthetic diagnostic caller."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import shutil
from run_renode_m55_probe import execute
from native_replay import IMAGE
from verify_rom_power_lifecycle import block
ROOT=Path(__file__).resolve().parents[1]
PRIVATE=Path.home()/'Library/Application Support/Blackwall'
ENTRIES={'adapter':0x4f5864,'buffer':0x488d34,'callback':0x5c69f8}
FAULTS=('success','rom-error','readback-corrupt','rom-unready','misaligned')


def validate_case(entry,fault,verification='memcmp',*,boot_restore=False):
    if entry not in ENTRIES or fault not in FAULTS:raise ValueError('Reviewed main entry and diagnostic fault required')
    if verification not in ('memcmp','ota') or verification=='ota' and entry!='callback':raise ValueError('Explicit callback OTA verifier required')
    if type(boot_restore) is not bool or boot_restore and (entry!='callback' or verification!='ota' or fault not in ('success','rom-error','readback-corrupt')):raise ValueError('Full boot diagnostic requires callback/OTA reviewed fault')


def sha(data):return hashlib.sha256(data).hexdigest()


def validate_delay_bytes(observed,literal):
    expected=bytes.fromhex('0138fdd17047')
    if len(observed)!=32 or observed[:6]!=expected or literal!=expected:
        raise ValueError('Observed original ITCM delay and stock main literal required')
    return expected


def class_source(source,name):
    start=source.index('    public sealed class '+name)
    brace=source.index('{',start);depth=1;end=brace+1
    while depth:
        depth += (source[end]=='{')-(source[end]=='}');end+=1
    return 'namespace Antmicro.Renode.Peripherals.Miscellaneous\n{\n'+source[start:end]+'\n}\n'


def run(output,entry='adapter',fault='success',*,chip_profile=False,delay_profile=False,verification='memcmp',boot_restore=False):
    validate_case(entry,fault,verification,boot_restore=boot_restore)
    if type(chip_profile) is not bool:raise ValueError('Explicit boolean chip profile required')
    if type(delay_profile) is not bool or delay_profile and not chip_profile:raise ValueError('Delay profile requires existing chip profile')
    if verification=='ota' and not delay_profile:raise ValueError('OTA verifier requires reviewed delay profile')
    output=Path(output).resolve()
    if output.exists() or not output.is_relative_to(PRIVATE) or output.is_relative_to(ROOT):raise ValueError('Fresh private output required')
    initial=PRIVATE/'simulator/full-main-restore-bw564-02/vector/exports/final-mram.bin';ram=PRIVATE/'simulator/full-main-restored-screen-bw564-02/exports/main-state-sram.bin'
    mram=initial.read_bytes();sram=ram.read_bytes()
    if sha(mram)!='3e5f340ef2ae006f60bbd476670a38f0ff1a45fbedff805b481a7cbfd4d9ede4' or sha(sram)!='95db71c2f3961db017dd8f8cef708768a331fb1a4e478990c03ab6e11ab5b268':raise ValueError('Pinned original native snapshots required')
    if sha(mram[0x38000:0x38000+3700068])!='df8cfddf3bd29a8351129a8364a8e0dafb347ffc7bfcbca5b52fdd973a7cce4a':raise ValueError('Stock24 main required')
    original=PRIVATE/'simulator/boot-self-restore-bw567-01/virtual-original-mram.bin';backup=original.read_bytes();data=backup[0x10000:0x37000] if boot_restore else backup[0x34000:0x35000]
    if boot_restore and (len(backup)!=0x400000 or backup[:0x10000]!=mram[:0x10000] or backup[0x37000:]!=mram[0x37000:] or sha(backup[0x10000:0x10000+149773])!='ecb91896234392e2b98ec80b1ac3ebf4aa27726d3cbed10927edf0b44d83d665' or any(backup[0x10000+149773:0x37000])):raise ValueError('Declared virtual original stock inventory required')
    if data==mram[0x34000:0x35000]:raise ValueError('A distinguishing target page is required')
    output.mkdir(mode=0o700,parents=True);(output/'exports').mkdir(mode=0o700);(output/'payload.bin').write_bytes(data)
    strict=(ROOT/'tools/renode-strict-mmio.cs').read_text();pos=strict.index('    public sealed class BlackwallChipIdentity');start=strict.rfind('namespace Antmicro.',0,pos);end=strict.index('\nnamespace Antmicro.',pos);chip_source=strict[start:end]
    source=(ROOT/'tools/renode-recovery-writer-fixture.cs').read_text()+block(strict)+chip_source+class_source(strict,'BlackwallHalStorage')+class_source(strict,'BlackwallMcuClock')+(ROOT/'tools/renode-stock-main-mram-probe.cs').read_text()
    (output/'model.cs').write_text(source);shutil.copy2(__file__,output/'runner-source.py')
    destination=0x410000 if boot_restore else 0x434004 if fault=='misaligned' else 0x434000
    args=(0x12344321,0x20240000,destination,1024) if entry=='adapter' else (destination,0x20240000,4096,0)
    asm='.syntax unified\n.thumb\n.cpu cortex-m55\n.global _start\n.global done\n_start:\n'+''.join(f' ldr r{i}, ={v:#x}\n' for i,v in enumerate(args))+f' ldr r4, ={ENTRIES[entry]|1:#x}\n blx r4\n mov r5, r0\n ldr r0, =0x20240000\n ldr r1, ={destination:#x}\n ldr r2, =4096\n ldr r4, =0x480dc9\n blx r4\n mov r6, r0\ndone:\n b done\n .ltorg\n'
    if verification=='ota':
        asm=asm.replace(f' ldr r0, =0x20240000\n ldr r1, ={destination:#x}',f' ldr r0, ={destination:#x}\n ldr r1, =0x20240000').replace(' ldr r4, =0x480dc9',' ldr r3, =0x20000394\n ldr r4, =0x446ab5')
    if boot_restore:
        asm='''.syntax unified
.thumb
.cpu cortex-m55
.global _start
.global done
.global page_verified
_start:
 ldr r8, =0x410000
 ldr r9, =0x20240000
 ldr r10, =0x437000
 movs r7, #0
page_loop:
 mov r0, r8
 mov r1, r9
 ldr r2, =4096
 ldr r4, =0x5c69f9
 blx r4
 mov r5, r0
 mov r0, r8
 mov r1, r9
 ldr r2, =4096
 ldr r3, =0x20000394
 ldr r4, =0x446ab5
 blx r4
page_verified:
 mov r6, r0
 cmp r0, #0
 bne done
 adds r7, #1
 add.w r8, r8, #4096
 add.w r9, r9, #4096
 cmp r8, r10
 bne page_loop
done:
 b done
 .ltorg
'''
    (output/'caller.S').write_text(asm);(output/'caller.ld').write_text('ENTRY(_start)\nSECTIONS { . = 0x20010000; .text : { *(.text*) } }\n')
    compiler='/opt/homebrew/opt/llvm@21/bin/clang';lld='/opt/homebrew/opt/lld@21/bin/ld.lld';objcopy='/opt/homebrew/opt/llvm@21/bin/llvm-objcopy';nm='/opt/homebrew/opt/llvm@21/bin/llvm-nm'
    execute([compiler,'--target=arm-none-eabi','-mcpu=cortex-m55','-mthumb','-nostdlib','-fuse-ld='+lld,'-Wl,-T,'+str(output/'caller.ld'),str(output/'caller.S'),'-o',str(output/'caller.elf')],output,'compiler')
    execute([objcopy,'-O','binary',str(output/'caller.elf'),str(output/'caller.bin')],output,'objcopy')
    symbols=execute([nm,str(output/'caller.elf')],output,'symbols');done=int(next(line.split()[0] for line in symbols.splitlines() if line.split()[-1]=='done'),16)
    (output/'board.repl').write_text('cpu: CPU.CortexM @ sysbus\n    cpuType: "cortex-m55"\n    nvic: nvic\nnvic: IRQControllers.NVIC @ sysbus 0xe000e000\n    systickFrequency: 1000000\nmram: Miscellaneous.BlackwallProtectedMram @ sysbus 0x400000\n    size: 0x400000\nsram: Memory.MappedMemory @ sysbus 0x20000000\n    size: 0x380000\nrom: Memory.MappedMemory @ sysbus 0x0200f000\n    size: 0x1000\ncontrol: Miscellaneous.BlackwallRecoveryMramControl @ sysbus 0x40014000\npower: Miscellaneous.BlackwallStockMainMramProbe @ sysbus 0x40020000\n    cpu: cpu\n    romStatus: '+('7' if fault=='rom-error' else '0')+'\n    corruptReadback: '+str(fault=='readback-corrupt').lower()+'\n    powerReady: '+str(fault!='rom-unready').lower()+'\n    chipProfile: '+str(chip_profile).lower()+'\n    delayProfile: '+str(delay_profile).lower()+'\n    bootRestore: '+str(boot_restore).lower()+'\n'+('chip_id: Miscellaneous.BlackwallStockMainChipIdentity @ sysbus 0xe00fefe0\n    owner: power\n' if chip_profile else '')+('itcm: Memory.MappedMemory @ sysbus 0x0\n    size: 0x400\n' if delay_profile else ''))
    if delay_profile:
        observed_path=PRIVATE/'simulator/gaf-delay-clock-native-02/exports/delay-path.json'
        observed=bytes(json.loads(observed_path.read_text())['itcm_bytes'])
        (output/'delay.bin').write_bytes(validate_delay_bytes(observed,mram[0x7bf54f-0x400000:0x7bf54f-0x400000+6]))
    runtime='''import json,time
from System.IO import File
from Antmicro.Renode.Core import EmulationManager
m=monitor.Machine;cpu=m['sysbus.cpu'];p=m['sysbus.power'];b=m.SystemBus
p.Start(0x20010000,DONE)
initial_ccr=int(b.ReadDoubleWord(0xe000ed14));initial_ipsr=int(cpu.GetRegister(25).RawValue)&511;initial_cpacr=int(cpu.GetRegister(27).RawValue)
EmulationManager.Instance.CurrentEmulation.StartAll();deadline=time.time()+5
while not cpu.IsHalted and not m.IsPaused and time.time()<deadline:time.sleep(0.001)
m.Pause()
File.WriteAllBytes('/work-output/final-mram.bin',b.ReadBytes(0x400000,0x400000,True))
answer=dict(pages_verified=int(cpu.GetRegister(7).RawValue) if p.BootRestore else None,rom_requests=[[int(v) for v in row] for row in p.RomRequests],verification_rows=[[int(v) for v in row] for row in p.VerificationRows],verifier_compared=bool(p.VerifierCompared),verifier_compare=int(p.VerifierCompare),initial_ccr=initial_ccr,final_ccr=int(b.ReadDoubleWord(0xe000ed14)),clock_reads=0 if p.Clock is None else int(p.Clock.ModeReads),delay_calls=int(p.DelayCalls),delay_returns=int(p.DelayReturns),initial_cpacr=initial_cpacr,cpacr=int(cpu.GetRegister(27).RawValue),info_returned=bool(p.InfoReturned),info_return=int(p.InfoReturn),info_mram_size=int(p.InfoMramSize),initial_ipsr=initial_ipsr,ipsr=int(cpu.GetRegister(25).RawValue)&511,stack=int(cpu.GetRegister(13).RawValue),completed=bool(p.Completed),rom_unready_boundary=bool(p.RomUnreadyBoundary),rom_attempts=int(p.RomAttempts),rom_calls=int(p.RomCalls),programmed_bytes=int(p.ProgrammedBytes),rom_primask=int(p.RomPrimask),power_return=int(p.PowerReturn),power_returned=bool(p.PowerReturned),initial_primask=int(p.InitialPrimask),initial_control=int(p.InitialControl),primask=int(cpu.GetRegister(28).RawValue),control=int(cpu.GetRegister(18).RawValue),pc=int(cpu.PC.RawValue),api_return=int(cpu.GetRegister(5).RawValue),compare_return=int(cpu.GetRegister(6).RawValue),cfsr=int(b.ReadDoubleWord(0xe000ed28)),hfsr=int(b.ReadDoubleWord(0xe000ed2c)),violations=int(p.Violations),failure=str(p.Failure),failure_address=int(p.FailureAddress),hits=dict((hex(int(x.Key)),int(x.Value)) for x in p.Hits),rom_request=int(p.Power.Registers[0x40021014].Value),rom_status=int(p.Power.Registers[0x40021018].Value),rom_enables=int(p.Power.RomEnables),rom_disables=int(p.Power.RomDisables)-1)
File.WriteAllText('/work-output/result.json',json.dumps(answer))
'''.replace('DONE',hex(done))
    if boot_restore:
        verified=int(next(line.split()[0] for line in symbols.splitlines() if line.split()[-1]=='page_verified'),16)
        runtime=runtime.replace('initial_ccr=int(',f'p.ObserveVerified({verified})\ninitial_ccr=int(').replace('answer=dict(',"File.WriteAllBytes('/work-output/verified-pages.bin',p.ReadbackBytes.ToArray())\nanswer=dict(")
    if verification=='ota':runtime=runtime.replace("answer=dict(","File.WriteAllBytes('/work-output/ota-readback.bin',b.ReadBytes(0x203214a0,4096,True))\nanswer=dict(")
    (output/'run.py').write_text(runtime);(output/'probe.resc').write_text('include @/work/model.cs\nmach create "stock-main-mram-diagnostic"\nmachine LoadPlatformDescription @/work/board.repl\nsysbus LoadBinary @/input-mram.bin 0x400000\nsysbus LoadBinary @/input-sram.bin 0x20000000\nsysbus LoadBinary @/work/payload.bin 0x20240000\nsysbus LoadBinary @/work/caller.bin 0x20010000\n'+('sysbus LoadBinary @/work/delay.bin 0x40\n' if delay_profile else '')+'include @/work/run.py\nquit\n')
    manifest=dict(boot_restore=boot_restore,virtual_original=dict(path=str(original),sha256=sha(backup)),verification=verification,delay_profile=delay_profile,delay_contract=None if not delay_profile else dict(observation=str(observed_path),observation_sha256=sha(observed_path.read_bytes()),code_sha256=sha((output/'delay.bin').read_bytes()),code_address=0x40,literal_address=0x7bf54f,clock_mode='existing BlackwallMcuClock hp22',synthetic_initialized_itcm=True,natural_copy_executed=False),extension_profile='FPU enabled and CPACR=f00000, matching established initialized-main profile; CONTROL/FPCA not forced',entry=entry,fault=fault,chip_profile=chip_profile,initial_mram=dict(path=str(initial),sha256=sha(mram)),initial_sram=dict(path=str(ram),sha256=sha(sram)),payload_sha256=sha(data),destination=destination,source=0x20240000,bytes=len(data),components={n:sha((output/n).read_bytes()) for n in ('model.cs','caller.S','caller.ld','caller.bin','board.repl','run.py','probe.resc','runner-source.py')},hardware_accessed=False,natural_ota_executed=False)
    if delay_profile:manifest['components']['delay.bin']=sha((output/'delay.bin').read_bytes())
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={output},target=/work,readonly','--mount',f'type=bind,source={initial},target=/input-mram.bin,readonly','--mount',f'type=bind,source={ram},target=/input-sram.bin,readonly','--mount',f'type=bind,source={output/"exports"},target=/work-output',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],output,'native',timeout=45,stream=True)
    r=json.loads((output/'exports/result.json').read_text());final=(output/'exports/final-mram.bin').read_bytes();r.update(entry=entry,fault=fault,verification=verification,chip_profile=chip_profile,delay_profile=delay_profile,final_mram_sha256=sha(final),whole_mram_unchanged=final==mram,page_equals_payload=final[0x34000:0x35000]==data,other_mram_unchanged=final[:0x34000]==mram[:0x34000] and final[0x35000:]==mram[0x35000:],hardware_accessed=False,rom_programming_modeled=True,natural_ota_executed=False)
    if boot_restore:
        checks=dict(whole_mram_expected=final==backup,all_pages=r['completed'] and r['pages_verified']==39 and len(r['verification_rows'])==39 and all(row[2:]==[0,0,0] for row in r['verification_rows']),clean=r['cfsr']==r['hfsr']==r['violations']==0 and r['primask']==0 and r['stack']==0x2007f000,rom_calls=r['rom_calls']==39 and r['programmed_bytes']==159744,actual_readback=(output/'exports/verified-pages.bin').read_bytes()==data)
        r.pop('page_equals_payload');r['boot_region_equals_payload']=final[0x10000:0x37000]==data;r['other_mram_unchanged']=final[:0x10000]==mram[:0x10000] and final[0x37000:]==mram[0x37000:]
        r.update(boot_restore=True,destination=destination,checks=checks,passed=all(checks.values()),full_stock_bytes=final==backup,virtual_original_sha256=sha(backup))
    (output/'report.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r),flush=True);return r


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);p.add_argument('--entry',choices=ENTRIES,default='adapter');p.add_argument('--fault',choices=FAULTS,default='success');p.add_argument('--chip-profile',action='store_true');p.add_argument('--delay-profile',action='store_true');p.add_argument('--verification',choices=('memcmp','ota'),default='memcmp');p.add_argument('--boot-restore',action='store_true');a=p.parse_args();run(a.output,a.entry,a.fault,chip_profile=a.chip_profile,delay_profile=a.delay_profile,verification=a.verification,boot_restore=a.boot_restore)
if __name__=='__main__':main()
