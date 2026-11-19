namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals;
    using Antmicro.Renode.Peripherals.Timers;
    using Antmicro.Renode.Time;

    public sealed class BlackwallRtcAdapter : BlackwallStrictMMIO, IBlackwallRtc
    {
        public BlackwallRtcAdapter(IMachine machine,bool halLowUpperWrites=false,bool independentWeekday=false) : base(0x400,0x40004800)
        {
            if(independentWeekday && !halLowUpperWrites) throw new ArgumentException("Independent weekday requires explicit counter-write profile");
            this.machine=machine; CounterWritesProfile=halLowUpperWrites;
            IndependentWeekday=independentWeekday;
            engine=new BlackwallRtcEngine(machine); Reset();
        }
        public bool Owns(ulong address) => address>=0x40004800 && address<0x40004c00;
        public override void Reset()
        {
            base.Reset(); engine.Reset(); engine.SetDateTime(2000,1,1,0,0,0,0);
            Reads=Writes=Commits=LateReads=0; pendingLow=false; readPair=false;
            pendingWord=upperSnapshot=alarmUpper=0; LastError="none";
            weekdayLatched=false; WeekdayMismatches=0;
        }
        public override uint ReadDoubleWord(long offset)
        {
            if(!Known(offset)) return BlockRead(offset,"unknown-register");
            if(offset==0x208 || offset==0x20c) return BlockRead(offset,"interrupt-action-read-unmodeled");
            if(!InCentury()) return BlockRead(offset,"century-range-unmodeled");
            if(offset==0x20)
            {
                if(pendingLow) return BlockRead(offset,"counter-write-pending");
                var low=engine.ReadDoubleWord(0x20);
                upperSnapshot=(engine.ReadDoubleWord(0x24)&0x7fffffffu)^0x10000000u;
                if(IndependentWeekday && weekdayLatched)
                    upperSnapshot=(upperSnapshot&~0x07000000u)|((uint)CurrentWeekday<<24);
                pairStarted=Now; readPair=true; Reads++; return low;
            }
            if(offset==0x24)
            {
                if(pendingLow || !readPair) return BlockRead(offset,"counter-pair-required");
                var late=Now-pairStarted>=10*TimeInterval.TicksPerMillisecond;
                var value=upperSnapshot|(late ? 0x80000000u : 0);
                readPair=false; if(late) LateReads++; Reads++; return value;
            }
            Reads++;
            if(offset==4) return pendingLow ? 1u : 0u;
            if(offset==0x34) return alarmUpper;
            return engine.ReadDoubleWord(offset);
        }
        public override void WriteDoubleWord(long offset,uint value)
        {
            if(!Known(offset)) { BlockWrite(offset,value,"unknown-register"); return; }
            if(!InCentury()) { BlockWrite(offset,value,"century-range-unmodeled"); return; }
            if(offset==4 || offset==0x204) { BlockWrite(offset,value,"read-only-or-unmodeled-write"); return; }
            if(offset==0)
            {
                var rpt=(value>>1)&7;
                if((value&~0x1fu)!=0 || (rpt!=0 && rpt!=7)) { BlockWrite(offset,value,"control-field-unmodeled"); return; }
                if(pendingLow && value!=engine.ReadDoubleWord(0)) { BlockWrite(offset,value,"unfinished-counter-write"); return; }
                engine.WriteDoubleWord(offset,value); Writes++; return;
            }
            if(offset==0x20)
            {
                if(!CounterWritesProfile || (engine.ReadDoubleWord(0)&1)==0 || pendingLow || !ValidLow(value))
                { BlockWrite(offset,value,"counter-low-precondition"); return; }
                pendingWord=value; pendingLow=true; Writes++; return;
            }
            if(offset==0x24)
            {
                DateTime date;
                if(!CounterWritesProfile || !pendingLow || !TryDate(pendingWord,value,out date))
                { BlockWrite(offset,value,"counter-upper-precondition"); return; }
                engine.SetDateTime(date.Year,date.Month,date.Day,date.Hour,date.Minute,date.Second,date.Millisecond/10);
                if(IndependentWeekday)
                {
                    weekdayAnchor=date.Date; weekdayValue=(int)((value>>24)&7); weekdayLatched=true;
                    if(weekdayValue!=(int)date.DayOfWeek) WeekdayMismatches++;
                }
                pendingLow=false; readPair=false; Commits++; Writes++; return;
            }
            if(offset==0x30)
            {
                if(!ValidLow(value)) { BlockWrite(offset,value,"alarm-value-unmodeled"); return; }
                engine.WriteDoubleWord(offset,value); Writes++; return;
            }
            if(offset==0x34)
            {
                // Zero is a disabled alarm reset value; do not feed invalid zero month/day to DateTime.
                if(value==0 && ((engine.ReadDoubleWord(0)>>1)&7)==0) { alarmUpper=0; Writes++; return; }
                if((value&~0x71f3fu)!=0 || Bcd(value&63)<1 || Bcd(value&63)>31 || Bcd((value>>8)&31)<1 || Bcd((value>>8)&31)>12 || ((value>>16)&7)>6)
                { BlockWrite(offset,value,"alarm-upper-unmodeled"); return; }
                engine.WriteDoubleWord(offset,value); alarmUpper=value; Writes++; return;
            }
            if((value&~1u)!=0) { BlockWrite(offset,value,"interrupt-field-unmodeled"); return; }
            engine.WriteDoubleWord(offset,value); Writes++;
        }
        private uint BlockRead(long offset,string error) { LastError=error; return base.ReadDoubleWord(offset); }
        private void BlockWrite(long offset,uint value,string error) { LastError=error; base.WriteDoubleWord(offset,value); }
        private static bool Known(long o) => o==0 || o==4 || o==0x20 || o==0x24 || o==0x30 || o==0x34 || o==0x200 || o==0x204 || o==0x208 || o==0x20c;
        private static int Bcd(uint value) => (value&15)>9 || ((value>>4)&15)>9 ? -1 : (int)((value>>4)*10+(value&15));
        private static bool ValidLow(uint value) => (value&~0x3f7f7fffu)==0 && Bcd(value&255)>=0 && Bcd(value&255)<=99 && Bcd((value>>8)&127)>=0 && Bcd((value>>8)&127)<=59 && Bcd((value>>16)&127)>=0 && Bcd((value>>16)&127)<=59 && Bcd((value>>24)&63)>=0 && Bcd((value>>24)&63)<=23;
        private bool TryDate(uint low,uint upper,out DateTime date)
        {
            date=default(DateTime);
            if((upper&~0x17ff1f3fu)!=0 || (upper&0x10000000u)==0 || !ValidLow(low)) return false;
            var yy=Bcd((upper>>16)&255); var month=Bcd((upper>>8)&31); var day=Bcd(upper&63); var weekday=(upper>>24)&7;
            if(yy<0 || month<1 || month>12 || day<1 || day>DateTime.DaysInMonth(2000+yy,month) || weekday>6) return false;
            date=new DateTime(2000+yy,month,day,Bcd((low>>24)&63),Bcd((low>>16)&127),Bcd((low>>8)&127),Bcd(low&255)*10);
            return IndependentWeekday || weekday==(uint)date.DayOfWeek;
        }
        private bool InCentury() => engine.CurrentDateTime.Year>=2000 && engine.CurrentDateTime.Year<=2099;
        private ulong Now => machine.ElapsedVirtualTime.TimeElapsed.Ticks;
        public GPIO IRQ => engine.IRQ;
        public bool CounterWritesProfile { get; }
        public bool IndependentWeekday { get; }
        public int WeekdayMismatches { get; private set; }
        public int CurrentWeekday => IndependentWeekday && weekdayLatched
            ? (((weekdayValue+(int)(engine.CurrentDateTime.Date-weekdayAnchor).TotalDays)%7)+7)%7
            : (int)engine.CurrentDateTime.DayOfWeek;
        public uint Control => engine.ReadDoubleWord(0);
        public bool WritePending => pendingLow;
        public bool PairPending => readPair;
        public ulong VirtualTicks => Now;
        public string VirtualDate => engine.CurrentDateTime.ToString("yyyy-MM-ddTHH:mm:ss.ff");
        public string LastError { get; private set; }
        public int Reads { get; private set; }
        public int Writes { get; private set; }
        public int Commits { get; private set; }
        public int LateReads { get; private set; }
        private readonly IMachine machine;
        private readonly BlackwallRtcEngine engine;
        private bool pendingLow,readPair;
        private uint pendingWord,upperSnapshot,alarmUpper;
        private ulong pairStarted;
        private bool weekdayLatched;
        private DateTime weekdayAnchor;
        private int weekdayValue;
    }
}
