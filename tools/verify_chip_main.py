"""Run original chip-info reads and check the actual guest-produced partial information structure."""
import argparse,json,subprocess,sys,hashlib
from pathlib import Path
from native_replay import parse_log,boundary_state,IMAGE
from pinned_main import load_pinned_main
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();s=a.simulator.resolve();o=a.output.resolve()
    if o.exists():raise ValueError('Use a fresh evidence directory')
    o.mkdir(mode=0o700);rows=[]
    for name,base,enabled in [('stock24','stock24-no-writes',True),('stock23','stock23',True),('cfw','cfw',True),('stock24-default','stock24-no-writes',False)]:
        previous=s/'rtc-functional-main-comparison-01';prior=json.loads((previous/base/'report.json').read_text());target=prior['observed']['register_context']['r4']
        if target%4 or not 0x20000000<=target<=0x20380000-64:raise ValueError('Info destination outside bounded SRAM')
        source_cmd=json.loads((previous/(base+'-launcher.json')).read_text())['command'];cmd=source_cmd[:4];i=4
        while i<len(source_cmd):
            if source_cmd[i] in ('--capture-sram-window','--rtc-counter-writes'):i+=2;continue
            cmd.append(source_cmd[i]);i+=1
        run=o/name;cmd[3]=str(run)
        if enabled:cmd+=['--chip-info-profile','source-reset-zero-ids','--capture-sram-window',hex(target)+':64']
        launch=subprocess.run(cmd,capture_output=True,text=True)
        (o/(name+'-launcher.json')).write_text(json.dumps(dict(command=cmd,returncode=launch.returncode,stdout=launch.stdout,stderr=launch.stderr),indent=2)+'\n')
        if launch.returncode:raise ValueError('Original chip info probe failed: '+name)
        report=json.loads((run/'report.json').read_text());v=parse_log((run/'renode.log').read_text())
        if v!=report['observed'] or report['image_id']!=IMAGE:raise ValueError('Native record/runtime differs')
        _,raw=load_pinned_main(Path(cmd[2]).read_bytes())
        if raw!=(run/'main.bin').read_bytes():raise ValueError('Original main differs')
        guards=[g for g in v['guards'] if g['accesses']];info=v['chip_info'];words=None
        if enabled:
            if info is None or info['hardware_verified'] or info['source_reset_is_device_state']:raise ValueError('Incorrect identity claim')
            if guards[0]['address']!=0xe00fefe0 or guards[0]['operation']!='read':raise ValueError('Expected unknown JEDEC boundary')
            if v['register_context']['r4']!=target:raise ValueError('Info pointer changed; do not interpret stale capture')
            windows=[w for w in v['sram_windows'] if w['base']==target]
            if len(windows)!=1 or len(windows[0]['bytes'])!=64:raise ValueError('Missing partial info snapshot')
            data=bytes(windows[0]['bytes']);words=[int.from_bytes(data[i:i+4],'little') for i in range(0,64,4)]
            revision=report['selected_hypotheses']['chip_revision']
            if words[:7]!=[0x10320080,0,0,revision,0,0x2d480f,1]:raise ValueError('Original info output differs')
            if words[8:12]!=[256*1024,512*1024,3072*1024,4096*1024]:raise ValueError('Original SKU size decode differs')
            values={r['address']:r['value'] for r in info['registers']}
            if values['0x4002000c']!=revision:raise ValueError('Conflicting revision models')
        elif info is not None or boundary_state(v)!=boundary_state(prior['observed']):raise ValueError('Default identity strict behavior changed')
        if any(report[k] for k in ('boot_verified','hardware_validated','installable')):raise ValueError('Unproven completion claim')
        row=dict(name=name,pc=hex(v['pc']),guards=guards,chip_info=info,partial_info_destination=hex(target) if enabled else None,partial_info_words=words,info_getter_return_observed=False)
        rows.append(row);print(json.dumps(row),flush=True)
    left=o/'stock23';right=o/'cfw'
    for name in ('board.repl','strict.cs','result.py','probe.resc'):
        if (left/name).read_bytes()!=(right/name).read_bytes():raise ValueError('Stock/CFW configuration differs')
    if (left/'run.py').read_text().replace('3758688','3829832')!=(right/'run.py').read_text():raise ValueError('Stock/CFW runtime differs beyond size')
    source=o/'source';source.mkdir(mode=0o700);hashes={}
    for name in ('verify_chip_main.py','verify_chip_identity.py','run_renode_main_probe.py','renode-strict-mmio.cs'):
        data=(ROOT/'tools'/name).read_bytes();(source/name).write_bytes(data);hashes[name]=hashlib.sha256(data).hexdigest()
    (o/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,source_sha256=hashes,scope='original partial device-info writes and SKU decode under explicit synthetic identity, getter not complete, no hardware identity/recovery validation'),indent=2)+'\n')

if __name__=='__main__':main()
