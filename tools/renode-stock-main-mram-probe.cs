namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using System.Collections.Generic;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals.CPU;
    using Antmicro.Renode.Peripherals.Bus;
    using Antmicro.Renode.Logging.Profiling;

    // Isolated diagnostic caller. Original main IRQ/power/callback code runs;
    // only the unavailable ROM program entry is a declared functional model.
    public sealed class BlackwallStockMainMramProbe : IDoubleWordPeripheral, IKnownSize
    {
        public BlackwallStockMainMramProbe(IMachine machine,CortexM cpu,uint romStatus=0,bool corruptReadback=false,bool powerReady=true,bool chipProfile=false,bool delayProfile=false,bool bootRestore=false)
        {
            this.machine=machine;this.cpu=cpu;RomStatus=romStatus;CorruptReadback=corruptReadback;
            BootRestore=bootRestore;
            if(bootRestore && (!chipProfile || !delayProfile))throw new ArgumentException("Full boot diagnostic requires initialized chip/delay profile");
            Power=new BlackwallMemoryStartup(powerReady?1:0);
            if(chipProfile)Chip=new BlackwallChipIdentity(0x23,0,0);
            if(delayProfile)Clock=new BlackwallMcuClock(new BlackwallHalStorage(),"hp",0);
            if(!Power.TryWrite(0x40021014,0x1f))throw new ArgumentException("Initial ROM-off profile rejected");
            foreach(var pc in new uint[]{0x4f5864,0x488d34,0x5c69f8,0x5c6994,0x494aae,0x5c2226,0x494b00,0x5791e8,0x480dc8,0x446ab4,0x480c14,0x5c69d0})
            {
                Hits[pc]=0;var address=pc;cpu.AddHook(address,(c,a)=>{Hits[address]++;});
            }
            cpu.AddHook(0x5c69b2,(c,a)=>{InfoReturned=true;InfoReturn=(uint)cpu.GetRegister(0).RawValue;InfoMramSize=machine.SystemBus.ReadDoubleWord(cpu.GetRegister(13).RawValue+0x2c);});
            cpu.AddHook(0x4f5836,(c,a)=>{PowerReturn=(uint)cpu.GetRegister(0).RawValue;PowerReturned=true;});
            cpu.AddHook(0x495ed2,(c,a)=>{DelayCalls++;});
            cpu.AddHook(0x495ed6,(c,a)=>{DelayReturns++;});
            cpu.AddHook(0x446b0e,(c,a)=>{VerifierCompared=true;VerifierCompare=(uint)cpu.GetRegister(0).RawValue;});
            cpu.AddHook(0x0200ff20,(c,a)=>Program());
            cpu.SetHookAtBlockBegin((pc,count)=>
            {
                if(pc==0x0200ff20 && (Power.Registers[0x40021018].Value&0x80)==0)
                {
                    RomUnreadyBoundary=true;throw new CpuAbortException("BLACKWALL original main attempted unready ROM");
                }
                if(!((pc>=0x438000 && pc<0x7bf564) || (pc>=0x20000000 && pc<0x20380000) || pc==0x0200ff20 || Clock!=null && pc>=0x40 && pc<0x46))
                {Violation("unexpected instruction",pc);}
            });
            cpu.SetHookAtMemoryAccess((pc,op,va,pa,width,value)=>
            {
                var write=op==MemoryOperation.MemoryWrite || op==MemoryOperation.MemoryIOWrite;var n=(ulong)width;
                if(write && pa>=0x400000 && pa<0x800000)Violation("direct guest MRAM store",pa);
                var allowed=pa>=0x20000000 && pa+n<=0x20380000
                    || !write && Clock!=null && pa>=0x40 && pa+n<=0x46
                    || !write && pa>=0x400000 && pa+n<=0x800000
                    || !write && pa>=0x0200f000 && pa+n<=0x02010000
                    || pa>=0x40020000 && pa+n<=0x40022000
                    || pa>=0x40014000 && pa+n<=0x40014028
                    || pa>=0xe000e000 && pa+n<=0xe000f000
                    || Chip!=null && pa>=0xe00fefe0 && pa+n<=0xe00ff000;
                if(!allowed)Violation("unexpected memory",pa);
            });
        }
        public void Start(uint caller,uint done)
        {
            ((BlackwallProtectedMram)machine["sysbus.mram"]).Arm();
            cpu.FpuEnabled=true;cpu.SetRegister(27,0xf00000u);
            for(int n=4;n<12;n++)cpu.SetRegister(n,(uint)(0xdead0000+n));
            cpu.SetRegister(13,0x2007f000u);cpu.SetRegister(14,done|1u);
            InitialPrimask=(uint)cpu.GetRegister(28).RawValue;InitialControl=(uint)cpu.GetRegister(18).RawValue;
            cpu.AddHook(done,(c,a)=>{Completed=true;cpu.IsHalted=true;});cpu.PC=caller|1u;
        }
        internal static bool ValidProgramRequest(ulong key,ulong operation,ulong offset,ulong words,ulong source,bool masked)
        {
            return key==0x12344321 && operation==1 && offset==(0x434000-0x400000)/4 && words==1024 && source==0x20240000 && masked;
        }
        public void ObserveVerified(uint address)
        {
            if(!BootRestore)throw new ArgumentException("Page observation requires explicit full boot diagnostic");
            cpu.AddHook(address,(c,a)=>
            {
                VerificationRows.Add(new ulong[]{cpu.GetRegister(8).RawValue,cpu.GetRegister(9).RawValue,cpu.GetRegister(0).RawValue,cpu.GetRegister(5).RawValue,cpu.GetRegister(28).RawValue});
                ReadbackBytes.AddRange(machine.SystemBus.ReadBytes(0x203214a0,4096,true));
            });
        }
        private void Program()
        {
            var bus=machine.SystemBus;var key=cpu.GetRegister(0).RawValue;var op=cpu.GetRegister(1).RawValue;
            var source=cpu.GetRegister(2).RawValue;var offset=cpu.GetRegister(3).RawValue;var words=bus.ReadDoubleWord(cpu.GetRegister(13).RawValue);
            RomAttempts++;RomPrimask=(uint)cpu.GetRegister(28).RawValue;
            RomRequests.Add(new ulong[]{key,op,offset,words,source,RomPrimask});
            var valid=BootRestore
                ? key==0x12344321 && op==1 && words==1024 && RomPrimask==1 && RomCalls<39 && offset==0x4000+RomCalls*1024 && source==0x20240000+RomCalls*4096
                : ValidProgramRequest(key,op,offset,words,source,RomPrimask==1);
            if(!valid) {Violation("ROM ABI/range",offset);return;}
            if((Power.Registers[0x40021018].Value&0x80)==0){Violation("ROM without readiness",0x0200ff20);return;}
            RomCalls++;
            if(RomStatus==0)
            {
                var memory=(BlackwallProtectedMram)machine["sysbus.mram"];
                var byteOffset=offset*4;
                for(uint i=0;i<4096;i+=4){memory.ProgramDoubleWord((long)byteOffset+i,bus.ReadDoubleWord(source+i));ProgrammedBytes+=4;}
                if(CorruptReadback)memory.ProgramDoubleWord((long)byteOffset,bus.ReadDoubleWord(0x400000+byteOffset)^1u);
                cpu.OrderTranslationBlocksInvalidation(new IntPtr((long)(0x400000+byteOffset)),new IntPtr((long)(0x401000+byteOffset)));
            }
            cpu.SetRegister(0,RomStatus);cpu.PC=cpu.GetRegister(14).RawValue;
        }
        internal void Violation(string reason,ulong address){Violations++;Failure=reason;FailureAddress=address;cpu.IsHalted=true;}
        public uint ReadDoubleWord(long offset)
        {
            uint value;var address=0x40020000UL+(ulong)offset;
            if(Clock!=null && address==0x40021000)return Clock.ReadMode();
            if(Power.TryRead(address,out value))return value;
            if(Chip!=null && Chip.TryRead(address,out value))return value;
            Violation("unsupported MMIO read",address);return 0;
        }
        public void WriteDoubleWord(long offset,uint value)
        {
            var address=0x40020000UL+(ulong)offset;
            if(!Power.TryWrite(address,value))Violation("unsupported MMIO write",address);
        }
        public void Reset(){}public long Size=>0x2000;
        public uint RomStatus {get;}public bool CorruptReadback {get;}
        public bool BootRestore {get;}
        public List<ulong[]> RomRequests {get;}=new List<ulong[]>();
        public List<ulong[]> VerificationRows {get;}=new List<ulong[]>();
        public List<byte> ReadbackBytes {get;}=new List<byte>();
        public BlackwallMemoryStartup Power {get;} public BlackwallChipIdentity Chip {get;}
        public BlackwallMcuClock Clock {get;}
        public uint DelayCalls {get;private set;}public uint DelayReturns {get;private set;}
        public bool VerifierCompared {get;private set;}public uint VerifierCompare {get;private set;}
        public bool InfoReturned {get;private set;}public uint InfoReturn {get;private set;}public uint InfoMramSize {get;private set;}
        public Dictionary<uint,uint> Hits {get;}=new Dictionary<uint,uint>();
        public bool Completed {get;private set;}public bool RomUnreadyBoundary {get;private set;}
        public uint PowerReturn {get;private set;}public bool PowerReturned {get;private set;}
        public uint InitialPrimask {get;private set;}public uint InitialControl {get;private set;}
        public uint RomAttempts {get;private set;}public uint RomCalls {get;private set;}public uint ProgrammedBytes {get;private set;}public uint RomPrimask {get;private set;}
        public int Violations {get;private set;}public string Failure {get;private set;}="none";public ulong FailureAddress {get;private set;}
        private readonly IMachine machine;private readonly CortexM cpu;
    }
    public sealed class BlackwallStockMainChipIdentity : IDoubleWordPeripheral,IKnownSize
    {
        public BlackwallStockMainChipIdentity(BlackwallStockMainMramProbe owner){this.owner=owner;if(owner.Chip==null)throw new ArgumentException("Explicit existing chip profile required");}
        public uint ReadDoubleWord(long offset){uint value;var address=0xe00fefe0UL+(ulong)offset;if(owner.Chip.TryRead(address,out value))return value;owner.Violation("unsupported chip identity read",address);return 0;}
        public void WriteDoubleWord(long offset,uint value){owner.Violation("read-only chip identity write",0xe00fefe0UL+(ulong)offset);}
        public long Size=>0x20;public void Reset(){}private readonly BlackwallStockMainMramProbe owner;
    }
}
