namespace Antmicro.Renode.Peripherals.Miscellaneous {
    using System; using System.Collections.Generic; using Antmicro.Renode.Core; using Antmicro.Renode.Peripherals.CPU;
    public sealed class BlackwallUiActivationHold {
    public BlackwallUiActivationHold(IMachine machine,CortexM cpu,uint pc) { cpu.AddHook(pc,(c,a)=>{if(!Held){Held=true;machine.Pause();}}); }
    public bool Held {get;private set;}
    }
    public sealed class BlackwallUiActivationDiagnostic {
    public BlackwallUiActivationDiagnostic(IMachine machine,CortexM cpu,uint stop) { this.cpu=cpu; cpu.AddHook(stop,(c,a)=>{if(!Stopped){Events.Add((uint)a);Stopped=true;machine.Pause();}}); }
    public void Seed(int index,uint value) { if(index!=0 && index!=1 && index!=2 && index!=14 && index!=15)throw new ArgumentException("Unreviewed seed");if(index==15)cpu.PC=value;else cpu.SetRegister(index,value); }
    public void AddStop(uint pc,IMachine machine) { cpu.AddHook(pc,(c,a)=>{if(!Stopped){Events.Add((uint)a);Stopped=true;machine.Pause();}}); }
    public void Watch(uint pc) { cpu.AddHook(pc,(c,a)=>{if(Events.Count<64)Events.Add((uint)a);}); }
    public bool Stopped {get;private set;} public List<uint> Events {get;}=new List<uint>(); private readonly CortexM cpu;
    }}
    
namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals.CPU;
    public sealed class BlackwallRuntimeConnectionObserver
    {
        public BlackwallRuntimeConnectionObserver(IMachine machine,CortexM cpu,uint isr,uint opened,uint finished,uint slot)
        {
            Func<int,uint> r=n=>(uint)cpu.GetRegister(n).RawValue;
            cpu.AddHook(isr,(c,a)=>IrqEntries++);
            cpu.AddHook(opened,(c,a)=>{OpenCalls++;if(OpenCalls==1)Entry=new uint[]{r(0),r(1),r(13),r(14),machine.SystemBus.ReadDoubleWord(slot),r(25)};});
            cpu.AddHook(finished,(c,a)=>{if(OpenCalls==1 && !Stopped){Exit=new uint[]{r(13),machine.SystemBus.ReadDoubleWord(slot),r(25)};Stopped=true;machine.Pause();}});
        }
        public bool Stopped {get;private set;}
        public uint IrqEntries {get;private set;}
        public uint OpenCalls {get;private set;}
        public uint[] Entry {get;private set;}=new uint[0];
        public uint[] Exit {get;private set;}=new uint[0];
    }
}
namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Time;
    using Antmicro.Renode.Peripherals.Timers;
    public sealed class BlackwallRuntimeInputDelay : Antmicro.Renode.Peripherals.IPeripheral
    {
        public BlackwallRuntimeInputDelay(IMachine machine,uint milliseconds,Func<bool> enqueue)
        {
            if(milliseconds==0 || milliseconds>1000 || enqueue==null)throw new ArgumentException("Explicit 1..1000ms virtual input delay and enqueue callback required");
            StartedAt=machine.ElapsedVirtualTime.TimeElapsed.Ticks;
            timer=new LimitTimer(machine.ClockSource,1000000,this,"runtime-peer-input",milliseconds*1000u,Direction.Ascending,enabled:false,workMode:WorkMode.OneShot,eventEnabled:true);
            timer.LimitReached+=()=>{Fired=true;FiredAt=machine.ElapsedVirtualTime.TimeElapsed.Ticks;Accepted=enqueue();};
            timer.Enabled=true;
        }
        public void Reset(){timer.Enabled=false;Fired=Accepted=false;FiredAt=0;}
        public bool Fired {get;private set;}
        public bool Accepted {get;private set;}
        public ulong StartedAt {get;private set;}
        public ulong FiredAt {get;private set;}
        private readonly LimitTimer timer;
    }
}

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
