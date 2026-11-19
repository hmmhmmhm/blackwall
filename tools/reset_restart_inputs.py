"""Reconstruct execution inputs only from fixed parent captures, not evolving candidate models."""
import hashlib
from reset_restart_profiles import sha,read,pin,profile,ATT_PIN,PREPARATION_PIN

def fixed_inputs(s,case):
    att=s/'runtime-att-research-01/manifest.json';parent=s/'cpu-retention-preparation-research-01/manifest.json'
    if sha(att)!=ATT_PIN or sha(parent)!=PREPARATION_PIN:raise ValueError('Changed source acceptance')
    am,pm=read(att),read(parent);base=s/'runtime-att-acceptance-native-01'/case;common=s/'cpu-retention-preparation-native-06';reference=s/'runtime-att-acceptance-native-01/stock24'
    pin(s,am,base/'capture-files.json');captured=read(base/'capture-files.json')['files'];base_inputs=read(base/'connection-inputs.json')
    for n in set(base_inputs)|{'connection-inputs.json'}:
        if sha(base/n)!=captured[n]:raise ValueError('Changed original input '+n)
    for n in ('strict.cs','activation.cs','run.py','board.repl','renode-reset-aware-nvic.cs','renode-reset-entry-observer.cs','renode-sleep-transition-observer.cs'):pin(s,pm,common/n)
    pin(s,am,reference/'capture-files.json');ref_capture=read(reference/'capture-files.json')['files']
    if sha(reference/'run.py')!=ref_capture['run.py'] or sha(reference/'activation.cs')!=ref_capture['activation.cs']:raise ValueError('Changed reference runtime')
    p=profile(s,case,(base/'main.bin').read_bytes());old=profile(s,'stock24',(common/'main.bin').read_bytes())
    if (base/'strict.cs').read_bytes()!=(reference/'strict.cs').read_bytes() or (base/'activation.cs').read_bytes()!=(reference/'activation.cs').read_bytes():raise ValueError('Profiles require shared original models and observer classes')
    whole=(common/'run.py').read_text();prefix=(reference/'run.py').read_text()
    if not whole.startswith(prefix):raise ValueError('Changed natural runtime boundary')
    tail=whole[len(prefix):];replacements=[]
    for k,count in (('retention_return',2),('wfi_return',1),('sleep_return',1)):
        before=hex(old[k]);after=hex(p[k])
        if tail.count(before)!=count:raise ValueError('Unreviewed version-boundary '+k)
        tail=tail.replace(before,after);replacements.append(dict(field=k,before=before,after=after,count=count))
    board=(base/'board.repl').read_text();anchor='    PerformanceInMips: 10\n'
    if board.count(anchor)!=1 or board.count('nvic: IRQControllers.NVIC @')!=1:raise ValueError('Unknown original CPU profile')
    board=board.replace(anchor,anchor+'    InitVectorTableOffset: 0x438000\n').replace('nvic: IRQControllers.NVIC @','nvic: Miscellaneous.BlackwallResetAwareNVIC @')
    anchor='cpu_normal_sleep: Miscellaneous.BlackwallCpuNormalSleep @ none\n'
    if board.count(anchor)!=1 or ('    flushReadPc: '+hex(p['flush_read'])+'\n') not in board:raise ValueError('Unknown CPU power/flush owner')
    board=board.replace(anchor,anchor+'    retentionFlush: true\n    inactiveAudioStatus: true\n    retentionStorePc: '+hex(p['retention_store'])+'\n    retentionReturnPc: '+hex(p['retention_return'])+'\n')
    anchor='Miscellaneous.BlackwallTimer14 @ none\n'
    if board.count(anchor)!=1:raise ValueError('Unknown TIMER owner')
    board=board.replace(anchor,anchor+'    idleChannelControls: true\n')

    values={n:(base/n).read_bytes() for n in base_inputs}
    for n in ('strict.cs','activation.cs','renode-reset-aware-nvic.cs','renode-reset-entry-observer.cs','renode-sleep-transition-observer.cs'):values[n]=(common/n).read_bytes()
    values['board.repl']=board.encode();values['run.py']=((base/'run.py').read_text()+tail).encode()
    meta=dict(p,replacements=replacements,reference=str(common.relative_to(s)),reference_manifest=PREPARATION_PIN,original_input=str(base.relative_to(s)),shared_model_sha256=hashlib.sha256(values['strict.cs']).hexdigest(),shared_observer_sha256=hashlib.sha256(values['activation.cs']).hexdigest(),original_main=True,hardware_accessed=False)
    return values,meta
