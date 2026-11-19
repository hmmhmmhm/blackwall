namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals.Timers;
    // Shared engine; optional Timer7 requires the explicit PWM engine candidate.
    public sealed class BlackwallTimer14 : IBlackwallTimer14
    {
        public BlackwallTimer14(IMachine machine,string profile,string timer0Profile="none",string timer7Profile="none")
        {
            if(profile!="nominal-xt-lfrc")throw new ArgumentException("Explicit Timer14 profile required");
            if(timer0Profile!="none" && timer0Profile!="nominal-hfrc96-upcount")throw new ArgumentException("Explicit nominal Timer0 profile required");
            Timer0Enabled=timer0Profile!="none";
            if(timer7Profile!="none" && timer7Profile!="nominal-hfrc96-pwm")throw new ArgumentException("Explicit nominal Timer7 profile required");
            Timer7Enabled=timer7Profile!="none";
            engine=new BlackwallApolloTimerEngine(machine);Reset();
        }
        public bool Owns(ulong a)=>a==0x40008010 || (a>=0x40008060 && a<=0x4000806c && (a&3)==0) || (a>=0x400083c0 && a<=0x400083d0 && (a&3)==0) || (Timer0Enabled && a>=0x40008200 && a<=0x40008210 && (a&3)==0) || (Timer7Enabled && (a==0x40008110 || (a>=0x400082e0 && a<=0x400082f0 && (a&3)==0)));
        public bool TryRead(ulong a,out uint value)
        {
            value=0;if(!Owns(a) || a==0x40008068 || a==0x4000806c)return false;
            value=a==0x400083c0 ? Control : a==0x40008200 ? Timer0Control : a==0x400082e0 ? Timer7Control : a==0x40008110 ? Timer7OutputConfig : engine.ReadDoubleWord((long)(a-0x40008000));Reads++;return true;
        }
        public bool TryWrite(ulong a,uint value)
        {
            if(!Owns(a))return false;
            var offset=(long)(a-0x40008000);
            if(Timer7Enabled && offset==0x110)
            {
                if((value&~0x7f00u)!=(Timer7OutputConfig&~0x7f00u) || (((value>>8)&0x7f)!=14 && ((value>>8)&0x7f)!=63))return false;
                Timer7OutputConfig=value;Writes++;return true;
            }
            if(Timer7Enabled && offset>=0x2e0 && offset<=0x2f0)
            {
                if(!TryWriteTimer7(offset,value))return false;
                Writes++;return true;
            }
            if(Timer0Enabled && offset>=0x200 && offset<=0x210)
            {
                if(!TryWriteTimer0(offset,value))return false;
                Writes++;return true;
            }
            if(offset==0x3c0)
            {
                var clock=(value>>8)&0x1ff;var fn=(value>>4)&15;
                if(value!=0 && ((value&~0x1ff13u)!=0 || fn!=1 || (clock!=6 && clock!=10)))return false;
                if((value&1)!=0 && !Timer14ConfigurationValid)return false;
                if(Running && clock!=((Control>>8)&0x1ff) && (value&3)!=2 && (value&3)!=3)return false;
                Control=value;
                var effective=value&~2u;if((value&2)!=0)effective&=~1u;
                engine.WriteDoubleWord(offset,effective);
                if((value&2)!=0)engine.WriteDoubleWord(0x3c4,0);
            }
            else if(offset==0x3c4)
            {
                if(Running || (Control&2)!=0)return false;
                engine.WriteDoubleWord(offset,value);
            }
            else if(offset==0x3c8)
            {
                if(Running && value!=0xffffffffu)return false;
                engine.WriteDoubleWord(offset,value);
            }
            else if(offset==0x3cc)
            {
                if(Running && value==0)return false;
                engine.WriteDoubleWord(offset,value);
            }
            else if(offset==0x3d0)
            {if(value!=0)return false;engine.WriteDoubleWord(offset,0);}
            else if(offset==0x10)
            {
                var mask=0x4000u | (Timer0Enabled ? 1u:0u) | (Timer7Enabled ? 0x80u:0u);
                if((value&~mask)!=(0xffffu&~mask))return false;
                if(Timer0Enabled && (value&1)!=0 && (Timer0Control&3)==1 && !Timer0ConfigurationValid)return false;
                if((value&0x4000)!=0 && (Control&3)==1 && !Timer14ConfigurationValid)return false;
                if(Timer7Enabled && (value&0x80)!=0 && (Timer7Control&3)==1 && !Timer7ConfigurationValid)return false;
                engine.WriteDoubleWord(offset,value);
            }
            else
            {var mask=0x30000000u | (Timer0Enabled ? 3u:0u) | (Timer7Enabled ? 0xc000u:0u);if((value&~mask)!=0 || offset==0x64)return false;engine.WriteDoubleWord(offset,value);}
            Writes++;return true;
        }
        private bool TryWriteTimer0(long offset,uint value)
        {
            if(offset==0x200)
            {
                if(value!=0 && (value<0x120 || value>0x123))return false;
                if(value==0 && Timer0Running)return false;
                if((value&1)!=0 && !Timer0ConfigurationValid)return false;
                Timer0Control=value;
                var effective=value&~2u;if((value&2)!=0)effective&=~1u;
                engine.WriteDoubleWord(offset,effective);
                if((value&2)!=0)engine.WriteDoubleWord(0x204,0);
                return true;
            }
            if(offset==0x204) {if(Timer0Running || (Timer0Control&2)!=0)return false;}
            else if(offset==0x208) {if((value!=0 && value!=6000) || (Timer0Running && value!=6000))return false;}
            else if(offset==0x20c) {if((value!=0 && value!=0xffffffff) || (Timer0Running && value!=0xffffffff))return false;}
            else if(offset==0x210) {if((value!=0 && value!=0x100) || (Timer0Running && value!=Timer0Mode))return false;}
            else return false;
            engine.WriteDoubleWord(offset,value);return true;
        }
        private bool TryWriteTimer7(long offset,uint value)
        {
            if(offset==0x2e0)
            {
                if(value!=0 && (value<0x40 || value>0x43))return false;
                if(value==0 && Timer7Running)return false;
                if((value&3)==1 && !Timer7ConfigurationValid)return false;
                Timer7Control=value;
                var effective=value&~2u;if((value&2)!=0)effective&=~1u;
                engine.WriteDoubleWord(offset,effective);
                if((value&2)!=0)engine.WriteDoubleWord(0x2e4,0);
                return true;
            }
            if(offset==0x2e4) {if(Timer7Running || (Timer7Control&2)!=0)return false;}
            else if(offset==0x2e8) {if(Timer7Running && value!=Timer7Compare0)return false;}
            else if(offset==0x2ec) {if(Timer7Running && value!=Timer7Compare1)return false;}
            else if(offset==0x2f0) {if((value!=0 && value!=0x100) || (Timer7Running && value!=Timer7Mode))return false;}
            else return false;
            engine.WriteDoubleWord(offset,value);return true;
        }
        public void Reset() {engine.Reset();Control=Timer0Control=Timer7Control=0;Timer7OutputConfig=0x3f3f3f3f;Reads=Writes=0;}
        private bool Timer7ConfigurationValid=>Timer7Compare0>0 && Timer7Compare0<0xffffffffu && Timer7Compare1>0 && Timer7Compare1<Timer7Compare0 && Timer7Mode==0x100 && Timer7Counter<Timer7Compare0;
        public bool Timer7Enabled {get;}
        public uint Timer7Control {get;private set;}
        public uint Timer7Counter=>engine.ReadDoubleWord(0x2e4);
        public uint Timer7Compare0=>engine.ReadDoubleWord(0x2e8);
        public uint Timer7Compare1=>engine.ReadDoubleWord(0x2ec);
        public uint Timer7Mode=>engine.ReadDoubleWord(0x2f0);
        public uint Timer7OutputConfig {get;private set;}
        public uint Timer7Pad145Selector=>(Timer7OutputConfig>>8)&0x7f;
        public bool Timer7Running=>(Timer7Control&3)==1 && (GlobalEnable&0x80)!=0;
        // Sampled logical phase only; no physical pin/electrical signal is modeled.
        public bool Timer7Output0=>Timer7Running && Timer7Counter>=Timer7Compare1;
        public bool Timer7Output1=>Timer7Running && !Timer7Output0;
        public ulong Timer7Frequency=>((Timer7Control>>4)&15)==4 ? 24000000UL:0UL;
        public GPIO Timer7IRQ=>(GPIO)engine.Connections[7];
        private bool Timer0ConfigurationValid=>Timer0Compare0==6000 && Timer0Compare1==0xffffffff && Timer0Mode==0x100;
        private bool Timer14ConfigurationValid=>Compare0==0xffffffffu && Compare1!=0;
        public bool Timer0Enabled {get;}
        public uint Timer0Control {get;private set;}
        public uint Timer0Counter=>engine.ReadDoubleWord(0x204);
        public uint Timer0Compare0=>engine.ReadDoubleWord(0x208);
        public uint Timer0Compare1=>engine.ReadDoubleWord(0x20c);
        public uint Timer0Mode=>engine.ReadDoubleWord(0x210);
        public bool Timer0Running=>(Timer0Control&3)==1 && (GlobalEnable&1)!=0;
        public ulong Timer0Frequency=>((Timer0Control>>8)&0x1ff)==1 ? 6000000UL:0UL;
        public GPIO Timer0IRQ=>(GPIO)engine.Connections[0];
        public uint Control {get;private set;}
        public uint Counter=>engine.ReadDoubleWord(0x3c4);
        public uint Compare0=>engine.ReadDoubleWord(0x3c8);
        public uint Compare1=>engine.ReadDoubleWord(0x3cc);
        public uint GlobalEnable=>engine.ReadDoubleWord(0x10);
        public uint Enable=>engine.ReadDoubleWord(0x60);
        public uint Status=>engine.ReadDoubleWord(0x64);
        public ulong Frequency=>((Control>>8)&0x1ff)==6 ? 900UL : ((Control>>8)&0x1ff)==10 ? 32768UL : 0UL;
        public bool Running=>(Control&3)==1 && (GlobalEnable&0x4000)!=0;
        public GPIO IRQ=>(GPIO)engine.Connections[14];
        public uint Reads {get;private set;}
        public uint Writes {get;private set;}
        private readonly BlackwallApolloTimerEngine engine;
    }
}
