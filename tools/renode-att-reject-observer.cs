namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals.CPU;
    public sealed class BlackwallAttRejectObserver
    {
        public BlackwallAttRejectObserver(IMachine machine,CortexM cpu,uint entry,uint returned,uint slot)
        {
            Func<int,uint> r=n=>(uint)cpu.GetRegister(n).RawValue;
            cpu.AddHook(entry,(c,a)=>Calls++);
            cpu.AddHook(returned,(c,a)=>{if(Calls==1 && !Stopped){Verdict=new uint[]{r(6),r(7),r(10),r(13),machine.SystemBus.ReadDoubleWord(slot),r(25)};Stopped=true;machine.Pause();}});
        }
        public bool Stopped {get;private set;}
        public uint Calls {get;private set;}
        public uint[] Verdict {get;private set;}=new uint[0];
    }
}
