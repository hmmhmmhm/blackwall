namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using System.Collections.Generic;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals.CPU;
    using Antmicro.Renode.Peripherals.IRQControllers;

    public sealed class BlackwallSustainedObserver
    {
        public BlackwallSustainedObserver(IMachine machine, CortexM cpu, NVIC nvic)
        {
            this.nvic = nvic;
            Action<int, bool> record = (kind, level) => {
                Counts[kind]++;
                if(kind < 2)
                {
                    if(level) Entered[kind]++;
                    else Exited[kind]++;
                }
                var row = new ulong[] {(ulong)kind, level ? 1UL : 0UL,
                    machine.ElapsedVirtualTime.TimeElapsed.Ticks, cpu.PC.RawValue};
                if(Samples.Count < 128) Samples.Add(row);
                else Truncated = true;
            };
            deep = level => record(0, level);
            sleep = level => record(1, level);
            irq = level => record(2, level);
            nvic.InDeepSleep.AddStateChangedHook(deep);
            nvic.InSleep.AddStateChangedHook(sleep);
            nvic.IRQ.AddStateChangedHook(irq);
        }

        public void Detach()
        {
            nvic.InDeepSleep.RemoveStateChangedHook(deep);
            nvic.InSleep.RemoveStateChangedHook(sleep);
            nvic.IRQ.RemoveStateChangedHook(irq);
        }

        public ulong[] Counts { get; } = new ulong[3];
        public ulong[] Entered { get; } = new ulong[2];
        public ulong[] Exited { get; } = new ulong[2];
        public List<ulong[]> Samples { get; } = new List<ulong[]>();
        public bool Truncated { get; private set; }
        private readonly NVIC nvic;
        private readonly Action<bool> deep, sleep, irq;
    }
}
