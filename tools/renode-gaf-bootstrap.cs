    // Explicit cold functional scenario. Completes the bus service contract,
    // not an execution of the sensor ROM or its numerical fusion algorithm.
    public sealed class BlackwallImuGafBootstrap : Antmicro.Renode.Peripherals.IPeripheral
    {
        public BlackwallImuGafBootstrap(IMachine machine,BlackwallImuEdmpService owner,BlackwallImuGafParameters configuration,int observationMicroseconds,BlackwallImuOdrConfiguration odr=null)
        {
            if(machine==null || owner==null || configuration==null || !configuration.ConfigurationEnabled || observationMicroseconds<1 || observationMicroseconds>1000000)
                throw new ArgumentException("Explicit cold GAF functional profile and bounded virtual duration required");
            this.odr=odr;this.machine=machine;this.owner=owner;this.configuration=configuration;ObservationMicroseconds=observationMicroseconds;
            timer=new LimitTimer(machine.ClockSource,1000000,this,"GAF-cold-scenario",(ulong)observationMicroseconds,Direction.Ascending,enabled:false,workMode:WorkMode.OneShot,eventEnabled:true);
            timer.LimitReached+=()=>
            {
                if(!Pending)return;
                Pending=false;CompletedServices++;Phase="completed";owner.GafControlReady();
                if(RequestId==2)for(var k=0;k<4;k++)owner.StoreRamByte(0x4a0+k,(byte)owner.RamByte(0x294+k));
                if(RequestId==4)
                {
                    for(var k=0;k<4;k++)owner.StoreRamByte(0x5bc+k,0);
                    AccuracyAssumed=true;
                }
                history.Add("scenario-complete:"+RequestId);
            };
            Reset();
        }
        public void Reset()
        {
            timer.Reset();Phase="unselected";RequestId=Requests=Reads=Writes=Triggers=BusyReads=UnsupportedResultRequests=0;
            RamReadRemaining=RamReads=RamWrittenBytes=CompletedServices=0;Pending=AccuracyAssumed=false;
            apexMasks[0]=apexMasks[1]=-1;Array.Clear(guestWritten,0,guestWritten.Length);ramReadFromGuestStorage=false;RequestedAt=TriggeredAt=0;lease=false;LastReject="";history.Clear();
        }
        public bool TryRequest(int address,byte[] data)
        {
            if(address!=4 || data==null || data.Length!=1 || !configuration.Complete || configuration.ReadRemaining!=0 ||
               configuration.WrittenBytes!=225 || configuration.ClockReads!=1 || owner.Completions!=2 || owner.Pending ||
               (Requests==0 ? data[0]!=2 || !owner.GafControlIdle : Requests!=1 || data[0]!=4 || Phase!="completed"))
                return Reject("scenario-request-prerequisite");
            if(Requests==0 && odr!=null)
            {
                int selection=odr.PeekRegister(0x27)&7;if(selection>5)return Reject("unsupported-decimation-odr");
                uint encoded=new uint[]{1,2,8,0x80,0x8000,0x80000000}[selection];
                for(int k=0;k<4;k++)owner.StoreRamByte(0x188+k,(byte)(encoded>>(k*8)));
            }
            owner.StoreRamByte(4,data[0]);RequestId=data[0];Requests++;RequestedAt=Now();Phase="requested";lease=false;history.Add("request:"+RequestId);return true;
        }
        public bool OwnsRegister(int address)=>address==0xa272 || address==0x29 || address==0x2a || address==0x73 || address==0xa297 || (address==ramReadBase && RamReadRemaining>0);
        public bool DirectRegister(int address)=>address==0x29 || address==0x2a || address==0x73;
        public bool CanSelectRead(int address)=>Active &&
            ((Phase=="requested" && address==0xa272) || (Phase=="masked" && address==0x2a) || (Phase=="enabled" && address==0x73) ||
             ((Pending || Phase=="completed" || Phase=="disabled") && address==0xa297) ||
             (Requests==2 && Phase=="completed" && address==0xa272) || (Phase=="cleanup-masked" && address==0x2a) ||
             (Phase=="disabled" && (address==0x29 || address==0x2a || address==0xa272 || address==0x73)));
        public bool TryReadRegister(int address,out byte value)
        {
            value=0;
            if(address==ramReadBase && RamReadRemaining>0)
            {value=(byte)owner.RamByte(ramReadBase+ramReadLength-RamReadRemaining);RamReadRemaining--;RamReads++;Reads++;return true;}
            if(!CanSelectRead(address))return Reject("scenario-read-order");
            if(address==0xa297) {value=(byte)(Pending ? 0:2);if(Pending)BusyReads++;Reads++;return true;}
            if(lease)return Reject("overlapping-read");
            previous=owner.GafControlValue(address);value=previous;lease=true;leasedAddress=address;Reads++;return true;
        }
        public bool TryWriteRegister(int address,byte value)
        {
            if(!Active || Pending || !lease || leasedAddress!=address)return Reject("scenario-write-order");
            byte expected;
            var phase=Phase;
            if(phase=="requested" && address==0xa272)expected=(byte)(previous&~0x20);
            else if(phase=="masked" && address==0x2a)expected=(byte)(previous|0x40);
            else if(phase=="enabled" && address==0x73)expected=(byte)(previous|0x20);
            else if(Requests==2 && phase=="completed" && address==0xa272)expected=(byte)(previous|0x20);
            else if(phase=="cleanup-masked" && address==0x2a)expected=(byte)(previous&~0x40);
            else if(phase=="disabled")
            {
                var mask=address==0x29 ? 0xff:(address==0x2a ? 0x70:0x20);
                if(((previous^value)&~mask)!=0)return Reject("scenario-control-bits");
                expected=value;
            }
            else return Reject("scenario-write-order");
            if(value!=expected)return Reject("rmw-bits");
            owner.GafControlStore(address,value);lease=false;Writes++;history.Add(address.ToString("x")+":"+value.ToString("x2"));
            if(phase=="requested")Phase="masked";
            else if(phase=="masked")Phase="enabled";
            else if(phase=="enabled")
            {TriggeredAt=Now();Pending=true;Triggers++;Phase="pending";owner.GafControlBusy();timer.ResetValue();timer.Enabled=true;}
            else if(phase=="completed")Phase="cleanup-masked";
            else if(phase=="cleanup-masked")Phase="disabled";
            return true;
        }
        public bool TryWriteRam(int address,byte[] data)
        {
            if(Phase!="disabled" || data==null || data.Length==0)return false;
            for(int k=0;k<data.Length;k++)if(!HostWriteByte(address+k))return Reject("scenario-ram-write-range");
            for(int k=0;k<data.Length;k++){owner.StoreRamByte(address+k,data[k]);guestWritten[address+k]=true;}
            RamWrittenBytes+=data.Length;history.Add("ram:"+address.ToString("x")+":"+data.Length);return true;
        }
        public bool BeginRamRead(int address)
        {
            int length=(address==0x5bc || address==0x4a0 || (address==0x188 && odr!=null)) ? 4:configuration.DeclaredFieldLength(address);
            bool fromGuest=false;
            if(length==0 && address>=0 && address<8192 && guestWritten[address])
            {fromGuest=true;while(address+length<8192 && guestWritten[address+length])length++;}
            if(Phase!="disabled" || !AccuracyAssumed || length==0 || (RamReadRemaining!=0 && !ramReadFromGuestStorage))
            {UnsupportedResultRequests++;return Reject("scenario-ram-read-range");}
            ramReadFromGuestStorage=fromGuest;ramReadBase=address;ramReadLength=RamReadRemaining=length;return true;
        }
        // Functional SRAM storage accepts guest-provided bytes; it never synthesizes unknown read results.
        public bool MaskRegister(int address)=>Phase=="disabled" && (address==0x39 || address==0x3a);
        public bool TryWriteMask(int address,byte[] data)
        {
            if(!MaskRegister(address) || data==null || data.Length<1 || address+data.Length>0x3b)return false;
            for(int k=0;k<data.Length;k++)if(address+k==0x3a && (data[k]&0x88)!=0)return false;
            for(int k=0;k<data.Length;k++)apexMasks[address+k-0x39]=data[k];
            history.Add("apex-mask:"+address.ToString("x")+":"+BitConverter.ToString(data));return true;
        }
        public byte[] ReadMask(int address,int count)
        {
            if(!MaskRegister(address) || count<1 || address+count>0x3b)return null;
            var result=new byte[count];for(int k=0;k<count;k++){if(apexMasks[address+k-0x39]<0)return null;result[k]=(byte)apexMasks[address+k-0x39];}return result;
        }
        public bool GuestReadActive=>ramReadFromGuestStorage && RamReadRemaining>0;
        public void EndGuestRead() {if(!GuestReadActive)throw new InvalidOperationException("No guest storage read");RamReadRemaining=0;ramReadFromGuestStorage=false;}
        private bool HostWriteByte(int address)=>address>=0 && address<8192;
        private ulong Now() {if(machine.SystemBus.TryGetCurrentCPU(out var cpu))cpu.SyncTime();return machine.ElapsedVirtualTime.TimeElapsed.Ticks;}
        private bool Reject(string reason) {LastReject=reason;return false;}
        public string FunctionalProfile=>"cold-bootstrap-v1";
        public bool Active=>Phase!="unselected";
        public bool FaultInjected=>false;
        public bool CalculationSupported=>false;
        public int CompletedCalculations=>0;
        public bool ObservationEnded=>false;
        public ulong DeadlineAt=>0;
        public ulong EndedObservedAt=>0;
        public bool AccuracyAssumed {get;private set;}
        public int CompletedServices {get;private set;}
        public string Phase {get;private set;}
        public string LastReject {get;private set;}
        public bool Pending {get;private set;}
        public int RequestId {get;private set;}
        public int Requests {get;private set;}
        public int Reads {get;private set;}
        public int Writes {get;private set;}
        public int Triggers {get;private set;}
        public int BusyReads {get;private set;}
        public int UnsupportedResultRequests {get;private set;}
        public int RamReadRemaining {get;private set;}
        public int RamReads {get;private set;}
        public int RamWrittenBytes {get;private set;}
        public int ObservationMicroseconds {get;}
        public ulong RequestedAt {get;private set;}
        public ulong TriggeredAt {get;private set;}
        public string History=>string.Join("|",history);
        private readonly BlackwallImuOdrConfiguration odr;
        private readonly IMachine machine;
        private readonly BlackwallImuEdmpService owner;
        private readonly BlackwallImuGafParameters configuration;
        private readonly LimitTimer timer;
        private readonly List<string> history=new List<string>();
        private readonly int[] apexMasks=new int[2];
        private readonly bool[] guestWritten=new bool[8192];
        private bool ramReadFromGuestStorage;
        private bool lease;
        private int leasedAddress,ramReadBase,ramReadLength;
        private byte previous;
    }
