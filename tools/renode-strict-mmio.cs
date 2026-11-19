using Antmicro.Renode.Peripherals;
using Antmicro.Renode.Core;
using Antmicro.Renode.Peripherals.Timers;
using Antmicro.Renode.Time;
using Antmicro.Renode.Peripherals.Bus;
using Antmicro.Renode.Peripherals.CPU;
using System.Linq;

namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    public interface IBlackwallGpuCommandDevice : IPeripheral
    {
        void Submit(uint ringBase,uint ringBytes,uint doorbell);
        void AcknowledgeInterrupt();
        void BeginEpoch();
        uint CompletedId { get; }
        bool HasPendingWork { get; }
    }
    public interface IBlackwallEm9305Reset : IPeripheral
    {
        void Attach(BlackwallGpioOutputLatch output);
        bool TryRead(ulong address,uint configuration,out uint value);
    }
    public interface IBlackwallMspi1Config : IPeripheral
    {
        bool Owns(ulong address);
        bool TryRead(ulong address, bool ready, out uint value);
        bool TryWrite(ulong address, uint value, bool ready);
        BlackwallPeripheralPower RetentionPower { get; }
        uint Reads { get; }
        uint Writes { get; }
        System.Collections.Generic.IReadOnlyDictionary<uint,uint> Values { get; }
    }
    public interface IBlackwallMspi1Clock : IPeripheral
    {
        uint Read();
        bool TryWrite(uint value);
        uint Value { get; }
        uint Reads { get; }
        uint Writes { get; }
        bool Enabled { get; }
        uint Selection { get; }
    }
    public interface IBlackwallTimer14 : IPeripheral
    {
        bool Owns(ulong address);
        bool TryRead(ulong address,out uint value);
        bool TryWrite(ulong address,uint value);
    }
    public interface IBlackwallStimer : IPeripheral
    {
        bool Owns(ulong address);
        bool TryRead(ulong address,out uint value);
        bool TryWrite(ulong address,uint value);
    }
    // Optional mapped clock model; the startup fixture does not depend on its engine implementation.
    public interface IBlackwallRtc : IPeripheral, IDoubleWordPeripheral
    {
        bool Owns(ulong address);
    }
    public class BlackwallStrictMMIO : IBytePeripheral, IWordPeripheral,
        IDoubleWordPeripheral, IQuadWordPeripheral, IKnownSize
    {
        public BlackwallStrictMMIO(long size, ulong baseAddress)
        {
            Size = size;
            this.baseAddress = baseAddress;
            ClearAccess();
        }

        public virtual void Reset() { ClearAccess(); }

        private void ClearAccess()
        {
            AccessCount = 0;
            LastAddress = 0;
            LastWidth = 0;
            LastValue = 0;
            LastOperation = "none";
        }

        private void Stop(long offset, int width, string operation, ulong value = 0)
        {
            AccessCount++;
            LastAddress = baseAddress + (ulong)offset;
            LastWidth = width;
            LastOperation = operation;
            LastValue = value;
            throw new CpuAbortException($"BLACKWALL unsupported {operation} at 0x{LastAddress:x}, width {width}");
        }

        public byte ReadByte(long offset) { Stop(offset, 1, "read"); return 0; }
        public ushort ReadWord(long offset) { Stop(offset, 2, "read"); return 0; }
        public virtual uint ReadDoubleWord(long offset) { Stop(offset, 4, "read"); return 0; }
        public ulong ReadQuadWord(long offset) { Stop(offset, 8, "read"); return 0; }
        public void WriteByte(long offset, byte value) { Stop(offset, 1, "write", value); }
        public void WriteWord(long offset, ushort value) { Stop(offset, 2, "write", value); }
        public virtual void WriteDoubleWord(long offset, uint value) { Stop(offset, 4, "write", value); }
        public void WriteQuadWord(long offset, ulong value) { Stop(offset, 8, "write", value); }

        public long Size { get; }
        public int AccessCount { get; private set; }
        public ulong LastAddress { get; private set; }
        public int LastWidth { get; private set; }
        public ulong LastValue { get; private set; }
        public string LastOperation { get; private set; }
        protected readonly ulong baseAddress;
    }

    public sealed class BlackwallG2StartupFixture : BlackwallStrictMMIO
    {
        public BlackwallG2StartupFixture(long size, ulong baseAddress, string powerMode = "none", int resetLatch = -1, bool startupControls = false, string shadowInfo1 = "none", string info1Metadata = "none", int chipRevision = -1, bool spotStorage = false, bool memoryStartup = false, bool halStorage = false, bool mramControlStorage = false, bool buckOverrideStorage = false, bool buckStartStorage = false, bool coreLdoReduction = false, bool memLdoSetup = false, int buckStatusFixture = -1, bool prefetchStorage = false, int buckResponse = -1, bool vddfTempcoStorage = false, int mcuClockResponse = -1, bool gfxPowerStorage = false, bool hfrcForceControl = false, bool gpuPowerPreparation = false, int gpuPowerResponse = -1, bool gpuInterruptClear = false, BlackwallG2StartupFixture gpuControlOwner = null, bool gpuIdInitialization = false, bool gpuRingConfiguration = false, int gpuIdentityResponse = -1, bool gpuInitialResets = false, bool gpuRasterInitStorage = false, bool gpuConfigLowResponse = false, int gpuConfigHighHypothesis = -1, int gpuInitialStatusHypothesis = -1, int gpuPowerOffResponse = -1, bool gpuOffSequenceStorage = false, bool gpioConfigStorage = false, bool gpioInterruptIdle = false, bool gpioOutputLatch = false, bool adcInfoZeroFixture = false, bool adcCalibrationControl = false, int adcPowerResponse = -1, bool adcTriggerConfigStorage = false, bool adcDisabledConfigStorage = false, bool adcEnableLatch = false, BlackwallAdcInternalTrigger adcInternalTrigger = null, int adcConstantChannel3 = -1, int adcPowerOffResponse = -1, BlackwallUartAdapter uart1 = null, int uart1PowerResponse = -1, int uart1OffResponse = -1, BlackwallUartAdapter uart0 = null, int uart0PowerResponse = -1, int uart0OffResponse = -1, BlackwallUartAdapter uart2 = null, int uart2PowerResponse = -1, int uart2OffResponse = -1, BlackwallUartAdapter uart3 = null, int uart3PowerResponse = -1, int uart3OffResponse = -1, BlackwallPeripheralPower iom2Power = null, BlackwallPeripheralPower iom4Power = null, BlackwallPeripheralPower iom5Power = null, BlackwallPeripheralPower iom7Power = null, int rtcOselInitial = -1, IBlackwallRtc rtc = null, bool chipInfo = false, int jedecMockPart = -1, long jedecMockCid = -1, BlackwallG2StartupFixture chipInfoOwner = null, IBlackwallStimer stimer = null, BlackwallPeripheralPower mspi1Power = null, IBlackwallMspi1Clock mspi1Clock = null, IBlackwallMspi1Config mspi1Config = null, IBlackwallTimer14 timer14 = null, BlackwallPeripheralPower otpPower = null, BlackwallPeripheralPower cryptoPower = null, int cryptoNvmIdle = -1, BlackwallOtpReadReadiness otpReadReadiness = null, BlackwallOtpSerialSlots otpSerialSlots = null, BlackwallCryptoOtpPowerLifecycle cryptoOtpPowerLifecycle = null, BlackwallGpioRoleInput gpioRoleInput = null, bool uartHcpaStatus = false, bool uartHcpaGate = false, bool gpioOutputIdempotentWrites = false, BlackwallPeripheralPower iom6Power = null, IBlackwallEm9305Reset em9305Reset = null, BlackwallPeripheralPower mspi0Power = null, IBlackwallMspi1Config mspi0Config = null, BlackwallCpuNormalSleep cpuNormalSleep = null, int gpuRuntimeWakeResponse = -1, BlackwallGpioInterruptIdle gpioInterruptController = null, int info1TrimRevision = -1, bool b0TonConfiguration = false)
            : base(size, baseAddress)
        {
            if(prefetchStorage && !startupControls)
                throw new System.ArgumentException("Prefetch storage requires startup controls");
            PrefetchStorage = prefetchStorage;
            if(gpuInterruptClear && gpuPowerResponse==-1)
                throw new System.ArgumentException("GPU IRQ clear requires explicit power response");
            if(gpuIdInitialization && !gpuInterruptClear)
                throw new System.ArgumentException("GPU ID initialization requires IRQ clear");
            if(gpuRingConfiguration && !gpuIdInitialization)
                throw new System.ArgumentException("GPU ring configuration requires ID initialization");
            if(gpuIdentityResponse < -1 || gpuIdentityResponse > 1 || (gpuIdentityResponse!=-1 && !gpuRingConfiguration))
                throw new System.ArgumentException("GPU identity response requires ring configuration and known profile");
            if(gpuInitialResets && gpuIdentityResponse!=1)
                throw new System.ArgumentException("Initial GPU resets require explicit source identity");
            if(gpuRasterInitStorage && !gpuInitialResets)
                throw new System.ArgumentException("Raster init storage requires initial reset controls");
            if(gpuConfigLowResponse && !gpuRasterInitStorage)
                throw new System.ArgumentException("GPU CONFIG observation requires raster trace storage");
            if((gpuConfigHighHypothesis!=-1 && gpuConfigHighHypothesis!=0 && gpuConfigHighHypothesis!=512)
                || (gpuConfigHighHypothesis!=-1 && !gpuConfigLowResponse))
                throw new System.ArgumentException("CONFIGH requires known explicit hypothesis and low response");
            if(gpuInitialStatusHypothesis < -1 || gpuInitialStatusHypothesis > 1
                || (gpuInitialStatusHypothesis!=-1 && gpuConfigHighHypothesis==-1))
                throw new System.ArgumentException("Initial STATUS requires explicit high CONFIG hypothesis");
            if(gpuPowerOffResponse < -1 || gpuPowerOffResponse > 1 || (gpuPowerOffResponse!=-1 && gpuPowerResponse!=1))
                throw new System.ArgumentException("GPU off response requires active power profile");
            if(gpuOffSequenceStorage && gpuPowerOffResponse==-1)
                throw new System.ArgumentException("GPU off sequence requires explicit off response");
            GpuInitialStatusHypothesis=gpuInitialStatusHypothesis;
            GpuConfigLowResponse = gpuConfigLowResponse; GpuConfigHighHypothesis = gpuConfigHighHypothesis;
            GpuRasterInitStorage = gpuRasterInitStorage;
            GpuReset = gpuInitialResets ? new BlackwallGpuInitialReset() : null;
            GpuIdentityProfile = gpuIdentityResponse;
            GpuRing = gpuRingConfiguration ? new BlackwallGpuRingConfiguration() : null;
            GpuIdInitialization = gpuIdInitialization;
            GpuInterruptClear = gpuInterruptClear;
            this.gpuControlOwner = gpuControlOwner;
            if(gpuPowerResponse < -1 || gpuPowerResponse > 1 || (gpuPowerResponse!=-1 && !gpuPowerPreparation))
                throw new System.ArgumentException("GPU response requires preparation and known profile");
            if(gpuPowerPreparation && (!gfxPowerStorage || !hfrcForceControl || mcuClockResponse!=0))
                throw new System.ArgumentException("GPU preparation requires GFX selection and nominal HFRC controls");
            if(hfrcForceControl && mcuClockResponse==-1)
                throw new System.ArgumentException("HFRC force control requires explicit clock response");
            if(gfxPowerStorage && !startupControls)
                throw new System.ArgumentException("GFX power storage requires peripherals-off startup controls");
            GfxPower = gfxPowerStorage ? new BlackwallGfxPowerStorage() : null;
            if(powerMode != "none" && powerMode != "lp" && powerMode != "hp")
                throw new System.ArgumentException("Unknown stable power scenario");
            if(resetLatch < -1 || resetLatch > 0x1fff)
                throw new System.ArgumentException("Reset shadow fixture must fit thirteen bits");
            if(shadowInfo1 != "none" && shadowInfo1 != "mram" && shadowInfo1 != "otp")
                throw new System.ArgumentException("Unknown hypothetical Info1 source");
            if(info1Metadata != "none" && info1Metadata != "zero" && info1Metadata != "erased")
                throw new System.ArgumentException("Only sparse invalid Info1 metadata is supported");
            if(chipRevision != -1 && (chipRevision < 0x21 || chipRevision > 0x24))
                throw new System.ArgumentException("Unsupported synthetic chip revision");
            if(buckOverrideStorage && !spotStorage)
                throw new System.ArgumentException("Ordered buck storage requires SPOT storage");
            if(buckStartStorage && !buckOverrideStorage)
                throw new System.ArgumentException("Buck start storage requires ordered override storage");
            if(buckStatusFixture != -1 && buckStatusFixture != 0 && buckStatusFixture != 2 && buckStatusFixture != 3)
                throw new System.ArgumentException("Unknown buck status fixture");
            if(buckStatusFixture != -1 && !memLdoSetup)
                throw new System.ArgumentException("Buck status fixture requires memory LDO setup");
            BuckStatusFixture = buckStatusFixture;
            if(buckResponse != -1 && buckResponse != 0 && buckResponse != 3)
                throw new System.ArgumentException("Unknown buck response profile");
            if(buckResponse != -1 && (!memLdoSetup || buckStatusFixture != -1))
                throw new System.ArgumentException("Buck response requires setup and excludes single samples");
            if(vddfTempcoStorage && buckResponse == -1)
                throw new System.ArgumentException("VDDF storage requires buck response");
            BuckResponse = buckResponse;
            if(mcuClockResponse < -1 || mcuClockResponse > 3 || (mcuClockResponse!=-1
                && (powerMode=="none" || !halStorage || buckResponse!=3 || !vddfTempcoStorage)))
                throw new System.ArgumentException("MCU clock response requires active buck, VDDF storage and explicit mode");
            if(memLdoSetup && !coreLdoReduction)
                throw new System.ArgumentException("Memory LDO setup requires core LDO reduction storage");
            if(coreLdoReduction && (!buckStartStorage || !halStorage))
                throw new System.ArgumentException("Core LDO reduction requires buck start and HAL fixtures");
            BuckStart = buckStartStorage ? new BlackwallBuckStart() : null;
            BuckOverrideStorage = buckOverrideStorage;
            MramControlStorage = mramControlStorage;
            if(b0TonConfiguration && (!halStorage || chipRevision!=0x21))
                throw new System.ArgumentException("B0 TON requires explicit B0 HAL profile");
            HalStorage = halStorage ? new BlackwallHalStorage(b0TonConfiguration) : null;
            CoreLdo = coreLdoReduction ? new BlackwallCoreLdoReduction(HalStorage,BuckStart) : null;
            MemLdo = memLdoSetup ? new BlackwallMemLdoSetup(HalStorage,BuckStart,CoreLdo) : null;
            VddfTempco = vddfTempcoStorage ? new BlackwallVddfTempco(HalStorage,MemLdo) : null;
            if(rtcOselInitial < -1 || rtcOselInitial > 1)
                throw new System.ArgumentException("RTC OSEL storage requires explicit XT0 or LFRC1 initial request");
            Rtc = rtc;
            Stimer = stimer;
            RtcOsel = rtcOselInitial!=-1 ? new BlackwallMemoryRegister((uint)rtcOselInitial << 7) : null;
            McuClock = mcuClockResponse!=-1 ? new BlackwallMcuClock(HalStorage,powerMode,mcuClockResponse,hfrcForceControl) : null;
            GpuPreparation = gpuPowerPreparation ? new BlackwallGpuPreparation(HalStorage) : null;
            if(gpuRuntimeWakeResponse < -1 || gpuRuntimeWakeResponse > 1 || (gpuRuntimeWakeResponse!=-1
                && (!gpuOffSequenceStorage || gpuPowerResponse==-1 || gpuPowerOffResponse==-1 || !gpuPowerPreparation)))
                throw new System.ArgumentException("GPU runtime wake requires preparation, off sequence and explicit power profiles");
            GpuRuntimeWakeResponse=gpuRuntimeWakeResponse;
            GpuPower = gpuPowerResponse!=-1 ? new BlackwallGpuPower(gpuPowerResponse,gpuPowerOffResponse,gpuRuntimeWakeResponse) : null;
            GpuOffSequence = gpuOffSequenceStorage ? new BlackwallGpuOffSequence(HalStorage) : null;
            if(gpioInterruptIdle && !gpioConfigStorage)
                throw new System.ArgumentException("GPIO interrupt idle requires GPIO config storage");
            GpioConfig = gpioConfigStorage ? new BlackwallGpioConfig() : null;
            if(gpioInterruptController!=null && !gpioInterruptIdle) throw new System.ArgumentException("Explicit GPIO interrupt owner requires GPIO interrupt profile");
            GpioInterrupts = gpioInterruptIdle ? (gpioInterruptController ?? new BlackwallGpioInterruptIdle()) : null;
            if(gpioOutputLatch && !gpioConfigStorage)
                throw new System.ArgumentException("GPIO output latch requires GPIO config storage");
            if(gpioOutputIdempotentWrites && !gpioOutputLatch)
                throw new System.ArgumentException("Unchanged GPIO writes require the output latch model");
            GpioOutput = gpioOutputLatch ? new BlackwallGpioOutputLatch(GpioConfig,gpioOutputIdempotentWrites) : null;
            if(gpioRoleInput!=null && GpioConfig==null)
                throw new System.ArgumentException("GPIO role input requires GPIO configuration storage");
            GpioRoleInput=gpioRoleInput;
            if(em9305Reset!=null && GpioOutput==null)throw new System.ArgumentException("EM9305 reset requires configured GPIO output latch");
            Em9305Reset=em9305Reset;
            if(Em9305Reset!=null)Em9305Reset.Attach(GpioOutput);
            MemoryStartup = memoryStartup ? new BlackwallMemoryStartup() : null;
            ChipRevision = chipRevision;
            if(chipInfo && chipRevision==-1) throw new System.ArgumentException("Chip info requires explicit revision hypothesis");
            if((jedecMockPart!=-1 || jedecMockCid!=-1) && !chipInfo) throw new System.ArgumentException("JEDEC mock requires chip info");
            if(chipInfoOwner!=null && (chipInfo || jedecMockPart!=-1 || jedecMockCid!=-1 || chipInfoOwner.ChipInfo==null)) throw new System.ArgumentException("Conflicting or absent chip info owner");
            ChipInfoOwner=chipInfoOwner;
            ChipInfo = chipInfo ? new BlackwallChipIdentity((uint)chipRevision,jedecMockPart,jedecMockCid) : null;
            SpotStorage = spotStorage;
            ShadowInfo1 = shadowInfo1;
            Info1Metadata = info1Metadata;
            if(info1TrimRevision < -1 || info1TrimRevision>2 || info1TrimRevision!=-1 && (info1Metadata!="zero" || (shadowInfo1!="mram" && (gpuControlOwner==null || gpuControlOwner.ShadowInfo1!="mram"))))
                throw new System.ArgumentException("Explicit synthetic MRAM trim revision0..2 requires zero metadata baseline");
            Info1TrimRevision=info1TrimRevision;
            if(adcInfoZeroFixture && info1Metadata!="zero")
                throw new System.ArgumentException("ADC info zero fixture requires zero metadata");
            AdcInfo = adcInfoZeroFixture ? new BlackwallAdcInfoZeroFixture() : null;
            AdcCalibrationControl = adcCalibrationControl ? new BlackwallMemoryRegister(1) : null;
            if(adcPowerResponse < -1 || adcPowerResponse > 1 || (adcPowerResponse!=-1 && (gpuPowerResponse==-1 || !adcCalibrationControl)))
                throw new System.ArgumentException("ADC power response requires GPU power and calibration control");
            AdcPower = adcPowerResponse!=-1 ? new BlackwallAdcPower(adcPowerResponse,adcPowerOffResponse) : null;
            if(adcTriggerConfigStorage && adcPowerResponse==-1)
                throw new System.ArgumentException("ADC trigger config requires ADC power response");
            AdcTriggerConfig = adcTriggerConfigStorage ? new BlackwallMemoryRegister(0) : null;
            if(adcDisabledConfigStorage && adcPowerResponse==-1)
                throw new System.ArgumentException("ADC disabled config requires ADC power response");
            if(adcEnableLatch && (!adcDisabledConfigStorage || !adcTriggerConfigStorage))
                throw new System.ArgumentException("ADC enable latch requires disabled config bank and timer config storage");
            AdcDisabledConfig = adcDisabledConfigStorage ? new BlackwallAdcDisabledConfig(adcEnableLatch) : null;
            if(adcInternalTrigger != null && !adcEnableLatch)
                throw new System.ArgumentException("ADC internal trigger requires enable latch");
            AdcInternalTrigger=adcInternalTrigger;
            if(adcConstantChannel3 < -1 || adcConstantChannel3>4095 || (adcConstantChannel3!=-1 && adcInternalTrigger==null))
                throw new System.ArgumentException("ADC constant channel3 requires trigger and code0..4095");
            if(adcPowerOffResponse!=-1 && adcConstantChannel3==-1) throw new System.ArgumentException("ADC power off requires constant scan profile");
            AdcScan=adcConstantChannel3!=-1 ? new BlackwallAdcConstantScan(AdcDisabledConfig,(uint)adcConstantChannel3) : null;
            if(AdcScan!=null) { AdcDisabledConfig.SourceReset=true; AdcInternalTrigger.Scan=AdcScan; }
            AddIomPower(2,iom2Power);
            AddIomPower(4,iom4Power);
            AddIomPower(5,iom5Power);
            AddIomPower(6,iom6Power);
            AddIomPower(7,iom7Power);
            if(mspi1Power!=null && (AdcPower==null || mspi1Power.Mask!=0x8000u))
                throw new System.ArgumentException("MSPI1 requires matching mask and shared ADC/GPU bank");
            Mspi1Power=mspi1Power;
            if(mspi0Power!=null && (AdcPower==null || mspi0Power.Mask!=0x4000u || (mspi0Power.OffProfile!=-1 && (mspi0Config==null || !System.Object.ReferenceEquals(mspi0Config.RetentionPower,mspi0Power)))))
                throw new System.ArgumentException("MSPI0 requires matching mask, shared ADC/GPU bank and no off support");
            Mspi0Power=mspi0Power;
            if(otpPower!=null && (AdcPower==null || otpPower.Mask!=0x08000000u || (otpPower.OffProfile!=-1 && cryptoOtpPowerLifecycle==null)))
                throw new System.ArgumentException("OTP requires matching mask, shared ADC/GPU bank and no off support");
            OtpPower=otpPower;
            if(cryptoNvmIdle < -1 || cryptoNvmIdle > 1 || (cryptoNvmIdle!=-1 && cryptoPower==null)
                || (cryptoPower!=null && (OtpPower==null || cryptoPower.Mask!=0x200000u || (cryptoPower.OffProfile!=-1 && cryptoOtpPowerLifecycle==null))))
                throw new System.ArgumentException("CRYPTO requires matching power mask, OTP owner, no off support and explicit NVM idle -1/0/1");
            CryptoPower=cryptoPower;CryptoNvmIdle=cryptoNvmIdle;
            if(otpReadReadiness!=null && (!System.Object.ReferenceEquals(otpReadReadiness.OtpPower,OtpPower)
                || !System.Object.ReferenceEquals(otpReadReadiness.CryptoPower,CryptoPower)))
                throw new System.ArgumentException("OTP read readiness requires identical power owners");
            OtpReadReadiness=otpReadReadiness;
            if(cryptoOtpPowerLifecycle!=null && (OtpReadReadiness==null
                || !System.Object.ReferenceEquals(cryptoOtpPowerLifecycle.Readiness,OtpReadReadiness)))
                throw new System.ArgumentException("CRYPTO OTP lifecycle requires identical readiness owner");
            CryptoOtpPowerLifecycle=cryptoOtpPowerLifecycle;
            if(otpSerialSlots!=null && !System.Object.ReferenceEquals(otpSerialSlots.Readiness,OtpReadReadiness))
                throw new System.ArgumentException("OTP serial slots require identical readiness owner");
            OtpSerialSlots=otpSerialSlots;
            Mspi1Clock=mspi1Clock;
            if(mspi1Config!=null && Mspi1Power==null) throw new System.ArgumentException("MSPI1 config requires explicit power owner");
            Mspi1Config=mspi1Config;
            if(mspi0Config!=null && (Mspi0Power==null || !mspi0Config.Owns(0x40060000) || mspi0Config.Owns(0x40061000)))throw new System.ArgumentException("MSPI0 config requires matching base and explicit power owner");
            Mspi0Config=mspi0Config;
            if(cpuNormalSleep!=null && !startupControls)throw new System.ArgumentException("Normal sleep requires explicit startup control storage");
            CpuNormalSleep=cpuNormalSleep;
            Timer14=timer14;
            AddUart(0,uart0,uart0PowerResponse,uart0OffResponse);
            AddUart(1,uart1,uart1PowerResponse,uart1OffResponse);
            AddUart(2,uart2,uart2PowerResponse,uart2OffResponse);
            AddUart(3,uart3,uart3PowerResponse,uart3OffResponse);
            if(uartHcpaStatus && Uarts.Count!=4)throw new System.ArgumentException("HCPA status requires four explicit UART adapters");
            UartHcpaStatus=uartHcpaStatus;
            if(uartHcpaGate && !uartHcpaStatus)throw new System.ArgumentException("HCPA gate requires shared HCPA status");
            UartHcpaGate=uartHcpaGate;
            PowerMode = powerMode;
            initialLatch = resetLatch;
            StartupControls = startupControls;
            Reset();
        }

        private void AddIomPower(int module,BlackwallPeripheralPower power)
        {
            if(power==null) return;
            if(AdcPower==null || power.Mask!=(1u<<(module+1))) throw new System.ArgumentException("IOM requires matching module mask and shared ADC/GPU bank");
            IomPowers.Add(module,power);
        }

        private void AddUart(int module,BlackwallUartAdapter adapter,int power,int off)
        {
            if((adapter==null)!=(power==-1) || (adapter!=null && (AdcPower==null || adapter.Module!=module)))
                throw new System.ArgumentException("UART adapter requires matching module and ADC/GPU bank");
            if(off < -1 || off > 1 || (off!=-1 && (adapter==null || !adapter.InterruptsEnabled)))
                throw new System.ArgumentException("UART off response requires interrupt model");
            if(adapter==null) return;
            Uarts.Add(module,adapter); UartPowers.Add(module,new BlackwallUartPower(power,off,module));
        }

        public override void Reset()
        {
            base.Reset();
            PowerReads = LatchReads = LatchWrites = 0;
            LatchValue = initialLatch;
            DevicePowerReads = DevicePowerWrites = DebugReads = DebugWrites = 0;
            CorePowerReads = CorePowerWrites = WicReads = WicWrites = 0;
            WicValue = 0;
            ShadowReads = TrackerReads = TrimRevisionReads = Ft1Reads = 0;
            ChipRevisionReads = AcrgReads = AcrgWrites = VrctrlReads = VrctrlWrites = 0;
            if(ChipInfo != null) ChipInfo.Reset();
            AcrgValue = 0x78;
            VrctrlValue = 0;
            if(MemoryStartup != null) MemoryStartup.Reset();
            if(HalStorage != null) HalStorage.Reset();
            MramValue = 2; MramReads = MramWrites = 0;
            BuckOverrideStep = 0;
            BuckStatusReads = 0;
            BuckResponsePhase = "off"; BuckResponseReads = BuckResponseTransitions = 0;
            PrefetchInitialized = false; PrefetchValue = 0; PrefetchReads = PrefetchWrites = 0;
            if(BuckStart != null) BuckStart.Reset();
            if(CoreLdo != null) CoreLdo.Reset();
            if(MemLdo != null) MemLdo.Reset();
            if(VddfTempco != null) VddfTempco.Reset();
            if(McuClock != null) McuClock.Reset();
            if(Rtc != null) Rtc.Reset();
            if(Stimer != null) Stimer.Reset();
            if(RtcOsel != null) { RtcOsel.Value=RtcOsel.InitialValue; RtcOsel.Reads=RtcOsel.Writes=0; }
            GpuRuntimeWakeCycles=GpuEpochIdentityReads=GpuEpochInterruptClears=0;
            if(GpuPreparation != null) GpuPreparation.Reset();
            if(GpuPower != null) GpuPower.Reset();
            if(GpuOffSequence != null) GpuOffSequence.Reset();
            if(GpioConfig != null) GpioConfig.Reset();
            if(GpioInterrupts != null) GpioInterrupts.Reset();
            if(GpioOutput != null) GpioOutput.Reset();
            if(GpioRoleInput != null) GpioRoleInput.Reset();
            if(Em9305Reset != null) Em9305Reset.Reset();
            if(AdcInfo != null) AdcInfo.Reset();
            if(AdcPower != null) AdcPower.Reset();
            if(AdcCalibrationControl != null) { AdcCalibrationControl.Value=AdcCalibrationControl.InitialValue; AdcCalibrationControl.Reads=AdcCalibrationControl.Writes=0; }
            if(AdcDisabledConfig != null) AdcDisabledConfig.Reset();
            if(AdcInternalTrigger != null) AdcInternalTrigger.Reset();
            if(AdcScan != null) AdcScan.Reset();
            foreach(var pair in Uarts) { pair.Value.Reset(); UartPowers[pair.Key].Reset(); }
            foreach(var power in IomPowers.Values) power.Reset();
            if(Mspi1Power!=null)Mspi1Power.Reset();
            if(Mspi0Power!=null)Mspi0Power.Reset();
            if(OtpPower!=null)OtpPower.Reset();
            if(CryptoPower!=null)CryptoPower.Reset();
            CryptoNvmReads=0;
            if(OtpReadReadiness!=null)OtpReadReadiness.Reset();
            if(OtpSerialSlots!=null)OtpSerialSlots.Reset();
            if(Mspi1Clock!=null)Mspi1Clock.Reset();
            if(Mspi1Config!=null)Mspi1Config.Reset();
            if(Mspi0Config!=null)Mspi0Config.Reset();
            if(CpuNormalSleep!=null)CpuNormalSleep.Reset();
            if(Timer14!=null)Timer14.Reset();
            AdcTriggerConfigured=false; AdcTriggerPowerBlocks=0;
            if(AdcTriggerConfig != null) { AdcTriggerConfig.Value=0; AdcTriggerConfig.Reads=AdcTriggerConfig.Writes=0; }
            GpuInterruptClears = 0;
            GpuIdInitialized = false;
            GpuIdentityReads = 0;
            GpuRasterInitStored = false;
            GpuConfigLowReads = GpuConfigHighReads = GpuInitialStatusReads = 0;
            if(GpuReset != null) GpuReset.Reset();
            if(GpuRing != null) GpuRing.Reset();
            if(GpuCommandDevice != null) GpuCommandDevice.Reset();
            if(GfxPower != null) GfxPower.Reset();
        }

        public override uint ReadDoubleWord(long offset)
        {
            var address = baseAddress + (ulong)offset;
            if(Timer14!=null && Timer14.Owns(address))
            {
                if(Timer14.TryRead(address,out var timer14Value))return timer14Value;
                return base.ReadDoubleWord(offset);
            }
            if(Stimer!=null && Stimer.Owns(address))
            {
                if(Stimer.TryRead(address,out var stimerValue))return stimerValue;
                return base.ReadDoubleWord(offset);
            }
            if(Rtc != null && Rtc.Owns(address)) return Rtc.ReadDoubleWord((long)(address-0x40004800));
            if(GpioRoleInput!=null && GpioRoleInput.Owns(address))
            {
                uint cfg;
                var touch=address==0x40010404;
                if(GpioRoleInput.TryRead(address,GpioConfig.Values.TryGetValue(touch ? 0x4001006cul:0x40010270ul,out cfg) && cfg==(touch ? 0x53u:0x93u),out var inputValue,GpioInterrupts))return inputValue;
                return base.ReadDoubleWord(offset);
            }
            if(Em9305Reset!=null && address==0x40010410)
            {
                uint cfg;
                if(GpioConfig.Values.TryGetValue(0x400101d4,out cfg) && Em9305Reset.TryRead(address,cfg,out var readyValue))return readyValue;
                return base.ReadDoubleWord(offset);
            }
            if(GpioOutput != null && GpioOutput.Owns(address))
            {
                if(GpioOutput.TryRead(address,out var outputValue)) return outputValue;
                return base.ReadDoubleWord(offset);
            }
            if(GpioInterrupts != null && GpioInterrupts.Owns(address))
            {
                if(GpioInterrupts.TryRead(address,out var irqValue)) return irqValue;
                return base.ReadDoubleWord(offset);
            }
            if(GpioConfig != null && GpioConfig.Owns(address))
            {
                if(GpioConfig.TryRead(address,out var pinValue)) return pinValue;
                return base.ReadDoubleWord(offset);
            }
            if(AdcCalibrationControl != null && address==0x4002010c)
            { AdcCalibrationControl.Reads++; return AdcCalibrationControl.Value; }
            var gpuControl = gpuControlOwner ?? this;
            if(gpuControl.CpuNormalSleep!=null && gpuControl.CpuNormalSleep.Owns(address))
            {
                if(gpuControl.CpuNormalSleep.TryRead(address,out var sleepValue))return sleepValue;
                return base.ReadDoubleWord(offset);
            }
            if(gpuControl.Mspi0Config!=null && gpuControl.Mspi0Config.Owns(address))
            {
                if(gpuControl.Mspi0Config.TryRead(address,gpuControl.Mspi0Power.Phase=="on",out var mspi0Value))return mspi0Value;
                return base.ReadDoubleWord(offset);
            }
            if(gpuControl.Mspi1Config!=null && gpuControl.Mspi1Config.Owns(address))
            {
                if(gpuControl.Mspi1Config.TryRead(address,gpuControl.Mspi1Power.Phase=="on",out var mspiValue))return mspiValue;
                return base.ReadDoubleWord(offset);
            }
            foreach(var pair in gpuControl.Uarts)
            {
                if(!pair.Value.Owns(address)) continue;
                if(pair.Value.TryRead(address,gpuControl.UartPowers[pair.Key].Phase=="on",out var uartValue)) return uartValue;
                return base.ReadDoubleWord(offset);
            }
            if(gpuControl.AdcScan!=null && gpuControl.AdcScan.Owns(address))
            {
                if(gpuControl.AdcPower.Phase=="on" && gpuControl.AdcScan.TryRead(address,out var scanValue)) return scanValue;
                return base.ReadDoubleWord(offset);
            }
            if(gpuControl.AdcDisabledConfig != null && gpuControl.AdcDisabledConfig.Owns(address))
            {
                if(gpuControl.AdcDisabledConfig.TryRead(address,gpuControl.AdcPower.Phase=="on",out var adcConfig)) return adcConfig;
                return base.ReadDoubleWord(offset);
            }
            if(gpuControl.AdcTriggerConfig != null && address==0x40038040)
            {
                if(gpuControl.AdcPower.Phase!="on") { gpuControl.AdcTriggerPowerBlocks++; return base.ReadDoubleWord(offset); }
                if(!gpuControl.AdcTriggerConfigured) return base.ReadDoubleWord(offset);
                gpuControl.AdcTriggerConfig.Reads++; return gpuControl.AdcTriggerConfig.Value;
            }
            if(gpuControl.GpuConfigLowResponse && gpuControl.GpuRasterInitStored && gpuControl.GpuPower.Phase=="on")
            {
                if(address==0x400901f0) { gpuControl.GpuConfigLowReads++; return 0xf4030105u; }
                if(address==0x400900fc && gpuControl.GpuInitialStatusHypothesis!=-1
                    && gpuControl.GpuRing.StepsCompleted==3 && gpuControl.GpuReset.StepsCompleted==2)
                { gpuControl.GpuInitialStatusReads++; return (uint)gpuControl.GpuInitialStatusHypothesis; }
                if(address==0x400901f4 && gpuControl.GpuConfigHighHypothesis!=-1)
                { gpuControl.GpuConfigHighReads++; return (uint)gpuControl.GpuConfigHighHypothesis; }
            }
            if(address==0x40090148 && gpuControl.GpuRuntimeWakeResponse!=-1 && gpuControl.GpuRuntimeWakeCycles>0
                && gpuControl.GpuPower.Phase=="on" && gpuControl.GpuIdInitialized)
            {
                return gpuControl.GpuCommandDevice==null ? 0 : gpuControl.GpuCommandDevice.CompletedId;
            }
            if(gpuControl.GpuIdentityProfile!=-1 && address==0x400901ec && gpuControl.GpuPower.Phase=="on"
                && (gpuControl.GpuRing.StepsCompleted==3 || (gpuControl.GpuRuntimeWakeResponse!=-1 && gpuControl.GpuRuntimeWakeCycles>0)))
            { gpuControl.GpuIdentityReads++; gpuControl.GpuEpochIdentityReads++; return gpuControl.GpuIdentityProfile==1 ? 0x86362000u : 0u; }
            if(address==0x400c1f10 && gpuControl.CryptoPower!=null && gpuControl.CryptoNvmIdle!=-1
                && gpuControl.CryptoPower.Phase=="on" && gpuControl.OtpPower.Phase=="on")
            { gpuControl.CryptoNvmReads++;return (uint)gpuControl.CryptoNvmIdle; }
            if(gpuControl.OtpReadReadiness!=null && gpuControl.OtpReadReadiness.Owns(address))
            {
                if(gpuControl.OtpReadReadiness.TryRead(address,out var readyValue))return readyValue;
                return base.ReadDoubleWord(offset);
            }
            if(gpuControl.OtpSerialSlots!=null && gpuControl.OtpSerialSlots.Owns(address))
            {
                if(gpuControl.OtpSerialSlots.TryRead(address,out var slotValue))return slotValue;
                return base.ReadDoubleWord(offset);
            }
            if(RtcOsel != null && address==0x4000400c) { RtcOsel.Reads++; return RtcOsel.Value; }
            if(Mspi1Clock!=null && address==0x40004110) return Mspi1Clock.Read();
            if(McuClock != null)
            {
                if(address==0x40004030) return McuClock.ReadClock();
                if(address==0x40021000) { PowerReads++; return McuClock.ReadMode(); }
            }
            if(GfxPower != null && GfxPower.TryRead(address,out var gfxValue)) return gfxValue;
            if((Uarts.Count!=0 || IomPowers.Count!=0 || Mspi0Power!=null || Mspi1Power!=null || OtpPower!=null || CryptoPower!=null) && (address==0x40021004 || address==0x40021008))
            {
                uint uartWord=0;
                if(address==0x40021004)
                {
                    foreach(var power in UartPowers.Values) uartWord|=power.RequestWord;
                    foreach(var power in IomPowers.Values) uartWord|=power.RequestWord;
                    if(Mspi1Power!=null)uartWord|=Mspi1Power.RequestWord;
                    if(Mspi0Power!=null)uartWord|=Mspi0Power.RequestWord;
                    if(OtpPower!=null)uartWord|=OtpPower.RequestWord;
                    if(CryptoPower!=null)uartWord|=CryptoPower.RequestWord;
                    DevicePowerReads++; return GpuPower.ReadEnable()|AdcPower.RequestWord|uartWord;
                }
                if(!AdcPower.TryReadStatus(AdcCalibrationControl.Value==0,out var adcStatus3)) return base.ReadDoubleWord(offset);
                foreach(var pair in UartPowers)
                {
                    var previous=pair.Value.Phase; uartWord|=pair.Value.ReadStatus();
                    if(previous=="off-requested" && pair.Value.Phase=="powered-off")
                    {
                        Uarts[pair.Key].PowerDown();
                        if(UartHcpaGate && !UartPowers.Values.Any(p => p.RequestWord!=0))
                            foreach(var gated in UartPowers)
                                if(gated.Value.CompleteSharedPowerOff())Uarts[gated.Key].PowerDown();
                    }
                }
                if(UartHcpaStatus && uartWord!=0)uartWord=0x1e00;
                foreach(var power in IomPowers.Values) uartWord|=power.ReadStatus();
                if(Mspi1Power!=null)uartWord|=Mspi1Power.ReadStatus();
                if(Mspi0Power!=null)uartWord|=Mspi0Power.ReadStatus();
                if(OtpPower!=null)uartWord|=OtpPower.ReadStatus();
                if(CryptoPower!=null)uartWord|=CryptoPower.ReadStatus();
                DevicePowerReads++; return GpuPower.ReadStatus()|adcStatus3|uartWord;
            }
            if(AdcPower != null && (address==0x40021004 || address==0x40021008))
            {
                if(address==0x40021004) { DevicePowerReads++; return GpuPower.ReadEnable()|AdcPower.RequestWord; }
                if(!AdcPower.TryReadStatus(AdcCalibrationControl.Value==0,out var adcStatus)) return base.ReadDoubleWord(offset);
                DevicePowerReads++; return GpuPower.ReadStatus()|adcStatus;
            }
            if(GpuPower != null && (address==0x40021004 || address==0x40021008))
            { DevicePowerReads++; return address==0x40021004 ? GpuPower.ReadEnable() : GpuPower.ReadStatus(); }
            if(PrefetchStorage && address == 0xe001e004)
            {
                if(!PrefetchInitialized) return base.ReadDoubleWord(offset);
                PrefetchReads++; return PrefetchValue;
            }
            if(BuckStart != null)
            {
                if(BuckStart.EnableRequested && address == 0x40021108)
                {
                    if(BuckResponse != -1 && MemLdo != null && MemLdo.StepsCompleted == 2)
                    {
                        if(BuckResponsePhase == "requested")
                        { BuckResponsePhase = BuckResponse == 3 ? "active" : "stuck-off"; BuckResponseTransitions++; }
                        BuckResponseReads++; return (uint)BuckResponse << 4;
                    }
                    if(BuckStatusFixture != -1 && MemLdo != null && MemLdo.StepsCompleted == 2 && BuckStatusReads == 0)
                    { BuckStatusReads++; return (uint)BuckStatusFixture << 4; }
                    return base.ReadDoubleWord(offset);
                }
                if(BuckStart.TryRead(address,out var startValue)) return startValue;
            }
            if(MramControlStorage && address == 0x400211c8) { MramReads++; return MramValue; }
            if(HalStorage != null && HalStorage.TryRead(address,out var halValue)) return halValue;
            if(MemoryStartup != null && MemoryStartup.TryRead(address,out var memoryValue)) return memoryValue;
            var chipSource=ChipInfoOwner ?? this;
            if(chipSource.ChipInfo != null && chipSource.ChipInfo.TryRead(address,out var chipWord))
            { if(address==0x4002000c) chipSource.ChipRevisionReads++; return chipWord; }
            if(address == 0x4002000c && ChipRevision != -1) { ChipRevisionReads++; return (uint)ChipRevision; }
            if(SpotStorage)
            {
                if(address == 0x40020028) { AcrgReads++; return AcrgValue; }
                if(address == 0x40020060) { VrctrlReads++; return VrctrlValue; }
            }
            if(address == 0x400201bc && ShadowInfo1 != "none")
            {
                ShadowReads++;
                return ShadowInfo1 == "otp" ? 9u : 1u;
            }
            if(AdcInfo != null && AdcInfo.TryRead(address,out var adcInfoValue)) return adcInfoValue;
            if(Info1Metadata != "none")
            {
                if(address == 0x42003240) { TrackerReads++; return MetadataValue; }
                if(address == 0x42003310) { TrimRevisionReads++; return Info1TrimRevision<0 ? MetadataValue : (uint)Info1TrimRevision; }
                if(address == 0x42003314) { Ft1Reads++; return MetadataValue; }
            }
            if(StartupControls)
            {
                if(address == 0x40021004 || address == 0x40021008) { DevicePowerReads++; return 0; }
                if(address == 0x40020250) { DebugReads++; return 0; }
                if(address == 0xe001e300) { CorePowerReads++; return 0; }
                if(address == 0x4002021c) { WicReads++; return WicValue; }
            }
            if(address == 0x40021000 && PowerMode != "none")
            {
                PowerReads++;
                return PowerMode == "lp" ? 0xdu : 0x16u;
            }
            if(address == 0x4000885c && initialLatch >= 0)
            {
                LatchReads++;
                return (uint)LatchValue;
            }
            return base.ReadDoubleWord(offset);
        }

        public override void WriteDoubleWord(long offset, uint value)
        {
            var address = baseAddress + (ulong)offset;
            if(Timer14!=null && Timer14.Owns(address))
            {
                if(!Timer14.TryWrite(address,value))base.WriteDoubleWord(offset,value);
                return;
            }
            if(Stimer!=null && Stimer.Owns(address))
            {
                if(!Stimer.TryWrite(address,value))base.WriteDoubleWord(offset,value);
                return;
            }
            if(Rtc != null && Rtc.Owns(address)) { Rtc.WriteDoubleWord((long)(address-0x40004800),value); return; }
            var chipSource=ChipInfoOwner ?? this;
            if(chipSource.ChipInfo != null && chipSource.ChipInfo.Owns(address)) { base.WriteDoubleWord(offset,value); return; }
            if(GpioOutput != null && GpioOutput.Owns(address))
            {
                if(!GpioOutput.TryWrite(address,value)) base.WriteDoubleWord(offset,value);
                return;
            }
            if(GpioInterrupts != null && GpioInterrupts.Owns(address))
            {
                if(!GpioInterrupts.TryWrite(address,value)) base.WriteDoubleWord(offset,value);
                return;
            }
            if(GpioConfig != null && GpioConfig.Owns(address))
            {
                if(!GpioConfig.TryWrite(address,value)) base.WriteDoubleWord(offset,value);
                return;
            }
            if(AdcCalibrationControl != null && address==0x4002010c)
            {
                if((value&~1u)!=0) base.WriteDoubleWord(offset,value);
                else { AdcCalibrationControl.Value=value; AdcCalibrationControl.Writes++; }
                return;
            }
            var gpuControl = gpuControlOwner ?? this;
            if(gpuControl.CpuNormalSleep!=null && gpuControl.CpuNormalSleep.Owns(address))
            {
                if(!gpuControl.CpuNormalSleep.TryWrite(address,value))base.WriteDoubleWord(offset,value);
                return;
            }
            if(gpuControl.Mspi0Config!=null && gpuControl.Mspi0Config.Owns(address))
            {
                if(!gpuControl.Mspi0Config.TryWrite(address,value,gpuControl.Mspi0Power.Phase=="on"))base.WriteDoubleWord(offset,value);
                return;
            }
            if(gpuControl.Mspi1Config!=null && gpuControl.Mspi1Config.Owns(address))
            {
                if(!gpuControl.Mspi1Config.TryWrite(address,value,gpuControl.Mspi1Power.Phase=="on"))base.WriteDoubleWord(offset,value);
                return;
            }
            foreach(var pair in gpuControl.Uarts)
            {
                if(!pair.Value.Owns(address)) continue;
                if(!pair.Value.TryWrite(address,value,gpuControl.UartPowers[pair.Key].Phase=="on")) base.WriteDoubleWord(offset,value);
                return;
            }
            if(gpuControl.AdcScan!=null && gpuControl.AdcScan.Owns(address))
            {
                if(gpuControl.AdcPower.Phase!="on" || !gpuControl.AdcScan.TryWrite(address,value)) base.WriteDoubleWord(offset,value);
                return;
            }
            if(gpuControl.AdcDisabledConfig != null && gpuControl.AdcDisabledConfig.Owns(address))
            {
                if(!gpuControl.AdcDisabledConfig.TryWrite(address,value,gpuControl.AdcPower.Phase=="on",gpuControl.AdcTriggerConfigured)) base.WriteDoubleWord(offset,value);
                return;
            }
            if(gpuControl.AdcTriggerConfig != null && address==0x40038040)
            {
                if(gpuControl.AdcPower.Phase!="on") { gpuControl.AdcTriggerPowerBlocks++; base.WriteDoubleWord(offset,value); }
                else if((value&0x80000000u)!=0 && gpuControl.AdcInternalTrigger != null)
                {
                    if(!gpuControl.AdcTriggerConfigured || gpuControl.AdcDisabledConfig==null || !gpuControl.AdcDisabledConfig.Enabled
                        || !gpuControl.AdcInternalTrigger.TryStart(value,gpuControl.AdcTriggerConfig.Value,gpuControl.AdcDisabledConfig.Values[0x40038000])) base.WriteDoubleWord(offset,value);
                    else { gpuControl.AdcTriggerConfig.Value=value; gpuControl.AdcTriggerConfig.Writes++; }
                }
                else if(gpuControl.AdcScan!=null && gpuControl.AdcTriggerConfigured && value==(gpuControl.AdcTriggerConfig.Value&~0x80000000u)
                    && gpuControl.AdcInternalTrigger.TryStop())
                { gpuControl.AdcTriggerConfig.Value=value; gpuControl.AdcTriggerConfig.Writes++; gpuControl.AdcDisabledConfig.StopAllowed=true; }
                else if(gpuControl.AdcDisabledConfig != null && gpuControl.AdcDisabledConfig.Enabled) base.WriteDoubleWord(offset,value);
                else if((value&~0x703ffu)!=0) base.WriteDoubleWord(offset,value);
                else { gpuControl.AdcTriggerConfig.Value=value; gpuControl.AdcTriggerConfig.Writes++; gpuControl.AdcTriggerConfigured=true; }
                return;
            }
            if(gpuControl.GpuRing != null && (address==0x400900ec || address==0x400900f0 || address==0x400900f4))
            {
                if(address==0x400900ec && gpuControl.GpuCommandDevice!=null && gpuControl.GpuRing.StepsCompleted==3
                    && gpuControl.GpuPower.Phase=="on" && gpuControl.GpuIdInitialized && gpuControl.GpuRasterInitStored)
                {
                    gpuControl.GpuCommandDevice.Submit(gpuControl.GpuRing.BaseAddress,gpuControl.GpuRing.ByteLength,value);return;
                }
                if(!gpuControl.GpuRing.TryWrite(address,value,gpuControl.GpuPower.Phase=="on" && gpuControl.GpuIdInitialized))
                    base.WriteDoubleWord(offset,value);
                return;
            }
            if(gpuControl.GpuRasterInitStorage && address==0x40090388 && value==1
                && gpuControl.GpuPower.Phase=="on" && gpuControl.GpuReset.StepsCompleted==2 && !gpuControl.GpuRasterInitStored)
            { gpuControl.GpuRasterInitStored=true; return; }
            if(gpuControl.GpuReset != null && (address==0x400900e8 || address==0x400900fc))
            {
                if(!gpuControl.GpuReset.TryWrite(address,value,gpuControl.GpuPower.Phase=="on"
                    && gpuControl.GpuEpochIdentityReads>0 && gpuControl.GpuRing.StepsCompleted==3))
                    base.WriteDoubleWord(offset,value);
                return;
            }
            if(gpuControl.GpuIdInitialization && address==0x40090148 && value==0
                && gpuControl.GpuPower.Phase=="on" && (gpuControl.GpuEpochInterruptClears>0 || (gpuControl.GpuRuntimeWakeResponse!=-1 && gpuControl.GpuRuntimeWakeCycles>0)) && !gpuControl.GpuIdInitialized)
            { gpuControl.GpuIdInitialized = true; return; }
            if(gpuControl.GpuInterruptClear && address==0x400900f8 && value==0 && gpuControl.GpuPower.Phase=="on")
            { if(gpuControl.GpuCommandDevice!=null)gpuControl.GpuCommandDevice.AcknowledgeInterrupt();gpuControl.GpuInterruptClears++; gpuControl.GpuEpochInterruptClears++; return; }
            if(address==0x40021004 && GpuCommandDevice!=null && GpuCommandDevice.HasPendingWork && (value&0x40000)==0)
            { base.WriteDoubleWord(offset,value);return; }
            if((Uarts.Count!=0 || IomPowers.Count!=0 || Mspi0Power!=null || Mspi1Power!=null || OtpPower!=null || CryptoPower!=null) && address==0x40021004)
            {
                var gx=value&0x40000u; var ad=value&0x2000u;
                var gc=gx!=GpuPower.RequestWord; var ac=ad!=AdcPower.RequestWord;
                var m0c=Mspi0Power!=null && (value&Mspi0Power.Mask)!=Mspi0Power.RequestWord;
                var mc=Mspi1Power!=null && (value&Mspi1Power.Mask)!=Mspi1Power.RequestWord;
                var oc=OtpPower!=null && (value&OtpPower.Mask)!=OtpPower.RequestWord;
                var cc=CryptoPower!=null && (value&CryptoPower.Mask)!=CryptoPower.RequestWord;
                uint allowed=0x42000; int changes=System.Convert.ToInt32(gc)+System.Convert.ToInt32(ac)+System.Convert.ToInt32(mc)+System.Convert.ToInt32(m0c)+System.Convert.ToInt32(oc)+System.Convert.ToInt32(cc); int changedUart=-1; int changedIom=-1;
                if(Mspi1Power!=null)allowed|=Mspi1Power.Mask;
                if(Mspi0Power!=null)allowed|=Mspi0Power.Mask;
                if(OtpPower!=null)allowed|=OtpPower.Mask;
                if(CryptoPower!=null)allowed|=CryptoPower.Mask;
                foreach(var pair in UartPowers)
                {
                    allowed|=pair.Value.Mask;
                    if((value&pair.Value.Mask)!=pair.Value.RequestWord) { changes++; changedUart=pair.Key; }
                }
                foreach(var pair in IomPowers)
                {
                    allowed|=pair.Value.Mask;
                    if((value&pair.Value.Mask)!=pair.Value.RequestWord) { changes++; changedIom=pair.Key; }
                }
                var accepted=(value&~allowed)==0 && changes<=1;
                if(accepted && gc) accepted=GpuPower.TryWrite(gx,GpuPreparation.Complete);
                else if(accepted && ac) accepted=AdcPower.TryWrite(ad,AdcCalibrationControl.Value==0,AdcScan!=null && !AdcDisabledConfig.Enabled && AdcScan.Count==0 && AdcInternalTrigger.Phase=="stopped");
                else if(accepted && changedUart!=-1)
                {
                    var power=UartPowers[changedUart];
                    var held=UartPowers.Any(p => p.Key!=changedUart && p.Value.Phase=="on" && p.Value.RequestWord==p.Value.Mask && p.Value.StatusWord==p.Value.Mask);
                    accepted=UartHcpaGate
                        ? power.TryWriteShared(value&power.Mask,true,Uarts[changedUart].Quiescent,held)
                        : power.TryWrite(value&power.Mask,true,Uarts[changedUart].Quiescent);
                }
                else if(accepted && changedIom!=-1) accepted=IomPowers[changedIom].TryWrite(value&IomPowers[changedIom].Mask,true,IomPowers[changedIom].CanShutdown());
                else if(accepted && m0c) accepted=Mspi0Power.TryWrite(value&Mspi0Power.Mask,BuckResponsePhase=="active",Mspi0Power.CanShutdown());
                else if(accepted && mc) accepted=Mspi1Power.TryWrite(value&Mspi1Power.Mask,BuckResponsePhase=="active",Mspi1Power.CanShutdown());
                else if(accepted && oc) accepted=OtpPower.TryWrite(value&OtpPower.Mask,BuckResponsePhase=="active",CryptoOtpPowerLifecycle!=null && CryptoOtpPowerLifecycle.CanShutdownOtp());
                else if(accepted && cc) accepted=CryptoPower.TryWrite(value&CryptoPower.Mask,BuckResponsePhase=="active" && OtpPower.Phase=="on",CryptoOtpPowerLifecycle!=null && CryptoOtpPowerLifecycle.CanShutdownCrypto());
                if(accepted) DevicePowerWrites++; else base.WriteDoubleWord(offset,value);
                return;
            }
            if(AdcPower != null && address==0x40021004)
            {
                var gpuNext=value&0x40000u; var adcNext=value&0x2000u;
                var gpuChanged=gpuNext!=GpuPower.RequestWord;var adcChanged=adcNext!=AdcPower.RequestWord;
                var accepted=(value&~0x42000u)==0 && !(gpuChanged && adcChanged);
                if(accepted && gpuChanged) accepted=GpuPower.TryWrite(gpuNext,GpuPreparation.Complete);
                else if(accepted && adcChanged) accepted=AdcPower.TryWrite(adcNext,AdcCalibrationControl.Value==0,AdcScan!=null && !AdcDisabledConfig.Enabled && AdcScan.Count==0 && AdcInternalTrigger.Phase=="stopped");
                if(accepted) DevicePowerWrites++; else base.WriteDoubleWord(offset,value);
                return;
            }
            if(GpuPower != null && address==0x40021004)
            {
                if(GpuPower.TryWrite(value,GpuPreparation.Complete)) DevicePowerWrites++;
                else base.WriteDoubleWord(offset,value);
                return;
            }
            if(TryBeginGpuRuntimeWake(address,value)) return;
            if(GpuOffSequence != null && GpuPower.EpochRetired && GpuOffSequence.Owns(address))
            {
                if(!GpuOffSequence.TryWrite(address,value,GpuPower.Phase=="powered-off"
                    && GpuPreparation.Complete && BuckResponsePhase=="active"))
                    base.WriteDoubleWord(offset,value);
                return;
            }
            if(GpuPreparation != null)
            {
                var ready=BuckResponsePhase=="active" && VddfTempco.Applied && GfxPower.Selection==1
                    && GfxPower.Request==3 && McuClock.ModeWord==22 && McuClock.HfrcForced && (McuClock.MiscWord&32)!=0;
                if(GpuPreparation.TryWrite(address,value,ready)) return;
                if(GpuPreparation.StepsCompleted>0 && GpuPreparation.Owns(address))
                { base.WriteDoubleWord(offset,value); return; }
            }
            if(RtcOsel != null && address==0x4000400c)
            {
                if((value&~0x80u)!=0) base.WriteDoubleWord(offset,value);
                else { RtcOsel.Value=value; RtcOsel.Writes++; }
                return;
            }
            if(Mspi1Clock!=null && address==0x40004110)
            {
                if(!Mspi1Clock.TryWrite(value)) base.WriteDoubleWord(offset,value);
                return;
            }
            if(GfxPower != null && GfxPower.TryWrite(address,value,BuckResponsePhase=="active")) return;
            if(McuClock != null && McuClock.TryWrite(address,value,BuckResponsePhase=="active")) return;
            if(VddfTempco != null && VddfTempco.TryWrite(address,value,BuckResponsePhase == "active")) return;
            if(PrefetchStorage && address == 0xe001e004 && (value & ~0x3ffu) == 0)
            { PrefetchValue=value; PrefetchInitialized=true; PrefetchWrites++; return; }
            if(MemLdo != null && MemLdo.TryWrite(address,value)) return;
            if(CoreLdo != null && CoreLdo.TryWrite(address,value)) return;
            if(BuckStart != null && BuckStart.TryWrite(address,value,BuckOverrideComplete))
            {
                if(BuckStart.EnableRequested && BuckResponse != -1)
                { BuckResponsePhase = "requested"; BuckResponseTransitions++; }
                return;
            }
            if(MramControlStorage && address == 0x400211c8 && (value == 6 || value == MramValue))
            { MramValue = value; MramWrites++; return; }
            if(Uarts.Count!=0 && address==0x400201b0 && HalStorage!=null)
            {
                BlackwallUartAdapter target=null; int candidates=0;
                foreach(var pair in Uarts)
                {
                    var ready=UartPowers[pair.Key].Phase=="on";
                    if(pair.Value.CanClockSpare(HalStorage.Registers[address],value,ready)) { target=pair.Value; candidates++; }
                }
                if(candidates==1 && target.TryClockSpare(HalStorage.Registers[address],value,true)) return;
            }
            if(HalStorage != null && HalStorage.TryWrite(address,value)) return;
            if(MemoryStartup != null && MemoryStartup.TryWrite(address,value)) return;
            if(SpotStorage)
            {
                if(address == 0x40020028 && (value == 0x78 || value == 0x79))
                { AcrgValue = value; AcrgWrites++; return; }
                if(address == 0x40020060 && BuckOverrideStorage)
                {
                    var legacy = BuckOverrideStep == 0 && (value == 0 || value == 0x8000 || value == 0xc000 || value == 0xe000);
                    var b0TonOverride = HalStorage!=null && HalStorage.B0TonConfiguration;
                    var ordered = BuckOverrideStep < BuckSteps.Length && value == (b0TonOverride ? BuckSteps[BuckOverrideStep]&~0xe000u : BuckSteps[BuckOverrideStep])
                        && (BuckOverrideStep > 0 || VrctrlValue == (b0TonOverride ? 0u : 0xe000u));
                    var repeated = BuckOverrideComplete && value == VrctrlValue;
                    if(legacy || ordered || repeated)
                    {
                        VrctrlValue = value; VrctrlWrites++;
                        if(ordered) BuckOverrideStep++;
                        return;
                    }
                    base.WriteDoubleWord(offset,value);
                    return;
                }
                if(address == 0x40020060 && (value == 0 || value == 0x8000 || value == 0xc000 || value == 0xe000))
                { VrctrlValue = value; VrctrlWrites++; return; }
            }
            if(StartupControls)
            {
                if(address == 0x40021004 && value == 0) { DevicePowerWrites++; return; }
                if(address == 0x40020250 && value == 0) { DebugWrites++; return; }
                if(address == 0xe001e300 && value == 0) { CorePowerWrites++; return; }
                if(address == 0x4002021c && value <= 1) { WicWrites++; WicValue = value; return; }
            }
            if(baseAddress + (ulong)offset == 0x4000885c && initialLatch >= 0
                && (LatchValue & 2) != 0 && value == ((uint)LatchValue & ~4u))
            {
                LatchValue = (int)value;
                LatchWrites++;
                return;
            }
            base.WriteDoubleWord(offset, value);
        }

        public BlackwallCoreLdoReduction CoreLdo { get; }
        public BlackwallMemLdoSetup MemLdo { get; }
        public bool PrefetchStorage { get; }
        public bool PrefetchInitialized { get; private set; }
        public uint PrefetchValue { get; private set; }
        public int PrefetchReads { get; private set; }
        public int PrefetchWrites { get; private set; }
        public int BuckStatusFixture { get; }
        public int BuckResponse { get; }
        public string BuckResponsePhase { get; private set; }
        public int BuckResponseReads { get; private set; }
        public int BuckResponseTransitions { get; private set; }
        public BlackwallVddfTempco VddfTempco { get; }
        public BlackwallMcuClock McuClock { get; }
        // Request latch only: actual oscillator/silicon effects are deliberately unknown.
        public BlackwallMemoryRegister RtcOsel { get; }
        public IBlackwallRtc Rtc { get; }
        public IBlackwallStimer Stimer { get; }
        public BlackwallGfxPowerStorage GfxPower { get; }
        public BlackwallGpuPreparation GpuPreparation { get; }
        public BlackwallGpuOffSequence GpuOffSequence { get; }
        public BlackwallGpioConfig GpioConfig { get; }
        public BlackwallGpioInterruptIdle GpioInterrupts { get; }
        public BlackwallGpioOutputLatch GpioOutput { get; }
        public BlackwallGpioRoleInput GpioRoleInput { get; }
        public IBlackwallEm9305Reset Em9305Reset { get; }
        public BlackwallAdcInfoZeroFixture AdcInfo { get; }
        public BlackwallMemoryRegister AdcCalibrationControl { get; }
        public BlackwallAdcPower AdcPower { get; }
        public System.Collections.Generic.SortedDictionary<int,BlackwallUartAdapter> Uarts { get; } = new System.Collections.Generic.SortedDictionary<int,BlackwallUartAdapter>();
        public bool UartHcpaStatus { get; }
        public bool UartHcpaGate { get; }
        public System.Collections.Generic.SortedDictionary<int,BlackwallUartPower> UartPowers { get; } = new System.Collections.Generic.SortedDictionary<int,BlackwallUartPower>();
        public System.Collections.Generic.SortedDictionary<int,BlackwallPeripheralPower> IomPowers { get; } = new System.Collections.Generic.SortedDictionary<int,BlackwallPeripheralPower>();
        public BlackwallPeripheralPower Mspi1Power { get; }
        public BlackwallPeripheralPower Mspi0Power { get; }
        public BlackwallPeripheralPower OtpPower { get; }
        public BlackwallPeripheralPower CryptoPower { get; }
        public int CryptoNvmIdle { get; }
        public int CryptoNvmReads { get; private set; }
        public BlackwallOtpReadReadiness OtpReadReadiness { get; }
        public BlackwallOtpSerialSlots OtpSerialSlots { get; }
        public BlackwallCryptoOtpPowerLifecycle CryptoOtpPowerLifecycle { get; }
        public IBlackwallMspi1Clock Mspi1Clock { get; }
        public IBlackwallMspi1Config Mspi1Config { get; }
        public IBlackwallMspi1Config Mspi0Config { get; }
        public BlackwallCpuNormalSleep CpuNormalSleep { get; }
        public IBlackwallTimer14 Timer14 { get; }
        public BlackwallAdcInternalTrigger AdcInternalTrigger { get; }
        public BlackwallAdcConstantScan AdcScan { get; }
        public BlackwallAdcDisabledConfig AdcDisabledConfig { get; }
        public BlackwallMemoryRegister AdcTriggerConfig { get; }
        public bool AdcTriggerConfigured { get; private set; }
        public int AdcTriggerPowerBlocks { get; private set; }
        private readonly BlackwallG2StartupFixture gpuControlOwner;
        public int GpuInitialStatusHypothesis { get; }
        public int GpuInitialStatusReads { get; private set; }
        public bool GpuConfigLowResponse { get; }
        public int GpuConfigHighHypothesis { get; }
        public int GpuConfigLowReads { get; private set; }
        public int GpuConfigHighReads { get; private set; }
        public bool GpuRasterInitStorage { get; }
        public bool GpuRasterInitStored { get; private set; }
        public BlackwallGpuInitialReset GpuReset { get; }
        public int GpuIdentityProfile { get; }
        public int GpuIdentityReads { get; private set; }
        public BlackwallGpuRingConfiguration GpuRing { get; }
        public IBlackwallGpuCommandDevice GpuCommandDevice {get;private set;}
        public void AttachGpuCommandDevice(IBlackwallGpuCommandDevice device)
        {
            if(device==null || GpuCommandDevice!=null || GpuRuntimeWakeResponse==-1)
                throw new System.InvalidOperationException("GPU consumer requires one explicit runtime profile");
            GpuCommandDevice=device;
        }
        public bool GpuIdInitialization { get; }
        public bool GpuIdInitialized { get; private set; }
        public bool GpuInterruptClear { get; }
        public int GpuInterruptClears { get; private set; }
        public int GpuRuntimeWakeResponse { get; }
        public int GpuRuntimeWakeCycles { get; private set; }
        public int GpuEpochIdentityReads { get; private set; }
        public int GpuEpochInterruptClears { get; private set; }
        public bool TryBeginGpuRuntimeWake(ulong address,uint value)
        {
            if(GpuRuntimeWakeResponse==-1 || GpuPower==null || !GpuPower.EpochRetired
                || GpuPower.Phase!="powered-off" || !GpuOffSequence.Complete) return false;
            var ready=BuckResponsePhase=="active" && VddfTempco.Applied && GfxPower.Selection==1
                && GfxPower.Request==3 && McuClock.ModeWord==22 && McuClock.HfrcForced && (McuClock.MiscWord&32)!=0;
            if(!GpuPreparation.CanRearm(address,value,ready))return false;
            GpuPreparation.Rearm();GpuOffSequence.Rearm();GpuPower.Rearm();GpuRuntimeWakeCycles++;
            GpuEpochIdentityReads=GpuEpochInterruptClears=0;
            GpuIdInitialized=false;GpuRasterInitStored=false;
            if(GpuCommandDevice!=null)GpuCommandDevice.BeginEpoch();
            if(GpuRing!=null)GpuRing.Reset();if(GpuReset!=null)GpuReset.Reset();
            if(!GpuPreparation.TryWrite(address,value,ready))throw new System.InvalidOperationException("Validated GPU wake did not commit");
            return true;
        }
        public BlackwallGpuPower GpuPower { get; }
        public int BuckStatusReads { get; private set; }
        public BlackwallBuckStart BuckStart { get; }
        public bool BuckOverrideStorage { get; }
        public int BuckOverrideStep { get; private set; }
        public bool BuckOverrideComplete => BuckOverrideStep == BuckSteps.Length;
        private static readonly uint[] BuckSteps = {0x2e000,0x6e000,0xee000,0xfe000,0xfe000,0xfe00e,0xfe00f,0xfe00f,0xfe1cf,0xfe1ef};
        public bool MramControlStorage { get; }
        public uint MramValue { get; private set; }
        public int MramReads { get; private set; }
        public int MramWrites { get; private set; }
        public BlackwallHalStorage HalStorage { get; }
        public BlackwallMemoryStartup MemoryStartup { get; }
        public int ChipRevision { get; }
        public BlackwallChipIdentity ChipInfo { get; }
        public BlackwallG2StartupFixture ChipInfoOwner { get; }
        public int ChipRevisionReads { get; private set; }
        public bool SpotStorage { get; }
        public uint AcrgValue { get; private set; }
        public int AcrgReads { get; private set; }
        public int AcrgWrites { get; private set; }
        public uint VrctrlValue { get; private set; }
        public int VrctrlReads { get; private set; }
        public int VrctrlWrites { get; private set; }
        public string AnalogPower => "not-modeled";
        public string ShadowInfo1 { get; }
        public string Info1Metadata { get; }
        public int Info1TrimRevision {get;}
        public int ShadowReads { get; private set; }
        public int TrackerReads { get; private set; }
        public int TrimRevisionReads { get; private set; }
        public int Ft1Reads { get; private set; }
        public bool ValidCalibration => false;
        private uint MetadataValue => Info1Metadata == "erased" ? 0xffffffffu : 0u;
        public string PowerMode { get; }
        public int PowerReads { get; private set; }
        public int LatchReads { get; private set; }
        public int LatchWrites { get; private set; }
        public int LatchValue { get; private set; }
        public bool StartupControls { get; }
        public int DevicePowerReads { get; private set; }
        public int DevicePowerWrites { get; private set; }
        public int DebugReads { get; private set; }
        public int DebugWrites { get; private set; }
        public int CorePowerReads { get; private set; }
        public int CorePowerWrites { get; private set; }
        public int WicReads { get; private set; }
        public int WicWrites { get; private set; }
        public uint WicValue { get; private set; }
        public bool HardwareVerified => false;
        public string PowerTransitions => "not-modeled";
        public string LatchMeaning => "hypothesized-reset-status-shadow";
        private readonly int initialLatch;
    }
}

namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    public sealed class BlackwallMemoryRegister
    {
        public BlackwallMemoryRegister(uint value) { InitialValue = Value = value; }
        public uint InitialValue { get; }
        public uint Value { get; internal set; }
        public int Reads { get; internal set; }
        public int Writes { get; internal set; }
    }

    public sealed class BlackwallMemoryStartup
    {
        public BlackwallMemoryStartup(int romEnableResponse=-1)
        {
            if(romEnableResponse < -1 || romEnableResponse>1)throw new System.ArgumentException("Explicit ROM power response required");
            RomEnableResponse=romEnableResponse;
            registers = new System.Collections.Generic.Dictionary<ulong,BlackwallMemoryRegister>
            {
                {0x40021014,new BlackwallMemoryRegister(0x3f)},
                {0x40021018,new BlackwallMemoryRegister(0xcf)},
                {0x4002101c,new BlackwallMemoryRegister(2)},
                {0x40021024,new BlackwallMemoryRegister(7)},
                {0x40021028,new BlackwallMemoryRegister(7)},
                {0x4002102c,new BlackwallMemoryRegister(0x7e38)},
                {0x40021040,new BlackwallMemoryRegister(0x1b0c)},
            };
        }

        public void Reset()
        {
            RomDisables = RomEnables = 0;
            foreach(var register in registers.Values)
            { register.Value = register.InitialValue; register.Reads = register.Writes = 0; }
        }

        public bool TryRead(ulong address,out uint value)
        {
            value = 0;
            if(!registers.TryGetValue(address,out var register)) return false;
            register.Reads++;
            value = register.Value;
            return true;
        }

        public bool TryWrite(ulong address,uint value)
        {
            if(!registers.TryGetValue(address,out var register)) return false;
            if(address == 0x40021014)
            {
                if(value != register.Value)
                {
                    if(value==0x1f && register.Value==0x3f)
                    {
                        registers[0x40021018].Value=0x4f; RomDisables++;
                    }
                    else if(value==0x3f && register.Value==0x1f && RomEnableResponse!=-1)
                    {
                        // Explicit ready/stuck functional profile; no ROM code or timing model.
                        registers[0x40021018].Value=RomEnableResponse==1 ? 0xcfu : 0x4fu; RomEnables++;
                    }
                    else return false;
                }
            }
            else if(address == 0x4002101c) { if(value > 3) return false; }
            else if(address == 0x40021024) { if(value != 7) return false; }
            else if(address == 0x4002102c) { if((value & ~0x7e3fu) != 0) return false; }
            else if(address == 0x40021040) { if(value != 0x1b0c && value != 0x30c && value != 0xc) return false; }
            else return false;
            register.Writes++;
            register.Value = value;
            return true;
        }

        public System.Collections.Generic.IReadOnlyDictionary<ulong,BlackwallMemoryRegister> Registers => registers;
        public int RomDisables { get; private set; }
        public int RomEnables {get;private set;}
        public int RomEnableResponse {get;}
        private readonly System.Collections.Generic.Dictionary<ulong,BlackwallMemoryRegister> registers;
    }
}

namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    public sealed class BlackwallHalStorage
    {
        public BlackwallHalStorage(bool b0TonConfiguration = false)
        {
            B0TonConfiguration=b0TonConfiguration;
            if(b0TonConfiguration) Add(0x40020340,0x00400000);
            Add(0x4002036c,0x0);
            Add(0x40020088,0x207c0774);
            Add(0x40020044,0xffc0);
            Add(0x4002004c,0x1fefc0);
            Add(0x40020374,0x0);
            Add(0x40020080,0x6d3d4);
            Add(0x40021108,0x0);
            Add(0x400201b0,0x0);
            Add(0x40020344,0x0);
            Add(0x4002034c,0x0);
            Add(0x40020358,0x0);
            Add(0x40020354,0x0);
            Add(0x40004020,0x25b800,0x25b800);
            Add(0x40004044,0x0,0x0,0xfbbfc0);
            Add(0x40004120,0x0,0x0);
            Add(0x40020448,0x200,0x200,0x400);
            Add(0x4002037c,0x80,0x80,0x40000080);
            Add(0x40020380,0x0,0x0,0x10000,0x11000);
            Add(0x400211a0,0x0,0x0,0x3e80000);
            Add(0x400211a4,0x0,0x0,0x320);
            Add(0x400211a8,0x0,0x0);
            Add(0x400211ac,0x0,0x0,0x1c2);
            Add(0x400211b4,0x0,0x0,0x258);
            Add(0x400211bc,0x0,0x0,0xfa);
            Add(0x40008858,0x0,0x0,0x5af00000);
        }

        private void Add(ulong address,uint initial,params uint[] observedWrites)
        {
            registers.Add(address,new BlackwallMemoryRegister(initial));
            allowed.Add(address,observedWrites);
        }

        public void Reset()
        {
            foreach(var register in registers.Values)
            { register.Value = register.InitialValue; register.Reads = register.Writes = 0; }
        }

        public bool TryRead(ulong address,out uint value)
        {
            value = 0;
            if(!registers.TryGetValue(address,out var register)) return false;
            register.Reads++;
            value = register.Value;
            return true;
        }

        public bool TryWrite(ulong address,uint value)
        {
            if(!registers.TryGetValue(address,out var register)) return false;
            uint mask=B0TonConfiguration ? TonMask(address) : 0;
            if(mask!=0)
            {
                if(((register.Value^value)&~mask)!=0) return false;
                if(address!=0x40020340 && (registers[0x40020340].Value&0x80000000u)==0) return false;
            }
            else if(System.Array.IndexOf(allowed[address],value)<0) return false;
            register.Writes++;
            register.Value = value;
            return true;
        }

        public bool B0TonConfiguration {get;}
        private static uint TonMask(ulong address)
        {
            switch(address)
            {
                case 0x40020340:return 0x80000000u;
                case 0x40020344:case 0x4002034c:return 0x3e00f800u;
                case 0x40020354:return 0x003e0000u;
                case 0x40020358:return 0x00001f00u;
                default:return 0;
            }
        }

        public bool TrimReadsObserved
        {
            get { foreach(var pair in allowed) if(pair.Value.Length == 0 && registers[pair.Key].Reads == 0) return false; return true; }
        }
        public string TrimCatalogSha256 => "0be186eab9db2c72cdc2fb8b82d72b2498aab90b5817843538d583c231ee9366";
        public System.Collections.Generic.IReadOnlyDictionary<ulong,BlackwallMemoryRegister> Registers => registers;
        private readonly System.Collections.Generic.Dictionary<ulong,BlackwallMemoryRegister> registers =
            new System.Collections.Generic.Dictionary<ulong,BlackwallMemoryRegister>();
        private readonly System.Collections.Generic.Dictionary<ulong,uint[]> allowed =
            new System.Collections.Generic.Dictionary<ulong,uint[]>();
    }
}

namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    public sealed class BlackwallBuckStart
    {
        public BlackwallBuckStart()
        {
            registers = new System.Collections.Generic.Dictionary<ulong,BlackwallMemoryRegister>();
            foreach(var address in Addresses) registers.Add(address,new BlackwallMemoryRegister(0));
        }
        public void Reset()
        {
            StepsCompleted = 0;
            foreach(var r in registers.Values) { r.Value = 0; r.Reads = r.Writes = 0; }
        }
        public bool TryRead(ulong address,out uint value)
        {
            value = 0;
            if(!registers.TryGetValue(address,out var r)) return false;
            value = r.Value; r.Reads++; return true;
        }
        public bool TryWrite(ulong address,uint value,bool overrideComplete)
        {
            if(!overrideComplete || StepsCompleted >= Addresses.Length || address != Addresses[StepsCompleted]
                || value != Values[StepsCompleted]) return false;
            var r = registers[address]; r.Value = value; r.Writes++; StepsCompleted++; return true;
        }
        public bool EnableRequested => StepsCompleted == Addresses.Length;
        public int StepsCompleted { get; private set; }
        public System.Collections.Generic.IReadOnlyDictionary<ulong,BlackwallMemoryRegister> Registers => registers;
        private static readonly ulong[] Addresses = {0x40020378,0x4002033c,0x40021100};
        private static readonly uint[] Values = {0x80000000,0xf,1};
        private readonly System.Collections.Generic.Dictionary<ulong,BlackwallMemoryRegister> registers;
    }
}

namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    public sealed class BlackwallCoreLdoReduction
    {
        public BlackwallCoreLdoReduction(BlackwallHalStorage hal,BlackwallBuckStart start)
        { this.hal = hal; this.start = start; OriginalWord = hal.Registers[Address].InitialValue; }
        public void Reset() { Applied = false; }
        public bool TryWrite(ulong address,uint value)
        {
            if(address != Address || Applied || start.StepsCompleted != 2 || !hal.TrimReadsObserved) return false;
            var r = hal.Registers[Address];
            if(value != ((r.Value & ~0x3ffu) | ReducedTrim)) return false;
            r.Value = value; r.Writes++; Applied = true; return true;
        }
        public uint OriginalWord { get; }
        private uint Reduction => hal.B0TonConfiguration ? 6u : 7u;
        public uint ReducedTrim => (OriginalWord & 0x3ff) > Reduction ? (OriginalWord & 0x3ff)-Reduction : 0;
        public bool Applied { get; private set; }
        public bool CacheWitness => hal.TrimReadsObserved;
        private const ulong Address = 0x40020080;
        private readonly BlackwallHalStorage hal;
        private readonly BlackwallBuckStart start;
    }
}

namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    public sealed class BlackwallMemLdoSetup
    {
        public BlackwallMemLdoSetup(BlackwallHalStorage hal,BlackwallBuckStart start,BlackwallCoreLdoReduction core)
        { this.hal = hal; this.start = start; this.core = core; }
        public void Reset() { StepsCompleted = 0; }
        public bool TryWrite(ulong address,uint value)
        {
            if(StepsCompleted >= Addresses.Length || start.StepsCompleted != 3 || !core.Applied) return false;
            if(address != Addresses[StepsCompleted]) return false;
            var r = hal.Registers[address];
            var field = hal.B0TonConfiguration ? (StepsCompleted==0 ? 0u : 0x8000u) : Fields[StepsCompleted];
            if(value != ((r.Value & ~Masks[StepsCompleted]) | field)) return false;
            r.Value = value; r.Writes++; StepsCompleted++; return true;
        }
        public int StepsCompleted { get; private set; }
        private static readonly ulong[] Addresses = {0x40020088,0x400201b0};
        private static readonly uint[] Masks = {0x3f,0x18000};
        private static readonly uint[] Fields = {1,0x10000};
        private readonly BlackwallHalStorage hal;
        private readonly BlackwallBuckStart start;
        private readonly BlackwallCoreLdoReduction core;
    }

    public sealed class BlackwallVddfTempco
    {
        public BlackwallVddfTempco(BlackwallHalStorage hal,BlackwallMemLdoSetup setup)
        { this.hal=hal; this.setup=setup; OriginalWord=hal.Registers[Address].InitialValue; }
        public void Reset() { Applied=false; }
        public bool TryWrite(ulong address,uint value,bool active)
        {
            if(address!=Address || !active || setup.StepsCompleted!=2) return false;
            var r=hal.Registers[Address];
            var expected=(OriginalWord & ~127u) | ReducedTrim;
            if(r.Reads<2 || ((value ^ r.Value) & ~127u)!=0) return false;
            if(!Applied && (r.Value!=OriginalWord || value!=expected)) return false;
            r.Value=value; r.Writes++; Applied=true; return true;
        }
        public bool Applied { get; private set; }
        public uint OriginalWord { get; }
        public uint ReducedTrim => (OriginalWord & 127)>10 ? (OriginalWord & 127)-10 : 0;
        private const ulong Address=0x4002004c;
        private readonly BlackwallHalStorage hal;
        private readonly BlackwallMemLdoSetup setup;
    }

    public sealed class BlackwallGpuInitialReset
    {
        public void Reset() { StepsCompleted=0; }
        public bool TryWrite(ulong address,uint value,bool ready)
        {
            if(!ready || value!=0) return false;
            if((StepsCompleted==0 && address==0x400900e8) || (StepsCompleted==1 && address==0x400900fc))
            { StepsCompleted++; return true; }
            return false;
        }
        public int StepsCompleted { get; private set; }
        public int CommandProcessorResets => StepsCompleted>0 ? 1 : 0;
        public int GpuResets => StepsCompleted==2 ? 1 : 0;
        public bool RingRequiresRevalidation => StepsCompleted>0;
    }

    public sealed class BlackwallGpuRingConfiguration
    {
        public void Reset() { StepsCompleted=0; RequestWord=BaseAddress=ByteLength=0; }
        public bool TryWrite(ulong address,uint value,bool ready)
        {
            if(!ready) return false;
            if(StepsCompleted==0 && address==0x400900ec && (value&7)==6)
            {
                var start=value&~7u;
                if(start<0x20000000 || start>0x20380000-16) return false;
                RequestWord=value; BaseAddress=start; StepsCompleted++; return true;
            }
            if(StepsCompleted==1 && address==0x400900f0 && value==BaseAddress)
            { StepsCompleted++; return true; }
            if(StepsCompleted==2 && address==0x400900f4 && value>=16 && value<=65536
                && value%16==0 && (ulong)BaseAddress+value<=0x20380000)
            { ByteLength=value; StepsCompleted++; return true; }
            return false;
        }
        public int StepsCompleted { get; private set; }
        public uint RequestWord { get; private set; }
        public uint BaseAddress { get; private set; }
        public uint ByteLength { get; private set; }
    }

    public sealed class BlackwallGpuPower
    {
        public BlackwallGpuPower(int profile,int offProfile=-1,int runtimeProfile=-1)
        { if(runtimeProfile < -1 || runtimeProfile > 1)throw new System.ArgumentException("Invalid GPU runtime response");Profile=profile;OffProfile=offProfile;RuntimeProfile=runtimeProfile;Reset(); }
        public void Reset()
        { Phase="off"; RequestWord=StatusWord=0; EnableReads=StatusReads=EnableWrites=Transitions=0; EpochRetired=false; OffRequests=0; activeProfile=Profile; }
        public void Rearm()
        {
            if(RuntimeProfile==-1 || Phase!="powered-off" || !EpochRetired || StatusWord!=0 || RequestWord!=0)
                throw new System.InvalidOperationException("GPU power epoch is not retired and powered off");
            Phase="off";EpochRetired=false;activeProfile=RuntimeProfile;
        }
        public uint ReadEnable() { EnableReads++; return RequestWord; }
        public uint ReadStatus()
        {
            StatusReads++;
            if(Phase=="requested")
            { Phase=activeProfile==1 ? "on" : "stuck-off"; StatusWord=activeProfile==1 ? Mask : 0; Transitions++; }
            if(Phase=="off-requested")
            { Phase=OffProfile==1 ? "powered-off" : "stuck-on"; StatusWord=OffProfile==1 ? 0 : Mask; Transitions++; }
            return StatusWord;
        }
        public bool TryWrite(uint value,bool preparationComplete)
        {
            if(value==Mask && preparationComplete && Phase!="cancelled" && !EpochRetired)
            {
                if(RequestWord==0) { Phase="requested"; RequestWord=Mask; Transitions++; }
                EnableWrites++; return true;
            }
            if(value==0 && Phase=="on" && OffProfile!=-1)
            { RequestWord=0; Phase="off-requested"; EpochRetired=true; OffRequests++; EnableWrites++; Transitions++; return true; }
            if(value==0 && Phase!="on" && !EpochRetired)
            {
                if(RequestWord!=0) { Phase="cancelled"; RequestWord=StatusWord=0; Transitions++; }
                EnableWrites++; return true;
            }
            return false;
        }
        public int Profile { get; }
        public int OffProfile { get; }
        public int RuntimeProfile { get; }
        private int activeProfile;
        public bool EpochRetired { get; private set; }
        public int OffRequests { get; private set; }
        public string Phase { get; private set; }
        public uint RequestWord { get; private set; }
        public uint StatusWord { get; private set; }
        public int EnableReads { get; private set; }
        public int StatusReads { get; private set; }
        public int EnableWrites { get; private set; }
        public int Transitions { get; private set; }
        private const uint Mask=0x40000;
    }

    public sealed class BlackwallAdcInternalTrigger : IPeripheral
    {
        public BlackwallAdcInternalTrigger(IMachine machine,long sourceHz)
        {
            if(sourceHz<1 || sourceHz>48000000) throw new System.ArgumentException("ADC trigger source Hz must be 1..48000000");
            this.machine=machine; SourceHz=(ulong)sourceHz;
            timer=new LimitTimer(machine.ClockSource,1,this,"FirstTrigger",1,Direction.Ascending,enabled:false,workMode:WorkMode.Periodic,eventEnabled:true);
            timer.LimitReached += () =>
            {
                TriggerEvents++;
                if(Scan!=null)
                {
                    if(!Scan.Primed || Scan.TryScan()) return;
                    timer.Enabled=false; Phase="scan-required"; machine.PauseAndRequestEmulationPause(); return;
                }
                timer.Enabled=false; Phase="trigger-consumption-required";
                machine.PauseAndRequestEmulationPause();
            };
            Reset();
        }
        public void Reset() { timer.Reset(); timer.Enabled=false; Phase="idle"; Word=0; StartRequests=TriggerEvents=0; Divider=TickLimit=0; }
        private void SyncTime() { if(machine.SystemBus.TryGetCurrentCPU(out var cpu)) cpu.SyncTime(); }
        public bool TryStart(uint word,uint previous,uint cfg)
        {
            if(Phase=="armed") { SyncTime(); return Phase=="armed" && word==Word; }
            if((Phase!="idle" && Phase!="stopped") || (previous&0x80000000u)!=0 || word!=(previous|0x80000000u) || (cfg&0x100005u)!=0x100005u) return false;
            var code=(word>>16)&7; var count=word&0x3ffu;
            if((code!=0 && code!=1 && code!=2 && code!=4) || count==0) return false;
            var divider=1ul<<(int)code;
            if(SourceHz%divider!=0 || SourceHz/divider==0) return false;
            SyncTime(); Word=word; Divider=divider; TickLimit=count; StartRequests++; Phase="armed";
            timer.Frequency=SourceHz/divider; timer.Limit=count; timer.ResetValue(); timer.Enabled=true; return true;
        }
        public BlackwallAdcConstantScan Scan { get; set; }
        public bool TryStop()
        {
            if(Scan==null || Phase!="armed") return false;
            timer.Enabled=false; Phase="stopped"; return true;
        }
        public ulong SourceHz { get; }
        public string Phase { get; private set; }
        public uint Word { get; private set; }
        public ulong Divider { get; private set; }
        public uint TickLimit { get; private set; }
        public int StartRequests { get; private set; }
        public int TriggerEvents { get; private set; }
        private readonly IMachine machine;
        private readonly LimitTimer timer;
    }

    public sealed class BlackwallAdcConstantScan
    {
        public BlackwallAdcConstantScan(BlackwallAdcDisabledConfig bank,uint rawCode) { if(bank==null || rawCode>4095) throw new System.ArgumentException("ADC constant input requires bank/code0..4095"); this.bank=bank; RawCode=rawCode; }
        public uint RawCode { get; }
        public bool Primed { get; private set; }
        public int Scans { get; private set; }
        public int Samples { get; private set; }
        public int Pops { get; private set; }
        public int Peeks { get; private set; }
        public int SoftwareTriggers { get; private set; }
        public uint Pending { get; private set; }
        public string Blocked { get; private set; }
        public int Count { get { lock(sync) return fifo.Count; } }
        public void Reset() { lock(sync) { fifo.Clear(); Primed=false; Scans=Samples=Pops=Peeks=SoftwareTriggers=0; Pending=0; Blocked="none"; } }
        public bool Owns(ulong a) { return a==0x40038008 || a==0x40038038 || a==0x4003803c || (a>=0x40038200 && a<=0x4003820c); }
        public bool TryScan()
        {
            lock(sync)
            {
                var values=new System.Collections.Generic.List<uint>();
                if(!bank.Enabled) { Blocked="adc-disabled"; return false; }
                for(uint i=0;i<8;i++)
                {
                    var v=bank.Values[0x4003800c+i*4]; if((v&1)==0) continue;
                    if(((v>>8)&15)!=3 || ((v>>16)&3)>1 || (v&2)!=0) { Blocked="unsupported-slot"; return false; }
                    values.Add((i<<28)|(RawCode<<6));
                }
                if(values.Count==0 || fifo.Count+values.Count>16) { Blocked="empty-scan-or-capacity"; return false; }
                foreach(var v in values) fifo.Enqueue(v);
                Scans++; Samples+=values.Count; Pending|=3;
                if(fifo.Count>=12) Pending|=4; if(fifo.Count==16) Pending|=8;
                return true;
            }
        }
        public bool TryRead(ulong address,out uint value)
        {
            lock(sync)
            {
                value=0;
                if(address==0x40038200) return true;
                if(address==0x40038204) { value=Pending; return true; }
                if(address!=0x40038038 && address!=0x4003803c) return false;
                var pop=address==0x4003803c && (bank.Values[0x40038000]&0x1000)!=0;
                if(fifo.Count==0) { if(pop) return false; Peeks++; return true; }
                var entry=fifo.Peek(); if(pop) { fifo.Dequeue(); Pops++; } else Peeks++;
                value=entry|((uint)fifo.Count<<20); return true;
            }
        }
        public bool TryWrite(ulong address,uint value)
        {
            lock(sync)
            {
                if(address==0x40038008)
                {
                    if(value!=0x37 || (bank.Values[0x40038000]&0x70001)!=0x70001 || !TryScan()) return false;
                    SoftwareTriggers++; Primed=true; return true;
                }
                if(address==0x40038038) { if(fifo.Count!=0) { fifo.Dequeue(); Pops++; } return true; }
                if(address==0x40038200 && value==0) return true;
                if(address==0x40038208 && (value&~0xfffu)==0) { Pending&=~value; return true; }
                return false;
            }
        }
        private readonly BlackwallAdcDisabledConfig bank;
        private readonly object sync=new object();
        private readonly System.Collections.Generic.Queue<uint> fifo=new System.Collections.Generic.Queue<uint>();
    }

    public sealed class BlackwallAdcDisabledConfig
    {
        public BlackwallAdcDisabledConfig(bool enableLatch=false) { EnableLatch=enableLatch; }
        public bool EnableLatch { get; }
        public bool SourceReset { get; set; }
        public bool StopAllowed { get; set; }
        public int EnableRequests { get; private set; }
        public bool Enabled { get { return Values.TryGetValue(0x40038000,out var cfg) && (cfg&1)!=0; } }
        public readonly System.Collections.Generic.Dictionary<ulong,uint> Values = new System.Collections.Generic.Dictionary<ulong,uint>();
        public int Reads { get; private set; }
        public int Writes { get; private set; }
        public int PowerBlocks { get; private set; }
        public void Reset()
        {
            Values.Clear(); Reads=Writes=PowerBlocks=EnableRequests=0; StopAllowed=false;
            if(SourceReset) { Values[0x40038000]=0; for(ulong a=0x4003800c;a<=0x40038028;a+=4) Values[a]=0; }
        }
        public bool Owns(ulong address) { return address==0x40038000 || (address>=0x4003800c && address<=0x40038028 && (address&3)==0); }
        public bool TryRead(ulong address,bool powered,out uint value)
        {
            value=0;
            if(!powered) { PowerBlocks++; return false; }
            if(!Values.TryGetValue(address,out value)) return false;
            Reads++; return true;
        }
        public bool TryWrite(ulong address,uint value,bool powered,bool timerConfigured=false)
        {
            if(!powered) { PowerBlocks++; return false; }
            if(Enabled)
            {
                if(address!=0x40038000) return false;
                var old=Values[address];
                if(SourceReset && StopAllowed && ((value==(old&~4u)) || ((old&4)==0 && value==(old&~1u))))
                { Values[address]=value; Writes++; return true; }
                if(value!=old) return false;
                Writes++; return true;
            }
            if(address==0x40038000 && (value&1)!=0)
            {
                if(!EnableLatch || !timerConfigured || !Values.TryGetValue(address,out var previous) || value!=(previous|1u)) return false;
                Values[address]=value; Writes++; EnableRequests++; return true;
            }
            if(address==0x40038000)
            {
                var trigger=(value>>16)&7;
                if((value&~0x71f101cu)!=0 || ((value>>24)&7)!=2 || (trigger>4 && trigger!=7)) return false;
            }
            else
            {
                if(!Values.ContainsKey(0x40038000) || (value&~0x7ff0f03u)!=0 || ((value>>18)&63)<32 || ((value>>8)&15)>11) return false;
            }
            Values[address]=value; Writes++; return true;
        }
    }

    public sealed class BlackwallCpuNormalSleep : IPeripheral
    {
        public BlackwallCpuNormalSleep(IMachine machine,string profile,uint flushReadPc)
        {
            if(machine==null || profile!="normal-sleep-storage" || flushReadPc<0x438000 || flushReadPc>=0x800000 || (flushReadPc&1)!=0)
                throw new System.ArgumentException("Explicit normal sleep storage, machine and original flush PC required");
            this.machine=machine;FlushReadPc=flushReadPc;Reset();
        }
        public bool Owns(ulong address) => address==0x40021050 || address==0xe001e300 || address==0x47ff0000;
        public void Reset() { PowerControlReads=CpdReads=CpdWrites=FlushReads=CpdValue=0; }
        public bool TryRead(ulong address,out uint value)
        {
            value=0;
            if(address==0x40021050) { PowerControlReads++;return true; }
            if(address==0xe001e300) { value=CpdValue;CpdReads++;return true; }
            if(address==0x47ff0000 && machine.SystemBus.TryGetCurrentCPU(out var current))
            {
                var cpu=current as CortexM;
                if(cpu!=null)return TryReadFlush((uint)cpu.PC.RawValue,(uint)cpu.GetRegister(0).RawValue,out value);
            }
            return false;
        }
        public bool TryWrite(ulong address,uint value)
        {
            if(address!=0xe001e300 || (value!=0 && value!=0x11u) || (value==0x11u && PowerControlReads<=FlushReads))return false;
            CpdValue=value;CpdWrites++;return true;
        }
        public bool TryReadFlush(uint pc,uint baseRegister,out uint value)
        {
            value=0;
            if(pc!=FlushReadPc || baseRegister!=0x47ff0000u || CpdValue!=0x11u || PowerControlReads<=FlushReads)return false;
            // Declared synchronous bus fixture; not a physical APB latency model.
            FlushReads++;return true;
        }
        public uint PowerControlReads { get; private set; }
        public uint CpdReads { get; private set; }
        public uint CpdWrites { get; private set; }
        public uint FlushReads { get; private set; }
        public uint CpdValue { get; private set; }
        public uint FlushReadPc { get; }
        private readonly IMachine machine;
    }
    public class BlackwallPeripheralPower : IPeripheral
    {
        public BlackwallPeripheralPower(uint mask,int profile,int offProfile=-1,bool synchronousOffResponse=false)
        {
            if(mask==0 || (mask&(mask-1))!=0 || profile<0 || profile>1 || offProfile < -1 || offProfile > 1) throw new System.ArgumentException("Power domain requires one mask bit and known profiles");
            if(synchronousOffResponse && offProfile!=0)throw new System.ArgumentException("Synchronous off response requires successful off profile");
            SynchronousOffResponse=synchronousOffResponse;
            Mask=mask; Profile=profile; OffProfile=offProfile; Reset();
        }
        public System.Func<bool> ShutdownReady { get; set; }
        public event System.Action PoweredOff;
        public bool CanShutdown() => ShutdownReady!=null && ShutdownReady();
        public void Reset() { Generation++; Phase="off"; RequestWord=StatusWord=0; Requests=Responses=OffRequests=PowerCycles=0; }
        public bool TryWrite(uint value,bool ready,bool quiescent=false)
        {
            if(value==0 && Phase=="on" && OffProfile!=-1 && quiescent) { Generation++; RequestWord=0; Phase="off-requested"; OffRequests++; if(SynchronousOffResponse)ReadStatus(); return true; }
            if(value==Mask && ready && (Phase=="off" || (Phase=="powered-off" && OffProfile==0))) { Generation++; RequestWord=value; Phase="requested"; Requests++; return true; }
            if(value==0 && (Phase=="requested" || Phase=="stuck-off")) { Generation++; RequestWord=StatusWord=0; Phase="cancelled"; return true; }
            return false;
        }
        public uint ReadStatus()
        {
            if(Phase=="requested") { Phase=Profile==1 ? "on" : "stuck-off"; StatusWord=Profile==1 ? Mask : 0; Responses++; }
            else if(Phase=="off-requested") { Phase=OffProfile==0 ? "powered-off" : "stuck-on"; StatusWord=OffProfile==0 ? 0 : Mask; Responses++; if(OffProfile==0) { PowerCycles++; PoweredOff?.Invoke(); } }
            return StatusWord;
        }
        public uint Mask { get; }
        public ulong Generation { get; protected set; }
        public bool SynchronousOffResponse {get;}
        public int OffProfile { get; }
        public int OffRequests { get; protected set; }
        public int PowerCycles { get; private set; }
        public int Profile { get; }
        public string Phase { get; protected set; }
        public uint RequestWord { get; protected set; }
        public uint StatusWord { get; protected set; }
        public int Requests { get; protected set; }
        public int Responses { get; protected set; }
    }
}

namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    public sealed class BlackwallUartPower : BlackwallPeripheralPower
    {
        public BlackwallUartPower(int profile,int offProfile=-1,int module=1):base(ModuleMask(module),profile,offProfile) { Module=module; }
        public bool TryWriteShared(uint value,bool ready,bool quiescent,bool domainHeld)
        {
            if(domainHeld && value==0 && Phase=="on" && OffProfile==0 && quiescent)
            {
                Generation++; RequestWord=StatusWord=0; Phase="gated"; OffRequests++; return true;
            }
            if(domainHeld && value==Mask && Phase=="gated" && ready)
            {
                Generation++; RequestWord=StatusWord=Mask; Phase="on"; Requests++; Responses++; return true;
            }
            return TryWrite(value,ready,quiescent);
        }
        public bool CompleteSharedPowerOff()
        {
            if(Phase!="gated" || OffProfile!=0)return false;
            Phase="off-requested"; ReadStatus(); return true;
        }
        private static uint ModuleMask(int module) { if(module<0 || module>3) throw new System.ArgumentException("UART module must be0..3"); return 0x200u<<module; }
        public int Module { get; }
    }
}

namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    public interface IBlackwallUartDmaTx : IPeripheral
    {
        void Bind(BlackwallUartAdapter adapter);
        bool Owns(long offset);
        bool TryRead(long offset,out uint value);
        bool TryWrite(long offset,uint value);
        void ClearInterrupts(uint mask);
        void PowerDown();
        uint RawInterrupts { get; }
        uint Control { get; }
        bool Busy { get; }
    }

    public sealed class BlackwallUartAdapter : IPeripheral
    {
        public BlackwallUartAdapter(IMachine machine,bool interrupts=false,int module=1,bool idleDmaInterrupts=false,IBlackwallUartDmaTx dmaTx=null,bool txInterruptQuirks=true,bool receiveFifo=false,bool receiveTimeout=false)
        {
            if(module<0 || module>3) throw new System.ArgumentException("UART module must be0..3");
            if(idleDmaInterrupts && (module!=0 || !interrupts)) throw new System.ArgumentException("idle DMA masks require interrupt-enabled UART0");
            IdleDmaInterrupts=idleDmaInterrupts;
            if(dmaTx!=null && (module!=0 || !interrupts || !idleDmaInterrupts)) throw new System.ArgumentException("DMA TX requires interrupt-enabled UART0 with DMA masks");
            if(receiveFifo && ((module!=0 && module!=2) || !interrupts))throw new System.ArgumentException("RX FIFO requires interrupt-enabled UART0 or UART2");
            ReceiveFifo=receiveFifo;
            if(receiveTimeout && (!receiveFifo || module!=0 || !interrupts))throw new System.ArgumentException("RX timeout requires interrupt-enabled UART0 FIFO");
            ReceiveTimeout=receiveTimeout;
            if(receiveTimeout)
            {
                rxTimeoutTimer=new LimitTimer(machine.ClockSource,24000000,this,"uart-rx-timeout",1,Direction.Ascending,enabled:false,workMode:WorkMode.OneShot,eventEnabled:true);
                rxTimeoutTimer.LimitReached+=()=>{
                    if(RxPending==0 || (Control&0x209)!=0x209)return;
                    RxTimeoutPending=true;RxTimeoutEvents++;UpdateIrq();
                };
            }
            DmaTx=dmaTx;
            TxInterruptQuirks=txInterruptQuirks;
            Module=module; InterruptsEnabled=interrupts; IRQ=new GPIO();
            engine=new Antmicro.Renode.Peripherals.UART.PL011(machine,32,24000000,false);
            engine.CharReceived += b => { TxBytes.Add(b); if(InterruptsEnabled) { TxComplete=true; TxCompletions++; } };
            DmaTx?.Bind(this);
            Reset();
        }
        public void Reset()
        {
            CancelRxTimeout();RxTimeoutEvents=0;
            engine.Reset(); RxPending=0;RxBytesInjected=RxBytesRead=RxDiscardedBytes=0;RxReadHash=14695981039346656037ul; TxBytes.Clear(); Reads=Writes=PowerBlocks=ClockSpareClears=PowerDowns=0; ClockSpareEpoch=false;
            if(!TxInterruptQuirks)engine.WriteDoubleWord(0x44,0x7fe);
            TxEnableQuirkSuppressions=0;
            IrqHandlerEntries=IrqExceptionEntries=0; LastActiveVector=0;
            InterruptMask=0; TxComplete=false; TxCompletions=InterruptClears=InterruptMaskWrites=IRQAssertions=IRQTransitions=0; IRQ.Unset();
            DmaTx?.Reset();
        }
        private void UpdateIrq()
        {
            var level=InterruptsEnabled && MaskedInterrupts!=0;
            if(level!=IRQ.IsSet) { IRQTransitions++; if(level) IRQAssertions++; }
            IRQ.Set(level);
        }
        public void AttachIrqProbe(CortexM cpu,uint address,IMachine machine)
        {
            if(!InterruptsEnabled || IrqHandlerAddress!=0) throw new System.ArgumentException("IRQ probe requires enabled model and one attachment");
            IrqHandlerAddress=address;
            cpu.AddHook(address,(c,a) => {
                IrqHandlerEntries++;
                LastActiveVector=machine.SystemBus.ReadDoubleWord(0xe000ed04)&0x1ffu;
                if(LastActiveVector==31+Module) IrqExceptionEntries++;
            });
        }
        public bool Quiescent => (!ReceiveFifo || RxPending==0) && Control==0 && RawInterrupts==0 && !IRQ.IsSet && (DmaTx==null ? engine.ReadDoubleWord(0x48)==0 : DmaTx.Control==0 && !DmaTx.Busy);
        public void PowerDown()
        {
            CancelRxTimeout();
            RxDiscardedBytes+=(ulong)RxPending;RxPending=0;engine.Reset(); InterruptMask=0; TxComplete=false; IRQ.Unset(); ClockSpareEpoch=false; PowerDowns++;
            if(!TxInterruptQuirks)engine.WriteDoubleWord(0x44,0x7fe);
            DmaTx?.PowerDown();
        }
        public int PowerDowns { get; private set; }
        private bool ClockSpareEpoch;
        public bool CanClockSpare(BlackwallMemoryRegister register,uint value,bool ready) => ready && Control==8 && !ClockSpareEpoch && value==(register.Value&~(0x400000u<<Module));
        public bool TryClockSpare(BlackwallMemoryRegister register,uint value,bool ready)
        {
            if(!CanClockSpare(register,value,ready)) return false;
            register.Value=value; register.Writes++; ClockSpareClears++; ClockSpareEpoch=true; return true;
        }
        public bool Owns(ulong address) { return address>=BaseAddress && address<BaseAddress+0x1000; }
        public bool TryRead(ulong address,bool powered,out uint value)
        {
            value=0; if(!powered) { PowerBlocks++; return false; }
            var offset=(long)(address-BaseAddress);
            if(DmaTx!=null && DmaTx.Owns(offset))
            {
                if(!DmaTx.TryRead(offset,out value))return false;
                Reads++;return true;
            }
            if(offset==0 && ReceiveFifo)
            {
                if(RxPending==0)return false;
                value=engine.ReadDoubleWord(0);RxPending--;RxBytesRead++;
                if(RxPending==0)CancelRxTimeout();
                RxReadHash=unchecked((RxReadHash^(byte)value)*1099511628211ul);
                Reads++;UpdateIrq();return true;
            }
            switch(offset)
            {
            case 4: value=0; break;
            case 0x18: case 0x20: case 0x24: case 0x28: case 0x2c: case 0x30: case 0x34: case 0x48:
                value=engine.ReadDoubleWord(offset); break;
            case 0x38: value=InterruptMask; break;
            case 0x3c: value=RawInterrupts; break;
            case 0x40: value=MaskedInterrupts; break;
            default: return false;
            }
            Reads++; return true;
        }
        public bool TryWrite(ulong address,uint value,bool powered)
        {
            if(!powered) { PowerBlocks++; return false; }
            var offset=(long)(address-BaseAddress);
            if(DmaTx!=null && DmaTx.Owns(offset))
            {
                if(!DmaTx.TryWrite(offset,value))return false;
                Writes++;UpdateIrq();return true;
            }
            if(ReceiveTimeout && RxPending!=0 && (offset==0x24 || offset==0x28) && value!=engine.ReadDoubleWord(offset))return false;
            if(ReceiveTimeout && RxPending!=0 && offset==0x30 && ((value^Control)&0x70)!=0)return false;
            switch(offset)
            {
            case 0:
                var cr=engine.ReadDoubleWord(0x30); var lc=engine.ReadDoubleWord(0x2c);
                if(value>255 || (cr&0x109)!=0x109 || ((cr>>4)&7)!=1 || ((lc>>5)&3)!=3 || TxBytes.Count>=4096) return false;
                break;
            case 4: if((value&~0x3fu)!=0) return false; break;
            case 0x20: if(value!=0) return false; break;
            case 0x24: if(value>0xffff) return false; break;
            case 0x28: if(value>63) return false; break;
            case 0x2c: if(ReceiveFifo && RxPending!=0 && ((value^engine.ReadDoubleWord(0x2c))&16)!=0)return false; if(value>255 || (value&1)!=0) return false; break;
            case 0x30: if(value>0xffff || (value&0xc086)!=0 || ((value>>4)&7)>6) return false; break;
            case 0x34: if(value>63 || (value&7)>4 || ((value>>3)&7)>4) return false; break;
            case 0x38:
                if((value&~(IdleDmaInterrupts ? 0x1fffu : 0x7ffu))!=0 || (!InterruptsEnabled && value!=0)) return false;
                if((value&0x1800u)!=0 && engine.ReadDoubleWord(0x48)!=0) return false;
                InterruptMask=value; if(InterruptsEnabled) InterruptMaskWrites++;
                engine.WriteDoubleWord(offset,value&0x7feu); Writes++; UpdateIrq(); return true;
            case 0x48: if(value!=0) return false; break;
            case 0x44:
                if(InterruptsEnabled && value==0xffffffffu) value=0x1fff;
                if((value&~0x1fffu)!=0) return false;
                if(InterruptsEnabled) { if((value&1)!=0) TxComplete=false; InterruptClears++; }
                DmaTx?.ClearInterrupts(value);
                if((value&0x40)!=0) { RxTimeoutPending=false;ArmRxTimeout(); }
                value&=0x7feu; break;
            default: return false;
            }
            var clearEnableTx=!TxInterruptQuirks && offset==0x30 && (value&1)!=0 && (Control&1)==0 && (engine.ReadDoubleWord(0x3c)&0x20)==0;
            engine.WriteDoubleWord(offset,value);
            if(ReceiveTimeout && offset==0x30)
            {
                if((Control&0x209)!=0x209)CancelRxTimeout();
                else if(RxPending!=0)ArmRxTimeout();
            }
            if(clearEnableTx && (engine.ReadDoubleWord(0x3c)&0x20)!=0) { engine.WriteDoubleWord(0x44,0x20);TxEnableQuirkSuppressions++; }
            Writes++; UpdateIrq(); return true;
        }
        public bool TryReceive(byte[] data,bool powered)
        {
            if(!ReceiveFifo || !powered || data==null || data.Length==0)return false;
            var control=Control;var line=engine.ReadDoubleWord(0x2c);
            var capacity=(line&16)!=0 ? 32:1;
            if((control&0x209)!=0x209 || ((control>>4)&7)!=1 || ((line>>5)&3)!=3 || data.Length>capacity-RxPending)return false;
            if(ReceiveTimeout && 64u*engine.ReadDoubleWord(0x24)+engine.ReadDoubleWord(0x28)==0)return false;
            foreach(var value in data) { engine.WriteChar(value);RxPending++;RxBytesInjected++; }
            ArmRxTimeout();
            UpdateIrq();return true;
        }
        private void CancelRxTimeout()
        {
            if(rxTimeoutTimer!=null) { rxTimeoutTimer.Enabled=false;rxTimeoutTimer.Value=0; }
            RxTimeoutPending=false;RxTimeoutCycles=0;
        }
        private void ArmRxTimeout()
        {
            if(rxTimeoutTimer==null)return;
            rxTimeoutTimer.Enabled=false;rxTimeoutTimer.Value=0;
            if(RxPending==0 || (Control&0x209)!=0x209 || ((Control>>4)&7)!=1)return;
            var divisor=64ul*engine.ReadDoubleWord(0x24)+engine.ReadDoubleWord(0x28);
            if(divisor==0)return;
            RxTimeoutCycles=8ul*divisor;rxTimeoutTimer.Limit=RxTimeoutCycles;rxTimeoutTimer.Enabled=true;
        }
        public bool ReceiveTimeout {get;}
        public bool RxTimeoutPending {get;private set;}
        public ulong RxTimeoutCycles {get;private set;}
        public ulong RxTimeoutEvents {get;private set;}
        private readonly LimitTimer rxTimeoutTimer;
        public bool ReceiveFifo {get;}
        public int RxPending {get;private set;}
        public ulong RxBytesInjected {get;private set;}
        public ulong RxBytesRead {get;private set;}
        public ulong RxReadHash {get;private set;}
        public ulong RxDiscardedBytes {get;private set;}
        public uint ReceiveLevelSelection => (engine.ReadDoubleWord(0x34)>>3)&7;
        public int Module { get; }
        public ulong BaseAddress => 0x40039000u+(uint)Module*0x1000u;
        public int IrqNumber => 15+Module;
        public GPIO IRQ { get; }
        public bool InterruptsEnabled { get; }
        public bool IdleDmaInterrupts { get; }
        public IBlackwallUartDmaTx DmaTx { get; }
        public bool TxInterruptQuirks { get; }
        public int TxEnableQuirkSuppressions { get; private set; }
        public uint InterruptMask { get; private set; }
        public uint RawInterrupts => (engine.ReadDoubleWord(0x3c)&0x7feu) | (RxTimeoutPending ? 0x40u : 0u) | (TxComplete ? 1u : 0) | (DmaTx==null ? 0u : DmaTx.RawInterrupts);
        public uint MaskedInterrupts => RawInterrupts & InterruptMask;
        public bool TxComplete { get; private set; }
        public int TxCompletions { get; private set; }
        public int InterruptClears { get; private set; }
        public int InterruptMaskWrites { get; private set; }
        public int IRQAssertions { get; private set; }
        public int IRQTransitions { get; private set; }
        public uint IrqHandlerAddress { get; private set; }
        public int IrqHandlerEntries { get; private set; }
        public int IrqExceptionEntries { get; private set; }
        public uint LastActiveVector { get; private set; }
        public uint Control { get { return engine.ReadDoubleWord(0x30); } }
        public uint VirtualBaud
        {
            get
            {
                if(((Control>>4)&7)!=1) return 0;
                var divisor=64u*engine.ReadDoubleWord(0x24)+engine.ReadDoubleWord(0x28);
                return divisor==0 ? 0 : 96000000u/divisor;
            }
        }
        public System.Collections.Generic.List<byte> TxBytes { get; } = new System.Collections.Generic.List<byte>();
        public int Reads { get; private set; }
        public int Writes { get; private set; }
        public int PowerBlocks { get; private set; }
        public int ClockSpareClears { get; private set; }
        internal bool CanDmaTransmit(uint count)
        {
            return count>0 && count<=4095 && TxBytes.Count+count<=4096 && (Control&0x109)==0x109
                && ((Control>>4)&7)==1 && ((engine.ReadDoubleWord(0x2c)>>5)&3)==3;
        }
        internal bool TransmitDma(byte[] data)
        {
            if(!CanDmaTransmit((uint)data.Length))return false;
            foreach(var value in data)engine.WriteDoubleWord(0,value);
            return true;
        }
        private readonly Antmicro.Renode.Peripherals.UART.PL011 engine;
    }

    public sealed class BlackwallAdcPower
    {
        public BlackwallAdcPower(int profile,int offProfile=-1) { if(profile<0 || profile>1 || offProfile < -1 || offProfile>1) throw new System.ArgumentException("ADC power profile invalid"); Profile=profile; OffProfile=offProfile; Reset(); }
        public void Reset() { Phase="off"; RequestWord=StatusWord=0; Requests=Cancellations=Transitions=Responses=OffRequests=0; EpochRetired=false; }
        public bool TryWrite(uint value,bool ready,bool quiescent=false)
        {
            var restart=Phase=="powered-off" && OffProfile==1 && StatusWord==0 && RequestWord==0 && quiescent;
            if(value==Mask && ready && (Phase=="off" || restart))
            { Phase="requested";RequestWord=Mask;EpochRetired=false;Requests++;Transitions++;return true; }
            if(value==0 && Phase=="on" && OffProfile!=-1 && quiescent)
            { RequestWord=0; Phase="off-requested"; EpochRetired=true; OffRequests++; Transitions++; return true; }
            if(value==0 && RequestWord!=0 && Phase!="on")
            { Phase="cancelled";RequestWord=StatusWord=0;Cancellations++;Transitions++;return true; }
            return false;
        }
        public bool TryReadStatus(bool automaticCalibrationDisabled,out uint value)
        {
            value=StatusWord;
            if(Phase=="requested")
            {
                if(!automaticCalibrationDisabled) return false;
                Phase=Profile==1 ? "on" : "stuck-off"; StatusWord=Profile==1 ? Mask : 0;
                Responses++;Transitions++;value=StatusWord;
            }
            if(Phase=="off-requested")
            { Phase=OffProfile==1 ? "powered-off" : "stuck-on"; StatusWord=OffProfile==1 ? 0u : Mask; Responses++; Transitions++; value=StatusWord; }
            return true;
        }
        public bool EpochRetired { get; private set; }
        public int OffProfile { get; }
        public int OffRequests { get; private set; }
        public int Profile { get; }
        public string Phase { get; private set; }
        public uint RequestWord { get; private set; }
        public uint StatusWord { get; private set; }
        public int Requests { get; private set; }
        public int Cancellations { get; private set; }
        public int Transitions { get; private set; }
        public int Responses { get; private set; }
        private const uint Mask=0x2000;
    }

    public sealed class BlackwallAdcInfoZeroFixture
    {
        public void Reset() { System.Array.Clear(Reads,0,5); }
        public bool TryRead(ulong address,out uint value)
        {
            value=0;var index=System.Array.IndexOf(Addresses,address);
            if(index<0) return false; Reads[index]++; return true;
        }
        public uint[] Reads { get; } = new uint[5];
        private static readonly ulong[] Addresses={0x42003300,0x42003304,0x42003308,0x42003328,0x4200332c};
    }

    // Narrow original-consumer adapter: zero padding is not a claim about other GPIOs.
    public sealed class BlackwallGpioRoleInput : IPeripheral
    {
        public BlackwallGpioRoleInput(IMachine machine,int level,uint readPc,int readBudget=5,int touchLevel=-1,int touchReadBudget=1)
        {
            if(machine==null || level<0 || level>1 || (readPc&1)!=0 || readPc<0x438000 || readPc>=0x800000 || readBudget<1 || readBudget>64)
                throw new System.ArgumentException("GPIO role input requires explicit level, original read PC and finite budget");
            this.machine=machine;Level=level;ReadPc=readPc;ReadBudget=readBudget;
            if(touchLevel< -1 || touchLevel>1 || touchReadBudget<1 || touchReadBudget>64)
                throw new System.ArgumentException("GPIO touch input requires explicit level and finite budget");
            TouchLevel=touchLevel;TouchReadBudget=touchReadBudget;
        }
        public bool Owns(ulong address) => address==0x40010414 || (TouchLevel>=0 && address==0x40010404);
        public bool TryRead(ulong address,bool configured,out uint value)
        { return TryRead(address,configured,out value,null); }
        public bool TryRead(ulong address,bool configured,out uint value,BlackwallGpioInterruptIdle runtimeTouchSource)
        {
            value=0;
            if(!Owns(address) || !machine.SystemBus.TryGetCurrentCPU(out var current))return false;
            var cpu=current as CortexM;if(cpu==null)return false;
            if(address==0x40010404)
            {
                LastTouchContextPc=(uint)cpu.PC.RawValue;LastTouchContextPin=(uint)cpu.GetRegister(0).RawValue;
                if(runtimeTouchSource!=null && runtimeTouchSource.RuntimePin27)
                    return TryRuntimeTouchSample(LastTouchContextPin,LastTouchContextPc,configured,runtimeTouchSource,out value);
                return TryTouchSample(LastTouchContextPin,LastTouchContextPc,configured,out value);
            }
            LastContextPc=(uint)cpu.PC.RawValue;LastContextPin=(uint)cpu.GetRegister(0).RawValue;
            return TrySample(LastContextPin,LastContextPc,configured,out value);
        }
        public bool TrySample(uint pin,uint pc,bool configured,out uint value)
        {
            value=0;if(!configured || pin!=156 || pc!=ReadPc || Reads>=ReadBudget)return false;
            value=(uint)Level<<28;Reads++;return true;
        }
        public bool TryTouchSample(uint pin,uint pc,bool configured,out uint value)
        {
            value=0;if(TouchLevel<0 || !configured || pin!=27 || pc!=ReadPc || TouchReads>=TouchReadBudget)return false;
            value=(uint)TouchLevel<<27;TouchReads++;return true;
        }
        public bool TryRuntimeTouchSample(uint pin,uint pc,bool configured,BlackwallGpioInterruptIdle source,out uint value)
        {
            value=0;
            if(source==null || !source.RuntimePin27 || TouchLevel<0 || !configured || pin!=27 || pc!=ReadPc || TouchReads>=TouchReadBudget)return false;
            value=source.Pin27High ? 1u<<27 : 0u;TouchReads++;return true;
        }
        public void Reset() { Reads=TouchReads=0;LastContextPc=LastContextPin=LastTouchContextPc=LastTouchContextPin=0; }
        public int Level { get; }
        public uint ReadPc { get; }
        public int ReadBudget { get; }
        public int Reads { get; private set; }
        public uint LastContextPc { get; private set; }
        public uint LastContextPin { get; private set; }
        public int TouchLevel { get; }
        public int TouchReadBudget { get; }
        public int TouchReads { get; private set; }
        public uint LastTouchContextPc { get; private set; }
        public uint LastTouchContextPin { get; private set; }
        private readonly IMachine machine;
    }

    public sealed class BlackwallGpioOutputLatch
    {
        public BlackwallGpioOutputLatch(BlackwallGpioConfig config,bool idempotentUnconfiguredWrites=false) { this.config=config;IdempotentUnconfiguredWrites=idempotentUnconfiguredWrites;Reset(); }
        public void Reset() { System.Array.Clear(Words,0,7); Reads=DirectWrites=SetWrites=ClearWrites=UnconfiguredNoOpWrites=LastNoOpGroup=0;LastNoOpMask=0; }
        public bool Owns(ulong address) { return address>=0x40010420 && address<=0x40010470; }
        private bool Supports(uint mask,int group,uint next,out uint noOpMask)
        {
            noOpMask=0;
            for(var bit=0;bit<32;bit++)
            {
                if((mask&(1u<<bit))==0) continue;
                var pin=group*32+bit; uint cfg;
                if(System.Array.IndexOf(ReservedPins,pin)>=0)return false;
                var configured=config.Values.TryGetValue(0x40010000u+(ulong)pin*4,out cfg) && (cfg&0x30f)==0x103 && (cfg&0x0c000000)==0;
                if(!configured)
                {
                    if(!IdempotentUnconfiguredWrites || ((Words[group]^next)&(1u<<bit))!=0)return false;
                    noOpMask|=1u<<bit;
                }
            }
            return true;
        }
        public bool TryRead(ulong address,out uint value)
        {
            value=0;
            if(!Owns(address) || (address&3)!=0 || address>=0x4001043c) return false;
            Reads++; value=Words[(int)(address-0x40010420)/4]; return true;
        }
        public bool TryWrite(ulong address,uint value)
        {
            if(!Owns(address) || (address&3)!=0) return false;
            var relative=(int)(address-0x40010420);var kind=relative/28;var group=(relative%28)/4;
            var next=kind==0 ? value : kind==1 ? Words[group]|value : Words[group]&~value;
            if(!Supports(kind==0 ? 0xffffffffu : value,group,next,out var noOpMask)) return false;
            Words[group]=next;
            if(kind==0)DirectWrites++;else if(kind==1)SetWrites++;else ClearWrites++;
            if(noOpMask!=0) {UnconfiguredNoOpWrites++;LastNoOpMask=noOpMask;LastNoOpGroup=group;}
            var notified=(kind==0 ? 0xffffffffu : value)&~noOpMask;
            if(OutputWritten!=null)
                for(var bit=0;bit<32;bit++)
                    if((notified&(1u<<bit))!=0)OutputWritten(group*32+bit,(next&(1u<<bit))!=0);

            return true;
        }
        public uint[] Words { get; } = new uint[7];
        public int Reads { get; private set; }
        public int DirectWrites { get; private set; }
        public int SetWrites { get; private set; }
        public int ClearWrites { get; private set; }
        public event System.Action<int,bool> OutputWritten;
        public bool IdempotentUnconfiguredWrites { get; }
        public int UnconfiguredNoOpWrites { get; private set; }
        public uint LastNoOpMask { get; private set; }
        public int LastNoOpGroup { get; private set; }
        private readonly BlackwallGpioConfig config;
        private static readonly int[] ReservedPins={135,137,163,164,166,167,168,169,170,171,172,174,176,177,178,179,180,181,182,183,184,185,190,193,194,196,197,198,202,203,204,205,206,207};
    }

    public sealed class BlackwallGpioInterruptIdle : IPeripheral
    {
        public BlackwallGpioInterruptIdle(bool runtimePin117=false,bool runtimePin27=false,bool runtimePin38=false) { RuntimePin117=runtimePin117;RuntimePin27=runtimePin27;RuntimePin38=runtimePin38; Reset(); }
        public bool TrySetPin38(bool high,bool configured)
        {
            if(!RuntimePin38 || !configured)return false;
            if(high && !Pin38High) { Pending38=true;Pin38RisingEdges++; }
            Pin38High=high;UpdateIrq();return true;
        }
        public bool TrySetPin27(bool high,bool configured)
        {
            if(!RuntimePin27 || !configured)return false;
            if(!high && Pin27High) { Pending27=true;FallingEdges++; }
            Pin27High=high;UpdateIrq();return true;
        }
        public bool TrySetPin117(bool high,bool configured)
        {
            if(!RuntimePin117 || !configured)return false;
            if(high && !pin117High) { Pending117=true; RisingEdges++; }
            pin117High=high; UpdateIrq(); return true;
        }
        private void UpdateIrq()
        {
            IRQ.Set(RuntimePin117 && Pending117 && (EnableWords[3]&(1u<<21))!=0);
            IRQ27.Set(RuntimePin27 && Pending27 && (EnableWords[0]&(1u<<27))!=0);
            IRQ38.Set(RuntimePin38 && Pending38 && (EnableWords[1]&(1u<<6))!=0);
        }
        [DefaultInterrupt]
        public GPIO IRQ { get; } = new GPIO();
        public GPIO IRQ27 { get; } = new GPIO();
        public GPIO IRQ38 { get; } = new GPIO();
        public bool RuntimePin38 {get;}
        public bool Pin38High {get;private set;}
        public bool Pending38 {get;private set;}
        public int Pin38RisingEdges {get;private set;}
        public bool RuntimePin27 {get;}
        public bool Pin27High {get;private set;}
        public bool Pending27 {get;private set;}
        public int FallingEdges {get;private set;}
        public bool RuntimePin117 { get; }
        public bool Pending117 {get; private set;}
        public int RisingEdges {get; private set;}
        private bool pin117High;
        public void Reset()
        {
            System.Array.Clear(EnableWords,0,14); System.Array.Clear(ClearRequests,0,14);
            EnableReads=EnableWrites=StatusReads=ClearWrites=0;
            Pending117=pin117High=false; RisingEdges=0; IRQ.Unset();
            Pending27=false;Pin27High=true;FallingEdges=0;IRQ27.Unset();
            Pending38=Pin38High=false;Pin38RisingEdges=0;IRQ38.Unset();
        }
        public bool Owns(ulong address) { return address>=0x40010530 && address<=0x4001060c; }
        public bool TryRead(ulong address,out uint value)
        {
            value=0; if(!Owns(address) || (address&3)!=0) return false;
            var relative=(int)(address-0x40010530);var index=relative/16;
            if(relative%16==0) { EnableReads++; value=EnableWords[index]; return true; }
            if(relative%16==4) { StatusReads++; if(RuntimePin117 && index==3 && Pending117)value=1u<<21;if(RuntimePin27 && index==0 && Pending27)value=1u<<27;if(RuntimePin38 && index==1 && Pending38)value=1u<<6; return true; }
            return false;
        }
        public bool TryWrite(ulong address,uint value)
        {
            if(!Owns(address) || (address&3)!=0) return false;
            var relative=(int)(address-0x40010530);var index=relative/16;
            if(relative%16==0) { EnableWrites++; EnableWords[index]=value; UpdateIrq(); return true; }
            if(relative%16==8) { ClearWrites++; ClearRequests[index]|=value; if(RuntimePin117 && index==3 && (value&(1u<<21))!=0)Pending117=false;if(RuntimePin27 && index==0 && (value&(1u<<27))!=0)Pending27=false;if(RuntimePin38 && index==1 && (value&(1u<<6))!=0)Pending38=false; UpdateIrq(); return true; }
            return false;
        }
        public uint[] EnableWords { get; } = new uint[14];
        public uint[] ClearRequests { get; } = new uint[14];
        public int EnableReads { get; private set; }
        public int EnableWrites { get; private set; }
        public int StatusReads { get; private set; }
        public int ClearWrites { get; private set; }
    }

    public sealed class BlackwallGpioConfig
    {
        public BlackwallGpioConfig() { Reset(); }
        public void Reset() { Unlocked=false; KeyWrites=ConfigWrites=ConfigReads=0; Values.Clear(); }
        public bool Owns(ulong address) { return address>=0x40010000 && address<=0x40010400; }
        private bool IsPin(ulong address) { return address>=0x40010000 && address<=0x4001037c && (address&3)==0; }
        public bool TryWrite(ulong address,uint value)
        {
            if(address==0x40010400 && (value==0x73 || value==0))
            { Unlocked=value==0x73; KeyWrites++; return true; }
            if(!IsPin(address) || !Unlocked || (value&~0x0c7fffffu)!=0) return false;
            Values[address]=value; ConfigWrites++; return true;
        }
        public bool TryRead(ulong address,out uint value)
        {
            value=0;
            if(!IsPin(address) || !Values.TryGetValue(address,out value)) return false;
            ConfigReads++; return true;
        }
        public bool Unlocked { get; private set; }
        public int KeyWrites { get; private set; }
        public int ConfigWrites { get; private set; }
        public int ConfigReads { get; private set; }
        public System.Collections.Generic.SortedDictionary<ulong,uint> Values { get; } = new System.Collections.Generic.SortedDictionary<ulong,uint>();
    }

    public sealed class BlackwallGpuOffSequence
    {
        public BlackwallGpuOffSequence(BlackwallHalStorage hal) { this.hal=hal; Reset(); }
        public void Reset() { StepsCompleted=0; OriginalCoreWord=BoostDelta=0; }
        public void Rearm()
        {
            if(!Complete)throw new System.InvalidOperationException("Incomplete GPU sequence cannot be rearmed");
            StepsCompleted=0;OriginalCoreWord=BoostDelta=0;
        }
        public bool Owns(ulong address) { return System.Array.IndexOf(Addresses,address)>=0; }
        public bool TryWrite(ulong address,uint value,bool ready)
        {
            if(!ready || StepsCompleted>=Addresses.Length || address!=Addresses[StepsCompleted]) return false;
            var r=hal.Registers[address]; var field=Values[StepsCompleted];
            if(StepsCompleted==0) field=System.Math.Min((r.Value&1023)+12,1023u);
            if(StepsCompleted==12) field=OriginalCoreWord&1023;
            var expected=(r.Value&~Masks[StepsCompleted])|field;
            if(value!=expected) return false;
            if(StepsCompleted==0) { OriginalCoreWord=r.Value; BoostDelta=field-(r.Value&1023); }
            r.Value=value; r.Writes++; StepsCompleted++; return true;
        }
        public int StepsCompleted { get; private set; }
        public bool Complete => StepsCompleted==Addresses.Length;
        public uint OriginalCoreWord { get; private set; }
        public uint BoostDelta { get; private set; }
        private static readonly ulong[] Addresses={0x40020080,0x40020088,
            0x40020380,0x40020380,0x40020380,0x40020380,
            0x40020344,0x40020344,0x4002034c,0x4002034c,0x40020358,0x40020354,
            0x40020080,0x40020088,0x40020380,0x40020380,0x40020380,0x40020380};
        private static readonly uint[] Masks={1023,63,0x20000000,0x10000000,0x80000000,0x40000000,
            0x3e000000,0xf800,0x3e000000,0xf800,0x1f00,0x3e0000,
            1023,63,0x20000000,0x10000000,0x80000000,0x40000000};
        private static readonly uint[] Values={0,5,0x20000000,0x10000000,0x80000000,0x40000000,
            6u<<25,6u<<11,5u<<25,5u<<11,7u<<8,10u<<17,0,1,0,0,0,0};
        private readonly BlackwallHalStorage hal;
    }

    public sealed class BlackwallGpuPreparation
    {
        public BlackwallGpuPreparation(BlackwallHalStorage hal) { this.hal=hal; Reset(); }
        public void Reset() { StepsCompleted=0; OriginalCoreWord=BoostDelta=0; }
        public void Rearm()
        {
            if(!Complete)throw new System.InvalidOperationException("Incomplete GPU sequence cannot be rearmed");
            StepsCompleted=0;OriginalCoreWord=BoostDelta=0;
        }
        public bool CanRearm(ulong address,uint value,bool ready)
        {
            if(!ready || !Complete || address!=Addresses[0])return false;
            var current=hal.Registers[address].Value;
            return value==((current&~1023u)|System.Math.Min((current&1023u)+12u,1023u));
        }
        public bool Owns(ulong address) { return System.Array.IndexOf(Addresses,address)>=0; }
        public bool TryWrite(ulong address,uint value,bool ready)
        {
            if(!ready || StepsCompleted>=Addresses.Length || address!=Addresses[StepsCompleted]) return false;
            var r=hal.Registers[address];
            var field=Values[StepsCompleted];
            if(StepsCompleted==0) field=System.Math.Min((r.Value&1023)+12,1023u);
            if(StepsCompleted==16) field=OriginalCoreWord&1023;
            var expected=(r.Value&~Masks[StepsCompleted])|field;
            if(value!=expected) return false;
            if(StepsCompleted==0) { OriginalCoreWord=r.Value; BoostDelta=field-(r.Value&1023); }
            r.Value=value; r.Writes++; StepsCompleted++; return true;
        }
        public int StepsCompleted { get; private set; }
        public bool Complete => StepsCompleted==Addresses.Length;
        public uint OriginalCoreWord { get; private set; }
        public uint BoostDelta { get; private set; }
        private static readonly ulong[] Addresses={0x40020080,0x40020088,
            0x40020380,0x40020380,0x40020380,0x40020380,
            0x40020344,0x40020344,0x4002034c,0x4002034c,0x40020358,0x40020354,
            0x40020380,0x40020380,0x40020380,0x40020380,0x40020080,0x40020088};
        private static readonly uint[] Masks={1023,63,0x20000000,0x10000000,0x80000000,0x40000000,
            0x3e000000,0xf800,0x3e000000,0xf800,0x1f00,0x3e0000,
            0x20000000,0x10000000,0x80000000,0x40000000,1023,63};
        private static readonly uint[] Values={0,5,0x20000000,0x10000000,0x80000000,0x40000000,
            6u<<25,6u<<11,5u<<25,5u<<11,13u<<8,19u<<17,0,0,0,0,0,1};
        private readonly BlackwallHalStorage hal;
    }

    public sealed class BlackwallGfxPowerStorage
    {
        public BlackwallGfxPowerStorage() { Reset(); }
        public void Reset()
        { Selection=Request=0; SelectionReads=RequestReads=SelectionWrites=RequestWrites=0; }
        public bool TryRead(ulong address,out uint value)
        {
            value=0;
            if(address==0x40021090) { SelectionReads++; value=Selection; return true; }
            if(address==0x4002108c) { RequestReads++; value=Request; return true; }
            return false;
        }
        public bool TryWrite(ulong address,uint value,bool buckActive)
        {
            if(address==0x40021090 && (value==0 || (value==1 && buckActive)))
            { Selection=value; SelectionWrites++; return true; }
            if(address==0x4002108c && ((value==0 && Selection==0) || (value==3 && Selection==1 && buckActive)))
            { Request=value; RequestWrites++; return true; }
            return false;
        }
        public uint Selection { get; private set; }
        public uint Request { get; private set; }
        public int SelectionReads { get; private set; }
        public int RequestReads { get; private set; }
        public int SelectionWrites { get; private set; }
        public int RequestWrites { get; private set; }
    }

    public sealed class BlackwallMcuClock
    {
        public BlackwallMcuClock(BlackwallHalStorage hal,string mode,int profile,bool hfrcForceControl=false)
        { this.hal=hal; initialMode=mode=="lp" ? 13u : 22u; Profile=profile; HfrcForceControl=hfrcForceControl; Reset(); }
        public void Reset()
        { ModeWord=initialMode; Phase="initial"; GateWrites=ForceWrites=ClockReads=ModeReads=ModeWrites=Transitions=0; }
        public bool Enabled => (MiscWord & 32)!=0 || ((ModeWord>>3)&3)==2;
        public bool Ready => Enabled && Profile!=1;
        public bool HfrcForceControl { get; }
        public bool HfrcForced => HfrcForceControl && (MiscWord & 1)!=0;
        public uint MiscWord => hal.Registers[0x40004044].Value;
        public uint ReadClock()
        { ClockReads++; return (Enabled ? 0x80000000u : 0)|(Ready ? 0x1000000u : 0)|(HfrcForced ? 0x40000000u : 0); }
        public uint ReadMode() { ModeReads++; return ModeWord; }
        public bool TryWrite(ulong address,uint value,bool buckActive)
        {
            if(address==0x40004044)
            {
                var r=hal.Registers[address];
                var forceMask=HfrcForceControl ? 33u : 32u;
                if(((r.Value^value)&~forceMask)!=0)
                {
                    if((r.Value&forceMask)!=(value&forceMask) || (r.Value&~forceMask)!=0 || (value&~forceMask)!=0xfbbfc0u) return false;
                    r.Value=value; r.Writes++; GateWrites++; return true;
                }
                r.Value=value; r.Writes++; ForceWrites++;
                if(Phase=="initial") Phase="clock-requested";
                return true;
            }
            var requested=value&3u;
            if(address!=0x40021000 || (requested!=1 && requested!=2) || (value&~3u)!=(ModeWord&~3u)
                || (requested==2 && (!buckActive || !Ready))) return false;
            var old=(ModeWord>>3)&3;
            var status=(Profile==2 || Profile==3) ? old : requested;
            var ack=Profile!=2;
            ModeWord=requested|(ack ? 4u : 0)|(status<<3); ModeWrites++;
            if(status!=old) Transitions++;
            Phase=!ack ? "pending" : status==requested ? "acked" : "denied";
            return true;
        }
        public int Profile { get; }
        public string Phase { get; private set; }
        public uint ModeWord { get; private set; }
        public int GateWrites { get; private set; }
        public int ForceWrites { get; private set; }
        public int ClockReads { get; private set; }
        public int ModeReads { get; private set; }
        public int ModeWrites { get; private set; }
        public int Transitions { get; private set; }
        private readonly BlackwallHalStorage hal;
        private readonly uint initialMode;
    }
}

namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    // SVD reset PN/SKU, deliberately synthetic zero unique IDs, and the shared revision hypothesis.
    public sealed class BlackwallChipIdentity
    {
        public BlackwallChipIdentity(uint revision,int jedecMockPart=-1,long jedecMockCid=-1)
        {
            if(revision<0x21 || revision>0x24) throw new System.ArgumentException("Unsupported synthetic revision");
            if((jedecMockPart==-1)!=(jedecMockCid==-1) || jedecMockPart < -1 || jedecMockPart>0xfff || jedecMockCid < -1 || jedecMockCid>0xffffffffL) throw new System.ArgumentException("Explicit paired JEDEC mock part/CID required");
            JedecMockPart=jedecMockPart; JedecMockCid=jedecMockCid;
            var a=new System.Collections.Generic.List<ulong> {0x40020000,0x40020004,0x40020008,0x4002000c,0x40020010,0x40020014};
            var v=new System.Collections.Generic.List<uint> {0x10320080,0,0,revision,0,0x002d480f};
            if(jedecMockPart!=-1)
            {
                a.AddRange(new ulong[] {0xe00fefe0,0xe00fefe4,0xe00fefe8,0xe00fefec,0xe00feff0,0xe00feff4,0xe00feff8,0xe00feffc});
                v.AddRange(new uint[] {(uint)jedecMockPart&255,0xb0u|((uint)jedecMockPart>>8),((revision>>4)<<4)|9u,(revision&15)<<4,(uint)jedecMockCid&255,((uint)jedecMockCid>>8)&255,((uint)jedecMockCid>>16)&255,(uint)jedecMockCid>>24});
            }
            addresses=a.ToArray(); values=v.ToArray(); reads=new int[addresses.Length];
        }
        public void Reset() { System.Array.Clear(reads,0,reads.Length); }
        public bool Owns(ulong address) => Index(address)>=0;
        public bool TryRead(ulong address,out uint value)
        {
            var index=Index(address); value=0;
            if(index<0) return false;
            reads[index]++; value=values[index]; return true;
        }
        public uint GetValue(ulong address)
        { var i=Index(address); if(i<0) throw new System.ArgumentOutOfRangeException("address"); return values[i]; }
        public int GetReads(ulong address)
        { var i=Index(address); if(i<0) throw new System.ArgumentOutOfRangeException("address"); return reads[i]; }
        public System.Collections.Generic.IEnumerable<ulong> Addresses
        { get { foreach(var address in addresses) yield return address; } }
        public bool JedecMockEnabled => JedecMockPart!=-1;
        public int JedecMockPart { get; }
        public long JedecMockCid { get; }
        private int Index(ulong address)
        { for(var i=0;i<addresses.Length;i++) if(addresses[i]==address) return i; return -1; }
        private readonly ulong[] addresses;
        private readonly uint[] values;
        private readonly int[] reads;
    }
}

namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    // Explicit read-only digital readiness fixtures, not OTP data or an engine.
    public sealed class BlackwallOtpReadReadiness : Antmicro.Renode.Peripherals.IPeripheral
    {
        public BlackwallOtpReadReadiness(BlackwallPeripheralPower otpPower,BlackwallPeripheralPower cryptoPower,int hostIdle=-1,int ptmBusy=-1,int ptmReadBudget=0)
        {
            if(otpPower==null || cryptoPower==null || otpPower.Mask!=0x08000000u || cryptoPower.Mask!=0x200000u
                || hostIdle < -1 || hostIdle > 1 || ptmBusy < -1 || ptmBusy > 1
                || (ptmBusy==1 ? ptmReadBudget<1 || ptmReadBudget>4096 : ptmReadBudget!=0))
                throw new System.ArgumentException("OTP read readiness requires matching power domains, -1/0/1 profiles and finite busy observation budget");
            OtpPower=otpPower;CryptoPower=cryptoPower;HostIdle=hostIdle;PtmBusy=ptmBusy;PtmReadBudget=ptmReadBudget;
        }
        public bool Owns(ulong address) => address==0x400c0a7c || address==0x40014ac4;
        public bool TryRead(ulong address,out uint value)
        {
            value=0;
            if(address==0x400c0a7c && HostIdle!=-1 && OtpPower.Phase=="on" && CryptoPower.Phase=="on")
            {
                // Other bits retain the documented reset-shaped hypothesis.
                value=0x3b8u|(uint)HostIdle;HostReads++;hostOtpGeneration=OtpPower.Generation;hostCryptoGeneration=CryptoPower.Generation;return true;
            }
            if(address==0x40014ac4 && PtmBusy!=-1 && OtpPower.Phase=="on")
            {
                if(PtmBudgetExhausted)return false;
                value=(uint)PtmBusy;PtmReads++;ptmOtpGeneration=OtpPower.Generation;return true;
            }
            return false;
        }
        public void Reset() { HostReads=PtmReads=0;hostOtpGeneration=hostCryptoGeneration=ptmOtpGeneration=0; }
        public bool HostObservedForCurrentPower => HostReads>0 && OtpPower.Phase=="on" && CryptoPower.Phase=="on" && hostOtpGeneration==OtpPower.Generation && hostCryptoGeneration==CryptoPower.Generation;
        public bool PtmObservedForCurrentPower => PtmReads>0 && OtpPower.Phase=="on" && ptmOtpGeneration==OtpPower.Generation;
        private ulong hostOtpGeneration,hostCryptoGeneration,ptmOtpGeneration;
        public BlackwallPeripheralPower OtpPower { get; }
        public BlackwallPeripheralPower CryptoPower { get; }
        public int HostIdle { get; }
        public int PtmBusy { get; }
        public int PtmReadBudget { get; }
        public uint HostReads { get; private set; }
        public uint PtmReads { get; private set; }
        public bool PtmBudgetExhausted => PtmBusy==1 && PtmReads>=(uint)PtmReadBudget;
    }
}

namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    public sealed class BlackwallCryptoOtpPowerLifecycle : Antmicro.Renode.Peripherals.IPeripheral
    {
        public BlackwallCryptoOtpPowerLifecycle(BlackwallOtpReadReadiness readiness)
        {
            if(readiness==null || readiness.HostIdle!=1 || readiness.PtmBusy!=0)
                throw new System.ArgumentException("CRYPTO OTP lifecycle requires explicit idle HOST and clear PTM profiles");
            Readiness=readiness;
        }
        public bool CanShutdownCrypto() => Readiness.HostObservedForCurrentPower && Readiness.PtmObservedForCurrentPower;
        public bool CanShutdownOtp() => Readiness.PtmObservedForCurrentPower
            && Readiness.CryptoPower.Phase=="powered-off" && Readiness.CryptoPower.RequestWord==0 && Readiness.CryptoPower.StatusWord==0;
        public void Reset() { }
        public BlackwallOtpReadReadiness Readiness { get; }
    }

    public sealed class BlackwallOtpSerialSlots : Antmicro.Renode.Peripherals.IPeripheral
    {
        public BlackwallOtpSerialSlots(BlackwallOtpReadReadiness readiness,string profile)
        {
            if(readiness==null || (profile!="empty" && profile!="mock-first" && profile!="mock-last" && profile!="invalid-prefix" && profile!="invalid-digit"))
                throw new System.ArgumentException("OTP serial slots require readiness owner and explicit synthetic profile");
            Readiness=readiness;Profile=profile;
            contents=new byte[128];for(int i=0;i<contents.Length;i++)contents[i]=255;
            if(profile=="mock-first" || profile=="mock-last")Seed(0,"S211MOCK000001");
            if(profile=="mock-last")Seed(7,"P100MOCK000002");
            if(profile=="invalid-prefix")Seed(0,"X211MOCK000001");
            if(profile=="invalid-digit")Seed(0,"S211MOCK00000X");
        }
        private void Seed(int slot,string text)
        {
            var bytes=System.Text.Encoding.ASCII.GetBytes(text);
            if(bytes.Length!=14)throw new System.ArgumentException("Synthetic serial length must be14");
            System.Array.Copy(bytes,0,contents,slot*16,14);contents[slot*16+14]=contents[slot*16+15]=0;
        }
        public bool Owns(ulong address) => address>=Start && address<(ulong)Start+Length;
        public bool TryRead(ulong address,out uint value)
        {
            value=0;
            if((address&3)!=0 || address<Start || address>(ulong)Start+Length-4
                || Readiness.OtpPower.Phase!="on" || Readiness.CryptoPower.Phase!="on"
                || Readiness.HostIdle!=1 || Readiness.PtmBusy!=0 || !Readiness.HostObservedForCurrentPower || !Readiness.PtmObservedForCurrentPower)return false;
            int offset=(int)(address-Start);
            for(int j=0;j<4;j++)value|=(uint)contents[offset+j]<<(8*j);
            Reads++;LastAddress=(uint)address;return true;
        }
        public void Reset() { Reads=LastAddress=0; }
        public uint Start => 0x400c2340u;
        public uint Length => 128;
        public string Profile { get; }
        public BlackwallOtpReadReadiness Readiness { get; }
        public uint Reads { get; private set; }
        public uint LastAddress { get; private set; }
        private readonly byte[] contents;
    }
}
