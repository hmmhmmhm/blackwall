"""Audit the observed controller-version frontier; never call it a GAF timeout."""
import argparse,hashlib,json,struct,tempfile
from pathlib import Path
from probe_gaf_natural_timeout import build

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def logged(cap,label):return [json.loads(l[len(label)+1:]) for l in (cap/'renode.log').read_text().splitlines() if l.startswith(label+' ')]

def verify(s,out):
 if out.exists():raise ValueError('Fresh audit output required')
 first=s/'gaf-natural-timeout-native-01';cap=s/'gaf-natural-timeout-native-03';parent=s/'main-read-routing-pilot-01/01-baseline'
 f=read(cap/'exports/frozen-core.json');a=read(cap/'exports/natural-timeout.json');d=read(cap/'exports/timeout-frontier.json');p=read(cap/'connection-profile.json');meta=read(cap/'natural-timeout-source.json');raw=(cap/'main.bin').read_bytes();ram=(cap/'exports/frozen-core-sram.bin').read_bytes();regs=d['registers'];tcb=d['tcb'];offset=tcb-0x20000000
 inputs=read(cap/'connection-inputs.json');name=ram[offset+52:offset+84].split(b'\0',1)[0].decode();packet=bytes(d['buffers']['10']['bytes'][:4]);addr=d['buffers']['10']['address']
 with tempfile.TemporaryDirectory(dir=s,prefix='timeout-input-audit-') as temporary:
  generated=Path(temporary)/'prepared';build(s,generated)
  regenerated=all((generated/n).read_bytes()==(cap/n).read_bytes() for n in inputs) and read(generated/'connection-inputs.json')==inputs
 checks=dict(inputs_pinned=all(sha(cap/n)==h for n,h in inputs.items()),original_main=sha(cap/'main.bin')=='df8cfddf3bd29a8351129a8364a8e0dafb347ffc7bfcbca5b52fdd973a7cce4a',original_loop_limit=struct.unpack_from('<I',raw,0x5559c0-0x438000)[0]==1000000 and meta['timeout_poll_limit']==200000 and meta['delay_us']==5,real_caller_boundary=meta['continuation']==0x55496e and meta['request_helper']==0x55405c,not_timeout=a['seen'] is False and a['stop_reason']==f['stop_reason']=='device-or-guard-pause' and not f['rows'] and a['r0']==0,actual_partial_polling=f['busy_reads']==11059 and f['requests']==f['triggers']==1,calculation_not_faked=f['completed_calculations']==0 and f['calculation_supported'] is False and f['ram_reads']==f['ram_written_bytes']==0,guard_not_fault=f['cfsr']==f['hfsr']==f['memory_violations']==0 and [(g['name'],g['accesses'],g['address']) for g in f['guards'] if g['accesses']]==[('guard',1,0x40010410)],frontier_pc=regs[15]==f['pc']==0x501676,original_wsf_thread=name=='ble_wsf' and d['xpsr']&511==0 and struct.unpack_from('<I',ram,p['tcb_slot']-0x20000000)[0]==tcb,command_pointer=regs[10]==addr and regs[8]==4 and ram[addr-0x20000000:addr-0x20000000+4]==packet,exact_version_query=packet==bytes.fromhex('01011000'),peer_not_extended=d['peer']==dict(state='Complete',commands=59,events=3),no_seed_or_physical=a['host_pc_register_seed'] is False and a['original_main_executed'] is True and a['hardware_accessed'] is False,log_matches=logged(cap,'BLACKWALL_GAF_FROZEN_CORE')==[f],diagnostic_state_equal=read(first/'exports/frozen-core.json')==f,entire_sram_before_after_diagnostic_equal=all((first/n).read_bytes()==(cap/n).read_bytes() for n in ('exports/sram-full.bin','exports/connected-sram.bin','exports/connection-sram.bin','exports/frozen-core-sram.bin')),initial_prefix_preserved=all((parent/n).read_bytes()==(cap/n).read_bytes() for n in ('exports/sram-full.bin','exports/connected-sram.bin','exports/connection-sram.bin')))
 checks['fixed_input_recipe_exact']=regenerated
 if not all(checks.values()):raise ValueError({k:v for k,v in checks.items() if not v})
 result=dict(passed=True,checks=checks,scenario_passed=False,natural_timeout_observed=False,first_timeout_return_unproven=True,busy_reads=f['busy_reads'],elapsed_virtual_ns=f['virtual_ticks']-f['start_ticks'],frontier=dict(task=name,pc=f['pc'],gpio=0x40010410,h4_command_hex=packet.hex(),opcode=0x1001,command_was_transmitted=False),legacy_fixed_boundary_metadata_inherited_unused=True,physical_hardware_access=False,observer_universally_neutral=False)
 out.mkdir(mode=0o700,parents=True);(out/'report.json').write_text(json.dumps(result,indent=2)+'\n');return result

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();r=verify(a.simulator,a.output);print(json.dumps(dict(audit_passed=True,checks=len(r['checks']),scenario_passed=False,natural_timeout_observed=False,frontier=r['frontier'])))
if __name__=='__main__':main()
