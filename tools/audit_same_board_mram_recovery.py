"""Independently verify actual UART stream, nonzero virtual repair and stock control."""
import argparse,hashlib,hmac,json,runpy,shutil,struct,zlib
from pathlib import Path
PRIVATE=Path.home()/'Library/Application Support/Blackwall'
MAIN='69f9ef63997c9bb53e5b97f83cc330e93651577ab1595ac57dcb481c3e513b9c'
BOOT='7010d103d02a49333362ec185fb04c9657626f97cec5240063375d1c52e55a7e'
CORRUPT='f56513682da145e87e5700350dc63890302e7a6a27344776ede8f03a22aabbb0'
STOCK='22a2b98e606b4d296e957a3a8b600a2158497638d79485c817c2025536329ba7'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def fnv(wire):
 h=14695981039346656037
 for b in wire:h=((h^b)*1099511628211)&0xffffffffffffffff
 return h
def audit(output):
 out=Path(output).resolve();here=Path(__file__).resolve().parent;root=here.parent
 sources=root/'tools' if (root/'tools/bounded_main_rom_model.py').exists() else here/'sources/tools'
 if out.exists() or not out.is_relative_to(PRIVATE):raise ValueError('Fresh private output required')
 sim=PRIVATE/'simulator';bind=runpy.run_path(str(sources/'bounded_main_rom_model.py'))['bind'];base=sim/'recovery-checksum-run-native-bw581-02';expected=bind((base/'strict.cs').read_text());checks={};reports={};records=[]
 runs=[('recover16-rom-native-bw582-04','success'),('recover16-repeat-native-bw582-01','repeat'),('recover16-stock-reference-native-bw582-01','stock'),('recover16-rom-error-native-bw582-04','error')]
 for name,kind in runs:
  d=sim/name;m=read(d/'manifest.json');r=read(d/'report.json');p=read(d/'recovery-plan.json');reports[kind]=r;pre=name+':'
  checks[pre+'frozen_components']=all(sha(d/k)==v for k,v in m['components'].items())
  checks[pre+'same_model']=(d/'strict.cs').read_text()==expected
  checks[pre+'same_board']=(d/'board.repl').read_bytes()==(sim/runs[0][0]/'board.repl').read_bytes()
  checks[pre+'explicit_profile']=m['bounded_main_rom'] and m['allow_checksum_sram'] and m['synchronous_iom7_off'] and m['watchdog_initial_fixture']=='matching-running' and not m['hardware_accessed'] and m['boot_sha256']==(STOCK if kind=='stock' else BOOT)
  runtime=(d/'run.py').read_text();checks[pre+'runtime_no_cpu_seed']='SetRegister' not in runtime and 'bus.Write' not in runtime and runtime.index('BindFunctionalRomEntry')<runtime.index('policy.Attach()')
  checks[pre+'clean_main_entry']=r['classification']=='main-entered' and r['scope']['main_entered'] and not r['machine_aborted'] and not r['engine_unmapped_access'] and r['cfsr']==r['hfsr']==r['policy']==r['system_control_violations']==r['events_dropped']==0 and not any(g['accesses'] for g in r['guards'])
  c={x['path']:x for x in r['cleanup']};initial=CORRUPT if kind!='stock' else MAIN;final=CORRUPT if kind=='error' else MAIN
  checks[pre+'initial_final_whole_hashes']=m['initial_main_sha256']==c['main.bin']['sha256']==initial and c['exports/guest-main.bin']['sha256']==final and c['boot.bin']['sha256']==c['exports/guest-boot.bin']['sha256']==m['boot_sha256'] and r['images_unchanged']==(kind!='error')
  checks[pre+'images_removed']=all(not (d/x).exists() for x in c) and read(d/'native.process.json')['status']=='removed'
  code=bytes(p['payload_bytes']);checks[pre+'pinned_original_recover']=len(code)==264 and hashlib.sha256(code).hexdigest()==p['payload_sha256']=='f046754b6ecba4dd4e3c8e7aa568a713e0961e7f286e98a6f96f955882408732' and p['address']==0x438010 and p['length']==16 and p['restore_bytes']==[0]*16
  uploaded=b''.join(bytes(x[10:10+x[9]]) for x in p['packets'][1:-1]);checks[pre+'load_data_crc']=uploaded==code and struct.unpack_from('<I',bytes(p['packets'][0]),21)[0]==zlib.crc32(code)
  g=r['sram_payload'];rom=r['bounded_main_rom'];v=r['virtual_peer'];cmd=r['recovery_command'];tx=bytes(r['uart2_tx'])
  if kind=='stock':
   checks[pre+'stock_unused_recovery']=len(tx)==v['rx_read']==v['rx_injected']==g['approvals']==g['blocks']==rom['entries']==rom['calls']==rom['programmed_bytes']==0 and not cmd['completed'] and not r['scope']['worker_entered'] and not r['scope']['authentication_verified']
  else:
   checks[pre+'actual_sram_execution']=g['length']==264 and g['approvals']==1 and g['blocks']>0 and g['word_validations']>0 and g['rejections']==0
   checks[pre+'rom_abi_boundary']=rom['entries']==rom['calls']==1 and rom['block_instructions']==0 and rom['key']==0x12344321 and rom['operation']==1 and rom['word_offset']==0xe004 and rom['words']==4 and rom['primask']==1 and 0x20000000<=rom['source']<=0x2007fff0 and rom['payload']==[0]*16 and rom['validated'] and not rom['violation']
   checks[pre+'declared_rom_effect']=rom['status']==(7 if kind=='error' else 0) and rom['programmed_bytes']==(0 if kind=='error' else 16) and ('control_writes' not in rom or rom['control_writes']==3)
   challenge=struct.unpack_from('<I',tx,16)[0];tag=lambda marker:hmac.digest(b'DEFAULTNOTSECRET',b'G2BOOT'+struct.pack('<II',2,challenge)+marker,'sha256')[:16]
   body=bytes([0,1,3,20])+b'OKAY'+tag(b'OKAY');okay=b'\x5a\xa5\xff'+bytes([len(body)])+body+bytes([(len(body)-2+sum(body))&255]);checks[pre+'actual_auth']=tx[21:50]==okay and r['virtual_peer']['held']['words']==[1,0,1,0]
   result=struct.unpack_from('<I',bytes(p['responses'][-1]),14)[0];checks[pre+'stock_error_translation']=result==(0x08000107 if kind=='error' else 0)
   expected_tx=b''.join(bytes(x) for x in p['responses'][:18])+bytes(p['block_request'])+(b'' if kind=='error' else bytes(p['block_output']))+bytes(p['responses'][-1])+bytes([90,165,255,8,0,1,3,4,82,76,83,68,67])
   checks[pre+'actual_complete_tx']=tx[50:]==expected_tx
   hold=bytes([0x7e,0,1,20])+b'HOLD'+tag(b'HOLD');wire=hold+bytes([(len(hold)+1+0x7d+sum(hold))&255])+b''.join(bytes(x) for x in p['packets'])+bytes(p['block_input'])+(b'' if kind=='error' else bytes(p['block_ack']));cont=bytes([0x7e,0,1,4])+b'CONT';wire+=cont+bytes([(len(cont)+1+0x7d+sum(cont))&255])
   checks[pre+'actual_complete_rx']=v['rx_read']==v['rx_injected']==len(wire) and v['rx_hash']==fnv(wire) and v['rx_pending']==v['rx_discarded']==0
   checks[pre+'host_only_fifo_input']=all(e['machine_paused'] for e in v['events']) and all(e['bytes']<=32 for e in v['events'] if e['kind']=='fifo')
   checks[pre+'protocol_result']=cmd['failure'] is None and cmd['input_sent'] and cmd['completed']==(kind!='error') and cmd['output_acked']==(kind!='error') and len(cmd['replies'])==19 and v['stage']=='released'
  records.append(dict(name=name,kind=kind,report_sha256=sha(d/'report.json'),nonzero_repair_verified=kind in ('success','repeat'),main_entered=True,boot_rom_original=False))
 a=reports['success'];b=reports['stock'];context=lambda r:next(x for x in r['contexts'] if x['label']=='main-reset')
 checks['stock_entry_context_exact']=context(a)==context(b)==context(reports['repeat'])==context(reports['error'])
 unit=read(sim/'recover16-domain-unit-bw582-01/report.json');checks['native_domain_checks']=unit['passed'] and unit['markers']==['BLACKWALL_ROM_DOMAIN 41'] and unit['model_sha256']==sha(sim/'recover16-repeat-native-bw582-01/strict.cs')
 # Exact stock ARM ORR r4,#0x08000000 and ORR r4,#0x100; no guessed error mapping.
 boot=(PRIVATE/'recovery/boot-2-4-analysis/boot-2.3.2.14.bin').read_bytes();checks['stock_error_mapping_instructions']=hashlib.sha256(boot).hexdigest()==STOCK and boot[0x1e830:0x1e838].hex()=='44f0006454f48074'
 result=dict(passed=all(checks.values()),checks=checks,cases=records,bv06_complete=all(checks.values()),scope='Cold-session UART2 LOAD/RUN/API3 16-byte virtual MRAM repair, original stock wrapper/readback/progress/RESULT/CONT/main; functional ROM ABI, no original Boot ROM or physical hardware validation',physical_compatibility=False)
 out.mkdir(parents=True,mode=0o700);dest=out/'sources/tools';dest.mkdir(parents=True)
 for n in ('bounded_main_rom_model.py','renode-bounded-main-rom.cs','renode-memory-policy.cs','renode-recovery-writer-fixture.cs'):
  shutil.copy2(sources/n,dest/n)
 shutil.copy2(__file__,out/'audit-source.py');(out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=result['passed'],checks=len(checks),failed=[k for k,v in checks.items() if not v])))
 if not result['passed']:raise ValueError('MRAM recovery audit failed')
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);audit(p.parse_args().output)
