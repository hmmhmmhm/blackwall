    // Explicit fault: the on-demand engine never executes or produces results.
    public sealed class BlackwallImuGafFrozenCore : Antmicro.Renode.Peripherals.IPeripheral
    {
        public BlackwallImuGafFrozenCore(IMachine machine,BlackwallImuEdmpService owner,BlackwallImuGafParameters configuration,int observationMicroseconds)
        {
            if(machine==null || owner==null || configuration==null || !configuration.ConfigurationEnabled || observationMicroseconds<1 || observationMicroseconds>1000000)
                throw new ArgumentException("Pinned configuration and explicit frozen-core fault required");
            this.machine=machine;this.owner=owner;this.configuration=configuration;ObservationMicroseconds=observationMicroseconds;Reset();
        }
        public void Reset()
        {
            Phase="unselected";RequestId=Requests=Reads=Writes=Triggers=BusyReads=UnsupportedResultRequests=0;
            RamReadRemaining=RamReads=RamWrittenBytes=0;Pending=false;RequestedAt=TriggeredAt=0;lease=false;LastReject="";history.Clear();
        }
        public bool TryRequest(int address,byte[] data)
        {
            if(address!=4 || data==null || data.Length!=1 || !configuration.Complete || configuration.ReadRemaining!=0
                || configuration.WrittenBytes!=225 || configuration.ClockReads!=1 || owner.Completions!=2 || owner.Pending
                || (Requests==0 ? data[0]!=2 || !owner.GafControlIdle : Requests!=1 || data[0]!=4 || Phase!="pending"))
                return Reject("fault-request-prerequisite");
            owner.StoreRamByte(4,data[0]);RequestId=data[0];Requests++;RequestedAt=Now();Phase="requested";lease=false;history.Add("request:"+RequestId);return true;
        }
        public bool OwnsRegister(int address)=>address==0xa272 || address==0x2a || address==0x73 || address==0xa297 || (address==0x5bc && RamReadRemaining>0);
        public bool DirectRegister(int address)=>address==0x2a || address==0x73;
        public bool CanSelectRead(int address)
        {
            return Active && ((Phase=="requested" && address==0xa272) || (Phase=="masked" && address==0x2a)
                || (Phase=="enabled" && address==0x73) || (Pending && address==0xa297)
                || (Requests==2 && Phase=="pending" && address==0xa272)
                || (Phase=="cleanup-masked" && address==0x2a));
        }
        public bool TryReadRegister(int address,out byte value)
        {
            value=0;
            if(address==0x5bc && RamReadRemaining>0)
            {
                value=(byte)owner.RamByte(0x5bc+4-RamReadRemaining);RamReadRemaining--;RamReads++;Reads++;return true;
            }
            if(!CanSelectRead(address))return Reject("fault-read-order");
            if(address==0xa297) {BusyReads++;Reads++;return true;}
            if(lease)return Reject("overlapping-read");
            previous=owner.GafControlValue(address);value=previous;lease=true;leasedAddress=address;Reads++;return true;
        }
        public bool TryWriteRegister(int address,byte value)
        {
            if(!Active || !lease || leasedAddress!=address)return Reject("fault-write-order");
            byte expected;
            if(Phase=="requested" && address==0xa272)expected=(byte)(previous&~0x20);
            else if(Phase=="masked" && address==0x2a)expected=(byte)(previous|0x40);
            else if(Phase=="enabled" && address==0x73)expected=(byte)(previous|0x20);
            else if(Requests==2 && Phase=="pending" && address==0xa272)expected=(byte)(previous|0x20);
            else if(Phase=="cleanup-masked" && address==0x2a)expected=(byte)(previous&~0x40);
            else return Reject("fault-write-order");
            if(value!=expected)return Reject("rmw-bits");
            owner.GafControlStore(address,value);lease=false;Writes++;history.Add(address.ToString("x")+":"+value.ToString("x2"));
            if(Phase=="requested")Phase="masked";
            else if(Phase=="masked")Phase="enabled";
            else if(Phase=="enabled") {TriggeredAt=Now();Pending=true;Triggers++;Phase="pending";owner.GafControlBusy();}
            else if(Phase=="pending")Phase="cleanup-masked";
            else Phase="failed-disabled";
            return true;
        }
        public bool TryWriteRam(int address,byte[] data)
        {
            if(Phase!="failed-disabled" || data==null || data.Length==0)return false;
            for(int k=0;k<data.Length;k++)if(!HostWriteByte(address+k))return Reject("fault-ram-write-range");
            for(int k=0;k<data.Length;k++)owner.StoreRamByte(address+k,data[k]);
            RamWrittenBytes+=data.Length;history.Add("ram:"+address.ToString("x")+":"+data.Length);return true;
        }
        public bool BeginRamRead(int address)
        {
            // The prior modeled init cleared this byte range. A frozen engine
            // retains it; this is not a synthesized calculation output.
            if(Phase!="failed-disabled" || address!=0x5bc || RamReads!=0 || RamReadRemaining!=0 || owner.ClearedBytes!=0x1800)
            {UnsupportedResultRequests++;return Reject("retained-ram-unavailable");}
            RamReadRemaining=4;return true;
        }
        private bool HostWriteByte(int address)=>
            (address>=0xb4 && address<0xb8) || (address>=0x154 && address<0x184)
            || (address>=0x6a0 && address<0x6a4) || (address>=0xc80 && address<0xcfd);
        private ulong Now()
        {
            if(machine.SystemBus.TryGetCurrentCPU(out var cpu))cpu.SyncTime();
            return machine.ElapsedVirtualTime.TimeElapsed.Ticks;
        }
        private bool Reject(string reason) {LastReject=reason;return false;}
        public bool Active=>Phase!="unselected";
        public bool FaultInjected=>true;
        public bool CalculationSupported=>false;
        public int CompletedCalculations=>0;
        public bool ObservationEnded=>false;
        public ulong DeadlineAt=>0;
        public ulong EndedObservedAt=>0;
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
        private readonly IMachine machine;
        private readonly BlackwallImuEdmpService owner;
        private readonly BlackwallImuGafParameters configuration;
        private readonly List<string> history=new List<string>();
        private bool lease;
        private int leasedAddress;
        private byte previous;
    }
