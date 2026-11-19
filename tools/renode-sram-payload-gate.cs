namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    public sealed class BlackwallSramPayloadGate
    {
        public BlackwallSramPayloadGate(byte[] image,uint entryOffset,System.Func<ulong,int,byte[]> read)
        {
            if(image==null || image.Length<2 || image.Length>512 || (image.Length&1)!=0
                || entryOffset>=(uint)image.Length || (entryOffset&1)!=0 || read==null)
                throw new System.ArgumentException("Bounded even SRAM payload image and entry required");
            expected=(byte[])image.Clone();EntryOffset=entryOffset;this.read=read;
        }
        public void Reset() { BaseAddress=0;Approvals=WordValidations=Rejections=0; }
        public bool TryEnter(ulong pc)
        {
            if((pc&1)!=0 || pc<EntryOffset)return Reject();
            var start=pc-EntryOffset;
            if(start<0x20000000 || start>0x20080000UL-(ulong)expected.Length || BaseAddress!=0 && BaseAddress!=start)return Reject();
            var actual=read(start,expected.Length);
            if(actual==null || actual.Length!=expected.Length)return Reject();
            for(var i=0;i<expected.Length;i++)if(actual[i]!=expected[i])return Reject();
            if(BaseAddress==0) { BaseAddress=start;Approvals++; }
            return true;
        }
        public bool TryReadWord(ulong address,out ushort word)
        {
            word=0;
            if(BaseAddress==0 || (address&1)!=0 || address<BaseAddress || address>BaseAddress+(ulong)expected.Length-2)return Reject();
            var actual=read(address,2);var offset=(int)(address-BaseAddress);
            if(actual==null || actual.Length!=2 || actual[0]!=expected[offset] || actual[1]!=expected[offset+1])return Reject();
            word=(ushort)(actual[0]|actual[1]<<8);WordValidations++;return true;
        }
        private bool Reject() { Rejections++;return false; }
        public int Length=>expected.Length;
        public uint EntryOffset {get;}
        public ulong BaseAddress {get;private set;}
        public uint Approvals {get;private set;}
        public uint WordValidations {get;private set;}
        public uint Rejections {get;private set;}
        private readonly byte[] expected;
        private readonly System.Func<ulong,int,byte[]> read;
    }
}
