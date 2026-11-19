namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals.CPU;
    using Antmicro.Renode.Logging.Profiling;

    // Isolated entry probe. All guest writes remain in the RAM fixture.
    public sealed class BlackwallCodecIngress
    {
        public BlackwallCodecIngress(IMachine machine, TranslationCPU cpu, ulong mainLength,
            ulong entry, ulong target, ulong other, ulong initialization, uint length)
        {
            this.cpu = cpu;
            cpu.SetHookAtMemoryAccess((pc, operation, va, pa, width, value) =>
            {
                var size = (ulong)width;
                var write = operation == MemoryOperation.MemoryWrite || operation == MemoryOperation.MemoryIOWrite;
                var ram = pa >= 0x20000000 && pa + size <= 0x20080000;
                var rom = pa >= 0x438000 && pa + size <= 0x438000 + mainLength;
                if(write)
                {
                    Writes++;
                    if(!((pa >= 0x2000ef80 && pa + size <= 0x2000f000)
                        || (pa >= initialization && pa + size <= initialization + length)))
                        Fail("write outside stack/initialization", pa);
                }
                else if(!ram && !rom) Fail("read outside ROM/RAM", pa);
            });
            cpu.SetHookAtBlockBegin((pc, instructions) =>
            {
                if(pc < 0x438000 || pc + 4UL * instructions > 0x438000 + mainLength)
                    Fail("execute outside main", pc);
            });
            cpu.AddHook(target, (c, a) => Stop("codec-check-entry", a));
            cpu.AddHook(other, (c, a) => Stop("other-state-path", a));
            cpu.SetRegister(13, 0x2000f000U);
            cpu.SetRegister(14, 0xffffffffU);
            cpu.PC = (uint)(entry | 1);
        }

        private void Stop(string boundary, ulong address)
        {
            Boundary = boundary;
            Force = (uint)cpu.GetRegister(0).RawValue;
            cpu.IsHalted = true;
        }
        private void Fail(string reason, ulong address)
        {
            Violations++;
            throw new CpuAbortException("BLACKWALL codec policy " + reason + " at " + address);
        }
        public string Boundary { get; private set; } = "none";
        public uint Force { get; private set; }
        public int Writes { get; private set; }
        public int Violations { get; private set; }
        private readonly TranslationCPU cpu;
    }
}
