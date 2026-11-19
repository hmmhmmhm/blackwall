namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using System.Collections.Generic;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals.Bus;
    using Antmicro.Renode.Peripherals.CPU;

    // Explicit diagnostic profile, not a hardware-validated Nema implementation.
    // One nominal synthetic ring, binary white A4, zero L8, integer translation.
    public sealed class BlackwallNemaReferenceGpu : IDoubleWordPeripheral, IKnownSize
    {
        public BlackwallNemaReferenceGpu(IMachine machine,CortexM cpu,uint mainLength,bool enabled=false,bool completionIrq=false,bool deferCompletionIrq=false)
        {
            if(deferCompletionIrq && !completionIrq)throw new ArgumentException("Deferred completion requires IRQ profile");
            this.machine=machine;this.cpu=cpu;this.mainLength=mainLength;this.enabled=enabled;this.completionIrq=completionIrq;this.deferCompletionIrq=deferCompletionIrq;
        }
        public uint ReadDoubleWord(long offset)
        {
            if(!completionIrq || offset!=0x148 || phase!=2 || !CompletionReleased)Reject("GPU reads/completion are unsupported");
            ClidReads++;return QueuedId;
        }
        public void WriteDoubleWord(long offset,uint value)
        {
            if(!enabled)Reject("Reference GPU profile is disabled");
            if(completionIrq && offset==0xf8)
            {
                if(phase!=2 || value!=0 || IrqAcks!=0)Reject("Unsupported GPU IRQ acknowledgement");
                IrqAcks++;IRQ.Set(false);return;
            }
            if(offset!=0xec)Reject("Unsupported GPU register");
            if(phase==0)
            {
                if(value!=0x22000014)Reject("Unsupported first ring boundary");
                var header=ReadWords(0x2100b000,4);
                if(header[0]!=0xf0 || header[1]!=0x21004000 || header[2]!=0x200f4 || header[3]!=42)
                    Reject("Unsupported ring list reference");
                var frame=PrepareFrame(ReadWords(header[1],42),out var bytes,out var samples);
                // All source/profile/destination checks finish before any DMA write.
                machine.SystemBus.WriteBytes(frame,0x2100a000);
                FrameBytesWritten=bytes;Samples=samples;FramesWritten=1;ConsumedWords=42;phase=1;
            }
            else if(phase==1)
            {
                if(value!=0x22000034)Reject("Unsupported second ring boundary");
                var footer=ReadWords(0x2100b010,8);
                var expected=new uint[]{0x148,8,0xf8,1,0xff0000f0,0x22000030,0xff0000f4,0};
                for(var n=0;n<expected.Length;n++)if(footer[n]!=expected[n])Reject("Unsupported queued-ID/hold footer");
                QueuedId=8;IrqRequestObserved=true;phase=2;
                if(completionIrq && !deferCompletionIrq)ReleaseCompletion();
            }
            else Reject("Only one submitted diagnostic list is supported");
            writes.Add(value);
        }
        private byte[] PrepareFrame(uint[] words,out uint bytes,out uint samples)
        {
            var order=new uint[]{0,4,8,0x110,0x114,0x1d0,0x118,0x11c,0x1c,0x10,0x14,0x18,
                0x174,0x168,0x160,0x164,0x16c,0x170,0x104,0x108,0xff000100};
            var state=new Dictionary<uint,uint>();
            for(var n=0;n<order.Length;n++)
            {
                if(words[n*2]!=order[n])Reject("Unsupported command order");
                state.Add(order[n],words[n*2+1]);
            }
            var stride=state[4]&0xffffU;
            var required=new Dictionary<uint,uint>{{0,0x2100a000},{4,0x09000000U|stride},{8,0x00200040},
                {0x1d0,0x504},{0x118,0},{0x11c,0x141f801f},{0x1c,0xffffffff},
                {0x160,0x3f800000},{0x164,0},{0x16c,0},{0x170,0x3f800000},{0xff000100,2}};
            if(stride!=64 && stride!=80)Reject("Unsupported destination stride");
            foreach(var pair in required)if(state[pair.Key]!=pair.Value)Reject("Unsupported render profile");
            var x0=state[0x104]&0xffff;var y0=state[0x104]>>16;
            var x1=state[0x108]&0xffff;var y1=state[0x108]>>16;
            var cx0=state[0x110]&0xffff;var cy0=state[0x110]>>16;
            var cx1=state[0x114]&0xffff;var cy1=state[0x114]>>16;
            if(!(x0<x1 && x1<=64 && y0<y1 && y1<=32 && cx0<=cx1 && cx1<=64 && cy0<=cy1 && cy1<=32))
                Reject("Unsupported draw/clip bounds");
            if(state[0x168]!=FloatWord(-(int)x0) || state[0x174]!=FloatWord(-(int)y0))Reject("Unsupported translation");
            var width=x1-x0;var height=y1-y0;var sourceStride=width/2+1;
            var sourceWidth=width+(width%2==0?2U:0U);
            if(state[0x14]!=(0x34000000U|sourceStride) || state[0x18]!=((height<<16)|sourceWidth))
                Reject("Unsupported source format/stride/filter");
            var source=state[0x10];var size=sourceStride*height;
            if(source<0x438000 || (ulong)source+size>0x438000UL+mainLength)Reject("Source outside original ROM");
            bytes=stride*32;samples=0;
            var initial=machine.SystemBus.ReadBytes(0x2100a000,(int)bytes);
            foreach(var pixel in initial)if(pixel!=0)Reject("Destination must be zero");
            var packed=machine.SystemBus.ReadBytes(source,(int)size);
            var frame=new byte[bytes];
            for(uint sy=0;sy<height;sy++)for(uint sx=0;sx<width;sx++)
            {
                var nibble=(packed[sy*sourceStride+sx/2]>>(sx%2==0?4:0))&15;
                if(nibble!=0 && nibble!=15)Reject("Intermediate A4 alpha is unverified");
                var x=x0+sx;var y=y0+sy;
                if(x>=cx0 && x<cx1 && y>=cy0 && y<cy1){frame[y*stride+x]=(byte)(nibble*17);samples++;}
            }
            return frame;
        }
        public void ReleaseCompletion()
        {
            if(!enabled || !completionIrq || phase!=2 || CompletionReleased)Reject("Completion release requires one fully consumed list");
            CompletionReleased=true;IRQ.Set(true);
        }
        private uint[] ReadWords(ulong address,int count)
        {
            var words=new uint[count];
            for(var n=0;n<count;n++)words[n]=machine.SystemBus.ReadDoubleWord(address+(ulong)(4*n));
            return words;
        }
        private static uint FloatWord(int value){return BitConverter.ToUInt32(BitConverter.GetBytes((float)value),0);}
        private void Reject(string reason)
        {
            Fault=reason;Stopped=true;Rejections++;cpu.IsHalted=true;
            throw new CpuAbortException("BLACKWALL reference GPU: "+reason);
        }
        public int WriteCount=>writes.Count;
        public uint GetWrite(int index){return writes[index];}
        public uint FramesWritten{get;private set;}public uint FrameBytesWritten{get;private set;}
        public uint ConsumedWords{get;private set;}public uint Samples{get;private set;}public uint QueuedId{get;private set;}
        public bool IrqRequestObserved{get;private set;}public bool Stopped{get;private set;}
        public string Fault{get;private set;}="";public uint Rejections{get;private set;}
        public void Reset(){phase=0;writes.Clear();FramesWritten=0;FrameBytesWritten=0;ConsumedWords=0;Samples=0;QueuedId=0;IrqRequestObserved=false;Stopped=false;Fault="";Rejections=0;ClidReads=0;IrqAcks=0;CompletionReleased=false;IRQ.Set(false);}
        public long Size=>0x1000;
        public GPIO IRQ{get;}=new GPIO();
        public uint ClidReads{get;private set;}public uint IrqAcks{get;private set;}
        public bool CompletionReleased{get;private set;}
        private readonly IMachine machine;private readonly CortexM cpu;private readonly uint mainLength;private readonly bool enabled;private readonly bool completionIrq;private readonly bool deferCompletionIrq;
        private readonly List<uint> writes=new List<uint>();private int phase;
    }
}
