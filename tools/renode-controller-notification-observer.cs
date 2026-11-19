namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using System.Collections.Generic;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals.CPU;
    public sealed class BlackwallControllerNotificationObserver
    {
        public BlackwallControllerNotificationObserver(IMachine machine,CortexM cpu,uint tcbSlot)
        {
            Func<int,uint> r=n=>(uint)cpu.GetRegister(n).RawValue;
            Action<int,uint> record=(stage,ptr)=>{
                if(Rows.Count>=32){Overflow=true;return;}
                uint word=ptr>=0x20000000 && ptr<=0x2037fffc?machine.SystemBus.ReadDoubleWord(ptr):0;
                Rows.Add(new ulong[]{(ulong)stage,machine.ElapsedVirtualTime.TimeElapsed.Ticks,r(15),r(0),r(1),r(2),r(13),r(14),machine.SystemBus.ReadDoubleWord(tcbSlot),r(25),ptr,word});
            };
            cpu.AddHook(0x4dab72,(c,a)=>{if(Sent)return;Message=r(0);record(1,Message);});
            cpu.AddHook(0x4dab7e,(c,a)=>{if(r(0)!=1 || r(1)!=Message || Message==0)return;Sent=true;record(2,Message);});
            cpu.AddHook(0x5647e2,(c,a)=>{if(!Sent || CallbackReturned)return;CallbackReturned=true;record(3,Message);});
            cpu.AddHook(0x4fa0f0,(c,a)=>{if(!Sent || r(1)!=Message || HandlerEntered)return;HandlerEntered=true;record(4,Message);});
            cpu.AddHook(0x4fa10c,(c,a)=>{if(!HandlerEntered || r(0)!=Message || Dispatched)return;Dispatched=true;record(5,Message);});
            cpu.AddHook(0x4da9a6,(c,a)=>{if(!Dispatched || r(0)!=Message || LeafEntered)return;LeafEntered=true;record(6,Message);});
            cpu.AddHook(0x4fa110,(c,a)=>{if(!HandlerEntered || HandlerReturnInstruction)return;HandlerReturnInstruction=true;record(7,Message);});
            cpu.AddHook(0x4d7aec,(c,a)=>{if(!HandlerReturnInstruction || r(6)!=Message || HandlerReturned)return;HandlerReturned=true;record(8,Message);});
            cpu.AddHook(0x4d7af2,(c,a)=>{if(!HandlerReturned || r(6)!=Message || MessageFreed)return;MessageFreed=true;record(9,Message);});
        }
        public List<ulong[]> Rows {get;}=new List<ulong[]>();
        public uint Message {get;private set;}
        public bool Sent {get;private set;}
        public bool CallbackReturned {get;private set;}
        public bool HandlerEntered {get;private set;}
        public bool Dispatched {get;private set;}
        public bool LeafEntered {get;private set;}
        public bool HandlerReturnInstruction {get;private set;}
        public bool HandlerReturned {get;private set;}
        public bool MessageFreed {get;private set;}
        public bool Overflow {get;private set;}
    }
}
