namespace Antmicro.Renode.Peripherals.Miscellaneous
{
using System;
using System.Collections.Generic;
using Antmicro.Renode.Peripherals.I2C;
using Antmicro.Renode.Peripherals.CPU;
    public interface IBlackwallPmicAdcBackend
    {
        bool CanWriteConfiguration(int address,byte value);
        bool SupportsResultStream {get;}
        bool OwnsTask(int address);
        bool TaskAt(int address,byte trigger,byte config,byte ibatEnable);
        bool Task(byte trigger,byte config,byte ibatEnable);
        byte[] Read(int address,int count);
    }
    // Declared startup state with optional digital register banks, not an analog PMIC model.
    public sealed class BlackwallPmicRestoreProbe : II2CPeripheral
    {
        public BlackwallPmicRestoreProbe(string profile,string interruptState=null,string gpioState=null,string chargerState=null,string vbusState=null,string adcState=null,string scratchState=null,int scratch0InitialMock=-1,string chargerStatusProfile=null,string buckState=null,string ldswState=null,string vbusStatusProfile=null)
        {
            if(profile!="source-reset-readonly") throw new ArgumentException("Explicit PMIC restore profile required");
            if(interruptState!=null && interruptState!="explicit-idle") throw new ArgumentException("Explicit interrupt state required");
            if(gpioState!=null && gpioState!="guest-storage") throw new ArgumentException("Explicit GPIO storage required");
            if(chargerState!=null && chargerState!="guest-storage") throw new ArgumentException("Explicit charger storage required");
            if(vbusState!=null && vbusState!="guest-storage") throw new ArgumentException("Explicit VBUS storage required");
            if(adcState!=null && adcState!="guest-storage" && adcState!="source-reset-storage") throw new ArgumentException("Explicit PMIC ADC storage required");
            if(scratchState!=null && scratchState!="guest-storage") throw new ArgumentException("Explicit scratch storage required");
            if((scratch0InitialMock!=-1 && scratch0InitialMock!=0) || (scratchState==null && scratch0InitialMock!=-1)) throw new ArgumentException("Explicit zero scratch0 fixture or unknown required");
            if(chargerStatusProfile!=null && chargerStatusProfile!="source-reset-snapshot" && chargerStatusProfile!="battery-detected-idle-snapshot")throw new ArgumentException("Explicit charger status snapshot required");
            ChargerStatusProfile=chargerStatusProfile;
            if(vbusStatusProfile!=null && vbusStatusProfile!="test-vbus-absent" && vbusStatusProfile!="test-vbus-present")throw new ArgumentException("Explicit test-only VBUS status snapshot required");
            VbusStatusProfile=vbusStatusProfile;
            if(buckState!=null && buckState!="guest-storage" && buckState!="source-reset-storage")throw new ArgumentException("Explicit BUCK storage required");
            BuckState=buckState;
            if(ldswState!=null && ldswState!="guest-storage" && ldswState!="source-reset-storage")throw new ArgumentException("Explicit LDSW storage required");
            LdswState=ldswState;
            GuestScratchStorage=scratchState!=null;Scratch0InitialMock=scratch0InitialMock;
            AdcSourceReset=adcState=="source-reset-storage";
            GuestAdcStorage=adcState!=null;
            GuestVbusStorage=vbusState!=null;
            GuestChargerStorage=chargerState!=null;
            GuestGpioStorage=gpioState!=null;
            InterruptRegistersEnabled=interruptState!=null;
            Reset();
        }
        public void Reset()
        {
            Pointer=-1; PointerWrites=DataReads=Finishes=AccessCount=ReturnedBytes=RegisterWrites=GpioWrites=ChargerWrites=ChargerTransactions=0;
            Array.Clear(scratchValues,0,2);Array.Clear(scratchMasks,0,2);ScratchWrites=0;if(Scratch0InitialMock==0)scratchMasks[0]=255;
            adcReadWindow=null;adcReadOffset=0;readPayloads.Clear();adcResultAddresses.Clear();adcResultPayloads.Clear();AdcResultReads=AdcResultBytes=0;
            ChargerStatusReads=ChargerStatusBytes=0;chargerStatusReadAddresses.Clear();chargerStatusReadPayloads.Clear();
            buck.Reset(BuckState=="source-reset-storage");
            ldsw.Reset(LdswState=="source-reset-storage");
            adcConfig.Clear();adcConfig[0x509]=0;adcConfig[0x50a]=1;AdcConfigWrites=AdcAutoUpdateWrites=AdcAutoUpdateRequests=0;AdcAutoUpdateLastRequest=0;
            if(AdcSourceReset) {adcConfig[0x50b]=3;adcConfig[0x50d]=0;adcConfig[0x524]=0;}
            VbusCurrentKnown=VbusSuspendKnown=false;VbusCurrent=VbusSuspend=0;VbusWrites=VbusApplyRequests=0;
            VbusStatusReads=0;
            LastAddress=LastValue=0; LastWidth=0; LastOperation="none";pending=false;
            readAddresses.Clear();readValues.Clear();writeAddresses.Clear();writeValues.Clear();
            Array.Clear(events,0,events.Length);Array.Clear(enables,0,enables.Length);
            Array.Clear(gpioKnown,0,gpioKnown.Length);Array.Clear(gpioValues,0,gpioValues.Length);charger.Reset();
        }
        private void Block(string operation,int width,ulong value=0)
        {
            AccessCount++;LastAddress=Pointer<0 ? 0ul : (ulong)Pointer;LastWidth=width;
            LastOperation=operation;LastValue=value;
            throw new CpuAbortException("Blackwall PMIC restore unsupported "+operation);
        }
        private int InterruptGroup(int address)
        {
            if(!InterruptRegistersEnabled)return -1;
            for(var i=0;i<groupBases.Length;i++)if(address>=groupBases[i] && address<groupBases[i]+4)return i;
            return -1;
        }
        private int GpioIndex(int address)=>GuestGpioStorage && address>=0x600 && address<0x61e ? address-0x600 : -1;
        private byte[] Value(int address)
        {
            if(LdswState!=null && ldsw.Owns(address))return ldsw.Read(address,1);
            if(BuckState!=null && buck.Owns(address))return buck.Read(address,1);
            if(IsChargerStatus(address))return ReadChargerStatus(address,1);
            if(address==0x207 && VbusStatusProfile!=null)return new byte[]{(byte)VbusStatusValue};
            if(AdcBackend!=null && address>=0x510 && address<=0x51a)return AdcBackend.Read(address,1);
            if(GuestScratchStorage && (address==0xe01 || address==0xe02))return scratchMasks[address-0xe01]==255 ? new byte[]{scratchValues[address-0xe01]} : null;
            if(GuestAdcStorage && AdcMask(address)>=0)return adcConfig.TryGetValue(address,out var adcValue) ? new byte[]{adcValue} : null;
            if(GuestVbusStorage && address==0x201)return VbusCurrentKnown ? new byte[]{VbusCurrent} : null;
            if(GuestVbusStorage && address==0x203)return VbusSuspendKnown ? new byte[]{VbusSuspend} : null;
            if(GuestChargerStorage && charger.Owns(address))return charger.Read(address,address==0x308 || address==0x30a ? 2 : 1);
            var gpio=GpioIndex(address);
            if(gpio>=0)return gpioKnown[gpio] ? new byte[]{gpioValues[gpio]} : null;
            var group=InterruptGroup(address);
            if(group>=0)
            {
                var op=address-groupBases[group];
                if(op==0)return new byte[]{events[group]};
                if(op==2)return new byte[]{enables[group]};
                return null;
            }
            switch(address)
            {
                case 0x0509:return new byte[]{0};
                case 0x050a:return new byte[]{1};
                case 0x0308:return new byte[]{8,0};
                case 0x030a:return new byte[]{0xcf,1};
                case 0x0b04:return new byte[]{3};
                default:return null;
            }
        }
        public void Write(byte[] data)
        {
            var address=data!=null && data.Length>=2 ? (data[0]<<8)|data[1] : -1;
            var group=InterruptGroup(address);
            var gpio=GpioIndex(address);
            var chargerWrite=GuestChargerStorage && data!=null && data.Length>=3 && data.Length<=4 && charger.Owns(address);
            var buckWrite=BuckState!=null && data!=null && data.Length>=3 && data.Length<=10 && buck.Owns(address);
            var ldswWrite=LdswState!=null && data!=null && data.Length>=3 && data.Length<=7 && ldsw.Owns(address);
            var vbusWrite=GuestVbusStorage && data!=null && data.Length==3 && (address==0x200 || address==0x201 || address==0x203);
            var adcWrite=GuestAdcStorage && data!=null && data.Length==3 && AdcMask(address)>=0;
            var scratchWrite=GuestScratchStorage && data!=null && data.Length==3 && (address==0xe01 || address==0xe02);
            var adcAutoWrite=AdcSourceReset && data!=null && data.Length==3 && address==0x50c;
            var adcMeasureWrite=AdcBackend!=null && data!=null && data.Length==3 && AdcBackend.OwnsTask(address);
            var registerWrite=ldswWrite || buckWrite || adcMeasureWrite || adcAutoWrite || scratchWrite || adcWrite || vbusWrite || chargerWrite || (data!=null && data.Length==3 && (group>=0 || gpio>=0));
            if(pending || data==null || (!registerWrite && (data.Length!=2 || Value(address)==null)) || (registerWrite && !ContinuousTransactions && writeAddresses.Count+(chargerWrite || buckWrite || ldswWrite ? data.Length-2 : 1)>64))
            {
                Block("peer-write-unsupported",data==null ? 0 : data.Length,address<0 ? 0ul : (ulong)address);return;
            }
            if(ldswWrite)
            {
                var values=new byte[data.Length-2];Array.Copy(data,2,values,0,values.Length);
                if(!ldsw.TryWrite(address,values)) {Block("ldsw-config-unsupported",data.Length,(ulong)address);return;}
                for(var i=0;i<values.Length;i++)RecordWrite(address+i,values[i]);
                RegisterWrites+=values.Length;Pointer=address;pending=true;return;
            }
            if(buckWrite)
            {
                var values=new byte[data.Length-2];Array.Copy(data,2,values,0,values.Length);
                if(!buck.TryWrite(address,values)) {Block("buck-config-unsupported",data.Length,(ulong)address);return;}
                for(var i=0;i<values.Length;i++)RecordWrite(address+i,values[i]);
                RegisterWrites+=values.Length;Pointer=address;pending=true;return;
            }
            if(AdcBackend!=null && (adcWrite || adcAutoWrite) && !AdcBackend.CanWriteConfiguration(address,data[2])) {Block("pmic-adc-config-unmodeled",3,(ulong)address);return;}
            if(adcMeasureWrite)
            {
                byte config,ibat;
                if(!adcConfig.TryGetValue(0x509,out config) || !adcConfig.TryGetValue(0x524,out ibat) || !AdcBackend.TaskAt(address,data[2],config,ibat)) {Block("pmic-adc-measure-unmodeled",3,(ulong)address);return;}
                RegisterWrites++;RecordWrite(address,data[2]);Pointer=address;pending=true;return;
            }
            if(adcAutoWrite)
            {
                if(data[2]>1 || (data[2]==1 && !adcConfig.ContainsKey(0x50b))) {Block("pmic-adc-auto-update-unsupported",3,(ulong)address);return;}
                if(data[2]==1) {AdcAutoUpdateRequests++;AdcAutoUpdateLastRequest=adcConfig[0x50b];}
                AdcAutoUpdateWrites++;RegisterWrites++;RecordWrite(address,data[2]);Pointer=address;pending=true;return;
            }
            if(scratchWrite)
            {
                var index=address-0xe01;
                if(index==0 && (data[2]&1)!=0) {Block("boot-monitor-enable-unmodeled",3,(ulong)address);return;}
                scratchValues[index]=data[2];scratchMasks[index]|=(byte)(index==0 ? 254 : 255);
                ScratchWrites++;RegisterWrites++;RecordWrite(address,data[2]);Pointer=address;pending=true;return;
            }
            if(adcWrite)
            {
                if((data[2]&~AdcMask(address))!=0) {Block("pmic-adc-config-unsupported",3,(ulong)address);return;}
                adcConfig[address]=data[2];AdcConfigWrites++;RegisterWrites++;
                RecordWrite(address,data[2]);Pointer=address;pending=true;return;
            }
            if(vbusWrite)
            {
                byte value=data[2];
                bool valid=address==0x201 ? (value==0 || value==1 || (value>=5 && value<=15))
                    : address==0x203 ? value<=1 : (value==0 || (value==1 && VbusCurrentKnown));
                if(!valid) {Block("vbus-config-unsupported",3,(ulong)address);return;}
                if(address==0x201) {VbusCurrent=value;VbusCurrentKnown=true;}
                else if(address==0x203) {VbusSuspend=value;VbusSuspendKnown=true;}
                else if(value==1) VbusApplyRequests++;
                VbusWrites++;RegisterWrites++;RecordWrite(address,value);
                Pointer=address;pending=true;return;
            }
            if(chargerWrite)
            {
                var values=new byte[data.Length-2];Array.Copy(data,2,values,0,values.Length);
                if(!charger.TryWrite(address,values)) {Block("charger-config-unsupported",data.Length,(ulong)address);return;}
                for(var i=0;i<values.Length;i++) {RecordWrite(address+i,values[i]);}
                ChargerWrites+=values.Length;ChargerTransactions++;RegisterWrites+=values.Length;
                Pointer=address;pending=true;return;
            }
            if(registerWrite && gpio>=0)
            {
                var mask=gpio<5 ? 15 : 1;
                if((data[2]&~mask)!=0 || (gpio<5 && data[2]>9)) {Block("gpio-config-unsupported",3,(ulong)address);return;}
                gpioValues[gpio]=data[2];gpioKnown[gpio]=true;GpioWrites++;
                RecordWrite(address,data[2]);RegisterWrites++;
                Pointer=address;pending=true;return;
            }
            if(registerWrite)
            {
                var bits=(byte)(data[2]&groupMasks[group]);
                switch(address-groupBases[group])
                {
                    case 0:events[group]|=bits;break;
                    case 1:events[group]&=(byte)~bits;break;
                    case 2:enables[group]|=bits;break;
                    case 3:enables[group]&=(byte)~bits;break;
                }
                RecordWrite(address,data[2]);RegisterWrites++;
                Pointer=address;pending=true;return;
            }
            Pointer=address;PointerWrites++;pending=true;
        }
        public byte[] Read(int count=1)
        {
            if(pending && adcReadWindow!=null)
            {
                if(count<1 || count>adcReadWindow.Length-adcReadOffset) {Block("pmic-adc-stream-unmodeled",count,(ulong)(Pointer+adcReadOffset));return null;}
                var part=new byte[count];Array.Copy(adcReadWindow,adcReadOffset,part,0,count);
                RecordRead(Pointer+adcReadOffset,part);adcReadOffset+=count;return part;
            }
            var value=LdswState!=null && ldsw.Owns(Pointer) ? ldsw.Read(Pointer,count) : BuckState!=null && buck.Owns(Pointer) ? buck.Read(Pointer,count) : IsChargerStatus(Pointer) ? ReadChargerStatus(Pointer,count) : AdcBackend!=null && Pointer>=0x510 && Pointer<=0x51a ? AdcBackend.Read(Pointer,count) : GuestChargerStorage && charger.Owns(Pointer) ? charger.Read(Pointer,count) : Value(Pointer);
            if(pending || value==null || count!=value.Length || (!ContinuousTransactions && readAddresses.Count>=(InterruptRegistersEnabled ? 64 : 16)))
            {Block("peer-read-unsupported",count);return null;}
            if(AdcBackend!=null && AdcBackend.SupportsResultStream && Pointer>=0x510 && Pointer<=0x51a)
            {adcReadWindow=AdcBackend.Read(Pointer,0x51b-Pointer) ?? (byte[])value.Clone();adcReadOffset=count;}
            pending=true;RecordRead(Pointer,value);return value;
        }
        private void RecordRead(int address,byte[] value)
        {
            if(address==0x207 && VbusStatusProfile!=null)VbusStatusReads++;
            if(IsChargerStatus(address))
            {
                ChargerStatusReads++;ChargerStatusBytes+=value.Length;
                if(chargerStatusReadAddresses.Count==64) {chargerStatusReadAddresses.RemoveAt(0);chargerStatusReadPayloads.RemoveAt(0);}
                chargerStatusReadAddresses.Add(address);chargerStatusReadPayloads.Add(BitConverter.ToString(value));
            }
            if(ContinuousTransactions && readAddresses.Count>=64) {readAddresses.RemoveAt(0);readValues.RemoveAt(0);readPayloads.RemoveAt(0);}
            if(address>=0x510 && address<=0x51a)
            {
                AdcResultReads++;AdcResultBytes+=value.Length;
                if(adcResultAddresses.Count==64) {adcResultAddresses.RemoveAt(0);adcResultPayloads.RemoveAt(0);}
                adcResultAddresses.Add(address);adcResultPayloads.Add(BitConverter.ToString(value));
            }
            DataReads++;ReturnedBytes+=value.Length;readAddresses.Add(address);readValues.Add(value.Length==1 ? value[0] : value[0]|(value[1]<<8));readPayloads.Add(BitConverter.ToString(value));
        }
        private void RecordWrite(int address,int value)
        {
            if(ContinuousTransactions && writeAddresses.Count>=64) {writeAddresses.RemoveAt(0);writeValues.RemoveAt(0);}
            writeAddresses.Add(address);writeValues.Add(value);
        }
        public void FinishTransmission()
        {
            if(!pending) {Block("peer-finish-without-transaction",0);return;}
            pending=false;if(adcReadWindow!=null)Pointer+=adcReadOffset;adcReadWindow=null;adcReadOffset=0;Finishes++;
        }
        internal bool ContinuousTransactions {get;set;}
        private byte[] adcReadWindow;private int adcReadOffset;
        private readonly List<string> readPayloads=new List<string>();
        public string[] ReadPayloads=>readPayloads.ToArray();
        private readonly List<int> adcResultAddresses=new List<int>();private readonly List<string> adcResultPayloads=new List<string>();
        public int AdcResultReads {get;private set;}public int AdcResultBytes {get;private set;}
        public int[] AdcResultAddresses=>adcResultAddresses.ToArray();public string[] AdcResultPayloads=>adcResultPayloads.ToArray();
        internal IBlackwallPmicAdcBackend AdcBackend {get;set;}
        internal void LatchVirtualAdcEvent(byte bits)
        {
            if(!InterruptRegistersEnabled || (bits&~0xcf)!=0)throw new InvalidOperationException("Explicit ADC event bank required");
            events[0]|=bits;
        }
        internal void LatchVirtualWatchdogWarning()
        {
            if(!InterruptRegistersEnabled)throw new InvalidOperationException("Explicit event registers required");
            events[4]|=8;
        }
        private readonly byte[] scratchValues=new byte[2],scratchMasks=new byte[2];
        public bool GuestScratchStorage {get;}
        public int Scratch0InitialMock {get;}
        public int ScratchWrites {get;private set;}
        public byte[] ScratchValues=>(byte[])scratchValues.Clone();
        public byte[] ScratchKnownMasks=>(byte[])scratchMasks.Clone();
        private static int AdcMask(int address)
        {
            switch(address) {case 0x509:case 0x50a:return 3;case 0x50b:return 15;case 0x50d:return 255;case 0x524:return 1;default:return -1;}
        }
        private readonly SortedDictionary<int,byte> adcConfig=new SortedDictionary<int,byte>();
        public bool GuestAdcStorage {get;}
        public bool AdcSourceReset {get;}
        public int AdcAutoUpdateWrites {get;private set;}
        public int AdcAutoUpdateRequests {get;private set;}
        public byte AdcAutoUpdateLastRequest {get;private set;}
        public int AdcConfigWrites {get;private set;}
        public int[] AdcConfigAddresses {get {var result=new List<int>();foreach(var pair in adcConfig)result.Add(pair.Key);return result.ToArray();}}
        public int[] AdcConfigValues {get {var result=new List<int>();foreach(var pair in adcConfig)result.Add(pair.Value);return result.ToArray();}}
        public bool GuestVbusStorage {get;}
        public bool VbusCurrentKnown {get;private set;}
        public bool VbusSuspendKnown {get;private set;}
        public byte VbusCurrent {get;private set;}
        public byte VbusSuspend {get;private set;}
        public int VbusWrites {get;private set;}
        public int VbusApplyRequests {get;private set;}
        public string VbusStatusProfile {get;}
        public int VbusStatusValue=>VbusStatusProfile==null ? -1 : VbusStatusProfile=="test-vbus-present" ? 1 : 0;
        public int VbusStatusReads {get;private set;}
        public bool GuestChargerStorage {get;}
        public string BuckState {get;}
        public string LdswState {get;}
        public int[] LdswKnownAddresses=>LdswState==null ? new int[0] : ldsw.KnownAddresses;
        public int[] LdswKnownValues=>LdswState==null ? new int[0] : ldsw.KnownValues;
        public int LdswConfigWrites=>ldsw.ConfigWrites;
        public int LdswTaskWrites=>ldsw.TaskWrites;
        public int[] LdswTaskRequests=>ldsw.TaskRequests;
        public int[] BuckKnownAddresses=>BuckState==null ? new int[0] : buck.KnownAddresses;
        public int[] BuckKnownValues=>BuckState==null ? new int[0] : buck.KnownValues;
        public int BuckConfigWrites=>buck.ConfigWrites;
        public int BuckTaskWrites=>buck.TaskWrites;
        public int[] BuckTaskRequests=>buck.TaskRequests;
        public string ChargerStatusProfile {get;}
        private bool IsChargerStatus(int address)=>ChargerStatusProfile!=null && Array.IndexOf(chargerStatusAddresses,address)>=0;
        private byte[] ReadChargerStatus(int address,int count)
        {
            if(count<1 || count>3)return null;
            var result=new byte[count];
            for(var i=0;i<count;i++)
            {
                if(!IsChargerStatus(address+i))return null;
                if(address+i==0x334 && ChargerStatusProfile=="battery-detected-idle-snapshot")result[i]=1;
            }
            return result;
        }
        private static readonly int[] chargerStatusAddresses={0x32d,0x332,0x333,0x334,0x336,0x337};
        public int[] ChargerStatusAddresses=>ChargerStatusProfile==null ? new int[0] : (int[])chargerStatusAddresses.Clone();
        public byte[] ChargerStatusValues=>ChargerStatusProfile==null ? new byte[0] : new byte[]{0,0,0,(byte)(ChargerStatusProfile=="battery-detected-idle-snapshot" ? 1 : 0),0,0};
        public int ChargerStatusReads {get;private set;}public int ChargerStatusBytes {get;private set;}
        private readonly List<int> chargerStatusReadAddresses=new List<int>();private readonly List<string> chargerStatusReadPayloads=new List<string>();
        public int[] ChargerStatusReadAddresses=>chargerStatusReadAddresses.ToArray();public string[] ChargerStatusReadPayloads=>chargerStatusReadPayloads.ToArray();
        public int ChargerWrites {get;private set;}
        public int ChargerTransactions {get;private set;}
        public int[] ChargerKnownAddresses=>GuestChargerStorage ? charger.KnownAddresses : new int[0];
        public int[] ChargerKnownValues=>GuestChargerStorage ? charger.KnownValues : new int[0];
        public int[] ChargerAliasKnownMasks=>GuestChargerStorage ? charger.AliasKnownMasks : new int[0];
        public bool GuestGpioStorage {get;}
        public int GpioWrites {get;private set;}
        public int[] GpioKnownAddresses
        {
            get { var result=new List<int>();for(var i=0;i<gpioKnown.Length;i++)if(gpioKnown[i])result.Add(0x600+i);return result.ToArray(); }
        }
        public int[] GpioValues
        {
            get { var result=new List<int>();for(var i=0;i<gpioKnown.Length;i++)if(gpioKnown[i])result.Add(gpioValues[i]);return result.ToArray(); }
        }
        public bool InterruptOutputModeConfigured=>gpioKnown[1] && gpioValues[1]==5;
        public bool InterruptRegistersEnabled {get;}
        public byte[] EventState=>(byte[])events.Clone();
        public byte[] EnableState=>(byte[])enables.Clone();
        public bool DigitalIrqPending
        {
            get { for(var i=0;i<events.Length;i++)if((events[i]&enables[i])!=0)return true;return false; }
        }
        public int RegisterWrites {get;private set;}
        public int[] WriteAddresses=>writeAddresses.ToArray();
        public int[] WriteValues=>writeValues.ToArray();
        public int[] ReadAddresses=>readAddresses.ToArray();
        public int[] ReadValues=>readValues.ToArray();
        public int Pointer {get;private set;}
        public int PointerWrites {get;private set;}
        public int DataReads {get;private set;}
        public int ReturnedBytes {get;private set;}
        public int Finishes {get;private set;}
        public int AccessCount {get;private set;}
        public ulong LastAddress {get;private set;}
        public int LastWidth {get;private set;}
        public ulong LastValue {get;private set;}
        public string LastOperation {get;private set;}
        private sealed class LdswRegisterBank
        {
            private static readonly int[] addresses={0x805,0x806,0x807,0x808,0x809,0x80c,0x80d};
            private readonly byte[] values=new byte[7];private readonly bool[] known=new bool[7];private readonly int[] tasks=new int[4];
            public int ConfigWrites {get;private set;}public int TaskWrites {get;private set;}
            public int[] TaskRequests=>(int[])tasks.Clone();
            public void Reset(bool sourceReset)
            {
                Array.Clear(values,0,7);Array.Clear(tasks,0,4);ConfigWrites=TaskWrites=0;
                for(var i=0;i<7;i++)known[i]=sourceReset;
            }
            public bool Owns(int address)=>(address>=0x800 && address<=0x803) || Array.IndexOf(addresses,address)>=0;
            public byte[] Read(int address,int count)
            {
                if(count<1 || count>5)return null;
                var result=new byte[count];
                for(var i=0;i<count;i++) {var index=Array.IndexOf(addresses,address+i);if(index<0 || !known[index])return null;result[i]=values[index];}
                return result;
            }
            public bool TryWrite(int address,byte[] data)
            {
                if(address>=0x800 && address<=0x803)
                {
                    if(data.Length!=1 || data[0]>1)return false;
                    TaskWrites++;if(data[0]==1)tasks[address-0x800]++;return true;
                }
                for(var i=0;i<data.Length;i++)
                {
                    var a=address+i;if(Array.IndexOf(addresses,a)<0)return false;
                    var max=a==0x805 || a==0x806 ? 15 : a==0x807 ? 255 : a==0x808 || a==0x809 ? 1 : 23;
                    if(data[i]>max)return false;
                }
                for(var i=0;i<data.Length;i++) {var index=Array.IndexOf(addresses,address+i);known[index]=true;values[index]=data[i];ConfigWrites++;}
                return true;
            }
            public int[] KnownAddresses {get {var result=new List<int>();for(var i=0;i<7;i++)if(known[i])result.Add(addresses[i]);return result.ToArray();}}
            public int[] KnownValues {get {var result=new List<int>();for(var i=0;i<7;i++)if(known[i])result.Add(values[i]);return result.ToArray();}}
        }
        private readonly LdswRegisterBank ldsw=new LdswRegisterBank();
        private sealed class BuckRegisterBank
        {
            private static readonly int[] addresses={0x408,0x409,0x40a,0x40b,0x40c,0x40d,0x40e,0x40f,0x415};
            private readonly byte[] values=new byte[9];private readonly bool[] known=new bool[9];private readonly int[] tasks=new int[8];
            public int ConfigWrites {get;private set;}public int TaskWrites {get;private set;}
            public int[] TaskRequests=>(int[])tasks.Clone();
            public void Reset(bool sourceReset)
            {
                Array.Clear(known,0,9);Array.Clear(values,0,9);Array.Clear(tasks,0,8);ConfigWrites=TaskWrites=0;
                if(sourceReset) {for(var i=0;i<9;i++)known[i]=true;values[0]=values[1]=2;values[2]=values[3]=8;}
            }
            public bool Owns(int address)=>(address>=0x400 && address<=0x407) || Array.IndexOf(addresses,address)>=0;
            public byte[] Read(int address,int count)
            {
                if(count<1 || count>8)return null;
                var result=new byte[count];
                for(var i=0;i<count;i++) {var index=Array.IndexOf(addresses,address+i);if(index<0 || !known[index])return null;result[i]=values[index];}
                return result;
            }
            public bool TryWrite(int address,byte[] data)
            {
                if(address>=0x400 && address<=0x407)
                {
                    if(data.Length!=1 || data[0]>1)return false;
                    TaskWrites++;if(data[0]==1)tasks[address-0x400]++;return true;
                }
                for(var i=0;i<data.Length;i++)
                {
                    var a=address+i;if(Array.IndexOf(addresses,a)<0)return false;
                    if(a<=0x40b && data[i]>24)return false;
                    if(a==0x40f && data[i]>3)return false;
                    if(a==0x415 && data[i]>15)return false;
                }
                for(var i=0;i<data.Length;i++) {var index=Array.IndexOf(addresses,address+i);known[index]=true;values[index]=data[i];ConfigWrites++;}
                return true;
            }
            public int[] KnownAddresses {get {var result=new List<int>();for(var i=0;i<9;i++)if(known[i])result.Add(addresses[i]);return result.ToArray();}}
            public int[] KnownValues {get {var result=new List<int>();for(var i=0;i<9;i++)if(known[i])result.Add(values[i]);return result.ToArray();}}
        }
        private readonly BuckRegisterBank buck=new BuckRegisterBank();
        private sealed class ChargerRegisterBank
        {
            public void Reset()
            {
                Array.Clear(known,0,known.Length);Array.Clear(values,0,values.Length);
                Array.Clear(aliasValues,0,aliasValues.Length);Array.Clear(aliasKnown,0,aliasKnown.Length);
                known[8]=known[9]=known[10]=known[11]=true;
                values[8]=8;values[9]=0;values[10]=0xcf;values[11]=1;
            }
            private int Mask(int address)
            {
                if(address>=0x304 && address<=0x307)return 3;
                if(address>=0x308 && address<=0x30b)return (address&1)==0 ? 255 : 1;
                if(address==0x30c || address==0x30d)return 15;
                if(address==0x30e || address==0x30f || address==0x33c || address==0x350)return 1;
                if(address>=0x310 && address<=0x31b)return (address&1)==0 ? 255 : 3;
                return -1;
            }
            public bool Owns(int address)=>Mask(address)>=0;
            public byte[] Read(int address,int count)
            {
                if(count<1 || count>2)return null;
                if(address>=0x304 && address<=0x307)
                {
                    var alias=(address-0x304)/2;
                    if(count!=1 || (address&1)!=0 || aliasKnown[alias]!=3)return null;
                    return new byte[]{aliasValues[alias]};
                }
                var result=new byte[count];
                for(var i=0;i<count;i++)
                {
                    var index=address+i-0x300;
                    if(Mask(address+i)<0 || index<0 || index>=known.Length || !known[index])return null;
                    result[i]=values[index];
                }
                return result;
            }
            public bool TryWrite(int address,byte[] data)
            {
                if(data.Length<1 || data.Length>2)return false;
                if(address>=0x304 && address<=0x307)
                {
                    if(data.Length!=1 || (data[0]&~3)!=0)return false;
                    var alias=(address-0x304)/2;
                    if((address&1)==0)aliasValues[alias]|=data[0];
                    else aliasValues[alias]&=(byte)~data[0];
                    aliasKnown[alias]|=data[0];return true;
                }
                for(var i=0;i<data.Length;i++)
                {
                    var mask=Mask(address+i);
                    if(mask<0 || (data[i]&~mask)!=0 || address+i<0x308)return false;
                }
                for(var i=0;i<data.Length;i++) {var index=address+i-0x300;values[index]=data[i];known[index]=true;}
                return true;
            }
            public int[] KnownAddresses
            {
                get {var result=new List<int>();for(var i=0;i<known.Length;i++)if(known[i])result.Add(0x300+i);for(var i=0;i<2;i++)if(aliasKnown[i]==3)result.Add(0x304+2*i);return result.ToArray();}
            }
            public int[] KnownValues
            {
                get {var result=new List<int>();foreach(var address in KnownAddresses)result.Add(Read(address,1)[0]);return result.ToArray();}
            }
            public int[] AliasKnownMasks=>new int[]{aliasKnown[0],aliasKnown[1]};
            private readonly byte[] values=new byte[81];
            private readonly bool[] known=new bool[81];
            private readonly byte[] aliasValues=new byte[2],aliasKnown=new byte[2];
        }
        private readonly ChargerRegisterBank charger=new ChargerRegisterBank();
        private static readonly int[] groupBases={2,6,10,14,18,22,26,34};
        private static readonly byte[] groupMasks={255,63,63,7,15,63,63,31};
        private readonly bool[] gpioKnown=new bool[30];
        private readonly byte[] gpioValues=new byte[30];
        private readonly byte[] events=new byte[8],enables=new byte[8];
        private readonly List<int> writeAddresses=new List<int>(),writeValues=new List<int>();
        private bool pending;
        private readonly List<int> readAddresses=new List<int>();
        private readonly List<int> readValues=new List<int>();
    }
}
