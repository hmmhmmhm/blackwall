"""Audit actual watchdog reset followed by original services and a fresh ATT time action."""
import argparse,hashlib,json,tempfile
from pathlib import Path
from probe_watchdog_restart import build
from verify_watchdog_reset_capture import entry_checks

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def clean(r):
 return r['cfsr']==r['hfsr']==0 and not any(x['accesses'] for x in r['guards']) and (r.get('memory_violations',r.get('memory',{}).get('violations'))==0)

def app_checks(r):
 return dict(app_return=r['stopped'] is True and r['pc']==0x492ce2 and len(r['returns'])==len(r['applied'])==len(r['consumers'])==len(r['inputs'])==1,rtc_reapplied=r['rtc']['commits']==1 and r['rtc']['pending'] is False and r['rtc']['date'].startswith('2023-11-14T22:13:20.'),fresh_peer=r['peer']['commands']==59 and r['peer']['events']==3 and r['peer']['state']=='Complete',single_watchdog_reset=r['watchdog_deliveries']==r['nvic_reset_count']==1,no_fault=clean(r),no_execution_bypass=r['host_pc_register_seed'] is False and r['original_firmware_executed'] is True and r['hardware_accessed'] is False)

def verify(s,out):
 if out.exists():raise ValueError('Fresh output required')
 base=s/'watchdog-restart-native-01';cap=s/'watchdog-restart-native-03';a=read(base/'exports/watchdog-restart.json');b=read(cap/'exports/watchdog-restart.json');app=read(cap/'exports/restart-app.json');connection=read(cap/'exports/restart-connection.json')
 entries=[read(x/'exports/watchdog-reset-entry.json') for x in (base,cap)]
 checks=dict(original_reset_entries=all(all(entry_checks(e).values()) for e in entries),baseline_strict_boundary=not a['held'] and a['pc']==0x4956e2 and a['cfsr']==a['hfsr']==a['memory_violations']==0 and [(g['name'],g['address'],g['width'],g['value'],g['operation']) for g in a['guards'] if g['accesses']]==[('ppb_guard',0xe001e300,4,0x22,'write')],service_restarted=b['held'] and b['pc']==0x5542c6 and clean(b),new_service_epoch=b['peer']==dict(state='Complete',commands=59,runtime_events=0) and b['rtc']['commits']==0 and b['rtc']['date'].startswith('2000-01-01') and b['wdt_configuration']==0x020ce005 and b['wdt_restarts']>0,new_connection=connection['accepted'] is True and connection['stopped'] is True and connection['peer']['events']==1 and clean(connection),single_reset=b['deliveries']==b['nvic_resets']==1)
 checks.update(app_checks(app))
 activation=(cap/'activation.cs').read_text();runtime=(cap/'run.py').read_text()
 checks['completed_pause_handoff']=activation.count('callback=(c,a)=>{machine.Pause();Seen=true;};')==1 and 'while not reset_entry_observer.Seen and not m.IsAborted and time.time()<deadline' in runtime and read(cap/'watchdog-restart-profile.json')['completed_entry_pause'] is True
 diag=s/'watchdog-restart-diagnostics-01';stacks=read(diag/'thread-stacks.json');text={x['thread']:'\n'.join(x['deepest_stack']) for x in stacks}
 checks['actual_deadlock_trace']='Thread.Join()' in text['Thread (22)'] and 'BlackwallResetEntryObserver' in text['Thread (38)'] and 'Core.Machine.Pause()' in text['Thread (38)'] and 'TimeHandle.WaitUntilDone' in text['Thread (31)'] and read(diag/'target-termination.json')['returncode']==0
 smoke=read(s/'reset-entry-pause-order-unit-01/report.json');checks['synthetic_pause_smoke']=smoke['passed'] is True and smoke['completed'] is True

 for n,retention,restart in [('watchdog-restart-native-01',False,False),('watchdog-restart-native-03',True,True)]:
  c=s/n;inputs=read(c/'connection-inputs.json')
  checks[n+'_pins']=all(sha(c/f)==h for f,h in inputs.items())
  with tempfile.TemporaryDirectory(dir=s,prefix='watchdog-restart-audit-') as t:
   p=Path(t)/'prepared';build(s,p,retention,restart,completed_entry_pause=retention);checks[n+'_recipe']=all((p/f).read_bytes()==(c/f).read_bytes() for f in inputs) and read(p/'connection-inputs.json')==inputs
  checks[n+'_original_main']=sha(c/'main.bin')=='df8cfddf3bd29a8351129a8364a8e0dafb347ffc7bfcbca5b52fdd973a7cce4a'
 log=(cap/'renode.log').read_text();expected=[('BLACKWALL_WATCHDOG_RESTART ',b),('BLACKWALL_RESTART_CONNECTION ',connection),('BLACKWALL_RESTART_APP ',app)]
 checks['log_equality']=all([json.loads(l.split(marker,1)[1]) for l in log.splitlines() if l.startswith(marker)]==[value] for marker,value in expected)
 # Compare rather than assume observer/model equivalence before reset.
 prefix=[]
 for n in ['sram-full.bin','connected-sram.bin','connection-sram.bin','frozen-core-sram.bin']:
  x=(base/'exports'/n).read_bytes();y=(cap/'exports'/n).read_bytes();prefix.append(dict(file=n,exact=x==y,different_bytes=sum(a!=b for a,b in zip(x,y)),same_size=len(x)==len(y)))
 if not all(checks.values()):raise ValueError({k:v for k,v in checks.items() if not v})
 negatives=[]
 for name,key,value in [('missing-rtc-commit','rtc',dict(app['rtc'],commits=0)),('stale-peer-session','peer',dict(app['peer'],events=0)),('extra-reset','watchdog_deliveries',2)]:
  bad=dict(app);bad[key]=value
  if all(app_checks(bad).values()):raise ValueError('Accepted '+name)
  negatives.append(dict(case=name,rejected=True))
 result=dict(passed=True,checks=checks,negatives=negatives,prefix_comparison=prefix,original_watchdog_app_action_verified=True,full_initialization_complete=False,e06_complete=False,hardware_accessed=False)
 out.mkdir(mode=0o700,parents=True);(out/'report.json').write_text(json.dumps(result,indent=2)+'\n');return result
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();r=verify(a.simulator,a.output);print(json.dumps(dict(passed=True,checks=len(r['checks']),negatives=len(r['negatives']),prefix=r['prefix_comparison'])))
