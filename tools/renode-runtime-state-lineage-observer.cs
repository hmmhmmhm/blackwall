namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System.Collections.Generic;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals.CPU;

    public sealed class BlackwallRuntimeStateLineageObserver
    {
        public BlackwallRuntimeStateLineageObserver(IMachine machine, CortexM cpu, uint slot)
        {
            foreach(var address in new uint[] {0x4fad8e, 0x4fad92, 0x4fadd2, 0x4fadd4})
            {
                cpu.AddHook(address, (c, pc) =>
                {
                    if(Rows.Count >= 16) { return; }
                    Rows.Add(new uint[] {
                        (uint)pc, (uint)cpu.GetRegister(0).RawValue,
                        (uint)cpu.GetRegister(1).RawValue, (uint)cpu.GetRegister(13).RawValue,
                        (uint)cpu.GetRegister(14).RawValue, machine.SystemBus.ReadDoubleWord(slot),
                        (uint)cpu.GetRegister(25).RawValue,
                        machine.SystemBus.ReadDoubleWord(0x200076b4),
                        machine.SystemBus.ReadByte(0x200076b8),
                        machine.SystemBus.ReadDoubleWord(0x2000690c),
                        machine.SystemBus.ReadDoubleWord(0x20006910),
                        machine.SystemBus.ReadByte(0x20006914),
                        machine.SystemBus.ReadWord(0x20006916),
                        machine.SystemBus.ReadDoubleWord(0x20052be0)
                    });
                });
            }
        }
        public List<uint[]> Rows {get;} = new List<uint[]>();
    }
}
