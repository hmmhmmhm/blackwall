namespace Antmicro.Renode.Peripherals.Miscellaneous
{
using System;
using System.Collections.Generic;
using Antmicro.Renode.Core;
using Antmicro.Renode.Peripherals.I2C;
using Antmicro.Renode.Peripherals.CPU;
using Antmicro.Renode.Peripherals.Timers;
using Antmicro.Renode.Time;

public sealed class BlackwallPmicWatchdogModel:Antmicro.Renode.Peripherals.IPeripheral
{
    public BlackwallPmicWatchdogModel(IMachine machine,Action warning,Action resetRequest)
    {
        warn=new LimitTimer(machine.ClockSource,500,this,"PmicWarning",1,Direction.Ascending,enabled:false,workMode:WorkMode.OneShot,eventEnabled:true);
        expiry=new LimitTimer(machine.ClockSource,500,this,"PmicExpiry",2,Direction.Ascending,enabled:false,workMode:WorkMode.OneShot,eventEnabled:true);
        warn.LimitReached+=()=> {Warnings++;warning();};
        expiry.LimitReached+=()=> {Running=false;ResetRequested=true;ResetRequests++;warn.Enabled=false;resetRequest();};
        Reset();
    }
    public void Reset()
    {
        warn.Reset();expiry.Reset();ConfigKnown=TargetKnown=Running=ResetRequested=false;
        Config=0;Target=0;staged=null;Starts=Stops=Kicks=Strobes=Warnings=ResetRequests=0;
    }
    public bool StageTarget(byte[] value)
    {
        if(Running || ResetRequested || value==null || value.Length!=3)return false;
        staged=(byte[])value.Clone();return true;
    }
    public bool Write(int address,byte value)
    {
        if(address==0x705)
        {
            if(Running || ResetRequested || value!=0x0a)return false;
            Config=value;ConfigKnown=true;return true;
        }
        if(address!=0x700 && address!=0x701 && address!=0x703 && address!=0x704)return false;
        if(value==0)return true;
        if(value!=1 || ResetRequested)return false;
        if(address==0x701) {warn.Enabled=expiry.Enabled=false;Running=false;Stops++;return true;}
        if(address==0x703)
        {
            if(Running || !ConfigKnown || staged==null)return false;
            uint next=(uint)((staged[0]<<16)|(staged[1]<<8)|staged[2]);
            if(next<2)return false;
            Target=next;TargetKnown=true;Strobes++;return true;
        }
        if(address==0x700)
        {
            if(Running || !ConfigKnown || !TargetKnown)return false;
            Starts++;Running=true;Arm();return true;
        }
        if(!Running)return false;
        Kicks++;Arm();return true;
    }
    private void Arm()
    {
        warn.Enabled=expiry.Enabled=false;
        warn.Limit=Target-1;expiry.Limit=Target;
        warn.ResetValue();expiry.ResetValue();warn.Enabled=expiry.Enabled=true;
    }
    public byte[] Read(int address,int count,int holeMock)
    {
        if(address==0x705 && count==1 && ConfigKnown)return new byte[]{Config};
        if(address==0x708 && count==3 && staged!=null)return (byte[])staged.Clone();
        // The recovery guard ignores these two bytes. Filling them requires a separate explicit mock.
        if(address==0x705 && count==6 && ConfigKnown && staged!=null && holeMock==0)
            return new byte[]{Config,0,0,staged[0],staged[1],staged[2]};
        return null;
    }
    public bool ConfigKnown {get;private set;}
    public bool TargetKnown {get;private set;}
    public byte Config {get;private set;}
    public uint Target {get;private set;}
    public bool Running {get;private set;}
    public bool ResetRequested {get;private set;}
    public int Starts {get;private set;} public int Stops {get;private set;} public int Kicks {get;private set;}
    public int Strobes {get;private set;} public int Warnings {get;private set;} public int ResetRequests {get;private set;}
    private byte[] staged;
    private readonly LimitTimer warn,expiry;
}

public sealed class BlackwallPmicTimedProbe:II2CPeripheral
{
    public BlackwallPmicTimedProbe(IMachine machine,string timerProfile,int recoveryReadHoleMock=-1,string vbusState=null,string adcState=null,string scratchState=null,int scratch0InitialMock=-1,string measurementProfile=null,int vbatCode=-1,int ibatCode=-1,int sharedResultBitsZeroMock=-1,int ntcCode=-1,int dieTempCode=-1,int vsysCode=-1,string resultResetProfile=null,int vbusCode=-1,string chargerStatusProfile=null,string buckState=null,string ldswState=null,string vbusStatusProfile=null)
    {
        if(timerProfile!="fast-reset-stopped" || (recoveryReadHoleMock!=-1 && recoveryReadHoleMock!=0))
            throw new ArgumentException("Explicit stopped fast watchdog profile and optional zero-hole mock required");
        this.machine=machine;RecoveryReadHoleMock=recoveryReadHoleMock;
        Inner=new BlackwallPmicRestoreProbe("source-reset-readonly","explicit-idle","guest-storage","guest-storage",vbusState,adcState,scratchState,scratch0InitialMock,chargerStatusProfile,buckState,ldswState,vbusStatusProfile);
        Timer=new BlackwallPmicWatchdogModel(machine,()=>Inner.LatchVirtualWatchdogWarning(),Expired);
        if(measurementProfile!=null)
        {
            if(adcState!="source-reset-storage")throw new ArgumentException("Explicit source-reset ADC config required");
            if(measurementProfile=="discharging-vbat-ibat-fixture")
            {
                if(ntcCode!=-1 || dieTempCode!=-1 || vsysCode!=-1 || resultResetProfile!=null || vbusCode!=-1)throw new ArgumentException("Queued samples require queued profile");
                AdcConversion=new BlackwallPmicAdcConversion(machine,vbatCode,ibatCode,250,sharedResultBitsZeroMock,Inner.LatchVirtualAdcEvent);Inner.AdcBackend=AdcConversion;
            }
            else if(measurementProfile=="queued-six-channel-fixture")
            {
                if(sharedResultBitsZeroMock!=-1)throw new ArgumentException("Use explicit queued result reset profile");
                QueuedAdc=new BlackwallPmicQueuedAdc(machine,new int[]{vbatCode,ntcCode,ibatCode,dieTempCode,vsysCode,vbusCode},resultResetProfile,Inner.LatchVirtualAdcEvent);Inner.AdcBackend=QueuedAdc;Inner.ContinuousTransactions=true;
            }
            else throw new ArgumentException("Unknown measurement profile");
        }
        else if(vbatCode!=-1 || ibatCode!=-1 || sharedResultBitsZeroMock!=-1 || ntcCode!=-1 || dieTempCode!=-1 || vsysCode!=-1 || resultResetProfile!=null || vbusCode!=-1)throw new ArgumentException("Measurement fixture must be selected");
        Reset();
    }
    public void Reset()
    {
        if(AdcConversion!=null)AdcConversion.Reset();if(QueuedAdc!=null)QueuedAdc.Reset();
        Inner.Reset();Timer.Reset();frame.Clear();delegated=reading=false;readWindow=null;readOffset=0;Pointer=-1;
        TimerWrites=TimerReads=Stops=RepeatedStarts=0;ownAccesses=0;lastWasOwn=false;lastAddress=lastValue=0;lastWidth=0;lastOperation="none";
    }
    private void Expired()
    {
        ownAccesses++;lastWasOwn=true;lastAddress=0x700;lastWidth=0;lastValue=0;lastOperation="pmic-watchdog-reset-request";
        machine.PauseAndRequestEmulationPause();
    }
    private void Block(string operation,int width,ulong value=0)
    {
        ownAccesses++;lastWasOwn=true;lastAddress=Pointer<0 ? 0ul : (ulong)Pointer;lastWidth=width;lastValue=value;lastOperation=operation;
        throw new CpuAbortException("Blackwall PMIC timer unsupported "+operation);
    }
    public void Write(byte[] data)
    {
        if(data==null || data.Length==0 || reading || delegated) {Block("timer-frame-state",data==null ? 0 : data.Length);return;}
        if(frame.Count==0 && data[0]!=7)
        {
            try {Inner.Write(data);} catch(CpuAbortException) {lastWasOwn=false;throw;}
            Pointer=-1;delegated=true;return;
        }
        if(frame.Count+data.Length>5) {Block("timer-frame-too-long",data.Length);return;}
        var next=new List<byte>(frame);next.AddRange(data);
        if(next[0]!=7 || (next.Count>=2 && !TimerAddress(next[1]))) {Block("timer-register-unknown",data.Length);return;}
        if(next.Count>=2 && next.Count>(next[1]==8 ? 5 : 3)) {Block("timer-frame-length",next.Count);return;}
        frame.Clear();frame.AddRange(next);
    }
    private bool TimerAddress(byte offset)=>offset==0 || offset==1 || offset==3 || offset==4 || offset==5 || offset==6 || offset==7 || offset==8;
    public byte[] Read(int count=1)
    {
        if(delegated) {return ReadInner(count);}
        if(reading)
        {
            if(readWindow==null || count<=0 || readOffset+count>readWindow.Length) {Block("timer-read-overlap",count);return null;}
            var tail=new byte[count];Array.Copy(readWindow,readOffset,tail,0,count);readOffset+=count;TimerReads++;return tail;
        }
        if(frame.Count!=0)
        {
            if(frame.Count!=2) {Block("timer-read-incomplete-frame",count);return null;}
            Pointer=0x700+frame[1];frame.Clear();RepeatedStarts++;
        }
        if(Pointer<0) {delegated=true;return ReadInner(count);}
        byte[] result;
        if(Pointer==0x705 && count==4 && RecoveryReadHoleMock==0)
        {
            readWindow=Timer.Read(Pointer,6,RecoveryReadHoleMock);
            result=readWindow==null ? null : new byte[4];
            if(result!=null) {Array.Copy(readWindow,result,4);readOffset=4;}
        }
        else result=Timer.Read(Pointer,count,RecoveryReadHoleMock);
        if(result==null) {Block("timer-read-unknown",count);return null;}
        reading=true;TimerReads++;return result;
    }
    private byte[] ReadInner(int count)
    {
        try {return Inner.Read(count);} catch(CpuAbortException) {lastWasOwn=false;throw;}
    }
    public void FinishTransmission()
    {
        if(delegated)
        {
            try {Inner.FinishTransmission();} catch(CpuAbortException) {lastWasOwn=false;throw;}
            delegated=false;Stops++;return;
        }
        if(reading) {reading=false;readWindow=null;readOffset=0;Stops++;return;}
        if(frame.Count<2) {Block("timer-stop-incomplete-frame",frame.Count);return;}
        int address=0x700+frame[1];
        if(frame.Count==2) {Pointer=address;frame.Clear();Stops++;return;}
        bool accepted=address==0x708 && frame.Count==5
            ? Timer.StageTarget(new byte[]{frame[2],frame[3],frame[4]})
            : frame.Count==3 && address!=0x708 && Timer.Write(address,frame[2]);
        if(!accepted) {Block("timer-write-unsupported",frame.Count,(ulong)address);return;}
        Pointer=address;frame.Clear();TimerWrites++;Stops++;
    }
    public BlackwallPmicQueuedAdc QueuedAdc {get;}
    public BlackwallPmicAdcConversion AdcConversion {get;}
    public BlackwallPmicRestoreProbe Inner {get;}
    public BlackwallPmicWatchdogModel Timer {get;}
    public int RecoveryReadHoleMock {get;}
    public int Pointer {get;private set;}
    public int TimerWrites {get;private set;} public int TimerReads {get;private set;}
    public int Stops {get;private set;} public int RepeatedStarts {get;private set;}
    public int AccessCount=>ownAccesses+Inner.AccessCount;
    public ulong LastAddress=>lastWasOwn ? lastAddress : Inner.LastAddress;
    public int LastWidth=>lastWasOwn ? lastWidth : Inner.LastWidth;
    public ulong LastValue=>lastWasOwn ? lastValue : Inner.LastValue;
    public string LastOperation=>lastWasOwn ? lastOperation : Inner.LastOperation;
    private readonly IMachine machine;
    private readonly List<byte> frame=new List<byte>();
    private byte[] readWindow;
    private int readOffset;
    private bool delegated,reading,lastWasOwn;
    private int ownAccesses,lastWidth;
    private ulong lastAddress,lastValue;
    private string lastOperation;
}
}

namespace Antmicro.Renode.Peripherals.Miscellaneous
{
using System;
using Antmicro.Renode.Core;
using Antmicro.Renode.Peripherals.Timers;
using Antmicro.Renode.Time;
// Explicit raw sample fixture; nominal virtual conversion time is not measured hardware timing.
public sealed class BlackwallPmicAdcConversion:IBlackwallPmicAdcBackend,Antmicro.Renode.Peripherals.IPeripheral
{
    public BlackwallPmicAdcConversion(IMachine machine,int vbatCode,int ibatCode,uint conversionMicroseconds,int sharedBitsZeroMock,Action<byte> complete)
    {
        if(complete==null || vbatCode<0 || vbatCode>1023 || ibatCode<0 || ibatCode>1023 || conversionMicroseconds==0 || conversionMicroseconds>1000000 || (sharedBitsZeroMock!=-1 && sharedBitsZeroMock!=0))throw new ArgumentException("Explicit raw10 samples, bounded conversion time and optional zero-bit mock required");
        VbatCode=vbatCode;IbatCode=ibatCode;ConversionMicroseconds=conversionMicroseconds;SharedBitsZeroMock=sharedBitsZeroMock;this.complete=complete;
        voltage=new LimitTimer(machine.ClockSource,1000000,this,"PmicVbatConversion",conversionMicroseconds,Direction.Ascending,enabled:false,workMode:WorkMode.OneShot,eventEnabled:true);
        current=new LimitTimer(machine.ClockSource,1000000,this,"PmicIbatConversion",conversionMicroseconds,Direction.Ascending,enabled:false,workMode:WorkMode.OneShot,eventEnabled:true);
        voltage.LimitReached+=VoltageDone;current.LimitReached+=CurrentDone;Reset();
    }
    public void Reset()
    {
        voltage.Reset();current.Reset();Array.Clear(values,0,values.Length);Array.Clear(masks,0,masks.Length);
        if(SharedBitsZeroMock==0) {masks[5]=0xfc;masks[10]=0xcf;}
        Phase="idle";Requests=RepeatedDrops=VbatCompletions=IbatCompletions=0;paired=false;
    }
    public bool SupportsResultStream=>false;
    public bool OwnsTask(int address)=>address==0x500;
    public bool TaskAt(int address,byte trigger,byte config,byte ibatEnable)=>OwnsTask(address) && Task(trigger,config,ibatEnable);
    public bool CanWriteConfiguration(int address,byte value)=>Phase=="idle" && (address!=0x509 || value==0);
    public bool Task(byte trigger,byte config,byte ibatEnable)
    {
        if(trigger==0)return true;
        if(trigger!=1 || config!=0 || ibatEnable>1)return false; // Burst and automatic scheduling require separate models.
        if(Phase=="ibat")return false; // A queued alternate request is outside this bounded subset.
        if(Phase=="vbat") {if(paired!=(ibatEnable==1))return false;RepeatedDrops++;return true;}
        paired=ibatEnable==1;Requests++;Phase="vbat";voltage.ResetValue();voltage.Enabled=true;return true;
    }
    private void Set(int address,byte value) {values[address-0x510]=value;masks[address-0x510]=255;}
    private void Merge(int address,byte mask,byte value)
    {
        int n=address-0x510;values[n]=(byte)((values[n]&~mask)|(value&mask));masks[n]|=mask;
    }
    private void VoltageDone()
    {
        Set(0x511,(byte)(VbatCode>>2));Merge(0x515,3,(byte)(VbatCode&3));VbatCompletions++;
        Phase=paired ? "ibat" : "idle";
        if(paired) {current.ResetValue();current.Enabled=true;}
        complete(1);
    }
    private void CurrentDone()
    {
        Set(0x518,(byte)(IbatCode>>2));Merge(0x51a,0x30,(byte)((IbatCode&3)<<4));
        Set(0x510,4); // Declared discharging/valid fixture, not a sensed charging state.
        IbatCompletions++;Phase="idle";complete(0x40);
    }
    public byte[] Read(int address,int count)
    {
        if(count<1 || count>11 || address<0x510 || address>0x51a || count>0x51b-address)return null;
        for(int i=0;i<count;i++)if(masks[address-0x510+i]!=255)return null;
        var result=new byte[count];Array.Copy(values,address-0x510,result,0,count);return result;
    }
    public int VbatCode {get;} public int IbatCode {get;} public uint ConversionMicroseconds {get;} public int SharedBitsZeroMock {get;}
    public string Phase {get;private set;} public int Requests {get;private set;} public int RepeatedDrops {get;private set;}
    public int VbatCompletions {get;private set;} public int IbatCompletions {get;private set;}
    public ulong VbatTicks=>voltage.Value;public ulong IbatTicks=>current.Value;
    public byte[] Values=>(byte[])values.Clone(); public byte[] KnownMasks=>(byte[])masks.Clone();
    private readonly byte[] values=new byte[11],masks=new byte[11];private bool paired;
    private readonly LimitTimer voltage,current;private readonly Action<byte> complete;
}
}

namespace Antmicro.Renode.Peripherals.Miscellaneous
{
using System;using System.Collections.Generic;
using Antmicro.Renode.Core;using Antmicro.Renode.Peripherals.Timers;using Antmicro.Renode.Time;
public sealed class BlackwallPmicQueuedAdc:IBlackwallPmicAdcBackend,Antmicro.Renode.Peripherals.IPeripheral
{
    public BlackwallPmicQueuedAdc(IMachine machine,int[] raw,string resultResetProfile,Action<byte> complete)
    {
        if(raw==null || raw.Length!=6 || complete==null || (resultResetProfile!=null && resultResetProfile!="source-reset"))throw new ArgumentException("Explicit six raw10 samples and optional source-reset results required");
        foreach(var sample in raw)if(sample<0 || sample>1023)throw new ArgumentException("Raw sample out of range");
        samples=(int[])raw.Clone();ResultResetProfile=resultResetProfile;this.complete=complete;
        timer=new LimitTimer(machine.ClockSource,1000000,this,"PmicQueuedConversion",250,Direction.Ascending,enabled:false,workMode:WorkMode.OneShot,eventEnabled:true);
        timer.LimitReached+=Done;Reset();
    }
    public void Reset()
    {
        timer.Reset();Array.Clear(values,0,11);Array.Clear(masks,0,11);Array.Clear(pending,0,6);Array.Clear(completed,0,6);
        if(ResultResetProfile=="source-reset")for(int i=0;i<11;i++)masks[i]=255;
        active=-1;Requests=RepeatedDrops=AutomaticIbatRequests=0;paired=false;queuedPair=false;order.Clear();
    }
    public bool SupportsResultStream=>true;
    public bool OwnsTask(int address)=>(address>=0x500 && address<=0x503) || address==0x507;
    public bool CanWriteConfiguration(int address,byte value)=>active<0 && PendingMask==0 && (address!=0x509 || value==0);
    public bool Task(byte trigger,byte config,byte ibatEnable)=>TaskAt(0x500,trigger,config,ibatEnable);
    public bool TaskAt(int address,byte trigger,byte config,byte ibatEnable)
    {
        if(!OwnsTask(address))return false;if(trigger==0)return true;
        if(trigger!=1 || config!=0 || ibatEnable>1)return false;
        int channel=address==0x500 ? 0 : address==0x501 ? 1 : address==0x502 ? 3 : address==0x503 ? 4 : 5;
        if(active==channel || pending[channel]) {RepeatedDrops++;return true;}
        pending[channel]=true;if(channel==0)queuedPair=ibatEnable==1;Requests++;StartNext();return true;
    }
    private void StartNext()
    {
        if(active>=0)return;
        for(int i=0;i<6;i++)if(pending[i])
        {
            pending[i]=false;active=i;if(i==0)paired=queuedPair;timer.ResetValue();timer.Enabled=true;return;
        }
    }
    private void Set(int address,byte value) {values[address-0x510]=value;masks[address-0x510]=255;}
    private void Merge(int address,byte mask,byte value) {int n=address-0x510;values[n]=(byte)((values[n]&~mask)|(value&mask));masks[n]|=mask;}
    private void Done()
    {
        int channel=active;if(channel<0)throw new InvalidOperationException("No active conversion");
        int raw=samples[channel];int[] msb={0x511,0x512,0x518,0x513,0x514,0x519};int[] shifts={0,2,4,4,6,6};byte[] events={1,2,0x40,4,8,0x80};
        Set(msb[channel],(byte)(raw>>2));Merge((channel==2 || channel==5) ? 0x51a : 0x515,(byte)(3<<shifts[channel]),(byte)((raw&3)<<shifts[channel]));
        if(channel==2)Set(0x510,4);
        completed[channel]++;if(order.Count==64)order.RemoveAt(0);order.Add(channel);
        if(channel==0 && paired) {if(!pending[2]) {pending[2]=true;AutomaticIbatRequests++;}}
        active=-1;StartNext();complete(events[channel]);
    }
    public byte[] Read(int address,int count)
    {
        if(count<1 || count>11 || address<0x510 || address>0x51a || count>0x51b-address)return null;
        for(int i=0;i<count;i++)if(masks[address-0x510+i]!=255)return null;
        var result=new byte[count];Array.Copy(values,address-0x510,result,0,count);return result;
    }
    public int PendingMask {get {int result=0;for(int i=0;i<6;i++)if(pending[i])result|=1<<i;return result;}}
    public string Active=>active<0 ? "idle" : new string[]{"vbat","ntc","ibat","die","vsys","vbus"}[active];
    public string ResultResetProfile {get;}public int Requests {get;private set;}public int RepeatedDrops {get;private set;}public int AutomaticIbatRequests {get;private set;}
    public int[] Samples=>(int[])samples.Clone();public int[] Completed=>(int[])completed.Clone();public int[] CompletionOrder=>order.ToArray();
    public byte[] Values=>(byte[])values.Clone();public byte[] KnownMasks=>(byte[])masks.Clone();
    private readonly int[] samples,completed=new int[6];private readonly bool[] pending=new bool[6];private int active;private bool paired,queuedPair;
    private readonly byte[] values=new byte[11],masks=new byte[11];private readonly List<int> order=new List<int>();private readonly LimitTimer timer;private readonly Action<byte> complete;
}
}
