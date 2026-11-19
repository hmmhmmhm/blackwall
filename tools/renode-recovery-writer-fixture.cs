namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using System.Collections.Generic;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Core.Structure.Registers;
    using Antmicro.Renode.Peripherals.IRQControllers;
    using Antmicro.Renode.Peripherals.Bus;
    using Antmicro.Renode.Peripherals.CPU;
    using Antmicro.Renode.Logging.Profiling;

    // Executable IO routes CPU stores through the write boundary; MappedMemory's
    // fast path and post-access observer cannot veto an already committed store.
    public sealed class BlackwallProtectedMram : Antmicro.Renode.Peripherals.Memory.ArrayMemory
    {
        public BlackwallProtectedMram(ulong size) : base(size) {}
        public void Arm(){Armed=true;}
        public bool Armed {get;private set;}
        public uint RejectedWrites {get;private set;}
        public long LastRejectedOffset {get;private set;}
        private bool Reject(long offset){if(!Armed)return false;RejectedWrites++;LastRejectedOffset=offset;return true;}
        public override void WriteByte(long offset,byte value){if(!Reject(offset))base.WriteByte(offset,value);}
        public override void WriteWord(long offset,ushort value){if(!Reject(offset))base.WriteWord(offset,value);}
        public override void WriteDoubleWord(long offset,uint value){if(!Reject(offset))base.WriteDoubleWord(offset,value);}
        public override void WriteQuadWord(long offset,ulong value){if(!Reject(offset))base.WriteQuadWord(offset,value);}
        // Only the bounded ROM fixture calls this after ABI/range validation.
        internal void ProgramDoubleWord(long offset,uint value){base.WriteDoubleWord(offset,value);}
    }
    // Isolated replay fixture. ROM programming, time, GPIO and UART readiness are hypotheses.
    public sealed class BlackwallRecoveryWriterFixture : IDoubleWordPeripheral, IKnownSize
    {
        public BlackwallRecoveryWriterFixture(IMachine machine,CortexM cpu,NVIC nvic,uint initialTick,
            uint returnPc,uint writerPc,uint recvPc,uint sendPc,uint destination,uint length,
            uint romStatus=0,bool corruptReadback=false,int interruptAfterWords=-1,bool fullMainRestore=false,bool bootRestore=false)
        {
            this.machine=machine;this.cpu=cpu;this.nvic=nvic;Tick=initialTick;Destination=destination;Length=length;
            RomStatus=romStatus;CorruptReadback=corruptReadback;FullMainRestore=fullMainRestore;BootRestore=bootRestore;
            if(interruptAfterWords < -1 || interruptAfterWords>(int)(length/4))throw new ArgumentException("Bounded virtual word interruption required");
            InterruptAfterWords=interruptAfterWords;
            if(!ValidWriteScope(destination,length,fullMainRestore,bootRestore))
                throw new ArgumentException("Bounded virtual main body fixture required");
            cpu.AddHook(0x4160e8,(c,a)=>{TickCalls++;Return(Tick);});
            cpu.AddHook(0x416378,(c,a)=>{DelayCalls++;Tick+=(uint)cpu.GetRegister(0).RawValue;Return(0);});
            cpu.AddHook(0x41d92c,(c,a)=>{GpioCalls++;Return(0);});
            cpu.AddHook(0x41b8ec,(c,a)=>{var mask=(uint)cpu.GetRegister(28).RawValue;cpu.SetRegister(28,1u);Return(mask);});
            cpu.AddHook(0x41bd92,(c,a)=>Return(0));
            cpu.AddHook(0x41bde4,(c,a)=>Return(0));
            cpu.AddHook(0x0200ff20,(c,a)=>Program());
            cpu.AddHook(0x434910,(c,a)=>{ContextEntries++;});
            cpu.AddHook(writerPc,(c,a)=>{WriterEntries++;});
            cpu.AddHook(0x42e84c,(c,a)=>{StockMramEntries++;});
            cpu.AddHook(recvPc,(c,a)=>{ReceiveCalls++;});
            cpu.AddHook(sendPc,(c,a)=>{SendCalls++;});
            cpu.AddHook(returnPc,(c,a)=>
            {
                ContextReturns++;
                for(var n=0;n<15;n++)ReturnRegisters[n]=(uint)cpu.GetRegister(n).RawValue;
                foreach(var index in new[]{18,19,25,28,30,31,74})ReturnSpecial[index]=(uint)cpu.GetRegister(index).RawValue;
                for(var n=0;n<32;n++)ReturnFloat[n]=(uint)cpu.GetRegister(75+n).RawValue;
            });
            cpu.SetHookAtBlockBegin((pc,count)=>
            {
                Blocks++;LastBlock=pc;
                if(BootRestore && initialBoot!=null && pc>=0x410000 && pc+2<=0x437000)
                {
                    var offset=(int)(pc-0x410000);var before=(uint)(initialBoot[offset]|initialBoot[offset+1]<<8);
                    var now=(uint)machine.SystemBus.ReadWord(pc);
                    if(before!=now){ChangedCodeFetches++;if(FirstChangedCodePc==0){FirstChangedCodePc=pc;OriginalCodeWord=before;UpdatedCodeWord=now;}}
                }
                if(!((pc>=0x410000 && pc<0x437000) || (pc>=0x20000000 && pc<0x20080000) || pc==0x0200ff20))Fail("unexpected instruction",pc);
            });
            cpu.SetHookAtMemoryAccess((pc,op,va,pa,width,value)=>
            {
                var bytes=(ulong)width;
                var write=op==MemoryOperation.MemoryWrite || op==MemoryOperation.MemoryIOWrite;
                if(write && pa>=0x400000 && pa<0x800000)Fail("guest MRAM write outside ROM model",pa);
                var allowed=(pa>=0x20000000 && pa+bytes<=0x20080000)
                    || (!write && pa>=0x400000 && pa+bytes<=0x800000)
                    || (!write && pa==0x0200ff20 && bytes<=4)
                    || (pa>=0x4003b000 && pa+bytes<=0x4003b01c)
                    || (pa>=0x40014000 && pa+bytes<=0x40014028)
                    || (pa>=0xe000e000 && pa+bytes<=0xe000f000);
                if(!allowed)Fail("unexpected memory access",pa);
            });
        }
        public void AttachCache()
        {
            if(cacheAttached)throw new InvalidOperationException("Cache fixture already attached");
            nvic.RegisterCollection.DefineRegister(0xf5c).WithValueField(0,32,FieldMode.Write,name:"bounded_readback_cache_invalidate");
            machine.SystemBus.SetHookBeforePeripheralWrite<uint>(nvic,(value,offset)=>
            {
                if(offset==0xf5c)
                {
                    if((value&31)!=0 || value<(Destination&~31u) || value>=Destination+Length)Fail("cache maintenance outside body",value);
                    CacheLines.Add(value);return 0;
                }
                return value;
            });
            if(BootRestore)initialBoot=machine.SystemBus.ReadBytes(0x410000,0x27000,true);
            cacheAttached=true;
        }
        private void Return(uint value){cpu.SetRegister(0,value);cpu.PC=(uint)cpu.GetRegister(14).RawValue;}
        public void SeedRegister(int index,uint value){if(index==15)cpu.PC=value;else cpu.SetRegister(index,value);}
        // Policy of this declared fixture only; not a claim about silicon ROM permissions.
        internal static bool ValidWriteScope(uint destination,uint length,bool full,bool boot=false)
        {
            if(full && boot)return false;
            if(boot)return destination==0x410000 && (length==149776 || length==159744) || destination==0x434910 && length==9968;
            return full ? (destination==0x438010 && length==3700064 || destination==0x438000 && length==16)
                : destination==0x438010 && length>0 && length<=4096 && (length&15)==0;
        }
        internal static bool ValidProgramRequest(ulong key,ulong operation,ulong wordOffset,
            ulong wordCount,ulong source,bool interruptsMasked,uint destination,uint length,bool fullMainRestore=false,bool bootRestore=false)
        {
            if(key!=0x12344321 || operation!=1 || !interruptsMasked || wordOffset>0xfffff
                || wordCount==0 || wordCount>64 || (wordCount&3)!=0
                || !ValidWriteScope(destination,length,fullMainRestore,bootRestore))return false;
            var address=0x400000UL+4*wordOffset;var bytes=4*wordCount;
            return address>=destination && address+bytes<=(ulong)destination+length
                && source>=0x20000000 && source<=0x20080000-bytes;
        }
        private void Program()
        {
            var source=(uint)cpu.GetRegister(2).RawValue;
            if(cpu.GetRegister(3).RawValue>0xfffff || machine.SystemBus.ReadDoubleWord(cpu.GetRegister(13).RawValue)>64)
                Fail("ROM word address/count overflow",source);
            var destination=0x400000u+4u*(uint)cpu.GetRegister(3).RawValue;
            var count=4u*machine.SystemBus.ReadDoubleWord(cpu.GetRegister(13).RawValue);
            if(!ValidProgramRequest(cpu.GetRegister(0).RawValue,cpu.GetRegister(1).RawValue,
                cpu.GetRegister(3).RawValue,count/4,source,cpu.GetRegister(28).RawValue==1,Destination,Length,FullMainRestore,BootRestore))
                Fail("invalid ROM programming ABI/range",destination);
            RomCalls++;ProgramDestinations.Add(destination);ProgramLengths.Add(count);
            if(RomStatus==0)
            {
                for(uint offset=0;offset<count;offset+=4)
                {
                    if(InterruptNow())return;
                    ((BlackwallProtectedMram)machine["sysbus.mram"]).ProgramDoubleWord(destination+offset-0x400000,machine.SystemBus.ReadDoubleWord(source+offset));
                    ProgrammedBytes+=4;
                }
                if(InterruptNow())return;
                if(CorruptReadback)((BlackwallProtectedMram)machine["sysbus.mram"]).ProgramDoubleWord(destination-0x400000,machine.SystemBus.ReadDoubleWord(destination)^1u);
                // Functional coherent executable IO, not a physical M55 I-cache model.
                // InvalidateTranslationBlocks alone only drains an already queued range.
                cpu.OrderTranslationBlocksInvalidation(new IntPtr((long)destination),new IntPtr((long)destination+count));
                CodeInvalidations++;
            }
            Return(RomStatus);
        }
        // A declared atomic-word prefix fault model, not silicon power-loss physics.
        private bool InterruptNow()
        {
            if(InterruptAfterWords<0 || ProgrammedBytes/4!=(uint)InterruptAfterWords)return false;
            PowerInterrupted=true;cpu.IsHalted=true;return true;
        }
        public int InterruptAfterWords {get;}
        public bool PowerInterrupted {get;private set;}
        public void Enqueue(byte[] data){foreach(var value in data)incoming.Enqueue(value);}
        public uint ReadDoubleWord(long offset)
        {
            if(offset==0x18)return incoming.Count==0 ? 0x10u : 0u;
            if(offset==0 && incoming.Count>0){RxBytes++;return incoming.Dequeue();}
            Fail("unsupported UART read",(ulong)offset);return 0;
        }
        public void WriteDoubleWord(long offset,uint value)
        {
            if(offset==4)return;
            if(offset!=0)Fail("unsupported UART write",(ulong)offset);
            TxBytes++;outgoing.Add((byte)value);int needed=0;
            if(outgoing.Count>=4 && outgoing[0]==0x5a && outgoing[1]==0xa5)needed=outgoing[3]+5;
            else if(outgoing.Count>=8 && outgoing[0]==66 && outgoing[1]==76 && outgoing[2]==75 && outgoing[3]==50)needed=outgoing[6]+(outgoing[7]<<8)+12;
            if(needed!=0 && outgoing.Count==needed)
            {
                var frame=outgoing.ToArray();Frames.Add(frame);outgoing.Clear();
                if(frame.Length==32 && frame[12]==2){ResultSeen=true;cpu.IsHalted=true;}
            }
        }
        private void Fail(string reason,ulong address){Violations++;Failure=reason;FailureAddress=address;throw new CpuAbortException("BLACKWALL recovery fixture "+reason+" at "+address);}
        public void Reset(){}
        public long Size=>0x1c;
        public bool FullMainRestore {get;} public bool BootRestore {get;}
        public uint Destination {get;} public uint Length {get;} public uint RomStatus {get;} public bool CorruptReadback {get;}
        public uint CodeInvalidations {get;private set;} public uint ChangedCodeFetches {get;private set;} public ulong FirstChangedCodePc {get;private set;} public uint OriginalCodeWord {get;private set;} public uint UpdatedCodeWord {get;private set;}
        public uint Tick {get;private set;} public uint TickCalls {get;private set;} public uint DelayCalls {get;private set;} public uint GpioCalls {get;private set;}
        public uint ContextEntries {get;private set;} public uint ContextReturns {get;private set;} public uint WriterEntries {get;private set;}
        public uint StockMramEntries {get;private set;} public uint RomCalls {get;private set;} public uint ProgrammedBytes {get;private set;}
        public uint ReceiveCalls {get;private set;} public uint SendCalls {get;private set;} public uint RxBytes {get;private set;} public uint TxBytes {get;private set;}
        public int Violations {get;private set;} public bool ResultSeen {get;private set;}
        public string Failure {get;private set;}="none";public ulong FailureAddress {get;private set;}
        public ulong Blocks {get;private set;} public ulong LastBlock {get;private set;}
        public uint[] ReturnRegisters {get;}=new uint[15]; public uint[] ReturnFloat {get;}=new uint[32];
        public Dictionary<int,uint> ReturnSpecial {get;}=new Dictionary<int,uint>();
        public List<uint> CacheLines {get;}=new List<uint>();
        public List<byte[]> Frames {get;}=new List<byte[]>(); public List<uint> ProgramDestinations {get;}=new List<uint>();public List<uint> ProgramLengths {get;}=new List<uint>();
        private readonly Queue<byte> incoming=new Queue<byte>();private readonly List<byte> outgoing=new List<byte>();
        private byte[] initialBoot;
        private readonly IMachine machine;private readonly CortexM cpu;private readonly NVIC nvic;private bool cacheAttached;
    }
    public sealed class BlackwallRecoveryMramControl : IDoubleWordPeripheral,IKnownSize
    {
        public uint ReadDoubleWord(long offset){if(offset==8)return key;if(offset==0x24)return config;throw new CpuAbortException("Unsupported MRAM control read");}
        public void WriteDoubleWord(long offset,uint value){if(offset==8 && (value==0 || value==0xc3))key=value;else if(offset==0x24 && value==0)config=value;else throw new CpuAbortException("Unsupported MRAM control write");Writes++;}
        public void Reset(){key=config=Writes=0;}public long Size=>0x28;public uint Writes {get;private set;}private uint key,config;
    }
}
