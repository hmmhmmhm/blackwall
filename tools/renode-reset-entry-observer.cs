namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals.CPU;
    public sealed class BlackwallResetEntryObserver
    {
        public BlackwallResetEntryObserver(IMachine machine,CortexM cpu,ulong entry)
        {
            this.cpu=cpu;this.entry=entry;
            callback=(c,a)=>{Seen=true;machine.Pause();};
            cpu.AddHook(entry,callback);
        }
        public void Detach() { cpu.RemoveHook(entry,callback); }
        public bool Seen {get;private set;}
        private readonly CortexM cpu;
        private readonly ulong entry;
        private readonly CpuAddressHook callback;
    }
}
