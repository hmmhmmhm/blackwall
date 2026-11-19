namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals.Timers;
    // Digital engine with declared nominal input clocks and immediate relative compare writes.
    public sealed class BlackwallStimerClockCounter : IBlackwallStimer
    {
        public BlackwallStimerClockCounter(IMachine machine,string profile)
        {
            if(profile!="nominal-source-clocks")throw new ArgumentException("Explicit nominal STIMER clock profile required");
            engine=new BlackwallStimerEngine(machine);Reset();
        }
        public bool Owns(ulong a)=>a==0x40008800 || a==0x40008804 || (a>=0x40008820 && a<=0x4000883c && (a&3)==0) || a==0x40008900 || a==0x40008904 || a==0x40008908 || a==0x4000890c;
        public bool TryRead(ulong address,out uint value)
        {
            value=0;
            if(!Owns(address) || address==0x40008908 || address==0x4000890c)return false;
            value=engine.ReadDoubleWord((long)(address-0x40008800));Reads++;return true;
        }
        public bool TryWrite(ulong address,uint value)
        {
            if(!Owns(address))return false;
            if(address==0x40008800)
            {
                if((value&~0xc000ff0fu)!=0 || (value&15)>6)return false;
                engine.WriteDoubleWord(0,value);
            }
            else if(address==0x40008804)
            {
                if((Config&0x80000000u)==0 || (Config&0x40000000u)!=0)return false;
                engine.LoadCounter(value);
            }
            else if(address>=0x40008900)
            {
                if((value&~0x1fffu)!=0 || (address==0x40008904 && value!=0))return false;
                engine.WriteDoubleWord(address==0x40008904 ? 0x108 : (long)(address-0x40008800),address==0x40008904 ? 0x1fffu : value);
            }
            else engine.WriteDoubleWord((long)(address-0x40008800),value);
            Writes++;return true;
        }
        public void Reset() {engine.Reset();Reads=Writes=0;}
        public uint Config=>engine.ReadDoubleWord(0);
        public uint Counter=>engine.Value;
        public ulong Frequency=>(Config&15)==0 ? 0 : engine.Frequency;
        public uint Enable=>engine.ReadDoubleWord(0x100);
        public uint Status=>engine.ReadDoubleWord(0x104);
        public bool Pending=>(Enable&Status)!=0;
        public int Reads {get;private set;}public int Writes {get;private set;}
        public GPIO IRQA=>engine.IRQA;public GPIO IRQB=>engine.IRQB;public GPIO IRQC=>engine.IRQC;
        public GPIO IRQD=>engine.IRQD;public GPIO IRQE=>engine.IRQE;public GPIO IRQF=>engine.IRQF;
        public GPIO IRQG=>engine.IRQG;public GPIO IRQH=>engine.IRQH;public GPIO IRQI=>engine.IRQI;
        private readonly BlackwallStimerEngine engine;
    }
}
