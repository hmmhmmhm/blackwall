"""Frozen audit of qualified boot retention, real WFI returns and UART auth release."""
import argparse,ast,hashlib,hmac,json,shutil,struct
from pathlib import Path
PRIVATE=Path.home()/'Library/Application Support/Blackwall'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def function(path,name,extra=()):
 tree=ast.parse(path.read_text());nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name or isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id in extra for x in n.targets)];ns={};exec(compile(ast.Module(body=nodes,type_ignores=[]),'frozen-method','exec'),ns);return ns

def audit(output):
 out=Path(output).resolve()
 if out.exists() or not out.is_relative_to(PRIVATE):raise ValueError('Fresh private output required')
 sim=PRIVATE/'simulator';d=sim/'boot-retention-auth-native-bw578-01';base=sim/'uart2-auth-good-native-bw577-06';m=read(d/'manifest.json');r=read(d/'report.json');checks={};parent=Path(__file__).parent
 binding=parent/'binding-source.py'
 if not binding.exists():binding=parent/'cpu_retention_staging_model.py'
 bind=function(binding,'compose_boot_binding')['compose_boot_binding'];expected=bind((base/'strict.cs').read_text());checks['exact_ctor_binding']=expected==(d/'strict.cs').read_text() and bind(expected)==expected
 checks['existing_handlers_preserved']=expected[expected.index('        public bool Owns(ulong address)',expected.index('public sealed class BlackwallCpuNormalSleep')):]==(base/'strict.cs').read_text()[(base/'strict.cs').read_text().index('        public bool Owns(ulong address)',(base/'strict.cs').read_text().index('public sealed class BlackwallCpuNormalSleep')):]
 board=(base/'board.repl').read_text()
 for a,b in [('retentionStorePc: 0x4956e2','retentionStorePc: 0x41ca00'),('retentionReturnPc: 0x44df60','retentionReturnPc: 0x41a7c0'),('flushReadPc: 0x44e16e','flushReadPc: 0x41a9ce')]:board=board.replace(a,b)
 board=board.replace('cpu_normal_sleep: Miscellaneous.BlackwallCpuNormalSleep @ none\n','cpu_normal_sleep: Miscellaneous.BlackwallCpuNormalSleep @ none\n    bootRetentionBinding: true\n');checks['exact_board_binding']=board==(d/'board.repl').read_text()
 runtime=(base/'run.py').read_text().replace("observer.AddPoint('peer-receive',0x4353e4)","observer.AddPoint('peer-receive',0x4353e4)\nobserver.AddPoint('boot-wfi',0x41a9d4)\nobserver.AddPoint('boot-wfi-return',0x41a9d6)")
 runtime=runtime.replace("result['machine_aborted']=","result['boot_retention']=dict(stages=int(g.CpuNormalSleep.RetentionStages),flushes=int(g.CpuNormalSleep.RetentionFlushes),cpd=int(g.CpuNormalSleep.CpdValue),cpd_writes=int(g.CpuNormalSleep.CpdWrites))\nresult['machine_aborted']=");checks['runtime_only_observer_and_export']=runtime==(d/'run.py').read_text()
 checks['component_pins']=all(sha(d/k)==v for k,v in m['components'].items());checks['profile_scope']=m['boot_retention_binding'] and m['synthetic_chip_revision']==0x21 and m['synthetic_trim']==1 and not m['hardware_accessed'] and not m['physical_chip_revision_observed']
 checks['firmware_unchanged']=r['images_unchanged'] and m['boot_sha256']=='7010d103d02a49333362ec185fb04c9657626f97cec5240063375d1c52e55a7e' and m['main_sha256']=='69f9ef63997c9bb53e5b97f83cc330e93651577ab1595ac57dcb481c3e513b9c'
 points={p['label']:p for p in r['points']};checks['wfi_and_return']=points['boot-wfi']['hits']==points['boot-wfi-return']['hits']==3 and r['boot_retention']==dict(flushes=3,cpd=0,stages=3,cpd_writes=7)
 seq=[x['label'] for x in r['events'] if x['label'] in ('boot-wfi','boot-wfi-return')];checks['wfi_pairs_in_order']=seq==['boot-wfi','boot-wfi-return']*3
 v=r['virtual_peer'];checks['live_claim_and_release']=v['accepted'] and v['held']['words']==[1,0,1,0] and r['final_session']['words']==[0,0,1,0]
 tx=bytes(r['uart2_tx']);challenge=struct.unpack_from('<I',tx,16)[0]
 def announcement(marker,payload=b''):
  body=bytes([0,1,3,4+len(payload)])+marker+payload;return b'\x5a\xa5\xff'+bytes([len(body)])+body+bytes([(len(body)-2+sum(body))&255])
 tag=lambda marker:hmac.digest(b'DEFAULTNOTSECRET',b'G2BOOT'+struct.pack('<II',2,challenge)+marker,'sha256')[:16]
 checks['actual_helo_okay_released']=tx==announcement(b'HELO',struct.pack('<II',2,challenge))+announcement(b'OKAY',tag(b'OKAY'))+announcement(b'RLSD')
 def request(marker,payload=b''):
  b=bytes([0x7e,0,1,4+len(payload)])+marker+payload;return b+bytes([(len(b)+1+0x7d+sum(b))&255])
 wire=request(b'HOLD',tag(b'HOLD'))+request(b'CONT');h=14695981039346656037
 for b in wire:h=((h^b)*1099511628211)&0xffffffffffffffff
 checks['uart_input_original_consumption']=v['rx_injected']==v['rx_read']==34 and v['rx_pending']==v['rx_discarded']==0 and v['rx_hash']==h
 checks['no_guest_mutation_by_peer']=all(e['machine_paused'] for e in v['events']) and 'bus.Write' not in (d/'run.py').read_text() and 'SetRegister' not in (d/'run.py').read_text()
 checks['no_false_main_recovery']=not r['scope']['main_entered'] and not r['scope']['recovery_verified'] and r['machine_aborted']
 checks['fault_and_observation']=r['cfsr']==r['hfsr']==r['policy']==r['system_control_violations']==r['events_dropped']==0
 log=(d/'native.log').read_text();checks['explicit_unmapped_dwt']=all(s in log for s in ('non existing peripheral at 0xE0001000','non existing peripheral at 0xE0001004'))
 checks['native_removed']=read(d/'native.process.json')['status']=='removed' and all(not (d/x['path']).exists() for x in r['cleanup'])
 for name,good,marker in [('boot-retention-binding-red-bw578-01',False,None),('boot-retention-binding-green-bw578-01',True,'BLACKWALL_BOOT_RETENTION 20')]:
  q=read(sim/name/'report.json');checks[name]=q['passed']==good and (marker is None or q['marker']==[marker]) and read(sim/name/'native.process.json')['status']=='removed'
 boot=PRIVATE/'recovery/boot-2-4-analysis/boot-2.3.2.14.bin';b=boot.read_bytes();checks['original_boot_pin']=sha(boot)=='22a2b98e606b4d296e957a3a8b600a2158497638d79485c817c2025536329ba7'
 checks['original_flush_wfi']=struct.unpack_from('<I',b,0xb0b0)[0]==0x47ff0000 and b[0xa9ce:0xa9d6]==bytes.fromhex('0068c046c04630bf')
 checks['original_store']=b[0xca00:0xca02]==bytes.fromhex('0160')
 tree=read(sim/'gaf-delay-clock-research-01/upstream-tree.json');blobs={x['path']:x['sha'] for x in tree['tree']};sources={}
 for name in ('am_hal_sysctrl.c','am_hal_pwrctrl.c','am_hal_pwrctrl.h'):
  p=sim/'upstream/hal-ambiq-61b293a'/name;raw=p.read_bytes();checks[name+'_source']=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==blobs['mcu/apollo510/hal/'+('mcu/' if name=='am_hal_sysctrl.c' else '')+name];sources[name]=dict(path=str(p),sha256=sha(p))
 result=dict(passed=all(checks.values()),checks=checks,source_commit='61b293a49db34030c545f99101f7ebf6a3050314',sources=sources,report_sha256=sha(d/'report.json'),wire_authentication_verified=True,continue_release_verified=True,recovery_verified=False,main_entered=False,corrected_classification='unsupported-engine',original_report_classification=r['classification'],unresolved='DWT CTRL/CYCCNT absent from board, then machine aborted in watchdog feed; not a successful feed or main handoff',physical_sleep_validated=False,scope='Qualified functional CPD retention/flush; original WFI/return3 and wire OKAY/CONT/RLSD, not physical retention/cycle accuracy')
 out.mkdir(parents=True,mode=0o700);shutil.copy2(__file__,out/'audit-source.py');shutil.copy2(binding,out/'binding-source.py');(out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=result['passed'],checks=len(checks),failed=[k for k,v in checks.items() if not v])))
 if not result['passed']:raise ValueError('Boot retention/auth audit failed')
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);audit(p.parse_args().output)
