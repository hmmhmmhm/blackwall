"""Compose original reset evidence with explicit reset domains and unfinished E05 dependency."""
import argparse,hashlib,json,re
from pathlib import Path
from verify_reset_restart_versions import verify
from probe_reset_cache_lifecycle import SOURCE, SCRIPT, validate

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def class_source(text,name):
    found=re.search(r'public (?:sealed )?class '+re.escape(name)+r'\b',text)
    if not found:raise ValueError('Missing source class '+name)
    tail=text[found.start():]
    following=re.search(r'\n    public (?:sealed )?class ',tail[1:])
    return tail[:following.start()+1] if following else tail

def audit_cache(cap,control,baseline):
    report=json.loads((cap/'report.json').read_text())
    expected={str(mode)+'-'+method for mode in range(1,5) for method in ('device-aircr','guest-aircr')}
    if {r['case'] for r in report['cases']}!=expected or len(report['cases'])!=8 or report['control_sha256']!=sha(control) or (cap/'fixture.c').read_text()!=SOURCE:raise ValueError('Changed cache test plan/source')
    for row in report['cases']:
        p=cap/row['case'];values=[json.loads(l.split('BLACKWALL_RESET_CACHE ',1)[1]) for l in (p/'renode.log').read_text().splitlines() if l.startswith('BLACKWALL_RESET_CACHE ')]
        if len(values)!=1 or row!={'case':p.name,**validate(values[0])} or json.loads((p/'report.json').read_text())!=row:raise ValueError('Cache log/report disagreement')
        v=values[0];script=SCRIPT.replace('__MODE__',str(v['mode'])).replace('__METHOD__',v['method'])
        if p.name!=str(v['mode'])+'-'+v['method'] or (p/'run.py').read_text()!=script or (p/'control.cs').read_bytes()!=control.read_bytes() or (p/'fixture.elf').read_bytes()!=(cap/('mode-'+str(v['mode'])+'.elf')).read_bytes():raise ValueError('Changed cache execution input')
        if row['passed']==baseline:raise ValueError('Unexpected cache test result')
    if report['passed']==baseline:raise ValueError('Unexpected cache suite result')
    return dict(cases=8,observed_passes=0 if baseline else 8,expected_failure_preserved=baseline,control_sha256=sha(control))

def audit(s,cap,out,scope_path):
    if out.exists():raise ValueError('Fresh audit output required')
    policy=s/'reset-memory-protection-research-01/candidate-memory-policy.cs'
    control=s/'reset-domain-acceptance-research-01/candidate-system-control.cs'
    if sha(policy)!='29daafce028464c94a217260df7cc0016617b8be3c158498b4dced63b6837c5e' or sha(control)!='5564e88984c662868830211cc1c2362fc15460159f1f4f54a967ef44623938f5':raise ValueError('Changed reset candidates')
    scope=json.loads(scope_path.read_text());criteria={c['id']:c for c in scope['criteria']}
    baseline=s/'reset-domain-acceptance-research-01/baseline-system-control.cs'
    if sha(baseline)!='82067ed1bdc22110330293a607718714e92b074d6835bee55cd761ae9e58d53c':raise ValueError('Changed baseline cache control')
    synthetic_before=audit_cache(s/'reset-cache-lifecycle-native-01',baseline,True)
    synthetic_after=audit_cache(s/'reset-cache-lifecycle-native-02',control,False)
    out.mkdir(mode=0o700,parents=True);rows=[]
    for case in ('stock24','stock23','cfw'):
        original=verify(s,cap/case,out/case,policy,control)
        exports=cap/case/'exports';entry_report=json.loads((exports/'system-reset-entry.json').read_text());before=entry_report['before'];entry=entry_report['entry'];after=json.loads((exports/'system-reset-after.json').read_text());service=json.loads((exports/'restart-service.json').read_text());app=json.loads((exports/'restart-app.json').read_text())
        text=(cap/case/'strict.cs').read_text()
        sources={name:class_source(text,name) for name in ('BlackwallRtcAdapter','BlackwallNorReadWindow','BlackwallMspi1PioReset','BlackwallEm9305EventPeer','BlackwallSystemControl','BlackwallMemoryPolicy','BlackwallCpuNormalSleep')}
        checks=dict(nor_no_reset_clear='public void Reset() { }' in sources['BlackwallNorReadWindow'],rtc_explicit_epoch='engine.SetDateTime(2000,1,1,0,0,0,0)' in sources['BlackwallRtcAdapter'],pio_pending_clear='pendingProgram=activeProgram=null' in sources['BlackwallMspi1PioReset'] and 'rxWords.Clear()' in sources['BlackwallMspi1PioReset'],peer_queue_clear='transmitted.Clear();written.Clear();accepted.Clear();' in sources['BlackwallEm9305EventPeer'],cache_reset_hook=control.read_text().strip() in text and 'DataCache?.Reset();' in sources['BlackwallSystemControl'],memory_route_hook=policy.read_text().strip() in text and 'RouteMainReadsViaIo();' in sources['BlackwallMemoryPolicy'],power_reset='CpdValue=RetentionStages=AudioStatusReads=RetentionFlushes=0' in sources['BlackwallCpuNormalSleep'])
        if not all(checks.values()):raise ValueError('Reset source disagreement '+case)
        rows.append(dict(case=case,original_restart_passed=original['passed'],checks=checks,source_classes={n:hashlib.sha256(v.encode()).hexdigest() for n,v in sources.items()},observed=dict(initial_sp=entry['sp'],reset_pc=entry['pc'],itcm_retained=len({x['itcm_sha256'] for x in (before,entry,after)})==1,guest_written_bytes=entry['memory']['written'],kv_window_retained=len({x['nor_kv_sha256'] for x in (before,entry,after)})==1,rtc_entry=entry['rtc'],controller_entry=entry['peer'],icache_before_entry_service=[x['system_control']['icache'] for x in (before,entry,service)],rtc_final=app['rtc'],sram_request_to_entry=original['sram_request_to_entry'])))
    domains=[
      dict(name='cpu-and-nvic',policy='reset original vector/SP, exception mask and interrupt state',evidence='original vector/basepri; synthetic IRQ reset',limit='not all M55 architectural state'),
      dict(name='main-image',policy='immutable input across reset',evidence='pinned original main; write and execution guards',limit='main reset only; bootloader is not executed'),
      dict(name='sram',policy='MappedMemory backing retained; original startup rewrites globals/stack',evidence='pinned no-op Reset source and synthetic retained cookie',limit='asynchronous request-to-entry snapshots include guest execution; no pure whole-SRAM equality claim'),
      dict(name='itcm',policy='backing and guest-written provenance retained',evidence='original whole-region hash and synthetic retained execution',limit='virtual profile; not physical retention validation'),
      dict(name='nor-kv',policy='retain backing; clear controller transfer state',evidence='whole selected KV window hash before/entry/initialization; idle PIO flags',limit='does not exercise interrupted program/erase in this scenario'),
      dict(name='littlefs-window',policy='retain backing through no-op Reset',evidence='compiled source and board additional-window link',limit='source-supported only; full window hash was not exported'),
      dict(name='rtc',policy='reset virtual epoch to 2000 and clear write latch/commits',evidence='source and original reset-entry/restarted ATT commit',limit='deliberate virtual profile; not physical RTC behavior'),
      dict(name='controller-peer',policy='clear session, queued/reply history, consumed-event counters',evidence='source, entry Unreleased/0/0, restarted Complete/59 and new events',limit='virtual peer; does not run controller firmware'),
      dict(name='functional-caches',policy='clear IC/DC enabled, selector and initialization leases; retain error diagnostics',evidence='synthetic CCR reads/guards plus original IC true/false/true',limit='coherent functional model; no physical dirty cache or cycle fidelity'),
      dict(name='other-peripherals',policy='registered Reset and owner reset methods',evidence='compiled model source',limit='not independently exercised in every non-idle state'),
      dict(name='observers-and-safety',policy='retain owned hooks and protection provenance; detach only owned one-shot observer',evidence='fixed execution input and memory guard tests',limit='observation is not proven neutral; sleep buffer overflows after preserved prefix')]
    report=dict(passed=True,cases=rows,domains=domains,synthetic_before=synthetic_before,synthetic_after=synthetic_after,scope_version=scope['version'],e05_status=criteria['E05']['status'],e06_status=criteria['E06']['status'],e06_complete=False,requirements=dict(device_reset_and_original_reentry='verified for fixed scenario',declared_domains='verified with stated evidence levels',original_app_restart='verified for service/ATT scenario',e05_full_required_initialization='incomplete'),next_action='E05 required GAF computation/initialization or an explicitly justified firmware path; do not add duplicate reset probes',physical_hardware_access=False)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');return report

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('capture',type=Path);p.add_argument('output',type=Path);p.add_argument('--scope',type=Path,default=Path(__file__).resolve().parents[1]/'docs/data/project-scope.json');a=p.parse_args();r=audit(a.simulator,a.capture,a.output,a.scope);print(json.dumps(dict(passed=True,original_cases=len(r['cases']),domains=len(r['domains']),e05_status=r['e05_status'],e06_complete=False)))
if __name__=='__main__':main()
