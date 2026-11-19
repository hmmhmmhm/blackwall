"""Run original main with existing UART0 and explicit HCPA status, retaining missing-font diagnosis."""
import argparse,json,shutil
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from native_replay import FILES,IMAGE,digest,parse_log,validate_assets
from pinned_main import load_pinned_main
from run_renode_m55_probe import execute
from verify_mspi1_pio_reset import models
from verify_uart_hcpa import uart0_board


def baseline_core(core):
    replacements=[(', bool uartHcpaStatus = false)',')'),
                  ('            if(uartHcpaStatus && Uarts.Count!=4)throw new System.ArgumentException("HCPA status requires four explicit UART adapters");\n            UartHcpaStatus=uartHcpaStatus;\n',''),
                  ('                if(UartHcpaStatus && uartWord!=0)uartWord=0x1e00;\n',''),
                  ('        public bool UartHcpaStatus { get; }\n','')]
    for before,after in replacements:
        if core.count(before)!=1:raise ValueError('Unexpected shared-status model edit')
        core=core.replace(before,after)
    return core


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);p.add_argument('--case',choices=['stock24','stock23','cfw'],required=True);p.add_argument('--uart0',action='store_true');p.add_argument('--hcpa-status',action='store_true');a=p.parse_args();s,o=a.simulator,a.output
    if a.hcpa_status and not a.uart0:p.error('--hcpa-status requires --uart0')
    src=s/'missing-font-header-main-01'/(a.case+'-low');prior=json.loads((src/'report.json').read_text());source_hashes=json.loads((src/'derived-inputs.json').read_text())['derived'];validate_assets(src,source_hashes)
    if parse_log((src/'renode.log').read_text())!=prior['observed']:raise ValueError('Prior native differs')
    filename={'stock24':'stock-2.4.0.24.bin','stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[a.case];_,raw=load_pinned_main((s/'inputs/verified-01'/filename).read_bytes())
    if raw!=(src/'main.bin').read_bytes():raise ValueError('Original main differs')
    contract=json.loads((s/'post-font-uart0-contract-02/report.json').read_text());meta=next(c for c in contract['cases'] if c['case']==a.case)
    if not contract['passed'] or contract['count']!=57:raise ValueError('Missing source contract')
    new=models(s);core=Path(__file__).with_name('renode-strict-mmio.cs').read_text().encode();old=baseline_core(core.decode()).encode();frozen=(src/'strict.cs').read_bytes()
    if not frozen.startswith(old) or new!=core+frozen[len(old):]:raise ValueError('Model edits exceed reviewed core changes')
    o.mkdir(mode=0o700,parents=True)
    for f in FILES:shutil.copyfile(src/f,o/f)
    (o/'strict.cs').write_bytes(new);labels=[];runtime=(src/'run.py').read_text()
    if a.uart0:
        (o/'board.repl').write_text(uart0_board((src/'board.repl').read_text(),a.hcpa_status))
        wrapper=int(meta['UART_power_entry'],0);c=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS);instructions=[]
        for i in c.disasm(raw[wrapper-0x438000:wrapper+0x100-0x438000],wrapper):
            instructions.append(i)
            if i.mnemonic=='pop' and 'pc' in i.op_str:break
        if instructions[-1].mnemonic!='pop':raise ValueError('UART power wrapper epilogue not found')
        client_return=prior['observed']['stack_context']['words'][15]&~1
        call=next(c.disasm(raw[client_return-4-0x438000:client_return-0x438000],client_return-4))
        if call.mnemonic!='bl' or int(call.op_str[1:],0)!=wrapper:raise ValueError('Original UART0 client call differs')
        sites=[('UART-power-enable-return',int(meta['UART_power_call'],0)+4),('UART-power-wrapper-return',instructions[-1].address),('UART0-power-client-return',client_return)]
        labels=[l for l,_ in sites]
        extra="    m['sysbus.guard'].Uarts[0].AttachIrqProbe(m['sysbus.cpu'],"+str(int(meta['UART0_vector'],0))+",m)\n"
        extra+=''.join("    observer.AddPoint('%s',%d)\n" % (l,pc) for l,pc in sites)
        if runtime.count('    e.StartAll()\n')!=1:raise ValueError('Unexpected start boundary')
        runtime=runtime.replace('    e.StartAll()\n',extra+'    e.StartAll()\n')
    needle="    Console.WriteLine('BLACKWALL_REPORT "
    marker="    Console.WriteLine('BLACKWALL_UART_HCPA '+json.dumps(dict(shared=bool(g.UartHcpaStatus),UART0=g.Uarts.ContainsKey(0),missing_fonts=True)))\n"
    if runtime.count(needle)!=1:raise ValueError('Unexpected report boundary')
    runtime=runtime.replace(needle,marker+needle);compile(runtime,'run.py','exec');(o/'run.py').write_text(runtime)
    derived={f:digest(o/f) for f in FILES};(o/'derived-inputs.json').write_text(json.dumps(dict(derived=derived,base=source_hashes,UART0=a.uart0,HCPA=a.hcpa_status),indent=2)+'\n')
    command=['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc']
    log=execute(command,o,'renode',timeout=None);validate_assets(o,derived);v=parse_log(log)
    def read_marker(name):
        rows=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith(name+' ')]
        if len(rows)!=1:raise ValueError('Missing marker '+name)
        return rows[0]
    obs=read_marker('BLACKWALL_OBSERVATION');hcpa=read_marker('BLACKWALL_UART_HCPA');font=read_marker('BLACKWALL_MISSING_FONT')
    result=dict(case=a.case,observed=v,selected_observation=obs,HCPA=hcpa,font_diagnostic=font,original_main_sha256=digest(o/'main.bin'),boot_verified=False,display_verified=False,hardware_accessed=False)
    (o/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    if obs['dropped_events'] or obs['sequence']!=len(obs['events']):raise ValueError('Event loss')
    filtered=[e for e in obs['events'] if e['label'] not in labels];prefix=[dict(e,sequence=i+1) for i,e in enumerate(filtered[:len(prior['selected_observation']['events'])])]
    result['prior_prefix_equal']=prefix==prior['selected_observation']['events']
    if not a.uart0 and (v!=prior['observed'] or obs!=prior['selected_observation']):raise ValueError('Default CPU/instruction count/trace changed')
    if font['reads']!=2:raise ValueError('Missing-font diagnostic contract changed')
    result['passed']=True;(o/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=True,case=a.case,UART0=a.uart0,shared=a.hcpa_status,pc=hex(v['pc']),prior_prefix_equal=result['prior_prefix_equal'],guards=[g for g in v['guards'] if g['accesses']])),flush=True)


if __name__=='__main__':main()
