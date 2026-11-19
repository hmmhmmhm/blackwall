namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using System.Collections.Generic;
    using Antmicro.Renode.Peripherals.CPU;

    public sealed class BlackwallStackLimitObserver
    {
        public BlackwallStackLimitObserver(CortexM cpu, uint mainLength)
        {
            this.cpu = cpu;
            this.mainLength = mainLength;
        }

        public void AddPoint(string label, uint address, int sourceRegister)
        {
            if(String.IsNullOrEmpty(label) || sourceRegister < 0 || sourceRegister > 12 ||
               (address & 1) != 0 || address < 0x438000 ||
               (ulong)address >= 0x438000UL + mainLength || !addresses.Add(address))
                throw new ArgumentException("Invalid original stack-register observation point");
            cpu.AddHook(address, (c, a) => {
                Sequence++;
                if(events.Count == 4096) { events.Dequeue(); DroppedEvents++; }
                events.Enqueue(new BlackwallStackLimitEvent {
                    Sequence = Sequence, Label = label, PC = cpu.PC.RawValue,
                    Value = cpu.GetRegister(sourceRegister).RawValue,
                    SP = cpu.GetRegister(13).RawValue, LR = cpu.GetRegister(14).RawValue,
                    Control = cpu.GetRegister(18).RawValue, Xpsr = cpu.GetRegister(25).RawValue,
                    ProcessStackSelected = cpu.IsUsingProcessSP
                });
            });
        }

        public void AddEmptyPoint(uint address)
        {
            if((address & 1) != 0 || address < 0x438000 ||
               (ulong)address >= 0x438000UL + mainLength || !addresses.Add(address))
                throw new ArgumentException("Invalid empty stack observation point");
            cpu.AddHook(address, (c, a) => { });
        }

        public IEnumerable<BlackwallStackLimitEvent> Events => events;
        public ulong Sequence { get; private set; }
        public ulong DroppedEvents { get; private set; }
        private readonly CortexM cpu;
        private readonly uint mainLength;
        private readonly HashSet<uint> addresses = new HashSet<uint>();
        private readonly Queue<BlackwallStackLimitEvent> events = new Queue<BlackwallStackLimitEvent>();
    }

    public sealed class BlackwallStackLimitEvent
    {
        public ulong Sequence { get; set; }
        public string Label { get; set; }
        public ulong PC { get; set; }
        public ulong Value { get; set; }
        public ulong SP { get; set; }
        public ulong LR { get; set; }
        public ulong Control { get; set; }
        public ulong Xpsr { get; set; }
        public bool ProcessStackSelected { get; set; }
    }
}
