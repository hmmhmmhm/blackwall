"""Opt-in synchronous functional off completion; not a physical power timing model."""
def bind(model):
    start=model.index('    public class BlackwallPeripheralPower : IPeripheral');end=model.index('\nnamespace ',start);section=model[start:end]
    if 'bool synchronousOffResponse=false' in section:return model
    edits=[
      ('public BlackwallPeripheralPower(uint mask,int profile,int offProfile=-1)','public BlackwallPeripheralPower(uint mask,int profile,int offProfile=-1,bool synchronousOffResponse=false)'),
      ('            Mask=mask; Profile=profile; OffProfile=offProfile; Reset();','''            if(synchronousOffResponse && offProfile!=0)throw new System.ArgumentException("Synchronous off response requires successful off profile");
            SynchronousOffResponse=synchronousOffResponse;
            Mask=mask; Profile=profile; OffProfile=offProfile; Reset();'''),
      ('Phase="off-requested"; OffRequests++; return true;', 'Phase="off-requested"; OffRequests++; if(SynchronousOffResponse)ReadStatus(); return true;'),
      ('        public int OffProfile { get; }','        public bool SynchronousOffResponse {get;}\n        public int OffProfile { get; }')]
    for old,new in edits:
        if section.count(old)!=1:raise ValueError('Unique peripheral off response boundary required: '+old)
        section=section.replace(old,new)
    return model[:start]+section+model[end:]
