namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals.Bus;
    using Antmicro.Renode.Peripherals.Timers;
    using Antmicro.Renode.Time;

    public sealed class BlackwallApollo510Watchdog : BlackwallStrictMMIO
    {
        public BlackwallApollo510Watchdog(IMachine machine, BlackwallResetController resetController = null) : base(0x1000, 0x40024000)
        {
            this.machine = machine;
            this.resetController = resetController;
            counter = new LimitTimer(machine.ClockSource, 256, this, "Counter", 4096,
                Direction.Ascending, enabled: false, workMode: WorkMode.Periodic);
            interrupt = new LimitTimer(machine.ClockSource, 256, this, "Interrupt", 16,
                Direction.Ascending, enabled: false, workMode: WorkMode.OneShot, eventEnabled: true);
            resetRequest = new LimitTimer(machine.ClockSource, 256, this, "ResetRequest", 16,
                Direction.Ascending, enabled: false, workMode: WorkMode.OneShot, eventEnabled: true);
            IRQ = new GPIO();
            interrupt.LimitReached += () => { InterruptEvents++; pending = true; UpdateIRQ(); };
            resetRequest.LimitReached += () =>
            {
                ResetDue = true;
                ResetGatingEvaluated = resetController != null;
                ResetAllowedByGate = resetController != null && resetController.WatchdogResetEnabled;
                counter.Enabled = interrupt.Enabled = resetRequest.Enabled = false;
                machine.PauseAndRequestEmulationPause();
            };
            Reset();
        }

        public override void Reset()
        {
            base.Reset();
            Configuration = 0;
            Restarts = InterruptEvents = ConfigurationReads = ConfigurationWrites = 0;
            pending = interruptEnabled = ResetDue = false;
            ResetGatingEvaluated = ResetAllowedByGate = false;
            counter.Reset();
            interrupt.Reset();
            resetRequest.Reset();
            IRQ.Unset();
        }

        private bool Supported(uint value)
        {
            var clock = value >> 24;
            if((value & ~0x07ffff07u) != 0 || clock > 4) return false;
            if((value & 1) != 0 && clock != 0)
            {
                if((value & 2) != 0 && ((value >> 16) & 255) == 0) return false;
                if((value & 4) != 0 && ((value >> 8) & 255) == 0) return false;
            }
            // Active reconfiguration, including disable, needs a separate model.
            return (Configuration & 1) == 0 || value == Configuration;
        }

        private void RestartTimers()
        {
            var clock = Configuration >> 24;
            var frequency = new ulong[] { 16, 2048, 256, 16, 1 }[clock];
            counter.Enabled = interrupt.Enabled = resetRequest.Enabled = false;
            counter.Frequency = interrupt.Frequency = resetRequest.Frequency = frequency;
            interrupt.Limit = System.Math.Max(1ul, ((Configuration >> 16) & 255) * 16ul);
            resetRequest.Limit = System.Math.Max(1ul, ((Configuration >> 8) & 255) * 16ul);
            counter.ResetValue();
            interrupt.ResetValue();
            resetRequest.ResetValue();
            var running = (Configuration & 1) != 0 && clock != 0 && !ResetDue;
            counter.Enabled = running;
            interrupt.Enabled = running && (Configuration & 2) != 0;
            resetRequest.Enabled = running && (Configuration & 4) != 0;
        }

        private void SyncTime()
        {
            if(machine.GetSystemBus(this).TryGetCurrentCPU(out var cpu)) cpu.SyncTime();
        }

        private void UpdateIRQ() { IRQ.Set(pending && interruptEnabled); }

        public override uint ReadDoubleWord(long offset)
        {
            switch(offset)
            {
            case 0: ConfigurationReads++; return Configuration;
            case 4: return 0;
            case 0xc: SyncTime(); return (uint)(counter.Value / 16) & 255;
            case 0x200: return interruptEnabled ? 1u : 0;
            case 0x204: return pending ? 1u : 0;
            default: return base.ReadDoubleWord(offset);
            }
        }

        public override void WriteDoubleWord(long offset, uint value)
        {
            if(offset == 0 && Supported(value))
            {
                ConfigurationWrites++;
                if(value != Configuration)
                {
                    Configuration = value;
                    RestartTimers();
                }
                return;
            }
            if(offset == 4 && value == 0xb2)
            {
                Restarts++;
                RestartTimers();
                return;
            }
            if((offset == 0x200 || offset == 0x208 || offset == 0x20c) && value <= 1)
            {
                if(offset == 0x200) interruptEnabled = value != 0;
                if(offset == 0x208 && value != 0) pending = false;
                if(offset == 0x20c && value != 0) pending = true;
                UpdateIRQ();
                return;
            }
            base.WriteDoubleWord(offset, value);
        }

        public GPIO IRQ { get; }
        public uint Configuration { get; private set; }
        public int ConfigurationReads { get; private set; }
        public int ConfigurationWrites { get; private set; }
        public int Restarts { get; private set; }
        public int InterruptEvents { get; private set; }
        public bool ResetDue { get; private set; }
        public bool ResetGatingEvaluated { get; private set; }
        public bool ResetAllowedByGate { get; private set; }
        public bool InterruptPending => pending;
        public string SourceClock => "nominal LFRC=1024Hz hypothesis; sixteen timer substeps per counter tick";
        public string ResetPropagation => resetController == null
            ? "unsupported; pause at reset request threshold before RSTGEN gating"
            : "unsupported; evaluate WDREN gate and pause, no full-system reset";
        public bool HardwareVerified => false;
        private bool pending, interruptEnabled;
        private readonly IMachine machine;
        private readonly BlackwallResetController resetController;
        private readonly LimitTimer counter, interrupt, resetRequest;
    }
}
