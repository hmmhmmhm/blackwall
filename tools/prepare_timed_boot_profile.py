#!/usr/bin/env python3
"""Create a separate read-only observation variant of the pinned boot profile."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = Path.home() / 'Library/Application Support/Blackwall'
BASE = PRIVATE / 'simulator/original-boot-ui-cadence-native-bw547-02/strict.cs'
DEST = PRIVATE / 'simulator/timed-boot-observer-bw595'
PROFILE = ROOT / 'docs/data/original-boot-stock24-profile.json'

def digest(data): return hashlib.sha256(data).hexdigest()
def replace_once(source, old, new):
    if source.count(old) != 1: raise ValueError('Expected one anchor: '+old[:100])
    return source.replace(old, new, 1)

def main():
    profile=json.loads(PROFILE.read_text()); raw=BASE.read_bytes()
    if digest(raw)!=profile['components']['strict.cs']['sha256']: raise ValueError('Frozen strict source differs')
    s=raw.decode()
    s=replace_once(s,'public BlackwallExecutionObserver(CortexM cpu, int eventCapacity=128)','public BlackwallExecutionObserver(CortexM cpu, int eventCapacity, IMachine observedMachine)')
    s=replace_once(s,'this.cpu=cpu; Capacity=eventCapacity;','this.cpu=cpu; this.observedMachine=observedMachine; Capacity=eventCapacity;')
    s=replace_once(s,'events.Enqueue(new BlackwallPcEvent(Sequence,label,address,cpu.PC.RawValue,cpu.GetRegister(0).RawValue,cpu.GetRegister(2).RawValue));','events.Enqueue(new BlackwallPcEvent(Sequence,label,address,cpu.PC.RawValue,cpu.GetRegister(0).RawValue,cpu.GetRegister(2).RawValue,observedMachine.ElapsedVirtualTime.TimeElapsed.Ticks));')
    s=replace_once(s,'private readonly Dictionary<uint,BlackwallObservedPoint> points=', 'private readonly IMachine observedMachine;\n        private readonly Dictionary<uint,BlackwallObservedPoint> points=')
    s=replace_once(s,'public BlackwallPcEvent(ulong sequence,string label,uint address,ulong pc,ulong r0,ulong r2)\n        { Sequence=sequence; Label=label; Address=address; PC=pc; R0=r0; R2=r2; }','public BlackwallPcEvent(ulong sequence,string label,uint address,ulong pc,ulong r0,ulong r2,ulong ticks)\n        { Sequence=sequence; Label=label; Address=address; PC=pc; R0=r0; R2=r2; Ticks=ticks; }\n        public ulong Ticks { get; }')
    s=replace_once(s,'    using Antmicro.Renode.Core;\n    using Antmicro.Renode.Peripherals.CPU;\n\n    public sealed class BlackwallNemaRingDevice', '    using Antmicro.Renode.Core;\n    using Antmicro.Renode.Peripherals.CPU;\n    using System.Collections.Generic;\n\n    public sealed class BlackwallNemaRingDevice')
    s=replace_once(s,'CompleteScreenHasDetail=min!=max;CompleteScreenAddress=consumer.LastPackingSource;CompleteScreenCaptures++;','CompleteScreenHasDetail=min!=max;CompleteScreenAddress=consumer.LastPackingSource;CompleteScreenCaptures++;\n                    if(ObservedFrames.Count<32) { ObservedFrames.Add(CompleteScreenFrameBytes); ObservedFrameTicks.Add(machine.ElapsedVirtualTime.TimeElapsed.Ticks); } else ObservedFramesDropped++;')
    s=replace_once(s,'        public uint CompleteScreenCaptures {get;private set;}','        public uint CompleteScreenCaptures {get;private set;}\n        public List<byte[]> ObservedFrames {get;}=new List<byte[]>();\n        public List<ulong> ObservedFrameTicks {get;}=new List<ulong>();\n        public uint ObservedFramesDropped {get;private set;}')
    s=replace_once(s,'public void Reset() {consumer=null;IRQ.Set(false);Doorbells=', 'public void Reset() {ObservedFrames.Clear();ObservedFrameTicks.Clear();ObservedFramesDropped=0;consumer=null;IRQ.Set(false);Doorbells=')
    runtime=(ROOT/'tools/renode-original-boot-runtime.py').read_text()
    runtime=replace_once(runtime,'observer=BlackwallExecutionObserver(cpu,128)','observer=BlackwallExecutionObserver(cpu,128,m)')
    runtime=replace_once(runtime,'r2=int(p.R2)) for p in observer.Events]', 'r2=int(p.R2),ticks=int(p.Ticks)) for p in observer.Events]')
    anchor="if screen['bytes']>0:File.WriteAllBytes('/work-output/complete-screen.bin',gpu.CompleteScreenFrameBytes)"
    runtime=replace_once(runtime,anchor,anchor+"\nframes=[]\nfor i in range(gpu.ObservedFrames.Count):\n name='observed-frame-%02d.bin'%i\n File.WriteAllBytes('/work-output/'+name,gpu.ObservedFrames[i])\n frames.append(dict(file=name,ticks=int(gpu.ObservedFrameTicks[i])))\nFile.WriteAllText('/work-output/observed-frames.json',json.dumps(dict(frames=frames,dropped=int(gpu.ObservedFramesDropped))))")
    DEST.mkdir(parents=True,exist_ok=False)
    (DEST/'strict.cs').write_text(s);(DEST/'run.py').write_text(runtime)
    for name in ('strict.cs','run.py'):
        profile['components'][name]={'origin':'private','path':str((DEST/name).relative_to(PRIVATE)),'sha256':digest((DEST/name).read_bytes())}
    (DEST/'profile.json').write_text(json.dumps(profile,ensure_ascii=False,indent=2)+'\n')
    print(DEST/'profile.json')
if __name__=='__main__':main()
