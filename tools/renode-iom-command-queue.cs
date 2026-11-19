namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    // Functional CQ for software/index pause inputs; external flag inputs and timing are unsupported.
    public sealed class BlackwallIomCommandQueue
    {
        public BlackwallIomCommandQueue(ulong baseAddress,System.Func<uint,uint> readMemory,System.Action<long,uint> writeRegister,System.Action<uint> interrupt,System.Action<long,string,uint> block,int inputLevels=-1)
        { if(inputLevels < -1 || inputLevels>31) throw new System.ArgumentException("CQ input levels must be unknown(-1) or a five-bit mock vector"); InputLevels=inputLevels; this.baseAddress=baseAddress; this.readMemory=readMemory; this.writeRegister=writeRegister; this.interrupt=interrupt; this.block=block; Reset(); }
        public void Reset() { ClearRegisters(); Pairs=0; LastPairAddress=LastTarget=LastData=0; LastError="none"; }
        public void PowerDown() { ClearRegisters(); }
        private void ClearRegisters() { Configuration=Address=SoftwareFlags=CurrentIndex=EndIndex=PauseEnable=IrqMask=0; Paused=running=pauseSignal=false; addressRevision=0; }
        public bool Enabled => (Configuration&1)!=0;
        public uint Status => Enabled ? 1u|(Paused?2u:0u) : 0u;
        public uint KnownFlags => SoftwareFlags|(CurrentIndex==EndIndex ? 0x8000u:0u);
        public int InputLevels {get;}
        public uint AvailableFlagsMask => InputLevels<0 ? 0x80ffu:0xffffu;
        public uint EffectiveFlags
        {
            get
            {
                if(InputLevels<0) return KnownFlags;
                return FlagsForInputLevels(InputLevels);
            }
        }
        public uint FlagsForInputLevels(int levels)
        {
            if(levels<0 || levels>31)throw new System.ArgumentException("Five-bit CQ representative vector required");
            var x0=((uint)levels^SoftwareFlags)&1u;
            var x1=(((uint)levels^SoftwareFlags)>>1)&1u;
            return KnownFlags|(x0<<8)|(x1<<9)|((x0^1u)<<10)|((x1^1u)<<11)|((((uint)levels^SoftwareFlags)&0x1cu)<<10);
        }
        public static bool Owns(long offset) => offset>=0x228 && offset<=0x244 && (offset&3)==0;
        private static bool ValidSource(uint address) => (address&3)==0 && address>=0x20000000u && (ulong)address+8<=0x20380000ul;
        private void Fail(long offset,string reason,uint value=0) { LastError=reason; block(offset,"cq-"+reason,value); }
        public uint Read(long offset)
        {
            switch(offset)
            {
            case 0x228:return Configuration;case 0x22c:return Address;case 0x230:return Status;
            case 0x23c:return PauseEnable;case 0x240:return CurrentIndex;case 0x244:return EndIndex;
            case 0x234:if(InputLevels<0) { Fail(offset,"external-flags-unknown");return 0; } return EffectiveFlags|(IrqMask<<16);
            case 0x238:Fail(offset,"command-readback-unknown");return 0;
            default:Fail(offset,"unknown-read");return 0;
            }
        }
        public void Write(long offset,uint value)
        {
            switch(offset)
            {
            case 0x228:
                if((value&~3u)!=0) { Fail(offset,"external-selector",value);return; }
                if((value&1)!=0 && !ValidSource(Address)) { Fail(offset,"fetch-range",Address);return; }
                Configuration=value;
                if(!Enabled) { Paused=false;pauseSignal=false; }
                break;
            case 0x22c:
                if(!ValidSource(value) && !(value==0 && !Enabled)) { Fail(offset,"fetch-range",value);return; }
                Address=value;addressRevision++;break;
            case 0x230:Fail(offset,"status-read-only",value);return;
            case 0x234:
                if(((value>>16)&~AvailableFlagsMask)!=0) { Fail(offset,"irq-mask-unknown",value);return; }
                IrqMask=value>>16;break;
            case 0x238:
                var set=value&255;var toggle=(value>>8)&255;var clear=(value>>16)&255;
                if((set&toggle)!=0 || (set&clear)!=0 || (toggle&clear)!=0 || (value&0xff000000)!=0) { Fail(offset,"flag-overlap",value);return; }
                SoftwareFlags=((SoftwareFlags|set)^toggle)&~clear;break;
            case 0x23c:
                if((value&~AvailableFlagsMask)!=0) { Fail(offset,"pause-input-unknown",value);return; }
                PauseEnable=value;break;
            case 0x240:
                if(value>255) { Fail(offset,"index-width",value);return; }
                CurrentIndex=value;break;
            case 0x244:
                if(value>255) { Fail(offset,"index-width",value);return; }
                EndIndex=value;break;
            default:Fail(offset,"unknown-write",value);return;
            }
            Pump();
        }
        private void SetPaused(bool paused)
        {
            Paused=paused;
            var signal=Enabled && paused && (EffectiveFlags&PauseEnable&IrqMask)!=0;
            if(signal && !pauseSignal) interrupt(1u<<12);
            pauseSignal=signal;
        }
        private void Pump()
        {
            if(running || !Enabled) return;
            running=true;
            try
            {
                int steps=0;
                while(Enabled)
                {
                    if((EffectiveFlags&PauseEnable)!=0) { SetPaused(true);return; }
                    SetPaused(false);
                    if(steps>=4096) { Fail(0x228,"model-pair-budget",Address);return; }
                    if(!ValidSource(Address)) { Fail(0x22c,"fetch-range",Address);return; }
                    var source=Address;
                    var encodedTarget=readMemory(source);var data=readMemory(source+4);
                    var target=encodedTarget&~1u;
                    LastPairAddress=source;LastTarget=target;LastData=data;
                    if((target&3)!=0 || (ulong)target<baseAddress || (ulong)target>=baseAddress+0x400)
                    { Fail(0x228,"foreign-target",encodedTarget);return; }
                    var revision=addressRevision;
                    try { writeRegister((long)((ulong)target-baseAddress),data); }
                    catch { LastError="target-write-blocked";throw; }
                    if(revision==addressRevision) Address=source+8;
                    Pairs++;steps++;
                    if((encodedTarget&1)!=0) interrupt(1u<<13);
                }
                SetPaused(false);
            }
            finally { running=false; }
        }
        public uint Configuration {get;private set;}
        public uint Address {get;private set;}
        public uint SoftwareFlags {get;private set;}
        public uint CurrentIndex {get;private set;}
        public uint EndIndex {get;private set;}
        public uint PauseEnable {get;private set;}
        public uint IrqMask {get;private set;}
        public bool Paused {get;private set;}
        public long Pairs {get;private set;}
        public uint LastPairAddress {get;private set;}
        public uint LastTarget {get;private set;}
        public uint LastData {get;private set;}
        public string LastError {get;private set;}
        private bool running,pauseSignal;
        private ulong addressRevision;
        private readonly ulong baseAddress;
        private readonly System.Func<uint,uint> readMemory;
        private readonly System.Action<long,uint> writeRegister;
        private readonly System.Action<uint> interrupt;
        private readonly System.Action<long,string,uint> block;
    }
}
