namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using System.Collections.Generic;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals.CPU;
    using Antmicro.Renode.Peripherals.IRQControllers;
    public sealed class BlackwallSleepTransitionObserver
    {
        public BlackwallSleepTransitionObserver(IMachine machine,CortexM cpu,NVIC nvic,uint timerIsr=0)
        {
            this.nvic=nvic;this.cpu=cpu;TimerIsr=timerIsr;InitialMaskedInterruptPresent=nvic.MaskedInterruptPresent;InitialIrq=nvic.IRQ.IsSet;
            Action<ulong,bool> save=(kind,level)=>{
                if(Events.Count>=128) { Overflow=true;return; }
                Events.Add(new ulong[]{kind,level?1UL:0UL,machine.ElapsedVirtualTime.TimeElapsed.Ticks,cpu.PC.RawValue,cpu.GetRegister(25).RawValue,nvic.IRQ.IsSet?1UL:0UL});
            };
            deep=level=>save(0,level);sleep=level=>save(1,level);irq=level=>save(2,level);
            if(timerIsr!=0) { if((timerIsr&1)!=0 || timerIsr<0x438000 || timerIsr>=0x800000)throw new ArgumentException("Pinned timer ISR required");timerHook=(c,a)=>save(3,true);cpu.AddHook(timerIsr,timerHook); }
            nvic.InDeepSleep.AddStateChangedHook(deep);nvic.InSleep.AddStateChangedHook(sleep);nvic.IRQ.AddStateChangedHook(irq);
        }
        public void Detach()
        {
            if(timerHook!=null)cpu.RemoveHook(TimerIsr,timerHook);
            nvic.InDeepSleep.RemoveStateChangedHook(deep);nvic.InSleep.RemoveStateChangedHook(sleep);nvic.IRQ.RemoveStateChangedHook(irq);
        }
        public bool InitialMaskedInterruptPresent {get;}
        public bool InitialIrq {get;}
        public uint TimerIsr {get;}
        private readonly CortexM cpu;
        private readonly CpuAddressHook timerHook;
        public List<ulong[]> Events {get;}=new List<ulong[]>();
        public bool Overflow {get;private set;}
        private readonly NVIC nvic;
        private readonly Action<bool> deep,sleep,irq;
    }
}
