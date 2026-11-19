namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using System.Collections.Generic;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals.CPU;
    public sealed class BlackwallPeerRecoveryObserver
    {
        public BlackwallPeerRecoveryObserver(IMachine m,CortexM cpu,uint timer,uint opcode,uint credit,uint start,uint entry,uint finish,uint healthy,uint readyReturn,uint slot,uint send,BlackwallEm9305EventPeer peer)
        {
            Func<int,uint> r=n=>(uint)cpu.GetRegister(n).RawValue;
            Func<uint[]> context=()=>new uint[]{r(0),r(13),r(14),m.SystemBus.ReadDoubleWord(slot),r(25)};
            cpu.AddHook(start,(c,a)=>{
                if(Started || r(0)!=timer || m.SystemBus.ReadWord(opcode)!=0x2006)return;
                Started=true;Seconds=r(1);StartedAt=m.ElapsedVirtualTime.TimeElapsed.Ticks;
            });
            cpu.AddHook(entry,(c,a)=>{
                if(Entered)return;Entered=true;Entry=context();EnteredAt=m.ElapsedVirtualTime.TimeElapsed.Ticks;
                if(r(0)>=0x20000000 && r(0)<=0x2037fffc)Message=m.SystemBus.ReadBytes(r(0),4,true);
            });
            cpu.AddHook(finish,(c,a)=>{
                if(!Entered || Returned)return;Returned=true;Return=context();ReturnedAt=m.ElapsedVirtualTime.TimeElapsed.Ticks;m.Pause();
            });
            cpu.AddHook(healthy,(c,a)=>{
                if(!Returned || Healthy || m.SystemBus.ReadWord(opcode)!=0x200a)return;
                Healthy=true;HealthyAt=m.ElapsedVirtualTime.TimeElapsed.Ticks;HealthyContext=context();m.Pause();
            });
            cpu.AddHook(readyReturn,(c,a)=>{
                if(!Healthy || CreditReturned || m.SystemBus.ReadWord(opcode)!=0x200a)return;
                CreditReturned=true;CreditAt=m.ElapsedVirtualTime.TimeElapsed.Ticks;CreditContext=context();m.Pause();
            });
            cpu.AddHook(send,(c,a)=>{
                uint ptr=r(0);if(ptr==0)return;
                if(ptr<0x20000000 || ptr>0x2037fffd){InvalidPointer=true;return;}
                var header=m.SystemBus.ReadBytes(ptr,3,true);int size=3+header[2];
                if((ulong)ptr+(ulong)size>0x20380000){InvalidPointer=true;return;}
                if(Packets.Count>=128){Overflow=true;return;}
                Packets.Add(m.SystemBus.ReadBytes(ptr,size,true));PacketGenerations.Add(peer.ControllerGeneration);
            });
        }
        public void WatchCall(CortexM cpu,uint address)
        {
            cpu.AddHook(address,(c,a)=>{
                if(!Entered || Returned)return;
                if(Calls.Count>=32){Overflow=true;return;}
                Calls.Add(new uint[]{address,(uint)cpu.GetRegister(0).RawValue,(uint)cpu.GetRegister(1).RawValue,(uint)cpu.GetRegister(2).RawValue,(uint)cpu.GetRegister(3).RawValue});
            });
        }
        public bool Started {get;private set;}
        public uint Seconds {get;private set;}
        public ulong StartedAt {get;private set;}
        public bool Entered {get;private set;}
        public ulong EnteredAt {get;private set;}
        public uint[] Entry {get;private set;}=new uint[0];
        public byte[] Message {get;private set;}=new byte[0];
        public bool Returned {get;private set;}
        public ulong ReturnedAt {get;private set;}
        public uint[] Return {get;private set;}=new uint[0];
        public bool Healthy {get;private set;}
        public ulong HealthyAt {get;private set;}
        public uint[] HealthyContext {get;private set;}=new uint[0];
        public bool CreditReturned {get;private set;}
        public ulong CreditAt {get;private set;}
        public uint[] CreditContext {get;private set;}=new uint[0];
        public List<uint[]> Calls {get;}=new List<uint[]>();
        public List<byte[]> Packets {get;}=new List<byte[]>();
        public List<int> PacketGenerations {get;}=new List<int>();
        public bool InvalidPointer {get;private set;}
        public bool Overflow {get;private set;}
    }
}
