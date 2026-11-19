namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using System.Collections.Generic;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals.CPU;
    public sealed class BlackwallTplServiceObserver
    {
        public BlackwallTplServiceObserver(IMachine machine,CortexM cpu,uint ingress,uint consumer,uint applied,uint returned,uint slot)
        {
            Func<int,uint> reg=n=>(uint)cpu.GetRegister(n).RawValue;
            Action<List<uint[]>> save=rows=>{if(rows.Count<8)rows.Add(new uint[]{reg(0),reg(1),reg(2),reg(13),reg(14),machine.SystemBus.ReadDoubleWord(slot),reg(25)});};
            cpu.AddHook(ingress,(c,a)=>save(Inputs));
            cpu.AddHook(consumer,(c,a)=>save(Consumers));
            cpu.AddHook(applied,(c,a)=>save(Applied));
            cpu.AddHook(returned,(c,a)=>{if(Applied.Count==1 && !Stopped){save(Returns);Stopped=true;machine.Pause();}});
        }
        public bool Stopped {get;private set;}
        public List<uint[]> Inputs {get;}=new List<uint[]>();
        public List<uint[]> Consumers {get;}=new List<uint[]>();
        public List<uint[]> Applied {get;}=new List<uint[]>();
        public List<uint[]> Returns {get;}=new List<uint[]>();
    }
}
