namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using System.Collections.Generic;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals.CPU;
    public sealed class BlackwallNorErrorObserver
    {
        public BlackwallNorErrorObserver(IMachine machine, CortexM cpu, BlackwallMspi1PioReset pio,
            uint slot, uint[] sites, bool firstEraseOnly=false)
        {
            if(sites == null || sites.Length != 5) throw new ArgumentException("Five original return sites required");
            for(uint n=0; n<sites.Length; n++)
            {
                var kind=n;
                cpu.AddHook(sites[n], (c, pc) =>
                {
                    if(firstEraseOnly && (Completed || pio.SectorEraseStarts==0)) return;
                    if(Rows.Count >= 256) { Overflow=true; return; }
                    Rows.Add(new uint[] {kind,(uint)pc,(uint)cpu.GetRegister(0).RawValue,
                        (uint)cpu.GetRegister(13).RawValue,(uint)cpu.GetRegister(14).RawValue,
                        machine.SystemBus.ReadDoubleWord(slot),(uint)cpu.GetRegister(25).RawValue,
                        firstEraseOnly ? pio.SectorEraseStarts : pio.PageProgramStarts,
                        firstEraseOnly ? pio.SectorEraseCompletions : pio.PageProgramCompletions,
                        firstEraseOnly ? 0 : pio.HeldProgramCompletions});
                    if(firstEraseOnly && kind==4) Completed=true;
                });
            }
        }
        public bool Overflow {get;private set;}
        public bool Completed {get;private set;}
        public List<uint[]> Rows {get;} = new List<uint[]>();
    }
}
