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
