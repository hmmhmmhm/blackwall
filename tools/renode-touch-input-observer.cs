namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System.Collections.Generic;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals.CPU;

    public sealed class BlackwallTouchInputObserver
    {
        public BlackwallTouchInputObserver(IMachine machine,CortexM cpu,uint tcbSlot)
        { this.machine=machine;this.cpu=cpu;this.tcbSlot=tcbSlot; }

        public void Watch(uint tag,uint address)
        {
            cpu.AddHook(address,(c,a)=>{
                if(Rows.Count==128) { Overflow=true;return; }
                uint sp=(uint)cpu.GetRegister(13).RawValue;
                Rows.Add(new ulong[]{tag,a,cpu.GetRegister(0).RawValue,cpu.GetRegister(1).RawValue,
                    cpu.GetRegister(2).RawValue,cpu.GetRegister(3).RawValue,sp,
                    cpu.GetRegister(14).RawValue,machine.SystemBus.ReadDoubleWord(tcbSlot),
                    cpu.GetRegister(25).RawValue,machine.ElapsedVirtualTime.TimeElapsed.Ticks});
                if(tag==1 && sp>=0x20000000u && sp<=0x2037ffbcu)
                    Frames.Add(machine.SystemBus.ReadBytes(sp+0x34u,16,true));
            });
        }

        public List<ulong[]> Rows {get;}=new List<ulong[]>();
        public List<byte[]> Frames {get;}=new List<byte[]>();
        public bool Overflow {get;private set;}
        private readonly IMachine machine;
        private readonly CortexM cpu;
        private readonly uint tcbSlot;
    }
}
