namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals.CPU;
    public sealed class BlackwallWakeRequestObserver
    {
        public BlackwallWakeRequestObserver(IMachine machine,CortexM cpu,uint start,uint finish,uint slot)
        {
            var b=machine.SystemBus;Func<int,uint> r=n=>(uint)cpu.GetRegister(n).RawValue;
            cpu.AddHook(start,(c,a)=>{
                var d=r(1);if(!InRam(d,24))return;var n=b.ReadDoubleWord(d+16);if(!InRam(n,12))return;var p=b.ReadDoubleWord(n+8);
                if(!InRam(p,8) || b.ReadWord(p)!=0x102 || b.ReadWord(p+2)!=1 || b.ReadWord(p+6)!=0)return;
                Matches++;Descriptor=d;Packet=p;Context=new uint[]{r(0),r(1),r(2),r(3),r(13),b.ReadDoubleWord(slot),r(25)};
            });
            cpu.AddHook(finish,(c,a)=>{
                if(Matches!=1 || Stopped)return;
                DescriptorBytes=b.ReadBytes(Descriptor,24,true);PacketBytes=b.ReadBytes(Packet,8,true);Exit=new uint[]{r(13),b.ReadDoubleWord(slot),r(25)};Stopped=true;machine.Pause();
            });
        }
        private static bool InRam(uint a,uint n)=>a>=0x20000000 && a<=0x20380000-n;
        public uint Matches {get;private set;}
        public uint Descriptor {get;private set;}
        public uint Packet {get;private set;}
        public uint[] Context {get;private set;}=new uint[0];
        public uint[] Exit {get;private set;}=new uint[0];
        public byte[] DescriptorBytes {get;private set;}=new byte[0];
        public byte[] PacketBytes {get;private set;}=new byte[0];
        public bool Stopped {get;private set;}
    }
}
namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System.Collections.Generic;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals.CPU;
    public sealed class BlackwallWakeRxObserver
    {
        public BlackwallWakeRxObserver(IMachine m,CortexM cpu,BlackwallUartAdapter uart,uint slot)
        {
            if(uart.IrqHandlerAddress==0)throw new System.ArgumentException("UART IRQ attachment required");
            cpu.AddHook(uart.IrqHandlerAddress,(c,a)=>{
                if(Rows.Count==16){Overflow=true;return;}
                Rows.Add(new ulong[]{uart.RawInterrupts,uart.MaskedInterrupts,(ulong)uart.RxPending,uart.RxTimeoutPending?1ul:0ul,uart.RxTimeoutEvents,cpu.GetRegister(13).RawValue,m.SystemBus.ReadDoubleWord(slot),cpu.GetRegister(25).RawValue,m.ElapsedVirtualTime.TimeElapsed.Ticks});
            });
        }
        public List<ulong[]> Rows {get;}=new List<ulong[]>();
        public bool Overflow {get;private set;}
    }
}
