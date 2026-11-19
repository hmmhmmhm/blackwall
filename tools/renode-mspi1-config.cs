namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals.Timers;
    using Antmicro.Renode.Time;
    public interface IBlackwallMspi1Pio : Antmicro.Renode.Peripherals.IPeripheral
    {
        bool Busy {get;}
        bool CommandComplete {get;}
        bool CanPowerDown {get;}
        BlackwallPeripheralPower PowerOwner {get;}
        void PowerDownController();
        bool TryRead(uint offset,out uint value);
        bool TryWriteTx(uint value);
        bool TryWrite(uint value,uint instruction,uint configuration,uint address,uint control1,uint ddr);
    }
    // Source-reset configuration with optional bounded PIO and interrupt adapters.
    public class BlackwallMspi1ConfigStorage : IBlackwallMspi1Config
    {
        public BlackwallMspi1ConfigStorage(string profile, bool commandQueueInit=false, BlackwallMspi1XipGuard xipGuard=null, BlackwallMspi1Interrupts interrupts=null, IBlackwallMspi1Pio pio=null, bool xipTurnaroundStorage=false, bool xipMixedStorage=false, int cqInputLevels=-1, bool xipRestoreStorage=false, ulong baseAddress=0x40061000, bool mspi0Initialization=false, BlackwallPeripheralPower mspi0RetentionPower=null, uint mspi0RetentionReadPc=0, Antmicro.Renode.Core.IMachine machine=null, bool mspi0QueueDma=false, bool completeDma=true)
        {
            if(profile!="source-reset-config")throw new System.ArgumentException("Explicit MSPI1 config profile required");
            if(baseAddress!=0x40060000 && baseAddress!=0x40061000)throw new System.ArgumentException("Explicit MSPI0/1 configuration base required");
            if(mspi0Initialization && (baseAddress!=0x40060000 || !commandQueueInit || interrupts==null))
                throw new System.ArgumentException("MSPI0 initialization requires module0 base, disabled command queue and independent interrupts");
            if(baseAddress==0x40060000 && ((!mspi0Initialization && (commandQueueInit || interrupts!=null)) || xipGuard!=null || (pio!=null && (!mspi0Initialization || !(pio is BlackwallMspi0Tx))) || xipTurnaroundStorage || xipMixedStorage || cqInputLevels!=-1 || xipRestoreStorage))
                throw new System.ArgumentException("MSPI0 supports configuration storage only");
            if(baseAddress==0x40060000 && pio!=null && (mspi0RetentionPower==null
                || !System.Object.ReferenceEquals(pio.PowerOwner,mspi0RetentionPower)
                || !System.Object.ReferenceEquals(((BlackwallMspi0Tx)pio).Interrupts,interrupts)))
                throw new System.ArgumentException("MSPI0 TX requires identical retention power and IRQ owners");
            BaseAddress=baseAddress;Mspi0Initialization=mspi0Initialization;
            if(cqInputLevels < -1 || cqInputLevels>3 || (cqInputLevels>=0 && (!commandQueueInit || pio==null)))throw new System.ArgumentException("CQ mock inputs require 0..3, disabled CQ profile and PIO signal provider; -1 is unknown");
            if(xipRestoreStorage && (xipGuard==null || pio==null || !commandQueueInit))throw new System.ArgumentException("XIP restore storage requires guarded XIP and retained-controller dependencies");
            XipRestoreStorage=xipRestoreStorage;
            CqInputLevels=cqInputLevels;
            CommandQueueInit=commandQueueInit;XipGuard=xipGuard;Interrupts=interrupts;Pio=pio;XipTurnaroundStorage=xipTurnaroundStorage;XipMixedStorage=xipMixedStorage;Reset();
            if(mspi0RetentionPower!=null || mspi0RetentionReadPc!=0)
            {
                if(!mspi0Initialization || machine==null || mspi0RetentionPower==null || mspi0RetentionPower.Mask!=0x4000u
                    || mspi0RetentionPower.OffProfile<0 || mspi0RetentionPower.Phase!="off" || mspi0RetentionPower.ShutdownReady!=null
                    || (mspi0RetentionReadPc&1)!=0 || mspi0RetentionReadPc<0x438000 || mspi0RetentionReadPc>=0x800000)
                    throw new System.ArgumentException("MSPI0 retention requires matching idle power owner, explicit off response, machine and original aligned read PC");
                Mspi0RetentionReadPc=mspi0RetentionReadPc;this.machine=machine;retentionPower=mspi0RetentionPower;
                retentionPower.ShutdownReady=CanPowerDown;retentionPower.PoweredOff+=PowerDownController;
            }
            if(mspi0QueueDma)
            {
                if(Mspi0RetentionReadPc==0 || !(pio is BlackwallMspi0Tx))
                    throw new System.ArgumentException("MSPI0 CQ/DMA requires retained module0 and bounded TX owner");
                QueueDma=new BlackwallMspi0QueueDma(machine,(BlackwallMspi0Tx)pio,interrupts,values,cqValues,completeDma);
            }
        }
        public ulong BaseAddress {get;}
        public bool Owns(ulong address) => address>=BaseAddress && address<BaseAddress+0x1000;
        public void Reset()
        {
            if(QueueDma!=null)QueueDma.Reset();
            ResetRegisters();ControllerPowerDowns=XipRestoreWrites=0;xipRestorePending=false;
            Reads=Writes=CqReads=CqWrites=TurnaroundWrites=MixedWrites=CqFlagReads=LastCqFlags=0;
            if(XipGuard!=null)XipGuard.Reset();
            if(Interrupts!=null)Interrupts.Reset();
            if(Pio!=null)Pio.Reset();
        }
        private void ResetRegisters()
        {
            values.Clear();foreach(var spec in Definitions)values.Add(spec.Offset,spec.Reset);
            cqValues.Clear();foreach(var offset in CqOffsets)cqValues.Add(offset,0);
        }
        // Opt-in hypothesis: external NOR supply survives MCU MSPI1 domain loss.
        public void AttachRetentionPower(BlackwallPeripheralPower power)
        {
            if(retentionPower!=null || power==null || power.Mask!=0x8000 || power.OffProfile<0
                || power.Phase!="off" || power.ShutdownReady!=null || Pio==null || !System.Object.ReferenceEquals(Pio.PowerOwner,power)
                || Interrupts==null || !CommandQueueInit)
                throw new System.ArgumentException("Retained external NOR requires one idle MSPI1 power owner and explicit off response");
            retentionPower=power;power.ShutdownReady=CanPowerDown;power.PoweredOff+=PowerDownController;
        }
        private bool Mspi0EnginesDisabled() => Mspi0RetentionReadPc!=0 && (cqValues[0x2a0]&1u)==0
            && (values[0x100]&1u)==0 && (values[0x90]&1u)==0 && (Pio==null || Pio.CanPowerDown);
        public bool CanPowerDown() => Mspi0RetentionReadPc!=0 ? Mspi0EnginesDisabled()
            && Interrupts.Enable==0 && CqFlagReads>ControllerPowerDowns : Pio!=null && Pio.CanPowerDown && CommandQueueInit
            && (cqValues[0x2a0]&1u)==0 && (values[0x100]&1u)==0
            && (XipGuard==null || XipGuard.AccessCount==0);
        private void PowerDownController()
        {
            if(QueueDma!=null)QueueDma.PowerDown();
            ResetRegisters();if(Pio!=null)Pio.PowerDownController();Interrupts.PowerDown();
            if(XipGuard!=null)XipGuard.Disable();
            xipRestorePending=XipRestoreStorage;
            ControllerPowerDowns++;
        }
        public uint ControllerPowerDowns { get; private set; }
        private BlackwallPeripheralPower retentionPower;
        public BlackwallPeripheralPower RetentionPower => retentionPower;
        public uint Mspi0RetentionReadPc { get; }
        private readonly Antmicro.Renode.Core.IMachine machine;
        public bool TryReadMspi0RetentionFlags(uint pc,uint baseRegister,out uint value)
        {
            value=0;
            if(pc!=Mspi0RetentionReadPc || baseRegister!=0x40060000u || retentionPower==null
                || retentionPower.Phase!="on" || !Mspi0EnginesDisabled())return false;
            // This bounded save/restore path ignores all high flag bits (bw309).
            // Their zero fixture is not a general idle or completion response.
            value=cqValues[0x2b0]&255u;LastCqFlags=value;CqFlagReads++;CqReads++;return true;
        }
        public bool TryRead(ulong address,bool ready,out uint value)
        {
            if(QueueDma!=null)QueueDma.Sync();
            value=0;if(!ready || !Owns(address))return false;
            if(QueueDma!=null && QueueDma.Fault!="")return false;
            var offset=(uint)(address-BaseAddress);
            if(offset==0x104 && QueueDma!=null) { value=QueueDma.DmaStatus;Reads++;return true; }
            if((offset==0 || offset==0x14 || offset==0x18 || offset==0x1c) && Pio!=null)return Pio.TryRead(offset,out value);
            if(Interrupts!=null && BlackwallMspi1Interrupts.Owns(offset))return Interrupts.TryRead(offset,out value);
            if(CommandQueueInit && cqValues.ContainsKey(offset))
            {
                if(Mspi0Initialization && offset==0x2ac && QueueDma==null)return false; // Engine status remains unknown.
                if(offset==0x2b0)
                {
                    if(Mspi0RetentionReadPc!=0)
                    {
                        if(machine.SystemBus.TryGetCurrentCPU(out var current))
                        {
                            var cpu=current as Antmicro.Renode.Peripherals.CPU.CortexM;
                            if(cpu!=null)return TryReadMspi0RetentionFlags((uint)cpu.PC.RawValue,(uint)cpu.GetRegister(1).RawValue,out value);
                        }
                        return false;
                    }
                    if(CqInputLevels<0)return false;
                    var route=(values[0x30]>>4)&15u;
                    if(route>11 && route!=15)return false;
                    var input=route==15 ? 0u:(uint)CqInputLevels; // DISABLED routing hardwires inputs low.
                    var sw=cqValues[offset]&255u;
                    // Explicit mock: each buffer's XOR/XNOR pair uses its corresponding SW bit.
                    // CQ and DMA execution remain unsupported, so STOP and DMACPL stay zero.
                    var x0=(input^sw)&1u;
                    var x1=((input^sw)>>1)&1u;
                    value=sw|((x0^1u)<<8)|((x1^1u)<<9)|(x0<<12)|(x1<<13)
                        |(Pio.CommandComplete ? 0x400u:0u)|(cqValues[0x2c0]==cqValues[0x2c4] ? 0x4000u:0u);
                    LastCqFlags=value;CqFlagReads++;CqReads++;return true;
                }
                value=cqValues[offset];CqReads++;return true;
            }
            if(!values.TryGetValue(offset,out value))return false;
            Reads++;return true;
        }
        public bool TryWrite(ulong address,uint value,bool ready)
        {
            if(QueueDma!=null)QueueDma.Sync();
            if(!ready || !Owns(address))return false;
            var offset=(uint)(address-BaseAddress);
            if(QueueDma!=null && (QueueDma.Fault!="" || (QueueDma.Enabled && offset==0) || (QueueDma.DmaActive && offset<0x200)))return false;
            if(offset==0 && Pio!=null)return Pio.TryWrite(value,values[0xc],values[0x84],values[8],values[4],values[0x88]);
            if(offset==0x10 && Pio!=null)return Pio.TryWriteTx(value);
            if(Pio!=null && Pio.Busy && offset<0x200)return false;
            if(Interrupts!=null && BlackwallMspi1Interrupts.Owns(offset))return Interrupts.TryWrite(offset,value);
            if(CommandQueueInit && (cqValues.ContainsKey(offset) || offset==0x2b4))return TryWriteCq(offset,value);
            Spec selected=null;foreach(var spec in Definitions)if(spec.Offset==offset){selected=spec;break;}
            if(selected==null || (value&~selected.Mask)!=0)return false;
            if(offset==0x30 && (value&0xe0000000u)!=0xc0000000u)return false;
            if(offset==0x100 && (value&1)!=0)return false;
            if(offset==0x9c && (value&0x80000000u)!=0)return false;
            if(offset==0x80 && XipGuard!=null && XipGuard.Enabled && value!=values[offset])return false;
            bool timingChange=false,mixedChange=false;
            if(offset==0x90)
            {
                if((value&1)!=0)
                {
                    if(XipGuard==null)return false;
                    if(xipRestorePending && !XipGuard.Enabled)
                    {
                        // One post-power-loss atomic restore; this never supplies XIP bytes.
                        var mode=(value>>8)&15u;
                        if(((value>>2)&3u)==1u || (mode!=0 && mode!=1 && mode!=3 && mode!=5 && mode!=7 && mode!=9 && mode!=11)
                            || !XipGuard.TryEnable(values[0x80]))return false;
                        xipRestorePending=false;XipRestoreWrites++;
                    }
                    else if((value&~1u)!=(values[offset]&~1u))
                    {
                        var delta=value^values[offset];
                        var allowed=(XipTurnaroundStorage ? 0xfc000u : 0u)|(XipMixedStorage ? 0xf00u : 0u);
                        var mode=(value>>8)&15;
                        if((values[offset]&1)==0 || (delta&~allowed)!=0 || !XipGuard.CanChangeConfiguration(values[0x80]))return false;
                        mixedChange=(delta&0xf00)!=0;
                        if(mixedChange && mode!=0 && mode!=1 && mode!=3 && mode!=5 && mode!=7 && mode!=9 && mode!=11)return false;
                        timingChange=(delta&0xfc000)!=0;
                    }
                    else if(!XipGuard.TryEnable(values[0x80]))return false;
                }
                else if(XipGuard!=null)XipGuard.Disable();
            }
            values[offset]=value;Writes++;if(timingChange)TurnaroundWrites++;if(mixedChange)MixedWrites++;return true;
        }
        public uint Reads { get; private set; }
        public uint Writes { get; private set; }
        public bool CommandQueueInit { get; }
        public bool Mspi0Initialization { get; }
        public bool XipTurnaroundStorage { get; }
        public bool XipMixedStorage { get; }
        public bool XipRestoreStorage { get; }
        public uint XipRestoreWrites { get; private set; }
        private bool xipRestorePending;
        public uint MixedWrites { get; private set; }
        public uint TurnaroundWrites { get; private set; }
        public BlackwallMspi1XipGuard XipGuard { get; }
        public BlackwallMspi1Interrupts Interrupts { get; }
        public IBlackwallMspi1Pio Pio { get; }
        public BlackwallMspi0QueueDma QueueDma { get; }
        public uint CqReads { get; private set; }
        public uint CqWrites { get; private set; }
        public int CqInputLevels { get; }
        public uint CqFlagReads { get; private set; }
        public uint LastCqFlags { get; private set; }
        // CQFLAGS entry holds software flags only; LastCqFlags tracks explicit full reads.
        public System.Collections.Generic.IReadOnlyDictionary<uint,uint> CqValues => cqValues;
        private bool TryWriteCq(uint offset,uint value)
        {
            if(QueueDma!=null && (offset==0x2a0 || QueueDma.Enabled))
            {
                if(!QueueDma.TryWriteCq(offset,value))return false;
                CqWrites++;return true;
            }
            switch(offset)
            {
            case 0x2a0:if((value&~2u)!=0)return false;break; // Priority only; never enable.
            case 0x2a8:if((value&3)!=0)return false;break;
            case 0x2ac:case 0x2b0:return false; // Status/flags are not writable storage.
            case 0x2b8:if((value&~0xffffu)!=0)return false;break;
            case 0x2c0:case 0x2c4:if(value>255)return false;break;
            case 0x2b4:
                var set=value&255u;var toggle=(value>>8)&255u;var clear=(value>>16)&255u;
                if((value&0xff000000u)!=0 || (toggle&(set|clear))!=0)return false;
                cqValues[0x2b0]=((cqValues[0x2b0]&~clear)^toggle)|set;
                CqWrites++;return true;
            default:return false;
            }
            cqValues[offset]=value;CqWrites++;return true;
        }
        public System.Collections.Generic.IReadOnlyDictionary<uint,uint> Values => values;
        private readonly System.Collections.Generic.Dictionary<uint,uint> values=new System.Collections.Generic.Dictionary<uint,uint>();
        private readonly System.Collections.Generic.Dictionary<uint,uint> cqValues=new System.Collections.Generic.Dictionary<uint,uint>();
        private static readonly uint[] CqOffsets={0x2a0,0x2a8,0x2ac,0x2b0,0x2b8,0x2c0,0x2c4};
        private sealed class Spec
        {
            public Spec(uint offset,uint reset,uint mask){Offset=offset;Reset=reset;Mask=mask;}
            public readonly uint Offset,Reset,Mask;
        }
        private static readonly Spec[] Definitions=new Spec[]
        {
            new Spec(0x4u,0x0u,0xfu), // CTRL1
            new Spec(0x8u,0x0u,0xffffffffu), // ADDR
            new Spec(0xcu,0x0u,0xffffu), // INSTR
            new Spec(0x20u,0x0u,0x3f3fu), // THRESHOLD
            new Spec(0x30u,0xc00000f0u,0xe00000f1u), // MSPICFG
            new Spec(0x44u,0x0u,0xc007ffffu), // PADOUTEN
            new Spec(0x48u,0x0u,0x7ffffu), // PADOVEREN
            new Spec(0x4cu,0x0u,0x7ffffu), // PADOVER
            new Spec(0x80u,0x0u,0x1fff001fu), // DEV0AXI
            new Spec(0x84u,0x20001u,0xffffffffu), // DEV0CFG
            new Spec(0x88u,0x0u,0xffffffffu), // DEV0DDR
            new Spec(0x8cu,0x8200u,0x6007ffbfu), // DEV0CFG1
            new Spec(0x90u,0x0u,0x3fffffdu), // DEV0XIP
            new Spec(0x94u,0xb0006u,0xffffffffu), // DEV0INSTR
            new Spec(0x98u,0x0u,0xffffu), // DEV0BOUNDARY
            new Spec(0x9cu,0x0u,0x9fff1fffu), // DEV0SCRAMBLING
            new Spec(0xa0u,0x900au,0x20ffffu), // DEV0XIPMISC
            new Spec(0xa4u,0x219u,0x7ffu), // DEV0XIPCPURQ
            new Spec(0xa8u,0x0u,0x1010101u), // DEV0DDRDLYEXT
            new Spec(0x100u,0x0u,0x6003fu), // DMACFG
            new Spec(0x108u,0x0u,0xffffffffu), // DMATARGADDR
            new Spec(0x10cu,0x0u,0xffffffffu), // DMADEVADDR
            new Spec(0x110u,0x0u,0xffffffu), // DMATOTCOUNT
            new Spec(0x114u,0x20u,0xffu), // DMABCOUNT
            new Spec(0x118u,0x808u,0x1f1fu), // DMATHRESH
        };
    }
    // Renode injects the machine into required constructor parameters.
    public sealed class BlackwallMspi0RetentionConfig : BlackwallMspi1ConfigStorage
    {
        public BlackwallMspi0RetentionConfig(Antmicro.Renode.Core.IMachine machine,
            BlackwallPeripheralPower power,BlackwallMspi1Interrupts interrupts,uint readPc,IBlackwallMspi1Pio pio=null,bool queueDma=false,bool completeDma=true)
            : base("source-reset-config",commandQueueInit:true,interrupts:interrupts,baseAddress:0x40060000,
                   mspi0Initialization:true,mspi0RetentionPower:power,mspi0RetentionReadPc:readPc,machine:machine,pio:pio,mspi0QueueDma:queueDma,completeDma:completeDma) { }
    }
    // Bounded logical transport, not panel/NOR state or measured bus timing.
    public sealed class BlackwallMspi0DmaFrame
    {
        public BlackwallMspi0DmaFrame(uint source,uint deviceAddress,uint configuration,uint instructionConfiguration,uint xipConfiguration,uint pioMixed,byte[] data)
        {
            Source=source;DeviceAddress=deviceAddress;Configuration=configuration;InstructionConfiguration=instructionConfiguration;XipConfiguration=xipConfiguration;PioMixed=pioMixed;
            payload=(byte[])data.Clone();
            using(var hash=System.Security.Cryptography.SHA256.Create())
                PayloadSha256=System.BitConverter.ToString(hash.ComputeHash(payload)).Replace("-","").ToLowerInvariant();
        }
        public uint Source { get; }
        public uint DeviceAddress { get; }
        public uint Configuration { get; }
        public uint InstructionConfiguration { get; }
        public uint XipConfiguration { get; }
        public uint PioMixed { get; }
        public int Length => payload.Length;
        public string PayloadSha256 { get; }
        public string PayloadHex => System.BitConverter.ToString(payload).Replace("-","").ToLowerInvariant();
        private readonly byte[] payload;
    }
    public sealed class BlackwallMspi0QueueDma : Antmicro.Renode.Peripherals.IPeripheral
    {
        public BlackwallMspi0QueueDma(IMachine machine,BlackwallMspi0Tx pio,BlackwallMspi1Interrupts irq,
            System.Collections.Generic.Dictionary<uint,uint> registers,System.Collections.Generic.Dictionary<uint,uint> queue,bool complete)
        {
            this.machine=machine;this.pio=pio;this.irq=irq;this.registers=registers;this.queue=queue;this.complete=complete;
            service=new LimitTimer(machine.ClockSource,1000000,this,"MSPI0-CQ-DMA",1,Direction.Ascending,
                enabled:false,workMode:WorkMode.Periodic,eventEnabled:true);
            service.LimitReached+=Step;Reset();
        }
        private bool Ready => pio.PowerOwner.Phase=="on" && pio.ClockOwner.Mspi0Enabled
            && pio.ClockOwner.Mspi0Selection>=7 && pio.ClockOwner.Mspi0Selection<=10;
        public void Sync()
        {
            if(machine.SystemBus.TryGetCurrentCPU(out var cpu))cpu.SyncTime();
            if(Enabled && (!Ready || (pio.ClockOwner.Value&31u)!=clockField))Reject("power-or-clock-changed");
        }
        public bool TryWriteCq(uint offset,uint value)
        {
            if(Fault!="")return false;
            if(offset==0x2a0)
            {
                if((value&~3u)!=0 || DmaActive)return false;
                if((value&1u)==0)
                {
                    Enabled=Paused=false;service.Enabled=false;queue[offset]=value;queue[0x2ac]=0;return true;
                }
                EnableState="pause="+queue[0x2b8].ToString("x")+",sw="+queue[0x2b0].ToString("x")
                    +",dma="+registers[0x100].ToString("x")+",xip="+registers[0x90].ToString("x");
                bool supportedPause=queue[0x2b8]==0x4000u || (queue[0x2b8]==0x4080u && (queue[0x2b0]&0x80u)!=0);
                if(Enabled || !Ready || pio.Busy || !RamRange(queue[0x2a8],8) || (queue[0x2a8]&3u)!=0
                    || !supportedPause || (registers[0x100]&3u)!=0 || (registers[0x90]&1u)!=0)return false;
                Enabled=true;Paused=false;queue[offset]=value;queue[0x2ac]=1;clockField=pio.ClockOwner.Value&31u;
                fetchedThisRun=0;service.ResetValue();service.Enabled=true;return true;
            }
            if(offset==0x2c4 && Paused && value<=255u)
            {
                queue[offset]=value;
                if(queue[0x2c0]!=value) { Paused=false;queue[0x2ac]=1;service.Enabled=true; }
                return true;
            }
            return false;
        }
        private static bool RamRange(uint address,uint length) => length>0 && address>=0x20000000u
            && (ulong)address+length<=0x20380000UL;
        private void Reject(string reason)
        {
            if(Fault!="")return;
            Fault=reason;if(Enabled || DmaActive)Aborted++;
            service.Enabled=false;Enabled=Paused=DmaActive=false;payload.Clear();
            // Model rejection: no fabricated hardware fault IRQ or completion/index.
        }
        private void Pause()
        {
            if(!Paused)irq.SetPending(0x400u);
            Paused=true;queue[0x2ac]=9;service.Enabled=false;
        }
        private void Step()
        {
            if(!Enabled || Fault!="") { service.Enabled=false;return; }
            if(!Ready || (pio.ClockOwner.Value&31u)!=clockField) { Reject("power-or-clock-changed");return; }
            if(DmaActive)
            {
                if(!complete)return;
                uint count=System.Math.Min(256u,dmaCount-(uint)payload.Count);
                var bytes=machine.SystemBus.ReadBytes(dmaSource+(uint)payload.Count,(int)count);
                if(bytes.Length!=(int)count) { Reject("short-dma-read");return; }
                payload.AddRange(bytes);BytesConsumed+=count;
                if(payload.Count==dmaCount)
                {
                    frames.Add(new BlackwallMspi0DmaFrame(dmaSource,dmaDevice,dmaConfiguration,dmaInstruction,dmaXip,dmaPioMixed,payload.ToArray()));
                    capturedBytes+=dmaCount;DmaActive=false;DmaStatus=2;Completions++;irq.SetPending(0x40u);
                }
                return;
            }
            // This profile only handles the observed index pause and SW7-high preamble.
            uint mask=queue[0x2b8];
            if(mask!=0x4000u && !(mask==0x4080u && (queue[0x2b0]&0x80u)!=0))
            { Reject("unsupported-pause-mask-or-software-level");return; }
            if(queue[0x2c0]==queue[0x2c4]) { Pause();return; }
            uint address=queue[0x2a8];
            if(!RamRange(address,8) || (address&3u)!=0 || fetchedThisRun>=128)
            { Reject("queue-fetch-range-or-limit");return; }
            uint destination=machine.SystemBus.ReadDoubleWord(address);
            uint value=machine.SystemBus.ReadDoubleWord(address+4);
            if(!ExecuteDescriptor(destination,value))return;
            queue[0x2a8]=address+8;Descriptors++;fetchedThisRun++;
            if((destination&1u)!=0)irq.SetPending(0x200u);
            if(!DmaActive && queue[0x2c0]==queue[0x2c4])Pause();
        }
        private bool ExecuteDescriptor(uint destination,uint value)
        {
            switch(destination)
            {
            case 0x400602b8:
                if(value!=0x4000u && !(value==0x4080u && (queue[0x2b0]&0x80u)!=0))break;
                queue[0x2b8]=value;return true;
            case 0x40060108:
                if(!RamRange(value,1))break;registers[0x108]=value;return true;
            case 0x4006010c:registers[0x10c]=value;return true;
            case 0x40060110:
                if(value==0 || value>0x400000u)break;registers[0x110]=value;return true;
            case 0x40060100:
                if(value==0) { registers[0x100]=0;return true; }
                uint count=registers[0x110];
                if(value!=0x17u || !RamRange(registers[0x108],count) || frames.Count>=64 || capturedBytes+count>0x400000u
                    || (registers[0x84]&31u)!=1u || (registers[0x88]&31u)!=0 || pio.Busy
                    || (registers[4]!=0 && registers[4]!=5) || ((registers[0x90]>>8)&15u)!=registers[4])break;
                dmaSource=registers[0x108];dmaDevice=registers[0x10c];dmaCount=count;
                dmaConfiguration=registers[0x84];dmaInstruction=registers[0x94];dmaXip=registers[0x90];dmaPioMixed=registers[4];
                payload.Clear();DmaActive=true;DmaStatus=1;Starts++;registers[0x100]=value;return true;
            case 0x400602b4:
                if(value!=0)break;return true;
            case 0x400602c1:
                if(value>255u || value!=queue[0x2c4])break;queue[0x2c0]=value;return true;
            }
            Reject("unsupported-descriptor");return false;
        }
        public void Reset()
        {
            service.Enabled=false;service.ResetValue();Enabled=Paused=DmaActive=false;Fault="";EnableState="";
            Starts=Completions=Aborted=Descriptors=BytesConsumed=DmaStatus=capturedBytes=fetchedThisRun=0;
            dmaSource=dmaDevice=dmaCount=dmaConfiguration=dmaInstruction=dmaXip=dmaPioMixed=clockField=0;frames.Clear();payload.Clear();
        }
        public void PowerDown() { service.Enabled=false;Enabled=Paused=DmaActive=false;DmaStatus=0;payload.Clear(); }
        public bool Enabled { get; private set; }
        public bool Paused { get; private set; }
        public bool DmaActive { get; private set; }
        public string Fault { get; private set; }
        public string EnableState { get; private set; }
        public uint DmaStatus { get; private set; }
        public uint Starts { get; private set; }
        public uint Completions { get; private set; }
        public uint Aborted { get; private set; }
        public uint Descriptors { get; private set; }
        public uint BytesConsumed { get; private set; }
        public System.Collections.Generic.IReadOnlyList<BlackwallMspi0DmaFrame> Frames => frames;
        private readonly IMachine machine;
        private readonly BlackwallMspi0Tx pio;
        private readonly BlackwallMspi1Interrupts irq;
        private readonly LimitTimer service;
        private readonly bool complete;
        private readonly System.Collections.Generic.Dictionary<uint,uint> registers,queue;
        private readonly System.Collections.Generic.List<BlackwallMspi0DmaFrame> frames=new System.Collections.Generic.List<BlackwallMspi0DmaFrame>();
        private readonly System.Collections.Generic.List<byte> payload=new System.Collections.Generic.List<byte>();
        private uint dmaSource,dmaDevice,dmaCount,dmaConfiguration,dmaInstruction,dmaXip,dmaPioMixed,clockField,capturedBytes,fetchedThisRun;
    }
    public sealed class BlackwallMspi0TxFrame
    {
        public BlackwallMspi0TxFrame(uint control,uint instruction,uint address,uint configuration,byte[] payload)
        {
            Control=control;Instruction=instruction;Address=address;Configuration=configuration;
            PayloadHex=System.BitConverter.ToString(payload).Replace("-","").ToLowerInvariant();
        }
        public uint Control { get; }
        public uint Instruction { get; }
        public uint Address { get; }
        public uint Configuration { get; }
        public string PayloadHex { get; }
    }
    // Logical TX transport with optional explicitly supplied diagnostic RX bytes.
    public sealed class BlackwallMspi0Tx : IBlackwallMspi1Pio
    {
        public BlackwallMspi0Tx(IMachine machine,string profile,BlackwallPeripheralPower power,
            BlackwallMspi1ClockStorage clock,BlackwallMspi1Interrupts interrupts,bool completeTransactions=true,string diagnosticRxHex="",bool completeReceive=true,string jbdStatusHex="")
        {
            if(machine==null || profile!="tx-capture" || power==null || power.Mask!=0x4000u || clock==null
                || !clock.Mspi0Storage || interrupts==null || !interrupts.AllowAllClear)
                throw new System.ArgumentException("Explicit MSPI0 TX power, clock and all-clear IRQ dependencies required");
            if(!string.IsNullOrEmpty(diagnosticRxHex))
            {
                if(diagnosticRxHex.Length!=8)throw new System.ArgumentException("Explicit four-byte diagnostic RX hex required");
                diagnostic=new byte[4];
                try { for(int n=0;n<4;n++)diagnostic[n]=System.Convert.ToByte(diagnosticRxHex.Substring(n*2,2),16); }
                catch(System.Exception) { throw new System.ArgumentException("Explicit four-byte diagnostic RX hex required"); }
            }
            if(!string.IsNullOrEmpty(jbdStatusHex))
            {
                if(jbdStatusHex.Length!=4)throw new System.ArgumentException("Explicit two-byte JBD status hex required");
                jbdStatus=new byte[2];
                try { for(int n=0;n<2;n++)jbdStatus[n]=System.Convert.ToByte(jbdStatusHex.Substring(n*2,2),16); }
                catch(System.Exception) { throw new System.ArgumentException("Explicit two-byte JBD status hex required"); }
            }
            JbdStatusHex=jbdStatusHex==null ? "":jbdStatusHex.ToLowerInvariant();
            DiagnosticRxHex=diagnosticRxHex==null ? "":diagnosticRxHex.ToLowerInvariant();CompleteReceive=completeReceive;
            this.machine=machine;PowerOwner=power;this.clock=clock;Interrupts=interrupts;CompleteTransactions=completeTransactions;
            service=new LimitTimer(machine.ClockSource,1000000,this,"MSPI0-TX",1,Direction.Ascending,
                enabled:false,workMode:WorkMode.Periodic,eventEnabled:true);
            service.LimitReached+=Drain;Reset();
        }
        private bool Ready => PowerOwner.Phase=="on" && clock.Mspi0Enabled
            && clock.Mspi0Selection>=7 && clock.Mspi0Selection<=10;
        private void SyncTime()
        {
            if(machine.SystemBus.TryGetCurrentCPU(out var cpu))cpu.SyncTime();
            if(busy && (!Ready || (clock.Value&0x1fu)!=clockField))Abort();
        }
        public bool TryRead(uint offset,out uint value)
        {
            SyncTime();value=0;if(!Ready)return false;
            if(offset==0)value=Control;
            else if(offset==0x18)value=(uint)fifo.Count;
            else if(offset==0x1c && (diagnostic!=null || jbdStatus!=null))value=rxReady ? 1u:0u;
            else if(offset==0x14 && rxReady)
            {
                for(int n=0;n<receivePayload.Length;n++)value|=(uint)receivePayload[n]<<(8*n);
                rxReady=false;RxReads++;RxBytesDelivered+=(uint)receivePayload.Length;
            }
            else return false;
            Reads++;return true;
        }
        public bool TryWrite(uint value,uint instruction,uint configuration,uint address,uint control1,uint ddr)
        {
            SyncTime();if(!Ready || busy || rxReady)return false;
            if(value==2) { Control&=~2u;Writes++;return true; }
            byte[] reply=null;
            if(value==0x40441u && instruction==0x9fu && diagnostic!=null)reply=diagnostic;
            else if(value==0x10441u && (instruction==5u || instruction==0x35u) && jbdStatus!=null)
                reply=new byte[]{jbdStatus[instruction==5u ? 0:1]};
            if(reply!=null)
            {
                if((configuration&31u)!=1u || control1!=0 || (ddr&31u)!=0 || receiveFrames.Count>=4096)return false;
                requestControl=value;requestInstruction=instruction;requestAddress=0;requestConfiguration=configuration;
                receivePayload=reply;clockField=clock.Value&31u;receiving=true;rxReady=false;busy=true;RxStarts++;Writes++;
                Control=(value&~7u)|4u;service.ResetValue();service.Enabled=true;return true;
            }
            uint count=value>>16;
            if((value&0xffffu&~0xe1u)!=0 || (value&0x81u)!=0x81u || (configuration&31u)!=1u
                || control1!=0 || (ddr&31u)!=0 || ((configuration&0x80u)==0 && instruction>255)
                || instruction>65535 || (count==0 && (value&0x60u)==0)
                || capturedBytes+count>0x400000u || frames.Count>=4096)return false;
            requestControl=value;requestInstruction=(value&0x40u)!=0 ? instruction:0;
            requestAddress=(value&0x20u)!=0 ? address:0;requestConfiguration=configuration;
            expected=count;accepted=0;fifo.Clear();payload.Clear();clockField=clock.Value&0x1fu;
            receiving=false;busy=true;Control=(value&~7u)|4u;Starts++;Writes++;
            service.ResetValue();service.Enabled=CompleteTransactions;return true;
        }
        public bool TryWriteTx(uint value)
        {
            SyncTime();if(!Ready || !busy || receiving || accepted>=expected || fifo.Count>=16)return false;
            fifo.Enqueue(value);accepted+=System.Math.Min(4u,expected-accepted);FifoWrites++;return true;
        }
        private void Drain()
        {
            if(!busy) { service.Enabled=false;return; }
            if(!Ready || (clock.Value&0x1fu)!=clockField) { Abort();return; }
            if(receiving)
            {
                rxReady=true;service.Enabled=false;
                if(CompleteReceive)
                {
                    busy=false;Control=(requestControl&~7u)|2u;RxCompletions++;
                    receiveFrames.Add(new BlackwallMspi0TxFrame(requestControl,requestInstruction,requestAddress,requestConfiguration,receivePayload));
                    Interrupts.SetPending(1);
                }
                return;
            }
            // Explicit 1us/word service hypothesis, not a measured serial bit rate.
            if(fifo.Count!=0)
            {
                uint word=fifo.Dequeue();uint count=System.Math.Min(4u,expected-(uint)payload.Count);
                for(int n=0;n<count;n++)payload.Add((byte)(word>>(n*8)));
                BytesShifted+=count;
            }
            if(accepted==expected && (uint)payload.Count==expected && fifo.Count==0)
            {
                frames.Add(new BlackwallMspi0TxFrame(requestControl,requestInstruction,requestAddress,requestConfiguration,payload.ToArray()));
                capturedBytes+=expected;busy=false;service.Enabled=false;
                Control=(requestControl&~7u)|2u;Completions++;Interrupts.SetPending(1);
            }
        }
        private void Abort()
        {
            service.Enabled=false;busy=false;Control=0;fifo.Clear();payload.Clear();rxReady=false;
            if(receiving)RxAborted++;else Aborted++;receiving=false;
        }
        public void Reset()
        {
            service.Enabled=false;service.ResetValue();fifo.Clear();payload.Clear();frames.Clear();receiveFrames.Clear();busy=receiving=rxReady=false;
            RxStarts=RxCompletions=RxAborted=RxReads=RxBytesDelivered=0;
            Control=Starts=Completions=Aborted=Reads=Writes=FifoWrites=BytesShifted=capturedBytes=0;
            expected=accepted=clockField=requestControl=requestInstruction=requestAddress=requestConfiguration=0;
        }
        public void PowerDownController()
        {
            if(busy)Abort();service.Enabled=false;fifo.Clear();payload.Clear();Control=0;receiving=rxReady=false;
        }
        public bool Busy { get { SyncTime();return busy; } }
        public bool CommandComplete { get { SyncTime();return (Control&2u)!=0; } }
        public bool CanPowerDown { get { SyncTime();return !busy && !rxReady && fifo.Count==0; } }
        public uint TxEntries { get { SyncTime();return (uint)fifo.Count; } }
        public uint Control { get; private set; }
        public uint Starts { get; private set; }
        public uint Completions { get; private set; }
        public uint Aborted { get; private set; }
        public uint Reads { get; private set; }
        public uint Writes { get; private set; }
        public uint FifoWrites { get; private set; }
        public uint BytesShifted { get; private set; }
        public bool CompleteTransactions { get; }
        public string DiagnosticRxHex { get; }
        public string JbdStatusHex { get; }
        public bool CompleteReceive { get; }
        public uint RxStarts { get; private set; }
        public uint RxCompletions { get; private set; }
        public uint RxAborted { get; private set; }
        public uint RxReads { get; private set; }
        public uint RxBytesDelivered { get; private set; }
        public System.Collections.Generic.IReadOnlyList<BlackwallMspi0TxFrame> ReceiveFrames => receiveFrames;
        public BlackwallPeripheralPower PowerOwner { get; }
        public BlackwallMspi1ClockStorage ClockOwner => clock;
        public BlackwallMspi1Interrupts Interrupts { get; }
        public System.Collections.Generic.IReadOnlyList<BlackwallMspi0TxFrame> Frames => frames;
        private readonly IMachine machine;
        private readonly BlackwallMspi1ClockStorage clock;
        private readonly LimitTimer service;
        private readonly System.Collections.Generic.Queue<uint> fifo=new System.Collections.Generic.Queue<uint>();
        private readonly System.Collections.Generic.List<byte> payload=new System.Collections.Generic.List<byte>();
        private readonly System.Collections.Generic.List<BlackwallMspi0TxFrame> frames=new System.Collections.Generic.List<BlackwallMspi0TxFrame>();
        private readonly byte[] diagnostic,jbdStatus;
        private byte[] receivePayload;
        private readonly System.Collections.Generic.List<BlackwallMspi0TxFrame> receiveFrames=new System.Collections.Generic.List<BlackwallMspi0TxFrame>();
        private bool busy,receiving,rxReady;
        private uint expected,accepted,clockField,requestControl,requestInstruction,requestAddress,requestConfiguration,capturedBytes;
    }
    public sealed class BlackwallMspi1Interrupts : Antmicro.Renode.Peripherals.IPeripheral
    {
        public BlackwallMspi1Interrupts(string profile, bool allowAllClear=false)
        {
            if(profile!="source-reset")throw new System.ArgumentException("Explicit MSPI1 interrupt profile required");
            AllowAllClear=allowAllClear;IRQ=new Antmicro.Renode.Core.GPIO();Reset();
        }
        public void Reset() { Enable=Status=Reads=Writes=ClearAllWrites=0;IRQ.Unset(); }
        public void PowerDown() { Enable=Status=0;IRQ.Unset(); }
        public static bool Owns(uint offset) => offset>=0x200 && offset<=0x20c && (offset&3)==0;
        public bool TryRead(uint offset,out uint value)
        {
            value=0;if(offset==0x200)value=Enable;else if(offset==0x204)value=Status;else return false;
            Reads++;return true;
        }
        public bool TryWrite(uint offset,uint value)
        {
            // HAL AM_HAL_MSPI_INT_ALL is an explicit command, not general reserved-bit tolerance.
            bool allClear=AllowAllClear && offset==0x208 && value==0xffffffffu;
            if(allClear)value=0x3fffu;
            if((value&~0x3fffu)!=0)return false;
            switch(offset)
            {
            case 0x200:Enable=value;break;
            case 0x208:Status&=~value;break;
            case 0x20c:Status|=value;break;
            default:return false;
            }
            Writes++;if(allClear)ClearAllWrites++;IRQ.Set((Enable&Status)!=0);return true;
        }
        public bool AllowAllClear { get; private set; }
        public uint ClearAllWrites { get; private set; }
        public void SetPending(uint mask)
        {
            if((mask&~0x3fffu)!=0)throw new System.ArgumentException("Unknown MSPI interrupt event");
            Status|=mask;IRQ.Set((Enable&Status)!=0);
        }
        public uint Enable { get; private set; }
        public uint Status { get; private set; }
        public uint Reads { get; private set; }
        public uint Writes { get; private set; }
        public Antmicro.Renode.Core.GPIO IRQ { get; }
    }
    // No general XIP backing. The opt-in diagnostic supplies only two invalid magic words.
    public sealed class BlackwallMspi1XipGuard : BlackwallStrictMMIO
    {
        public BlackwallMspi1XipGuard(Antmicro.Renode.Core.IMachine machine,
            BlackwallPeripheralPower power, IBlackwallMspi1Clock clock, string fontHeaderProfile=null,
            uint primaryHeaderReadPc=0, uint secondaryHeaderReadPc=0)
            : base(0x4000000,0x80000000)
        {
            if(power==null || power.Mask!=0x8000 || clock==null)throw new System.ArgumentException("MSPI1 XIP guard requires matching power and clock");
            if(fontHeaderProfile!=null && (fontHeaderProfile!="missing-font-magic-only" || machine==null
                || (primaryHeaderReadPc&1)!=0 || (secondaryHeaderReadPc&1)!=0
                || primaryHeaderReadPc<0x438000 || primaryHeaderReadPc>=0x800000
                || secondaryHeaderReadPc<0x438000 || secondaryHeaderReadPc>=0x800000
                || primaryHeaderReadPc==secondaryHeaderReadPc))
                throw new System.ArgumentException("Missing-font diagnostic requires explicit profile, machine and distinct original read PCs");
            if(fontHeaderProfile==null && (primaryHeaderReadPc!=0 || secondaryHeaderReadPc!=0))
                throw new System.ArgumentException("Missing-font diagnostic requires explicit profile");
            this.power=power;this.clock=clock;this.machine=machine;FontHeaderProfile=fontHeaderProfile;
            PrimaryHeaderReadPc=primaryHeaderReadPc;SecondaryHeaderReadPc=secondaryHeaderReadPc;Reset();
        }
        public override void Reset() { base.Reset();Enabled=false;EnableRequests=Transitions=0;FontHeaderReads=LastFontHeaderPc=0; }
        public bool TryReadMissingFontHeader(long offset,uint pc,uint baseRegister,out uint value)
        {
            value=0;
            if(FontHeaderProfile==null || !CanChangeConfiguration(0x19) || FontHeaderReads>=2)return false;
            var expectedOffset=FontHeaderReads==0 ? 0x100000L:0x700000L;
            var expectedPc=FontHeaderReads==0 ? PrimaryHeaderReadPc:SecondaryHeaderReadPc;
            if(offset!=expectedOffset || pc!=expectedPc || baseRegister!=0x80000000u+(uint)expectedOffset)return false;
            value=0xffffffff;FontHeaderReads++;LastFontHeaderPc=pc;return true;
        }
        public override uint ReadDoubleWord(long offset)
        {
            if(FontHeaderProfile!=null && machine.SystemBus.TryGetCurrentCPU(out var current))
            {
                var cpu=current as Antmicro.Renode.Peripherals.CPU.CortexM;
                if(cpu!=null && TryReadMissingFontHeader(offset,(uint)cpu.PC.RawValue,(uint)cpu.GetRegister(4).RawValue,out var value))return value;
            }
            return base.ReadDoubleWord(offset);
        }
        public string FontHeaderProfile { get; }
        public uint PrimaryHeaderReadPc { get; }
        public uint SecondaryHeaderReadPc { get; }
        public uint FontHeaderReads { get; private set; }
        public uint LastFontHeaderPc { get; private set; }
        private bool Ready(uint axi) => axi==0x19 && power.Phase=="on" && clock.Enabled && (clock.Selection==7 || clock.Selection==8);
        public bool CanChangeConfiguration(uint axi) => Enabled && Ready(axi);
        public bool TryEnable(uint axi)
        {
            if(!Ready(axi))return false;
            EnableRequests++;if(!Enabled){Enabled=true;Transitions++;}return true;
        }
        public void Disable() { if(Enabled){Enabled=false;Transitions++;} }
        public bool Enabled { get; private set; }
        public uint EnableRequests { get; private set; }
        public uint Transitions { get; private set; }
        public ulong ApertureBase => 0x80000000;
        public ulong ApertureLength => 0x2000000;
        private readonly BlackwallPeripheralPower power;
        private readonly IBlackwallMspi1Clock clock;
        private readonly Antmicro.Renode.Core.IMachine machine;
    }
}
