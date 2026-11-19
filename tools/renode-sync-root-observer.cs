namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using System.Collections.Generic;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals.CPU;
    public sealed class BlackwallSyncRootObserver
    {
        public BlackwallSyncRootObserver(IMachine machine,CortexM cpu,uint input,uint producer,uint start,uint finishReturn,uint tcbSlot)
        {
            var bus=machine.SystemBus;
            Func<int,uint> reg=n=>(uint)cpu.GetRegister(n).RawValue;
            cpu.AddHook(input,(c,a)=>{if(Inputs.Count<8)Inputs.Add(new uint[]{reg(0),reg(1),reg(2),reg(13),bus.ReadDoubleWord(tcbSlot),reg(25)});});
            cpu.AddHook(producer,(c,a)=>{if(Producers.Count<8)Producers.Add(new uint[]{reg(0),reg(1),reg(2),reg(3),reg(13),bus.ReadDoubleWord(tcbSlot),reg(25)});});
            cpu.AddHook(start,(c,a)=>{
                RequestsSeen++;
                var descriptor=reg(1);
                if(!InRam(descriptor,24))return;
                var node=bus.ReadDoubleWord(descriptor+16);
                if(!InRam(node,12))return;
                var packet=bus.ReadDoubleWord(node+8);
                if(!InRam(packet,12) || bus.ReadWord(packet)!=0x901 || bus.ReadWord(packet+2)!=11 || bus.ReadWord(packet+6)!=4 || bus.ReadDoubleWord(packet+8)!=0x04030201)return;
                Matches++;Descriptor=descriptor;Node=node;Packet=packet;
                Context=new uint[]{reg(0),reg(1),reg(2),reg(3),reg(13),bus.ReadDoubleWord(tcbSlot),reg(25)};
            });
            cpu.AddHook(finishReturn,(c,a)=>{if(Matches==1 && !Stopped){DescriptorBytes=bus.ReadBytes(Descriptor,24);PacketBytes=bus.ReadBytes(Packet,12);FinishContext=new uint[]{reg(13),bus.ReadDoubleWord(tcbSlot),reg(25)};Stopped=true;machine.Pause();}});
        }
        private static bool InRam(uint address,uint count)=>address>=0x20000000 && address<=0x20380000-count;
        public bool Stopped {get;private set;}
        public uint RequestsSeen {get;private set;}
        public uint Matches {get;private set;}
        public uint Descriptor {get;private set;}
        public uint Node {get;private set;}
        public uint Packet {get;private set;}
        public byte[] DescriptorBytes {get;private set;}=new byte[0];
        public byte[] PacketBytes {get;private set;}=new byte[0];
        public uint[] FinishContext {get;private set;}=new uint[0];
        public uint[] Context {get;private set;}=new uint[0];
        public List<uint[]> Inputs {get;}=new List<uint[]>();
        public List<uint[]> Producers {get;}=new List<uint[]>();
    }
}
