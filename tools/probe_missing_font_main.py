"""Run original main with an explicitly missing-font-magic diagnostic, never stock assets."""
import argparse,json,shutil
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from native_replay import FILES,IMAGE,digest,parse_log,validate_assets
from pinned_main import load_pinned_main
from run_renode_m55_probe import execute
from verify_mspi1_pio_reset import models


def verify_model_delta(old,new):
    def section(text,comment):
        start=text.index(comment);declaration=text.index('public sealed class BlackwallMspi1XipGuard',start)
        opening=text.index('{',declaration);depth=1;end=opening+1
        while depth:
            if text[end]=='{':depth+=1
            elif text[end]=='}':depth-=1
            end+=1
        return start,end
    a,b=section(old,'    // Covers the entire MSPI1 module window.')
    c,d=section(new,'    // No general XIP backing.')
    if old[:a]+new[c:d]+old[b:]!=new:raise ValueError('Model changes extend beyond the reviewed XIP guard')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--case',choices=['stock24','stock23','cfw'],required=True)
    p.add_argument('--role',choices=['low','high'],default='low')
    p.add_argument('--missing-font-magic',action='store_true',help='Explicit synthetic diagnostic; does not supply valid fonts')
    a=p.parse_args();s,o=a.simulator,a.output;src=s/'timer0-shared-main-02'/(a.case+'-'+a.role)
    prior=json.loads((src/'report.json').read_text());source_hashes=json.loads((src/'derived-inputs.json').read_text())['derived'];validate_assets(src,source_hashes)
    if parse_log((src/'renode.log').read_text())!=prior['observed']:raise ValueError('Prior native evidence differs')
    filename={'stock24':'stock-2.4.0.24.bin','stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[a.case]
    _,raw=load_pinned_main((s/'inputs/verified-01'/filename).read_bytes())
    if raw!=(src/'main.bin').read_bytes():raise ValueError('Original main differs')
    source=json.loads((s/'xip-font-contract-03/report.json').read_text());meta=next(c for c in source['cases'] if c['case']==a.case)
    if not source['passed'] or source['count']!=173:raise ValueError('Missing source contract')
    o.mkdir(mode=0o700,parents=True)
    for f in FILES:shutil.copyfile(src/f,o/f)
    updated=models(s)
    verify_model_delta((src/'strict.cs').read_text(),updated.decode())
    (o/'strict.cs').write_bytes(updated)
    labels=[]
    if a.missing_font_magic:
        needle='xip_guard: Miscellaneous.BlackwallMspi1XipGuard @ sysbus 0x80000000\n';board=(o/'board.repl').read_text()
        if board.count(needle)!=1:raise ValueError('Unexpected XIP owner')
        board=board.replace(needle,needle+'    fontHeaderProfile: "missing-font-magic-only"\n    primaryHeaderReadPc: '+meta['banks'][0]['read_pc']+'\n    secondaryHeaderReadPc: '+meta['banks'][1]['read_pc']+'\n')
        (o/'board.repl').write_text(board)
        sites=[('font-configure-entry',int(meta['initializer'],0)),('font-configure-return',int(meta['return_pc'],0))]
        for i,bank in enumerate(meta['banks']):
            sites += [('font-header-invalid-'+str(i),int(bank['invalid_branch'],0)),('font-descriptor-cleared-'+str(i),int(bank['descriptor_clear_pc'],0)+2)]
        start=int(meta['parent_call'],0)-2;builder=int(meta['chain_builder'],0);md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS)
        parent=[]
        for ins in md.disasm(raw[start-0x438000:start+0x180-0x438000],start):
            parent.append(ins)
            if ins.mnemonic=='pop' and 'pc' in ins.op_str:break
        if not parent or parent[0].mnemonic!='push' or parent[-1].mnemonic!='pop':raise ValueError('Parent entry/return not found')
        calls=[i.address for i in parent if i.mnemonic=='bl' and int(i.op_str[1:],0)==builder]
        if len(calls)!=2:raise ValueError('Two original chain calls required')
        sites += [('font-chain-return-'+str(i),pc+4) for i,pc in enumerate(calls)]
        sites += [('font-manager-return',parent[-1].address)]
        labels=[label for label,_ in sites]
        extra=''.join("    observer.AddPoint('%s',%d)\n" % (label,pc) for label,pc in sites)
        for i,bank in enumerate(meta['banks']):
            extra += "    observer.CaptureSram(m,'font-descriptor-cleared-%d',%d,1)\n" % (i,int(bank['font_object'],0)+0x18)
        runtime=(o/'run.py').read_text()
        if runtime.count('    e.StartAll()\n')!=1:raise ValueError('Unexpected start boundary')
        runtime=runtime.replace('    e.StartAll()\n',extra+'    e.StartAll()\n')
    else:runtime=(o/'run.py').read_text()
    # Host-side diagnostic metadata only; guard counters are preserved separately.
    tail="    x=m['sysbus.xip_guard']\n    Console.WriteLine('BLACKWALL_MISSING_FONT '+json.dumps(dict(profile=x.FontHeaderProfile,reads=int(x.FontHeaderReads),last_pc=int(x.LastFontHeaderPc),stock_font_assets=False)))\n"
    needle="    Console.WriteLine('BLACKWALL_REPORT "
    if runtime.count(needle)!=1:raise ValueError('Unexpected report boundary')
    runtime=runtime.replace(needle,tail+needle)
    compile(runtime,'run.py','exec');(o/'run.py').write_text(runtime)
    derived={f:digest(o/f) for f in FILES};(o/'derived-inputs.json').write_text(json.dumps(dict(derived=derived,base=source_hashes,diagnostic=a.missing_font_magic,source_contract=meta),indent=2)+'\n')
    command=['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc']
    log=execute(command,o,'renode',timeout=None);validate_assets(o,derived)
    def marker(name):
        rows=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith(name+' ')]
        if len(rows)!=1:raise ValueError('Missing marker '+name)
        return rows[0]
    # Preserve raw evidence even if the diagnostic hits an execution-policy boundary.
    observed=marker('BLACKWALL_REPORT');obs=marker('BLACKWALL_OBSERVATION');diag=marker('BLACKWALL_MISSING_FONT')
    result=dict(case=a.case,role=a.role,diagnostic=a.missing_font_magic,observed=observed,selected_observation=obs,font_diagnostic=diag,
                original_main_sha256=digest(o/'main.bin'),boot_verified=False,display_verified=False,hardware_accessed=False)
    (o/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    if not observed['machine_paused_before_host']:raise ValueError('Native did not reach a paused boundary')
    if parse_log(log)!=observed:raise ValueError('Unsupported or inconsistent native endpoint')
    if not obs['dropped_events']==0:raise ValueError('Observation event loss')
    if not a.missing_font_magic:
        if parse_log(log)!=prior['observed'] or obs!=prior['selected_observation'] or diag['reads']!=0:raise ValueError('Default CPU/trace changed')
    else:
        filtered=[e for e in obs['events'] if e['label'] not in labels]
        prefix=[dict(e,sequence=i+1) for i,e in enumerate(filtered[:len(prior['selected_observation']['events'])])]
        if prefix!=prior['selected_observation']['events']:raise ValueError('Prior trace prefix changed')
        if diag['reads']!=2:raise ValueError('Both bounded header reads not completed; inspect preserved evidence')
    result['passed']=True
    (o/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=True,case=a.case,diagnostic=a.missing_font_magic,pc=hex(observed['pc']),font_reads=diag['reads'],points={p['label']:p['hits'] for p in obs['points'] if p['label'] in labels})),flush=True)


if __name__=='__main__':main()
