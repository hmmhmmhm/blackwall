namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using System.Collections.Generic;
    using Antmicro.Renode.Peripherals;

    public sealed class BlackwallImuRawFifo : IPeripheral
    {
        public BlackwallImuRawFifo(bool enabled=false,bool bigEndian=false,int capacityPackets=128,int frameBytes=16)
        {
            if((frameBytes!=16 && frameBytes!=32) || capacityPackets<1 || capacityPackets>2048/frameBytes)
                throw new ArgumentException("Explicit raw16/raw32 packet capacity within the 2KB profile required");
            Enabled=enabled;BigEndian=bigEndian;CapacityPackets=capacityPackets;FrameBytes=frameBytes;
        }

        public bool TryEnqueueFrame(byte[] frame)
        {
            if(!Enabled || (EnqueueGate!=null && !EnqueueGate()) || frame==null || frame.Length!=FrameBytes || frames.Count==CapacityPackets)
                return false;
            if(FrameBytes==16 ? frame[0]!=0x68 : (frame[0]&0xf0)!=0xe0 || (frame[1]&0xf3)!=0x13)
                return false;
            frames.Enqueue((byte[])frame.Clone());PacketsEnqueued++;FrameEnqueued?.Invoke();return true;
        }

        public bool TryBeginRead(int register,int byteCount)
        {
            if(!Enabled || ReadActive)return false;
            byte[] selected;
            int packets;
            if(register==0x12 && byteCount==2)
            {
                var count=frames.Count;
                selected=BigEndian ? new byte[]{(byte)(count>>8),(byte)count}
                                   : new byte[]{(byte)count,(byte)(count>>8)};
                packets=0;
            }
            else if(register==0x14 && byteCount>0 && byteCount%FrameBytes==0 && byteCount/FrameBytes<=frames.Count)
            {
                selected=new byte[byteCount];packets=byteCount/FrameBytes;
                var prefix=frames.ToArray();
                for(var index=0;index<packets;index++)Array.Copy(prefix[index],0,selected,index*FrameBytes,FrameBytes);
            }
            else return false;
            readBuffer=selected;readCursor=0;reservedPackets=packets;return true;
        }

        public byte[] ReadChunk(int count)
        {
            if(!ReadActive || count<1 || count>ReadRemaining)return null;
            var result=new byte[count];Array.Copy(readBuffer,readCursor,result,0,count);
            readCursor+=count;ReadBytes+=count;return result;
        }

        public bool TryFinishRead()
        {
            if(!ReadActive || ReadRemaining!=0)return false;
            for(var index=0;index<reservedPackets;index++)frames.Dequeue();
            PacketsConsumed+=reservedPackets;ReadsCompleted++;ClearRead();return true;
        }

        public bool TryFlush()
        {
            if(!Enabled || ReadActive)return false;
            frames.Clear();Flushes++;return true;
        }

        public void Reset()
        {
            frames.Clear();ClearRead();PacketsEnqueued=PacketsConsumed=ReadBytes=ReadsCompleted=Flushes=0;
            DeviceReset?.Invoke();
        }

        private void ClearRead() { readBuffer=null;readCursor=reservedPackets=0; }
        public bool Enabled {get;}
        public bool BigEndian {get;}
        public int CapacityPackets {get;}
        public int FrameBytes {get;}
        public int PacketCount => frames.Count;
        public bool ReadActive => readBuffer!=null;
        public int ReadRemaining => ReadActive ? readBuffer.Length-readCursor : 0;
        public long PacketsEnqueued {get;private set;}
        public long PacketsConsumed {get;private set;}
        public long ReadBytes {get;private set;}
        public long ReadsCompleted {get;private set;}
        public long Flushes {get;private set;}
        public event Action FrameEnqueued;
        public event Action DeviceReset;
        internal Func<bool> EnqueueGate {get;set;}
        private readonly Queue<byte[]> frames=new Queue<byte[]>();
        private byte[] readBuffer;
        private int readCursor,reservedPackets;
    }
}
