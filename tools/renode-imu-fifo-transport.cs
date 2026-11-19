namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using Antmicro.Renode.Peripherals.I2C;

    public interface IBlackwallImuFifoRegisters
    {
        bool HandlesRegister(int register);
        bool TryWrite(byte[] data);
        bool TryBeginRead(int register,int bytes);
        byte[] ReadChunk(int bytes);
        bool TryFinishRead();
        bool ReadActive {get;}
        void Reset();
    }

    public sealed class BlackwallImuFifoTransport : II2CPeripheral
    {
        public BlackwallImuFifoTransport(BlackwallStrictIom owner,II2CPeripheral startupPeer,BlackwallImuRawFifo rawFifo=null,BlackwallImuFifoThreshold threshold=null,IBlackwallImuFifoRegisters configuration=null)
        {
            if(owner==null || owner.Module!=4 || startupPeer==null)
                throw new ArgumentException("IOM4 and an existing startup peer required");
            if(threshold!=null && !Object.ReferenceEquals(threshold.RawFifo,rawFifo))
                throw new ArgumentException("Threshold and transport must share the same FIFO");
            this.owner=owner;StartupPeer=startupPeer;RawFifo=rawFifo;Threshold=threshold;Configuration=configuration;
        }

        public void Write(byte[] data)
        {
            if(writeBuffer!=null)
            { AppendConfigurationWrite(data);return; }
            if(statusLease || (RawFifo!=null && RawFifo.ReadActive) || (Configuration!=null && Configuration.ReadActive))
            { Reject("peer-write",data==null ? 0 : data.Length);return; }
            if(Configuration!=null && data!=null && data.Length>0 && Configuration.HandlesRegister(data[0]))
            {
                var command=owner.RegistersCollection.Read(0x120);
                var remaining=(int)((owner.RegistersCollection.Read(0x12c)>>8)&0xfff);
                if((command&0xff)!=1 || remaining<1 || remaining>7 || data.Length!=Math.Min(4,remaining))
                {Reject("peer-write",data.Length);return;}
                if(remaining==1) {selected=data[0];Selections++;return;}
                writeBuffer=new byte[remaining];writeCursor=0;writeCommand=command;
                AppendConfigurationWrite(data);return;
            }
            if(FifoEnabled && RawFifo.PacketCount!=0 && data!=null && data.Length>=2 && data[0]==0x20 && (data[1]&0x80)!=0)
            { Reject("peer-write",data.Length);return; }
            if(FifoEnabled && data!=null && data.Length==1 && (data[0]==0x12 || data[0]==0x14))
            { selected=data[0];Selections++;return; }
            if(FifoEnabled && Threshold!=null && (RawFifo.PacketCount!=0 || Threshold.EventsRaised!=0)
                && data!=null && data.Length==1 && data[0]==0x19)
            { StartupPeer.Write(data);selected=0x19;Selections++;return; }
            StartupPeer.Write(data);selected=-1;
        }

        public byte[] Read(int count=1)
        {
            if(!FifoEnabled || selected<0)return StartupPeer.Read(count);
            if(Configuration!=null && Configuration.HandlesRegister(selected))
            {
                if(!Configuration.ReadActive)
                {
                    var command=owner.RegistersCollection.Read(0x120);
                    var remaining=(int)((owner.RegistersCollection.Read(0x12c)>>8)&0xfff);
                    if(count<1 || count>remaining || (command&0x80)!=0 || !Configuration.TryBeginRead(selected,remaining))
                    {Reject("peer-read",count);return null;}
                }
                var result=Configuration.ReadChunk(count);
                if(result==null) {Reject("peer-read",count);return null;}
                ChunksRead++;BytesRead+=result.Length;return result;
            }
            if(selected==0x19)
            {
                var command=owner.RegistersCollection.Read(0x120);
                var remaining=(int)((owner.RegistersCollection.Read(0x12c)>>8)&0xfff);
                if(statusLease || count!=2 || remaining!=2 || (command&0x80)!=0)
                { Reject("peer-read",count);return null; }
                var snapshot=Threshold.Snapshot();
                var baseline=StartupPeer.Read(count);
                if(baseline==null || baseline.Length!=2 || (baseline[0]&2)!=0)
                { Reject("peer-read",count);return null; }
                var result=(byte[])baseline.Clone();
                if(snapshot!=0)result[0]|=2;
                statusSnapshot=snapshot;statusLease=true;ChunksRead++;BytesRead+=2;return result;
            }
            if(!RawFifo.ReadActive)
            {
                // These pinned engine fields are read-only metadata, not a guest register write.
                var command=owner.RegistersCollection.Read(0x120);
                var remaining=(int)((owner.RegistersCollection.Read(0x12c)>>8)&0xfff);
                if(count<1 || count>remaining || (command&0x80)!=0 || !RawFifo.TryBeginRead(selected,remaining))
                { Reject("peer-read",count);return null; }
            }
            var data=RawFifo.ReadChunk(count);
            if(data==null) { Reject("peer-read",count);return null; }
            ChunksRead++;BytesRead+=data.Length;return data;
        }

        public void FinishTransmission()
        {
            if(writeBuffer!=null)
            {Reject("peer-finish",writeBuffer.Length-writeCursor);return;}
            if(Configuration!=null && Configuration.ReadActive)
            {
                if(!Configuration.TryFinishRead()) {Reject("peer-finish",0);return;}
                selected=-1;TransactionsCompleted++;
            }
            if(statusLease)
            {
                Threshold.Acknowledge(statusSnapshot);statusLease=false;selected=-1;TransactionsCompleted++;
            }
            if(FifoEnabled && selected>=0 && RawFifo.ReadActive)
            {
                if(!RawFifo.TryFinishRead()) { Reject("peer-finish",RawFifo.ReadRemaining);return; }
                selected=-1;TransactionsCompleted++;
            }
            StartupPeer.FinishTransmission();
        }

        public void Reset()
        {
            StartupPeer.Reset();RawFifo?.Reset();selected=-1;statusLease=false;statusSnapshot=0;
            Configuration?.Reset();
            writeBuffer=null;writeCursor=0;writeCommand=0;
            Selections=ChunksRead=BytesRead=TransactionsCompleted=0;
        }

        private void Reject(string operation,int value)
        { owner.RejectDiagnosticPeerAccess(operation=="peer-finish" ? "peer-read" : operation,(uint)Math.Max(0,value)); }
        public II2CPeripheral StartupPeer {get;}
        public BlackwallImuRawFifo RawFifo {get;}
        public BlackwallImuFifoThreshold Threshold {get;}
        public IBlackwallImuFifoRegisters Configuration {get;}
        public bool FifoEnabled => RawFifo!=null && RawFifo.Enabled;
        public int SelectedRegister => selected;
        public long Selections {get;private set;}
        public long ChunksRead {get;private set;}
        public long BytesRead {get;private set;}
        public long TransactionsCompleted {get;private set;}
        private int selected=-1;
        private bool statusLease;
        private ulong statusSnapshot;
        private byte[] writeBuffer;
        private int writeCursor;
        private uint writeCommand;
        private void AppendConfigurationWrite(byte[] data)
        {
            var remaining=(int)((owner.RegistersCollection.Read(0x12c)>>8)&0xfff);
            if(data==null || owner.RegistersCollection.Read(0x120)!=writeCommand || remaining!=writeBuffer.Length-writeCursor || data.Length!=Math.Min(4,remaining))
            {Reject("peer-write",data==null ? 0:data.Length);return;}
            Array.Copy(data,0,writeBuffer,writeCursor,data.Length);writeCursor+=data.Length;
            if(writeCursor!=writeBuffer.Length)return;
            var complete=writeBuffer;writeBuffer=null;writeCursor=0;writeCommand=0;selected=-1;
            if(!Configuration.TryWrite(complete))Reject("peer-write",complete.Length);
        }
        private readonly BlackwallStrictIom owner;
    }
}
