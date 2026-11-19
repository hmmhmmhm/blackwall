namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals;
    using Antmicro.Renode.Peripherals.Timers;
    using Antmicro.Renode.Time;

    // Fixed active-high INT1 profile; pulse duration is declared, not measured silicon timing.
    public sealed class BlackwallImuInt1Gpio : IPeripheral, IGPIOReceiver
    {
        public BlackwallImuInt1Gpio(IMachine machine,BlackwallG2StartupFixture owner,int interruptConfiguration,int pulseMicroseconds=8)
        {
            if(machine==null || owner==null || owner.GpioConfig==null || owner.GpioInterrupts==null || !owner.GpioInterrupts.RuntimePin38)
                throw new ArgumentException("Configured GPIO owner with explicit pin38 input required");
            if(interruptConfiguration<0 || interruptConfiguration>255 || ((interruptConfiguration&7)!=1 && (interruptConfiguration&7)!=3) ||
               (pulseMicroseconds!=8 && pulseMicroseconds!=100) || ((interruptConfiguration&2)!=0 && pulseMicroseconds!=8))
                throw new ArgumentException("Explicit active-high push-pull pulse/latch profile and supported minimum pulse duration required");
            this.owner=owner;
            InterruptConfiguration=interruptConfiguration;PulseMicroseconds=pulseMicroseconds;
            timer=new LimitTimer(machine.ClockSource,1000000,this,"imu-int1-pulse",(ulong)pulseMicroseconds,Direction.Ascending,enabled:false,workMode:WorkMode.OneShot,eventEnabled:true);
            timer.LimitReached+=()=>Drive(false);
        }

        public void OnGPIO(int number,bool value)
        {
            if(number!=0)throw new ArgumentException("INT1 connection uses input zero");
            if(High==value)return;
            High=value;
            if(PulseMode)
            {
                if(!value)return;
                Drive(true);timer.ResetValue();timer.Enabled=true;
                return;
            }
            Drive(value);
        }

        private void Drive(bool value)
        {
            if(PinHigh==value)return;
            uint pad;
            var configured=!value || (owner.GpioConfig.Values.TryGetValue(0x40010098,out pad) && pad==0x93);
            if(owner.GpioInterrupts.TrySetPin38(value,configured))AcceptedTransitions++;
            else RejectedTransitions++;
            PinHigh=value;
        }

        public void Reset()
        {
            timer.Enabled=false;owner.GpioInterrupts.TrySetPin38(false,true);
            High=PinHigh=false;AcceptedTransitions=RejectedTransitions=0;
        }

        public bool High {get;private set;}
        public bool PinHigh {get;private set;}
        public int InterruptConfiguration {get;}
        public int PulseMicroseconds {get;}
        public bool PulseMode => (InterruptConfiguration&2)==0;
        public int AcceptedTransitions {get;private set;}
        public int RejectedTransitions {get;private set;}
        private readonly BlackwallG2StartupFixture owner;
        private readonly LimitTimer timer;
    }
}
