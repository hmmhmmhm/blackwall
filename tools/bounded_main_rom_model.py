"""Reuse reviewed ROM range validation; add a callback-qualified MRAM invalidate domain."""
from pathlib import Path
import hashlib
ROOT=Path(__file__).resolve().parents[1]
def method(s,token):
 a=s.index(token);b=s.index('{',a);n=1;e=b+1
 while n:n+=(s[e]=='{')-(s[e]=='}');e+=1
 return s[a:e]
def bind(model):
 if 'public sealed class BlackwallBoundedMainRom' in model:return model
 # Frozen same-board source predates the functional ROM binding; preserve its policy.
 start=model.index('    public sealed class BlackwallMemoryPolicy : IPeripheral');end=model.index('\nnamespace ',start)
 section=model[start:end]
 if 'BindFunctionalRomEntry' not in section:
  current=(ROOT/'tools/renode-memory-policy.cs').read_text()
  anchor='        public void Attach()\n        {'
  if section.count(anchor)!=1:raise ValueError('Unique policy attach required')
  section=section.replace(anchor,method(current,'        public void BindFunctionalRomEntry(')+'\n        private Action<uint> functionalRomGuard;\n'+anchor)
  anchor='        private void CheckBlock(ulong pc, uint instructions)\n        {'
  if section.count(anchor)!=1:raise ValueError('Unique policy block guard required')
  section=section.replace(anchor,anchor+'\n            if(pc==0x0200ff20 && functionalRomGuard!=null)\n            { functionalRomGuard(instructions); return; }')
 model=model[:start]+section+model[end:]
 for sig,body in [('public override uint ReadDoubleWord(long offset)','if(RecoveryMramControl!=null && address>=0x40014000 && address<0x40014028)return RecoveryMramControl.ReadDoubleWord((long)(address-0x40014000));'),('public override void WriteDoubleWord(long offset, uint value)','if(RecoveryMramControl!=null && address>=0x40014000 && address<0x40014028){RecoveryMramControl.WriteDoubleWord((long)(address-0x40014000),value);return;}')]:
  prefix=sig+'\n        {\n            var address = baseAddress + (ulong)offset;'
  if model.count(prefix)!=1:raise ValueError('Unique shared MRAM control dispatch required')
  model=model.replace(prefix,prefix+'\n            '+body)
 anchor='public BlackwallMemoryStartup MemoryStartup { get; }'
 if model.count(anchor)!=1:raise ValueError('Unique shared MRAM control owner required')
 model=model.replace(anchor,'public BlackwallRecoveryMramControl RecoveryMramControl { get; set; }\n        '+anchor)

 source=(ROOT/'tools/renode-recovery-writer-fixture.cs').read_text()
 control='namespace Antmicro.Renode.Peripherals.Miscellaneous { using Antmicro.Renode.Peripherals.Bus; using Antmicro.Renode.Core; using Antmicro.Renode.Peripherals.CPU; '+method(source,'    public sealed class BlackwallRecoveryMramControl')+' }\n'
 validators='namespace Antmicro.Renode.Peripherals.Miscellaneous { internal static class BlackwallMramRangeContract {\n'+method(source,'internal static bool ValidWriteScope(')+'\n'+method(source,'internal static bool ValidProgramRequest(')+'\n}}\n'
 old='if(!SramAddressMaintenance || value>uint.MaxValue || line<0x20000000 || line>=0x20380000)return false;'
 new='if(value>uint.MaxValue)return false;\n                var sram=SramAddressMaintenance && line>=0x20000000 && line<0x20380000;\n                var mram=offset==0xf5c && ApprovedMramInvalidation!=null && ApprovedMramInvalidation(line);\n                if(!sram&&!mram)return false;'
 if model.count(old)!=1:raise ValueError('Unique coherent MVA boundary required')
 model=model.replace(old,new)
 old='        public bool SramAddressMaintenance { get; }'
 if model.count(old)!=1:raise ValueError('Unique coherent address domain required')
 model=model.replace(old,old+'\n        public System.Func<ulong,bool> ApprovedMramInvalidation {get;set;}')
 return model+'\n'+control+validators+'\n'+(ROOT/'tools/renode-bounded-main-rom.cs').read_text()
