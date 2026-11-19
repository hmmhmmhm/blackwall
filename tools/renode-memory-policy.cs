namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using System.Collections.Generic;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals;
    using Antmicro.Renode.Peripherals.CPU;
    using Antmicro.Renode.Peripherals.Memory;
    using Antmicro.Renode.Logging.Profiling;
    
    public sealed class BlackwallMemoryPolicy : IPeripheral
    {
        public BlackwallMemoryPolicy(IMachine machine, TranslationCPU cpu, MappedMemory main,
            MappedMemory itcm, ulong mainLength)
        {
            if(mainLength < 10 || mainLength > 0x3c0000)
                throw new ArgumentException("Main extent outside research mapping");
            this.machine = machine;
            this.cpu = cpu;
            this.main = main;
            this.itcm = itcm;
            this.mainLength = mainLength;
            Reset();
        }

        public void Reset()
        {
            Array.Clear(written, 0, written.Length);
            validatedBlocks.Clear();
            Violations = WrittenBytes = 0;
            LastAddress = LastPC = 0;
            LastWidth = 0;
            LastOperation = "none";
        }

        public void BindBootImage(MappedMemory bootImage, ulong length)
        {
            if(attached || boot != null)
                throw new InvalidOperationException("Bind one boot image before attaching the policy");
            if(bootImage == null || ReferenceEquals(bootImage, main) || ReferenceEquals(bootImage, itcm)
                || length < 10 || length > MainBase-BootBase)
                throw new ArgumentException("Boot extent outside the separate boot mapping");
            boot = bootImage;
            bootLength = length;
        }

        public void Attach()
        {
            if(attached) throw new InvalidOperationException("Policy already attached");
            var bus = machine.SystemBus;
            cpu.EnableExternalWindowMmu(ExternalMmuPosition.BeforeInternal);
            if(boot == null)
                AddWindow(0,MainBase,ExternalMmuBase.Privilege.All);
            else
            {
                AddWindow(0,BootBase,ExternalMmuBase.Privilege.All);
                AddWindow(BootBase,MainBase,ExternalMmuBase.Privilege.Read | ExternalMmuBase.Privilege.Execute);
            }
            AddWindow(MainBase,MainBase+0x3c0000,ExternalMmuBase.Privilege.Read | ExternalMmuBase.Privilege.Execute);
            AddWindow(MainBase+0x3c0000,0x100000000,ExternalMmuBase.Privilege.All);
            cpu.AddHookOnMmuFault((address,accessType,windowId,firstTry) =>
            {
                var operation = accessType == AccessType.Write && boot != null && address >= BootBase && address < MainBase
                    ? "write-boot" : accessType == AccessType.Write && address >= MainBase && address < MainBase+0x3c0000
                    ? "write-main" : "external-permission-fault";
                Stop(operation,address,0);
                return ExternalMmuResult.Fault;
            });
            bus.SetHookAfterPeripheralRead<byte>(main, (v,o) => { CheckMainRead(o,1); return v; });
            bus.SetHookAfterPeripheralRead<ushort>(main, (v,o) => { CheckMainRead(o,2); return v; });
            bus.SetHookAfterPeripheralRead<uint>(main, (v,o) => { CheckMainRead(o,4); return v; });
            bus.SetHookAfterPeripheralRead<ulong>(main, (v,o) => { CheckMainRead(o,8); return v; });
            if(boot != null)
            {
                bus.SetHookAfterPeripheralRead<byte>(boot, (v,o) => { CheckBootRead(o,1); return v; });
                bus.SetHookAfterPeripheralRead<ushort>(boot, (v,o) => { CheckBootRead(o,2); return v; });
                bus.SetHookAfterPeripheralRead<uint>(boot, (v,o) => { CheckBootRead(o,4); return v; });
                bus.SetHookAfterPeripheralRead<ulong>(boot, (v,o) => { CheckBootRead(o,8); return v; });
            }
            cpu.SetHookAtMemoryAccess((pc,operation,virtualAddress,physicalAddress,width,value) =>
            {
                if((operation == MemoryOperation.MemoryWrite || operation == MemoryOperation.MemoryIOWrite)
                    && physicalAddress < 0x40000)
                    MarkWritten((long)physicalAddress,(int)width);
            });
            RouteMainReadsViaIo();
            machine.PeripheralReset += (m, peripheral) =>
            {
                if(ReferenceEquals(peripheral, cpu)) RouteMainReadsViaIo();
            };
            cpu.SetHookAtBlockBegin(CheckBlock);
            attached = true;
        }

        public void BindFunctionalRomEntry(Action<uint> guard)
        {
            if(attached || functionalRomGuard!=null || guard==null)
                throw new InvalidOperationException("Bind one explicit ROM entry contract before attaching");
            functionalRomGuard=guard;
        }

        private void RouteMainReadsViaIo()
        {
            for(ulong page=MainBase; page<MainBase+0x3c0000; page+=0x1000) cpu.SetPageAccessViaIo(page);
            if(boot != null)
                for(ulong page=BootBase; page<MainBase; page+=0x1000) cpu.SetPageAccessViaIo(page);
        }

        private void AddWindow(ulong start, ulong end, ExternalMmuBase.Privilege permissions)
        {
            var id = cpu.AcquireExternalMmuWindow(ExternalMmuBase.Privilege.All);
            cpu.SetMmuWindowPrivileges(id,permissions);
            cpu.SetMmuWindowStart(id,start);
            cpu.SetMmuWindowEnd(id,end);
            cpu.SetMmuWindowAddend(id,0);
        }

        private void CheckMainRead(long offset, int width)
        {
            if(offset < 0 || (ulong)offset+ (ulong)width > mainLength)
                Stop("read-main-padding", MainBase+(ulong)offset, width);
        }

        private void CheckBootRead(long offset, int width)
        {
            if(offset < 0 || (ulong)offset+(ulong)width > bootLength)
                Stop("read-boot-padding", BootBase+(ulong)offset, width);
        }

        private void MarkWritten(long offset, int width)
        {
            if(offset < 0 || offset+width > written.Length)
                Stop("write-outside-itcm", (ulong)offset, width);
            validatedBlocks.Clear();
            for(var i=offset; i<offset+width; i++)
            {
                if(!written[i]) { written[i] = true; WrittenBytes++; }
            }
        }

        private void CheckBlock(ulong pc, uint instructions)
        {
            if(pc==0x0200ff20 && functionalRomGuard!=null)
            { functionalRomGuard(instructions); return; }
            if(pc >= MainBase && pc < MainBase+mainLength && pc+4UL*instructions <= MainBase+mainLength)
                return;
            if(boot != null && pc >= BootBase && pc < BootBase+bootLength && pc+4UL*instructions <= BootBase+bootLength)
                return;
            if(pc < 0x40000 && validatedBlocks.TryGetValue(pc,out var cachedSize) && cachedSize == instructions) return;
            var address = pc;
            for(uint i=0; i<instructions; i++)
            {
                var inMain = address >= MainBase && address+2 <= MainBase+mainLength;
                var inBoot = boot != null && address >= BootBase && address+2 <= BootBase+bootLength;
                var inItcm = address+2 <= 0x40000;
                if(!inMain && !inBoot && !inItcm) Stop("execute-outside-code",address,2);
                if(inItcm && (!written[address] || !written[address+1]))
                    Stop("execute-unwritten-itcm",address,2);
                var first = inMain ? main.ReadWord((long)(address-MainBase))
                    : inBoot ? boot.ReadWord((long)(address-BootBase)) : itcm.ReadWord((long)address);
                var width = (first >> 11) >= 0x1d ? 4 : 2;
                if(inMain && address+(ulong)width > MainBase+mainLength)
                    Stop("execute-outside-code",address,width);
                if(inBoot && address+(ulong)width > BootBase+bootLength)
                    Stop("execute-outside-code",address,width);
                if(inItcm && (address+(ulong)width > 0x40000 ||
                    (width == 4 && (!written[address+2] || !written[address+3]))))
                    Stop("execute-unwritten-itcm",address,width);
                address += (ulong)width;
            }
            if(pc < 0x40000) validatedBlocks[pc] = instructions;
        }

        private void Stop(string operation, ulong address, int width)
        {
            Violations++;
            LastOperation = operation;
            LastAddress = address;
            LastWidth = width;
            LastPC = cpu.PC.RawValue;
            throw new CpuAbortException($"BLACKWALL memory policy {operation} at 0x{address:x}, width {width}");
        }

        public int Violations { get; private set; }
        public string LastOperation { get; private set; }
        public ulong LastAddress { get; private set; }
        public ulong LastPC { get; private set; }
        public int LastWidth { get; private set; }
        public int WrittenBytes { get; private set; }
        private const ulong MainBase = 0x438000;
        private const ulong BootBase = 0x410000;
        private readonly IMachine machine;
        private readonly TranslationCPU cpu;
        private readonly MappedMemory main;
        private readonly MappedMemory itcm;
        private readonly ulong mainLength;
        private MappedMemory boot;
        private ulong bootLength;
        private readonly bool[] written = new bool[0x40000];
        private readonly Dictionary<ulong,uint> validatedBlocks = new Dictionary<ulong,uint>();
        private bool attached;
        private Action<uint> functionalRomGuard;
    }
}
