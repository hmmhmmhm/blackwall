namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals.CPU;

    public sealed class BlackwallNemaRingDevice : IBlackwallGpuCommandDevice
    {
        public BlackwallNemaRingDevice(IMachine machine,CortexM cpu,BlackwallG2StartupFixture owner,bool referenceCoverage=false,bool packingReference=false,bool textureReference=false)
        {
            this.machine=machine;this.cpu=cpu;this.referenceCoverage=referenceCoverage;this.packingReference=packingReference;this.textureReference=textureReference;owner.AttachGpuCommandDevice(this);
        }
        public void Submit(uint ringBase,uint ringBytes,uint doorbell)
        {
            try
            {
                if(consumer==null)
                {
                    start=ringBase;size=ringBytes;
                    consumer=new NemaRingConsumer(start,size,
                        (address,count)=>machine.SystemBus.ReadBytes(address,count),
                        (address,data)=>machine.SystemBus.WriteBytes(data,address),referenceCoverage,packingReference,textureReference);
                }
                if(start!=ringBase || size!=ringBytes)throw new InvalidOperationException("Ring changed without GPU reset");
                var packs=consumer.PackingSubmits;var lists=consumer.ListsConsumed;var words=consumer.ConsumedWords;var pixels=consumer.PixelsWritten;var id=consumer.CompletedId;var draws=consumer.Draws;
                consumer.Submit(doorbell);Doorbells++;LastDoorbell=doorbell;
                ListsConsumed+=consumer.ListsConsumed-lists;ConsumedWords+=consumer.ConsumedWords-words;PixelsWritten+=consumer.PixelsWritten-pixels;
                Draws+=consumer.Draws-draws;
                if(consumer.LastSurfaceAddress!=0)
                {
                    FrameAddress=consumer.LastSurfaceAddress;FrameStride=consumer.LastSurfaceStride;FrameWidth=consumer.LastSurfaceWidth;FrameHeight=consumer.LastSurfaceHeight;
                    FrameBytes=machine.SystemBus.ReadBytes(FrameAddress,(int)(FrameStride*FrameHeight));
                    NonzeroPixels=0;foreach(var pixel in FrameBytes)if(pixel!=0)NonzeroPixels++;
                    if(FrameWidth==576 && FrameHeight==288)
                    {
                        ScreenFrameBytes=new byte[576*288];byte min=255,max=0;ScreenNonzeroPixels=0;
                        for(int y=0;y<288;y++)Array.Copy(FrameBytes,y*(int)FrameStride,ScreenFrameBytes,y*576,576);
                        foreach(var pixel in ScreenFrameBytes){if(pixel!=0)ScreenNonzeroPixels++;if(pixel<min)min=pixel;if(pixel>max)max=pixel;}
                        ScreenHasDetail=min!=max;ScreenFrameAddress=FrameAddress;ScreenSourceStride=FrameStride;ScreenCaptures++;
                    }
                }
                if(consumer.PackingSubmits>packs && consumer.LastPackingWidth==576 && consumer.LastPackingHeight==288)
                {
                    CompleteScreenFrameBytes=machine.SystemBus.ReadBytes(consumer.LastPackingSource,576*288);
                    byte min=255,max=0;CompleteScreenNonzero=0;
                    foreach(var pixel in CompleteScreenFrameBytes){if(pixel!=0)CompleteScreenNonzero++;if(pixel<min)min=pixel;if(pixel>max)max=pixel;}
                    CompleteScreenHasDetail=min!=max;CompleteScreenAddress=consumer.LastPackingSource;CompleteScreenCaptures++;
                }
                if(consumer.CompletedId!=id){CompletionEvents++;LastCompletedId=consumer.CompletedId;IrqAssertions++;}
                IRQ.Set(consumer.InterruptPending);
            }
            catch(InvalidOperationException e)
            {
                Fault=e.Message;Rejections++;cpu.IsHalted=true;
                throw new CpuAbortException("BLACKWALL Nema ring: "+e.Message);
            }
        }
        public void AcknowledgeInterrupt() {if(consumer!=null){if(consumer.InterruptPending)IrqAcks++;consumer.AcknowledgeInterrupt();}IRQ.Set(false);}
        public void BeginEpoch() {consumer=null;IRQ.Set(false);Fault="";Epochs++;}
        public void Reset() {consumer=null;IRQ.Set(false);Doorbells=LastDoorbell=Rejections=ListsConsumed=ConsumedWords=PixelsWritten=CompletionEvents=LastCompletedId=IrqAssertions=IrqAcks=Epochs=Draws=0;CompleteScreenFrameBytes=new byte[0];CompleteScreenHasDetail=false;CompleteScreenNonzero=CompleteScreenAddress=CompleteScreenCaptures=0;ScreenFrameBytes=new byte[0];ScreenHasDetail=false;ScreenNonzeroPixels=ScreenFrameAddress=ScreenSourceStride=ScreenCaptures=0;NonzeroPixels=0;FrameAddress=FrameStride=FrameWidth=FrameHeight=0;FrameBytes=new byte[0];Fault="";}
        public uint CompletedId=>consumer==null?0:consumer.CompletedId;
        public bool HasPendingWork=>consumer!=null && consumer.HasPendingWork;
        public uint ListsConsumed {get;private set;}
        public uint ConsumedWords {get;private set;}
        public uint PixelsWritten {get;private set;}
        public uint CompletionEvents {get;private set;}
        public uint LastCompletedId {get;private set;}
        public uint IrqAssertions {get;private set;}
        public uint IrqAcks {get;private set;}
        public uint Epochs {get;private set;}
        public uint Draws {get;private set;}
        public uint FrameAddress {get;private set;}
        public uint FrameStride {get;private set;}
        public uint FrameWidth {get;private set;}
        public uint FrameHeight {get;private set;}
        public byte[] CompleteScreenFrameBytes {get;private set;}=new byte[0];
        public bool CompleteScreenHasDetail {get;private set;}
        public uint CompleteScreenNonzero {get;private set;}
        public uint CompleteScreenAddress {get;private set;}
        public uint CompleteScreenCaptures {get;private set;}
        public byte[] ScreenFrameBytes {get;private set;}=new byte[0];
        public bool ScreenHasDetail {get;private set;}
        public uint ScreenNonzeroPixels {get;private set;}
        public uint ScreenFrameAddress {get;private set;}
        public uint ScreenSourceStride {get;private set;}
        public uint ScreenCaptures {get;private set;}
        public uint NonzeroPixels {get;private set;}
        public byte[] FrameBytes {get;private set;}=new byte[0];
        public string CoverageProfile=>referenceCoverage?"area-reference":"strict";
        public bool InterruptPending=>consumer!=null && consumer.InterruptPending;
        public uint Doorbells {get;private set;}
        public uint LastDoorbell {get;private set;}
        public uint Rejections {get;private set;}
        public string Fault {get;private set;}="";
        public GPIO IRQ {get;}=new GPIO();
        private NemaRingConsumer consumer;
        private uint start,size;
        private readonly IMachine machine;
        private readonly CortexM cpu;
        private readonly bool referenceCoverage,packingReference,textureReference;
    }
}
