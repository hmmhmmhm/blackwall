namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using System.Linq;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals;
    using Antmicro.Renode.Peripherals.CPU;
    using Antmicro.Renode.Peripherals.Bus;

    // Explicit synthetic slot contents; scanner-only is the default.
    // This is neither actual pairing data nor a writable persistent MRAM model.
    public sealed class BlackwallKeyDbSlotStorage : IBytePeripheral,IWordPeripheral,
        IDoubleWordPeripheral,IQuadWordPeripheral,IKnownSize
    {
        public BlackwallKeyDbSlotStorage(IMachine machine,CortexM cpu,long size,ulong baseAddress,
            string profile="unknown",uint uniformPc=0,uint loopPc=0,uint callerPc=0,bool readOnlySlots=false,BlackwallOtaMarkerRead otaMarker=null)
        {
            var pcs=new uint[]{uniformPc,loopPc,callerPc};
            if(machine==null || cpu==null || size!=0x8000 || baseAddress!=0x7f8000
                || profile!="unknown" && profile!="zero" && profile!="uninit-ff" || readOnlySlots && profile=="unknown"
                || (profile!="unknown" || pcs.Any(p=>p!=0)) && (pcs.Any(p=>p<0x438000 || p>=0x800000 || (p&1)!=0) || pcs.Distinct().Count()!=3))
                throw new ArgumentException("Explicit bounded keydb profile and distinct original consumers required");
            this.machine=machine;this.cpu=cpu;this.baseAddress=baseAddress;
            Profile=profile;UniformPc=uniformPc;LoopPc=loopPc;CallerPc=callerPc;ReadOnlySlots=readOnlySlots;OtaMarker=otaMarker;
            denied=new BlackwallStrictMMIO(size,baseAddress);Size=size;Reset();
        }
        public void Reset()
        {
            denied.Reset();Reads=CompletedSlots=SlotPosition=LastReadPc=0;
            DataReads=DataBytes=DataWordReads=DataByteReads=0;LastDataAddress=0;
            OtaMarker?.Reset();
        }
        public bool TrySample(uint pc,uint r0,uint r4,uint r7,ulong address,out byte value)
        {
            value=0;
            if(Profile=="unknown" || CompletedSlots>=10)return false;
            var slot=0x7ff000u+CompletedSlots*256u;
            if(pc==UniformPc && SlotPosition==0 && r0==slot && address==slot)SlotPosition=1;
            else if(pc==LoopPc && SlotPosition>=1 && SlotPosition<256 && r0==slot && r4==SlotPosition && address==slot+SlotPosition)SlotPosition++;
            else if(pc==CallerPc && SlotPosition==256 && r0==1 && r7==slot && address==slot) { CompletedSlots++;SlotPosition=0; }
            else return false;
            Reads++;LastReadPc=pc;value=Profile=="zero"?(byte)0:(byte)255;return true;
        }
        public byte ReadByte(long offset)
        {
            if(machine.SystemBus.TryGetCurrentCPU(out var current) && current==cpu
                && TrySample((uint)cpu.PC.RawValue,(uint)cpu.GetRegister(0).RawValue,
                    (uint)cpu.GetRegister(4).RawValue,(uint)cpu.GetRegister(7).RawValue,
                    baseAddress+(ulong)offset,out var value))return value;
            if(TryReadBacked(offset,1,out var data))return (byte)data;
            return denied.ReadByte(offset);
        }
        private bool TryReadBacked(long offset,int width,out ulong value)
        {
            value=0;
            if(!ReadOnlySlots || offset<0x7000 || offset>=0x7a00 || offset+width>0x7a00)return false;
            if(Profile=="uninit-ff")value=width==8?ulong.MaxValue:(1UL<<(width*8))-1;
            DataReads++;DataBytes+=(uint)width;LastDataAddress=baseAddress+(ulong)offset;
            if(width==4)DataWordReads++;
            if(width==1)DataByteReads++;
            return true;
        }
        public ushort ReadWord(long offset)=>TryReadBacked(offset,2,out var value)?(ushort)value:denied.ReadWord(offset);
        public uint ReadDoubleWord(long offset)
        {
            if(TryReadBacked(offset,4,out var data))return (uint)data;
            if(OtaMarker!=null && machine.SystemBus.TryGetCurrentCPU(out var current) && current==cpu
                && OtaMarker.TrySample((uint)cpu.PC.RawValue,(uint)cpu.GetRegister(0).RawValue,
                    (uint)cpu.GetRegister(4).RawValue,baseAddress+(ulong)offset,out var value))return value;
            return denied.ReadDoubleWord(offset);
        }
        public ulong ReadQuadWord(long offset)=>TryReadBacked(offset,8,out var value)?value:denied.ReadQuadWord(offset);
        public void WriteByte(long offset,byte value)=>denied.WriteByte(offset,value);
        public void WriteWord(long offset,ushort value)=>denied.WriteWord(offset,value);
        public void WriteDoubleWord(long offset,uint value)=>denied.WriteDoubleWord(offset,value);
        public void WriteQuadWord(long offset,ulong value)=>denied.WriteQuadWord(offset,value);
        public long Size {get;}
        public string Profile {get;}
        public bool ReadOnlySlots {get;}
        public BlackwallOtaMarkerRead OtaMarker {get;}
        public uint DataReads {get;private set;}
        public uint DataBytes {get;private set;}
        public uint DataWordReads {get;private set;}
        public uint DataByteReads {get;private set;}
        public ulong LastDataAddress {get;private set;}
        public uint UniformPc {get;}
        public uint LoopPc {get;}
        public uint CallerPc {get;}
        public uint Reads {get;private set;}
        public uint CompletedSlots {get;private set;}
        public uint SlotPosition {get;private set;}
        public uint LastReadPc {get;private set;}
        public int AccessCount=>denied.AccessCount;
        public ulong LastAddress=>denied.LastAddress;
        public int LastWidth=>denied.LastWidth;
        public string LastOperation=>denied.LastOperation;
        public ulong LastValue=>denied.LastValue;
        private readonly IMachine machine;
        private readonly CortexM cpu;
        private readonly ulong baseAddress;
        private readonly BlackwallStrictMMIO denied;
    }
}
