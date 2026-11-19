namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using System.Collections.Generic;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals.CPU;
    using Antmicro.Renode.Peripherals.Bus;
    public sealed class BlackwallHciTimeoutObserver
    {
        public BlackwallHciTimeoutObserver(IMachine machine,CortexM cpu,uint timer,uint start,uint entry,uint finish,uint tcbSlot)
        {
            Func<int,uint> reg=n=>(uint)cpu.GetRegister(n).RawValue;
            Func<ulong> now=()=>machine.ElapsedVirtualTime.TimeElapsed.Ticks;
            cpu.AddHook(start,(c,a)=>{
                if(reg(0)!=timer || machine.SystemBus.ReadWord(timer+0x20)!=0x2006)return;
                Starts++;StartSeconds=reg(1);StartTicks=now();
            });
            cpu.AddHook(entry,(c,a)=>{
                if(Entered)return;
                Entry=new uint[]{reg(0),reg(13),reg(14),machine.SystemBus.ReadDoubleWord(tcbSlot),reg(25)};
                if(reg(0)>=0x20000000 && reg(0)<=0x20380000-4)EntryMessage=machine.SystemBus.ReadBytes(reg(0),4,true);
                EntryTicks=now();Entered=true;
            });
            cpu.AddHook(finish,(c,a)=>{
                if(!Entered || Returned)return;
                Exit=new uint[]{reg(13),machine.SystemBus.ReadDoubleWord(tcbSlot),reg(25)};
                ReturnTicks=now();Returned=true;machine.Pause();
            });
        }
        public void WatchCall(CortexM cpu,uint address)
        {
            cpu.AddHook(address,(c,a)=>{
                if(!Entered)return;
                if(Calls.Count>=32){Overflow=true;return;}
                Calls.Add(new uint[]{address,(uint)cpu.GetRegister(0).RawValue,(uint)cpu.GetRegister(1).RawValue,(uint)cpu.GetRegister(2).RawValue,(uint)cpu.GetRegister(3).RawValue});
            });
        }
        public void WatchHealthyStop(IMachine machine,CortexM cpu,uint address,uint timer)
        {
            cpu.AddHook(address,(c,a)=>{
                if(machine.SystemBus.ReadWord(timer+0x20)!=0x200a || HealthyStop)return;
                HealthyStop=true;HealthyStopTicks=machine.ElapsedVirtualTime.TimeElapsed.Ticks;
                HealthyTimer=machine.SystemBus.ReadBytes(timer,16,true);machine.Pause();
            });
        }
        public int Starts {get;private set;}
        public uint StartSeconds {get;private set;}
        public ulong StartTicks {get;private set;}
        public bool Entered {get;private set;}
        public ulong EntryTicks {get;private set;}
        public uint[] Entry {get;private set;}=new uint[0];
        public byte[] EntryMessage {get;private set;}=new byte[0];
        public bool Returned {get;private set;}
        public ulong ReturnTicks {get;private set;}
        public uint[] Exit {get;private set;}=new uint[0];
        public List<uint[]> Calls {get;}=new List<uint[]>();
        public bool Overflow {get;private set;}
        public bool HealthyStop {get;private set;}
        public ulong HealthyStopTicks {get;private set;}
        public byte[] HealthyTimer {get;private set;}=new byte[0];
    }
}
