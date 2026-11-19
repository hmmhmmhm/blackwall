namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    // MSPI1 field storage only. Does not generate a clock or implement a bus engine.
    public sealed class BlackwallMspi1ClockStorage : IBlackwallMspi1Clock
    {
        public BlackwallMspi1ClockStorage(string profile,bool mspi0Storage=false)
        {
            if(profile!="source-reset-storage") throw new System.ArgumentException("Explicit MSPI1 clock profile required");
            Mspi0Storage=mspi0Storage;
            Reset();
        }
        public void Reset() { Value=0xa4214; Reads=Writes=ChangeEpoch=0; }
        public uint Read() { Reads++; return Value; }
        public bool TryWrite(uint value)
        {
            // Unselected modules and reserved bits must retain their source reset values.
            var selection=(value>>6)&15;
            var mask=Mspi0Storage ? 0x3ffu : 0x3e0u;
            var selection0=(value>>1)&15;
            if((value&~mask)!=(0xa4214u&~mask) || (selection!=7 && selection!=8)
                || (Mspi0Storage && (selection0<7 || selection0>10))) return false;
            if(Mspi0Storage && ((Value^value)&0x1fu)!=0 && ((Value^value)&0x3e0u)!=0)return false;
            if(Value!=value)ChangeEpoch++;
            Value=value; Writes++; return true;
        }
        public uint Value { get; private set; }
        public uint ChangeEpoch { get; private set; }
        public uint Reads { get; private set; }
        public uint Writes { get; private set; }
        public bool Enabled => (Value&0x20)!=0;
        public uint Selection => (Value>>6)&15;
        public bool Mspi0Storage {get;}
        public bool Mspi0Enabled => (Value&1)!=0;
        public uint Mspi0Selection => (Value>>1)&15;
    }
}
