namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using System.Collections.Generic;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals.CPU;

    // Read-only, bounded software-call diagnostics; never returns data to the guest.
    public sealed class BlackwallPhaseStackObserver
    {
        public BlackwallPhaseStackObserver(IMachine machine,CortexM cpu,uint openPc,uint closePc,uint samplePc,int budget=4,uint indirectWordPointerAddress=0,uint directAddress=0,int directWords=0)
        {
            if(machine==null || cpu==null || budget<1 || budget>8 || !CodePc(openPc) || !CodePc(closePc)
                || !CodePc(samplePc) || openPc==closePc || openPc==samplePc || closePc==samplePc)
                throw new ArgumentException("Phase observation requires bounded distinct original PCs and sample budget");
            if(indirectWordPointerAddress!=0 && !Sram(indirectWordPointerAddress,4))throw new ArgumentException("Indirect snapshot requires a bounded SRAM pointer slot");
            if(directWords<0 || directWords>16 || (directWords==0)!=(directAddress==0) || (directWords>0 && !Sram(directAddress,4u*(uint)directWords)))throw new ArgumentException("Direct snapshot requires bounded SRAM words");
            this.machine=machine;this.cpu=cpu;Budget=budget;
            this.indirectWordPointerAddress=indirectWordPointerAddress;
            this.directAddress=directAddress;this.directWords=directWords;
            usedPcs.Add(openPc);usedPcs.Add(closePc);usedPcs.Add(samplePc);
            cpu.AddHook(openPc,(c,a) => { OpenHits++;Active=true;if(Open==null)Open=Capture(openPc); });
            cpu.AddHook(closePc,(c,a) => { if(Active){CloseHits++;Active=false;if(Close==null)Close=Capture(closePc);} });
            cpu.AddHook(samplePc,(c,a) => {
                if(!Active)return;
                SampleHits++;
                if(samples.Count<Budget){var sample=Capture(samplePc);if(sample!=null)samples.Add(sample);}
            });
        }
        public void AddWatch(string label,uint pc)
        {
            if(string.IsNullOrEmpty(label) || !CodePc(pc) || watches.Count>=8 || usedPcs.Contains(pc) || watches.Exists(x=>x.Label==label))
                throw new ArgumentException("Watch requires a unique bounded source PC and label");
            var watch=new BlackwallPhaseWatch(label,pc);watches.Add(watch);usedPcs.Add(pc);
            cpu.AddHook(pc,(c,a) => {
                watch.TotalHits++;if(watch.FirstAny==null)watch.FirstAny=Capture(pc);
                if(!Active)return;
                watch.Hits++;if(watch.Samples.Count<Budget){var sample=Capture(pc);if(sample!=null)watch.Samples.Add(sample);}
            });
        }
        private static bool CodePc(uint pc) => (pc&1)==0 && pc>=0x438000 && pc<0x800000;
        private static bool Sram(uint address,uint bytes) => (address&3)==0 && address>=0x20000000 && (ulong)address+bytes<=0x20380000;
        private BlackwallPhaseStackSample Capture(uint pc)
        {
            var sp=(uint)cpu.GetRegister(13).RawValue;
            if((sp&3)!=0 || sp<0x20000000 || (ulong)sp+768>0x20380000){RejectedSnapshots++;return null;}
            var stack=new uint[192];for(var i=0;i<192;i++)stack[i]=machine.SystemBus.ReadDoubleWord(sp+4u*(uint)i);
            var args=new uint[8];for(var i=0;i<8;i++)args[i]=(uint)cpu.GetRegister(i).RawValue;
            var pointer=indirectWordPointerAddress==0 ? 0u:machine.SystemBus.ReadDoubleWord(indirectWordPointerAddress);
            var valid=indirectWordPointerAddress!=0 && Sram(pointer,4);
            var word=valid ? machine.SystemBus.ReadDoubleWord(pointer):0u;
            var direct=new uint[directWords];for(var i=0;i<directWords;i++)direct[i]=machine.SystemBus.ReadDoubleWord(directAddress+4u*(uint)i);
            return new BlackwallPhaseStackSample(pc,sp,(uint)cpu.GetRegister(14).RawValue,
                machine.SystemBus.ReadDoubleWord(0xe000ed04)&0x1ffu,pointer,word,valid,direct,args,stack);
        }
        public int Budget { get; }
        public ulong OpenHits { get; private set; }
        public ulong CloseHits { get; private set; }
        public ulong SampleHits { get; private set; }
        public ulong RejectedSnapshots { get; private set; }
        public bool Active { get; private set; }
        public BlackwallPhaseStackSample Open { get; private set; }
        public BlackwallPhaseStackSample Close { get; private set; }
        public IEnumerable<BlackwallPhaseStackSample> Samples => samples;
        public IEnumerable<BlackwallPhaseWatch> Watches => watches;
        private readonly IMachine machine;
        private readonly CortexM cpu;
        private readonly List<BlackwallPhaseStackSample> samples=new List<BlackwallPhaseStackSample>();
        private readonly List<BlackwallPhaseWatch> watches=new List<BlackwallPhaseWatch>();
        private readonly HashSet<uint> usedPcs=new HashSet<uint>();
        private readonly uint indirectWordPointerAddress;
        private readonly uint directAddress;
        private readonly int directWords;
    }
    public sealed class BlackwallPhaseStackSample
    {
        public BlackwallPhaseStackSample(uint pc,uint sp,uint lr,uint activeVector,uint indirectPointer,uint indirectWord,bool indirectValid,uint[] direct,uint[] registers,uint[] stack)
        { PC=pc;SP=sp;LR=lr;ActiveVector=activeVector;IndirectPointer=indirectPointer;IndirectWord=indirectWord;IndirectValid=indirectValid;Direct=direct;Registers=registers;Stack=stack; }
        public uint PC { get; }
        public uint SP { get; }
        public uint LR { get; }
        public uint ActiveVector { get; }
        public uint[] Direct { get; }
        public uint IndirectPointer { get; }
        public uint IndirectWord { get; }
        public bool IndirectValid { get; }
        public uint[] Registers { get; }
        public uint[] Stack { get; }
    }
    public sealed class BlackwallPhaseWatch
    {
        public BlackwallPhaseWatch(string label,uint pc) { Label=label;PC=pc; }
        public string Label { get; }
        public uint PC { get; }
        public ulong TotalHits { get; internal set; }
        public ulong Hits { get; internal set; }
        public BlackwallPhaseStackSample FirstAny { get; internal set; }
        public List<BlackwallPhaseStackSample> Samples { get; }=new List<BlackwallPhaseStackSample>();
    }
}
