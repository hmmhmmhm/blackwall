namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using System.Collections.Generic;
    using Antmicro.Renode.Peripherals.Bus;

    // Passive function-fixture sink. No ring consumption, CLID, IRQ or pixels.
    public sealed class BlackwallNemaDoorbellLatch : IDoubleWordPeripheral, IKnownSize
    {
        public uint ReadDoubleWord(long offset){throw new InvalidOperationException("GPU read is not modeled");}
        public void WriteDoubleWord(long offset,uint value)
        {
            if(offset!=0xec || (value&0xffffff00U)!=0x22000000U || (value&7U)!=4)
                throw new InvalidOperationException("Unsupported function-fixture GPU write");
            writes.Add(value);
        }
        public int WriteCount=>writes.Count;
        public uint GetWrite(int index){return writes[index];}
        public void Reset(){writes.Clear();}
        public long Size=>0x1000;
        private readonly List<uint> writes=new List<uint>();
    }
}
