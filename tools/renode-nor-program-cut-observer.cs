namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using System.Collections.Generic;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals.CPU;

    public sealed class BlackwallNorProgramCutObserver
    {
        public BlackwallNorProgramCutObserver(IMachine machine, CortexM cpu,
            BlackwallMspi1PioReset pio, uint statusReturn, uint stopProgram)
        {
            if(pio == null || stopProgram > 7) throw new ArgumentException("Explicit kvTime program boundary required");
            InitialStarts = pio.PageProgramStarts;
            InitialCompletions = pio.PageProgramCompletions;
            InitialBytes = pio.ProgramBytesCommitted;
            uint last = InitialStarts;
            cpu.AddHook(statusReturn, (c, pc) =>
            {
                if(Stopped || !pio.ProgramBusy || pio.PageProgramStarts == last) return;
                last = pio.PageProgramStarts;
                Rows.Add(new uint[] {last - InitialStarts,
                    pio.PageProgramCompletions - InitialCompletions,
                    pio.ProgramBytesCommitted - InitialBytes, pio.LastProgramAddress,
                    (uint)pc, (uint)cpu.GetRegister(0).RawValue,
                    (uint)cpu.GetRegister(13).RawValue, (uint)cpu.GetRegister(25).RawValue});
                if(stopProgram != 0 && last - InitialStarts == stopProgram)
                {
                    Stopped = true;
                    machine.Pause();
                }
            });
        }
        public uint InitialStarts {get;}
        public uint InitialCompletions {get;}
        public uint InitialBytes {get;}
        public bool Stopped {get;private set;}
        public List<uint[]> Rows {get;} = new List<uint[]>();
    }
}
