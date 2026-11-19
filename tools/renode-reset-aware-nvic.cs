namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using System.Linq;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals;
    using Antmicro.Renode.Peripherals.CPU;
    using Antmicro.Renode.Peripherals.IRQControllers;

    public sealed class BlackwallResetAwareNVIC : NVIC, IPeripheral
    {
        public BlackwallResetAwareNVIC(IMachine machine,ulong systickFrequency=50*0x800000,byte priorityMask=0xff,bool haltSystickOnDeepSleep=true)
            : base(machine,systickFrequency,priorityMask,haltSystickOnDeepSleep)
        {
            this.machine=machine;
        }
        public new void Reset()
        {
            if(machine.SystemBus.GetCPUs().OfType<CortexM>().Any(cpu=>cpu.TrustZoneEnabled))
                throw new InvalidOperationException("Reset-aware NVIC currently requires the declared non-secure Cortex-M profile");
            base.Reset();
            BASEPRI_NS=0;
            ResetCompletions++;
        }
        public uint ResetCompletions {get;private set;}
        private readonly IMachine machine;
    }
}
