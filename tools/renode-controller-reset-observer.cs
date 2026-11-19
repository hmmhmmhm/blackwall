namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using System.Collections.Generic;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals.CPU;

    public sealed class BlackwallControllerResetObserver
    {
        public BlackwallControllerResetObserver(IMachine machine,CortexM cpu,BlackwallGpioOutputLatch output,BlackwallEm9305ResetHypothesis reset)
        {
            output.OutputWritten+=(pin,high)=>{
                if(pin!=93 && pin!=149)return;
                if(Rows.Count>=128){Overflow=true;return;}
                var peer=reset.HciPeer;
                Rows.Add(new ulong[]{machine.ElapsedVirtualTime.TimeElapsed.Ticks,(ulong)cpu.PC.RawValue,(ulong)cpu.GetRegister(14).RawValue,
                    (ulong)pin,high?1UL:0UL,reset.Held?1UL:0UL,reset.Released?1UL:0UL,reset.AssertedAt,reset.ReleasedAt,
                    (ulong)peer.Frames,(ulong)peer.CommandsAccepted,(ulong)peer.Replies,peer.CsKnown?1UL:0UL,peer.CsHigh?1UL:0UL});
                States.Add(peer.State);Phases.Add(reset.Phase);
            };
        }
        public List<ulong[]> Rows {get;}=new List<ulong[]>();
        public List<string> States {get;}=new List<string>();
        public List<string> Phases {get;}=new List<string>();
        public bool Overflow {get;private set;}
    }
}
