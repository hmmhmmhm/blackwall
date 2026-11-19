"""Pinned virtual boot scenarios; no serial, BLE, hardware, or installation API."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from run_original_boot_screen import (PROFILE, PRIVATE, checked_asset, checked_path,
    read_json, validate_profile, validate_runtime, write_json, sha)
from run_renode_m55_probe import execute

CASES=('pending-marker','pending-rom-ready','pending-rom-stuck','corrupt-marker','invalid-sp','invalid-sp-diagnostic','sp-bit29-outside','invalid-reset','patched-silent','patched-diagnostic')
PINS={'boot':'ecb91896234392e2b98ec80b1ac3ebf4aa27726d3cbed10927edf0b44d83d665',
      'main':'df8cfddf3bd29a8351129a8364a8e0dafb347ffc7bfcbca5b52fdd973a7cce4a',
      'patched':'5ac1b02d337b57e0d25886a06296df2d5932af1f31168c416e64b50c5417a91d'}
GUARDS=('rstgen','guard','wdt','guard_high','ppb_guard','iom2','iom4','iom5','iom6','iom7','guard_iom2_tail','guard_iom4_tail','guard_iom5_tail','guard_iom6_tail','guard_iom7_tail','xip_guard','guard_mram_tail')


def require_case(case):
    if case not in CASES:raise ValueError('Unknown boot scenario')


def check_image(data,kind):
    if kind not in PINS or hashlib.sha256(data).hexdigest()!=PINS[kind]:
        raise ValueError('Unreviewed boot validation asset')


def mutate_main(data,case):
    require_case(case)
    result=bytearray(data)
    if len(result)<8:raise ValueError('Main vector missing')
    if case in ('invalid-sp','invalid-sp-diagnostic'):struct.pack_into('<I',result,0,0xdead0000)
    if case=='sp-bit29-outside':struct.pack_into('<I',result,0,0xa007fb00)
    if case=='invalid-reset':struct.pack_into('<I',result,4,0x90000001)
    return bytes(result)


def classify(v):
    if v.get('unsupported_rom_fetch') is True and v.get('pc')==0x0200ff20:return 'unsupported-rom'
    if v.get('events_dropped',0):return 'observation-incomplete'
    if v['policy'] or v.get('system_control_violations',0) or any(g['accesses'] for g in v['guards']):return 'unsupported-model'
    if v['cfsr'] or v['hfsr']:return 'cpu-fault'
    if v['main']:return 'main-entered'
    if v['limit']:return 'timeout'
    if v['handoff']:return 'handoff-only'
    return 'stopped-unclassified'


def recovery_facts(result):
    points={p['label']:p['hits'] for p in result['points']}
    return dict(patched_manager_entered=points.get('patched-manager',0)>0,
                worker_entered=points.get('patched-worker',0)>0,
                recovery_verified=False,uart_authentication_verified=False)


def runtime(boot_length,*,capture_rom_request=False):
    if boot_length not in (149773,159744):raise ValueError('Unreviewed boot size')
    if type(capture_rom_request) is not bool:raise ValueError('Explicit ROM observation option required')
    source='''import json,time,clr
from System.IO import File
from Antmicro.Renode.Utilities import TypeManager
from Antmicro.Renode.Core import EmulationManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallMemoryPolicy').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallMemoryPolicy,BlackwallSystemControl,BlackwallExecutionObserver
m=monitor.Machine;cpu=m['sysbus.cpu'];bus=m.SystemBus
policy=BlackwallMemoryPolicy(m,cpu,m['sysbus.main'],m['sysbus.itcm'],3700068)
policy.BindBootImage(m['sysbus.boot'],BOOT_LENGTH)
policy.Attach()
control=BlackwallSystemControl(m,cpu,m['sysbus.nvic'],True,True,True);control.Attach()
m['sysbus.guard'].Mspi1Config.AttachRetentionPower(m['sysbus.guard'].Mspi1Power)
observer=BlackwallExecutionObserver(cpu,128)
for label,address in [('boot-reset',0x432cb2),('boot-manager',0x42e650),('marker-load',0x42e582),('stock-handoff',0x42dfe8),('main-reset',0x5fbe3e),('patched-manager',0x4354b8),('patched-worker',WORKER_PC)]:observer.AddPoint(label,address)
for label in ('boot-reset','stock-handoff','main-reset'):observer.CaptureCpuContext(label)
start=int(m.ElapsedVirtualTime.TimeElapsed.Ticks);deadline=time.time()+150
EmulationManager.Instance.CurrentEmulation.StartAll()
def main_hit():return any(str(p.Label)=='main-reset' and int(p.Hits)>0 for p in observer.Points)
while not cpu.IsHalted and not m.IsPaused and not main_hit() and time.time()<deadline and int(m.ElapsedVirtualTime.TimeElapsed.Ticks)-start<8000000000:time.sleep(0.005)
limit=time.time()>=deadline or int(m.ElapsedVirtualTime.TimeElapsed.Ticks)-start>=8000000000
m.Pause()
points=[dict(label=str(p.Label),address=int(p.Address),hits=int(p.Hits),first=int(p.FirstSequence)) for p in observer.Points]
result=dict(pc=int(cpu.PC.RawValue),sp=int(cpu.GetRegister(13).RawValue),registers=[int(cpu.GetRegister(i).RawValue) for i in range(16)],instructions=int(cpu.ExecutedInstructions),ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks),halted=bool(cpu.IsHalted),limit=bool(limit),policy=int(policy.Violations),policy_address=int(policy.LastAddress),policy_operation=str(policy.LastOperation),policy_pc=int(policy.LastPC),system_control_violations=int(control.Violations),cfsr=int(bus.ReadDoubleWord(0xe000ed28)),hfsr=int(bus.ReadDoubleWord(0xe000ed2c)),points=points,events_dropped=int(observer.DroppedEvents),guards=[])
for name in GUARD_NAMES:
 g=m['sysbus.'+name];result['guards'].append(dict(name=name,accesses=int(g.AccessCount),address=int(g.LastAddress),width=int(g.LastWidth),operation=str(g.LastOperation),value=int(g.LastValue)))
File.WriteAllText('/work-output/result.json',json.dumps(result))
g=m['sysbus.guard']
def power(v):return dict(mask=int(v.Mask),request=int(v.RequestWord),status=int(v.StatusWord),phase=str(v.Phase))
result['power_owners']=dict(uarts=[dict(power(p.Value),module=int(p.Key),quiescent=bool(g.Uarts[p.Key].Quiescent)) for p in g.UartPowers],ioms=[dict(power(p.Value),module=int(p.Key)) for p in g.IomPowers],extras=dict((name,power(getattr(g,name))) for name in ('Mspi0Power','Mspi1Power','OtpPower','CryptoPower')),gpu=dict(request=int(g.GpuPower.RequestWord),status=int(g.GpuPower.StatusWord)),adc=dict(request=int(g.AdcPower.RequestWord),status=int(g.AdcPower.StatusWord)))
result['snapshots']=[dict(label=str(p.Label),address=int(p.Snapshot.Address),words=[int(x) for x in p.Snapshot.Words]) for p in observer.Points if p.Snapshot is not None]
result['contexts']=[]
for point in observer.Points:
 c=point.Context
 if c is not None:result['contexts'].append(dict(label=str(point.Label),pc=int(c.PC),sp=int(c.SP),msp=int(c.MSP),psp=int(c.PSP),control=int(c.Control),vtor=int(c.VectorTableOffset)))
result['events']=[dict(sequence=int(p.Sequence),label=str(p.Label),pc=int(p.PC),r0=int(p.R0),r2=int(p.R2)) for p in observer.Events]
for name,address,length in [('boot',0x410000,BOOT_LENGTH),('main',0x438000,3700068)]:File.WriteAllBytes('/work-output/guest-'+name+'.bin',bus.ReadBytes(address,length,True))
File.WriteAllText('/work-output/result.json',json.dumps(result))
'''.replace('BOOT_LENGTH',str(boot_length)).replace('WORKER_PC','0x4352a0').replace('GUARD_NAMES',repr(GUARDS))
    if capture_rom_request:
        source+='''request=dict(seen=int(cpu.PC.RawValue)==0x0200ff20,pc=int(cpu.PC.RawValue),registers=[int(cpu.GetRegister(i).RawValue) for i in range(16)],primask=int(cpu.GetRegister(28).RawValue),hardware_accessed=False,rom_executed=False,observation_after_machine_pause=True)
if request['seen']:
 request['words']=int(bus.ReadDoubleWord(request['registers'][13]))
 request['source']=request['registers'][2]
 request['destination']=0x400000+request['registers'][3]*4
 request['power_status']=int(bus.ReadDoubleWord(0x40021018))
 bounded=request['words']==4 and 0x20000000<=request['source']<=0x20380000-16
 request['source_capture_bounded']=bounded
 if bounded:request['source_bytes']=[int(x) for x in bus.ReadBytes(request['source'],16,True)]
File.WriteAllText('/work-output/rom-request.json',json.dumps(request))
'''
    return source


def derive(case,out,private=PRIVATE,*,capture_rom_request=False):
    require_case(case);private=Path(private).resolve();out=Path(out).resolve()
    if capture_rom_request and case not in ('pending-rom-ready','pending-rom-stuck'):raise ValueError('ROM capture requires bounded pending-ROM case')
    if out.exists() or not out.is_relative_to(private) or out.is_relative_to(ROOT):raise ValueError('Fresh private output required')
    profile=read_json(PROFILE);validate_profile(profile)
    assets={k:checked_asset(private,v) for k,v in profile['assets'].items()}
    candidate=private/'recovery/private-boot-24-candidate-01'
    boot=assets['boot'] if not case.startswith('patched-') else candidate/'source/build/bootloader.bin'
    check_image(boot.read_bytes(),'patched' if case.startswith('patched-') else 'boot')
    main=assets['main'].read_bytes();check_image(main,'main');main=mutate_main(main,case)
    sources={}
    for name,spec in profile['components'].items():
        p=checked_path(ROOT if spec['origin']=='repo' else private,spec['path'])
        if sha(p)!=spec['sha256']:raise ValueError('Frozen component changed: '+name)
        sources[name]=p.read_bytes()
    board=sources['board.repl']
    if case in ('pending-marker','pending-rom-ready','pending-rom-stuck','corrupt-marker'):
        if board.count(b'    profile: "cleared"')!=1:raise ValueError('Marker input not unique')
        board=board.replace(b'    profile: "cleared"',b'    profile: "pending"')
    strict=sources['strict.cs']
    if case=='corrupt-marker':
        token=b'value=Profile=="cleared"?0xffffffffu:0x55555555u'
        if strict.count(token)!=1:raise ValueError('Marker value source not unique')
        strict=strict.replace(token,b'value=Profile=="cleared"?0xffffffffu:0x55555554u')
    if case in ('pending-rom-ready','pending-rom-stuck'):
        from verify_rom_power_lifecycle import block
        old=block(strict.decode())
        if hashlib.sha256(old.encode()).hexdigest()!='4370e69e585b35b5fa26104703b34830b0f8438e9e6248f89d8a4fd209453764':
            raise ValueError('Unreviewed legacy ROM memory model')
        new=block((ROOT/'tools/renode-strict-mmio.cs').read_text())
        response=1 if case=='pending-rom-ready' else 0
        text=strict.decode().replace(old,new)
        if text.count('new BlackwallMemoryStartup()')!=1:raise ValueError('ROM model owner not unique')
        strict=text.replace('new BlackwallMemoryStartup()',f'new BlackwallMemoryStartup({response})').encode()
    source=runtime(boot.stat().st_size,capture_rom_request=capture_rom_request)
    meta=read_json(candidate/'source/build/patch.json')
    worker=meta['base']+meta['functions']['uart2_worker']['offset']
    source=source.replace('0x4352a0',hex(worker))
    if case=='patched-diagnostic':
        extra="""observer.CaptureSram(m,'patched-manager',0x20000494,6)
for label,address in [('pre-callback-check',0x4354f6),('fallback',0x435500),('wake-path',0x43550c),('wake-return',0x43552a),('create-return',0x435570)]:observer.AddPoint(label,address)
observer.CaptureSram(m,'pre-callback-check',0x20026e44,2)
"""
        source=source.replace('start=int(m.ElapsedVirtualTime',extra+'start=int(m.ElapsedVirtualTime')
    if case in ('invalid-sp-diagnostic','sp-bit29-outside'):
        extra="""for label,address in [('sp-predicate',0x42e400),('sp-accepted',0x42e406),('sp-rejected-target',0x42e1f6)]:observer.AddPoint(label,address)
"""
        source=source.replace('start=int(m.ElapsedVirtualTime',extra+'start=int(m.ElapsedVirtualTime')
    validate_runtime(source)
    out.mkdir(parents=True,mode=0o700);(out/'exports').mkdir(mode=0o700)
    for name,data in [('strict.cs',strict),('board.repl',board),('main-fixture.bin',main)]:
        (out/name).write_bytes(data);(out/name).chmod(0o600)
    (out/'run.py').write_text(source)
    script=sources['probe.resc'].decode()
    script=script.replace('include @/work/input-delay.cs\n','').replace('include @/work/screen-observer.cs\n','').replace('@/reference/main.bin','@/work/main-fixture.bin')
    (out/'probe.resc').write_text(script)
    shutil.copy2(__file__,out/'runner-source.py')
    manifest=dict(schema=1,case=case,capture_rom_request=capture_rom_request,profile_sha256=sha(PROFILE),boot=dict(path=str(boot),sha256=sha(boot),bytes=boot.stat().st_size),main=dict(canonical_sha256=PINS['main'],fixture_sha256=hashlib.sha256(main).hexdigest(),bytes=len(main)),components={n:sha(out/n) for n in ('strict.cs','board.repl','run.py','probe.resc','runner-source.py')},hardware_accessed=False,boot_rom_executed=False,forced_execution=False)
    write_json(out/'manifest.json',manifest)
    cmd=['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={out},target=/work,readonly','--mount',f'type=bind,source={assets["main"].parent},target=/reference,readonly','--mount',f'type=bind,source={boot},target=/input-boot.bin,readonly','--mount',f'type=bind,source={out/"exports"},target=/work-output',profile['image_id'],'--disable-gui','--console','-p','-e','quit','/work/probe.resc']
    write_json(out/'launcher.json',dict(command=cmd));return cmd


def run(case,out,*,capture_rom_request=False):
    out=Path(out).resolve();cmd=derive(case,out,capture_rom_request=capture_rom_request)
    log=execute(cmd,out,'native',timeout=220,stream=True)
    result=read_json(out/'exports/result.json');manifest=read_json(out/'manifest.json')
    p={x['label']:x['hits'] for x in result['points']}
    result['unsupported_rom_fetch']=result['pc']==0x0200ff20 and 'Trying to execute code outside RAM or ROM at 0x0200FF20.' in log
    result['handoff']=p['stock-handoff'];result['main']=p['main-reset']
    result['classification']=classify(result)
    result['recovery']=recovery_facts(result)
    result['images']={n:dict(sha256=sha(out/'exports'/('guest-'+n+'.bin'))) for n in ('boot','main')}
    result['images_unchanged']=result['images']['boot']['sha256']==manifest['boot']['sha256'] and result['images']['main']['sha256']==manifest['main']['fixture_sha256']
    result['hardware_accessed']=False;result['vendor_recovery_verified']=False
    cleanup=[]
    for f in [out/'main-fixture.bin',out/'exports/guest-boot.bin',out/'exports/guest-main.bin']:
        cleanup.append(dict(name=str(f.relative_to(out)),bytes=f.stat().st_size,sha256=sha(f)));f.unlink()
    result['cleanup']=cleanup
    write_json(out/'report.json',result)
    print(json.dumps(dict(case=case,classification=result['classification'],images_unchanged=result['images_unchanged'],pc=hex(result['pc']),guards=[x for x in result['guards'] if x['accesses']]),ensure_ascii=False),flush=True)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('case',choices=CASES);p.add_argument('output',type=Path)
    p.add_argument('--capture-rom-request',action='store_true')
    a=p.parse_args();run(a.case,a.output,capture_rom_request=a.capture_rom_request)

if __name__=='__main__':main()
