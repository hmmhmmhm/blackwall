namespace Antmicro.Renode.Peripherals.Miscellaneous
{
using System.Linq;
using Antmicro.Renode.Core;
using Antmicro.Renode.Peripherals;
using Antmicro.Renode.Peripherals.Bus;
using Antmicro.Renode.Peripherals.CPU;
using Antmicro.Renode.Peripherals.SPI;
using Antmicro.Renode.Peripherals.I2C;
using Antmicro.Renode.Core.Structure;
    // Apollo510 boundary around a hash-pinned source-derived, FIFO-corrected polling engine.
    public sealed class BlackwallStrictIom : BlackwallPollingIomEngine, IPeripheral, IDoubleWordPeripheral, IBytePeripheral, IWordPeripheral, IQuadWordPeripheral
    {
        public BlackwallStrictIom(IMachine machine, BlackwallPeripheralPower power, int module=2,int cqInputLevels=-1,bool spiConfigStorage=false,long cqStartupRetentionPc=-1,bool spiDcxNoPinsStorage=false,bool spiFullDuplexPreflight=false,IBlackwallCheckedSpiPeer spiWordPeer=null,int cqStartupRetentionBudget=1,bool cqRetentionPerDisable=false,bool spiReceiveStreaming=false,int i2cNakCommand=-1,bool i2cRecoveryClock=false):base(machine)
        {
            if(module<0 || module>7 || power==null || power.Mask!=(1u<<(module+1))) throw new System.ArgumentException("IOM module/power mismatch");
            if(spiDcxNoPinsStorage && (module!=6 || !spiConfigStorage))throw new System.ArgumentException("DCX without CE routing requires explicit IOM6 SPI storage profile");
            if(spiFullDuplexPreflight && (module!=6 || !spiConfigStorage || !spiDcxNoPinsStorage))throw new System.ArgumentException("Full-duplex preflight requires explicit IOM6 SPI and no-pin DCX profiles");
            if(spiWordPeer!=null && !spiFullDuplexPreflight)throw new System.ArgumentException("SPI word transfer requires the explicit IOM6 full-duplex profile");
            if(spiReceiveStreaming && (module!=6 || !(spiWordPeer is IBlackwallReceiveSpiPeer)))throw new System.ArgumentException("Receive streaming requires an explicit IOM6 receive peer");
            if(i2cNakCommand!=-1 && (i2cNakCommand<1 || module!=4 || !i2cRecoveryClock))throw new System.ArgumentException("Declared NAK fault requires positive command index and IOM4 recovery profile");
            if(i2cRecoveryClock && module!=4)throw new System.ArgumentException("Recovery clock profile is limited to IOM4");
            I2CNakCommand=i2cNakCommand;I2CRecoveryClock=i2cRecoveryClock;
            SpiReceiveStreaming=spiReceiveStreaming;
            SpiFullDuplexPreflight=spiFullDuplexPreflight;
            Module=module; Power=power; SpiConfigStorage=spiConfigStorage;SpiDcxNoPinsStorage=spiDcxNoPinsStorage;
            if(cqStartupRetentionPc!=-1 && (module!=6 || !spiConfigStorage || cqInputLevels!=-1 || cqStartupRetentionPc<0x438000 || cqStartupRetentionPc>=0x800000 || (cqStartupRetentionPc&1)!=0))
                throw new System.ArgumentException("Startup retention requires IOM6, explicit SPI latch, unknown global inputs and pinned aligned original PC");
            if(cqStartupRetentionBudget!=1 && (cqStartupRetentionBudget!=2 || cqStartupRetentionPc<0))throw new System.ArgumentException("Retention budget is one by default or explicit two with pinned context");
            if(cqRetentionPerDisable && (cqStartupRetentionPc<0 || cqStartupRetentionBudget!=1))throw new System.ArgumentException("Per-disable retention requires pinned context and default count profile");
            CqRetentionPerDisable=cqRetentionPerDisable;
            CqStartupRetentionBudget=cqStartupRetentionBudget;
            CqStartupRetentionPc=cqStartupRetentionPc;this.machine=machine;
            CommandQueue=new BlackwallIomCommandQueue(BaseAddress,address=>machine.SystemBus.ReadDoubleWord(address),(offset,value)=>WriteDoubleWord(offset,value),RaiseQueueInterrupt,(offset,operation,value)=>Block(offset,4,operation,value),cqInputLevels);
            if(spiWordPeer!=null)SpiWordTransfer=new BlackwallSpiWordTransfer(spiWordPeer,(o,op,v)=>Block(o,4,op,v),()=>RaiseQueueInterrupt(1),spiReceiveStreaming);
            Power.ShutdownReady=()=>Quiescent;
            Power.PoweredOff+=PowerDown;
            Reset();
        }
        public new void Reset() { base.Reset(); SpiWordTransfer?.Reset(); CommandQueue?.Reset(); DmaTrigger=0; NakInjected=0;recoveryClock=0; RetentionSnapshotReads=RetentionEpoch=0;LastRetentionEpoch=-1;LastRetentionFlags=0; clock=i2cConfig=dcx=0; spiConfig=0x00200000; fifo=2; Reads=Writes=Commands=PowerDowns=AccessCount=I2CConfigurationWrites=0; LastI2CConfiguration=0; LastAddress=LastValue=0; LastWidth=0; LastOperation="none"; }
        private void PowerDown() { base.Reset(); SpiWordTransfer?.Reset(); CommandQueue.PowerDown(); DmaTrigger=0; recoveryClock=0; clock=i2cConfig=dcx=0; spiConfig=0x00200000; fifo=2; PowerDowns++; }
        public void ResetThroughInterface() { ((IPeripheral)this).Reset(); }
        private void RaiseQueueInterrupt(uint mask) { base.WriteDoubleWord(0x20c,mask); }
        public BlackwallIomCommandQueue CommandQueue {get;}
        public bool SpiReceiveStreaming {get;}
        public uint DmaTrigger {get;private set;}
        private void Block(long offset,int width,string operation,ulong value=0)
        {
            AccessCount++; LastAddress=BaseAddress+(ulong)offset; LastWidth=width; LastValue=value; LastOperation=operation;
            throw new CpuAbortException("Blackwall unsupported IOM access "+LastOperation+" @0x"+LastAddress.ToString("x"));
        }
        public void RejectDiagnosticPeerAccess(string operation,uint value)
        {
            if(operation!="peer-read" && operation!="peer-write")throw new System.ArgumentException("Unknown peer diagnostic operation");
            Block(0x120,4,operation,value);
        }
        private void Require(bool condition,long offset,string operation,uint value=0) { if(!condition) Block(offset,4,operation,value); }
        private uint Mask(long offset)
        {
            if(offset>=0 && offset<=0x3c && (offset&3)==0)return 0xffffffffu;
            switch(offset) {
            case 0x100:case 0x108:case 0x10c:case 0x128:case 0x220:case 0x234:case 0x388:return 0xffffffffu;
            case 0x104:return 0x3f3f;case 0x110:case 0x210:return 3;case 0x114:return 0xf0f;
            case 0x118:return 0xffff3f01;case 0x11c:return 0xff;case 0x120:return 0xff3fffff;case 0x124:return 0x1f;case 0x12c:return 0xfffff;
            case 0x200:case 0x204:case 0x208:case 0x20c:return 0x7fff;
            case 0x214:case 0x224:case 0x230:case 0x248:return 7;case 0x218:return 0x303;case 0x21c:return 0xfff;
            case 0x228:return 0xf;case 0x22c:return 0xfffffffc;case 0x238:return 0xffffff;case 0x23c:return 0xffff;
            case 0x240:case 0x244:return 0xff;case 0x280:return 0x7ff70007;case 0x2c0:return 0x1ffff77;case 0x2c4:return 0x3ff;
            default: return 0;
            }
        }
        public new uint ReadDoubleWord(long offset)
        {
            Require(Power.Phase=="on" && Mask(offset)!=0,offset,"read");
            if(SpiWordTransfer!=null)
            {
                if(offset<0x40)Block(offset,4,"spi-direct-fifo-unsupported");
                if(SpiWordTransfer.OwnsRead(offset)) { var result=SpiWordTransfer.Read(offset);Reads++;return result; }
            }
            if(offset==0x234 && TryStartupRetentionFlags(out var flags)) { Reads++;return flags; }
            if(BlackwallIomCommandQueue.Owns(offset)) { var result=CommandQueue.Read(offset); Reads++;return result; }
            Require(offset!=0x214 || DmaTrigger==0,offset,"read");
            if(offset==0x210) { Reads++;return DmaTrigger; }
            if(offset==0x388 && I2CRecoveryClock) { Reads++;return recoveryClock; }
            if(offset==0x124 && SpiDcxNoPinsStorage) { Reads++;return dcx; }
            // DMA execution is unsupported; disabled DMA status is zero.
            uint value=offset>=0x210 && offset<=0x244 ? 0 : offset==0x118 ? clock : offset==0x110 ? fifo : offset==0x2c0 ? i2cConfig : offset==0x280 && SpiConfigStorage ? spiConfig : base.ReadDoubleWord(offset)&Mask(offset);
            Reads++; return value;
        }
        public new void WriteDoubleWord(long offset,uint value)
        {
            Require(Power.Phase=="on" && Mask(offset)!=0,offset,"write",value);
            if(offset==0x208 && value==0xffffffffu)value=0x7fff;
            Require((value&~Mask(offset))==0,offset,"write",value);
            if(offset==0x388 && I2CRecoveryClock)
            {
                Require((value&~2u)==0 && (base.ReadDoubleWord(0x11c)&0x11)==0 && (fifo&2)==0 && (base.ReadDoubleWord(0x12c)&31)==0,offset,"i2c-recovery-clock-unsupported",value);
                recoveryClock=value;Writes++;return;
            }
            Require(!(offset>=0x20 && offset<=0x3c) && offset!=0x100 && offset!=0x108 && offset!=0x114 && offset!=0x12c && offset!=0x204 && offset!=0x248 && offset!=0x388,offset,"write",value);
            if(BlackwallIomCommandQueue.Owns(offset)) { CommandQueue.Write(offset,value); Writes++;return; }
            if(SpiWordTransfer!=null)
            {
                if(offset<0x20)Block(offset,4,"spi-direct-fifo-unsupported",value);
                if(offset==0x110 || offset==0x118 || offset==0x11c || offset==0x124 || offset==0x128 || offset==0x280)Require(!SpiWordTransfer.Active,offset,"spi-config-while-active",value);
                if(offset==0x110) { Require(value==0 || value==2,offset,"spi-fifo-control-unsupported",value);if(value==0)SpiWordTransfer.Reset(); }
                if(offset==0x120)
                {
                    var receiveOnly=(value&15)==2;
                    Require(((spiConfig==4 && !receiveOnly) || (spiConfig==0 && receiveOnly && SpiWordTransfer.SupportsReceive)) && (clock&1)!=0 && fifo==2 && (base.ReadDoubleWord(0x11c)&0x11)==1,offset,"spi-transfer-config-unsupported",value);
                    Require((base.ReadDoubleWord(0x12c)&31)==0,offset,"spi-base-engine-busy",value);
                    SpiWordTransfer.Start(value,receiveOnly);Commands++;Writes++;return;
                }
                if(offset==0x10c) { SpiWordTransfer.Push(value);Writes++;return; }
            }
            if(offset==0x124 && SpiConfigStorage)
            {
                Require(value==0 || (SpiDcxNoPinsStorage && value==0x10),offset,"spi-dcx-unsupported",value);
                if(SpiDcxNoPinsStorage) { dcx=value;Writes++;return; }
            }
            if(offset==0x210) { DmaTrigger=value; Writes++;return; }
            if(offset>=0x214 && offset<=0x224) { Require(value==0,offset,"write",value); Writes++; return; }
            if(offset==0x118) { clock=value; Writes++; return; }
            if(offset==0x11c)
            {
                Require((value&0x11)!=0x11,offset,"write",value);
                Require(((value^base.ReadDoubleWord(0x11c))&0x11)==0 || (base.ReadDoubleWord(0x12c)&31)==0,offset,"write",value);
            }
            if(offset==0x280)
            {
                Require((value&(SpiFullDuplexPreflight ? 0x40d70000u : 0x40d70004u))==0,offset,"write",value);
                if(SpiFullDuplexPreflight)Require(value==0 || value==4,offset,"spi-full-duplex-config-unsupported",value);
                if(SpiConfigStorage) { Require((base.ReadDoubleWord(0x12c)&31)==0,offset,"write",value); spiConfig=value; Writes++; return; }
            }
            if(offset==0x2c0)
            {
                Require((value&2u)==0,offset,"write",value);
                Require((base.ReadDoubleWord(0x12c)&31)==0 || ((value^i2cConfig)&~0x40u)==0,offset,"write",value);
                // Timing/unused fields are explicit configuration storage; only address width drives this untimed engine.
                base.WriteDoubleWord(offset,value&1u); i2cConfig=value; LastI2CConfiguration=value; I2CConfigurationWrites++; Writes++; return;
            }
            if(offset==0x2c4)
            {
                Require(value<=((i2cConfig&1)!=0 ? 0x3ffu:0x7fu),offset,"write",value);
                Require((base.ReadDoubleWord(0x12c)&31)==0 || value==base.ReadDoubleWord(0x2c4),offset,"write",value);
            }
            if(offset==0x120)
            {
                // Capture unsupported SPI before the I2C path or base engine can mutate state.
                Require(!SpiFullDuplexPreflight || (spiConfig&4)==0,offset,"spi-full-duplex-command-unsupported",value);
                var command=value&15;
                Require((clock&1)!=0 && (i2cConfig&4)==0 && (fifo&2)!=0 && (base.ReadDoubleWord(0x11c)&0x11)==0x10 && (command==1 || command==2),offset,"write",value);
                var address=(int)base.ReadDoubleWord(0x2c4);
                Require(address<=((i2cConfig&1)!=0 ? 0x3ff:0x7f),offset,"write",value);
                var peers=(IPeripheralContainer<II2CPeripheral,TypedNumberRegistrationPoint<int>>)this;
                Require(peers.Children.Any(p=>p.RegistrationPoint.Address==address),offset,"write",value);
                Require(((value>>4)&7)<=5 && (command!=2 || ((value>>8)&0xfff)!=0),offset,"write",value);
                Require((base.ReadDoubleWord(0x12c)&31)==0,offset,"write",value);
                Require(command!=1 || ((value>>8)&0xfff)==0 || (base.ReadDoubleWord(0x100)&0xff)!=0,offset,"write",value);
                Commands++;
                if(Commands==I2CNakCommand)
                {
                    // Declared address-phase fault: no peer callback or payload delivery.
                    // Queued FIFO words remain until the original error handler resets them.
                    base.WriteDoubleWord(0x20c,0x10);NakInjected++;Writes++;return;
                }
            }
            if(offset==0x110)fifo=value;
            var disabled=offset==0x11c && (base.ReadDoubleWord(0x11c)&0x11)!=0 && (value&0x11)==0;
            base.WriteDoubleWord(offset,value);if(disabled)RetentionEpoch++; Writes++;
        }
        public bool Quiescent => (SpiWordTransfer==null || SpiWordTransfer.Quiescent) && !CommandQueue.Enabled && (base.ReadDoubleWord(0x248)&6)==4 && (base.ReadDoubleWord(0x12c)&31)==0 && (base.ReadDoubleWord(0x11c)&0x11)==0 && (base.ReadDoubleWord(0x100)&0xff00ff)==0 && !IRQ.IsSet;
        public byte ReadByte(long o) { Block(o,1,"read"); return 0; } public void WriteByte(long o,byte v) { Block(o,1,"write",v); }
        public ushort ReadWord(long o) { Block(o,2,"read"); return 0; } public void WriteWord(long o,ushort v) { Block(o,2,"write",v); }
        public ulong ReadQuadWord(long o) { Block(o,8,"read"); return 0; } public void WriteQuadWord(long o,ulong v) { Block(o,8,"write",v); }
        private bool TryStartupRetentionFlags(out uint value)
        {
            value=0;
            if(CqStartupRetentionPc<0 || (CqRetentionPerDisable ? LastRetentionEpoch==RetentionEpoch : RetentionSnapshotReads>=CqStartupRetentionBudget) || !SpiConfigStorage || spiConfig!=0 || clock!=0x1201 || DmaTrigger!=2
                || (CqRetentionPerDisable && SpiWordTransfer!=null && !SpiWordTransfer.Quiescent)
                || SubmoduleControl!=0x20 || CommandQueue.Configuration!=2 || CommandQueue.SoftwareFlags!=64
                || CommandQueue.PauseEnable!=0 || CommandQueue.IrqMask!=0 || CommandQueue.CurrentIndex!=0 || CommandQueue.EndIndex!=0
                || !machine.SystemBus.TryGetCurrentCPU(out var current))return false;
            var cpu=current as CortexM;
            if(cpu==null || (uint)cpu.PC.RawValue!=CqStartupRetentionPc || (uint)cpu.GetRegister(1).RawValue!=BaseAddress)return false;
            var handle=(uint)cpu.GetRegister(4).RawValue;
            if(handle<0x20000000u || (ulong)handle+0x8a0>0x20080000ul || (handle&3)!=0 || machine.SystemBus.ReadDoubleWord(handle+4)!=6)return false;
            // Source-proven retention-only representative. Does not set global external pin values.
            value=CommandQueue.FlagsForInputLevels(0);LastRetentionFlags=value;LastRetentionEpoch=RetentionEpoch;RetentionSnapshotReads++;return true;
        }
        public bool CqRetentionPerDisable {get;}
        public int RetentionEpoch {get;private set;}
        public int LastRetentionEpoch {get;private set;}
        public int CqStartupRetentionBudget {get;}
        public long CqStartupRetentionPc {get;}
        public int RetentionSnapshotReads {get;private set;}
        public uint LastRetentionFlags {get;private set;}
        private readonly IMachine machine;
        public bool SpiConfigStorage {get;}
        public bool SpiDcxNoPinsStorage {get;}
        public bool SpiFullDuplexPreflight {get;}
        public BlackwallSpiWordTransfer SpiWordTransfer {get;}
        public uint DcxControl=>SpiDcxNoPinsStorage?dcx:base.ReadDoubleWord(0x124)&Mask(0x124);
        public uint SpiConfiguration => SpiConfigStorage ? spiConfig : base.ReadDoubleWord(0x280)&Mask(0x280);
        public uint I2CConfiguration => i2cConfig;
        public int I2CConfigurationWrites {get;private set;}
        public uint LastI2CConfiguration {get;private set;}
        public uint ClockConfiguration => clock;
        public uint FifoControl => fifo;
        public uint SubmoduleControl => base.ReadDoubleWord(0x11c)&0xffu;
        public int Module {get;}
        public ulong BaseAddress => 0x40050000u+(uint)Module*0x1000u;
        public BlackwallPeripheralPower Power {get;}
        public int Reads {get;private set;} public int Writes {get;private set;} public int Commands {get;private set;} public int PowerDowns {get;private set;}
        public int AccessCount {get;private set;} public ulong LastAddress {get;private set;} public int LastWidth {get;private set;} public ulong LastValue {get;private set;} public string LastOperation {get;private set;}
        public uint RecoveryClockValue=>recoveryClock;
        public int I2CNakCommand {get;}
        public bool I2CRecoveryClock {get;}
        public int NakInjected {get;private set;}
        private uint recoveryClock;
        private uint clock,fifo,i2cConfig,spiConfig,dcx;
    }
}

namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using System.Collections.Generic;
    using System.Linq;
    using Antmicro.Renode.Peripherals.SPI;

    public interface IBlackwallCheckedSpiPeer : ISPIPeripheral
    {
        bool CanBegin(int length);
        bool CanExchange(uint word,int length);
        void BeginTransaction(int length);
        void AbortTransaction();
        string Transmitted {get;}
        int Finished {get;}
    }

    public interface IBlackwallReceiveSpiPeer : IBlackwallCheckedSpiPeer
    {
        bool CanReceive(int length);
        void BeginReceive(int length);
    }

    // Untimed CMD-before-FIFO transactions; FIFO storage is padded to words,
    // while only TSIZE bytes reach the peer. No offsets/CONT/other CE modes.
    public sealed class BlackwallSpiWordTransfer
    {
        public BlackwallSpiWordTransfer(IBlackwallCheckedSpiPeer peer,Action<long,string,uint> reject,Action completed,bool streamReceive=false)
        { this.peer=peer;this.reject=reject;this.completed=completed;this.streamReceive=streamReceive; }
        public IBlackwallCheckedSpiPeer Peer=>peer;
        public bool SupportsReceive=>peer is IBlackwallReceiveSpiPeer;
        public bool Active=>Remaining!=0;
        public bool Quiescent=>!Active && receive.Count==0;
        public int Remaining {get;private set;}
        public int ReceiveWords=>receive.Count;
        public uint LastCommand {get;private set;}
        public int Completed {get;private set;}
        public uint LastReceiveWord {get;private set;}
        public int BytesExchanged {get;private set;}
        public bool OwnsRead(long offset)=>offset==0x100 || offset==0x108 || offset==0x120 || offset==0x12c || offset==0x248;
        private void Require(bool valid,long offset,string op,uint value=0) { if(!valid)reject(offset,op,value); }
        public void Reset()
        {
            if(Active)peer.AbortTransaction();
            Remaining=0;LastCommand=LastReceiveWord=0;Completed=BytesExchanged=0;receive.Clear();
            receiveClocking=false;
        }
        public void Start(uint command,bool receiveOnly=false)
        {
            var length=(int)((command>>8)&0xfff);
            Require((command&0xfff000ffu)==(receiveOnly?2u:1u) && length>=1 && (length<=32 || streamReceive && receiveOnly && length<=255),0x120,"spi-command-format-unsupported",command);
            Require(Quiescent,0x120,"spi-command-before-drain",command);
            var receiver=peer as IBlackwallReceiveSpiPeer;
            Require(receiveOnly ? receiver!=null && receiver.CanReceive(length) : peer.CanBegin(length),0x120,"spi-peer-script-unavailable",command);
            if(receiveOnly)receiver.BeginReceive(length);else peer.BeginTransaction(length);
            Remaining=length;LastCommand=command;
            receiveClocking=receiveOnly && streamReceive && length>32;
            if(receiveOnly)RefillReceive();
        }
        public void Push(uint word)
        {
            Require(!receiveClocking,0x10c,"spi-receive-clock-owned",word);
            ExchangeWord(word);
        }
        private void RefillReceive()
        {
            while(Active && receive.Count<8)ExchangeWord(0);
        }
        private void ExchangeWord(uint word)
        {
            Require(Active && receive.Count<8,0x10c,"spi-fifo-push-unsupported",word);
            var length=Math.Min(4,Remaining);
            Require(peer.CanExchange(word,length),0x10c,"spi-peer-word-mismatch",word);
            uint response=0;
            for(var i=0;i<length;i++)response|=(uint)peer.Transmit((byte)(word>>(8*i)))<<(8*i);
            receive.Enqueue(response);LastReceiveWord=response;BytesExchanged+=length;Remaining-=length;
            if(!Active) { peer.FinishTransmission();Completed++;completed(); }
        }
        public uint Read(long offset)
        {
            switch(offset)
            {
                case 0x100:return ((uint)(32-4*receive.Count)<<24)|((uint)(4*receive.Count)<<16)|0x2000u;
                case 0x108:
                    Require(receive.Count!=0,offset,"spi-rx-underflow");
                    var word=receive.Dequeue();
                    if(receiveClocking)RefillReceive();
                    return word;
                case 0x120:return LastCommand;
                case 0x12c:return ((uint)Remaining<<8)|(Active?0xc1u:0x80u);
                case 0x248:return Active?2u:4u;
                default:throw new ArgumentOutOfRangeException(nameof(offset));
            }
        }
        private readonly Queue<uint> receive=new Queue<uint>();
        private readonly IBlackwallCheckedSpiPeer peer;
        private readonly bool streamReceive;
        private bool receiveClocking;
        private readonly Action<long,string,uint> reject;
        private readonly Action completed;
    }

    // Explicit one-transaction scenario, not an EM9305 controller firmware model.
    public sealed class BlackwallScriptedSpiPeer : IBlackwallCheckedSpiPeer
    {
        public BlackwallScriptedSpiPeer(string expectedHex,string responseHex) { SetScenario(expectedHex,responseHex); }
        public void SetScenario(string expectedHex,string responseHex)
        {
            if(Active)throw new ArgumentException("Cannot replace an active SPI scenario");
            var tx=Parse(expectedHex);var rx=Parse(responseHex);
            if(tx.Length!=rx.Length)throw new ArgumentException("SPI scenario lengths differ");
            expected=tx;response=rx;Reset();
        }
        private static byte[] Parse(string hex)
        {
            if(hex==null || hex.Length<2 || hex.Length>64 || hex.Length%2!=0 || hex.Any(c=>!Uri.IsHexDigit(c)))throw new ArgumentException("Expected 1..32 explicit hex bytes");
            return Enumerable.Range(0,hex.Length/2).Select(i=>Convert.ToByte(hex.Substring(2*i,2),16)).ToArray();
        }
        public void Reset() { Active=false;Used=false;Position=Finished=Aborted=0;transmitted.Clear(); }
        public bool CanBegin(int length)=>!Active && !Used && length==expected.Length;
        public bool CanExchange(uint word,int length)=>Active && Position+length<=expected.Length && Enumerable.Range(0,length).All(i=>expected[Position+i]==(byte)(word>>(8*i)));
        public void BeginTransaction(int length)
        {
            if(!CanBegin(length))throw new ArgumentException("SPI scenario unavailable");
            Active=Used=true;
        }
        public byte Transmit(byte data)
        {
            if(!Active || Position>=expected.Length || expected[Position]!=data)throw new ArgumentException("Unexpected SPI byte");
            transmitted.Add(data);return response[Position++];
        }
        public void FinishTransmission()
        {
            if(!Active || Position!=expected.Length)throw new ArgumentException("Incomplete SPI scenario");
            Active=false;Finished++;
        }
        public void AbortTransaction() { if(Active) { Active=false;Aborted++; } }
        public bool Active {get;private set;}
        public bool Used {get;private set;}
        public int Position {get;private set;}
        public int Finished {get;private set;}
        public int Aborted {get;private set;}
        public string Transmitted=>string.Concat(transmitted.Select(b=>b.ToString("x2")));
        private byte[] expected,response;
        private readonly List<byte> transmitted=new List<byte>();
    }
}
