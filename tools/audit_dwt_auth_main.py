"""Audit synthetic DWT/PMIC initial state and complete same-board UART2 auth cases."""
import argparse,hashlib,hmac,json,shutil,struct
from pathlib import Path
PRIVATE=Path.home()/'Library/Application Support/Blackwall'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def request(marker,payload=b''):
 b=bytes([0x7e,0,1,4+len(payload)])+marker+payload;return b+bytes([(len(b)+1+0x7d+sum(b))&255])
def announcement(marker,payload=b''):
 b=bytes([0,1,3,4+len(payload)])+marker+payload;return b'\x5a\xa5\xff'+bytes([len(b)])+b+bytes([(len(b)-2+sum(b))&255])
def fnv(b):
 v=14695981039346656037
 for x in b:v=((v^x)*1099511628211)&0xffffffffffffffff
 return v

def audit(output):
 out=Path(output).resolve()
 if out.exists() or not out.is_relative_to(PRIVATE):raise ValueError('Fresh private output required')
 sim=PRIVATE/'simulator';base=sim/'boot-retention-auth-native-bw578-01';checks={};records=[]
 cases=[('good-cont','dwt-auth-main-native-bw579-04',True,True),('good-cont','dwt-auth-mismatch-native-bw579-01',True,False),('bad-only','dwt-auth-bad-native-bw579-01',False,False),('silent','dwt-auth-silent-native-bw579-01',False,False),('bad-then-good','dwt-auth-retry-native-bw579-01',True,True),('partial-timeout-good','dwt-auth-partial-native-bw579-01',True,True)]
 for case,name,authed,kicked in cases:
  d=sim/name;r=read(d/'report.json');m=read(d/'manifest.json');v=r['virtual_peer'];w=r['watchdog_platform'];initial=r['watchdog_initial_snapshot'];key=name+':';mismatch='mismatch' in name;target=0x3c01 if mismatch else 0x3c00
  checks[key+'components']=all(sha(d/k)==v for k,v in m['components'].items())
  checks[key+'same_model']=(d/'strict.cs').read_bytes()==(base/'strict.cs').read_bytes()
  board=(base/'board.repl').read_text().replace('pointerProbe: Miscellaneous.BlackwallPmicTimedProbe @ iom7 0x6b\n','pointerProbe: Miscellaneous.BlackwallPmicTimedProbe @ iom7 0x6b\n    recoveryReadHoleMock: 0\n')+'\nboot_dwt: Miscellaneous.DWT @ sysbus 0xe0001000\n    frequency: 10000000\n';checks[key+'only_board_options']=board==(d/'board.repl').read_text()
  runtime=(base/'run.py').read_text().replace("PEER_CASE='good-cont'\n",'PEER_CASE='+repr(case)+'\n')
  anchor="observer.AddPoint('peer-receive',0x4353e4)";runtime=runtime.replace(anchor,anchor+"\nobserver.AddPoint('watchdog-feed',0x434978)\nobserver.AddPoint('watchdog-command',0x434ad0)\nobserver.AddPoint('watchdog-feed-return',0x434a3e)")
  setup="q=m['sysbus.iom7.pointerProbe']\ndef initial_pmic(data):\n q.Write(Array[Byte](data));q.FinishTransmission()\ninitial_pmic([7,5,10])\ninitial_pmic([7,8,0,"+str(target>>8)+","+str(target&255)+"])\ninitial_pmic([7,3,1])\ninitial_pmic([7,0,1])\nif not q.Timer.Running or not q.Timer.ConfigKnown or not q.Timer.TargetKnown or int(q.Timer.Target)!="+str(target)+":raise Exception('Invalid explicit PMIC initial state')\nwatchdog_initial_snapshot=dict(target=int(q.Timer.Target),running=bool(q.Timer.Running),kicks=int(q.Timer.Kicks),timer_writes=int(q.TimerWrites),cpu_instructions=int(cpu.ExecutedInstructions))\n"
  runtime=runtime.replace(anchor,setup+anchor)
  extra="result['watchdog_platform']=dict(dwt_ctrl=int(m['sysbus.boot_dwt'].ReadDoubleWord(0)),dwt_cycles=int(m['sysbus.boot_dwt'].ReadDoubleWord(4)),iom_commands=int(m['sysbus.iom7'].Commands),iom_accesses=int(m['sysbus.iom7'].AccessCount),iom_last=str(m['sysbus.iom7'].LastOperation),pmic_accesses=int(m['sysbus.iom7.pointerProbe'].AccessCount),pmic_last=str(m['sysbus.iom7.pointerProbe'].LastOperation),kicks=int(m['sysbus.iom7.pointerProbe'].Timer.Kicks))\nresult['watchdog_initial_snapshot']=watchdog_initial_snapshot\n"
  runtime=runtime.replace("result['machine_aborted']=",extra+"result['machine_aborted']=");checks[key+'only_declared_runtime']=runtime==(d/'run.py').read_text()
  checks[key+'initial_before_cpu']=initial==dict(kicks=0,running=True,target=target,cpu_instructions=0,timer_writes=4)
  checks[key+'synthetic_manifest']=m['synthetic_chip_revision']==0x21 and m['synthetic_trim']==1 and m['dwt_frequency_hypothesis']==10000000 and m['pmic_ignored_read_holes_mock']==0 and m['watchdog_initial_fixture']==('mismatch-running' if mismatch else 'matching-running') and not m['hardware_accessed'] and not m['physical_chip_revision_observed']
  checks[key+'main_clean']=r['classification']=='main-entered' and r['scope']['main_entered'] and not r['machine_aborted'] and not r['engine_unmapped_access'] and r['cfsr']==r['hfsr']==r['policy']==r['system_control_violations']==r['events_dropped']==0 and not any(g['accesses'] for g in r['guards'])
  checks[key+'original_images']=r['images_unchanged'] and m['boot_sha256']=='7010d103d02a49333362ec185fb04c9657626f97cec5240063375d1c52e55a7e' and m['main_sha256']=='69f9ef63997c9bb53e5b97f83cc330e93651577ab1595ac57dcb481c3e513b9c'
  tx=bytes(r['uart2_tx']);challenge=struct.unpack_from('<I',tx,16)[0];tag=lambda marker:hmac.digest(b'DEFAULTNOTSECRET',b'G2BOOT'+struct.pack('<II',2,challenge)+marker,'sha256')[:16]
  hold=request(b'HOLD',tag(b'HOLD'));bad=bytearray(hold);bad[8]^=1;bad[-1]=(len(bad)+0x7d+sum(bad[:-1]))&255
  wire={'good-cont':hold,'bad-only':bytes(bad),'silent':b'','bad-then-good':bytes(bad)+hold,'partial-timeout-good':hold[:8]+hold}[case]+(request(b'CONT') if authed else b'')
  expected=announcement(b'HELO',struct.pack('<II',2,challenge))+(announcement(b'OKAY',tag(b'OKAY'))+announcement(b'RLSD') if authed else b'')
  checks[key+'wire_and_rx']=tx==expected and v['rx_read']==v['rx_injected']==len(wire) and v['rx_hash']==fnv(wire) and v['rx_pending']==v['rx_discarded']==0
  checks[key+'auth_decision']=r['scope']['authentication_verified']==v['accepted']==authed and (not authed or v['held']['words']==[1,0,1,0]) and not r['scope']['recovery_verified']
  checks[key+'external_input_paused']=all(e['machine_paused'] for e in v['events'])
  checks[key+'watchdog_outcome']=w['kicks']==int(kicked) and w['iom_commands']==(3 if kicked else 2 if authed else 0) and w['dwt_ctrl']==w['iom_accesses']==w['pmic_accesses']==0
  points={x['label']:x for x in r['points']};returns=[e for e in r['events'] if e['label']=='watchdog-feed-return'];checks[key+'real_feed_return']=len(returns)==int(authed) and (not authed or returns[0]['r0']==int(kicked) and returns[0]['sequence']<points['main-reset']['first']) and points['watchdog-feed']['hits']==int(authed)
  checks[key+'power_cleanup']=next(x for x in r['power_owners']['ioms'] if x['module']==7)['status']==0
  if case=='bad-only':checks[key+'wrong_hmac_unclaimed']=next(e['session']['words'] for e in v['events'] if e['kind']=='rejected-window')==[0,0,0,0]
  if case in ('bad-then-good','partial-timeout-good'):
   e=next(e for e in v['events'] if e['kind']=='retry');checks[key+'retry']=e['session']['words']==[0,0,0,0] and e['wait_ticks']>=(128 if case=='partial-timeout-good' else 10) and points['peer-receive']['hits']==3
  log=(d/'native.log').read_text();checks[key+'engine_log_clean']=not any(s in log.lower() for s in ('[error]','non existing','non-existing','error executing','unhandled','blackwall_runtime_error'))
  checks[key+'removed']=read(d/'native.process.json')['status']=='removed' and all(not (d/x['path']).exists() for x in r['cleanup'])
  records.append(dict(case=case,initial_target=target,authentication=authed,watchdog_kicks=int(kicked),main=True,report_sha256=sha(d/'report.json')))
 unit=read(sim/'boot-dwt-unit-bw579-01/report.json');checks['native_dwt_unit']=unit['passed'] and unit['count']==10 and not unit['physical_cycle_accuracy']
 for name in ('dwt-auth-main-native-bw579-02','dwt-auth-main-native-bw579-03'):
  r=read(sim/name/'report.json');checks[name+'_unknown_still_stops']=r['classification']=='engine-aborted' and r['watchdog_platform']['pmic_last']=='timer-read-unknown' and r['watchdog_platform']['kicks']==0 and not r['scope']['main_entered'] and not r['engine_unmapped_access']
 checks['ignored_fields_all65536']=all(((0x0a|(value<<8))&0xff0000ff)==0x0a for value in range(65536))
 source=sim/'upstream/renode-infrastructure-bw567/src/Emulator/Cores/Arm-M/DWT.cs';checks['dwt_source_pin']=sha(source)=='646fe41e6325da8cbc6b420da87e9085b534c2e635a79d3de5b24c5436a0c216'
 result=dict(passed=all(checks.values()),checks=checks,cases=records,bv05_virtual_criteria_met=True,bv06_recovery_command_completed=False,physical_compatibility=False,physical_cycle_accuracy=False,scope='Original same-board reset/worker, UART auth normal/bad/timeout/retry, real watchdog kick/rejection and main. Explicit running PMIC fixture and ignored-byte zero mock; unknown initial state stays unsupported.')
 out.mkdir(parents=True,mode=0o700);shutil.copy2(__file__,out/'audit-source.py');(out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=result['passed'],checks=len(checks),failed=[k for k,v in checks.items() if not v])))
 if not result['passed']:raise ValueError('DWT/auth/main audit failed')
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);audit(p.parse_args().output)
