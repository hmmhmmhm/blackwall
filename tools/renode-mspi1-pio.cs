namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals.Timers;
    using Antmicro.Renode.Time;
    // Bounded idle NOR scenario. A named identity is a datasheet model, not a device inventory.
    public sealed class BlackwallMspi1PioReset : IBlackwallMspi1Pio
    {
        public BlackwallMspi1PioReset(IMachine machine,string profile,BlackwallPeripheralPower power,BlackwallMspi1ClockStorage clock,BlackwallMspi1Interrupts interrupts,bool completeTransactions=true,string identityProfile="none",string samplingProfile="fixed-capture",int statusByte=-1,bool emulateWriteEnableLatch=false,int configurationByte=-1,bool continuousStatusRead=false,BlackwallNorReadWindow arrayBacking=null,uint sectorEraseMicroseconds=0,bool completeSectorErase=true,uint pageProgramMicroseconds=0,bool completePageProgram=true,uint maxArrayReadBytes=64)
        {
            if(profile!="idle-nor-reset" || power==null || power.Mask!=0x8000 || clock==null || interrupts==null)throw new ArgumentException("Explicit idle NOR dependencies required");
            if(identityProfile!="none" && identityProfile!="mx25u25643g")throw new ArgumentException("Unknown NOR identity profile");
            if(samplingProfile!="fixed-capture" && samplingProfile!="ideal-sdr")throw new ArgumentException("Unknown sampling profile");
            if(statusByte < -1 || statusByte > 255)throw new ArgumentException("Status byte must be explicit 0..255 or unknown -1");
            if(emulateWriteEnableLatch && (identityProfile!="mx25u25643g" || statusByte<0 || (statusByte&3)!=0))throw new ArgumentException("Latch mode requires known idle WIP/WEL0 and MX25U25643G identity");
            if(configurationByte!=-1 && configurationByte!=0 && configurationByte!=8)throw new ArgumentException("Configuration seed must be unknown -1 or reset TB fixture 0/8");
            if(configurationByte>=0 && (identityProfile!="mx25u25643g" || statusByte<0 || (statusByte&1)!=0))throw new ArgumentException("Known configuration needs explicit idle NOR identity/status");
            if(continuousStatusRead && (identityProfile!="mx25u25643g" || statusByte<0 || samplingProfile!="ideal-sdr"))throw new ArgumentException("Repeated status requires known MX status and explicit ideal logical SDR transport");
            if(arrayBacking!=null && (identityProfile!="mx25u25643g" || statusByte<0 || samplingProfile!="ideal-sdr"))throw new ArgumentException("NOR read window requires explicit MX status and logical SDR transport");
            ArrayBacking=arrayBacking;
            if(maxArrayReadBytes<64 || maxArrayReadBytes>65535 || (maxArrayReadBytes>64 && arrayBacking==null))throw new ArgumentException("Explicit bounded backing and 64..65535-byte RX limit required");
            MaxArrayReadBytes=maxArrayReadBytes;
            if(sectorEraseMicroseconds>1000000 || (sectorEraseMicroseconds!=0 && (arrayBacking==null || !emulateWriteEnableLatch)))throw new ArgumentException("Erase needs bounded backing, dynamic WEL and explicit 1..1000000us hypothesis; 0 is unknown");
            SectorEraseMicroseconds=sectorEraseMicroseconds;CompleteSectorErase=completeSectorErase;
            if(pageProgramMicroseconds>1000000 || (pageProgramMicroseconds!=0 && (arrayBacking==null || !emulateWriteEnableLatch)))throw new ArgumentException("Program needs bounded backing, dynamic WEL and explicit 1..1000000us hypothesis; 0 is unknown");
            PageProgramMicroseconds=pageProgramMicroseconds;CompletePageProgram=completePageProgram;
            ContinuousStatusRead=continuousStatusRead;
            ConfigurationByte=configurationByte;
            EmulateWriteEnableLatch=emulateWriteEnableLatch;
            StatusByte=statusByte;
            SamplingProfile=samplingProfile;IdentityProfile=identityProfile;this.machine=machine;this.power=power;this.clock=clock;this.interrupts=interrupts;CompleteTransactions=completeTransactions;
            transfer=new LimitTimer(machine.ClockSource,1000000,this,"PIO-command",10,Direction.Ascending,enabled:false,workMode:WorkMode.OneShot,eventEnabled:true);
            recovery=new LimitTimer(machine.ClockSource,1000000,this,"NOR-reset-recovery",100,Direction.Ascending,enabled:false,workMode:WorkMode.OneShot,eventEnabled:true);
            erase=new LimitTimer(machine.ClockSource,1000000,this,"NOR-sector-erase",Math.Max(1u,sectorEraseMicroseconds),Direction.Ascending,enabled:false,workMode:WorkMode.OneShot,eventEnabled:true);
            program=new LimitTimer(machine.ClockSource,1000000,this,"NOR-page-program",Math.Max(1u,pageProgramMicroseconds),Direction.Ascending,enabled:false,workMode:WorkMode.OneShot,eventEnabled:true);
            transfer.LimitReached+=Complete;
            recovery.LimitReached+=()=>{Recovering=false;};erase.LimitReached+=CompleteErase;program.LimitReached+=CompleteProgram;Reset();
        }
        private bool Ready=>power.Phase=="on" && clock.Enabled && (clock.Selection==7 || clock.Selection==8);
        private void SyncTime(){if(machine.SystemBus.TryGetCurrentCPU(out var cpu))cpu.SyncTime();}
        public bool TryRead(uint offset,out uint value)
        {
            SyncTime();value=0;
            if(offset==0)value=Control;
            else if(offset==0x18)value=TxEntries;
            else if(offset==0x1c)value=RxEntries;
            else if(offset==0x14)
            {
                if(rxWords.Count==0)return false;
                value=rxWords.Dequeue(); // Unused lanes are model padding, not device bytes.
                FifoReads++;
            }
            else return false;
            Reads++;return true;
        }
        public bool TryWriteTx(uint value)
        {
            if(!Ready || !Busy || command!=2 || pendingProgram==null || txWords.Count==16 || txReceived>=(uint)pendingProgram.Length)return false;
            txWords.Enqueue(value);txReceived+=Math.Min(4u,(uint)pendingProgram.Length-txReceived);TxFifoWrites++;return true;
        }
        public bool TryWrite(uint value,uint instruction,uint configuration,uint address,uint control1,uint ddr)
        {
            if(!Ready)return false;
            if(value==2 && !Busy){Control&=~2u;Writes++;return true;}
            if(Busy || Recovering || rxWords.Count!=0)return false;
            bool resetCommand=value==0xc1 && configuration==0x1410061 && (instruction==0x66 || instruction==0x99 || instruction==0);
            // ideal-sdr abstracts physical sampling errors; it does not manufacture a calibrated timing window.
            uint normalizedCapture=configuration&~0x1c00000u;
            bool captureSupported=configuration==0x3010861 || (SamplingProfile=="ideal-sdr" && (normalizedCapture==0x2010861u || normalizedCapture==0x2010061u));
            bool readId=IdentityProfile=="mx25u25643g" && value==0x30441 && captureSupported && instruction==0x9f;
            // Eight turnaround clocks consume one repeated RDSR byte. Pin routing is
            // an explicit logical transport hypothesis, not validated by ideal sampling.
            bool repeatedStatus=ContinuousStatusRead && normalizedCapture==0x10861;
            bool readStatus=IdentityProfile=="mx25u25643g" && StatusByte>=0 && value==0x10441 && (configuration==0x3010061 || repeatedStatus) && instruction==5;
            bool writeEnable=EmulateWriteEnableLatch && value==0xc1 && configuration==0x3010061 && instruction==6;
            bool writeDisable=EmulateWriteEnableLatch && value==0xc1 && configuration==0x3010061 && instruction==4;
            bool enter4Byte=ConfigurationByte>=0 && value==0xc1 && configuration==0x3010061 && instruction==0xb7;
            bool readConfiguration=ConfigurationByte>=0 && value==0x10441 && configuration==0x3010061 && instruction==0x15;
            if((EraseBusy || ProgramBusy) && !readStatus)return false;
            bool sectorErase=SectorEraseMicroseconds!=0 && instruction==0x20 && value==0xe1 && configuration==0x3010061
                && control1==0 && (ddr&0x1fu)==0 && FourByteAddressMode && WriteEnabled && (StatusByte&~0x40)==0
                && ArrayBacking.CanEraseSector(address);
            byte[] arrayData=null;
            uint count=value>>16;
            bool pageProgram=PageProgramMicroseconds!=0 && instruction==2 && (value&0xffffu)==0xe1u && count>=1 && count<=256
                && configuration==0x3010061 && control1==0 && (ddr&0x1fu)==0 && FourByteAddressMode && WriteEnabled && (StatusByte&~0x40)==0
                && ArrayBacking.CanProgramPage(address,count);
            // QREAD4B is a 1-1-4 transaction with an explicit four-byte address,
            // independent of the NOR's EN4B latch. No pin-level behavior is implied.
            bool readArray=ArrayBacking!=null && instruction==0x6c && (value&0xffffu)==0x461u && count>=1 && count<=MaxArrayReadBytes
                && normalizedCapture==0x10861 && control1==5 && (ddr&0x1fu)==0 && (CurrentStatusByte&0x41)==0x40
                && ArrayBacking.TryRead(address,count,out arrayData);
            if(!resetCommand && !readId && !readStatus && !writeEnable && !writeDisable && !enter4Byte && !readConfiguration && !readArray && !sectorErase && !pageProgram)return false;
            if(pageProgram){pendingProgram=new byte[count];pendingProgramAddress=address;txReceived=txDrained=0;}
            if(sectorErase)pendingSector=address&~0xfffu;
            pendingArray=arrayData;pendingArrayAddress=address;pendingArrayOffset=0;
            command=instruction;pendingStatusDiscard=readStatus && repeatedStatus;pendingSampling=readId ? 1u<<(int)((configuration>>22)&7) : 0;frameBits=value&~7u;clockEpoch=clock.ChangeEpoch;Control=frameBits|4u;Busy=true;Starts++;Writes++;
            transfer.ResetValue();transfer.Enabled=CompleteTransactions;return true;
        }
        private void Complete()
        {
            if(!Busy)return;
            if(!Ready || clock.ChangeEpoch!=clockEpoch){Busy=false;Control=0;pendingArray=pendingProgram=null;pendingArrayOffset=0;rxWords.Clear();txWords.Clear();txReceived=txDrained=0;Aborted++;return;}
            if(command==0x6c && pendingArray.Length>64)
            {
                // Logical FIFO-paced transport. The 10us service interval is a
                // scenario assumption, not a measured bit clock or throughput.
                while(rxWords.Count<16 && pendingArrayOffset<(uint)pendingArray.Length)
                {
                    uint word=0;
                    for(int j=0;j<4 && pendingArrayOffset<(uint)pendingArray.Length;j++)word|=(uint)pendingArray[pendingArrayOffset++]<<(j*8);
                    rxWords.Enqueue(word);
                }
                if(pendingArrayOffset<(uint)pendingArray.Length){transfer.ResetValue();transfer.Enabled=CompleteTransactions;return;}
            }
            if(command==2)
            {
                while(txWords.Count!=0)
                {
                    uint word=txWords.Dequeue();
                    for(int j=0;j<4 && txDrained<(uint)pendingProgram.Length;j++)pendingProgram[txDrained++]=(byte)(word>>(8*j));
                }
                if(txDrained<(uint)pendingProgram.Length){transfer.ResetValue();transfer.Enabled=CompleteTransactions;return;}
            }
            // A completed SPI byte has no device acknowledgment. Device semantics are separate.
            if(command==0x66)ResetArmed=true;
            else if(command==0x99)
            {
                if(ResetArmed){Resets++;WriteEnabled=FourByteAddressMode=false;Recovering=true;recovery.ResetValue();recovery.Enabled=true;}
                else IgnoredResets++;
                ResetArmed=false;
            }
            else
            {
                ResetArmed=false;
                if(command==0x9f){rxWords.Enqueue(0x003925c2u);ReadIdTransfers++;CompletedSamplingMask|=pendingSampling;}
                else if(command==5){rxWords.Enqueue((uint)CurrentStatusByte);StatusReadTransfers++;if(pendingStatusDiscard){ContinuousStatusTransfers++;StatusDiscardedBytes++;}}
                else if(command==6){WriteEnabled=true;WriteEnableTransfers++;}
                else if(command==4){WriteEnabled=false;WriteDisableTransfers++;}
                else if(command==0xb7){FourByteAddressMode=true;Enter4ByteTransfers++;}
                else if(command==0x15){rxWords.Enqueue((uint)CurrentConfigurationByte);ConfigurationReadTransfers++;}
                else if(command==0x20)
                {
                    EraseBusy=true;SectorEraseStarts++;LastEraseAddress=pendingSector;
                    erase.ResetValue();erase.Enabled=CompleteSectorErase;
                }
                else if(command==2)
                {
                    ProgramBusy=true;PageProgramStarts++;LastProgramAddress=pendingProgramAddress;
                    activeProgram=pendingProgram;activeProgramAddress=pendingProgramAddress;pendingProgram=null;
                    program.ResetValue();program.Enabled=CompletePageProgram && !ProgramCompletionHeld;
                    if(ProgramCompletionHeld){ProgramCompletionHeld=false;HeldProgramCompletions++;}
                }
                else if(command==0x6c)
                {
                    for(int i=0;pendingArray.Length<=64 && i<pendingArray.Length;i+=4)
                    {
                        uint word=0;for(int j=0;j<4 && i+j<pendingArray.Length;j++)word|=(uint)pendingArray[i+j]<<(j*8);
                        rxWords.Enqueue(word);
                    }
                    ArrayReadTransfers++;ArrayBytesRead+=(uint)pendingArray.Length;LastArrayAddress=pendingArrayAddress;pendingArray=null;
                }
            } // Commands other than reset cancel the reset-enable latch.

            Busy=false;Control=frameBits|2u;Completions++;interrupts.SetPending(1);
        }
        private void CompleteErase()
        {
            if(!EraseBusy)return;
            if(!ArrayBacking.TryEraseSector(pendingSector))throw new InvalidOperationException("Accepted erase escaped declared NOR window");
            EraseBusy=false;WriteEnabled=false;SectorEraseCompletions++;
        }
        private void CompleteProgram()
        {
            if(!ProgramBusy)return;
            if(!ArrayBacking.TryProgramPage(activeProgramAddress,activeProgram))throw new InvalidOperationException("Accepted program escaped declared NOR window");
            ProgramBusy=false;WriteEnabled=false;PageProgramCompletions++;ProgramBytesCommitted+=(uint)activeProgram.Length;activeProgram=null;
        }
        public void HoldNextProgramCompletion()
        {
            if(PageProgramMicroseconds==0 || !CompletePageProgram || ArrayBacking==null
                || ProgramCompletionHeld || Busy || Recovering || ProgramBusy || EraseBusy)
                throw new InvalidOperationException("One explicit idle next-program fault may be armed at a time");
            ProgramCompletionHeld=true;
        }
        public bool ProgramCompletionHeld {get;private set;}
        public uint HeldProgramCompletions {get;private set;}
        public void Reset()
        {
            ProgramCompletionHeld=false;HeldProgramCompletions=0;
            erase.Reset();EraseBusy=false;SectorEraseStarts=SectorEraseCompletions=LastEraseAddress=pendingSector=0;
            program.Reset();ProgramBusy=false;pendingProgram=activeProgram=null;txWords.Clear();txReceived=txDrained=TxFifoWrites=PageProgramStarts=PageProgramCompletions=ProgramBytesCommitted=LastProgramAddress=pendingProgramAddress=activeProgramAddress=0;
            transfer.Reset();recovery.Reset();rxWords.Clear();pendingArray=null;Control=Starts=Completions=Resets=IgnoredResets=Aborted=Reads=Writes=command=frameBits=ReadIdTransfers=FifoReads=clockEpoch=CompletedSamplingMask=pendingSampling=StatusReadTransfers=WriteEnableTransfers=WriteDisableTransfers=Enter4ByteTransfers=ConfigurationReadTransfers=ContinuousStatusTransfers=StatusDiscardedBytes=ArrayReadTransfers=ArrayBytesRead=LastArrayAddress=pendingArrayAddress=pendingArrayOffset=0;Busy=ResetArmed=Recovering=WriteEnabled=FourByteAddressMode=pendingStatusDiscard=false;
        }
        public uint Control {get;private set;}
        public BlackwallPeripheralPower PowerOwner => power;
        public bool CanPowerDown { get { SyncTime();return !Busy && !Recovering && rxWords.Count==0 && txWords.Count==0; } }
        public void PowerDownController()
        {
            if(!CanPowerDown)throw new InvalidOperationException("MSPI controller has outstanding activity");
            transfer.Reset();Control=command=frameBits=clockEpoch=pendingSampling=pendingArrayOffset=0;rxWords.Clear();pendingArray=null;
            txWords.Clear();pendingProgram=null;txReceived=txDrained=0;
            Busy=pendingStatusDiscard=false;
            // NOR latches, address mode, reset recovery and lifetime diagnostics are external.
        }
        public bool Busy {get;private set;}
        // Internal signal synchronization is not a guest CTRL register read.
        public bool CommandComplete { get { SyncTime();return (Control&2u)!=0; } }
        public bool ResetArmed {get;private set;}
        public bool Recovering {get;private set;}
        public bool CompleteTransactions {get;private set;}
        public uint Starts {get;private set;}
        public uint Completions {get;private set;}
        public uint Resets {get;private set;}
        public uint IgnoredResets {get;private set;}
        public uint Aborted {get;private set;}
        public uint Reads {get;private set;}
        public uint Writes {get;private set;}
        public string IdentityProfile {get;private set;}
        public string SamplingProfile {get;private set;}
        public uint CompletedSamplingMask {get;private set;}
        public uint RxEntries=>(uint)rxWords.Count;
        public uint ReadIdTransfers {get;private set;}
        public uint FifoReads {get;private set;}
        // Immutable seed or fixed fault input. Optional WEL changes no NV bits or content.
        public int StatusByte {get;private set;}
        public int CurrentStatusByte=>EmulateWriteEnableLatch ? StatusByte|(WriteEnabled ? 2 : 0)|((EraseBusy || ProgramBusy) ? 1 : 0) : StatusByte;
        public bool EmulateWriteEnableLatch {get;private set;}
        public bool WriteEnabled {get;private set;}
        public uint WriteEnableTransfers {get;private set;}
        public uint WriteDisableTransfers {get;private set;}
        public int ConfigurationByte {get;private set;}
        public int CurrentConfigurationByte=>ConfigurationByte<0 ? -1 : ConfigurationByte|(FourByteAddressMode ? 32 : 0);
        public bool FourByteAddressMode {get;private set;}
        public uint Enter4ByteTransfers {get;private set;}
        public uint ConfigurationReadTransfers {get;private set;}
        public uint StatusReadTransfers {get;private set;}
        public bool ContinuousStatusRead {get;private set;}
        public uint ContinuousStatusTransfers {get;private set;}
        public uint StatusDiscardedBytes {get;private set;}
        private bool pendingStatusDiscard;
        public BlackwallNorReadWindow ArrayBacking {get;}
        public uint MaxArrayReadBytes {get;}
        public uint ArrayReadTransfers {get;private set;}
        public uint ArrayBytesRead {get;private set;}
        public uint LastArrayAddress {get;private set;}
        public uint SectorEraseMicroseconds {get;}
        public bool CompleteSectorErase {get;}
        public bool EraseBusy {get;private set;}
        public uint SectorEraseStarts {get;private set;}
        public uint SectorEraseCompletions {get;private set;}
        public uint LastEraseAddress {get;private set;}
        public uint PageProgramMicroseconds {get;}
        public bool CompletePageProgram {get;}
        public bool ProgramBusy {get;private set;}
        public uint PageProgramStarts {get;private set;}
        public uint PageProgramCompletions {get;private set;}
        public uint ProgramBytesCommitted {get;private set;}
        public uint LastProgramAddress {get;private set;}
        public uint TxFifoWrites {get;private set;}
        public uint TxEntries=>(uint)txWords.Count;
        private uint txReceived,txDrained,pendingProgramAddress,activeProgramAddress;
        private byte[] pendingProgram,activeProgram;
        private readonly System.Collections.Generic.Queue<uint> txWords=new System.Collections.Generic.Queue<uint>();
        private uint pendingSector;
        private byte[] pendingArray;
        private readonly System.Collections.Generic.Queue<uint> rxWords=new System.Collections.Generic.Queue<uint>();
        private uint command,clockEpoch,frameBits,pendingSampling,pendingArrayAddress,pendingArrayOffset;
        private readonly IMachine machine;
        private readonly BlackwallPeripheralPower power;
        private readonly BlackwallMspi1ClockStorage clock;
        private readonly BlackwallMspi1Interrupts interrupts;
        private readonly LimitTimer transfer,recovery,erase,program;
    }
    public sealed class BlackwallNorReadWindow : Antmicro.Renode.Peripherals.IPeripheral
    {
        public BlackwallNorReadWindow(string profile,uint start,uint length,bool allowSectorErase=false,bool allowPageProgram=false,BlackwallNorReadWindow additionalWindow=null)
        {
            if((profile!="erased-range" && profile!="synthetic-ramp") || length==0 || (ulong)start+length>0x2000000UL)
                throw new ArgumentException("Explicit bounded NOR read-only range required");
            if(additionalWindow!=null && (additionalWindow.AdditionalWindow!=null
                || !((ulong)start+length<=additionalWindow.Start || (ulong)additionalWindow.Start+additionalWindow.Length<=start)))
                throw new ArgumentException("NOR requires disjoint single additional window");
            AdditionalWindow=additionalWindow;
            Profile=profile;Start=start;Length=length;AllowSectorErase=allowSectorErase;
            AllowPageProgram=allowPageProgram;
            contents=new byte[length];
            for(uint i=0;i<length;i++)contents[i]=profile=="erased-range" ? (byte)255:(byte)i;
        }
        public bool TryRead(uint address,uint length,out byte[] bytes)
        {
            bytes=null;if(!Contains(address,length))return AdditionalWindow!=null && AdditionalWindow.TryRead(address,length,out bytes);
            accessed=true;
            bytes=new byte[length];
            Array.Copy(contents,(int)(address-Start),bytes,0,(int)length);
            return true;
        }
        internal bool CanEraseSector(uint address)
        {
            uint sector=address&~0xfffu;
            if(!Contains(sector,4096))return AdditionalWindow!=null && AdditionalWindow.CanEraseSector(address);
            return AllowSectorErase;
        }
        internal bool TryEraseSector(uint address)
        {
            if(!Contains(address&~0xfffu,4096))return AdditionalWindow!=null && AdditionalWindow.TryEraseSector(address);
            if(!CanEraseSector(address))return false;
            accessed=true;
            uint offset=(address&~0xfffu)-Start;
            for(uint i=0;i<4096;i++)contents[offset+i]=255;
            return true;
        }
        internal bool CanProgramPage(uint address,uint length)
        {
            if(length==0 || length>256)return false;
            if(!ContainsPage(address,length))return AdditionalWindow!=null && AdditionalWindow.CanProgramPage(address,length);
            return AllowPageProgram;
        }
        private bool Contains(uint address,uint length) => length!=0 && address>=Start && (ulong)address+length<=(ulong)Start+Length;
        private bool ContainsPage(uint address,uint length)
        {
            uint page=address&~255u;
            for(uint i=0;i<length;i++)
            {
                uint target=page|(((address&255u)+i)&255u);
                if(target<Start || (ulong)target>=(ulong)Start+Length)return false;
            }
            return true;
        }
        internal bool TryProgramPage(uint address,byte[] bytes)
        {
            if(bytes==null || bytes.Length==0 || bytes.Length>256)return false;
            if(!ContainsPage(address,(uint)bytes.Length))return AdditionalWindow!=null && AdditionalWindow.TryProgramPage(address,bytes);
            if(!CanProgramPage(address,(uint)bytes.Length))return false;
            accessed=true;
            uint page=address&~255u;
            for(uint i=0;i<(uint)bytes.Length;i++)contents[(page|(((address&255u)+i)&255u))-Start]&=bytes[i];
            return true;
        }
        // This emulator reset preserves committed NOR bytes, as distinct from volatile controller state.
        public void Reset() { }
        public void LoadCommittedImage(byte[] image)
        {
            if(image==null || image.Length!=contents.Length)throw new ArgumentException("Snapshot extent differs from NOR window");
            if(accessed || SnapshotLoaded)throw new InvalidOperationException("NOR snapshot loading requires a fresh unused window");
            Array.Copy(image,contents,image.Length);
            SnapshotLoaded=true;
        }
        public bool SnapshotLoaded {get;private set;}
        private bool accessed;
        private readonly byte[] contents;
        public bool AllowSectorErase {get;}
        public bool AllowPageProgram {get;}
        public BlackwallNorReadWindow AdditionalWindow {get;}
        public string Profile {get;}
        public uint Start {get;}
        public uint Length {get;}
    }
}
