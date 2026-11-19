namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals.CPU;

    public sealed class BlackwallCompleteScreenObserver
    {
        public BlackwallCompleteScreenObserver(IMachine machine,CortexM cpu,uint afterStore,Func<bool> complete)
        {
            if(machine==null || cpu==null || complete==null || (afterStore&1)!=0)
                throw new ArgumentException("A verified original post-store PC and frame predicate are required");
            cpu.AddHook(afterStore,(c,a)=>{
                Checks++;
                if(Stopped || !complete())return;
                Stopped=true;PC=(uint)a;machine.Pause();
            });
        }
        public bool Stopped {get;private set;}
        public uint PC {get;private set;}
        public uint Checks {get;private set;}
    }
}
