namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using System.Collections.Generic;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals.CPU;
    public sealed class BlackwallHciEmissionObserver
    {
        public BlackwallHciEmissionObserver(IMachine machine,CortexM cpu,BlackwallEm9305EventPeer peer,uint tcbSlot)
        {
            cpu.AddHook(0x563c08,(c,a)=>{
                uint ptr=(uint)cpu.GetRegister(0).RawValue;
                if(ptr==0)return;
                if(ptr<0x20000000 || ptr>0x2037ff00){InvalidPointer=true;return;}
                if(Rows.Count>=128){Overflow=true;return;}
                var header=machine.SystemBus.ReadBytes(ptr,3,true);
                var data=machine.SystemBus.ReadBytes(ptr,3+header[2],true);
                Rows.Add(new ulong[]{machine.ElapsedVirtualTime.TimeElapsed.Ticks,ptr,(ulong)cpu.GetRegister(14).RawValue,(ulong)cpu.GetRegister(13).RawValue,machine.SystemBus.ReadDoubleWord(tcbSlot),(ulong)cpu.GetRegister(25).RawValue,(ulong)peer.ControllerGeneration});
                Packets.Add(data);
            });
        }
        public List<ulong[]> Rows {get;}=new List<ulong[]>();
        public List<byte[]> Packets {get;}=new List<byte[]>();
        public bool Overflow {get;private set;}
        public bool InvalidPointer {get;private set;}
    }
}
