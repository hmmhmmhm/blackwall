namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using Antmicro.Renode.Peripherals.CPU;
    using Antmicro.Renode.Core;
    using System;
    using System.Collections.Generic;
    // Observation only. Does not replace the existing block/memory hooks or mutate guest state.
    public sealed class BlackwallExecutionObserver
    {
        public BlackwallExecutionObserver(CortexM cpu, int eventCapacity=128)
        {
            if(eventCapacity<1 || eventCapacity>32768) throw new System.ArgumentException("Invalid observation event capacity");
            this.cpu=cpu; Capacity=eventCapacity;
        }
        public void AddPoint(string label, uint address)
        {
            if(string.IsNullOrEmpty(label) || (address&1)!=0 || points.Count>=128 || points.ContainsKey(address))
                throw new System.ArgumentException("Observation requires unique aligned instruction points");
            foreach(var p in points.Values) if(p.Label==label) throw new System.ArgumentException("Duplicate observation label");
            var point=new BlackwallObservedPoint(label,address);
            points.Add(address,point);
            CpuAddressHook callback=(c,a) => {
                point.Hits++; Sequence++;
                if(point.FirstSequence==0) point.FirstSequence=Sequence;
                if(events.Count==Capacity) { events.Dequeue(); DroppedEvents++; }
                events.Enqueue(new BlackwallPcEvent(Sequence,label,address,cpu.PC.RawValue,cpu.GetRegister(0).RawValue,cpu.GetRegister(2).RawValue));
                if(point.ReadContext!=null && point.Context==null) point.Context=point.ReadContext();
                if(point.ReadSnapshot!=null && point.Snapshot==null)
                    point.Snapshot=new BlackwallSramSnapshot(Sequence,point.SnapshotAddress,point.ReadSnapshot());
            };
            point.Callback=callback;
            cpu.AddHook(address,callback);
        }
        public bool SuspendPoint(string label)
        {
            if(string.IsNullOrEmpty(label)) throw new System.ArgumentException("Observation label required");
            BlackwallObservedPoint point=null;
            foreach(var p in points.Values) if(p.Label==label) point=p;
            if(point==null) throw new System.ArgumentException("Unknown observation label");
            if(point.Suspended) return false;
            cpu.RemoveHook(point.Address,point.Callback);
            point.Suspended=true;
            return true;
        }
        public void CaptureCpuContext(string label)
        {
            BlackwallObservedPoint point=null;
            foreach(var p in points.Values) if(p.Label==label) point=p;
            if(point==null || point.Hits!=0 || point.ReadContext!=null)
                throw new ArgumentException("CPU context requires an unused observation point");
            point.ReadContext=() => {
                var sp=cpu.GetRegister(13).RawValue;
                var other=cpu.GetRegister(22).RawValue;
                var process=cpu.IsUsingProcessSP;
                return new BlackwallCpuContextSnapshot {
                    Sequence=Sequence, PC=cpu.PC.RawValue, SP=sp,
                    MSP=process ? other : sp, PSP=process ? sp : other,
                    Control=cpu.GetRegister(18).RawValue, Xpsr=cpu.GetRegister(25).RawValue,
                    VectorTableOffset=cpu.VectorTableOffset, ProcessStackSelected=process
                };
            };
        }
        public void CaptureSram(IMachine machine,string label,uint address,int words)
        {
            if(words<1 || words>16 || (address&3)!=0 || address<0x20000000 || (ulong)address+4UL*(ulong)words>0x20380000)
                throw new ArgumentException("Snapshot requires bounded G2 SRAM words");
            BlackwallObservedPoint point=null;
            foreach(var p in points.Values) if(p.Label==label) point=p;
            if(point==null || point.Hits!=0 || point.ReadSnapshot!=null) throw new ArgumentException("Snapshot requires an unused observation point");
            point.SnapshotAddress=address;
            point.ReadSnapshot=() => {
                var data=new uint[words];
                for(var i=0;i<words;i++) data[i]=machine.SystemBus.ReadDoubleWord(address+4u*(uint)i);
                return data;
            };
        }
        public IEnumerable<BlackwallObservedPoint> Points => points.Values;
        public IEnumerable<BlackwallPcEvent> Events => events;
        public int Capacity { get; }
        public ulong Sequence { get; private set; }
        public ulong DroppedEvents { get; private set; }
        private readonly CortexM cpu;
        private readonly Dictionary<uint,BlackwallObservedPoint> points=new Dictionary<uint,BlackwallObservedPoint>();
        private readonly Queue<BlackwallPcEvent> events=new Queue<BlackwallPcEvent>();
    }
    public sealed class BlackwallObservedPoint
    {
        public BlackwallObservedPoint(string label,uint address) { Label=label; Address=address; }
        public string Label { get; }
        public uint Address { get; }
        public ulong Hits { get; internal set; }
        public ulong FirstSequence { get; internal set; }
        public bool Suspended { get; internal set; }
        public BlackwallCpuContextSnapshot Context { get; internal set; }
        public BlackwallSramSnapshot Snapshot { get; internal set; }
        internal uint SnapshotAddress;
        internal Func<uint[]> ReadSnapshot;
        internal Func<BlackwallCpuContextSnapshot> ReadContext;
        internal CpuAddressHook Callback;
    }
    public sealed class BlackwallCpuContextSnapshot
    {
        public ulong Sequence { get; internal set; }
        public ulong PC { get; internal set; }
        public ulong SP { get; internal set; }
        public ulong MSP { get; internal set; }
        public ulong PSP { get; internal set; }
        public ulong Control { get; internal set; }
        public ulong Xpsr { get; internal set; }
        public uint VectorTableOffset { get; internal set; }
        public bool ProcessStackSelected { get; internal set; }
    }
    public sealed class BlackwallSramSnapshot
    {
        public BlackwallSramSnapshot(ulong sequence,uint address,uint[] words) { Sequence=sequence; Address=address; Words=words; }
        public ulong Sequence { get; }
        public uint Address { get; }
        public uint[] Words { get; }
    }
    public sealed class BlackwallPcEvent
    {
        public BlackwallPcEvent(ulong sequence,string label,uint address,ulong pc,ulong r0,ulong r2)
        { Sequence=sequence; Label=label; Address=address; PC=pc; R0=r0; R2=r2; }
        public ulong Sequence { get; }
        public string Label { get; }
        public uint Address { get; }
        public ulong PC { get; }
        public ulong R0 { get; }
        public ulong R2 { get; }
    }
}
