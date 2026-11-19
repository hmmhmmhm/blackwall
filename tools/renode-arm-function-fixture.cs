namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using System.Collections.Generic;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals.Bus;
    using Antmicro.Renode.Peripherals.CPU;
    using Antmicro.Renode.Logging.Profiling;

    // Function replay only. No ROM services, MMIO completion or guest return stubs.
    public sealed class BlackwallArmFunctionFixture : IDoubleWordPeripheral, IKnownSize
    {
        public BlackwallArmFunctionFixture(IMachine machine, CortexM cpu, uint mainLength, bool memoryGuard=true, uint itcmRawReadPc=0, uint harnessLength=0, uint gpuDoorbellWritePc=0)
        {
            this.cpu=cpu;this.machine=machine;
            cpu.AddHook(0x10000000,(c,a)=>{Boundary="return";Stopped=true;cpu.IsHalted=true;});
            cpu.SetHookAtBlockBegin((pc,count)=>
            {
                Blocks++;
                if(irqConfigured && pc==irqPendSv)
                {
                    PendSvEntries++;PendSvEntryR0=cpu.GetRegister(0).RawValue;
                    if(deferredRelease!=null && !DeferredReleased)
                    {
                        BlockWaiters=machine.SystemBus.ReadDoubleWord(deferredQueue+0x24);
                        BlockMessages=machine.SystemBus.ReadDoubleWord(deferredQueue+0x38);
                        BlockEventContainer=machine.SystemBus.ReadDoubleWord(deferredTcb+40);
                        BlockStateContainer=machine.SystemBus.ReadDoubleWord(deferredTcb+20);
                        BlockSchedulerSuspended=machine.SystemBus.ReadDoubleWord(deferredSuspended);
                        BlockReadyCount=machine.SystemBus.ReadDoubleWord(deferredReadyList);
                        if(BlockWaiters!=1 || BlockMessages!=0 || BlockEventContainer!=deferredQueue+0x24 ||
                           BlockStateContainer==deferredReadyList || BlockSchedulerSuspended!=0 || BlockReadyCount!=0)
                            Fail("deferred-wait-not-established",pc,deferredQueue,4);
                        if(blockBoundaryControl)
                        {
                            Boundary="semaphore-blocked";Stopped=true;cpu.IsHalted=true;
                            throw new CpuAbortException("BLACKWALL deferred GPU completion withheld at real waiter boundary");
                        }
                        deferredRelease();DeferredReleased=true;
                    }
                    if(!kernelContext)
                    {
                        Boundary="rtos-context-required";Stopped=true;cpu.IsHalted=true;
                        throw new CpuAbortException("BLACKWALL original PendSV requires a complete RTOS context");
                    }
                }
                if(harnessLength>0x1000)throw new ArgumentException("Bounded ARM test caller required");
                var harness=harnessLength!=0 && pc>=0x2100e000 && pc<0x2100e000UL+harnessLength;
                if(pc!=0x10000000 && !harness && !(pc>=0x438000 && pc<0x438000UL+mainLength))
                    Fail("execute-boundary",pc,pc,0);
            });
            if(memoryGuard)cpu.SetHookAtMemoryAccess((pc,op,va,pa,width,value)=>
            {
                var size=(ulong)width;
                var write=op==MemoryOperation.MemoryWrite || op==MemoryOperation.MemoryIOWrite;
                var rom=pa>=0x438000 && pa+size<=0x438000UL+mainLength;
                var sram=pa>=0x20000000 && pa+size<=(kernelContext?0x20380000UL:0x20080000UL);
                var work=pa>=0x21000000 && pa+size<=0x21010000;
                var returnSentinel=pa>=0x10000000 && pa+size<=0x10001000;
                var rawItcmRead=false;
                if(!write && itcmRawReadPc!=0 && pc==itcmRawReadPc && pa==0x10 && size==4 && cpu.GetRegister(5).RawValue==0)
                {
                    var descriptor=cpu.GetRegister(0).RawValue;
                    var descriptorInWork=descriptor>=0x21000000 && descriptor+32<=0x21010000;
                    var descriptorInTask=kernelContext && descriptor>=pspLow && descriptor+32<=pspHigh;
                    if((descriptorInWork || descriptorInTask)
                        && (machine.SystemBus.ReadByte(descriptor+20)&1)!=0
                        && machine.SystemBus.ReadDoubleWord(descriptor+24)!=0)
                    {
                        rawItcmRead=true;ItcmReads++;ItcmReadWord=machine.SystemBus.ReadDoubleWord(0x10);
                    }
                }
                if(write)
                {
                    Writes++;
                    var doorbell=gpuDoorbellWritePc!=0 && pc==gpuDoorbellWritePc && pa==0x400900ec && size==4
                        && (value&0xffffff00UL)==0x22000000UL && (value&7UL)==4;
                    var irqWrite=irqConfigured && size==4 &&
                        ((pc==irqRegisterWritePc && pa==0x400900f8 && value==0) ||
                         (pa==0xe000e280 && value==0x10000000) ||
                         (pa==0xe000ed04 && value==0x10000000) ||
                         (pc==irqLastStorePc && pa==irqLastAddress) ||
                         (pc==irqCountStorePc && pa==irqCountAddress));
                    var kernelWrite=kernelContext && ((pa>=pspLow && pa+size<=pspHigh) ||
                        (pa>=mspLow && pa+size<=mspHigh) || (size<=4 && pa>=0x20000000 && pa+size<=0x20380000 &&
                         kernelWords.Contains((uint)pa&~3U) && (pa&3)+size<=4));
                    if(kernelContext)foreach(var range in extraStacks)if(pa>=range.Item1 && pa+size<=range.Item2)kernelWrite=true;
                    if(!work && !doorbell && !irqWrite && !kernelWrite)Fail("write-boundary",pc,pa,size);
                }
                else if(!rom && !sram && !work && !returnSentinel && !rawItcmRead &&
                        !(irqConfigured && pc==irqRegisterReadPc && pa==0x40090148 && size==4))Fail("read-boundary",pc,pa,size);
            });
        }
        public void ConfigureGpuIrq(uint handler,uint pendsv,uint readPc,uint writePc,uint lastStorePc,uint lastAddress,uint countStorePc,uint countAddress)
        {
            if(irqConfigured || lastAddress<0x20000000 || lastAddress>0x2007fffc || countAddress<0x20000000 || countAddress>0x2007fffc)
                throw new ArgumentException("Invalid bounded GPU IRQ fixture");
            irqConfigured=true;irqPendSv=pendsv;irqRegisterReadPc=readPc;irqRegisterWritePc=writePc;
            irqLastStorePc=lastStorePc;irqLastAddress=lastAddress;irqCountStorePc=countStorePc;irqCountAddress=countAddress;
            cpu.AddHook(handler,(c,a)=>{IrqEntries++;IrqEntryR3=cpu.GetRegister(3).RawValue;IrqEntryXpsr=cpu.GetRegister(25).RawValue;});
        }
        public void AddKernelWord(uint address)
        {
            if(kernelContext || (address&3)!=0 || address<0x20000000 || address>0x2037fffc || kernelWords.Count>=128)
                throw new ArgumentException("Invalid bounded kernel word");
            kernelWords.Add(address);
        }
        public void AddKernelStack(uint low,uint high)
        {
            if(kernelContext || low>=high || low<0x20000000 || high>0x20380000 || extraStacks.Count>=2)
                throw new ArgumentException("Bounded captured alternate task stack required");
            extraStacks.Add(Tuple.Create(low,high));
        }
        public void EnableKernelContext(uint taskLow,uint taskHigh,uint handlerLow,uint handlerHigh,uint selector,uint afterSelector,uint returnPc,uint tcbSlot)
        {
            if(!irqConfigured || kernelContext || taskLow>=taskHigh || taskLow<0x20000000 || taskHigh>0x20380000 ||
                handlerLow>=handlerHigh || handlerLow<0x20000000 || handlerHigh>0x20380000)
                throw new ArgumentException("Explicit captured stack ranges required");
            kernelContext=true;pspLow=taskLow;pspHigh=taskHigh;mspLow=handlerLow;mspHigh=handlerHigh;
            cpu.AddHook(selector,(c,a)=>{SelectorEntries++;});
            cpu.AddHook(afterSelector,(c,a)=>{SelectedTcb=machine.SystemBus.ReadDoubleWord(tcbSlot);SavedTaskSp=machine.SystemBus.ReadDoubleWord(SelectedTcb);selectedTasks.Add(SelectedTcb);});
            cpu.AddHook(returnPc,(c,a)=>{PortReturns++;PortExceptionReturn=cpu.GetRegister(3).RawValue;});
        }
        public void ConfigureDeferredCompletion(Action release,uint queue,uint tcb,uint suspendedSlot,uint readyList,bool boundaryControl=false)
        {
            if(!kernelContext || deferredRelease!=null || release==null)throw new ArgumentException("Deferred completion requires one captured kernel context");
            deferredRelease=release;deferredQueue=queue;deferredTcb=tcb;deferredSuspended=suspendedSlot;deferredReadyList=readyList;blockBoundaryControl=boundaryControl;
        }
        public void SeedRegister(int index,uint value)
        {
            if(index==18 && (value&2)!=0)
                throw new ArgumentException("Select PSP with guest MSR CONTROL; the host register setter does not switch stack banks");
            if(index==15)cpu.PC=value;else cpu.SetRegister(index,value);
        }
        public void BeginCall(){Boundary="none";Stopped=false;cpu.IsHalted=false;}
        private void Fail(string reason,ulong pc,ulong address,ulong width)
        {
            Boundary=reason;FaultPc=pc;FaultAddress=address;FaultWidth=width;Violations++;Stopped=true;
            throw new CpuAbortException("BLACKWALL function boundary "+reason);
        }
        public uint ReadDoubleWord(long offset){throw new InvalidOperationException("No guest fixture IO allowed");}
        public void WriteDoubleWord(long offset,uint value){throw new InvalidOperationException("No guest fixture IO allowed");}
        public void Reset(){}
        public long Size=>4;
        public bool Stopped{get;private set;}
        public string Boundary{get;private set;}="none";
        public ulong FaultPc{get;private set;} public ulong FaultAddress{get;private set;} public ulong FaultWidth{get;private set;}
        public ulong Blocks{get;private set;} public ulong Writes{get;private set;} public int Violations{get;private set;}
        public uint ItcmReads{get;private set;} public uint ItcmReadWord{get;private set;}
        public uint IrqEntries{get;private set;}public uint PendSvEntries{get;private set;}
        public ulong IrqEntryR3{get;private set;}public ulong IrqEntryXpsr{get;private set;}
        public ulong PendSvEntryR0{get;private set;}
        public uint SelectorEntries{get;private set;}public uint PortReturns{get;private set;}
        public uint SelectedTcb{get;private set;}public uint SavedTaskSp{get;private set;}
        public ulong PortExceptionReturn{get;private set;}
        public uint GetSelectedTask(int index){return selectedTasks[index];}
        public int SelectionCount=>selectedTasks.Count;
        public bool DeferredReleased{get;private set;}
        public uint BlockWaiters{get;private set;}public uint BlockMessages{get;private set;}
        public uint BlockEventContainer{get;private set;}public uint BlockStateContainer{get;private set;}
        public uint BlockSchedulerSuspended{get;private set;}public uint BlockReadyCount{get;private set;}
        private Action deferredRelease;private uint deferredQueue,deferredTcb,deferredSuspended,deferredReadyList;private bool blockBoundaryControl;
        private bool irqConfigured;
        private bool kernelContext;private uint pspLow,pspHigh,mspLow,mspHigh;
        private readonly HashSet<uint> kernelWords=new HashSet<uint>();
        private readonly List<Tuple<uint,uint>> extraStacks=new List<Tuple<uint,uint>>();
        private readonly List<uint> selectedTasks=new List<uint>();
        private uint irqPendSv,irqRegisterReadPc,irqRegisterWritePc,irqLastStorePc,irqLastAddress,irqCountStorePc,irqCountAddress;
        private readonly CortexM cpu;
        private readonly IMachine machine;
    }
}
