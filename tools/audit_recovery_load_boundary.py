"""Audit original UART recovery LOAD/CRC and strict cache/SRAM/power boundaries."""
import argparse,ast,hashlib,hmac,json,shutil,struct,zlib
from pathlib import Path
PRIVATE=Path.home()/'Library/Application Support/Blackwall'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load_functions(p,names,assignments=()):
 t=ast.parse(p.read_text());nodes=[n for n in t.body if isinstance(n,ast.FunctionDef) and n.name in names or isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id in assignments for x in n.targets)];ns=dict(hashlib=hashlib,struct=struct,zlib=zlib,Path=Path);exec(compile(ast.Module(body=nodes,type_ignores=[]),'frozen-source','exec'),ns);return ns

def audit(output):
 out=Path(output).resolve()
 if out.exists() or not out.is_relative_to(PRIVATE):raise ValueError('Fresh private audit required')
 sim=PRIVATE/'simulator';parent=Path(__file__).parent;peer=parent/'recovery-peer-source.py';cache=parent/'cache-binding-source.py'
 if not peer.exists():peer=parent/'same_board_recovery_peer.py'
 if not cache.exists():cache=parent/'dcache_address_models.py'
 ns=load_functions(peer,('request','reply','plan','bind_peer'),('PAYLOAD_SHA','HELPER'));bind=load_functions(cache,('bind_dccmvau',))['bind_dccmvau'];checks={};reports={}
 base=sim/'recovery-checksum-strict-native-bw580-01';good=sim/'recovery-checksum-strict-native-bw580-03';bad=sim/'recovery-bad-crc-native-bw580-01'
 for name,d,mode in [('before-cache',base,'checksum'),('strict-sram',good,'checksum'),('bad-crc',bad,'bad-crc')]:
  m=read(d/'manifest.json');r=read(d/'report.json');p=read(d/'recovery-plan.json');reports[name]=r;prefix=name+':'
  checks[prefix+'plan']=p==ns['plan'](PRIVATE/'recovery/upstream-stock23-bw558-01',mode)
  checks[prefix+'components']=all(sha(d/k)==v for k,v in m['components'].items())
  checks[prefix+'original_images']=r['images_unchanged'] and m['boot_sha256']=='7010d103d02a49333362ec185fb04c9657626f97cec5240063375d1c52e55a7e' and m['main_sha256']=='69f9ef63997c9bb53e5b97f83cc330e93651577ab1595ac57dcb481c3e513b9c'
  checks[prefix+'no_completion_claim']=not r['recovery_command']['completed'] and not r['scope']['recovery_verified'] and not r['scope']['main_entered']
  tx=bytes(r['uart2_tx']);challenge=struct.unpack_from('<I',tx,16)[0];tag=lambda marker:hmac.digest(b'DEFAULTNOTSECRET',b'G2BOOT'+struct.pack('<II',2,challenge)+marker,'sha256')[:16]
  body=bytes([0,1,3,20])+b'OKAY'+tag(b'OKAY');okay=b'\x5a\xa5\xff'+bytes([len(body)])+body+bytes([(len(body)-2+sum(body))&255]);checks[prefix+'wire_auth']=r['scope']['authentication_verified'] and tx[21:50]==okay and r['virtual_peer']['held']['words']==[1,0,1,0]
  count=5 if mode=='bad-crc' else 4
  released_body=bytes([0,1,3,4])+b'RLSD';released=b'\x5a\xa5\xff'+bytes([len(released_body)])+released_body+bytes([(len(released_body)-2+sum(released_body))&255])
  checks[prefix+'real_replies']=tx[50:]==b''.join(bytes(x) for x in p['responses'][:count])+(released if mode=='bad-crc' else b'') and len(r['recovery_command']['replies'])==count
  hold=bytes([0x7e,0,1,20])+b'HOLD'+tag(b'HOLD');hold+=bytes([(len(hold)+1+0x7d+sum(hold))&255]);wire=hold+b''.join(bytes(x) for x in p['packets'])
  if mode=='bad-crc':
   b=bytes([0x7e,0,1,4])+b'CONT';wire+=b+bytes([(len(b)+1+0x7d+sum(b))&255])
  v=14695981039346656037
  for b in wire:v=((v^b)*1099511628211)&0xffffffffffffffff
  checks[prefix+'uart_bytes_injected']=r['virtual_peer']['rx_injected']==len(wire)
  # A pending CONT at the power boundary is recorded rather than assumed consumed.
  checks[prefix+'uart_consumed']=r['virtual_peer']['rx_read']==len(wire) and r['virtual_peer']['rx_hash']==v and r['virtual_peer']['rx_pending']==0
  checks[prefix+'no_cpu_fault']=r['cfsr']==r['hfsr']==r['events_dropped']==0 and not r['engine_unmapped_access']
  checks[prefix+'owned_removed']=read(d/'native.process.json')['status']=='removed' and all(not (d/x['path']).exists() for x in r['cleanup'])
 checks['only_cache_model_extension']=(good/'strict.cs').read_text()==bind((base/'strict.cs').read_text())==(bad/'strict.cs').read_text()
 extra="result['recovery_cache']=dict(clean_pou=int(control.DataCache.AddressUnificationCleans),last_line=int(control.DataCache.LastAddressLine),icache_invalidations=int(control.Invalidations),last_operation=str(control.LastOperation),last_address=int(control.LastAddress),last_value=int(control.LastValue))\n"
 checks['only_cache_export_delta']=(good/'run.py').read_text()==(base/'run.py').read_text().replace("result['machine_aborted']=",extra+"result['machine_aborted']=")
 gp=read(good/'recovery-plan.json');bp=read(bad/'recovery-plan.json');checks['only_negative_plan_delta']=(bad/'run.py').read_text()==(good/'run.py').read_text().replace('RECOVERY_PLAN='+repr(gp),'RECOVERY_PLAN='+repr(bp))
 r=reports['before-cache'];checks['initial_pou_guard']=r['pc']==0x43503a and r['system_control_violations']==1 and r['policy']==0 and r['registers'][2]+0x14==0xe000ef64
 r=reports['strict-sram'];checks['strict_first_sram_instruction']=r['policy_operation']=='execute-outside-code' and r['policy_address']==r['pc']==0x2001c7a0 and r['policy']==1 and r['system_control_violations']==0
 checks['actual_two_pou_cleans']=r['recovery_cache']['clean_pou']==2 and r['recovery_cache']['icache_invalidations']==2 and r['recovery_cache']['last_operation']=='none'
 r=reports['bad-crc'];checks['crc_and_unavailable']= [(x['kind'],x['status']) for x in r['recovery_command']['replies']]==[(0,0),(0,0),(0,0),(4,3),(4,1)] and r['recovery_cache']['clean_pou']==0 and r['policy']==0
 guards=[g for g in r['guards'] if g['accesses']];power=next(x for x in r['power_owners']['ioms'] if x['module']==7);request=0
 for group in ('ioms','uarts'):
  for item in r['power_owners'][group]:request|=item['request']
 checks['pending_off_reactivation_boundary']=len(guards)==1 and guards[0]['address']==0x40021004 and guards[0]['value']==0xd00 and (guards[0]['value']^request)==0x100 and power['phase']=='off-requested' and power['request']==0 and power['status']==0x100
 green=read(sim/'recovery-dccmvau-green-bw580-01/report.json');checks['cache_native_green']=green['passed'] and green['count']==66
 checks['cache_native_red']='SRAM-clean-to-PoU' in (sim/'recovery-dccmvau-red-bw580-01/renode.log').read_text()
 result=dict(passed=all(checks.values()),checks=checks,program_sha256=ns['PAYLOAD_SHA'],program_bytes=48,main_crc_expected=gp['expected_crc32'],program_executed=False,recovery_complete=False,progress='11/12 unchanged',scope='Original UART LOAD/DATA CRC/READY, RUN first SRAM instruction guard, bad CRC/RUN-unavailable; PoU coherent-cache extension only. Pending IOM7 off reactivation remains unsupported.')
 out.mkdir(parents=True,mode=0o700);shutil.copy2(__file__,out/'audit-source.py');shutil.copy2(peer,out/'recovery-peer-source.py');shutil.copy2(cache,out/'cache-binding-source.py');(out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=result['passed'],checks=len(checks),failed=[k for k,v in checks.items() if not v])))
 if not result['passed']:raise ValueError('Recovery LOAD boundary audit failed')
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);audit(p.parse_args().output)
