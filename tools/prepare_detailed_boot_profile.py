#!/usr/bin/env python3
"""Derive an isolated observer variant with bounded UART observation timestamps."""
import hashlib
import json
from pathlib import Path

PRIVATE=Path.home()/'Library/Application Support/Blackwall'
BASE=PRIVATE/'simulator/timed-boot-observer-bw595'
DEST=PRIVATE/'simulator/detailed-boot-observer-bw601'

def digest(data): return hashlib.sha256(data).hexdigest()
def replace_once(source,old,new):
    if source.count(old)!=1: raise ValueError('Expected one anchor: '+old[:100])
    return source.replace(old,new,1)

def main():
    profile=json.loads((BASE/'profile.json').read_text())
    for name in ('strict.cs','run.py'):
        if digest((BASE/name).read_bytes())!=profile['components'][name]['sha256']: raise ValueError('Observer input hash changed: '+name)
    s=(BASE/'strict.cs').read_text()
    old='if(!BoundedTxCapture || TxBytes.Count<4096)TxBytes.Add(b);'
    new='if(!BoundedTxCapture || TxBytes.Count<4096) { TxBytes.Add(b); if(Module==1)TxObservedTicks.Add(machine.ElapsedVirtualTime.TimeElapsed.Ticks); }'
    s=replace_once(s,old,new)
    s=replace_once(s,'TxBytes.Clear();TxBytesTotal=0;', 'TxBytes.Clear();TxObservedTicks.Clear();TxBytesTotal=0;')
    s=replace_once(s,'public System.Collections.Generic.List<byte> TxBytes { get; } = new System.Collections.Generic.List<byte>();', 'public System.Collections.Generic.List<byte> TxBytes { get; } = new System.Collections.Generic.List<byte>();\n        public System.Collections.Generic.List<ulong> TxObservedTicks {get;} = new System.Collections.Generic.List<ulong>();')
    s=replace_once(s,'Transfers.Add(new Transfer(Target,bytes));','Transfers.Add(new Transfer(Target,bytes,machine.ElapsedVirtualTime.TimeElapsed.Ticks));')
    s=replace_once(s,'public Transfer(uint target,byte[] data) { Target=target;Data=data; }','public Transfer(uint target,byte[] data,ulong ticks) { Target=target;Data=data;Ticks=ticks; }\n            public ulong Ticks { get; }')
    runtime=(BASE/'run.py').read_text()
    runtime=replace_once(runtime,"wire=dict(stages=[],requests=[],replies=[],hardware_accessed=False,guest_writes=False)","wire=dict(stages=[],requests=[],replies=[],hardware_accessed=False,guest_writes=False,initial_observation=dict(reason=reason,start_ticks=start,stop_ticks=int(m.ElapsedVirtualTime.TimeElapsed.Ticks),pc=int(cpu.PC.RawValue)))")
    runtime=replace_once(runtime,"return dict(data=d,identifier=d[1]*256+d[2],channel=d[6],payload=d[9:-2])", "return dict(data=d,identifier=d[1]*256+d[2],channel=d[6],payload=d[9:-2],ticks=int(t.Ticks))")
    runtime=replace_once(runtime,"dict(module=int(p.Key),tx=[int(b) for b in p.Value.TxBytes],writes=int(p.Value.Writes))", "dict(module=int(p.Key),tx=[int(b) for b in p.Value.TxBytes],ticks=[int(t) for t in p.Value.TxObservedTicks],dropped=int(p.Value.TxBytesDropped),writes=int(p.Value.Writes),transfers=[dict(ticks=int(t.Ticks),data=[int(b) for b in t.Data]) for t in p.Value.DmaTx.Transfers] if p.Value.DmaTx is not None else [])")
    DEST.mkdir(parents=True,exist_ok=False)
    (DEST/'strict.cs').write_text(s);(DEST/'run.py').write_text(runtime)
    for name in ('strict.cs','run.py'):
        profile['components'][name]={'origin':'private','path':str((DEST/name).relative_to(PRIVATE)),'sha256':digest((DEST/name).read_bytes())}
    (DEST/'profile.json').write_text(json.dumps(profile,ensure_ascii=False,indent=2)+'\n')
    print(DEST/'profile.json')
if __name__=='__main__':main()
