"""Run an external virtual UART2 peer against the original B0 reset/worker/main."""
import argparse,hashlib,json,shutil,struct
from pathlib import Path
from run_upstream_boot_probe import derive,PRIVATE,BUILD,MAIN,RELEASES,interpret
from run_boot_validation import classify
from run_original_boot_screen import sha,read_json,write_json
from run_renode_m55_probe import execute
from verify_uart2_receive import bind_uart2_receive
CASES=('silent','good-cont','bad-only','bad-then-good','partial-timeout-good')
PEER='''from System import Array,Byte
clr.AddReference('System.Security.Cryptography')
from System.Security.Cryptography import HMACSHA256
from Antmicro.Renode.Time import TimeInterval
observer.AddPoint('peer-receive',0x4353e4)
g=m['sysbus.guard'];uart=g.Uarts[2];peer_log=[];peer_queue=[];peer_stage='hello';queued_kind='';sent_tick=0;challenge=None;peer_accepted=False;held_snapshot=None
# Original stock Thread and Handler tick accessors both load this pinned word.
def tick():return int(bus.ReadDoubleWord(0x20027148))
def tag(marker):
 message=[ord(x) for x in 'G2BOOT']+[(v>>(8*i))&255 for v in (2,challenge) for i in range(4)]+[ord(x) for x in marker]
 mac=HMACSHA256(Array[Byte]([ord(x) for x in 'DEFAULTNOTSECRET']))
 try:return [int(x) for x in mac.ComputeHash(Array[Byte](message))][:16]
 finally:mac.Dispose()
def request(marker,payload=[]):
 body=[0x7e,0,1,4+len(payload)]+[ord(x) for x in marker]+list(payload)
 return body+[(len(body)+1+0x7d+sum(body))&255]
def event(kind,**extra):
 row=dict(kind=kind,tick=tick(),time=int(m.ElapsedVirtualTime.TimeElapsed.Ticks),machine_paused=bool(m.IsPaused));row.update(extra);peer_log.append(row)
def queue(kind,data):
 global peer_queue,queued_kind
 if peer_queue:raise Exception('Overlapping peer frame')
 peer_queue=list(data);queued_kind=kind;event('queue',frame=kind,bytes=len(data))
def session():
 hits=[p for p in observer.Events if str(p.Label)=='patched-worker']
 if len(hits)!=1:raise Exception('Worker session not unique')
 address=int(hits[0].R0)
 if not 0x20000000<=address<=0x2007fff0:raise Exception('Invalid original session pointer')
 return dict(address=address,words=[int(bus.ReadDoubleWord(address+4*i)) for i in range(4)])
def advance_peer():
 global peer_stage,peer_queue,queued_kind,sent_tick,challenge,peer_accepted,held_snapshot
 tx=[int(x) for x in uart.TxBytes]
 if peer_stage=='hello' and len(tx)>=21:
  if tx[:8]!=[90,165,255,16,0,1,3,12] or tx[8:12]!=[ord(x) for x in 'HELO'] or tx[12:16]!=[2,0,0,0] or tx[20]!=(14+sum(tx[4:20]))&255:raise Exception('Invalid original HELLO')
  challenge=sum(tx[16+i]<<(8*i) for i in range(4));event('hello',session=session());peer_stage='waiting'
  if PEER_CASE!='silent':
   hold=request('HOLD',tag('HOLD'))
   if PEER_CASE in ('bad-only','bad-then-good'):
    hold[8]^=1;hold[-1]=(len(hold)+0x7d+sum(hold[:-1]))&255
   if PEER_CASE=='partial-timeout-good':hold=hold[:8]
   queue('first',hold)
 if peer_queue:
  if not m.IsPaused:raise Exception('Peer input requires paused machine')
  n=len(peer_queue)
  if not uart.TryReceive(Array[Byte](peer_queue),g.UartPowers[2].Phase=='on'):
   n=1
   if not uart.TryReceive(Array[Byte](peer_queue[:1]),g.UartPowers[2].Phase=='on'):return
  peer_queue=peer_queue[n:];event('fifo',frame=queued_kind,bytes=n,pending=int(uart.RxPending))
  if not peer_queue:sent_tick=tick();event('sent',frame=queued_kind)
 if peer_stage=='waiting' and not peer_queue and int(uart.RxPending)==0:
  delay=150 if PEER_CASE=='partial-timeout-good' else 10
  if PEER_CASE in ('bad-then-good','partial-timeout-good') and queued_kind=='first' and (tick()-sent_tick)&0xffffffff>=delay:
   event('retry',wait_ticks=(tick()-sent_tick)&0xffffffff,session=session());queue('retry',request('HOLD',tag('HOLD')))
 if peer_stage=='waiting' and PEER_CASE=='bad-only' and not peer_queue and int(uart.RxPending)==0 and queued_kind=='first' and (tick()-sent_tick)&0xffffffff>=10:
  event('rejected-window',session=session());peer_stage='rejected'
 if peer_stage=='waiting' and len(tx)>=50:
  body=[0,1,3,20]+[ord(x) for x in 'OKAY']+tag('OKAY');expected=[90,165,255,len(body)]+body+[(len(body)-2+sum(body))&255]
  if tx[21:50]!=expected:raise Exception('Original OKAY HMAC/checksum mismatch')
  peer_accepted=True;held_snapshot=session();event('okay',session=held_snapshot);peer_stage='continue';queue('continue',request('CONT'))
 if peer_stage=='continue' and len(tx)>=63:
  body=[0,1,3,4]+[ord(x) for x in 'RLSD'];expected=[90,165,255,len(body)]+body+[(len(body)-2+sum(body))&255]
  if tx[50:63]!=expected:raise Exception('Invalid release')
  peer_stage='released';event('released',session=session())
start=int(m.ElapsedVirtualTime.TimeElapsed.Ticks);deadline=time.time()+150
def main_hit():return any(str(p.Label)=='main-reset' and int(p.Hits)>0 for p in observer.Points)
EmulationManager.Instance.CurrentEmulation.StartAll()
while not cpu.IsHalted and not m.IsAborted and not m.IsPaused and not main_hit() and time.time()<deadline and int(m.ElapsedVirtualTime.TimeElapsed.Ticks)-start<8000000000:
 time.sleep(0.002)
 if m.IsAborted or m.IsPaused or cpu.IsHalted:break
 m.Pause()
 if m.IsAborted or cpu.IsHalted or main_hit():break
 advance_peer()
 EmulationManager.Instance.CurrentEmulation.StartAll()
limit=time.time()>=deadline or int(m.ElapsedVirtualTime.TimeElapsed.Ticks)-start>=8000000000
m.Pause()
'''

def peer_runtime(source,case):
 if case not in CASES:raise ValueError('Unknown peer case')
 a=source.index('start=int(m.ElapsedVirtualTime');b=source.index('\npoints=[',a)
 source=source[:a]+"PEER_CASE="+repr(case)+'\n'+PEER+source[b:]
 anchor="result['uart2_tx']="
 if source.count(anchor)!=1:raise ValueError('Unique UART exporter required')
 extra="result['machine_aborted']=bool(m.IsAborted)\nresult['final_session']=session() if any(str(p.Label)=='patched-worker' for p in observer.Events) else None\nresult['virtual_peer']=dict(case=PEER_CASE,stage=peer_stage,accepted=peer_accepted,held=held_snapshot,events=peer_log,rx_injected=int(uart.RxBytesInjected),rx_read=int(uart.RxBytesRead),rx_discarded=int(uart.RxDiscardedBytes),rx_pending=int(uart.RxPending),rx_hash=int(uart.RxReadHash),irq_assertions=int(uart.IRQAssertions),irq_exceptions=int(uart.IrqExceptionEntries))\n"
 return source.replace(anchor,extra+anchor)

def finalize_peer_scope(d,engine_log):
 d['engine_unmapped_access']=any('non existing peripheral' in line or 'non-existing peripheral' in line for line in engine_log.splitlines())
 if d['engine_unmapped_access']:d['classification']='unsupported-engine'
 elif d.get('machine_aborted') and d['classification']=='stopped-unclassified':d['classification']='engine-aborted'
 d['scope']['authentication_verified']=bool(d['virtual_peer']['accepted'] and d['virtual_peer']['held'] and d['virtual_peer']['held']['words']==[1,0,1,0])


def finalized_nonzero_repair(d,manifest):
 """A main entry or successful diagnostic alone is not restored virtual MRAM."""
 cmd=d.get('recovery_command',{});rom=d.get('bounded_main_rom',{})
 return bool(manifest.get('bounded_main_rom') and manifest.get('corrupt_main16') and manifest.get('initial_main_sha256')!=MAIN and d.get('images_unchanged') and cmd.get('mode')=='recover16' and cmd.get('completed') and cmd.get('input_sent') and cmd.get('output_acked') and not cmd.get('failure') and rom.get('validated') and rom.get('status')==0 and rom.get('programmed_bytes')==16 and rom.get('calls')==1 and not rom.get('violation') and d.get('classification')=='main-entered' and not d.get('machine_aborted') and not d.get('engine_unmapped_access') and not d.get('policy') and not d.get('system_control_violations') and not d.get('events_dropped') and not any(g['accesses'] for g in d.get('guards',[])))


def run(case,out,*,boot_retention=False,dwt=False,watchdog_read_holes=False,watchdog_initial='unknown',recovery=None,allow_checksum_sram=False,synchronous_iom7_off=False,stock_reference=False,bounded_main_rom=False,rom_status=0,corrupt_main16=False):
 out=Path(out).resolve()
 if case not in CASES:raise ValueError('Unknown peer case')
 if type(boot_retention) is not bool:raise ValueError('Explicit boot retention option required')
 if type(dwt) is not bool or dwt and not boot_retention:raise ValueError('DWT requires explicit boot retention profile')
 if type(watchdog_read_holes) is not bool or watchdog_read_holes and not dwt:raise ValueError('Ignored PMIC read-hole mock requires explicit DWT profile')
 if watchdog_initial not in ('unknown','matching-running','mismatch-running') or watchdog_initial!='unknown' and not watchdog_read_holes:raise ValueError('Explicit synthetic watchdog initial state requires read-hole profile')
 if recovery not in (None,'checksum','bad-crc','tamper','recover16') or recovery is not None and (not watchdog_read_holes or watchdog_initial=='unknown'):raise ValueError('Recovery needs the explicit supported watchdog profile')
 if type(allow_checksum_sram) is not bool or allow_checksum_sram and recovery is None:raise ValueError('SRAM permission requires a pinned recovery plan')
 if type(synchronous_iom7_off) is not bool or synchronous_iom7_off and not watchdog_read_holes:raise ValueError('Synchronous IOM7 off requires explicit watchdog profile')
 if type(stock_reference) is not bool or stock_reference and case!='silent':raise ValueError('Stock reference requires a silent external peer')
 if type(bounded_main_rom) is not bool or bounded_main_rom and (recovery!='recover16' or not allow_checksum_sram):raise ValueError('Bounded ROM requires the pinned nonzero recover payload')
 if type(rom_status) is not int or rom_status not in (0,7) or rom_status and not bounded_main_rom:raise ValueError('Reviewed ROM status requires bounded contract')
 if type(corrupt_main16) is not bool or corrupt_main16 and not bounded_main_rom:raise ValueError('Corrupt main fixture requires bounded recovery contract')
 metadata=read_json(BUILD/'source/build/patch.json');default_id=hashlib.sha256(b'DEFAULTNOTSECRET'.ljust(64,b'\0')).hexdigest()
 if metadata['auth_key_sha256']!=default_id:raise ValueError('This profile requires the public default key artifact')
 boot=(PRIVATE/'recovery/boot-2-4-analysis/boot-2.3.2.14.bin').read_bytes()
 if struct.unpack_from('<I',boot,0x8ae4)[0]!=0x20027148:raise ValueError('Pinned original tick word changed')
 command=derive('current',out,1,chip_revision=0x21,b0_ton=True)
 expected_boot_sha=RELEASES['current'];expected_boot_bytes=159744
 if stock_reference:
  if hashlib.sha256(boot).hexdigest()!='22a2b98e606b4d296e957a3a8b600a2158497638d79485c817c2025536329ba7':raise ValueError('Exact stock2.3 boot reference required')
  expected_boot_sha=hashlib.sha256(boot).hexdigest();expected_boot_bytes=len(boot);(out/'boot.bin').write_bytes(boot)
 source=bind_uart2_receive((out/'strict.cs').read_text())
 if boot_retention:
  from cpu_retention_staging_model import compose_boot_binding
  source=compose_boot_binding(source)
 if recovery is not None:
  from dcache_address_models import bind_dccmvau
  source=bind_dccmvau(source)
 if allow_checksum_sram:
  from sram_payload_policy import bind as bind_sram
  source=bind_sram(source,Path(__file__).with_name('renode-sram-payload-gate.cs').read_text())
 if synchronous_iom7_off:
  from recovery_power_response import bind as bind_power
  source=bind_power(source)
 if bounded_main_rom:
  from bounded_main_rom_model import bind as bind_main_rom
  source=bind_main_rom(source)
 (out/'strict.cs').write_text(source)
 board=(out/'board.repl').read_text();anchor='uart2_adapter: Miscellaneous.BlackwallUartAdapter\n'
 if board.count(anchor)!=1:raise ValueError('Unique UART2 adapter required')
 board=board.replace(anchor,anchor+'    receiveFifo: true\n')
 if boot_retention:
  for old,new in [('retentionStorePc: 0x4956e2','retentionStorePc: 0x41ca00'),('retentionReturnPc: 0x44df60','retentionReturnPc: 0x41a7c0'),('flushReadPc: 0x44e16e','flushReadPc: 0x41a9ce')]:
   if board.count(old)!=1:raise ValueError('Unique existing retention binding required')
   board=board.replace(old,new)
  anchor='cpu_normal_sleep: Miscellaneous.BlackwallCpuNormalSleep @ none\n'
  if board.count(anchor)!=1:raise ValueError('Unique CPU sleep owner required')
  board=board.replace(anchor,anchor+'    bootRetentionBinding: true\n')
 if watchdog_read_holes:
  anchor='pointerProbe: Miscellaneous.BlackwallPmicTimedProbe @ iom7 0x6b\n'
  if board.count(anchor)!=1:raise ValueError('Unique timed PMIC owner required')
  board=board.replace(anchor,anchor+'    recoveryReadHoleMock: 0\n')
 if synchronous_iom7_off:
  anchor='iom7_power: Miscellaneous.BlackwallPeripheralPower\n'
  if board.count(anchor)!=1:raise ValueError('Unique IOM7 power owner required')
  board=board.replace(anchor,anchor+'    synchronousOffResponse: true\n')
 if bounded_main_rom:board+='\nbounded_rom: Memory.MappedMemory @ sysbus 0x0200f000\n    size: 0x1000\n'
 if dwt:board+='\nboot_dwt: Miscellaneous.DWT @ sysbus 0xe0001000\n    frequency: 10000000\n'
 (out/'board.repl').write_text(board)
 run_source=peer_runtime((out/'run.py').read_text(),case)
 if stock_reference:
  run_source=run_source.replace('159744',str(expected_boot_bytes))
  anchor=' advance_peer()\n'
  if run_source.count(anchor)!=1:raise ValueError('Unique external peer action required')
  run_source=run_source.replace(anchor,' pass # silent stock reference: no external protocol input\n')
 if boot_retention:
  anchor="observer.AddPoint('peer-receive',0x4353e4)"
  run_source=run_source.replace(anchor,anchor+"\nobserver.AddPoint('boot-wfi',0x41a9d4)\nobserver.AddPoint('boot-wfi-return',0x41a9d6)")
  anchor="result['machine_aborted']="
  run_source=run_source.replace(anchor,"result['boot_retention']=dict(stages=int(g.CpuNormalSleep.RetentionStages),flushes=int(g.CpuNormalSleep.RetentionFlushes),cpd=int(g.CpuNormalSleep.CpdValue),cpd_writes=int(g.CpuNormalSleep.CpdWrites))\n"+anchor)
 if dwt:
  anchor="observer.AddPoint('peer-receive',0x4353e4)"
  run_source=run_source.replace(anchor,anchor+"\nobserver.AddPoint('watchdog-feed',0x434978)\nobserver.AddPoint('watchdog-command',0x434ad0)\nobserver.AddPoint('watchdog-feed-return',0x434a3e)")
  anchor="result['machine_aborted']="
  extra="result['watchdog_platform']=dict(dwt_ctrl=int(m['sysbus.boot_dwt'].ReadDoubleWord(0)),dwt_cycles=int(m['sysbus.boot_dwt'].ReadDoubleWord(4)),iom_commands=int(m['sysbus.iom7'].Commands),iom_accesses=int(m['sysbus.iom7'].AccessCount),iom_last=str(m['sysbus.iom7'].LastOperation),pmic_accesses=int(m['sysbus.iom7.pointerProbe'].AccessCount),pmic_last=str(m['sysbus.iom7.pointerProbe'].LastOperation),kicks=int(m['sysbus.iom7.pointerProbe'].Timer.Kicks))\n"
  run_source=run_source.replace(anchor,extra+anchor)
 if watchdog_initial!='unknown':
  target=0x3c00 if watchdog_initial=='matching-running' else 0x3c01
  anchor="observer.AddPoint('peer-receive',0x4353e4)"
  setup="q=m['sysbus.iom7.pointerProbe']\ndef initial_pmic(data):\n q.Write(Array[Byte](data));q.FinishTransmission()\n"
  setup+="initial_pmic([7,5,10])\ninitial_pmic([7,8,0,"+str(target>>8)+","+str(target&255)+"])\ninitial_pmic([7,3,1])\ninitial_pmic([7,0,1])\n"
  setup+="if not q.Timer.Running or not q.Timer.ConfigKnown or not q.Timer.TargetKnown or int(q.Timer.Target)!="+str(target)+":raise Exception('Invalid explicit PMIC initial state')\n"
  setup+="watchdog_initial_snapshot=dict(target=int(q.Timer.Target),running=bool(q.Timer.Running),kicks=int(q.Timer.Kicks),timer_writes=int(q.TimerWrites),cpu_instructions=int(cpu.ExecutedInstructions))\n"
  run_source=run_source.replace(anchor,setup+anchor)
  run_source=run_source.replace("result['machine_aborted']=","result['watchdog_initial_snapshot']=watchdog_initial_snapshot\n"+"result['machine_aborted']=")
 if recovery is not None:
  from same_board_recovery_peer import plan,bind_peer
  recovery_plan=plan(BUILD,recovery)
  if recovery=='recover16':
   from same_board_recovery_peer import reply
   # Stock 2.3 ARM at 42e830/42e834 adds subsystem/status bits to ROM errors.
   expected_return=(rom_status|0x08000100) if rom_status else 0
   recovery_plan.update(expect_progress=rom_status==0,expected_return=expected_return)
   recovery_plan['responses'][-1]=reply(2,0,struct.pack('<I',expected_return))
  run_source=bind_peer(run_source,recovery_plan)
  run_source=run_source.replace("result['machine_aborted']=","result['recovery_cache']=dict(clean_pou=int(control.DataCache.AddressUnificationCleans),last_line=int(control.DataCache.LastAddressLine),icache_invalidations=int(control.Invalidations),last_operation=str(control.LastOperation),last_address=int(control.LastAddress),last_value=int(control.LastValue))\n"+"result['machine_aborted']=")
  if allow_checksum_sram:
   anchor='policy.Attach()'
   if run_source.count(anchor)!=1:raise ValueError('Unique execution policy attachment required')
   run_source=run_source.replace(anchor,'from System import Array,Byte\npolicy.BindSramPayload(Array[Byte]('+repr(recovery_plan['payload_bytes'])+'),0)\n'+anchor)
   run_source=run_source.replace("result['machine_aborted']=","result['sram_payload']=dict(base=int(policy.SramPayload.BaseAddress),length=int(policy.SramPayload.Length),approvals=int(policy.SramPayload.Approvals),word_validations=int(policy.SramPayload.WordValidations),rejections=int(policy.SramPayload.Rejections),blocks=int(policy.SramPayloadBlocks))\n"+"result['machine_aborted']=")
  write_json(out/'recovery-plan.json',recovery_plan)
 if bounded_main_rom:
  anchor='policy.Attach()'
  if run_source.count(anchor)!=1:raise ValueError('Unique ROM policy attachment required')
  setup="from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallBoundedMainRom,BlackwallRecoveryMramControl\n"
  setup+="m['sysbus.guard'].RecoveryMramControl=BlackwallRecoveryMramControl()\nm['sysbus.bounded_rom'].WriteWord(0xf20,0xbe00)\n"
  setup+="main_rom=BlackwallBoundedMainRom(m,cpu,m['sysbus.main'],m['sysbus.guard'].MemoryStartup,Array[Byte]("+repr(recovery_plan['restore_bytes'])+"),"+str(rom_status)+")\npolicy.BindFunctionalRomEntry(main_rom.CheckEntry)\n"
  run_source=run_source.replace(anchor,setup+anchor)
  anchor="observer.AddPoint('peer-receive',0x4353e4)"
  run_source=run_source.replace(anchor,"control.DataCache.ApprovedMramInvalidation=main_rom.AllowInvalidation\n"+anchor)
  extra="result['bounded_main_rom']=dict(entries=int(main_rom.Entries),calls=int(main_rom.Calls),block_instructions=int(main_rom.BlockInstructions),control_writes=int(m['sysbus.guard'].RecoveryMramControl.Writes),key=int(main_rom.Key),operation=int(main_rom.Operation),source=int(main_rom.Source),word_offset=int(main_rom.WordOffset),words=int(main_rom.WordCount),primask=int(main_rom.Primask),programmed_bytes=int(main_rom.ProgrammedBytes),status=int(main_rom.Status),validated=bool(main_rom.Validated),violation=bool(main_rom.Violation),failure=str(main_rom.Failure),payload=[] if main_rom.Payload is None else [int(x) for x in main_rom.Payload])\n"
  run_source=run_source.replace("result['machine_aborted']=",extra+"result['machine_aborted']=")
 if corrupt_main16:
  path=out/'main.bin';data=bytearray(path.read_bytes());data[16:32]=bytes(x^0xa5 for x in data[16:32]);path.write_bytes(data)
 (out/'run.py').write_text(run_source);shutil.copy2(__file__,out/'peer-runner-source.py')
 m=read_json(out/'manifest.json');m['peer_case']=case;m['boot_retention_binding']=boot_retention;m['dwt_frequency_hypothesis']=10000000 if dwt else None;m['pmic_ignored_read_holes_mock']=0 if watchdog_read_holes else None;m['watchdog_initial_fixture']=watchdog_initial;m['recovery_mode']=recovery;m['allow_checksum_sram']=allow_checksum_sram;m['synchronous_iom7_off']=synchronous_iom7_off;m['stock_reference']=stock_reference;m['boot_sha256']=expected_boot_sha;m['boot_image_bytes']=expected_boot_bytes;m['bounded_main_rom']=bounded_main_rom;m['rom_status']=rom_status;m['corrupt_main16']=corrupt_main16;m['initial_main_sha256']=sha(out/'main.bin');m['public_default_key']=True;m['execution_schedule']='StartAll + host pause/FIFO input/resume; no CPU or guest RAM writes';m['components'].update({n:sha(out/n) for n in ('strict.cs','board.repl','run.py','peer-runner-source.py')});write_json(out/'manifest.json',m)
 engine_log=execute(command,out,'native',timeout=220,stream=True)
 d=read_json(out/'exports/result.json');points={p['label']:p['hits'] for p in d['points']};d['main']=points['main-reset'];d['handoff']=points['stock-handoff'];d['classification']=classify(d);d['scope']=interpret(points)
 finalize_peer_scope(d,engine_log)
 d['scope']['ram_diagnostic_verified']=bool(d.get('recovery_command',{}).get('completed') and d['scope']['main_entered'] and not d.get('engine_unmapped_access') and not d.get('machine_aborted') and not d['policy'] and not d['system_control_violations'] and d['classification']=='main-entered')
 d['scope']['recovery_verified']=False # Nonzero MRAM recovery transport has a separate completion gate.
 d['images_unchanged']=sha(out/'exports/guest-boot.bin')==expected_boot_sha and sha(out/'exports/guest-main.bin')==MAIN;d['cleanup']=[]
 d['scope']['payload_execution_verified']=d['scope']['ram_diagnostic_verified']
 d['scope']['ram_diagnostic_verified']=d['scope']['payload_execution_verified'] and recovery=='checksum'
 d['scope']['nonzero_mram_recovery_verified']=finalized_nonzero_repair(d,m)
 d['scope']['recovery_verified']=d['scope']['nonzero_mram_recovery_verified']
 for name in ('boot.bin','main.bin','exports/guest-boot.bin','exports/guest-main.bin'):
  p=out/name;d['cleanup'].append(dict(path=name,bytes=p.stat().st_size,sha256=sha(p)));p.unlink()
 write_json(out/'report.json',d);print(json.dumps(dict(case=case,classification=d['classification'],images_unchanged=d['images_unchanged'],peer=d['virtual_peer'],uart2_tx_bytes=len(d['uart2_tx']))));return d
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--boot-retention',action='store_true');p.add_argument('--dwt',action='store_true');p.add_argument('--watchdog-read-holes',action='store_true');p.add_argument('--allow-checksum-sram',action='store_true');p.add_argument('--synchronous-iom7-off',action='store_true');p.add_argument('--bounded-main-rom',action='store_true');p.add_argument('--rom-status',type=int,choices=(0,7),default=0);p.add_argument('--corrupt-main16',action='store_true');p.add_argument('--stock-reference',action='store_true');p.add_argument('--recovery',choices=('checksum','bad-crc','tamper','recover16'));p.add_argument('--watchdog-initial',choices=('unknown','matching-running','mismatch-running'),default='unknown');p.add_argument('case',choices=CASES);p.add_argument('output',type=Path);a=p.parse_args();run(a.case,a.output,boot_retention=a.boot_retention,dwt=a.dwt,watchdog_read_holes=a.watchdog_read_holes,watchdog_initial=a.watchdog_initial,recovery=a.recovery,allow_checksum_sram=a.allow_checksum_sram,synchronous_iom7_off=a.synchronous_iom7_off,stock_reference=a.stock_reference,bounded_main_rom=a.bounded_main_rom,rom_status=a.rom_status,corrupt_main16=a.corrupt_main16)
