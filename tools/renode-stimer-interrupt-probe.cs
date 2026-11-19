namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    // Interrupt register subset only. No counter/capture events or NVIC delivery.
    public sealed class BlackwallStimerInterruptStorage : IBlackwallStimer
    {
        public BlackwallStimerInterruptStorage(string profile)
        {
            if(profile!="source-reset-storage")throw new System.ArgumentException("Explicit STIMER interrupt storage required");
            Reset();
        }
        public void Reset() {Enable=Status=0;Reads=Writes=0;}
        public bool Owns(ulong address)=>address==0x40008900 || address==0x40008904 || address==0x40008908 || address==0x4000890c;
        public bool TryRead(ulong address,out uint value)
        {
            value=0;
            if(address==0x40008900)value=Enable;
            else if(address==0x40008904)value=Status;
            else return false;
            Reads++;return true;
        }
        public bool TryWrite(ulong address,uint value)
        {
            if((value&~0x1fffu)!=0)return false;
            if(address==0x40008900)Enable=value;
            else if(address==0x40008904 && value==0)Status=0;
            else if(address==0x40008908)Status&=~value;
            else if(address==0x4000890c)Status|=value;
            else return false;
            Writes++;return true;
        }
        public uint Enable {get;private set;}public uint Status {get;private set;}
        public int Reads {get;private set;}public int Writes {get;private set;}
        public bool Pending=>(Enable&Status)!=0;
    }
}
