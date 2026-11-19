namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals;

    // Explicit packet watermark profile, not guest register configuration or a physical pin.
    public sealed class BlackwallImuFifoThreshold : IPeripheral
    {
        public BlackwallImuFifoThreshold(BlackwallImuRawFifo rawFifo,int watermarkPackets=0,bool interruptEnabled=false,bool greaterOrEqual=true)
        {
            if(rawFifo==null || watermarkPackets<0 || watermarkPackets>rawFifo.CapacityPackets)
                throw new ArgumentException("A raw FIFO and watermark within its packet capacity required");
            RawFifo=rawFifo;initialWatermark=watermarkPackets;initialEnabled=interruptEnabled;initialGreater=greaterOrEqual;
            IRQ=new GPIO();rawFifo.FrameEnqueued+=OnFrameEnqueued;rawFifo.DeviceReset+=Reset;
        }

        private void OnFrameEnqueued()
        {
            if(!RawFifo.Enabled || !InterruptEnabled || WatermarkPackets==0)return;
            var count=RawFifo.PacketCount;
            if(GreaterOrEqual ? count>=WatermarkPackets : count==WatermarkPackets)
            { generation++;Pending=true;EventsRaised++;IRQ.Set(); }
        }

        public ulong Snapshot() => Pending ? generation : 0;

        public void Acknowledge(ulong snapshot)
        {
            if(!Pending || snapshot!=generation)return;
            Pending=false;StatusClears++;IRQ.Unset();
        }

        public void Reset()
        { generation++;Pending=false;EventsRaised=StatusClears=0;IRQ.Unset(); }

        public BlackwallImuRawFifo RawFifo {get;}
        public int WatermarkPackets => WatermarkProvider!=null ? WatermarkProvider():initialWatermark;
        public bool InterruptEnabled => InterruptProvider!=null ? InterruptProvider():initialEnabled;
        public bool GreaterOrEqual => GreaterProvider!=null ? GreaterProvider():initialGreater;
        public bool Pending {get;private set;}
        public long EventsRaised {get;private set;}
        public long StatusClears {get;private set;}
        public GPIO IRQ {get;}
        private ulong generation;
        private readonly int initialWatermark;
        private readonly bool initialEnabled,initialGreater;
        internal Func<int> WatermarkProvider {get;set;}
        internal Func<bool> InterruptProvider {get;set;}
        internal Func<bool> GreaterProvider {get;set;}
    }
}
