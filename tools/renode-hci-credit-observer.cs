namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals.CPU;
    public sealed class BlackwallHciCreditObserver
    {
        public BlackwallHciCreditObserver(IMachine machine,CortexM cpu,uint timer,uint tcbSlot)
        {
            Before=machine.SystemBus.ReadByte(timer+0x22);Started=machine.ElapsedVirtualTime.TimeElapsed.Ticks;
            cpu.AddHook(0x563d3e,(c,a)=>{
                if(Stopped || machine.SystemBus.ReadWord(timer+0x20)!=0x200a)return;
                After=machine.SystemBus.ReadByte(timer+0x22);Timer=machine.SystemBus.ReadBytes(timer,16,true);
                Context=new uint[]{(uint)cpu.GetRegister(13).RawValue,(uint)cpu.GetRegister(14).RawValue,machine.SystemBus.ReadDoubleWord(tcbSlot),(uint)cpu.GetRegister(25).RawValue};
                Finished=machine.ElapsedVirtualTime.TimeElapsed.Ticks;Stopped=true;machine.Pause();
            });
        }
        public byte Before {get;}
        public byte After {get;private set;}
        public ulong Started {get;}
        public ulong Finished {get;private set;}
        public bool Stopped {get;private set;}
        public uint[] Context {get;private set;}=new uint[0];
        public byte[] Timer {get;private set;}=new byte[0];
    }
}
