"""Audit byte-exact RAM diagnostics, mutations rejected and original stock comparison."""
import argparse,ast,hashlib,hmac,json,shutil,struct,zlib
from pathlib import Path
PRIVATE=Path.home()/'Library/Application Support/Blackwall'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def functions(path,names):
 t=ast.parse(path.read_text());ns={};exec(compile(ast.Module(body=[n for n in t.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[]),'frozen-bind','exec'),ns);return ns

def audit(output):
 out=Path(output).resolve()
 if out.exists() or not out.is_relative_to(PRIVATE):raise ValueError('Fresh private output required')
 sim=PRIVATE/'simulator';parent=Path(__file__).parent
 paths={n:parent/n for n in ('sram_payload_policy.py','recovery_power_response.py','renode-sram-payload-gate.cs')}
 if not paths['sram_payload_policy.py'].exists():paths={n:parent/'sources'/n for n in paths}
 bind_sram=functions(paths['sram_payload_policy.py'],('bind',))['bind'];bind_power=functions(paths['recovery_power_response.py'],('bind',))['bind'];gate=paths['renode-sram-payload-gate.cs'].read_text();base=sim/'recovery-checksum-strict-native-bw580-03';expected_model=bind_power(bind_sram((base/'strict.cs').read_text(),gate));checks={};records=[];reports={}
 names=[('recovery-checksum-run-native-bw581-01','checksum',True),('recovery-checksum-run-native-bw581-02','checksum',True),('recovery-bad-crc-native-bw581-01','bad-crc',False),('recovery-tamper-native-bw581-01','tamper',False),('recovery-stock-reference-native-bw581-01','stock',False)]
 for name,kind,executed in names:
  d=sim/name;m=read(d/'manifest.json');r=read(d/'report.json');p=read(d/'recovery-plan.json');reports[kind if kind!='checksum' else name]=r;prefix=name+':'
  checks[prefix+'components']=all(sha(d/k)==v for k,v in m['components'].items())
  checks[prefix+'same_bound_model']=(d/'strict.cs').read_text()==expected_model
  board=(base/'board.repl').read_text().replace('iom7_power: Miscellaneous.BlackwallPeripheralPower\n','iom7_power: Miscellaneous.BlackwallPeripheralPower\n    synchronousOffResponse: true\n');checks[prefix+'only_power_option']=board==(d/'board.repl').read_text()
  code=bytes(p['payload_bytes']);checks[prefix+'approved_image']=len(code)==48 and hashlib.sha256(code).hexdigest()==p['payload_sha256']=='4bbd4bfbd4f403b9da4967da4a88b23d61f99f00e523cd527262ce10347fc4ac' and p['expected_crc32']==0xa0fd4d3f
  wire_code=b''.join(bytes(x[10:26]) for x in p['packets'][1:4]);crc=struct.unpack_from('<I',bytes(p['packets'][0]),21)[0]
  checks[prefix+'wire_crc_contract']=crc==(zlib.crc32(wire_code)^(1 if kind=='bad-crc' else 0)) and (wire_code!=code if kind=='tamper' else wire_code==code)
  checks[prefix+'explicit_profile']=m['allow_checksum_sram'] and m['synchronous_iom7_off'] and m['watchdog_initial_fixture']=='matching-running' and not m['hardware_accessed']
  runtime=(d/'run.py').read_text();checks[prefix+'bind_before_attach']=runtime.index('policy.BindSramPayload(')<runtime.index('policy.Attach()') and 'bus.Write' not in runtime and 'SetRegister' not in runtime
  checks[prefix+'firmware_unchanged']=r['images_unchanged'] and m['main_sha256']=='69f9ef63997c9bb53e5b97f83cc330e93651577ab1595ac57dcb481c3e513b9c' and m['boot_sha256']==('22a2b98e606b4d296e957a3a8b600a2158497638d79485c817c2025536329ba7' if kind=='stock' else '7010d103d02a49333362ec185fb04c9657626f97cec5240063375d1c52e55a7e')
  checks[prefix+'no_fault_or_unmapped']=r['cfsr']==r['hfsr']==r['system_control_violations']==r['events_dropped']==0 and not r['engine_unmapped_access']
  g=r['sram_payload'];checks[prefix+'execution_gate']=g['length']==48 and ((g['approvals']==1 and g['base']==0x2001c7a0 and g['blocks']>0 and g['word_validations']>0 and g['rejections']==0) if executed else (g['approvals']==0 and g['base']==0 and g['blocks']==0))
  if kind=='tamper':checks[prefix+'rejected_before_first_instruction']=r['classification']=='unsupported-model' and r['policy']==1 and r['policy_operation']=='execute-outside-code' and r['policy_address']==r['pc']==0x2001c7a0 and g['rejections']==1 and not r['recovery_command']['completed']
  else:checks[prefix+'main_clean']=r['classification']=='main-entered' and r['scope']['main_entered'] and not r['machine_aborted'] and r['policy']==0 and not any(x['accesses'] for x in r['guards'])
  if kind=='stock':
   checks[prefix+'stock_control']=not r['scope']['worker_entered'] and not r['scope']['authentication_verified'] and len(r['uart2_tx'])==r['virtual_peer']['rx_injected']==0 and not r['recovery_command']['replies']
   checks[prefix+'peer_disabled']='pass # silent stock reference: no external protocol input' in runtime and m['stock_reference'] and m['boot_image_bytes']==149760
  else:
   tx=bytes(r['uart2_tx']);challenge=struct.unpack_from('<I',tx,16)[0];tag=lambda marker:hmac.digest(b'DEFAULTNOTSECRET',b'G2BOOT'+struct.pack('<II',2,challenge)+marker,'sha256')[:16]
   body=bytes([0,1,3,20])+b'OKAY'+tag(b'OKAY');okay=b'\x5a\xa5\xff'+bytes([len(body)])+body+bytes([(len(body)-2+sum(body))&255]);checks[prefix+'actual_auth']=tx[21:50]==okay and r['virtual_peer']['held']['words']==[1,0,1,0]
   replies=p['responses'][:4] if kind=='tamper' else p['responses'];released=bytes([90,165,255,8,0,1,3,4,82,76,83,68,67]);checks[prefix+'real_wire_result']=tx[50:]==b''.join(bytes(x) for x in replies)+(b'' if kind=='tamper' else released)
   hold=bytes([0x7e,0,1,20])+b'HOLD'+tag(b'HOLD');wire=hold+bytes([(len(hold)+1+0x7d+sum(hold))&255])+b''.join(bytes(x) for x in p['packets'])
   if kind!='tamper':b=bytes([0x7e,0,1,4])+b'CONT';wire+=b+bytes([(len(b)+1+0x7d+sum(b))&255])
   h=14695981039346656037
   for b in wire:h=((h^b)*1099511628211)&0xffffffffffffffff
   v=r['virtual_peer'];checks[prefix+'actual_rx']=v['rx_injected']==v['rx_read']==len(wire) and v['rx_hash']==h and v['rx_pending']==v['rx_discarded']==0
   if kind=='bad-crc':checks[prefix+'crc_rejection']=[(x['kind'],x['status']) for x in r['recovery_command']['replies']]==[(0,0),(0,0),(0,0),(4,3),(4,1)] and r['recovery_cache']['clean_pou']==0
  if executed:checks[prefix+'actual_crc_result']=r['recovery_command']['completed'] and r['recovery_cache']['clean_pou']==2 and struct.unpack_from('<I',bytes(p['responses'][-1]),14)[0]==0xa0fd4d3f
  checks[prefix+'removed']=read(d/'native.process.json')['status']=='removed' and all(not (d/x['path']).exists() for x in r['cleanup'])
  records.append(dict(name=name,mode=kind,ram_diagnostic_verified=executed,main=r['scope']['main_entered'],report_sha256=sha(d/'report.json'),nonzero_mram_recovery_verified=False))
 a=reports['recovery-checksum-run-native-bw581-02'];b=reports['stock'];checks['stock_main_context_exact']=next(x for x in a['contexts'] if x['label']=='main-reset')==next(x for x in b['contexts'] if x['label']=='main-reset')
 checks['normal_repeat_same_result']=reports['recovery-checksum-run-native-bw581-01']['recovery_command']['expected_crc32']==a['recovery_command']['expected_crc32']==0xa0fd4d3f
 for name,passed,marker in [('sram-payload-gate-red-bw581-01',False,None),('sram-payload-gate-green-bw581-02',True,'BLACKWALL_PAYLOAD_GATE 26'),('recovery-power-red-bw581-01',False,None),('recovery-power-green-bw581-01',True,'BLACKWALL_RECOVERY_POWER 24')]:
  d=sim/name;r=read(d/'report.json');checks[name]=r['passed']==passed and (marker is None or r['marker']==[marker]) and read(d/'native.process.json')['status']=='removed'
 result=dict(passed=all(checks.values()),checks=checks,cases=records,ram_diagnostic_verified=True,nonzero_mram_recovery_verified=False,bv06_complete=False,physical_compatibility=False,scope='Original UART LOAD/RUN readonly checksum/result/CONT/main + CRC rejection + tamper denial + stock original reference. Actual nonzero MRAM recovery still pending; historical raw recovery_verified flags denote diagnostic protocol only.')
 out.mkdir(parents=True,mode=0o700);(out/'sources').mkdir()
 for name,p in paths.items():shutil.copy2(p,out/'sources'/name)
 shutil.copy2(__file__,out/'audit-source.py');(out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=result['passed'],checks=len(checks),failed=[k for k,v in checks.items() if not v])))
 if not result['passed']:raise ValueError('Bounded recovery audit failed')
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);audit(p.parse_args().output)
