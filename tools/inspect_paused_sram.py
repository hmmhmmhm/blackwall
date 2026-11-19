"""Replay frozen original main and inspect bounded SRAM only after the verified strict stop."""
import argparse,hashlib,json,re,shutil
from pathlib import Path
from native_replay import FILES,IMAGE,digest,parse_log,validate_assets
from pinned_main import MAIN_LAYOUT
from run_renode_m55_probe import execute


def parse_range(value):
    try:
        label,address,words=value.split(':');address=int(address,0);words=int(words,0)
    except (ValueError,TypeError) as e:
        raise argparse.ArgumentTypeError('Use label:address:word-count') from e
    if not re.fullmatch('[a-z][a-z0-9-]{0,39}',label) or address&3 or not 1<=words<=256 or not 0x20000000<=address<=address+4*words<=0x20380000:
        raise argparse.ArgumentTypeError('Only bounded aligned simulated SRAM ranges are allowed')
    return dict(label=label,address=address,words=words)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--range',dest='ranges',action='append',type=parse_range,required=True);a=p.parse_args();src,o=a.source,a.output
    if len(a.ranges)>16 or len({r['label'] for r in a.ranges})!=len(a.ranges) or sum(r['words'] for r in a.ranges)>1024:p.error('Use unique labels, at most 16 ranges and 1024 words total')
    prior=json.loads((src/'report.json').read_text());derived=json.loads((src/'derived-inputs.json').read_text())['derived'];validate_assets(src,derived)
    if parse_log((src/'renode.log').read_text())!=prior['observed']:raise ValueError('Source native report differs')
    if digest(src/'main.bin') not in {x[3] for x in MAIN_LAYOUT.values()}:raise ValueError('Only hash-pinned original main is supported')
    o.mkdir(mode=0o700,parents=True)
    for f in FILES:shutil.copyfile(src/f,o/f)
    runtime=(src/'run.py').read_text();needle='    e.PauseAll()\n'
    if runtime.count(needle)!=1:raise ValueError('Unexpected paused boundary')
    extra="    from System import Console\n    if not m.IsPaused or not blackwall_paused_before_host:raise ValueError('SRAM capture requires the original paused stop')\n    stopped_sram=[]\n"
    for r in a.ranges:
        extra+="    stopped_sram.append(dict(label='%s',address=%d,words=[int(m.SystemBus.ReadDoubleWord(%d+4*i)) for i in range(%d)]))\n" % (r['label'],r['address'],r['address'],r['words'])
    extra+="    Console.WriteLine('BLACKWALL_PAUSED_SRAM '+json.dumps(dict(paused=bool(m.IsPaused),ranges=stopped_sram)))\n"
    runtime=runtime.replace(needle,needle+extra);compile(runtime,'run.py','exec');(o/'run.py').write_text(runtime)
    hashes={f:digest(o/f) for f in FILES};(o/'derived-inputs.json').write_text(json.dumps(dict(derived=hashes,base=derived,ranges=a.ranges),indent=2)+'\n')
    command=['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={o},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc']
    log=execute(command,o,'renode',timeout=None);validate_assets(o,hashes);observed=parse_log(log)
    def marker(name):
        rows=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith(name+' ')]
        if len(rows)!=1:raise ValueError('Missing marker '+name)
        return rows[0]
    obs=marker('BLACKWALL_OBSERVATION');memory=marker('BLACKWALL_PAUSED_SRAM')
    result=dict(observed=observed,selected_observation=obs,memory=memory,source=str(src),new_execution_hooks=False,guest_writes_added=False,hardware_accessed=False)
    (o/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    if observed!=prior['observed'] or obs!=prior['selected_observation']:raise ValueError('Frozen CPU/instruction count/trace changed')
    if not memory['paused'] or len(memory['ranges'])!=len(a.ranges):raise ValueError('Missing paused memory')
    for expected,actual in zip(a.ranges,memory['ranges']):
        if actual['label']!=expected['label'] or actual['address']!=expected['address'] or len(actual['words'])!=expected['words']:raise ValueError('Snapshot range mismatch')
    result['passed']=True;(o/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,ranges=memory['ranges'])),flush=True)


if __name__=='__main__':main()
