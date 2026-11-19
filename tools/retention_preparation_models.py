"""Expose reset control words of unselected TIMER channels from the existing shared engine."""
def compose_timer_controls(model):
    begin=model.index('    public sealed class BlackwallTimer14 : IBlackwallTimer14')
    end=model.index('\n    }\n}',begin)+len('\n    }')
    text=model[begin:end]
    edits=[('string timer7Profile="none")','string timer7Profile="none",bool idleChannelControls=false)'),
      ('            engine=new BlackwallApolloTimerEngine(machine);Reset();','            IdleChannelControls=idleChannelControls;engine=new BlackwallApolloTimerEngine(machine);Reset();'),
      ('public bool Owns(ulong a)=>','public bool Owns(ulong a)=>IsIdleControl(a) || '),
      ('            value=a==0x400083c0 ?', '''            if(IsIdleControl(a))
            {
                value=engine.ReadDoubleWord((long)(a-0x40008000));
                if(value!=0)return false;
                IdleControlReads[(a-0x40008200)/0x20]++;Reads++;return true;
            }
            value=a==0x400083c0 ?'''),
      ('            if(!Owns(a))return false;','            if(!Owns(a) || IsIdleControl(a))return false;'),
      ('public void Reset() {engine.Reset();','public void Reset() {System.Array.Clear(IdleControlReads,0,16);engine.Reset();'),
      ('        private readonly BlackwallApolloTimerEngine engine;', '''        public bool IdleChannelControls {get;}
        public uint[] IdleControlReads {get;}=new uint[16];
        private bool IsIdleControl(ulong a)
        {
            if(!IdleChannelControls || a<0x40008200 || a>0x400083e0 || ((a-0x40008200)&31)!=0)return false;
            var n=(a-0x40008200)/32;
            return n!=14 && (n!=0 || !Timer0Enabled) && (n!=7 || !Timer7Enabled);
        }
        private readonly BlackwallApolloTimerEngine engine;''')]
    for old,new in edits:
        if text.count(old)!=1:raise ValueError('Unreviewed shared TIMER adapter: '+old)
        text=text.replace(old,new)
    return model[:begin]+text+model[end:]

def compose_inactive_audio(model):
    begin=model.index('    public sealed class BlackwallCpuNormalSleep : IPeripheral')
    end=model.index('    public class BlackwallPeripheralPower',begin)
    text=model[begin:end]
    edits=[('uint retentionReturnPc=0)','uint retentionReturnPc=0,bool inactiveAudioStatus=false)'),
        ('RetentionReturnPc=retentionReturnPc;Reset();','RetentionReturnPc=retentionReturnPc;InactiveAudioStatus=inactiveAudioStatus;Reset();'),
        ('public bool Owns(ulong address) =>','public bool Owns(ulong address) => (InactiveAudioStatus && address==0x40021010) || '),
        ('CpdValue=RetentionStages=0;','CpdValue=RetentionStages=AudioStatusReads=0;'),
        ('            value=0;\n            if(address==0x40021050)', '            value=0;\n            if(InactiveAudioStatus && address==0x40021010) { AudioStatusReads++;return true; }\n            if(address==0x40021050)'),
        ('        public uint RetentionStorePc {','        public bool InactiveAudioStatus {get;}\n        public uint AudioStatusReads {get;private set;}\n        public uint RetentionStorePc {')]
    for old,new in edits:
        if text.count(old)!=1:raise ValueError('Unknown inactive audio boundary: '+old)
        text=text.replace(old,new)
    return model[:begin]+text+model[end:]

def compose_retention_flush(model):
    begin=model.index('    public sealed class BlackwallCpuNormalSleep : IPeripheral')
    end=model.index('    public class BlackwallPeripheralPower',begin)
    text=model[begin:end]
    edits=[('bool inactiveAudioStatus=false)','bool inactiveAudioStatus=false,bool retentionFlush=false)'),
        ('InactiveAudioStatus=inactiveAudioStatus;Reset();','InactiveAudioStatus=inactiveAudioStatus;RetentionFlush=retentionFlush;Reset();'),
        ('RetentionStages=AudioStatusReads=0;','RetentionStages=AudioStatusReads=RetentionFlushes=0;'),
        ('            if(pc!=FlushReadPc || baseRegister!=0x47ff0000u || CpdValue!=0x11u', '''            if(RetentionFlush && pc==FlushReadPc && baseRegister==0x47ff0000u && CpdValue==0x22u && RetentionStages>RetentionFlushes)
            {
                if(!machine.SystemBus.TryGetCurrentCPU(out var current) || !(current is CortexM) || (machine.SystemBus.ReadDoubleWord(0xe000ed10)&4u)==0)return false;
                RetentionFlushes++;return true;
            }
            if(pc!=FlushReadPc || baseRegister!=0x47ff0000u || CpdValue!=0x11u'''),
        ('        public bool InactiveAudioStatus {','        public bool RetentionFlush {get;}\n        public uint RetentionFlushes {get;private set;}\n        public bool InactiveAudioStatus {')]
    for old,new in edits:
        if text.count(old)!=1:raise ValueError('Unknown retention flush boundary: '+old)
        text=text.replace(old,new)
    return model[:begin]+text+model[end:]
