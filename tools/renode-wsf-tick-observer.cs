namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using System.Collections.Generic;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals.CPU;
    public sealed class BlackwallWsfTickObserver
    {
        public BlackwallWsfTickObserver(IMachine machine,CortexM cpu,uint timer,uint start,uint update,uint returned,uint osTick,uint previousTick)
        {
            Func<uint,uint> word=a=>machine.SystemBus.ReadDoubleWord(a);
            Func<ulong> now=()=>machine.ElapsedVirtualTime.TimeElapsed.Ticks;
            cpu.AddHook(start,(c,a)=>{
                if((uint)cpu.GetRegister(0).RawValue!=timer || machine.SystemBus.ReadWord(timer+0x20)!=0x2006)return;
                Start=new ulong[]{now(),word(osTick),word(previousTick),word(timer+4),machine.SystemBus.ReadByte(timer+13),cpu.GetRegister(1).RawValue};
            });
            cpu.AddHook(update,(c,a)=>{
                if(Rows.Count>=2048){Overflow=true;pending=null;return;}
                pending=new ulong[]{now(),word(osTick),word(previousTick),cpu.GetRegister(0).RawValue,word(timer+4),machine.SystemBus.ReadByte(timer+13),0,0,0};
                Rows.Add(pending);
            });
            cpu.AddHook(returned,(c,a)=>{
                if(pending==null)return;
                pending[6]=now();pending[7]=word(timer+4);pending[8]=machine.SystemBus.ReadByte(timer+13);pending=null;
            });
        }
        public ulong[] Start {get;private set;}=new ulong[0];
        public List<ulong[]> Rows {get;}=new List<ulong[]>();
        public bool Overflow {get;private set;}
        private ulong[] pending;
    }
}
