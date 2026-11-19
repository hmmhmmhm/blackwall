"""Audit original firmware device reset entry separately from application recovery."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

MAIN_SHA={'stock24':'df8cfddf3bd29a8351129a8364a8e0dafb347ffc7bfcbca5b52fdd973a7cce4a','stock23':'fffbf74b3439bf0e4752fb620a7990d0a133898c54f6fb08005ea6b7029655c5','cfw':'4118af85ebb8e634493a61a3ce4a62ae37451e17cea6d0b8b08465f29538dd8f'}

def sha(data):return hashlib.sha256(data).hexdigest()

def read(p):return json.loads(p.read_text())

def clean(s):return not any(v['accesses'] for v in s['guards']) and s['cfsr']==s['hfsr']==s['memory']['violations']==s['system_control']['violations']==0

def log_values(cap,prefix):return [json.loads(x[len(prefix)+1:]) for x in (cap/'renode.log').read_text().splitlines() if x.startswith(prefix+' ')]

def verify(cap,out,staged_retention=False):
    p=read(cap/'connection-profile.json');r=read(cap/'exports/system-reset-entry.json');a=read(cap/'exports/system-reset-after.json');b=r['before'];e=r['entry'];raw=(cap/'main.bin').read_bytes();sp,entry=struct.unpack_from('<II',raw);entry&=~1
    conn=read(cap/'exports/connection.json');inputs=read(cap/'connection-inputs.json')
    checks=dict(original_main=sha(raw)==MAIN_SHA[p['case']],inputs_pinned=all(sha((cap/n).read_bytes())==v for n,v in inputs.items()),att_return_before_reset=conn['att']['stopped'] and conn['att']['rtc']['commits']==1 and b['pc']==p['service']['consumer_return'] and b['rtc']['commits']==1,entry_is_original_vector=r['entry_seen'] and r['expected_entry']==e['pc']==entry and r['expected_sp']==e['sp']==sp and e['vtor']==0x438000,actual_reset_count=b['nvic_reset_count']==0 and e['nvic_reset_count']==a['nvic_reset_count']==1,device_reset_input=r['request']==dict(address=0xe000ed0c,value=0x05fa0004,origin='external virtual NVIC device input'),no_pc_register_seed=r['host_pc_or_register_seed'] is False,original_not_synthetic=r['original_firmware_executed'] is True and r['hardware_accessed'] is False,basepri_cleared=e['basepri']==a['basepri']==0,clean_entry_and_first_slice=all(clean(s) for s in (b,e,a)),rtc_existing_reset_observed=e['rtc']['commits']==a['rtc']['commits']==0 and e['rtc']['date']=='2000-01-01T00:00:00.00',peer_reset=b['peer']['commands']==59 and b['peer']['events']==3 and e['peer']==dict(state='Unreleased',commands=0,events=0),itcm_backing_retained=b['itcm_sha256']==e['itcm_sha256']==a['itcm_sha256'],memory_policy_history_retained=b['memory']['written']==e['memory']['written']==a['memory']['written'] and b['memory']['written']>0,initialization_executed=a['ticks']-e['ticks']>=20000000 and a['pc']!=entry,entry_log=log_values(cap,'BLACKWALL_ORIGINAL_RESET_ENTRY')==[dict(seen=True,pc=e['pc'],resets=1)],after_log=log_values(cap,'BLACKWALL_ORIGINAL_RESET_AFTER')==[a])
    differences=None
    if 'nor_kv_sha256' in b:
        checks['kv_nor_retained']=len({s['nor_kv_sha256'] for s in (b,e,a)})==1
        checks['pio_idle_reset']=all(not s[k] for s in (b,e,a) for k in ('pio_busy','pio_program_busy','pio_erase_busy'))
        for phase,state in (('before',b),('entry',e),('after',a)):
            data=(cap/'exports'/('system-reset-'+phase+'-sram.bin')).read_bytes()
            checks['sram_capture_'+phase]=len(data)==0x380000 and sha(data)==state['sram_sha256']
        old=(cap/'exports/system-reset-before-sram.bin').read_bytes();new=(cap/'exports/system-reset-entry-sram.bin').read_bytes();delta=[i for i,(x,y) in enumerate(zip(old,new)) if x!=y]
        differences=dict(count=len(delta),bytes=[dict(address=0x20000000+i,before=old[i],entry=new[i]) for i in delta],reset_request_to_entry_ticks=e['ticks']-b['ticks'],interpretation='includes execution between asynchronous request and reset; not pure reset memory retention proof')
    later_path=cap/'exports/system-reset-later.json';later=read(later_path) if later_path.exists() else None
    if later is not None:
        checks['later_log']=log_values(cap,'BLACKWALL_ORIGINAL_RESET_LATER')==[later]
        checks['later_snapshot']=sha((cap/'exports/system-reset-later-sram.bin').read_bytes())==later['sram_sha256']
        if p['case']!='stock24':raise ValueError('Later reset frontier is only verified for stock24')
        code=raw[0x4956ca-0x438000:0x4956e4-0x438000]
        stack=(cap/'exports/system-reset-later-sram.bin').read_bytes()[later['sp']-0x20000000:later['sp']-0x20000000+3]
        value=(stack[0]<<8)|(stack[1]<<4)|stack[2]
        checks['original_cpd_store_contract']=code.hex()=='9df8000051ea00219df8010051ea00119df8020001437e480160' and struct.unpack_from('<I',raw,0x4958dc-0x438000)[0]==0xe001e300
        if staged_retention:
            checks['qualified_retention_return']=later.get('retention_return_seen') is True and later['pc']==0x44df60 and later.get('cpd_value')==0x22 and later.get('retention_stages')==1 and clean(later) and not later['held']
        else:
            checks['declared_cpd_frontier']=code.hex()=='9df8000051ea00219df8010051ea00119df8020001437e480160' and struct.unpack_from('<I',raw,0x4958dc-0x438000)[0]==0xe001e300 and value==0x22 and later['pc']==0x4956e2 and not later['held'] and later['cfsr']==later['hfsr']==later['memory']['violations']==0 and [(v['name'],v['address'],v['accesses']) for v in later['guards'] if v['accesses']]==[('ppb_guard',0xe001e300,1)]
    if not all(checks.values()):raise ValueError({k:v for k,v in checks.items() if not v})
    report=dict(passed=True,checks=checks,case=p['case'],scope='original application to device reset and bounded initialization/configuration slice; app recovery unproven',staged_retention=staged_retention,original_main_sha256=sha(raw),reset_entry=entry,initial_sp=sp,sram_request_to_entry=differences,later=later,g2_application_restart_verified=False,e06_complete=False,physical_hardware_access=False)
    out.mkdir(mode=0o700,parents=True,exist_ok=False);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');return report

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('capture',type=Path);p.add_argument('output',type=Path);p.add_argument('--staged-retention',action='store_true');a=p.parse_args();r=verify(a.capture,a.output,a.staged_retention);print(json.dumps(dict(passed=True,checks=len(r['checks']),e06_complete=False,later_pc=hex(r['later']['pc']) if r['later'] else None)))
if __name__=='__main__':main()
