"""Explicit shared HCPB/HCPC lifecycle; leave the shared source and default board intact."""
import hashlib
from pathlib import Path
import re

CLASS_SHA='5221ccf22756c86c7049c73bc305a2a30c9df380f587373688faeed0a78826da'


def compose(model):
    source=Path(__file__).with_name('renode-strict-mmio.cs').read_text()
    begin=source.index('    public class BlackwallPeripheralPower');end=source.index('\n}\n\nnamespace ',begin)
    old=source[begin:end]
    if hashlib.sha256(old.encode()).hexdigest()!=CLASS_SHA or model.count(old)!=1:raise ValueError('Unknown power class')
    new=old.replace('int offProfile=-1)', 'int offProfile=-1,bool sharedIomGate=false)')
    new=new.replace('            Mask=mask; Profile=profile;', '''            if(sharedIomGate && (mask&0x1feu)==0)throw new System.ArgumentException("Shared IOM gate requires IOM0..7 mask");
            SharedIomGate=sharedIomGate;
            Mask=mask; Profile=profile;''')
    anchor='        public uint ReadStatus()'
    extra='''        public bool SharedIomGate {get;}
        public uint IomDomainMask => (Mask&0x1eu)!=0 ? 0x1eu : 0x1e0u;
        public bool TryWriteIomShared(uint value,bool ready,bool quiescent,bool domainHeld)
        {
            if(SharedIomGate && domainHeld && ready && quiescent && OffProfile==0)
            {
                if(value==0 && Phase=="on")
                {Generation++;RequestWord=StatusWord=0;Phase="gated";OffRequests++;return true;}
                if(value==Mask && Phase=="gated")
                {Generation++;RequestWord=StatusWord=Mask;Phase="on";Requests++;Responses++;return true;}
            }
            return TryWrite(value,ready,quiescent);
        }
        public bool CompleteIomSharedPowerOff()
        {
            if(!SharedIomGate || Phase!="gated" || OffProfile!=0)return false;
            Phase="off-requested";ReadStatus();return true;
        }
'''
    new=new.replace(anchor,extra+anchor);model=model.replace(old,new)
    old_read='                foreach(var power in IomPowers.Values) uartWord|=power.ReadStatus();'
    new_read='''                foreach(var power in IomPowers.Values)
                {
                    var previous=power.Phase;uartWord|=power.ReadStatus();
                    if(previous=="off-requested" && power.Phase=="powered-off"
                        && !IomPowers.Values.Any(p => (p.Mask&power.IomDomainMask)!=0 && p.RequestWord!=0))
                        foreach(var gated in IomPowers.Values)
                            if((gated.Mask&power.IomDomainMask)!=0)gated.CompleteIomSharedPowerOff();
                }'''
    old_write='                else if(accepted && changedIom!=-1) accepted=IomPowers[changedIom].TryWrite(value&IomPowers[changedIom].Mask,BuckResponsePhase=="active",IomPowers[changedIom].CanShutdown());'
    new_write='''                else if(accepted && changedIom!=-1)
                {
                    var power=IomPowers[changedIom];
                    var held=IomPowers.Values.Any(p => p!=power && (p.Mask&power.IomDomainMask)!=0 && p.Phase=="on" && p.RequestWord==p.Mask && p.StatusWord==p.Mask);
                    accepted=power.SharedIomGate
                        ? power.TryWriteIomShared(value&power.Mask,BuckResponsePhase=="active",power.CanShutdown(),held)
                        : power.TryWrite(value&power.Mask,BuckResponsePhase=="active",power.CanShutdown());
                }'''
    for a,b in ((old_read,new_read),(old_write,new_write)):
        if model.count(a)!=1:raise ValueError('Unknown shared power dispatch')
        model=model.replace(a,b)
    return model


def board_profile(board):
    pattern=r'(iom[0-7]_power: Miscellaneous.BlackwallPeripheralPower\n)'
    changed,count=re.subn(pattern,r'\1    sharedIomGate: true\n',board)
    if count!=5:raise ValueError('Expected five declared IOM power owners')
    return changed
