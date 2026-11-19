namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    public sealed class BlackwallResetController : BlackwallStrictMMIO
    {
        public BlackwallResetController() : base(0x1000, 0x40000000) { Reset(); }
        public override void Reset()
        {
            base.Reset();
            Configuration = 0;
            ConfigurationReads = ConfigurationWrites = 0;
            PendingPorRequested=false;PendingPorPc=PendingPorPrimask=0;
        }
        public override uint ReadDoubleWord(long offset)
        {
            if(offset == 0) { ConfigurationReads++; return Configuration; }
            return base.ReadDoubleWord(offset);
        }
        public override void WriteDoubleWord(long offset, uint value)
        {
            if(pendingCpu!=null && offset==8 && value==0xd4)
            {
                PendingPorRequested=true;PendingPorPc=pendingCpu.PC.RawValue;
                PendingPorPrimask=pendingCpu.GetRegister(28).RawValue;
                pendingCpu.IsHalted=true;return;
            }
            if(offset == 0 && value <= 3)
            {
                ConfigurationWrites++;
                Configuration = value;
                return;
            }
            base.WriteDoubleWord(offset, value);
        }
        public uint Configuration { get; private set; }
        public void BindPendingPor(Antmicro.Renode.Peripherals.CPU.CortexM cpu)
        {
            if(cpu==null || pendingCpu!=null)throw new System.InvalidOperationException("Bind one virtual POR observer");
            pendingCpu=cpu;
        }
        public bool PendingPorRequested {get;private set;}
        public ulong PendingPorPc {get;private set;}
        public ulong PendingPorPrimask {get;private set;}
        private Antmicro.Renode.Peripherals.CPU.CortexM pendingCpu;
        public int ConfigurationReads { get; private set; }
        public int ConfigurationWrites { get; private set; }
        public bool WatchdogResetEnabled => (Configuration & 2) != 0;
        public bool HardwareVerified => false;
        public string ResetPropagation => "unsupported; CFG storage and watchdog gate only";
    }
}
