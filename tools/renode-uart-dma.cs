namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using Antmicro.Renode.Core;

    public sealed class BlackwallUartDmaTx : IBlackwallUartDmaTx
    {
        public BlackwallUartDmaTx(IMachine machine,string profile="sram-tx-complete")
        {
            if(profile!="sram-tx-complete" && profile!="sram-tx-stalled")throw new ArgumentException("Unknown SRAM UART DMA TX profile");
            this.machine=machine;Profile=profile;Reset();
        }
        public void Bind(BlackwallUartAdapter adapter)
        {
            if(owner!=null || adapter==null || adapter.Module!=0 || !adapter.InterruptsEnabled || !adapter.IdleDmaInterrupts)throw new ArgumentException("One UART0 DMA owner required");
            owner=adapter;
        }
        public bool Owns(long offset) => offset==4 || offset==0x48 || offset==0x4c || offset==0x50;
        public bool TryRead(long offset,out uint value)
        {
            value=0;
            if(offset==4)value=Status;
            else if(offset==0x48)value=Control;
            else if(offset==0x4c)value=Target;
            else if(offset==0x50)value=Count;
            else return false;
            return true;
        }
        public bool TryWrite(long offset,uint value)
        {
            if(offset==4)
            {
                if((value&~0x3fu)!=0 || ((value&0x30u)&~Status)!=0)return false;
                Status=value&0x30u;return true;
            }
            if(offset==0x4c)
            {
                if((Control&2)!=0 || Busy || value<0x20000000 || value>=0x20380000)return false;
                Target=value;targetSet=true;return true;
            }
            if(offset==0x50)
            {
                if((Control&2)!=0 || Busy || value>4095)return false;
                Count=value;countSet=true;return true;
            }
            if(offset!=0x48 || (value!=0 && value!=8 && value!=2 && value!=10))return false;
            if(value==0)
            {
                if(Busy) { Cancellations++;Phase="cancelled"; }
                else Phase="stopped";
                Control=0;targetSet=countSet=false;return true;
            }
            if(value==8)
            {
                if((Control&2)!=0 || Busy)return false;
                Control=8;return true;
            }
            if((Control!=0 && Control!=8) || Busy || owner==null || !targetSet || !countSet || Count==0
                || (ulong)Target+Count>0x20380000 || Status!=0 || RawInterrupts!=0 || !owner.CanDmaTransmit(Count))return false;
            if(Profile=="sram-tx-stalled") { Control=value;Starts++;Phase="running";return true; }
            var bytes=new byte[Count];
            for(uint index=0;index<Count;index++)bytes[index]=machine.SystemBus.ReadByte(Target+index);
            if(!owner.TransmitDma(bytes))return false;
            Transfers.Add(new Transfer(Target,bytes));
            Control=value;Starts++;TransferredBytes+=Count;Completions++;Status=0x10;RawInterrupts=0x800;Phase="completed";
            return true;
        }
        public void ClearInterrupts(uint mask) { RawInterrupts&=~(mask&0x1800u); }
        private void ClearState()
        {
            Target=Count=Control=Status=RawInterrupts=0;targetSet=countSet=false;Phase="idle";
        }
        public void Reset() { Starts=Completions=Cancellations=0;TransferredBytes=0;Transfers.Clear();ClearState(); }
        public void PowerDown() { if(Busy)Cancellations++;ClearState(); }
        public string Profile { get; }
        public string Phase { get; private set; }
        public bool Busy => Phase=="running";
        public uint Control { get; private set; }
        public uint Target { get; private set; }
        public uint Count { get; private set; }
        public uint Status { get; private set; }
        public uint RawInterrupts { get; private set; }
        public uint Starts { get; private set; }
        public uint Completions { get; private set; }
        public uint Cancellations { get; private set; }
        public ulong TransferredBytes { get; private set; }
        public System.Collections.Generic.List<Transfer> Transfers { get; } = new System.Collections.Generic.List<Transfer>();
        public sealed class Transfer
        {
            public Transfer(uint target,byte[] data) { Target=target;Data=data; }
            public uint Target { get; }
            public byte[] Data { get; }
        }
        private bool targetSet,countSet;
        private readonly IMachine machine;
        private BlackwallUartAdapter owner;
    }
}
