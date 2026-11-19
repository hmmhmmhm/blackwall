"""Audit real UART2 byte consumption/auth decisions without claiming recovery completion."""
import argparse,ast,hashlib,hmac,json,shutil,struct
from pathlib import Path
PRIVATE=Path.home()/'Library/Application Support/Blackwall'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def request(marker,payload=b''):
 b=bytes([0x7e,0,1,4+len(payload)])+marker+payload;return b+bytes([(len(b)+1+0x7d+sum(b))&255])
def fnv(b):
 v=14695981039346656037
 for x in b:v=((v^x)*1099511628211)&0xffffffffffffffff
 return v

def audit(out):
 out=Path(out).resolve()
 if out.exists() or not out.is_relative_to(PRIVATE):raise ValueError('Fresh private audit required')
 sim=PRIVATE/'simulator';base=sim/'upstream23-b0-ton-native-bw576-03';checks={}
 parent=Path(__file__).parent;peer=parent/'peer-source.py';binding=parent/'uart-binding-source.py'
 if not peer.exists():peer=parent/'run_same_board_uart2.py'
 if not binding.exists():binding=parent/'verify_uart2_receive.py'
 tree=ast.parse(binding.read_text());ns={};exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='bind_uart2_receive'],type_ignores=[]),'frozen-uart-binding','exec'),ns)
 expected_model=ns['bind_uart2_receive']((base/'strict.cs').read_text())
 t=ast.parse(peer.read_text());nodes=[n for n in t.body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id in ('CASES','PEER') for x in n.targets) or isinstance(n,ast.FunctionDef) and n.name=='peer_runtime'];pns={};exec(compile(ast.Module(body=nodes,type_ignores=[]),'frozen-peer','exec'),pns)
 result_rows=[];cleanup=[]
 cases=[('good-cont','uart2-auth-good-native-bw577-06',25,1),('bad-only','uart2-auth-bad-native-bw577-01',25,2),('partial-timeout-good','uart2-auth-partial-native-bw577-01',33,2),('bad-then-good','uart2-auth-retry-native-bw577-01',50,2),('silent','uart2-auth-silent-native-bw577-01',0,1)]
 for case,name,nrx,receives in cases:
  d=sim/name;m=read(d/'manifest.json');r=read(d/'report.json');v=r['virtual_peer'];prefix=case+':';positive=case not in ('bad-only','silent');points={x['label']:x for x in r['points']}
  checks[prefix+'pinned_components']=all(sha(d/k)==h for k,h in m['components'].items())
  checks[prefix+'model_only_fifo_gate']=(d/'strict.cs').read_text()==expected_model
  checks[prefix+'board_only_receive_option']=(d/'board.repl').read_text()==(base/'board.repl').read_text().replace('uart2_adapter: Miscellaneous.BlackwallUartAdapter\n','uart2_adapter: Miscellaneous.BlackwallUartAdapter\n    receiveFifo: true\n')
  checks[prefix+'external_peer_runtime']=(d/'run.py').read_text()==pns['peer_runtime']((base/'run.py').read_text(),case)
  checks[prefix+'no_firmware_change']=r['images_unchanged'] and m['boot_sha256']=='7010d103d02a49333362ec185fb04c9657626f97cec5240063375d1c52e55a7e' and m['main_sha256']=='69f9ef63997c9bb53e5b97f83cc330e93651577ab1595ac57dcb481c3e513b9c'
  checks[prefix+'synthetic_only']=m['peer_case']==case and m['synthetic_chip_revision']==0x21 and m['synthetic_trim']==1 and m['public_default_key'] and not m['hardware_accessed'] and not m['physical_chip_revision_observed']
  checks[prefix+'read_counts']=v['rx_injected']==v['rx_read']==nrx and v['rx_pending']==v['rx_discarded']==0
  checks[prefix+'pause_input']=all(x['machine_paused'] for x in v['events'])
  checks[prefix+'worker_original']=points['boot-reset']['hits']==points['patched-worker']['hits']==1 and points['peer-receive']['hits']==receives
  tx=bytes(r['uart2_tx']);challenge=struct.unpack_from('<I',tx,16)[0];hold=request(b'HOLD',hmac.digest(b'DEFAULTNOTSECRET',b'G2BOOT'+struct.pack('<II',2,challenge)+b'HOLD','sha256')[:16]);bad=bytearray(hold);bad[8]^=1;bad[-1]=(len(bad)+0x7d+sum(bad[:-1]))&255
  wire={'good-cont':hold,'bad-only':bytes(bad),'partial-timeout-good':hold[:8]+hold,'bad-then-good':bytes(bad)+hold,'silent':b''}[case]
  checks[prefix+'actual_wire_fnv']=v['rx_hash']==fnv(wire)
  checks[prefix+'no_okay_or_recovery_claim']=len(tx)==21 and tx[8:12]==b'HELO' and not v['accepted'] and not r['scope']['authentication_verified'] and not r['scope']['recovery_verified']
  checks[prefix+'no_cpu_fault']=r['cfsr']==r['hfsr']==r['policy']==r['system_control_violations']==r['events_dropped']==0
  if positive:
   guards=[x for x in r['guards'] if x['accesses']]
   checks[prefix+'accepted_before_cpd_stop']=r['final_session']['words']==[1,0,1,0] and r['pc']==0x41ca00 and r['classification']=='unsupported-model' and r['machine_aborted'] and len(guards)==1 and guards[0]['address']==0xe001e300 and guards[0]['operation']=='write' and guards[0]['value']==0x22 and not r['scope']['main_entered']
  else:
   checks[prefix+'natural_main_no_auth']=r['classification']=='main-entered' and r['scope']['main_entered'] and not r['machine_aborted'] and not any(x['accesses'] for x in r['guards'])
  if case=='bad-only':checks[prefix+'wrong_hmac_no_claim']=next(x['session']['words'] for x in v['events'] if x['kind']=='rejected-window')==[0,0,0,0]
  if case in ('partial-timeout-good','bad-then-good'):
   retry=next(x for x in v['events'] if x['kind']=='retry');checks[prefix+'retry_unclaimed']=retry['session']['words']==[0,0,0,0] and retry['wait_ticks']>=(128 if case=='partial-timeout-good' else 10)
  checks[prefix+'removed']=read(d/'native.process.json')['status']=='removed' and len(r['cleanup'])==4 and all(not (d/x['path']).exists() for x in r['cleanup'])
  cleanup+=r['cleanup'];result_rows.append(dict(case=case,report_sha256=sha(d/'report.json'),bytes_consumed=nrx,original_receive_calls=receives,held_before_stop=positive,full_authentication=False,recovery=False))
 for name,count in [('uart2-rx-green-bw577-01',23),('uart0-rx-regression-bw577-01',49)]:
  r=read(sim/name/'report.json');checks[name]=r['passed'] and r['count']==count and read(sim/name/('renode.process.json' if name.startswith('uart0-') else 'native.process.json'))['status']=='removed'
 checks['uart2_red']=not read(sim/'uart2-rx-red-bw577-01/report.json')['passed']
 checks['peer_crypto_preflight']=read(sim/'uart2-peer-hmac-preflight-bw577-01/report.json')['passed']
 boot=PRIVATE/'recovery/boot-2-4-analysis/boot-2.3.2.14.bin';b=boot.read_bytes();checks['stock_tick_literal']=hashlib.sha256(b).hexdigest()=='22a2b98e606b4d296e957a3a8b600a2158497638d79485c817c2025536329ba7' and struct.unpack_from('<I',b,0x8ae4)[0]==0x20027148
 checks['original_cpd_store_bytes']=b[0xca00:0xca02]==bytes.fromhex('0160')
 result=dict(passed=all(checks.values()),checks=checks,cases=result_rows,public_default_key_only=True,irq_exception_counter_unprobed=True,complete_authentication_verified=False,recovery_verified=False,progress='10/12 unchanged',scope='Same original B0 reset/worker and actual UART2 FIFO: good/bad HMAC and timeout/retry decisions; good claims stop at unsupported deep-sleep CPD preparation, before OKAY/commands')
 out.mkdir(parents=True,mode=0o700);shutil.copy2(__file__,out/'audit-source.py');shutil.copy2(peer,out/'peer-source.py');shutil.copy2(binding,out/'uart-binding-source.py');(out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=result['passed'],checks=len(checks),failed=[k for k,v in checks.items() if not v])))
 if not result['passed']:raise ValueError('Same-board UART2 audit failed')
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);audit(p.parse_args().output)
