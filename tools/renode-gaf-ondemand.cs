    // Included inside the pinned IMU namespace. Control state only; no EDMP calculation.
    public sealed class BlackwallImuGafOnDemand : Antmicro.Renode.Peripherals.IPeripheral
    {
        public BlackwallImuGafOnDemand(IMachine machine,BlackwallImuEdmpService owner,BlackwallImuGafParameters configuration,int observationMicroseconds)
        {
            if(machine==null || owner==null || configuration==null || !configuration.ConfigurationEnabled || observationMicroseconds<1 || observationMicroseconds>1000000)
                throw new ArgumentException("Explicit GAF configuration and bounded control observation window required");
            this.machine=machine;this.owner=owner;this.configuration=configuration;ObservationMicroseconds=observationMicroseconds;
            timer=new LimitTimer(machine.ClockSource,1000000,this,"GAF-control-observation",(ulong)observationMicroseconds,Direction.Ascending,enabled:false,workMode:WorkMode.OneShot,eventEnabled:true);
            timer.LimitReached+=()=>{ObservationEnded=true;EndedObservedAt=machine.ElapsedVirtualTime.TimeElapsed.Ticks;Phase="result-unsupported";};
            Reset();
        }
        public void Reset()
        {
            timer.Reset();Phase="unselected";RequestId=Requests=Reads=Writes=Triggers=BusyReads=UnsupportedResultRequests=0;
            Pending=ObservationEnded=false;RequestedAt=TriggeredAt=DeadlineAt=EndedObservedAt=0;lease=false;LastReject="";history.Clear();
        }
        public bool TryRequest(int address,byte[] data)
        {
            if(Active || address!=4 || data==null || data.Length!=1 || (data[0]!=2 && data[0]!=4)
                || !configuration.Complete || configuration.ReadRemaining!=0 || configuration.WrittenBytes!=225 || configuration.ClockReads!=1
                || owner.Completions!=2 || owner.Pending || !owner.GafControlIdle)
                return Reject("request-prerequisite");
            owner.StoreRamByte(4,data[0]);RequestId=data[0];Requests++;RequestedAt=Now();Phase="requested";history.Add("request:"+RequestId);return true;
        }
        public bool OwnsRegister(int address)=>address==0xa272 || address==0x2a || address==0x73 || address==0xa297;
        public bool DirectRegister(int address)=>address==0x2a || address==0x73;
        public bool CanSelectRead(int address)
        {
            if(address==0xa297 && ObservationEnded) {UnsupportedResultRequests++;return Reject("derived-result-unavailable");}
            return Active && ((Phase=="requested" && address==0xa272) || (Phase=="masked" && address==0x2a)
                || (Phase=="enabled" && address==0x73) || (Pending && !ObservationEnded && address==0xa297));
        }
        public bool TryReadRegister(int address,out byte value)
        {
            value=0;
            if(!CanSelectRead(address))return Reject(LastReject=="derived-result-unavailable" ? LastReject:"read-order");
            if(address==0xa297) {value=0;BusyReads++;Reads++;return true;}
            if(lease)return Reject("overlapping-read");
            previous=owner.GafControlValue(address);value=previous;lease=true;leasedAddress=address;Reads++;return true;
        }
        public bool TryWriteRegister(int address,byte value)
        {
            if(!Active || Pending || !lease || leasedAddress!=address)return Reject("write-order");
            byte expected;
            if(Phase=="requested" && address==0xa272)expected=(byte)(previous&~0x20);
            else if(Phase=="masked" && address==0x2a)expected=(byte)(previous|0x40);
            else if(Phase=="enabled" && address==0x73)expected=(byte)(previous|0x20);
            else return Reject("write-order");
            if(value!=expected)return Reject("rmw-bits");
            owner.GafControlStore(address,value);lease=false;Writes++;history.Add(address.ToString("x")+":"+value.ToString("x2"));
            if(address==0xa272)Phase="masked";
            else if(address==0x2a)Phase="enabled";
            else {TriggeredAt=Now();DeadlineAt=TriggeredAt+(ulong)ObservationMicroseconds*(TimeInterval.TicksPerMillisecond/1000);Pending=true;Triggers++;Phase="pending";owner.GafControlBusy();timer.ResetValue();timer.Enabled=true;}
            return true;
        }
        private ulong Now()
        {
            if(machine.SystemBus.TryGetCurrentCPU(out var cpu))cpu.SyncTime();
            return machine.ElapsedVirtualTime.TimeElapsed.Ticks;
        }
        private bool Reject(string reason) {LastReject=reason;return false;}
        public bool Active=>Phase!="unselected";
        public bool CalculationSupported=>false;
        public int CompletedCalculations=>0;
        public string Phase {get;private set;}
        public string LastReject {get;private set;}
        public bool Pending {get;private set;}
        public bool ObservationEnded {get;private set;}
        public int RequestId {get;private set;}
        public int Requests {get;private set;}
        public int Reads {get;private set;}
        public int Writes {get;private set;}
        public int Triggers {get;private set;}
        public int BusyReads {get;private set;}
        public int UnsupportedResultRequests {get;private set;}
        public int ObservationMicroseconds {get;}
        public ulong RequestedAt {get;private set;}
        public ulong TriggeredAt {get;private set;}
        public ulong DeadlineAt {get;private set;}
        public ulong EndedObservedAt {get;private set;}
        public string History=>string.Join("|",history);
        private readonly IMachine machine;
        private readonly BlackwallImuEdmpService owner;
        private readonly BlackwallImuGafParameters configuration;
        private readonly LimitTimer timer;
        private readonly List<string> history=new List<string>();
        private bool lease;
        private int leasedAddress;
        private byte previous;
    }
