"""Audit saved watchdog gate/lifecycle and actual original reset-entry artifacts."""
import argparse,json,hashlib,tempfile
from pathlib import Path
from probe_watchdog_reset_entry import build

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def entry_checks(r):
 return dict(original_vector_entry=r['seen'] is True and r['pc']==r['expected_pc'] and r['sp']==r['expected_sp'] and r['vtor']==0x438000,single_delivery=r['deliveries']==r['nvic_resets']==1 and r['pending'] is False,cause=r['boot_status']==64,fresh_watchdog=r['watchdog_configuration']==0,no_fault=r['memory_violations']==r['cfsr']==r['hfsr']==0,declared_limits=r['host_pc_register_seed'] is False and r['main_only_virtual_boot_contract'] is True and r['bootrom_executed'] is False and r['hardware_accessed'] is False and r['guest_status_mapped'] is False)
def verify(s,out):
 if out.exists():raise ValueError('Fresh audit required')
 cap=s/'watchdog-reset-entry-native-02';r=read(cap/'exports/watchdog-reset-entry.json');checks=entry_checks(r);inputs=read(cap/'connection-inputs.json')
 with tempfile.TemporaryDirectory(dir=s,prefix='watchdog-reset-audit-') as t:
  p=Path(t)/'inputs';build(s,p);checks['regenerated_recipe']=all((p/n).read_bytes()==(cap/n).read_bytes() for n in inputs) and read(p/'connection-inputs.json')==inputs
 checks['input_pins']=all(sha(cap/n)==h for n,h in inputs.items())
 checks['original_main']=sha(cap/'main.bin')=='df8cfddf3bd29a8351129a8364a8e0dafb347ffc7bfcbca5b52fdd973a7cce4a'
 unit=read(s/'watchdog-reset-delivery-unit-02/report.json');life=read(s/'watchdog-reset-delivery-lifecycle-01/report.json');red=read(s/'watchdog-reset-delivery-red-02/report.json')
 rows=unit['cases']+life['cases']
 checks['all_gates']=sorted(c['gate'] for c in unit['cases'])==[0,1,2,3]
 checks['unit_and_lifecycle']=all(all(c['checks'].values()) for c in rows) and unit['passed'] and life['passed']
 checks['baseline_red']=red['passed'] is False and red['cases'][0]['checks']['boot_count'] is False and red['cases'][0]['observed']['words'][0]==1
 logs=[]
 for path,report in [(s/'watchdog-reset-delivery-unit-02',unit),(s/'watchdog-reset-delivery-lifecycle-01',life)]:
  for c in report['cases']:
   logged=[json.loads(l.split('BLACKWALL_WDT_RESET ',1)[1]) for l in (path/('gate-'+str(c['gate']))/'renode.log').read_text().splitlines() if l.startswith('BLACKWALL_WDT_RESET ')]
   logs.append(logged==(c.get('lifecycle_rows') or [c['observed']]))
 checks['unit_log_equality']=all(logs)
 parent=s/'watchdog-natural-request-native-01'
 checks['prefix_sram_exact']=all((cap/n).read_bytes()==(parent/n).read_bytes() for n in ['exports/sram-full.bin','exports/connected-sram.bin','exports/connection-sram.bin'])
 frontier=read(cap/'exports/timeout-frontier.json');checks['strict_guards_clean']=not any(x['accesses'] for x in frontier['guards'])
 if not all(checks.values()):raise ValueError({k:v for k,v in checks.items() if not v})
 negatives=[]
 for name,key,value in [('missing-delivery','deliveries',0),('wrong-cause','boot_status',4096),('physical-boot-claim','bootrom_executed',True)]:
  bad=dict(r);bad[key]=value
  if all(entry_checks(bad).values()):raise ValueError('Accepted '+name)
  negatives.append(dict(case=name,rejected=True))
 result=dict(passed=True,checks=checks,unit_assertions=sum(len(c['checks']) for c in rows),negatives=negatives,entry=r,g2_service_restart_verified=False,e06_complete=False,hardware_accessed=False)
 out.mkdir(mode=0o700,parents=True);(out/'report.json').write_text(json.dumps(result,indent=2)+'\n');return result
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();r=verify(a.simulator,a.output);print(json.dumps(dict(passed=True,checks=len(r['checks']),unit_assertions=r['unit_assertions'],negatives=len(r['negatives']))))
