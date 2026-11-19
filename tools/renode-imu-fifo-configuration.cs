namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;

    // Raw32 stop-on-full configuration. Register storage does not generate samples or GAF results.
    public sealed class BlackwallImuFifoConfiguration : IBlackwallImuFifoRegisters, IBlackwallImuIndirectExtension
    {
        public BlackwallImuFifoConfiguration(BlackwallImuIdentity startupPeer,BlackwallImuRawFifo rawFifo,BlackwallImuFifoThreshold threshold,int timestampControl=0x60)
        {
            if(startupPeer==null || startupPeer.Configuration==null || startupPeer.Auxiliary==null || !startupPeer.HasIndirectTransport || startupPeer.IndirectExtension!=null ||
               rawFifo==null || rawFifo.FrameBytes!=32 || rawFifo.EnqueueGate!=null || threshold==null || !Object.ReferenceEquals(threshold.RawFifo,rawFifo) || threshold.WatermarkProvider!=null || timestampControl<0 || timestampControl>255)
                throw new ArgumentException("One raw32 FIFO, threshold, shared power configuration and timed startup peer required");
            startup=startupPeer;raw=rawFifo;this.threshold=threshold;initialTimestamp=(byte)timestampControl;
            Reset();startup.AttachIndirectExtension(this);raw.DeviceReset+=Reset;
            raw.EnqueueGate=()=>Ready;
            threshold.WatermarkProvider=()=>Watermark;
            threshold.GreaterProvider=()=> (startup.Configuration.FifoValue&8)!=0;
            threshold.InterruptProvider=()=> (startup.Auxiliary.Interrupt0&2)!=0;
        }

        public bool HandlesRegister(int register)
        { return register==0x1d || (Active && ((register>=0x1d && register<=0x22) || register==0x28)); }

        public bool TryBeginRead(int register,int bytes)
        {
            if(ReadActive || !startup.Configuration.FlushDone || startup.Configuration.FlushPending || bytes<1 ||
               !(register>=0x1d && register+bytes<=0x23 || register==0x28 && bytes==1))return false;
            var snapshot=new byte[bytes];
            for(var k=0;k<bytes;k++)snapshot[k]=register+k==0x20 ? startup.Configuration.ReadRegister(0x20):register+k==0x28 ? decimation:registers[register+k-0x1d];
            buffer=snapshot;cursor=0;Active=true;Reads++;return true;
        }

        public byte[] ReadChunk(int bytes)
        {
            if(!ReadActive || bytes<1 || cursor+bytes>buffer.Length)return null;
            var result=new byte[bytes];Array.Copy(buffer,cursor,result,0,bytes);cursor+=bytes;return result;
        }

        public bool TryFinishRead()
        {
            if(!ReadActive || cursor!=buffer.Length)return false;
            buffer=null;cursor=0;return true;
        }

        public bool TryWrite(byte[] data)
        {
            if(!CanReconfigure || data==null || data.Length<2 || !HandlesRegister(data[0]))return false;
            var address=(int)data[0];var bytes=data.Length-1;
            if(address==0x28)
            {
                if(bytes!=1)return false;
                decimation=data[1];Writes++;return true;
            }
            if(address<0x1d || address+bytes>0x23)return false;
            var trial=(byte[])registers.Clone();var low=lowWritten;var watermark=Watermark;bool comparator=false;
            byte comparatorValue=startup.Configuration.FifoValue;
            for(var k=0;k<bytes;k++)
            {
                var reg=address+k;var value=data[k+1];trial[reg-0x1d]=value;
                if(reg==0x1e)low=true;
                if(reg==0x1f)
                {
                    if(!low)return false;
                    watermark=(trial[2]<<8)|trial[1];low=false;
                }
                if(reg==0x20) {comparator=true;comparatorValue=value;}
            }
            if((trial[0]!=0 && trial[0]!=7 && trial[0]!=0x87) || (trial[4]!=0 && trial[4]!=0x36 && trial[4]!=0x37) || (trial[5]&~3)!=0 ||
               ((trial[4]&1)!=0 && (trial[0]!=0x87 || (trial[5]&1)==0)))return false;
            if(comparator && ((trial[0]&0xc0)!=0 || !startup.Configuration.CanWriteFifoComparator(comparatorValue)))return false;
            if(comparator && !startup.Configuration.TryWriteFifoComparator(comparatorValue))
                throw new InvalidOperationException("Validated shared FIFO comparator changed during transaction");
            registers=trial;lowWritten=low;Watermark=watermark;Writes++;return true;
        }

        public bool Contains(int address) => Active && address==0xa258;

        public bool BeginRead(int address)
        {
            if(!Active || !Contains(address) || indirectPending || ReadActive)return false;
            indirectPending=true;timestampRead=false;return true;
        }

        public byte Read(int address)
        {
            if(!Contains(address) || !indirectPending)throw new ArgumentException("No matching FIFO timestamp read");
            indirectPending=false;timestampRead=true;IndirectReads++;
            return startup.Odr!=null ? startup.Odr.Read(address):timestampStorage;
        }

        public bool TryWrite(int address,byte[] data)
        {
            if(!Contains(address) || !CanReconfigure || !timestampRead || data==null || data.Length!=1)return false;
            var delta=data[0]^TimestampControl;
            if((delta&~3)==0)
            {
                if(startup.Odr!=null)
                { if(!startup.Odr.TryWriteFifoTimestamp(data[0]))return false; }
                else timestampStorage=data[0];
            }
            else if(startup.Odr==null || (delta&~0x10)!=0 || !startup.Odr.TryWrite(address,data[0]))return false;
            timestampRead=false;IndirectWrites++;return true;
        }

        public void Reset()
        {
            registers=new byte[]{0,0,0,0,0,0};decimation=0;Watermark=0;timestampStorage=initialTimestamp;
            Active=lowWritten=indirectPending=timestampRead=false;buffer=null;cursor=0;Reads=Writes=IndirectReads=IndirectWrites=0;
        }

        private bool CanReconfigure => Active && !ReadActive && !raw.ReadActive && raw.PacketCount==0 && !threshold.Pending;
        public bool Ready => Active && registers[0]==0x87 && registers[4]==0x37 && (registers[5]&1)!=0;
        public bool Active {get;private set;}
        public bool ReadActive => buffer!=null;
        public int Watermark {get;private set;}
        public byte TimestampControl => startup.Odr!=null ? startup.Odr.PeekRegister(0xa258):timestampStorage;
        public int Reads {get;private set;}
        public int Writes {get;private set;}
        public int IndirectReads {get;private set;}
        public int IndirectWrites {get;private set;}
        private readonly BlackwallImuIdentity startup;
        private readonly BlackwallImuRawFifo raw;
        private readonly BlackwallImuFifoThreshold threshold;
        private readonly byte initialTimestamp;
        private byte[] registers,buffer;
        private byte decimation;
        private byte timestampStorage;
        private int cursor;
        private bool lowWritten,indirectPending,timestampRead;
    }
}
