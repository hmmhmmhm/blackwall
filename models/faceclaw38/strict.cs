using Antmicro.Renode.Peripherals;
using Antmicro.Renode.Core;
using Antmicro.Renode.Peripherals.Timers;
using Antmicro.Renode.Time;
using Antmicro.Renode.Peripherals.Bus;
using Antmicro.Renode.Peripherals.CPU;
using System.Linq;

namespace Antmicro.Renode.Peripherals.Miscellaneous
{
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
        public BlackwallG2StartupFixture(long size, ulong baseAddress, string powerMode = "none", int resetLatch = -1, bool startupControls = false, string shadowInfo1 = "none", string info1Metadata = "none", int chipRevision = -1, bool spotStorage = false, bool memoryStartup = false, bool halStorage = false, bool mramControlStorage = false, bool buckOverrideStorage = false, bool buckStartStorage = false, bool coreLdoReduction = false, bool memLdoSetup = false, int buckStatusFixture = -1, bool prefetchStorage = false, int buckResponse = -1, bool vddfTempcoStorage = false, int mcuClockResponse = -1, bool gfxPowerStorage = false, bool hfrcForceControl = false, bool gpuPowerPreparation = false, int gpuPowerResponse = -1, bool gpuInterruptClear = false, BlackwallG2StartupFixture gpuControlOwner = null, bool gpuIdInitialization = false, bool gpuRingConfiguration = false, int gpuIdentityResponse = -1, bool gpuInitialResets = false, bool gpuRasterInitStorage = false, bool gpuConfigLowResponse = false, int gpuConfigHighHypothesis = -1, int gpuInitialStatusHypothesis = -1, int gpuPowerOffResponse = -1, bool gpuOffSequenceStorage = false, bool gpioConfigStorage = false, bool gpioInterruptIdle = false, bool gpioOutputLatch = false, bool adcInfoZeroFixture = false, bool adcCalibrationControl = false, int adcPowerResponse = -1, bool adcTriggerConfigStorage = false, bool adcDisabledConfigStorage = false, bool adcEnableLatch = false, BlackwallAdcInternalTrigger adcInternalTrigger = null, int adcConstantChannel3 = -1, int adcPowerOffResponse = -1, BlackwallUartAdapter uart1 = null, int uart1PowerResponse = -1, int uart1OffResponse = -1, BlackwallUartAdapter uart0 = null, int uart0PowerResponse = -1, int uart0OffResponse = -1, BlackwallUartAdapter uart2 = null, int uart2PowerResponse = -1, int uart2OffResponse = -1, BlackwallUartAdapter uart3 = null, int uart3PowerResponse = -1, int uart3OffResponse = -1, BlackwallPeripheralPower iom2Power = null, BlackwallPeripheralPower iom4Power = null, BlackwallPeripheralPower iom5Power = null, BlackwallPeripheralPower iom7Power = null, int rtcOselInitial = -1, IBlackwallRtc rtc = null, bool chipInfo = false, int jedecMockPart = -1, long jedecMockCid = -1, BlackwallG2StartupFixture chipInfoOwner = null, IBlackwallStimer stimer = null, BlackwallPeripheralPower mspi1Power = null, IBlackwallMspi1Clock mspi1Clock = null, IBlackwallMspi1Config mspi1Config = null, IBlackwallTimer14 timer14 = null, BlackwallPeripheralPower otpPower = null, BlackwallPeripheralPower cryptoPower = null, int cryptoNvmIdle = -1, BlackwallOtpReadReadiness otpReadReadiness = null, BlackwallOtpSerialSlots otpSerialSlots = null, BlackwallCryptoOtpPowerLifecycle cryptoOtpPowerLifecycle = null, BlackwallGpioRoleInput gpioRoleInput = null, bool uartHcpaStatus = false, bool uartHcpaGate = false, bool gpioOutputIdempotentWrites = false, BlackwallPeripheralPower iom6Power = null, IBlackwallEm9305Reset em9305Reset = null, BlackwallPeripheralPower mspi0Power = null, IBlackwallMspi1Config mspi0Config = null, BlackwallCpuNormalSleep cpuNormalSleep = null, int gpuRuntimeWakeResponse = -1, BlackwallGpioInterruptIdle gpioInterruptController = null)
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
            HalStorage = halStorage ? new BlackwallHalStorage() : null;
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
                if(address == 0x42003310) { TrimRevisionReads++; return MetadataValue; }
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
                else if(accepted && ac) accepted=AdcPower.TryWrite(ad,AdcCalibrationControl.Value==0 && BuckResponsePhase=="active",AdcScan!=null && !AdcDisabledConfig.Enabled && AdcScan.Count==0 && AdcInternalTrigger.Phase=="stopped");
                else if(accepted && changedUart!=-1)
                {
                    var power=UartPowers[changedUart];
                    var held=UartPowers.Any(p => p.Key!=changedUart && p.Value.Phase=="on" && p.Value.RequestWord==p.Value.Mask && p.Value.StatusWord==p.Value.Mask);
                    accepted=UartHcpaGate
                        ? power.TryWriteShared(value&power.Mask,BuckResponsePhase=="active",Uarts[changedUart].Quiescent,held)
                        : power.TryWrite(value&power.Mask,BuckResponsePhase=="active",Uarts[changedUart].Quiescent);
                }
                else if(accepted && changedIom!=-1) accepted=IomPowers[changedIom].TryWrite(value&IomPowers[changedIom].Mask,BuckResponsePhase=="active",IomPowers[changedIom].CanShutdown());
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
                else if(accepted && adcChanged) accepted=AdcPower.TryWrite(adcNext,AdcCalibrationControl.Value==0 && BuckResponsePhase=="active",AdcScan!=null && !AdcDisabledConfig.Enabled && AdcScan.Count==0 && AdcInternalTrigger.Phase=="stopped");
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
                    var ready=UartPowers[pair.Key].Phase=="on" && MemLdo!=null && MemLdo.StepsCompleted==2;
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
                    var ordered = BuckOverrideStep < BuckSteps.Length && value == BuckSteps[BuckOverrideStep]
                        && (BuckOverrideStep > 0 || VrctrlValue == 0xe000);
                    if(legacy || ordered)
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
        public BlackwallMemoryStartup()
        {
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
            RomDisables = 0;
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
                    if(value != 0x1f || register.Value != 0x3f) return false;
                    registers[0x40021018].Value = 0x4f;
                    RomDisables++;
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
        private readonly System.Collections.Generic.Dictionary<ulong,BlackwallMemoryRegister> registers;
    }
}

namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    public sealed class BlackwallHalStorage
    {
        public BlackwallHalStorage()
        {
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
            if(!registers.TryGetValue(address,out var register) || System.Array.IndexOf(allowed[address],value) < 0)
                return false;
            register.Writes++;
            register.Value = value;
            return true;
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
        public uint ReducedTrim => (OriginalWord & 0x3ff) > 7 ? (OriginalWord & 0x3ff)-7 : 0;
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
            if(value != ((r.Value & ~Masks[StepsCompleted]) | Fields[StepsCompleted])) return false;
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
            if(address!=Address || Applied || !active || setup.StepsCompleted!=2) return false;
            var r=hal.Registers[Address];
            var expected=(OriginalWord & ~127u) | ReducedTrim;
            if(r.Reads<2 || r.Value!=OriginalWord || value!=expected) return false;
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
            if(Phase!="idle" || (previous&0x80000000u)!=0 || word!=(previous|0x80000000u) || (cfg&0x100005u)!=0x100005u) return false;
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
        public BlackwallCpuNormalSleep(IMachine machine,string profile,uint flushReadPc,uint retentionStorePc=0,uint retentionReturnPc=0,bool inactiveAudioStatus=false,bool retentionFlush=false)
        {
            if(machine==null || profile!="normal-sleep-storage" || flushReadPc<0x438000 || flushReadPc>=0x800000 || (flushReadPc&1)!=0)
                throw new System.ArgumentException("Explicit normal sleep storage, machine and original flush PC required");
            if((retentionStorePc==0)!=(retentionReturnPc==0) || (retentionStorePc!=0 &&
                (retentionStorePc<0x438000 || retentionStorePc>=0x800000 || (retentionStorePc&1)!=0 || retentionReturnPc<0x438000 || retentionReturnPc>=0x800000 || (retentionReturnPc&1)!=0)))
                throw new System.ArgumentException("Retention staging requires a pinned store and return pair");
            this.machine=machine;FlushReadPc=flushReadPc;RetentionStorePc=retentionStorePc;RetentionReturnPc=retentionReturnPc;InactiveAudioStatus=inactiveAudioStatus;RetentionFlush=retentionFlush;Reset();
        }
        public bool Owns(ulong address) => (InactiveAudioStatus && address==0x40021010) ||  address==0x40021050 || address==0xe001e300 || address==0x47ff0000;
        public void Reset() { PowerControlReads=CpdReads=CpdWrites=FlushReads=CpdValue=RetentionStages=AudioStatusReads=RetentionFlushes=0; }
        public bool TryRead(ulong address,out uint value)
        {
            value=0;
            if(InactiveAudioStatus && address==0x40021010) { AudioStatusReads++;return true; }
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
            if(address==0xe001e300 && value==0x22u)
            {
                if(RetentionStorePc==0 || !machine.SystemBus.TryGetCurrentCPU(out var current))return false;
                var cpu=current as CortexM;
                if(cpu==null || cpu.PC.RawValue!=RetentionStorePc || cpu.GetRegister(14).RawValue!=(RetentionReturnPc|1u))return false;
                var sp=cpu.GetRegister(13).RawValue;
                if(sp<0x20000000 || sp>0x20380000-3 || machine.SystemBus.ReadByte(sp)!=0 || machine.SystemBus.ReadByte(sp+1)!=2 || machine.SystemBus.ReadByte(sp+2)!=2)return false;
                CpdValue=value;CpdWrites++;RetentionStages++;return true;
            }
            if(address!=0xe001e300 || (value!=0 && value!=0x11u) || (value==0x11u && PowerControlReads<=FlushReads))return false;
            CpdValue=value;CpdWrites++;return true;
        }
        public bool TryReadFlush(uint pc,uint baseRegister,out uint value)
        {
            value=0;
            if(RetentionFlush && pc==FlushReadPc && baseRegister==0x47ff0000u && CpdValue==0x22u && RetentionStages>RetentionFlushes)
            {
                if(!machine.SystemBus.TryGetCurrentCPU(out var current) || !(current is CortexM) || (machine.SystemBus.ReadDoubleWord(0xe000ed10)&4u)==0)return false;
                RetentionFlushes++;return true;
            }
            if(pc!=FlushReadPc || baseRegister!=0x47ff0000u || CpdValue!=0x11u || PowerControlReads<=FlushReads)return false;
            // Declared synchronous bus fixture; not a physical APB latency model.
            FlushReads++;return true;
        }
        public bool RetentionFlush {get;}
        public uint RetentionFlushes {get;private set;}
        public bool InactiveAudioStatus {get;}
        public uint AudioStatusReads {get;private set;}
        public uint RetentionStorePc { get; }
        public uint RetentionReturnPc { get; }
        public uint RetentionStages { get; private set; }
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
        public BlackwallPeripheralPower(uint mask,int profile,int offProfile=-1)
        {
            if(mask==0 || (mask&(mask-1))!=0 || profile<0 || profile>1 || offProfile < -1 || offProfile > 1) throw new System.ArgumentException("Power domain requires one mask bit and known profiles");
            Mask=mask; Profile=profile; OffProfile=offProfile; Reset();
        }
        public System.Func<bool> ShutdownReady { get; set; }
        public event System.Action PoweredOff;
        public bool CanShutdown() => ShutdownReady!=null && ShutdownReady();
        public void Reset() { Generation++; Phase="off"; RequestWord=StatusWord=0; Requests=Responses=OffRequests=PowerCycles=0; }
        public bool TryWrite(uint value,bool ready,bool quiescent=false)
        {
            if(value==0 && Phase=="on" && OffProfile!=-1 && quiescent) { Generation++; RequestWord=0; Phase="off-requested"; OffRequests++; return true; }
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
            if(receiveFifo && (module!=0 || !interrupts))throw new System.ArgumentException("RX FIFO requires interrupt-enabled UART0");
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
            if(value==Mask && ready && Phase=="off")
            { Phase="requested";RequestWord=Mask;Requests++;Transitions++;return true; }
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
        { ModeWord=initialMode; Phase="initial"; ForceWrites=ClockReads=ModeReads=ModeWrites=Transitions=0; }
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
            if(!buckActive) return false;
            if(address==0x40004044)
            {
                var r=hal.Registers[address];
                if(((r.Value^value)&~(HfrcForceControl ? 33u : 32u))!=0) return false;
                r.Value=value; r.Writes++; ForceWrites++;
                if(Phase=="initial") Phase="clock-requested";
                return true;
            }
            if(address!=0x40021000 || (value&3)!=2 || (value&~3u)!=(ModeWord&~3u) || !Ready) return false;
            var old=(ModeWord>>3)&3;
            var status=(Profile==2 || Profile==3) ? old : 2u;
            var ack=Profile!=2;
            ModeWord=2u|(ack ? 4u : 0)|(status<<3); ModeWrites++;
            if(status!=old) Transitions++;
            Phase=!ack ? "pending" : status==2 ? "acked" : "denied";
            return true;
        }
        public int Profile { get; }
        public string Phase { get; private set; }
        public uint ModeWord { get; private set; }
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

namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using System.Collections.Generic;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals;
    using Antmicro.Renode.Peripherals.CPU;
    using Antmicro.Renode.Peripherals.Memory;
    using Antmicro.Renode.Logging.Profiling;
    
    public sealed class BlackwallMemoryPolicy : IPeripheral
    {
        public BlackwallMemoryPolicy(IMachine machine, TranslationCPU cpu, MappedMemory main,
            MappedMemory itcm, ulong mainLength)
        {
            if(mainLength < 10 || mainLength > 0x3c0000)
                throw new ArgumentException("Main extent outside research mapping");
            this.machine = machine;
            this.cpu = cpu;
            this.main = main;
            this.itcm = itcm;
            this.mainLength = mainLength;
            Reset();
        }

        public void Reset()
        {
            Array.Clear(written, 0, written.Length);
            validatedBlocks.Clear();
            Violations = WrittenBytes = 0;
            LastAddress = LastPC = 0;
            LastWidth = 0;
            LastOperation = "none";
        }

        public void Attach()
        {
            if(attached) throw new InvalidOperationException("Policy already attached");
            var bus = machine.SystemBus;
            cpu.EnableExternalWindowMmu(ExternalMmuPosition.BeforeInternal);
            AddWindow(0,MainBase,ExternalMmuBase.Privilege.All);
            AddWindow(MainBase,MainBase+0x3c0000,ExternalMmuBase.Privilege.Read | ExternalMmuBase.Privilege.Execute);
            AddWindow(MainBase+0x3c0000,0x100000000,ExternalMmuBase.Privilege.All);
            cpu.AddHookOnMmuFault((address,accessType,windowId,firstTry) =>
            {
                Stop(accessType == AccessType.Write && address >= MainBase && address < MainBase+0x3c0000
                    ? "write-main" : "external-permission-fault",address,0);
                return ExternalMmuResult.Fault;
            });
            bus.SetHookAfterPeripheralRead<byte>(main, (v,o) => { CheckMainRead(o,1); return v; });
            bus.SetHookAfterPeripheralRead<ushort>(main, (v,o) => { CheckMainRead(o,2); return v; });
            bus.SetHookAfterPeripheralRead<uint>(main, (v,o) => { CheckMainRead(o,4); return v; });
            bus.SetHookAfterPeripheralRead<ulong>(main, (v,o) => { CheckMainRead(o,8); return v; });
            cpu.SetHookAtMemoryAccess((pc,operation,virtualAddress,physicalAddress,width,value) =>
            {
                if((operation == MemoryOperation.MemoryWrite || operation == MemoryOperation.MemoryIOWrite)
                    && physicalAddress < 0x40000)
                    MarkWritten((long)physicalAddress,(int)width);
            });
            for(ulong page=MainBase; page<MainBase+0x3c0000; page+=0x1000) cpu.SetPageAccessViaIo(page);
            cpu.SetHookAtBlockBegin(CheckBlock);
            attached = true;
        }

        private void AddWindow(ulong start, ulong end, ExternalMmuBase.Privilege permissions)
        {
            var id = cpu.AcquireExternalMmuWindow(ExternalMmuBase.Privilege.All);
            cpu.SetMmuWindowPrivileges(id,permissions);
            cpu.SetMmuWindowStart(id,start);
            cpu.SetMmuWindowEnd(id,end);
            cpu.SetMmuWindowAddend(id,0);
        }

        private void CheckMainRead(long offset, int width)
        {
            if(offset < 0 || (ulong)offset+ (ulong)width > mainLength)
                Stop("read-main-padding", MainBase+(ulong)offset, width);
        }

        private void MarkWritten(long offset, int width)
        {
            if(offset < 0 || offset+width > written.Length)
                Stop("write-outside-itcm", (ulong)offset, width);
            validatedBlocks.Clear();
            for(var i=offset; i<offset+width; i++)
            {
                if(!written[i]) { written[i] = true; WrittenBytes++; }
            }
        }

        private void CheckBlock(ulong pc, uint instructions)
        {
            if(pc >= MainBase && pc < MainBase+mainLength && pc+4UL*instructions <= MainBase+mainLength)
                return;
            if(pc < 0x40000 && validatedBlocks.TryGetValue(pc,out var cachedSize) && cachedSize == instructions) return;
            var address = pc;
            for(uint i=0; i<instructions; i++)
            {
                var inMain = address >= MainBase && address+2 <= MainBase+mainLength;
                var inItcm = address+2 <= 0x40000;
                if(!inMain && !inItcm) Stop("execute-outside-code",address,2);
                if(inItcm && (!written[address] || !written[address+1]))
                    Stop("execute-unwritten-itcm",address,2);
                var first = inMain ? main.ReadWord((long)(address-MainBase)) : itcm.ReadWord((long)address);
                var width = (first >> 11) >= 0x1d ? 4 : 2;
                if(inMain && address+(ulong)width > MainBase+mainLength)
                    Stop("execute-outside-code",address,width);
                if(inItcm && (address+(ulong)width > 0x40000 ||
                    (width == 4 && (!written[address+2] || !written[address+3]))))
                    Stop("execute-unwritten-itcm",address,width);
                address += (ulong)width;
            }
            if(pc < 0x40000) validatedBlocks[pc] = instructions;
        }

        private void Stop(string operation, ulong address, int width)
        {
            Violations++;
            LastOperation = operation;
            LastAddress = address;
            LastWidth = width;
            LastPC = cpu.PC.RawValue;
            throw new CpuAbortException($"BLACKWALL memory policy {operation} at 0x{address:x}, width {width}");
        }

        public int Violations { get; private set; }
        public string LastOperation { get; private set; }
        public ulong LastAddress { get; private set; }
        public ulong LastPC { get; private set; }
        public int LastWidth { get; private set; }
        public int WrittenBytes { get; private set; }
        private const ulong MainBase = 0x438000;
        private readonly IMachine machine;
        private readonly TranslationCPU cpu;
        private readonly MappedMemory main;
        private readonly MappedMemory itcm;
        private readonly ulong mainLength;
        private readonly bool[] written = new bool[0x40000];
        private readonly Dictionary<ulong,uint> validatedBlocks = new Dictionary<ulong,uint>();
        private bool attached;
    }
}

namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Core.Structure.Registers;
    using Antmicro.Renode.Peripherals.CPU;
    using Antmicro.Renode.Peripherals.IRQControllers;

    public sealed class BlackwallSystemControl
    {
        public BlackwallSystemControl(IMachine machine,CortexM cpu,NVIC nvic,bool coherentICache,bool coherentDCache=false,bool sramAddressMaintenance=false)
        {
            if(coherentDCache && !coherentICache) throw new ArgumentException("Data cache requires coherent instruction memory");
            if(sramAddressMaintenance && !coherentDCache) throw new ArgumentException("SRAM address maintenance requires coherent data cache");
            this.machine=machine;this.cpu=cpu;this.nvic=nvic;FunctionalICache=coherentICache;
            DataCache=coherentDCache ? new BlackwallCoherentDataCache(sramAddressMaintenance) : null;
        }
        public void Attach()
        {
            if(attached) throw new InvalidOperationException("System control already attached");
            nvic.RegisterCollection.DefineRegister(0xf50).WithValueField(0,32,FieldMode.Write,name:"functional_ICIALLU");
            foreach(var offset in new long[]{0xf5c,0xf60,0xf68,0xf6c,0xf70,0xf74})
                nvic.RegisterCollection.DefineRegister(offset).WithValueField(0,32,FieldMode.Write,name:"guarded_data_maintenance");
            var bus=machine.SystemBus;
            bus.SetHookBeforePeripheralWrite<byte>(nvic,(v,o)=>(byte)Write(o,1,v));
            bus.SetHookBeforePeripheralWrite<ushort>(nvic,(v,o)=>(ushort)Write(o,2,v));
            bus.SetHookBeforePeripheralWrite<uint>(nvic,(v,o)=>(uint)Write(o,4,v));
            bus.SetHookBeforePeripheralWrite<ulong>(nvic,(v,o)=>Write(o,8,v));
            bus.SetHookAfterPeripheralRead<byte>(nvic,(v,o)=>(byte)Read(o,1,v));
            bus.SetHookAfterPeripheralRead<ushort>(nvic,(v,o)=>(ushort)Read(o,2,v));
            bus.SetHookAfterPeripheralRead<uint>(nvic,(v,o)=>(uint)Read(o,4,v));
            bus.SetHookAfterPeripheralRead<ulong>(nvic,(v,o)=>Read(o,8,v));
            attached=true;
        }
        private static bool Touches(long o,int width,long target) => o < target+4 && o+width > target;
        private ulong Read(long offset,int width,ulong value)
        {
            if(offset < 0xd88 && offset+width > 0xd80)
            {
                if(DataCache!=null && DataCache.TryRead(offset,width,out var geometry)) return geometry;
                Stop("read",offset,width,0);
            }
            if(offset < 0xf78 && offset+width > 0xf58) Stop("read",offset,width,0);
            if(Touches(offset,width,0xf50)) Stop("read",offset,width,0);
            if(Touches(offset,width,0xd14))
            {
                if(offset!=0xd14 || width!=4) Stop("read",offset,width,0);
                CcrReads++;
                if(FunctionalICache) return (value & ~(IC|DC)) | (ICacheEnabled ? IC : 0)
                    | (DataCache!=null && DataCache.Enabled ? DC : 0);
            }
            return value;
        }
        private ulong Write(long offset,int width,ulong value)
        {
            if((offset < 0xd88 && offset+width > 0xd80) || (offset < 0xf78 && offset+width > 0xf58))
            {
                if(DataCache!=null && DataCache.TryWrite(offset,width,value)) return 0;
                Stop("write",offset,width,value);
            }
            if(Touches(offset,width,0xf50))
            {
                if(!FunctionalICache || offset!=0xf50 || width!=4 || value!=0) Stop("write",offset,width,value);
                Invalidations++;
                return 0;
            }
            if(Touches(offset,width,0xd14))
            {
                if(offset!=0xd14 || width!=4) Stop("write",offset,width,value);
                if(!FunctionalICache)
                {
                    if((value & (IC|DC))!=0) Stop("write",offset,width,value);
                    return value;
                }
                var current=(ulong)cpu.ConfigurationAndControlRegister & ~(IC|DC);
                if((value & ~(IC|DC))!=current || ((value & IC)!=0 && Invalidations==0)
                    || ((value & DC)!=0 && DataCache==null)
                    || (DataCache!=null && !DataCache.CanSetEnabled((value & DC)!=0)))
                    Stop("write",offset,width,value);
                ICacheEnabled=(value & IC)!=0;
                if(DataCache!=null) DataCache.SetEnabled((value & DC)!=0);
                CcrWrites++;
                return value & ~(IC|DC);
            }
            return value;
        }
        private void Stop(string operation,long offset,int width,ulong value)
        {
            Violations++; LastOperation=operation;LastAddress=0xe000e000+(ulong)offset;
            LastWidth=width;LastValue=value;LastPC=cpu.PC.RawValue;
            throw new CpuAbortException("BLACKWALL unsupported system control");
        }
        public bool FunctionalICache { get; }
        public BlackwallCoherentDataCache DataCache { get; }
        public bool ICacheEnabled { get; private set; }
        public int Invalidations { get; private set; }
        public int CcrReads { get; private set; }
        public int CcrWrites { get; private set; }
        public int Violations { get; private set; }
        public string LastOperation { get; private set; }="none";
        public ulong LastAddress { get; private set; }
        public ulong LastPC { get; private set; }
        public ulong LastValue { get; private set; }
        public int LastWidth { get; private set; }
        private const ulong IC=1UL<<17,DC=1UL<<16;
        private readonly IMachine machine;
        private readonly CortexM cpu;
        private readonly NVIC nvic;
        private bool attached;
    }

    public sealed class BlackwallCoherentDataCache
    {
        public BlackwallCoherentDataCache(bool sramAddressMaintenance=false) { SramAddressMaintenance=sramAddressMaintenance; }
        public bool TryRead(long offset,int width,out ulong value)
        {
            value=0;
            if(width!=4 || !Selected) return false;
            if(offset==0xd84) { SelectorReads++; return true; }
            if(offset==0xd80) { GeometryReads++; value=0xf03fe019; return true; }
            return false;
        }
        public bool TryWrite(long offset,int width,ulong value)
        {
            if(width!=4) return false;
            if(offset==0xf5c || offset==0xf68 || offset==0xf70)
            {
                var line=value&~31UL;
                if(!SramAddressMaintenance || value>uint.MaxValue || line<0x20000000 || line>=0x20380000)return false;
                if(offset==0xf5c)AddressInvalidations++;
                else if(offset==0xf68)AddressCleans++;
                else AddressCleanInvalidations++;
                LastAddressLine=line; return true;
            }
            if(offset==0xd84 && value==0) { Selected=true; SelectorWrites++; return true; }
            if(!Selected || (value & ~0xc0003fe0UL)!=0) return false;
            if(offset==0xf60) Invalidations++;
            else if(offset==0xf6c) Cleans++;
            else if(offset==0xf74) CleanInvalidations++;
            else return false;
            if(offset!=0xf6c)
            {
                var index=(int)(((value>>5)&511)*4+(value>>30));
                if(!initialized[index]) { initialized[index]=true; InitializedLines++; }
            }
            return true;
        }
        public bool CanSetEnabled(bool enabled) => !enabled || Enabled || InitializedLines==2048;
        public void SetEnabled(bool enabled)
        {
            if(!CanSetEnabled(enabled)) throw new InvalidOperationException("Data cache not initialized");
            if(Enabled && !enabled) { Array.Clear(initialized,0,initialized.Length); InitializedLines=0; }
            Enabled=enabled;
        }
        public bool Enabled { get; private set; }
        public bool SramAddressMaintenance { get; }
        public ulong LastAddressLine { get; private set; }
        public int AddressInvalidations { get; private set; }
        public int AddressCleans { get; private set; }
        public int AddressCleanInvalidations { get; private set; }
        public bool Selected { get; private set; }
        public int SelectorReads { get; private set; }
        public int SelectorWrites { get; private set; }
        public int GeometryReads { get; private set; }
        public int InitializedLines { get; private set; }
        public int Invalidations { get; private set; }
        public int Cleans { get; private set; }
        public int CleanInvalidations { get; private set; }
        private readonly bool[] initialized=new bool[2048];
    }
}

namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    public sealed class BlackwallResetController : BlackwallStrictMMIO
    {
        public BlackwallResetController() : base(0x1000, 0x40000000) { Reset(); }
        public override void Reset()
        {
            base.Reset();
            Configuration = 0;
            ConfigurationReads = ConfigurationWrites = 0;
        }
        public override uint ReadDoubleWord(long offset)
        {
            if(offset == 0) { ConfigurationReads++; return Configuration; }
            return base.ReadDoubleWord(offset);
        }
        public override void WriteDoubleWord(long offset, uint value)
        {
            if(offset == 0 && value <= 3)
            {
                ConfigurationWrites++;
                Configuration = value;
                return;
            }
            base.WriteDoubleWord(offset, value);
        }
        public uint Configuration { get; private set; }
        public int ConfigurationReads { get; private set; }
        public int ConfigurationWrites { get; private set; }
        public bool WatchdogResetEnabled => (Configuration & 2) != 0;
        public bool HardwareVerified => false;
        public string ResetPropagation => "unsupported; CFG storage and watchdog gate only";
    }
}

namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals.Bus;
    using Antmicro.Renode.Peripherals.Timers;
    using Antmicro.Renode.Time;

    public sealed class BlackwallApollo510Watchdog : BlackwallStrictMMIO
    {
        public BlackwallApollo510Watchdog(IMachine machine, BlackwallResetController resetController = null) : base(0x1000, 0x40024000)
        {
            this.machine = machine;
            this.resetController = resetController;
            counter = new LimitTimer(machine.ClockSource, 256, this, "Counter", 4096,
                Direction.Ascending, enabled: false, workMode: WorkMode.Periodic);
            interrupt = new LimitTimer(machine.ClockSource, 256, this, "Interrupt", 16,
                Direction.Ascending, enabled: false, workMode: WorkMode.OneShot, eventEnabled: true);
            resetRequest = new LimitTimer(machine.ClockSource, 256, this, "ResetRequest", 16,
                Direction.Ascending, enabled: false, workMode: WorkMode.OneShot, eventEnabled: true);
            IRQ = new GPIO();
            interrupt.LimitReached += () => { InterruptEvents++; pending = true; UpdateIRQ(); };
            resetRequest.LimitReached += () =>
            {
                ResetDue = true;
                ResetGatingEvaluated = resetController != null;
                ResetAllowedByGate = resetController != null && resetController.WatchdogResetEnabled;
                counter.Enabled = interrupt.Enabled = resetRequest.Enabled = false;
                machine.PauseAndRequestEmulationPause();
            };
            Reset();
        }

        public override void Reset()
        {
            base.Reset();
            Configuration = 0;
            Restarts = InterruptEvents = ConfigurationReads = ConfigurationWrites = 0;
            pending = interruptEnabled = ResetDue = false;
            ResetGatingEvaluated = ResetAllowedByGate = false;
            counter.Reset();
            interrupt.Reset();
            resetRequest.Reset();
            IRQ.Unset();
        }

        private bool Supported(uint value)
        {
            var clock = value >> 24;
            if((value & ~0x07ffff07u) != 0 || clock > 4) return false;
            if((value & 1) != 0 && clock != 0)
            {
                if((value & 2) != 0 && ((value >> 16) & 255) == 0) return false;
                if((value & 4) != 0 && ((value >> 8) & 255) == 0) return false;
            }
            // Active reconfiguration, including disable, needs a separate model.
            return (Configuration & 1) == 0 || value == Configuration;
        }

        private void RestartTimers()
        {
            var clock = Configuration >> 24;
            var frequency = new ulong[] { 16, 2048, 256, 16, 1 }[clock];
            counter.Enabled = interrupt.Enabled = resetRequest.Enabled = false;
            counter.Frequency = interrupt.Frequency = resetRequest.Frequency = frequency;
            interrupt.Limit = System.Math.Max(1ul, ((Configuration >> 16) & 255) * 16ul);
            resetRequest.Limit = System.Math.Max(1ul, ((Configuration >> 8) & 255) * 16ul);
            counter.ResetValue();
            interrupt.ResetValue();
            resetRequest.ResetValue();
            var running = (Configuration & 1) != 0 && clock != 0 && !ResetDue;
            counter.Enabled = running;
            interrupt.Enabled = running && (Configuration & 2) != 0;
            resetRequest.Enabled = running && (Configuration & 4) != 0;
        }

        private void SyncTime()
        {
            if(machine.GetSystemBus(this).TryGetCurrentCPU(out var cpu)) cpu.SyncTime();
        }

        private void UpdateIRQ() { IRQ.Set(pending && interruptEnabled); }

        public override uint ReadDoubleWord(long offset)
        {
            switch(offset)
            {
            case 0: ConfigurationReads++; return Configuration;
            case 4: return 0;
            case 0xc: SyncTime(); return (uint)(counter.Value / 16) & 255;
            case 0x200: return interruptEnabled ? 1u : 0;
            case 0x204: return pending ? 1u : 0;
            default: return base.ReadDoubleWord(offset);
            }
        }

        public override void WriteDoubleWord(long offset, uint value)
        {
            if(offset == 0 && Supported(value))
            {
                ConfigurationWrites++;
                if(value != Configuration)
                {
                    Configuration = value;
                    RestartTimers();
                }
                return;
            }
            if(offset == 4 && value == 0xb2)
            {
                Restarts++;
                RestartTimers();
                return;
            }
            if((offset == 0x200 || offset == 0x208 || offset == 0x20c) && value <= 1)
            {
                if(offset == 0x200) interruptEnabled = value != 0;
                if(offset == 0x208 && value != 0) pending = false;
                if(offset == 0x20c && value != 0) pending = true;
                UpdateIRQ();
                return;
            }
            base.WriteDoubleWord(offset, value);
        }

        public GPIO IRQ { get; }
        public uint Configuration { get; private set; }
        public int ConfigurationReads { get; private set; }
        public int ConfigurationWrites { get; private set; }
        public int Restarts { get; private set; }
        public int InterruptEvents { get; private set; }
        public bool ResetDue { get; private set; }
        public bool ResetGatingEvaluated { get; private set; }
        public bool ResetAllowedByGate { get; private set; }
        public bool InterruptPending => pending;
        public string SourceClock => "nominal LFRC=1024Hz hypothesis; sixteen timer substeps per counter tick";
        public string ResetPropagation => resetController == null
            ? "unsupported; pause at reset request threshold before RSTGEN gating"
            : "unsupported; evaluate WDREN gate and pause, no full-system reset";
        public bool HardwareVerified => false;
        private bool pending, interruptEnabled;
        private readonly IMachine machine;
        private readonly BlackwallResetController resetController;
        private readonly LimitTimer counter, interrupt, resetRequest;
    }
}

//
// Copyright (c) 2010-2023 Antmicro
//
// This file is licensed under the MIT License.
// Full license text is available in 'licenses/MIT.txt'.
//
namespace Antmicro.Renode.Peripherals.SPI
{
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;

using Antmicro.Renode.Core;
using Antmicro.Renode.Core.Structure;
using Antmicro.Renode.Core.Structure.Registers;
using Antmicro.Renode.Exceptions;
using Antmicro.Renode.Logging;
using Antmicro.Renode.Peripherals.Bus;
using Antmicro.Renode.Peripherals.I2C;
using Antmicro.Renode.Utilities;

    [AllowedTranslations(AllowedTranslation.ByteToDoubleWord | AllowedTranslation.WordToDoubleWord)]
    public class BlackwallPollingIomEngine : IPeripheralContainer<ISPIPeripheral, TypedNumberRegistrationPoint<int>>, IPeripheralContainer<II2CPeripheral, TypedNumberRegistrationPoint<int>>,
        IDoubleWordPeripheral, IProvidesRegisterCollection<DoubleWordRegisterCollection>, IPeripheral, IKnownSize
    {
        public BlackwallPollingIomEngine(IMachine machine)
        {
            RegistersCollection = new DoubleWordRegisterCollection(this);

            IRQ = new GPIO();

            // The countChangeAction cannot be set in the FIFO constructor.
            incomingFifo = new Fifo("incoming FIFO", this);
            incomingFifo.CountChangeAction += IncomingFifoCountChangeAction;
            outgoingFifo = new Fifo("outgoing FIFO", this);
            outgoingFifo.CountChangeAction += OutgoingFifoCountChangeAction;

            spiPeripherals = new Dictionary<int, ISPIPeripheral>();
            i2cPeripherals = new Dictionary<int, II2CPeripheral>();

            this.machine = machine;

            DefineRegisters();
            Reset();
        }

        public void Reset()
        {
            activeTransactionContinue = false;
            activeSpiSlaveSelect = 0;
            i2cSlaveAddress = 0;

            RegistersCollection.Reset();
            activeTransactionStatus.Value = Status.Idle;
            status = Status.Idle;

            IRQ.Unset();
            incomingFifo.Reset();
            outgoingFifo.Reset();
        }

        public uint ReadDoubleWord(long offset)
        {
            return RegistersCollection.Read(offset);
        }

        public void WriteDoubleWord(long offset, uint value)
        {
            RegistersCollection.Write(offset, value);
        }

        public void Register(ISPIPeripheral peripheral, TypedNumberRegistrationPoint<int> registrationPoint)
        {
            if(registrationPoint.Address < 0 || registrationPoint.Address >= MaxSpiPeripheralsConnected)
            {
                throw new ConstructionException($"Invalid SPI peripheral ID: {registrationPoint.Address}! Only IDs from 0 to {MaxSpiPeripheralsConnected - 1} are valid.");
            }
            Register(spiPeripherals, peripheral, registrationPoint.WithType<ISPIPeripheral>());
        }

        public void Register(II2CPeripheral peripheral, TypedNumberRegistrationPoint<int> registrationPoint)
        {
            Register(i2cPeripherals, peripheral, registrationPoint.WithType<II2CPeripheral>());
        }

        public void Unregister(ISPIPeripheral peripheral)
        {
            Unregister(spiPeripherals, peripheral);
        }

        public void Unregister(II2CPeripheral peripheral)
        {
            Unregister(i2cPeripherals, peripheral);
        }

        public IEnumerable<TypedNumberRegistrationPoint<int>> GetRegistrationPoints(ISPIPeripheral peripheral)
        {
            return spiPeripherals.Keys.Select(x => new TypedNumberRegistrationPoint<int>(x, typeof(ISPIPeripheral)))
                .ToList();
        }

        public IEnumerable<TypedNumberRegistrationPoint<int>> GetRegistrationPoints(II2CPeripheral peripheral)
        {
            return i2cPeripherals.Keys.Select(x => new TypedNumberRegistrationPoint<int>(x, typeof(II2CPeripheral)))
                .ToList();
        }

        IEnumerable<IRegistered<ISPIPeripheral, TypedNumberRegistrationPoint<int>>> IPeripheralContainer<ISPIPeripheral, TypedNumberRegistrationPoint<int>>.Children =>
            spiPeripherals.Select(x => Registered.Create(x.Value, new TypedNumberRegistrationPoint<int>(x.Key, typeof(ISPIPeripheral)))).ToList();

        IEnumerable<IRegistered<II2CPeripheral, TypedNumberRegistrationPoint<int>>> IPeripheralContainer<II2CPeripheral, TypedNumberRegistrationPoint<int>>.Children =>
            i2cPeripherals.Select(x => Registered.Create(x.Value, new TypedNumberRegistrationPoint<int>(x.Key, typeof(II2CPeripheral)))).ToList();

        public GPIO IRQ { get; }

        public DoubleWordRegisterCollection RegistersCollection { get; }

        public long Size => 0x400;

        private void DefineRegisters()
        {
            Registers.OutgoingFifoAccessPort.DefineMany(this, 8, (register, index) =>
                {
                    register.WithValueField(0, 32,
                        valueProviderCallback: _ => outgoingFifo.DirectGet((uint)index),
                        writeCallback: (_, newValue) => outgoingFifo.DirectSet((uint)index, (uint)newValue));
                }, stepInBytes: 4);

            Registers.IncomingFifoAccessPort.DefineMany(this, 8, (register, index) =>
                {
                    register.WithValueField(0, 32, FieldMode.Read,
                        valueProviderCallback: _ => incomingFifo.DirectGet((uint)index));
                }, stepInBytes: 4);

            Registers.FifoSizeAndRemainingSlotsOpenValues.Define(this)
                .WithValueField(0, 8, FieldMode.Read, name: "FIFO0SIZ", valueProviderCallback: _ => outgoingFifo.BytesCount)
                .WithValueField(8, 8, FieldMode.Read, name: "FIFO0REM", valueProviderCallback: _ => outgoingFifo.BytesLeft)
                .WithValueField(16, 8, FieldMode.Read, name: "FIFO1SIZ", valueProviderCallback: _ => incomingFifo.BytesCount)
                .WithValueField(24, 8, FieldMode.Read, name: "FIFO1REM", valueProviderCallback: _ => incomingFifo.BytesLeft)
                ;

            Registers.FifoThresholdConfiguration.Define(this)
                .WithValueField(0, 6, out fifoInterruptReadThreshold, name: "FIFORTHR")
                .WithReservedBits(6, 2)
                .WithValueField(8, 6, out fifoInterruptWriteThreshold, name: "FIFOWTHR")
                .WithReservedBits(14, 18)
                .WithChangeCallback((_, __) => UpdateFifoThresholdInterruptStatus())
                ;

            Registers.FifoPop.Define(this)
                .WithValueField(0, 32, FieldMode.Read, name: "FIFODOUT", valueProviderCallback: _ =>
                {
                    // "Will advance the internal read pointer of the incoming FIFO (FIFO1) when read, if POPWR is not active.
                    // If POPWR is active, a write to this register is needed to advance the internal FIFO pointer."
                    if(!(writePopToAdvanceReadPointer.Value ? incomingFifo.TryPeek(out var value) : incomingFifo.TryPop(out value)))
                    {
                        this.Log(LogLevel.Warning, "Failed to read from incoming FIFO");
                        InterruptStatusSet(IoMasterInterrupts.ReadFifoUnderflow, true);
                    }
                    return value;
                }, writeCallback: (_, __) =>
                {
                    if(writePopToAdvanceReadPointer.Value)
                    {
                        if(!incomingFifo.TryAdvancePointer())
                        {
                            this.Log(LogLevel.Warning, "Failed to advance the internal read pointer of the incoming FIFO");
                        }
                    }
                    else
                    {
                        this.Log(LogLevel.Warning, "Tried to write the FIFOPOP register but the POPWR isn't set");
                    }
                })
                ;

            Registers.FifoPush.Define(this)
                .WithValueField(0, 32, FieldMode.Write, name: "FIFODIN", writeCallback: (_, newValue) =>
                {
                    if(!outgoingFifo.TryPush((uint)newValue))
                    {
                        this.Log(LogLevel.Warning, "Failed to write to the outgoing FIFO (value: 0x{0})", newValue);
                        InterruptStatusSet(IoMasterInterrupts.WriteFifoOverflow, true);
                    }
                })
                ;

            Registers.FifoControl.Define(this, 0x00000002)
                .WithFlag(0, out writePopToAdvanceReadPointer, name: "POPWR")
                .WithFlag(1, name: "FIFORSTN", writeCallback: (_, newValue) =>
                    {
                        // FIFORSTN is an inversed reset flag; FIFOs are reset when this flag is 0.
                        incomingFifo.ResetFlag = !newValue;
                        outgoingFifo.ResetFlag = !newValue;
                    },
                    // The value should be the same for both FIFOs so it doesn't matter which is returned here.
                    valueProviderCallback: _ => incomingFifo.ResetFlag)
                .WithReservedBits(2, 30)
                ;

            Registers.FifoPointers.Define(this)
                .WithValueField(0, 4, FieldMode.Read, name: "FIFOWPTR", valueProviderCallback: _ => outgoingFifo.Pointer)
                .WithReservedBits(4, 4)
                .WithValueField(8, 4, FieldMode.Read, name: "FIFORPTR", valueProviderCallback: _ => incomingFifo.Pointer)
                .WithReservedBits(12, 20)
                ;

            // Some software expects values written to
            // IOCLKEN, FSEL, DIVEN, LOWPER, TOTPER to be retained
            Registers.IOClockConfiguration.Define(this)
                .WithFlag(0, name: "IOCLKEN")
                .WithReservedBits(1, 7)
                .WithValueField(8, 3, name: "FSEL")
                .WithTaggedFlag("DIV3", 11)
                .WithFlag(12, name: "DIVEN")
                .WithReservedBits(13, 3)
                .WithValueField(16, 8, name: "LOWPER")
                .WithValueField(24, 8, name: "TOTPER")
                ;

            Registers.SubmoduleControl.Define(this)
                .WithFlag(0, out spiMasterEnabled, name: "SMOD0EN")
                .WithEnumField<DoubleWordRegister, SubmoduleTypes>(1, 3, FieldMode.Read, name: "SMOD0TYPE", valueProviderCallback: _ => SubmoduleTypes.SpiMaster)
                .WithFlag(4, out i2cMasterEnabled, name: "SMOD1EN")
                .WithEnumField<DoubleWordRegister, SubmoduleTypes>(5, 3, FieldMode.Read, name: "SMOD1TYPE", valueProviderCallback: _ => SubmoduleTypes.I2CMaster)
                .WithTaggedFlag("SMOD2EN", 8)
                // It should be I2SMaster_Slave (0x4), but I2S isn't currently supported so let's mark it as NotInstalled.
                .WithEnumField<DoubleWordRegister, SubmoduleTypes>(9, 3, FieldMode.Read, name: "SMOD2TYPE", valueProviderCallback: _ => SubmoduleTypes.NotInstalled)
                .WithReservedBits(12, 20)
                .WithWriteCallback((_, __) =>
                {
                    if(spiMasterEnabled.Value && i2cMasterEnabled.Value)
                    {
                        this.Log(LogLevel.Warning, "Both SPI and I2C modules have been enabled");
                        spiMasterEnabled.Value = false;
                        i2cMasterEnabled.Value = false;
                    }
                })
                ;

            Registers.CommandAndOffset.Define(this)
                .WithEnumField(0, 4, out transactionCommand, name: "CMD")
                .WithValueField(4, 3, out transactionOffsetCount, name: "OFFSETCNT")
                .WithFlag(7, out transactionContinue, name: "CONT")
                .WithValueField(8, 12, out transactionSize, name: "TSIZE")
                .WithValueField(20, 2, out spiSlaveSelect, name: "CMDSEL")
                .WithReservedBits(22, 2)
                .WithValueField(24, 8, out transactionOffsetLow, name: "OFFSETLO")
                .WithWriteCallback((_, __) =>
                {
                    this.Log(LogLevel.Debug,
                            "Transaction received for #{0}; command: {1}, size: {2}, offset: <count: {3}, low=0x{4:X2}, high=0x{5:X8}>, cont: {6}",
                            PrettyPendingPeripheral, transactionCommand.Value, transactionSize.Value, transactionOffsetCount.Value,
                            transactionOffsetLow.Value, transactionOffsetHigh.Value, transactionContinue.Value);

                    if(!spiMasterEnabled.Value && !i2cMasterEnabled.Value)
                    {
                        this.Log(LogLevel.Error, "Invalid operation; SPI/I2C Master inferfaces are disabled!");
                        return;
                    }

                    if(activeTransactionCommand.Value != Commands.None)
                    {
                        this.Log(LogLevel.Error, "Dropping the new transaction received for #{0}: {1}; {2} on {3} is still being processed.",
                            PrettyPendingPeripheral, transactionCommand.Value, activeTransactionCommand.Value, PrettyActivePeripheral);
                        return;
                    }

                    if(!IsTransactionValid(transactionCommand.Value, (uint)transactionSize.Value, (uint)transactionOffsetCount.Value,
                            (int)spiSlaveSelect.Value, out var errorMessage))
                    {
                        this.Log(LogLevel.Error, errorMessage);
                        activeTransactionStatus.Value = Status.Error;
                        status = Status.Idle;
                        InterruptStatusSet(IoMasterInterrupts.IllegalCommand);
                        return;
                    }

                    // Preserve important values for the transaction being currently processed.
                    // Only the command and size left values are accessible through registers.
                    activeTransactionCommand.Value = transactionCommand.Value;
                    activeTransactionContinue = transactionContinue.Value;
                    activeSpiSlaveSelect = (int)spiSlaveSelect.Value;
                    activeTransactionSizeLeft.Value = transactionSize.Value;

                    SendTransactionOffset((uint)transactionOffsetCount.Value);

                    if(activeTransactionSizeLeft.Value == 0)
                    {
                        // As this is 0-size TX transaction and we already send transaction offset,
                        // there is nothing more to do.
                        TryFinishTransaction();
                        return;
                    }

                    status = Status.Active;

                    while(activeTransactionSizeLeft.Value > 0)
                    {
                        if(activeTransactionCommand.Value == Commands.Read)
                        {
                            if(!incomingFifo.TryReceiveAndPush(ReceiveData))
                            {
                                this.Log(LogLevel.Debug, "Cannot push more data to the incoming FIFO; {0}B remain to complete the read command.",
                                    activeTransactionSizeLeft.Value);
                                break;
                            }
                        }
                        else if(activeTransactionCommand.Value == Commands.Write)
                        {
                            if(!outgoingFifo.TryPop(out var value))
                            {
                                this.Log(LogLevel.Debug, "No more data in the outgoing FIFO; {0}B remain to complete the write command.",
                                    activeTransactionSizeLeft.Value);
                                break;
                            }
                            SendData(value);
                        }  // No else because only Read and Write commands are handled after 'IsTransactionValid'.
                    }

                    if(activeTransactionSizeLeft.Value != 0)
                    {
                        activeTransactionStatus.Value = Status.Wait;
                    }
                })
                ;

            Registers.DcxControlAndCeUsageSelection.Define(this)
                .WithTag("DCXSEL", 0, 4)
                .WithTaggedFlag("DCXEN", 4)
                .WithReservedBits(5, 27)
                ;

            Registers.HighOrderBytesBfOffsetForIOTransaction.Define(this)
                .WithValueField(0, 32, out transactionOffsetHigh, name: "OFFSETHI")
                ;

            Registers.CommandStatus.Define(this)
                // This field is designed to hold the value written to CMD. The MSB is stated as unused.
                .WithEnumField(0, 5, out activeTransactionCommand, FieldMode.Read, name: "CCMD")
                .WithEnumField(5, 3, out activeTransactionStatus, FieldMode.Read, name: "CMDSTAT")
                .WithValueField(8, 12, out activeTransactionSizeLeft, FieldMode.Read, name: "CTSIZE")
                .WithReservedBits(20, 12)
                ;

            Registers.IOMasterInterruptsEnable.Define(this)
                .WithFlags(0, IoMasterInterruptsCount, out ioMasterInterruptsEnableFlags, name: "INTENi")
                .WithReservedBits(15, 17)
                .WithChangeCallback((_, __) => UpdateIRQ())
                ;

            Registers.IOMasterInterruptsStatus.Define(this)
                .WithFlags(0, IoMasterInterruptsCount, out ioMasterInterruptsStatusFlags, FieldMode.Read, name: "INTSTATi")
                .WithReservedBits(15, 17)
                ;

            Registers.IOMasterInterruptsClear.Define(this)
                .WithFlags(0, IoMasterInterruptsCount, FieldMode.Write, writeCallback: (interrupt, _, newValue) =>
                {
                    if(newValue)
                    {
                        InterruptStatusSet((IoMasterInterrupts)interrupt, false);
                    }
                }, name: "INTCLRi")
                // IgnoredBits not to trigger warnings when 0xFFFFFFFF is written to clear all INTs.
                .WithIgnoredBits(15, 17)
                ;

            Registers.IOMasterInterruptsSet.Define(this)
                .WithFlags(0, IoMasterInterruptsCount, FieldMode.Write, writeCallback: (interrupt, _, newValue) =>
                {
                    if(newValue)
                    {
                        InterruptStatusSet((IoMasterInterrupts)interrupt, true);
                    }
                }, name: "INTSETi")
                .WithReservedBits(15, 17)
                ;

            Registers.DmaTriggerEnable.Define(this)
                .WithTaggedFlag("DCMDCMPEN", 0)
                .WithTaggedFlag("DTHREN", 1)
                .WithReservedBits(2, 30)
                ;

            Registers.DmaTriggerStatus.Define(this)
                .WithTaggedFlag("DCMDCMP", 0)
                .WithTaggedFlag("DTHR", 1)
                .WithTaggedFlag("DTOTCMP", 2)
                .WithReservedBits(3, 29)
                ;

            Registers.DmaConfiguration.Define(this)
                .WithTaggedFlag("DMAEN", 0)
                .WithTaggedFlag("DMADIR", 1)
                .WithReservedBits(2, 6)
                .WithTaggedFlag("DMAPRI", 8)
                .WithTaggedFlag("DPWROFF", 9)
                .WithReservedBits(10, 22)
                ;

            Registers.DmaTotalTransferCount.Define(this)
                .WithTag("TOTCOUNT", 0, 12)
                .WithReservedBits(12, 20)
                ;

            Registers.DmaTargetAddress.Define(this)
                .WithTag("TARGADDR", 0, 29)
                .WithReservedBits(29, 3)
                ;

            Registers.DmaStatus.Define(this)
                .WithTaggedFlag("DMATIP", 0)
                .WithTaggedFlag("DMACPL", 1)
                .WithTaggedFlag("DMAERR", 2)
                .WithReservedBits(3, 29)
                ;

            Registers.CommandQueueConfiguration.Define(this)
                .WithTaggedFlag("CQEN", 0)
                .WithTaggedFlag("CQPRI", 1)
                .WithTag("MSPIFLGSEL", 2, 2)
                .WithReservedBits(4, 28)
                ;

            Registers.CommandQueueTargetReadAddress.Define(this)
                .WithReservedBits(0, 2)
                .WithTag("CQADDR", 2, 27)
                .WithReservedBits(29, 3)
                ;

            Registers.CommandQueueStatus.Define(this)
                .WithTaggedFlag("CQTIP", 0)
                .WithTaggedFlag("CQPAUSED", 1)
                .WithTaggedFlag("CQERR", 2)
                .WithReservedBits(3, 29)
                ;

            Registers.CommandQueueFlag.Define(this)
                .WithTag("CQFLAGS", 0, 16)
                .WithTag("CQIRQMASK", 16, 16)
                ;

            Registers.CommandQueueFlagSetClear.Define(this)
                .WithTag("CQFSET", 0, 8)
                .WithTag("CQFTGL", 8, 8)
                .WithTag("CQFCLR", 16, 8)
                .WithReservedBits(24, 8)
                ;

            Registers.CommandQueuePauseEnable.Define(this)
                .WithTag("CQPEN", 0, 16)
                .WithReservedBits(16, 16)
                ;

            Registers.CommandQueueCurrentIndexValue.Define(this)
                .WithTag("CQCURIDX", 0, 8)
                .WithReservedBits(8, 24)
                ;

            Registers.CommandQueueEndIndexValue.Define(this)
                .WithTag("CQENDIDX", 0, 8)
                .WithReservedBits(8, 24)
                ;

            Registers.IOModuleStatus.Define(this)
                .WithTaggedFlag("ERR", 0)
                .WithFlag(1, FieldMode.Read, name: "CMDACT", valueProviderCallback: _ => status == Status.Active)
                .WithFlag(2, FieldMode.Read, name: "IDLEST", valueProviderCallback: _ => status == Status.Idle)
                .WithReservedBits(3, 29)
                ;

            Registers.SpiModuleMasterConfiguration.Define(this, 0x00200000)
                .WithTaggedFlag("SPOL", 0)
                .WithTaggedFlag("SPHA", 1)
                .WithTaggedFlag("FULLDUP", 2)
                .WithReservedBits(3, 13)
                .WithTaggedFlag("WTFC", 16)
                .WithTaggedFlag("RDFC", 17)
                .WithTaggedFlag("MOSIINV", 18)
                .WithReservedBits(19, 1)
                .WithTaggedFlag("WTFCIRQ", 20)
                .WithTaggedFlag("WTFCPOL", 21)
                .WithTaggedFlag("RDFCPOL", 22)
                .WithTaggedFlag("SPILSB", 23)
                .WithTag("DINDLY", 24, 3)
                .WithTag("DOUTDLY", 27, 3)
                .WithTaggedFlag("MSPIRST", 30)
                .WithReservedBits(31, 1)
                ;

            // Some software expects values written to
            // SDADLY, SCLENDLY and SDAENDLY to be retined
            Registers.I2CMasterConfiguration.Define(this)
                .WithFlag(0, out i2cExtendedAdressingMode, name: "ADDRSZ")
                .WithTaggedFlag("I2CLSB", 1)
                .WithTaggedFlag("ARBEN", 2)
                .WithReservedBits(3, 1)
                .WithValueField(4, 2, name: "SDADLY")
                .WithFlag(6, name: "MI2CRST")
                .WithReservedBits(7, 1)
                .WithValueField(8, 4, name: "SCLENDLY")
                .WithValueField(12, 4, name: "SDAENDLY")
                .WithTag("SMPCNT", 16, 8)
                .WithTaggedFlag("STRDIS", 24)
                .WithReservedBits(25, 7)
                ;

            Registers.I2CDeviceConfiguration.Define(this)
                .WithValueField(0, 10, name: "DEVADDR",
                    valueProviderCallback: _ => i2cSlaveAddress,
                    writeCallback: (_, value) =>
                    {
                        if(!i2cExtendedAdressingMode.Value && value > 0x7F)
                        {
                            value &= 0x7F;
                            this.Log(LogLevel.Warning, "Tried to set 10-bit address with extended mode disabled; truncated to 7-bit");
                        }
                        i2cSlaveAddress = (uint)value;
                    })
                .WithReservedBits(10, 22)
                ;

            Registers.I2SControl.Define(this)
                .WithTaggedFlag("I2SEN", 0)
                .WithTaggedFlag("RXTXN", 1)
                .WithTaggedFlag("CLKMS", 2)
                .WithTaggedFlag("SE", 3)
                .WithTag("CHANSIZE", 4, 5)
                .WithTag("SAMPLESIZE", 9, 5)
                .WithTag("BOFFSET", 14, 5)
                .WithTag("CHANCNT", 19, 3)
                .WithTaggedFlag("LSBFIRST", 22)
                .WithTaggedFlag("CLKGAP", 23)
                .WithTag("CTRLSPARE", 24, 8)
                ;

            Registers.I2SClockControl.Define(this)
                .WithTaggedFlag("ASRCEN", 0)
                .WithTaggedFlag("ASRCCLKSEL", 1)
                .WithTag("I2SCLKSEL", 2, 2)
                .WithTag("ASEL", 4, 3)
                .WithReservedBits(7, 25)
                ;

            Registers.I2SFrameSyncControl.Define(this)
                .WithTag("FSLEN", 0, 5)
                .WithTaggedFlag("FSPOL", 5)
                .WithTaggedFlag("FSEDGE", 6)
                .WithReservedBits(7, 1)
                .WithTag("FSOFFSET", 8, 4)
                .WithReservedBits(12, 20)
                ;

            Registers.IOModuleDebug.Define(this)
                .WithTaggedFlag("DBGEN", 0)
                .WithTaggedFlag("IOCLKON", 1)
                .WithTaggedFlag("APBCLKON", 2)
                .WithTag("DBGDATA", 3, 29)
                ;
        }

        private void IncomingFifoCountChangeAction(Fifo fifo, uint currentCount, uint previousCount)
        {
            // Ignore change in count if it didn't decrease
            if(currentCount >= previousCount)
            {
                return;
            }

            // Receive more data if there's a space to receive and Read command awaits.
            if(!fifo.Full && activeTransactionCommand.Value == Commands.Read && activeTransactionSizeLeft.Value > 0)
            {
                if(fifo.TryReceiveAndPush(ReceiveData))
                {
                    this.Log(LogLevel.Noisy, "Unfinished read command found and incoming FIFO has a space; receiving...");
                }
            }
            UpdateFifoThresholdInterruptStatus();
        }

        private void InterruptStatusSet(IoMasterInterrupts interrupt, bool value = true)
        {
            ioMasterInterruptsStatusFlags[(int)interrupt].Value = value;
            UpdateIRQ();
        }

        private bool IsTransactionValid(Commands command, uint size, uint offsetCount, int spiSlaveSelect, out string errorMessage)
        {
            errorMessage = null;
            if(command != Commands.Read && command != Commands.Write)
            {
                errorMessage = $"Unsupported transaction command: {command}";
            }
            else if(command == Commands.Read && size == 0)
            {
                errorMessage = "Read transaction with size 0 is illegal.";
            }
            else if(command == Commands.Write && size != 0 && outgoingFifo.Empty)
            {
                errorMessage = $"{size}-byte write requested but the outgoing FIFO is empty.";
            }
            else if(offsetCount > 5)
            {
                errorMessage = $"Invalid transaction offset count: {offsetCount}";
            }
            else if(spiMasterEnabled.Value && !spiPeripherals.ContainsKey(spiSlaveSelect))
            {
                errorMessage = $"Transaction cannot be completed. There's no SPI peripheral registered with ID: {spiSlaveSelect}";
            }
            else if(i2cMasterEnabled.Value && !i2cPeripherals.ContainsKey((int)i2cSlaveAddress))
            {
                errorMessage = $"Transaction cannot be completed. There's no I2C peripheral registered with ID: {i2cSlaveAddress}";
            }
            return errorMessage == null;
        }

        private void OutgoingFifoCountChangeAction(Fifo fifo, uint currentCount, uint previousCount)
        {
            // Ignore if we are currently sending data
            if(currentCount <= previousCount)
            {
                return;
            }

            // Send more data if there's data to send and Write command awaits.
            if(!fifo.Empty && activeTransactionCommand.Value == Commands.Write && activeTransactionSizeLeft.Value > 0)
            {
                if(fifo.TryPop(out var value))
                {
                    this.Log(LogLevel.Noisy, "Unfinished write command found and outgoing FIFO contains data; sending 0x{0:X}...", value);
                    SendData(value);
                }
            }
            UpdateFifoThresholdInterruptStatus();
        }

        private uint ReceiveData()
        {
            if(activeTransactionSizeLeft.Value > 0)
            {
                var bytesToReceive = Math.Min(4, (uint)activeTransactionSizeLeft.Value);
                uint result = 0;
                if(ActiveTransactionPeripheral is ISPIPeripheral spiPeripheral)
                {
                    for(int i = 0; i < bytesToReceive; i++)
                    {
                        BitHelper.UpdateWithShifted(ref result, spiPeripheral.Transmit(0), (int)(i * 8), 8);
                    }
                }
                else if(ActiveTransactionPeripheral is II2CPeripheral i2cPeripheral)
                {
                    var data = i2cPeripheral.Read((int)bytesToReceive);
                    foreach(var item in data.Select((value, index) => new { index, value }))
                    {
                        BitHelper.UpdateWithShifted(ref result, item.value, (int)(item.index * 8), 8);
                    }
                }
                else
                {
                    // This code should be unreachable
                    throw new ArgumentException("Peripheral has to be selected before receiving data!");
                }
                activeTransactionSizeLeft.Value -= bytesToReceive;
                TryFinishTransaction();
                return result;
            }
            else
            {
                throw new ArgumentException($"Data shouldn't be received if activeTransactionSizeLeft equals 0!");
            }
        }

        private void Send(uint data, uint size, bool forceMSBFirst = false)
        {
            if(ActiveTransactionPeripheral is ISPIPeripheral spiPeripheral)
            {
                var dataBytes = BitHelper.GetBytesFromValue(data, (int)size, reverse: !forceMSBFirst);
                foreach(var dataByte in dataBytes)
                {
                    spiPeripheral.Transmit(dataByte);
                    this.Log(LogLevel.Noisy, "Byte sent to the SPI peripheral: 0x{0:X}", dataByte);
                }
            }
            else if(ActiveTransactionPeripheral is II2CPeripheral i2cPeripheral)
            {
                var dataBytes = BitHelper.GetBytesFromValue(data, (int)size, reverse: !forceMSBFirst);
                i2cPeripheral.Write(dataBytes);
                this.Log(LogLevel.Noisy, "{0} byte(s) sent to the I2C peripheral: 0x{0:X08}", size, data);
            }
            else
            {
                // This code should be unreachable
                throw new ArgumentException("Peripheral has to be selected before sending data!");
            }
        }

        private void SendData(uint value)
        {
            if(activeTransactionSizeLeft.Value > 0)
            {
                var bytesToSend = Math.Min(4, (uint)activeTransactionSizeLeft.Value);
                Send(value, bytesToSend);
                activeTransactionSizeLeft.Value -= bytesToSend;
                TryFinishTransaction();
            }
            else
            {
                throw new ArgumentException("Data shouldn't be sent if activeTransactionSizeLeft equals 0!");
            }
        }

        private void SendTransactionOffset(uint count)
        {
            // Depending on the offset count:
            // * for high=0xDEADBEEF, low=0x12: count=1 sends only 0x12, count=2: 0xEF12...
            // * transfer always begins with the MSB of the resulting value (0xEF for the count=2 example).
            if(count > 0)
            {
                if(count > 1)
                {
                    Send((uint)transactionOffsetHigh.Value, count - 1, forceMSBFirst: true);
                }
                Send((uint)transactionOffsetLow.Value, 1);
            }
        }

        private bool TryFinishTransaction()
        {
            if(activeTransactionSizeLeft.Value == 0)
            {
                this.Log(LogLevel.Noisy, "Command completed: {0}", activeTransactionCommand.Value);
                if(activeTransactionContinue)
                {
                    this.Log(LogLevel.Noisy, "The transmission won't be finished; the CONT flag was sent with the command.");
                }
                else
                {
                    if(ActiveTransactionPeripheral is ISPIPeripheral spiPeripheral)
                    {
                        spiPeripheral.FinishTransmission();
                    }
                    else if(ActiveTransactionPeripheral is II2CPeripheral i2cPeripheral)
                    {
                        i2cPeripheral.FinishTransmission();
                    }
                    else
                    {
                        // This code should be unreachable
                        throw new ArgumentException("Trying to finish transaction for which peripherial wasn't chosen");
                    }
                }
                activeTransactionCommand.Value = Commands.None;

                // Not sure if these are valid for the continuous transmission.
                activeTransactionStatus.Value = Status.Idle;
                status = Status.Idle;
                InterruptStatusSet(IoMasterInterrupts.CommandComplete);

                return true;
            }
            return false;
        }

        private void UpdateFifoThresholdInterruptStatus()
        {
            InterruptStatusSet(IoMasterInterrupts.FifoThreshold, value:
                outgoingFifo.BytesCount < fifoInterruptWriteThreshold.Value
                || incomingFifo.BytesCount > fifoInterruptReadThreshold.Value
            );
        }

        private void UpdateIRQ()
        {
            var newIrqState = false;
            for(var i = 0; i < IoMasterInterruptsCount; i++)
            {
                if(ioMasterInterruptsEnableFlags[i].Value && ioMasterInterruptsStatusFlags[i].Value)
                {
                    newIrqState = true;
                    break;
                }
            }

            if(newIrqState != IRQ.IsSet)
            {
                this.Log(LogLevel.Debug, "{0} IRQ", newIrqState ? "Setting" : "Resetting");
                IRQ.Set(newIrqState);
            }
        }

        private void Register<T>(Dictionary<int, T> container, T peripheral, TypedNumberRegistrationPoint<int> registrationPoint) where T : IPeripheral
        {
            if(container.ContainsKey(registrationPoint.Address))
            {
                throw new RegistrationException("The specified registration point is already in use.");
            }
            container.Add(registrationPoint.Address, peripheral);
            machine.RegisterAsAChildOf(this, peripheral, registrationPoint);
        }

        private void Unregister<T>(Dictionary<int, T> container, T peripheral) where T : IPeripheral
        {
            var toRemove = container.Where(x => x.Value.Equals(peripheral)).Select(x => x.Key).ToList(); //ToList required, as we remove from the source
            if(toRemove.Count == 0)
            {
                throw new RegistrationException("The specified peripheral was never registered.");
            }
            foreach(var key in toRemove)
            {
                container.Remove(key);
            }
            machine.UnregisterAsAChildOf(this, peripheral);
        }

        private string PrettyPendingPeripheral
        {
            get
            {
                if(spiMasterEnabled.Value)
                {
                    return $"SPI#{spiSlaveSelect.Value}";
                }
                else if(i2cMasterEnabled.Value)
                {
                    return $"I2C#{i2cSlaveAddress}";
                }
                return String.Empty;
            }
        }

        private string PrettyActivePeripheral
        {
            get
            {
                if(spiMasterEnabled.Value)
                {
                    return $"SPI#{activeSpiSlaveSelect}";
                }
                else if(i2cMasterEnabled.Value)
                {
                    return $"I2C#{i2cSlaveAddress}";
                }
                return String.Empty;
            }
        }

        private IPeripheral ActiveTransactionPeripheral
        {
            get
            {
                if(activeTransactionCommand.Value == Commands.None)
                {
                    return null;
                }
                else if(spiMasterEnabled.Value)
                {
                    return spiPeripherals[activeSpiSlaveSelect];
                }
                else if(i2cMasterEnabled.Value)
                {
                    return i2cPeripherals[(int)i2cSlaveAddress];
                }
                return null;
            }
        }

        private IEnumRegisterField<Commands> activeTransactionCommand;
        private IValueRegisterField activeTransactionSizeLeft;
        private IEnumRegisterField<Status> activeTransactionStatus;
        private IValueRegisterField fifoInterruptReadThreshold;
        private IValueRegisterField fifoInterruptWriteThreshold;
        private IFlagRegisterField[] ioMasterInterruptsEnableFlags;
        private IFlagRegisterField[] ioMasterInterruptsStatusFlags;
        private IFlagRegisterField spiMasterEnabled;
        private IFlagRegisterField i2cMasterEnabled;
        private IEnumRegisterField<Commands> transactionCommand;
        private IFlagRegisterField transactionContinue;
        private IValueRegisterField transactionOffsetCount;
        private IValueRegisterField transactionOffsetHigh;
        private IValueRegisterField transactionOffsetLow;
        private IValueRegisterField transactionSize;
        private IValueRegisterField spiSlaveSelect;
        private IFlagRegisterField writePopToAdvanceReadPointer;
        private IFlagRegisterField i2cExtendedAdressingMode;

        private bool activeTransactionContinue;
        private int activeSpiSlaveSelect;
        private uint i2cSlaveAddress;
        private Status status;

        /*
            Both FIFOs occupy a single 64-byte memory:
            * 0x00 -- 0x1F outgoingFifo: "FIFO 0 (written by MCU, read by interface)",
            * 0x20 -- 0x3F incomingFifo: "FIFO 1 (written by interface, read by MCU)"
            Queues aren't used because random access is also needed.
        */
        private readonly Fifo incomingFifo;
        private readonly Fifo outgoingFifo;
        private readonly Dictionary<int, ISPIPeripheral> spiPeripherals;
        private readonly Dictionary<int, II2CPeripheral> i2cPeripherals;
        private readonly IMachine machine;

        private const int IoMasterInterruptsCount = 15;
        private const int MaxSpiPeripheralsConnected = 4;

        private class Fifo
        {
            public Fifo(string name, IPeripheral owner)
            {
                this.name = name;
                this.owner = owner;
                Reset();
            }

            public uint DirectGet(uint index)
            {
                if(CheckResetFlag("get"))
                {
                    return memory[index];
                }
                return 0x0;
            }

            public void DirectSet(uint index, uint value)
            {
                if(CheckResetFlag("set"))
                {
                    memory[index] = value;
                }
            }

            public void Reset()
            {
                SoftwareReset();
                resetFlag = false;
            }

            public override string ToString()
            {
                StringBuilder builder = new StringBuilder();
                builder.AppendFormat("{0}: ", name);
                builder.AppendFormat("Count: {0}; values: ", Count, headIndex, tailIndex);
                for(int index = headIndex; index < headIndex + Count; index++)
                {
                    builder.AppendFormat("0x{0:X8} ", memory[index % DoubleWordCapacity]);
                }
                return builder.ToString();
            }

            public bool TryAdvancePointer()
            {
                if(CheckResetFlag("advance the pointer") && Check(!Empty, "Cannot advance the pointer; FIFO is empty."))
                {
                    // Clear the current head. It won't be read with Peek/Pop without a prior
                    // setting it with Push but it could be read with a random access.
                    memory[headIndex] = 0x0;

                    headIndex = (headIndex + 1) % DoubleWordCapacity;
                    Count--;
                    return true;
                }
                return false;
            }

            public bool TryPeek(out uint value, string actionName = "peek")
            {
                if(CheckResetFlag(actionName) && Check(!Empty, $"Cannot {actionName}; FIFO is empty."))
                {
                    value = memory[headIndex];
                    return true;
                }
                value = 0x0;
                return false;
            }

            public bool TryPop(out uint value)
            {
                if(TryPeek(out value, actionName: "pop"))
                {
                    TryAdvancePointer();
                    return true;
                }
                return false;
            }

            public bool TryPush(uint value)
            {
                return TryReceiveAndPush(() => value);
            }

            // To prevent losing the received value, the receiveFunction will only be called if push is possible.
            public bool TryReceiveAndPush(Func<uint> receiveFunction)
            {
                if(CheckResetFlag("push") && Check(!Full, "Cannot push; FIFO is full."))
                {
                    Push(receiveFunction());
                    return true;
                }
                return false;
            }

            public Action<Fifo, uint, uint> CountChangeAction { get; set; }

            public uint BytesCapacity => DoubleWordCapacity * 4;

            public uint BytesCount => Count * 4;

            public uint BytesLeft => (DoubleWordCapacity * 4) - BytesCount;

            public bool Empty => Count == 0;

            public bool Full => Count == DoubleWordCapacity;

            public uint Pointer => (uint)headIndex;

            public bool ResetFlag
            {
                get => resetFlag;
                set
                {
                    if(!resetFlag && value)
                    {
                        SoftwareReset();
                    }
                    resetFlag = value;
                }
            }

            private bool Check(bool condition, string errorMessage)
            {
                if(!condition)
                {
                    owner.DebugLog("{0}: {1}", name, errorMessage);
                    return false;
                }
                return true;
            }

            private bool CheckResetFlag(string actionName)
            {
                return Check(!resetFlag, $"Cannot {actionName}; the reset flag is set.");
            }

            private void ClearMemory()
            {
                for(int i = 0; i < DoubleWordCapacity; i++)
                {
                    memory[i] = 0x0;
                }
            }

            private void Push(uint value)
            {
                if(Full)
                {
                    throw new ArgumentException($"Cannot push; the {name} is full!");
                }
                tailIndex = (tailIndex + 1) % DoubleWordCapacity;
                memory[tailIndex] = value;
                Count++;
            }

            private void SoftwareReset()
            {
                ClearMemory();
                Count = 0;
                headIndex = 0;
                tailIndex = -1;
            }

            private uint Count
            {
                get => count;
                set
                {
                    if(value < 0 || value > DoubleWordCapacity)
                    {
                        throw new ArgumentException($"{name}: Invalid value for Count: {value} (Capacity: {DoubleWordCapacity})");
                    }
                    var previousCount = count;
                    count = value;
                    CountChangeAction?.Invoke(this, count, previousCount);
                }
            }

            private uint count;
            private int headIndex;
            private bool resetFlag;
            private int tailIndex = -1;

            private readonly uint[] memory = new uint[DoubleWordCapacity];
            private readonly string name;
            private readonly IPeripheral owner;

            private const int DoubleWordCapacity = 8;
        }

        private enum Commands
        {
            None = 0x0,
            Write = 0x1,
            Read = 0x2,
            TestModeWrite = 0x3,
            TestModeRead = 0x4,
        }

        private enum Status
        {
            Error = 0x1,
            Active = 0x2,
            Idle = 0x4,
            Wait = 0x6,
        }

        private enum IoMasterInterrupts
        {
            CommandComplete,
            FifoThreshold,
            ReadFifoUnderflow,
            WriteFifoOverflow,
            I2CNak,
            IllegalFifoAccess,
            IllegalCommand,
            StartCommand,
            StopCommand,
            ArbitrationLoss,
            DmaComplete,
            DmaError,
            CommandQueuePaused,
            // No sure what "UPD" means here. This is the full description:
            // "CQ write operation performed a register write with the register address bit 0 set to 1.
            // The low address bits in the CQ address fields are unused and bit 0 can be used to trigger
            // an interrupt to indicate when this register write is performed by the CQ operation."
            CommandQueueUPD,
            CommandQueueError,
        }

        private enum Registers : long
        {
            OutgoingFifoAccessPort = 0x0,
            IncomingFifoAccessPort = 0x20,
            FifoSizeAndRemainingSlotsOpenValues = 0x100,
            FifoThresholdConfiguration = 0x104,
            FifoPop = 0x108,
            FifoPush = 0x10C,
            FifoControl = 0x110,
            FifoPointers = 0x114,
            IOClockConfiguration = 0x118,
            SubmoduleControl = 0x11C,
            CommandAndOffset = 0x120,
            DcxControlAndCeUsageSelection = 0x124,
            HighOrderBytesBfOffsetForIOTransaction = 0x128,
            CommandStatus = 0x12C,
            IOMasterInterruptsEnable = 0x200,
            IOMasterInterruptsStatus = 0x204,
            IOMasterInterruptsClear = 0x208,
            IOMasterInterruptsSet = 0x20C,
            DmaTriggerEnable = 0x210,
            DmaTriggerStatus = 0x214,
            DmaConfiguration = 0x218,
            DmaTotalTransferCount = 0x21C,
            DmaTargetAddress = 0x220,
            DmaStatus = 0x224,
            CommandQueueConfiguration = 0x228,
            CommandQueueTargetReadAddress = 0x22C,
            CommandQueueStatus = 0x230,
            CommandQueueFlag = 0x234,
            CommandQueueFlagSetClear = 0x238,
            CommandQueuePauseEnable = 0x23C,
            CommandQueueCurrentIndexValue = 0x240,
            CommandQueueEndIndexValue = 0x244,
            IOModuleStatus = 0x248,
            SpiModuleMasterConfiguration = 0x280,
            I2CMasterConfiguration = 0x2C0,
            I2CDeviceConfiguration = 0x2C4,
            I2SControl = 0x300,
            I2SClockControl = 0x304,
            I2SFrameSyncControl = 0x308,
            IOModuleDebug = 0x388,
        }

        private enum SubmoduleTypes : uint
        {
            SpiMaster = 0x0,
            I2CMaster = 0x1,
            SpiSlave = 0x2,
            I2CSlave = 0x3,
            I2SMaster_Slave = 0x4,
            NotInstalled = 0x7,
        }
    }
}
namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    // Functional CQ for software/index pause inputs; external flag inputs and timing are unsupported.
    public sealed class BlackwallIomCommandQueue
    {
        public BlackwallIomCommandQueue(ulong baseAddress,System.Func<uint,uint> readMemory,System.Action<long,uint> writeRegister,System.Action<uint> interrupt,System.Action<long,string,uint> block,int inputLevels=-1)
        { if(inputLevels < -1 || inputLevels>31) throw new System.ArgumentException("CQ input levels must be unknown(-1) or a five-bit mock vector"); InputLevels=inputLevels; this.baseAddress=baseAddress; this.readMemory=readMemory; this.writeRegister=writeRegister; this.interrupt=interrupt; this.block=block; Reset(); }
        public void Reset() { ClearRegisters(); Pairs=0; LastPairAddress=LastTarget=LastData=0; LastError="none"; }
        public void PowerDown() { ClearRegisters(); }
        private void ClearRegisters() { Configuration=Address=SoftwareFlags=CurrentIndex=EndIndex=PauseEnable=IrqMask=0; Paused=running=pauseSignal=false; addressRevision=0; }
        public bool Enabled => (Configuration&1)!=0;
        public uint Status => Enabled ? 1u|(Paused?2u:0u) : 0u;
        public uint KnownFlags => SoftwareFlags|(CurrentIndex==EndIndex ? 0x8000u:0u);
        public int InputLevels {get;}
        public uint AvailableFlagsMask => InputLevels<0 ? 0x80ffu:0xffffu;
        public uint EffectiveFlags
        {
            get
            {
                if(InputLevels<0) return KnownFlags;
                return FlagsForInputLevels(InputLevels);
            }
        }
        public uint FlagsForInputLevels(int levels)
        {
            if(levels<0 || levels>31)throw new System.ArgumentException("Five-bit CQ representative vector required");
            var x0=((uint)levels^SoftwareFlags)&1u;
            var x1=(((uint)levels^SoftwareFlags)>>1)&1u;
            return KnownFlags|(x0<<8)|(x1<<9)|((x0^1u)<<10)|((x1^1u)<<11)|((((uint)levels^SoftwareFlags)&0x1cu)<<10);
        }
        public static bool Owns(long offset) => offset>=0x228 && offset<=0x244 && (offset&3)==0;
        private static bool ValidSource(uint address) => (address&3)==0 && address>=0x20000000u && (ulong)address+8<=0x20380000ul;
        private void Fail(long offset,string reason,uint value=0) { LastError=reason; block(offset,"cq-"+reason,value); }
        public uint Read(long offset)
        {
            switch(offset)
            {
            case 0x228:return Configuration;case 0x22c:return Address;case 0x230:return Status;
            case 0x23c:return PauseEnable;case 0x240:return CurrentIndex;case 0x244:return EndIndex;
            case 0x234:if(InputLevels<0) { Fail(offset,"external-flags-unknown");return 0; } return EffectiveFlags|(IrqMask<<16);
            case 0x238:Fail(offset,"command-readback-unknown");return 0;
            default:Fail(offset,"unknown-read");return 0;
            }
        }
        public void Write(long offset,uint value)
        {
            switch(offset)
            {
            case 0x228:
                if((value&~3u)!=0) { Fail(offset,"external-selector",value);return; }
                if((value&1)!=0 && !ValidSource(Address)) { Fail(offset,"fetch-range",Address);return; }
                Configuration=value;
                if(!Enabled) { Paused=false;pauseSignal=false; }
                break;
            case 0x22c:
                if(!ValidSource(value) && !(value==0 && !Enabled)) { Fail(offset,"fetch-range",value);return; }
                Address=value;addressRevision++;break;
            case 0x230:Fail(offset,"status-read-only",value);return;
            case 0x234:
                if(((value>>16)&~AvailableFlagsMask)!=0) { Fail(offset,"irq-mask-unknown",value);return; }
                IrqMask=value>>16;break;
            case 0x238:
                var set=value&255;var toggle=(value>>8)&255;var clear=(value>>16)&255;
                if((set&toggle)!=0 || (set&clear)!=0 || (toggle&clear)!=0 || (value&0xff000000)!=0) { Fail(offset,"flag-overlap",value);return; }
                SoftwareFlags=((SoftwareFlags|set)^toggle)&~clear;break;
            case 0x23c:
                if((value&~AvailableFlagsMask)!=0) { Fail(offset,"pause-input-unknown",value);return; }
                PauseEnable=value;break;
            case 0x240:
                if(value>255) { Fail(offset,"index-width",value);return; }
                CurrentIndex=value;break;
            case 0x244:
                if(value>255) { Fail(offset,"index-width",value);return; }
                EndIndex=value;break;
            default:Fail(offset,"unknown-write",value);return;
            }
            Pump();
        }
        private void SetPaused(bool paused)
        {
            Paused=paused;
            var signal=Enabled && paused && (EffectiveFlags&PauseEnable&IrqMask)!=0;
            if(signal && !pauseSignal) interrupt(1u<<12);
            pauseSignal=signal;
        }
        private void Pump()
        {
            if(running || !Enabled) return;
            running=true;
            try
            {
                int steps=0;
                while(Enabled)
                {
                    if((EffectiveFlags&PauseEnable)!=0) { SetPaused(true);return; }
                    SetPaused(false);
                    if(steps>=4096) { Fail(0x228,"model-pair-budget",Address);return; }
                    if(!ValidSource(Address)) { Fail(0x22c,"fetch-range",Address);return; }
                    var source=Address;
                    var encodedTarget=readMemory(source);var data=readMemory(source+4);
                    var target=encodedTarget&~1u;
                    LastPairAddress=source;LastTarget=target;LastData=data;
                    if((target&3)!=0 || (ulong)target<baseAddress || (ulong)target>=baseAddress+0x400)
                    { Fail(0x228,"foreign-target",encodedTarget);return; }
                    var revision=addressRevision;
                    try { writeRegister((long)((ulong)target-baseAddress),data); }
                    catch { LastError="target-write-blocked";throw; }
                    if(revision==addressRevision) Address=source+8;
                    Pairs++;steps++;
                    if((encodedTarget&1)!=0) interrupt(1u<<13);
                }
                SetPaused(false);
            }
            finally { running=false; }
        }
        public uint Configuration {get;private set;}
        public uint Address {get;private set;}
        public uint SoftwareFlags {get;private set;}
        public uint CurrentIndex {get;private set;}
        public uint EndIndex {get;private set;}
        public uint PauseEnable {get;private set;}
        public uint IrqMask {get;private set;}
        public bool Paused {get;private set;}
        public long Pairs {get;private set;}
        public uint LastPairAddress {get;private set;}
        public uint LastTarget {get;private set;}
        public uint LastData {get;private set;}
        public string LastError {get;private set;}
        private bool running,pauseSignal;
        private ulong addressRevision;
        private readonly ulong baseAddress;
        private readonly System.Func<uint,uint> readMemory;
        private readonly System.Action<long,uint> writeRegister;
        private readonly System.Action<uint> interrupt;
        private readonly System.Action<long,string,uint> block;
    }
}

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
        public BlackwallStrictIom(IMachine machine, BlackwallPeripheralPower power, int module=2,int cqInputLevels=-1,bool spiConfigStorage=false,long cqStartupRetentionPc=-1,bool spiDcxNoPinsStorage=false,bool spiFullDuplexPreflight=false,IBlackwallCheckedSpiPeer spiWordPeer=null,int cqStartupRetentionBudget=1,bool cqRetentionPerDisable=false,bool spiReceiveStreaming=false):base(machine)
        {
            if(module<0 || module>7 || power==null || power.Mask!=(1u<<(module+1))) throw new System.ArgumentException("IOM module/power mismatch");
            if(spiDcxNoPinsStorage && (module!=6 || !spiConfigStorage))throw new System.ArgumentException("DCX without CE routing requires explicit IOM6 SPI storage profile");
            if(spiFullDuplexPreflight && (module!=6 || !spiConfigStorage || !spiDcxNoPinsStorage))throw new System.ArgumentException("Full-duplex preflight requires explicit IOM6 SPI and no-pin DCX profiles");
            if(spiWordPeer!=null && !spiFullDuplexPreflight)throw new System.ArgumentException("SPI word transfer requires the explicit IOM6 full-duplex profile");
            if(spiReceiveStreaming && (module!=6 || !(spiWordPeer is IBlackwallReceiveSpiPeer)))throw new System.ArgumentException("Receive streaming requires an explicit IOM6 receive peer");
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
        public new void Reset() { base.Reset(); SpiWordTransfer?.Reset(); CommandQueue?.Reset(); DmaTrigger=0; RetentionSnapshotReads=RetentionEpoch=0;LastRetentionEpoch=-1;LastRetentionFlags=0; clock=i2cConfig=dcx=0; spiConfig=0x00200000; fifo=2; Reads=Writes=Commands=PowerDowns=AccessCount=I2CConfigurationWrites=0; LastI2CConfiguration=0; LastAddress=LastValue=0; LastWidth=0; LastOperation="none"; }
        private void PowerDown() { base.Reset(); SpiWordTransfer?.Reset(); CommandQueue.PowerDown(); DmaTrigger=0; clock=i2cConfig=dcx=0; spiConfig=0x00200000; fifo=2; PowerDowns++; }
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

//
// Copyright (c) 2010-2023 Antmicro
//
// This file is licensed under the MIT License.
// Full license text is available in 'licenses/MIT.txt'.
//
namespace Antmicro.Renode.Peripherals.Timers
{
using System;

using Antmicro.Renode.Core;
using Antmicro.Renode.Core.Structure.Registers;
using Antmicro.Renode.Exceptions;
using Antmicro.Renode.Logging;
using Antmicro.Renode.Peripherals.Bus;
using Antmicro.Renode.Time;
using Antmicro.Renode.Utilities;

    [AllowedTranslations(AllowedTranslation.ByteToDoubleWord | AllowedTranslation.WordToDoubleWord)]
    public class BlackwallRtcEngine : BasicDoubleWordPeripheral, IKnownSize
    {
        public BlackwallRtcEngine(IMachine machine) : base(machine)
        {
            IRQ = new GPIO();
            // Blackwall supplies a fixed virtual epoch; ignore machine wall-clock mode events.

            var baseDateTime = Misc.UnixEpoch;
            internalTimer = new RTCTimer(machine, this, baseDateTime, alarmAction: () => InterruptStatus = true);

            DefineRegisters();
            Reset();
        }

        public override uint ReadDoubleWord(long offset)
        {
            if(offset == (long)Registers.CountersLower || offset == (long)Registers.CountersUpper)
            {
                // Cannot be done in read callback because field values are established first.
                UpdateCounterFields();
            }

            return base.ReadDoubleWord(offset);
        }

        public override void Reset()
        {
            interruptStatus = false;
            lastUpdateTimerValue = ulong.MaxValue;
            writeBusy = false;
            valueReadWithCountersLower = 0;

            InitializeBCDValueFields();
            IRQ.Unset();
            internalTimer.Reset();

            base.Reset();

            SetDateTimeFromMachine();
        }

        public override void WriteDoubleWord(long offset, uint value)
        {
            if(!counterWritesEnabled.Value &&
                (offset == (long)Registers.CountersLower || offset == (long)Registers.CountersUpper))
            {
                this.Log(LogLevel.Warning, "The {0} register ({1}) cannot be written to; WRTC isn't set!", (Registers)offset, offset);
                return;
            }

            base.WriteDoubleWord(offset, value);
        }

        public string PrintNextAlarmDateTime()
        {
            return internalTimer.IsAlarmSet() ? internalTimer.GetNextAlarmDateTime().ToString("o") : "Alarm not set.";
        }

        public string PrintPreciseCurrentDateTime()
        {
            return CurrentDateTime.ToString("o");
        }

        public void SetDateTime(int? year = null, int? month = null, int? day = null, int? hours = null, int? minutes = null, int? seconds = null, int? secondHundredths = null)
        {
            UpdateCounterFields();

            if(year == null)
            {
                year = CalculateYear(centuryBit.Value, yearsOfCentury);
            }
            else
            {
                // The 200 years range simply makes it possible to tell a specific year from the century bit and a two-digit year.
                if(year < 1970 || year > 2169)
                {
                    throw new RecoverableException("Year has to be in range: 1970 .. 2169.");
                }
            }

            try
            {
                SetDateTimeInternal(new DateTime(
                    year.Value,
                    month ?? this.month,
                    day ?? this.day,
                    hours ?? this.hours,
                    minutes ?? this.minutes,
                    seconds ?? this.seconds,
                    (secondHundredths ?? this.secondHundredths) * 10));
            }
            catch(ArgumentOutOfRangeException)
            {
                throw new RecoverableException("Provided date or time is invalid.");
            }
        }

        public void SetDateTimeFromMachine()
        {
            // Normally the warning is logged if the millisecond value isn't a multiple of 10 since that's an RTC
            // precision. It doesn't make sense to log such a warning for the value taken from the machine.
            SetDateTimeInternal(machine.RealTimeClockDateTime, hushPrecisionWarning: true);
        }

        public DateTime CurrentDateTime => internalTimer.GetCurrentDateTime();

        public GPIO IRQ { get; }

        public long Size => 0x210;

        private static int CalculateYear(bool centuryBit, int yearsOfCentury)
        {
            // The century bit set indicates "1900s/2100s" according to the documentation.
            // To make it specific, the range supported has to be 200 years. The arbitrarily chosen range is 1970-2169
            // because of the default Machine's RTC Mode, 'Epoch', which starts in 1970. Hence the century bit set
            // translates to 1900 only if a two-digit year number ('yearsOfCentury') is >= 70 and to 2100 otherwise.
            if(centuryBit)
            {
                return (yearsOfCentury < 70 ? 2100 : 1900) + yearsOfCentury;
            }
            else
            {
                return 2000 + yearsOfCentury;
            }
        }

        private void DefineRegisters()
        {
            Registers.AlarmsLower.Define(this)
                .WithValueField(0, 8, name: "ALM100", writeCallback: (_, newValue) => alarmSecondHundredths.BCDSet((byte)newValue), valueProviderCallback: _ => alarmSecondHundredths.BCDGet())
                .WithValueField(8, 7, name: "ALMSEC", writeCallback: (_, newValue) => alarmSeconds.BCDSet((byte)newValue), valueProviderCallback: _ => alarmSeconds.BCDGet())
                .WithReservedBits(15, 1)
                .WithValueField(16, 7, name: "ALMMIN", writeCallback: (_, newValue) => alarmMinutes.BCDSet((byte)newValue), valueProviderCallback: _ => alarmMinutes.BCDGet())
                .WithReservedBits(23, 1)
                .WithValueField(24, 6, name: "ALMHR", writeCallback: (_, newValue) => alarmHours.BCDSet((byte)newValue), valueProviderCallback: _ => alarmHours.BCDGet())
                .WithReservedBits(30, 2)
                .WithChangeCallback((_, __) => UpdateAlarm())
                ;

            Registers.AlarmsUpper.Define(this)
                .WithValueField(0, 6, name: "ALMDATE", writeCallback: (_, newValue) => alarmDay.BCDSet((byte)newValue), valueProviderCallback: _ => alarmDay.BCDGet())
                .WithReservedBits(6, 2)
                .WithValueField(8, 5, name: "ALMMO", writeCallback: (_, newValue) => alarmMonth.BCDSet((byte)newValue), valueProviderCallback: _ => alarmMonth.BCDGet())
                .WithReservedBits(13, 3)
                .WithValueField(16, 3, name: "ALMWKDY", writeCallback: (_, newValue) => alarmWeekday.BCDSet((byte)newValue), valueProviderCallback: _ => alarmWeekday.BCDGet())
                .WithReservedBits(19, 13)
                .WithChangeCallback((_, __) => UpdateAlarm())
                ;

            Registers.Control.Define(this)
                .WithFlag(0, out counterWritesEnabled, name: "WRTC")
                .WithEnumField(1, 3, out alarmRepeatInterval, name: "RPT", changeCallback: (_, __) => UpdateAlarm())
                .WithFlag(4, name: "RSTOP", writeCallback: (_, newValue) => { internalTimer.Enabled = !newValue; }, valueProviderCallback: _ => !internalTimer.Enabled)
                .WithReservedBits(5, 27)
                ;

            Registers.CountersLower.Define(this)
                .WithValueField(0, 8, name: "CTR100", writeCallback: (_, newValue) => secondHundredths.BCDSet((byte)newValue), valueProviderCallback: _ => secondHundredths.BCDGet())
                .WithValueField(8, 7, name: "CTRSEC", writeCallback: (_, newValue) => seconds.BCDSet((byte)newValue), valueProviderCallback: _ => seconds.BCDGet())
                .WithReservedBits(15, 1)
                .WithValueField(16, 7, name: "CTRMIN", writeCallback: (_, newValue) => minutes.BCDSet((byte)newValue), valueProviderCallback: _ => minutes.BCDGet())
                .WithReservedBits(23, 1)
                .WithValueField(24, 6, name: "CTRHR", writeCallback: (_, newValue) => hours.BCDSet((byte)newValue), valueProviderCallback: _ => hours.BCDGet())
                .WithReservedBits(30, 2)
                .WithReadCallback((_, __) => { valueReadWithCountersLower = internalTimer.Value; readError.Value = false; })
                .WithWriteCallback((_, __) => writeBusy = true)
                ;

            Registers.CountersUpper.Define(this)
                .WithValueField(0, 6, name: "CTRDATE", writeCallback: (_, newValue) => day.BCDSet((byte)newValue), valueProviderCallback: _ => day.BCDGet())
                .WithReservedBits(6, 2)
                .WithValueField(8, 5, name: "CTRMO", writeCallback: (_, newValue) => month.BCDSet((byte)newValue), valueProviderCallback: _ => month.BCDGet())
                .WithReservedBits(13, 3)
                .WithValueField(16, 8, name: "CTRYR", writeCallback: (_, newValue) => yearsOfCentury.BCDSet((byte)newValue), valueProviderCallback: _ => yearsOfCentury.BCDGet())
                .WithValueField(24, 3, name: "CTRWKDY", writeCallback: (_, newValue) => weekday.BCDSet((byte)newValue), valueProviderCallback: _ => weekday.BCDGet())
                .WithReservedBits(27, 1)
                // Documentation on Century Bit set: "Century is 1900s/2100s". In this model the century bit is set for years 1970-1999 and 2100-2169.
                .WithFlag(28, out centuryBit, name: "CB")
                .WithFlag(29, out centuryChangeEnabled, name: "CEB")
                .WithReservedBits(30, 1)
                .WithFlag(31, out readError, name: "CTERR")
                .WithWriteCallback((_, __) =>
                {
                    readError.Value = valueReadWithCountersLower == internalTimer.Value;
                    if(!writeBusy)
                    {
                        this.Log(LogLevel.Warning, "The Counters Upper register written without prior write to the Counters Lower register!", Registers.CountersLower);
                    }
                    writeBusy = false;

                    var year = CalculateYear(centuryBit.Value, yearsOfCentury);
                    var newDateTime = new DateTime(year, month, day, hours, minutes, seconds, secondHundredths * 10);

                    // Check if weekday matches (Sunday is 0 for both).
                    if(weekday != (int)newDateTime.DayOfWeek)
                    {
                        this.Log(LogLevel.Warning, "Weekday given doesn't match the given date! New date's day of week: {0} ({1})", newDateTime.DayOfWeek, (int)newDateTime.DayOfWeek);
                    }

                    SetDateTimeInternal(newDateTime);
                })
                ;

            Registers.InterruptClear.Define(this)
                .WithFlag(0, FieldMode.Write, name: "ALM", writeCallback: (_, newValue) => { if(newValue) InterruptStatus = false; })
                .WithReservedBits(1, 31)
                ;

            Registers.InterruptEnable.Define(this)
                .WithFlag(0, out interruptEnable, name: "ALM", changeCallback: (_, __) => UpdateInterrupt())
                .WithReservedBits(1, 31)
                ;

            Registers.InterruptSet.Define(this)
                .WithFlag(0, FieldMode.Write, name: "ALM", writeCallback: (_, newValue) => { if(newValue) InterruptStatus = true; })
                .WithReservedBits(1, 31)
                ;

            Registers.InterruptStatus.Define(this)
                .WithFlag(0, FieldMode.Read, name: "ALM", valueProviderCallback: _ => InterruptStatus)
                .WithReservedBits(1, 31)
                ;

            Registers.Status.Define(this)
                .WithFlag(0, FieldMode.Read, name: "WRITEBUSY", valueProviderCallback: _ => writeBusy)
                .WithReservedBits(1, 31)
                ;
        }

        private void InitializeBCDValueFields()
        {
            alarmDay = new BCDValueField(this, "days", 0x31, zeroAllowed: false);
            alarmHours = new BCDValueField(this, "hours", 0x23);
            alarmMinutes = new BCDValueField(this, "minutes", 0x59);
            alarmMonth = new BCDValueField(this, "months", 0x12, zeroAllowed: false);
            alarmSeconds = new BCDValueField(this, "seconds", 0x59);
            alarmSecondHundredths = new BCDValueField(this, "hundredths of a second");
            alarmWeekday = new BCDValueField(this, "weekdays", 0x6);
            day = new BCDValueField(this, "days", 0x31, zeroAllowed: false);
            hours = new BCDValueField(this, "hours", 0x23);
            minutes = new BCDValueField(this, "minutes", 0x59);
            month = new BCDValueField(this, "months", 0x12, zeroAllowed: false);
            secondHundredths = new BCDValueField(this, "hundredths of a second");
            seconds = new BCDValueField(this, "seconds", 0x59);
            weekday = new BCDValueField(this, "weekdays", 0x6);
            yearsOfCentury = new BCDValueField(this, "years of a century");
        }

        private void SetDateTimeInternal(DateTime dateTime, bool hushPrecisionWarning = false)
        {
            internalTimer.SetDateTime(dateTime, hushPrecisionWarning);

            // All the other registers will be updated before reading any of the Counters registers
            // but the century bit might not get updated if the centuryChangeEnabled is false.
            UpdateCenturyBit(dateTime.Year);

            UpdateAlarm();
        }

        private void UpdateAlarm()
        {
            internalTimer.UpdateAlarm(alarmRepeatInterval.Value, alarmMonth, alarmWeekday, alarmDay, alarmHours, alarmMinutes, alarmSeconds, alarmSecondHundredths * 10);
        }

        private void UpdateCenturyBit(int year)
        {
            centuryBit.Value = year < 2000 || year >= 2100;
        }

        private void UpdateCounterFields()
        {
            if(lastUpdateTimerValue == internalTimer.Value)
            {
                return;
            }

            var dateTime = internalTimer.GetCurrentDateTime();

            secondHundredths.SetFromInteger((int)Math.Round(dateTime.Millisecond / 10.0, 0));
            seconds.SetFromInteger(dateTime.Second);
            minutes.SetFromInteger(dateTime.Minute);
            hours.SetFromInteger(dateTime.Hour);
            day.SetFromInteger(dateTime.Day);
            month.SetFromInteger(dateTime.Month);
            yearsOfCentury.SetFromInteger(dateTime.Year % 100);
            weekday.SetFromInteger((int)dateTime.DayOfWeek);
            if(centuryChangeEnabled.Value)
            {
                UpdateCenturyBit(dateTime.Year);
            }

            lastUpdateTimerValue = internalTimer.Value;
        }

        private void UpdateInterrupt()
        {
            var newIrqState = interruptEnable.Value && interruptStatus;
            if(newIrqState != IRQ.IsSet)
            {
                this.Log(LogLevel.Debug, "IRQ {0}", newIrqState ? "set" : "reset");
                IRQ.Set(newIrqState);
            }
        }

        private bool InterruptStatus
        {
            get => interruptStatus;
            set
            {
                interruptStatus = value;
                UpdateInterrupt();
            }
        }

        private bool interruptStatus;
        private IFlagRegisterField counterWritesEnabled;
        private IFlagRegisterField centuryChangeEnabled;
        private IFlagRegisterField centuryBit;

        private IEnumRegisterField<AlarmRepeatIntervals> alarmRepeatInterval;
        private BCDValueField yearsOfCentury;
        private BCDValueField weekday;
        private BCDValueField seconds;
        private BCDValueField secondHundredths;  // 0.01s
        private BCDValueField month;
        private BCDValueField minutes;
        private IFlagRegisterField interruptEnable;
        private BCDValueField hours;
        private BCDValueField alarmWeekday;
        private BCDValueField alarmSecondHundredths;
        private BCDValueField alarmSeconds;
        private BCDValueField alarmMonth;
        private BCDValueField alarmMinutes;
        private BCDValueField alarmHours;

        private BCDValueField alarmDay;
        private ulong valueReadWithCountersLower;
        private bool writeBusy;
        private ulong lastUpdateTimerValue;
        private BCDValueField day;
        private IFlagRegisterField readError;

        private readonly RTCTimer internalTimer;

        private class BCDValueField
        {
            public static implicit operator int(BCDValueField field)
            {
                return field.GetInteger();
            }

            public BCDValueField(IPeripheral owner, string fieldTypeName, byte maxValueBCD = 0x99, bool zeroAllowed = true)
            {
                this.fieldTypeName = fieldTypeName;
                this.maxValueBCD = maxValueBCD;
                this.owner = owner;
                this.zeroAllowed = zeroAllowed;
            }

            public byte BCDGet()
            {
                return value;
            }

            public void BCDSet(byte bcdValue)
            {
                if(bcdValue > maxValueBCD || (!zeroAllowed && bcdValue == 0x0))
                {
                    owner.Log(LogLevel.Warning, "Invalid value for {0}: {1:X}", fieldTypeName, bcdValue);
                    return;
                }

                value = bcdValue;
            }

            public int GetInteger()
            {
                return BCDHelper.DecodeFromBCD(value);
            }

            public void SetFromInteger(int value)
            {
                BCDSet(BCDHelper.EncodeToBCD((byte)value));
            }

            public override string ToString()
            {
                // BCD value printed in hex is always equal to its decimal value.
                return $"{value:X}";
            }

            private byte value;

            private readonly string fieldTypeName;
            private readonly byte maxValueBCD;
            private readonly IPeripheral owner;
            private readonly bool zeroAllowed;
        }

        private class RTCTimer : LimitTimer
        {
            public RTCTimer(IMachine machine, IBusPeripheral owner, DateTime baseDateTime, Action alarmAction) : base(machine.ClockSource, Frequency, owner, "RTC",
                limit: ulong.MaxValue, direction: Direction.Ascending, enabled: true, workMode: WorkMode.Periodic, eventEnabled: true)
            {
                this.alarmAction = alarmAction;
                baseDateTimeTicks = baseDateTime.Ticks;
                this.owner = owner;
                systemBus = machine.GetSystemBus(owner);

                // It can be reached only after setting up the alarm.
                LimitReached += AlarmHandler;
            }

            public DateTime GetCurrentDateTime()
            {
                return ValueToDateTime(Value);
            }

            public DateTime GetNextAlarmDateTime()
            {
                return ValueToDateTime(nextAlarmValue);
            }

            public bool IsAlarmSet()
            {
                return Limit != ulong.MaxValue;
            }

            public override void Reset()
            {
                ResetAlarm();
                base.Reset();
            }

            public void SetDateTime(DateTime newDateTime, bool hushPrecisionWarning = false)
            {
                ResetAlarm();
                Value = ValueFromDateTime(newDateTime, hushPrecisionWarning);

                // The format is the same as 'o' but with only first two millisecond digits.
                // Further digits, if nonzero, were ignored setting RTC's value so let's not print them.
                owner.Log(LogLevel.Info, "New date time set: {0:yyyy-MM-ddTHH:mm:ss.ffK}", newDateTime);
            }

            public void UpdateAlarm(AlarmRepeatIntervals interval, int month, int weekday, int day, int hour, int minute, int second, int millisecond)
            {
                if(interval == AlarmRepeatIntervals.Month || interval == AlarmRepeatIntervals.Year)
                {
                    if(day == 0)
                    {
                        owner.Log(LogLevel.Warning, "Day cannot be zero for the {0} alarm repeat interval! Using 1st as an alarm day.", interval);
                        day = 1;
                    }
                }

                if(interval == AlarmRepeatIntervals.Year)
                {
                    if(month == 0)
                    {
                        owner.Log(LogLevel.Warning, "Month cannot be zero for the {0} alarm repeat interval! Using January as an alarm month.", interval);
                        month = 1;
                    }
                }

                var currentDateTime = GetCurrentDateTime();
                DateTime firstAlarm, intervalDateTime;
                switch(interval)
                {
                case AlarmRepeatIntervals.Second:
                    firstAlarm = new DateTime(currentDateTime.Year, currentDateTime.Month, currentDateTime.Day,
                        currentDateTime.Hour, currentDateTime.Minute, currentDateTime.Second, millisecond);
                    intervalDateTime = new DateTime().AddSeconds(1);
                    break;
                case AlarmRepeatIntervals.Minute:
                    firstAlarm = new DateTime(currentDateTime.Year, currentDateTime.Month, currentDateTime.Day,
                        currentDateTime.Hour, currentDateTime.Minute, second, millisecond);
                    intervalDateTime = new DateTime().AddMinutes(1);
                    break;
                case AlarmRepeatIntervals.Hour:
                    firstAlarm = new DateTime(currentDateTime.Year, currentDateTime.Month, currentDateTime.Day,
                        currentDateTime.Hour, minute, second, millisecond);
                    intervalDateTime = new DateTime().AddHours(1);
                    break;
                case AlarmRepeatIntervals.Day:
                    firstAlarm = new DateTime(currentDateTime.Year, currentDateTime.Month, currentDateTime.Day, hour,
                        minute, second, millisecond);
                    intervalDateTime = new DateTime().AddDays(1);
                    break;
                case AlarmRepeatIntervals.Week:
                    firstAlarm = new DateTime(currentDateTime.Year, currentDateTime.Month, currentDateTime.Day, hour,
                        minute, second, millisecond);
                    // This can take us "back in time" but we're always adjusting such a 'firstAlarm' nevertheless.
                    var daysToTheNearestAlarmWeekday = weekday - (int)firstAlarm.DayOfWeek;
                    firstAlarm = firstAlarm.AddDays(daysToTheNearestAlarmWeekday);
                    intervalDateTime = new DateTime().AddDays(7);
                    break;
                case AlarmRepeatIntervals.Month:
                    firstAlarm = new DateTime(currentDateTime.Year, currentDateTime.Month, day, hour, minute, second,
                        millisecond);
                    intervalDateTime = new DateTime().AddMonths(1);
                    break;
                case AlarmRepeatIntervals.Year:
                    firstAlarm = new DateTime(currentDateTime.Year, month, day, hour, minute, second, millisecond);
                    intervalDateTime = new DateTime().AddYears(1);
                    break;
                case AlarmRepeatIntervals.Disabled:
                    ResetAlarm();
                    return;
                default:
                    throw new ArgumentException("Something's very wrong; this should never happen.");
                }

                // Before this adjustment 'firstAlarm' can be in the past.
                if(firstAlarm < currentDateTime)
                {
                    firstAlarm = firstAlarm.AddTicks(intervalDateTime.Ticks);
                }

                alarmIntervalTicks = (ulong)intervalDateTime.Ticks / TimerTickToDateTimeTicks;
                nextAlarmValue = ValueFromDateTime(firstAlarm);
                Limit = nextAlarmValue;
                owner.Log(LogLevel.Debug, "First alarm set to: {0:o}, alarm repeat interval: {1}", firstAlarm, interval);
            }

            public new ulong Value
            {
                get
                {
                    if(systemBus.TryGetCurrentCPU(out var cpu))
                    {
                        // being here means we are on the CPU thread
                        cpu.SyncTime();
                    }
                    else
                    {
                        owner.Log(LogLevel.Noisy, "Couldn't synchronize time: returned value might lack precision");
                    }
                    return base.Value;
                }

                set => base.Value = value;
            }

            private static readonly ulong TimerTickToDateTimeTicks = (ulong)new DateTime().AddSeconds(1.0 / Frequency).Ticks;

            private void AlarmHandler()
            {
                alarmAction();

                // Value is automatically reset when the limit is reached.
                Value = nextAlarmValue;

                nextAlarmValue += alarmIntervalTicks;
                Limit = nextAlarmValue;

                owner.Log(LogLevel.Debug, "Alarm occurred at: {0:o}; next alarm: {1:o}", GetCurrentDateTime(), GetNextAlarmDateTime());
            }

            private void ResetAlarm()
            {
                Limit = ulong.MaxValue;
                alarmIntervalTicks = 0;
                nextAlarmValue = 0;
            }

            private ulong ValueFromDateTime(DateTime dateTime, bool hushPrecisionWarning = false)
            {
                var newDateTimeTicks = (ulong)(dateTime.Ticks - baseDateTimeTicks);
                if(!hushPrecisionWarning && (newDateTimeTicks % TimerTickToDateTimeTicks != 0))
                {
                    owner.Log(LogLevel.Warning, "Requested time for RTC is more precise than it supports (0.01s): {0:o}", dateTime);
                }
                return newDateTimeTicks / TimerTickToDateTimeTicks;
            }

            private DateTime ValueToDateTime(ulong value)
            {
                var dateTimeTicksPassed = value * TimerTickToDateTimeTicks;
                return new DateTime(baseDateTimeTicks + (long)dateTimeTicksPassed);
            }

            private ulong alarmIntervalTicks;
            private ulong nextAlarmValue;

            private readonly Action alarmAction;
            private readonly long baseDateTimeTicks;
            private readonly IPeripheral owner;
            private readonly IBusController systemBus;

            private new const long Frequency = 100;
        }

        private enum AlarmRepeatIntervals
        {
            Disabled,
            Year,
            Month,
            Week,
            Day,
            Hour,
            Minute,
            // Docs: "Interrupt every second/10th/100th".
            Second,
        }

        private enum Registers : long
        {
            Control = 0x0,
            Status = 0x4,
            CountersLower = 0x20,
            CountersUpper = 0x24,
            AlarmsLower = 0x30,
            AlarmsUpper = 0x34,
            InterruptEnable = 0x200,
            InterruptStatus = 0x204,
            InterruptClear = 0x208,
            InterruptSet = 0x20C,
        }
    }
}
namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals;
    using Antmicro.Renode.Peripherals.Timers;
    using Antmicro.Renode.Time;

    public sealed class BlackwallRtcAdapter : BlackwallStrictMMIO, IBlackwallRtc
    {
        public BlackwallRtcAdapter(IMachine machine,bool halLowUpperWrites=false) : base(0x400,0x40004800)
        {
            this.machine=machine; CounterWritesProfile=halLowUpperWrites;
            engine=new BlackwallRtcEngine(machine); Reset();
        }
        public bool Owns(ulong address) => address>=0x40004800 && address<0x40004c00;
        public override void Reset()
        {
            base.Reset(); engine.Reset(); engine.SetDateTime(2000,1,1,0,0,0,0);
            Reads=Writes=Commits=LateReads=0; pendingLow=false; readPair=false;
            pendingWord=upperSnapshot=alarmUpper=0; LastError="none";
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
        private static bool TryDate(uint low,uint upper,out DateTime date)
        {
            date=default(DateTime);
            if((upper&~0x17ff1f3fu)!=0 || (upper&0x10000000u)==0 || !ValidLow(low)) return false;
            var yy=Bcd((upper>>16)&255); var month=Bcd((upper>>8)&31); var day=Bcd(upper&63); var weekday=(upper>>24)&7;
            if(yy<0 || month<1 || month>12 || day<1 || day>DateTime.DaysInMonth(2000+yy,month) || weekday>6) return false;
            date=new DateTime(2000+yy,month,day,Bcd((low>>24)&63),Bcd((low>>16)&127),Bcd((low>>8)&127),Bcd(low&255)*10);
            return weekday==(uint)date.DayOfWeek;
        }
        private bool InCentury() => engine.CurrentDateTime.Year>=2000 && engine.CurrentDateTime.Year<=2099;
        private ulong Now => machine.ElapsedVirtualTime.TimeElapsed.Ticks;
        public GPIO IRQ => engine.IRQ;
        public bool CounterWritesProfile { get; }
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
    }
}

namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using Antmicro.Renode.Peripherals.CPU;
    using Antmicro.Renode.Core;
    using System;
    using System.Collections.Generic;
    // Observation only. Does not replace the existing block/memory hooks or mutate guest state.
    public sealed class BlackwallExecutionObserver
    {
        public BlackwallExecutionObserver(CortexM cpu, int eventCapacity=128)
        {
            if(eventCapacity<1 || eventCapacity>32768) throw new System.ArgumentException("Invalid observation event capacity");
            this.cpu=cpu; Capacity=eventCapacity;
        }
        public void AddPoint(string label, uint address)
        {
            if(string.IsNullOrEmpty(label) || (address&1)!=0 || points.Count>=128 || points.ContainsKey(address))
                throw new System.ArgumentException("Observation requires unique aligned instruction points");
            foreach(var p in points.Values) if(p.Label==label) throw new System.ArgumentException("Duplicate observation label");
            var point=new BlackwallObservedPoint(label,address);
            points.Add(address,point);
            cpu.AddHook(address,(c,a) => {
                point.Hits++; Sequence++;
                if(point.FirstSequence==0) point.FirstSequence=Sequence;
                if(events.Count==Capacity) { events.Dequeue(); DroppedEvents++; }
                events.Enqueue(new BlackwallPcEvent(Sequence,label,address,cpu.PC.RawValue,cpu.GetRegister(0).RawValue,cpu.GetRegister(2).RawValue));
                if(point.ReadSnapshot!=null && point.Snapshot==null)
                    point.Snapshot=new BlackwallSramSnapshot(Sequence,point.SnapshotAddress,point.ReadSnapshot());
            });
        }
        public void CaptureSram(IMachine machine,string label,uint address,int words)
        {
            if(words<1 || words>16 || (address&3)!=0 || address<0x20000000 || (ulong)address+4UL*(ulong)words>0x20380000)
                throw new ArgumentException("Snapshot requires bounded G2 SRAM words");
            BlackwallObservedPoint point=null;
            foreach(var p in points.Values) if(p.Label==label) point=p;
            if(point==null || point.Hits!=0 || point.ReadSnapshot!=null) throw new ArgumentException("Snapshot requires an unused observation point");
            point.SnapshotAddress=address;
            point.ReadSnapshot=() => {
                var data=new uint[words];
                for(var i=0;i<words;i++) data[i]=machine.SystemBus.ReadDoubleWord(address+4u*(uint)i);
                return data;
            };
        }
        public IEnumerable<BlackwallObservedPoint> Points => points.Values;
        public IEnumerable<BlackwallPcEvent> Events => events;
        public int Capacity { get; }
        public ulong Sequence { get; private set; }
        public ulong DroppedEvents { get; private set; }
        private readonly CortexM cpu;
        private readonly Dictionary<uint,BlackwallObservedPoint> points=new Dictionary<uint,BlackwallObservedPoint>();
        private readonly Queue<BlackwallPcEvent> events=new Queue<BlackwallPcEvent>();
    }
    public sealed class BlackwallObservedPoint
    {
        public BlackwallObservedPoint(string label,uint address) { Label=label; Address=address; }
        public string Label { get; }
        public uint Address { get; }
        public ulong Hits { get; internal set; }
        public ulong FirstSequence { get; internal set; }
        public BlackwallSramSnapshot Snapshot { get; internal set; }
        internal uint SnapshotAddress;
        internal Func<uint[]> ReadSnapshot;
    }
    public sealed class BlackwallSramSnapshot
    {
        public BlackwallSramSnapshot(ulong sequence,uint address,uint[] words) { Sequence=sequence; Address=address; Words=words; }
        public ulong Sequence { get; }
        public uint Address { get; }
        public uint[] Words { get; }
    }
    public sealed class BlackwallPcEvent
    {
        public BlackwallPcEvent(ulong sequence,string label,uint address,ulong pc,ulong r0,ulong r2)
        { Sequence=sequence; Label=label; Address=address; PC=pc; R0=r0; R2=r2; }
        public ulong Sequence { get; }
        public string Label { get; }
        public uint Address { get; }
        public ulong PC { get; }
        public ulong R0 { get; }
        public ulong R2 { get; }
    }
}

namespace Antmicro.Renode.Peripherals.Miscellaneous
{
using System;
using Antmicro.Renode.Peripherals.I2C;
using Antmicro.Renode.Peripherals.CPU;
    // Explicit synthetic pointer transaction, not a PMIC model or a data responder.
    public sealed class BlackwallI2cPointerProbe : II2CPeripheral
    {
        public BlackwallI2cPointerProbe() { Reset(); }
        public void Reset()
        {
            Pointer=-1; Writes=Finishes=ReadAttempts=AccessCount=0;
            LastAddress=LastValue=0; LastWidth=0; LastOperation="none"; pending=false;
        }
        private void Block(string operation,int length,ulong value=0)
        {
            AccessCount++; LastAddress=Pointer<0 ? 0ul : (ulong)Pointer;
            LastWidth=length; LastOperation=operation; LastValue=value;
            throw new CpuAbortException("Blackwall pointer probe unsupported "+operation);
        }
        public void Write(byte[] data)
        {
            if(pending || data==null || data.Length!=2 || data[0]!=5 || data[1]!=9)
            {
                Block("peer-write-unsupported",data==null ? 0 : data.Length);
                return;
            }
            Pointer=0x0509; Writes++; pending=true;
        }
        public byte[] Read(int count=1)
        {
            ReadAttempts++;
            Block("peer-read-unknown",count);
            return null;
        }
        public void FinishTransmission()
        {
            if(!pending) { Block("peer-finish-without-pointer",0);return; }
            pending=false; Finishes++;
        }
        public int Pointer {get;private set;}
        public int Writes {get;private set;}
        public int Finishes {get;private set;}
        public int ReadAttempts {get;private set;}
        public int AccessCount {get;private set;}
        public ulong LastAddress {get;private set;}
        public int LastWidth {get;private set;}
        public ulong LastValue {get;private set;}
        public string LastOperation {get;private set;}
        private bool pending;
    }
}

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

namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    // Interrupt register subset only. No counter/capture events or NVIC delivery.
    public sealed class BlackwallStimerInterruptStorage : IBlackwallStimer
    {
        public BlackwallStimerInterruptStorage(string profile)
        {
            if(profile!="source-reset-storage")throw new System.ArgumentException("Explicit STIMER interrupt storage required");
            Reset();
        }
        public void Reset() {Enable=Status=0;Reads=Writes=0;}
        public bool Owns(ulong address)=>address==0x40008900 || address==0x40008904 || address==0x40008908 || address==0x4000890c;
        public bool TryRead(ulong address,out uint value)
        {
            value=0;
            if(address==0x40008900)value=Enable;
            else if(address==0x40008904)value=Status;
            else return false;
            Reads++;return true;
        }
        public bool TryWrite(ulong address,uint value)
        {
            if((value&~0x1fffu)!=0)return false;
            if(address==0x40008900)Enable=value;
            else if(address==0x40008904 && value==0)Status=0;
            else if(address==0x40008908)Status&=~value;
            else if(address==0x4000890c)Status|=value;
            else return false;
            Writes++;return true;
        }
        public uint Enable {get;private set;}public uint Status {get;private set;}
        public int Reads {get;private set;}public int Writes {get;private set;}
        public bool Pending=>(Enable&Status)!=0;
    }
}

//
// Copyright (c) 2010-2026 Antmicro
//
// This file is licensed under the MIT License.
// Full license text is available in 'licenses/MIT.txt'.
//
namespace Antmicro.Renode.Peripherals.Timers
{
using System;

using Antmicro.Renode.Core;
using Antmicro.Renode.Core.Structure.Registers;
using Antmicro.Renode.Logging;
using Antmicro.Renode.Peripherals.Bus;
using Antmicro.Renode.Time;

    [AllowedTranslations(AllowedTranslation.ByteToDoubleWord | AllowedTranslation.WordToDoubleWord)]
    public class BlackwallStimerEngine : BasicDoubleWordPeripheral, IKnownSize, IGPIOReceiver
    {
        public BlackwallStimerEngine(IMachine machine) : base(machine)
        {
            // Changing 'CLKSEL' (it's 'NOCLK' by default) is necessary to enable 'systemTimer'.
            systemTimer = new LimitTimer(machine.ClockSource, InvalidFrequency, this, "System Timer", 0x100000000UL,
                Direction.Ascending, enabled: false, workMode: WorkMode.Periodic, eventEnabled: true, autoUpdate: true, divider: 1);
            systemTimer.LimitReached += () => HandleLimitReached();

            for(var i = 0; i < interruptOutputs.Length; i++)
            {
                interruptOutputs[i] = new GPIO();
            }
            for(var i = 0; i < captureRegisters.Length; i++)
            {
                captureRegisters[i] = new CaptureRegister(this, i);
            }
            for(var i = 0; i < compareRegisters.Length; i++)
            {
                compareRegisters[i] = new CompareRegister(this, i, interruptOutputs[i], systemTimer);
            }

            DefineRegisters();
            Reset();
        }

        public void OnGPIO(int number, bool value)
        {
            this.Log(LogLevel.Debug, "GPIO#{0} {1}", number, value ? "set" : "unset");
            foreach(var captureRegister in captureRegisters)
            {
                captureRegister.OnGPIO(number, value);
            }
        }

        public override void Reset()
        {
            Array.ForEach(captureRegisters, register => register.Reset());
            Array.ForEach(compareRegisters, register => register.Reset());
            // All but IRQI should be reset with CompareRegister.Reset; nevertheless, let's unset all IRQs.
            Array.ForEach(interruptOutputs, irq => irq.Unset());
            systemTimer.Reset();

            base.Reset();
        }

        public ulong Frequency => systemTimer.Frequency;

        // Comparator IRQs
        public GPIO IRQA => interruptOutputs[0];

        public GPIO IRQB => interruptOutputs[1];

        public GPIO IRQC => interruptOutputs[2];

        public GPIO IRQD => interruptOutputs[3];

        public GPIO IRQE => interruptOutputs[4];

        public GPIO IRQF => interruptOutputs[5];

        public GPIO IRQG => interruptOutputs[6];

        public GPIO IRQH => interruptOutputs[7];

        // Capture + overflow event IRQ
        public GPIO IRQI => interruptOutputs[8];

        public long Size => 0x110;

        public uint Value
        {
            get
            {
                if(machine.SystemBus.TryGetCurrentCPU(out var cpu))
                {
                    // being here means we are on the CPU thread
                    cpu.SyncTime();
                }
                return (uint)systemTimer.Value;
            }
        }

        public void LoadCounter(uint value)
        {
            systemTimer.Value=value;
            Array.ForEach(compareRegisters, register => register.UpdateState());
        }

        private void DefineRegisters()
        {
            Registers.Capture0.DefineMany(this, 4,
                (register, registerIndex) =>
                {
                    register.WithValueField(0, 32, FieldMode.Read, name: $"SCAPT{registerIndex}",
                        valueProviderCallback: _ => captureRegisters[registerIndex].ValueCaptured);
                }, stepInBytes: 4);

            Registers.CaptureControl0.DefineMany(this, 4,
                (register, registerIndex) =>
                {
                    var captureRegister = captureRegisters[registerIndex];
                    register.WithValueField(0, 7, out captureRegister.TriggerSourceGPIOPinNumber, name: $"STSEL{registerIndex}")
                        .WithReservedBits(7, 1)
                        .WithFlag(8, out captureRegister.CaptureOnHighToLowGPIOTransition, name: $"STPOL{registerIndex}")
                        .WithFlag(9, out captureRegister.Enabled, name: $"CAPTURE{registerIndex}")
                        .WithReservedBits(10, 22)
                        ;
                }, stepInBytes: 4, resetValue: 0x7F);

            Registers.Compare0.DefineMany(this, 8,
                (register, registerIndex) =>
                {
                    register.WithValueField(0, 32, name: $"SCMPR{registerIndex}",
                        // SCMPR value written is relative to the current COUNTER (systemTimer's Value).
                        writeCallback: (_, newValue) =>
                        {
                            // Ambiq HAL does a Compare delta adjustment:
                            // on HW it takes 2 clock cycles for writes to this register to be effective
                            // and the interrupt itself is delayed by 1.
                            // Hence the timer incrementation.
                            // Explicit immediate-write timing model; no synthetic counter increment.
                            compareRegisters[registerIndex].CompareValue = Value + (uint)newValue;
                        },
                        valueProviderCallback: _ => compareRegisters[registerIndex].CompareValue);
                }, stepInBytes: 4);

            Registers.Configuration.Define(this, 0x80000000)
                .WithEnumField(0, 4, out clockSelect, name: "CLKSEL", changeCallback: (_, __) => UpdateFrequency())
                .WithReservedBits(4, 4)
                .WithFlags(8, 8, name: "COMPARExEN", changeCallback: (registerIndex, _, newValue) => compareRegisters[registerIndex].Enabled = newValue)
                .WithReservedBits(16, 14)
                .WithFlag(30, out clear, name: "CLEAR", changeCallback: (_, __) => UpdateSystemTimerState())
                .WithFlag(31, out freeze, name: "FREEZE", changeCallback: (_, __) => UpdateSystemTimerState())
                ;

            Registers.InterruptClear.Define(this)
                .WithFlags(0, 8, FieldMode.Write, name: "COMPAREx",
                    writeCallback: (registerIndex, _, newValue) => { if(newValue) compareRegisters[registerIndex].InterruptStatus = false; })
                .WithFlag(8, out overflowInterruptStatus, FieldMode.WriteOneToClear, name: "OVERFLOW",
                    changeCallback: (_, __) => UpdateCaptureOverflowIRQ())
                .WithFlags(9, 4, FieldMode.Write, name: "CAPTUREx",
                    writeCallback: (registerIndex, _, newValue) => { if(newValue) captureRegisters[registerIndex].InterruptStatus = false; })
                .WithReservedBits(13, 19)
                ;

            Registers.InterruptEnable.Define(this)
                .WithFlags(0, 8, name: "COMPAREx",
                    changeCallback: (registerIndex, _, newValue) => compareRegisters[registerIndex].InterruptEnable = newValue,
                    valueProviderCallback: (registerIndex, _) => compareRegisters[registerIndex].InterruptEnable)
                .WithFlag(8, out overflowInterruptEnable, name: "OVERFLOW",
                    changeCallback: (_, __) => UpdateCaptureOverflowIRQ())
                .WithFlags(9, 4, name: "CAPTUREx",
                    changeCallback: (registerIdx, _, newValue) => captureRegisters[registerIdx].InterruptEnable = newValue,
                    valueProviderCallback: (registerIdx, _) => captureRegisters[registerIdx].InterruptEnable)
                .WithReservedBits(13, 19)
                ;

            Registers.InterruptSet.Define(this)
                .WithFlags(0, 8, FieldMode.Write, name: "COMPAREx",
                    writeCallback: (registerIndex, _, newValue) => { if(newValue) compareRegisters[registerIndex].InterruptStatus = true; })
                .WithFlag(8, out overflowInterruptStatus, FieldMode.Set, name: "OVERFLOW",
                    changeCallback: (_, __) => UpdateCaptureOverflowIRQ())
                .WithFlags(9, 4, FieldMode.Write, name: "CAPTUREx",
                    writeCallback: (registerIndex, _, newValue) => { if(newValue) captureRegisters[registerIndex].InterruptStatus = true; })
                .WithReservedBits(13, 19)
                ;

            Registers.InterruptStatus.Define(this)
                .WithFlags(0, 8, FieldMode.Read, name: "COMPAREx",
                    valueProviderCallback: (registerIndex, _) => compareRegisters[registerIndex].InterruptStatus)
                .WithFlag(8, out overflowInterruptStatus, FieldMode.Read, name: "OVERFLOW")
                .WithFlags(9, 4, FieldMode.Read, name: "CAPTUREx",
                    valueProviderCallback: (registerIdx, _) => captureRegisters[registerIdx].InterruptStatus)
                .WithReservedBits(13, 19)
                ;

            Registers.SystemTimerCount.Define(this)
                .WithValueField(0, 32, FieldMode.Read, name: "STTMR", valueProviderCallback: _ => Value)
                ;
        }

        private void HandleLimitReached()
        {
            this.Log(LogLevel.Debug, "COUNTER overflow occurred");
            overflowInterruptStatus.Value = true;
            UpdateCaptureOverflowIRQ();
        }

        private void UpdateCaptureOverflowIRQ()
        {
            var newIrqState = false;
            foreach(var captureRegister in captureRegisters)
            {
                if(captureRegister.InterruptEnable && captureRegister.InterruptStatus)
                {
                    newIrqState = true;
                    break;
                }
            }
            if(!newIrqState && overflowInterruptStatus.Value && overflowInterruptEnable.Value)
            {
                newIrqState = true;
            }

            if(IRQI.IsSet != newIrqState)
            {
                this.Log(LogLevel.Debug, "IRQI {0}", newIrqState ? "set" : "unset");
                IRQI.Set(newIrqState);
            }
        }

        private void UpdateFrequency()
        {
            var frequencySet = InvalidFrequency;
            const long khz = 1000;
            switch(clockSelect.Value)
            {
            case ClockSelectValues.NOCLK:
                this.Log(LogLevel.Debug, "CLKSEL set to NOCLK. Timer will be disabled.");
                break;
            case ClockSelectValues.HFRC_6MHZ:
                frequencySet = 6 * 1000 * khz;
                break;
            case ClockSelectValues.HFRC_375KHZ:
                frequencySet = 375 * khz;
                break;
            case ClockSelectValues.XTAL_32KHZ:
                frequencySet = 32768;
                break;
            case ClockSelectValues.XTAL_16KHZ:
                frequencySet = 16384;
                break;
            case ClockSelectValues.XTAL_1KHZ:
                frequencySet = 1024;
                break;
            case ClockSelectValues.LFRC_1KHZ:
                frequencySet = 900;
                break;
            case ClockSelectValues.CTIMER0:
            case ClockSelectValues.CTIMER1:
                this.Log(LogLevel.Warning, "Unsupported CLKSEL value: {0}", clockSelect.Value);
                break;
            default:
                this.Log(LogLevel.Error, "Invalid CLKSEL value: 0x{0:X}", (uint)clockSelect.Value);
                break;
            }

            systemTimer.Frequency = frequencySet;
            Array.ForEach(compareRegisters, register => register.Frequency = frequencySet);
            if(frequencySet != InvalidFrequency)
            {
                this.Log(LogLevel.Debug, "Updating timer's frequency to {0} KHz; CLKSEL={1} ({2})", frequencySet / khz, (uint)clockSelect.Value, clockSelect.Value);
            }
            // CLKSEL influences the timer state depending on whether the frequency is valid or not.
            UpdateSystemTimerState();
        }

        private void UpdateSystemTimerState()
        {
            systemTimer.Enabled = !freeze.Value && !clear.Value && systemTimer.Frequency != InvalidFrequency;
            if(clear.Value)
            {
                systemTimer.ResetValue();
            }
            Array.ForEach(compareRegisters, register => register.UpdateState());
        }

        private IFlagRegisterField clear;
        private IEnumRegisterField<ClockSelectValues> clockSelect;
        private IFlagRegisterField freeze;
        private IFlagRegisterField overflowInterruptEnable;
        private IFlagRegisterField overflowInterruptStatus;

        private readonly CaptureRegister[] captureRegisters = new CaptureRegister[CaptureRegistersCount];
        private readonly CompareRegister[] compareRegisters = new CompareRegister[CompareRegistersCount];
        private readonly GPIO[] interruptOutputs = new GPIO[InterruptOutputsCount];
        private readonly LimitTimer systemTimer;

        private const uint CompareRegistersCount = 8;
        private const uint CaptureRegistersCount = 4;
        private const uint InterruptOutputsCount = 9;
        // It's used for CLKSEL options which stop the timer. 0 can't be set as the timer's frequency, hence 1.
        private const ulong InvalidFrequency = 1;

        private class CaptureRegister
        {
            public CaptureRegister(BlackwallStimerEngine owner, int index)
            {
                this.owner = owner;
                var nameSuffix = (char)('A' + index);
                name = $"CAPTURE_{nameSuffix}";
            }

            public void OnGPIO(int number, bool high)
            {
                if(Enabled.Value
                        && (int)TriggerSourceGPIOPinNumber.Value == number
                        // The 'value' is 'true' here if the opposite (low to high) transition has just occurred.
                        && CaptureOnHighToLowGPIOTransition.Value != high)
                {
                    ValueCaptured = owner.Value;
                    InterruptStatus = true;
                    owner.Log(LogLevel.Debug, "{0}: Register set with value: 0x{1:X}", name, ValueCaptured);
                }
            }

            public void Reset()
            {
                interruptEnable = false;
                interruptStatus = false;
                ValueCaptured = 0;
            }

            public bool InterruptEnable
            {
                get => interruptEnable;
                set
                {
                    owner.Log(LogLevel.Noisy, "{0}: Setting Interrupt Enable to: {1}", name, value);
                    interruptEnable = value;
                    owner.UpdateCaptureOverflowIRQ();
                }
            }

            public bool InterruptStatus
            {
                get => interruptStatus;
                set
                {
                    owner.Log(LogLevel.Noisy, "{0}: Setting Interrupt Status to: {1}", name, value);
                    interruptStatus = value;
                    owner.UpdateCaptureOverflowIRQ();
                }
            }

            public IFlagRegisterField CaptureOnHighToLowGPIOTransition;
            public IFlagRegisterField Enabled;
            public IValueRegisterField TriggerSourceGPIOPinNumber;
            public uint ValueCaptured;

            private bool interruptEnable;
            private bool interruptStatus;

            private readonly string name;
            private readonly BlackwallStimerEngine owner;
        }

        private class CompareRegister
        {
            public CompareRegister(BlackwallStimerEngine owner, int index, GPIO irq, LimitTimer systemTimer)
            {
                this.irq = irq;
                this.owner = owner;
                this.systemTimer = systemTimer;
                var nameSuffix = (char)('A' + index);
                name = $"COMPARE_{nameSuffix}";

                innerTimer = new ComparingTimer(owner.machine.ClockSource, owner.Frequency, owner, name, direction: Direction.Ascending, limit: 0x100000000UL,
                        enabled: false, workMode: WorkMode.Periodic, eventEnabled: true, compare: 0, divider: 1);
                innerTimer.CompareReached += () =>
                {
                    owner.Log(LogLevel.Debug, "{0}: Compare value (0x{1:X}) reached", name, innerTimer.Compare);
                    InterruptStatus = true;
                };
            }

            public void Reset()
            {
                enabled = false;
                innerTimer.Reset();
                interruptEnable = false;
                interruptStatus = false;
                irq.Unset();
            }

            public void UpdateState()
            {
                if(enabled && systemTimer.Enabled)
                {
                    innerTimer.Value = owner.Value;
                    innerTimer.Enabled = true;
                }
                else
                {
                    innerTimer.Enabled = false;
                }
            }

            public uint CompareValue
            {
                get => (uint)innerTimer.Compare;
                set
                {
                    owner.Log(LogLevel.Noisy, "{0}: Setting compare value to: 0x{1:X}", name, value);
                    innerTimer.Compare = value;
                }
            }

            public bool Enabled
            {
                get => enabled;
                set
                {
                    owner.Log(LogLevel.Noisy, "{0}: Setting Enabled to: {1}", name, value);
                    enabled = value;
                    UpdateState();
                }
            }

            public ulong Frequency
            {
                get => innerTimer.Frequency;
                set => innerTimer.Frequency = value;
            }

            public bool InterruptEnable
            {
                get => interruptEnable;
                set
                {
                    owner.Log(LogLevel.Noisy, "{0}: Setting interrupt enable to: {1}", name, value);
                    interruptEnable = value;
                    UpdateIRQ();
                }
            }

            public bool InterruptStatus
            {
                get => interruptStatus;
                set
                {
                    owner.Log(LogLevel.Noisy, "{0}: Setting interrupt status to: {1}", name, value);
                    interruptStatus = value;
                    UpdateIRQ();
                }
            }

            private void UpdateIRQ()
            {
                var newIrqState = interruptEnable && interruptStatus;
                if(irq.IsSet != newIrqState)
                {
                    owner.Log(LogLevel.Debug, "{0}: {1} IRQ", name, newIrqState ? "Setting" : "Clearing");
                    irq.Set(newIrqState);
                }
            }

            private bool enabled;
            private bool interruptEnable;
            private bool interruptStatus;

            private readonly ComparingTimer innerTimer;
            private readonly GPIO irq;
            private readonly string name;
            private readonly BlackwallStimerEngine owner;
            private readonly LimitTimer systemTimer;
        }

        private enum ClockSelectValues
        {
            NOCLK,
            HFRC_6MHZ,
            HFRC_375KHZ,
            XTAL_32KHZ,
            XTAL_16KHZ,
            XTAL_1KHZ,
            LFRC_1KHZ,
            CTIMER0,
            CTIMER1,
        }

        private enum Registers : long
        {
            Configuration = 0x0,
            SystemTimerCount = 0x4,
            CaptureControl0 = 0x10,
            CaptureControl1 = 0x14,
            CaptureControl2 = 0x18,
            CaptureControl3 = 0x1C,
            Compare0 = 0x20,
            Compare1 = 0x24,
            Compare2 = 0x28,
            Compare3 = 0x2C,
            Compare4 = 0x30,
            Compare5 = 0x34,
            Compare6 = 0x38,
            Compare7 = 0x3C,
            Capture0 = 0x40,
            Capture1 = 0x44,
            Capture2 = 0x48,
            Capture3 = 0x4C,
            SystemTimerNVRAM0 = 0x50,
            SystemTimerNVRAM1 = 0x54,
            SystemTimerNVRAM2 = 0x58,
            InterruptEnable = 0x100,
            InterruptStatus = 0x104,
            InterruptClear = 0x108,
            InterruptSet = 0x10C,
        }
    }
}
namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals.Timers;
    // Digital engine with declared nominal input clocks and immediate relative compare writes.
    public sealed class BlackwallStimerClockCounter : IBlackwallStimer
    {
        public BlackwallStimerClockCounter(IMachine machine,string profile)
        {
            if(profile!="nominal-source-clocks")throw new ArgumentException("Explicit nominal STIMER clock profile required");
            engine=new BlackwallStimerEngine(machine);Reset();
        }
        public bool Owns(ulong a)=>a==0x40008800 || a==0x40008804 || (a>=0x40008820 && a<=0x4000883c && (a&3)==0) || a==0x40008900 || a==0x40008904 || a==0x40008908 || a==0x4000890c;
        public bool TryRead(ulong address,out uint value)
        {
            value=0;
            if(!Owns(address) || address==0x40008908 || address==0x4000890c)return false;
            value=engine.ReadDoubleWord((long)(address-0x40008800));Reads++;return true;
        }
        public bool TryWrite(ulong address,uint value)
        {
            if(!Owns(address))return false;
            if(address==0x40008800)
            {
                if((value&~0xc000ff0fu)!=0 || (value&15)>6)return false;
                engine.WriteDoubleWord(0,value);
            }
            else if(address==0x40008804)
            {
                if((Config&0x80000000u)==0 || (Config&0x40000000u)!=0)return false;
                engine.LoadCounter(value);
            }
            else if(address>=0x40008900)
            {
                if((value&~0x1fffu)!=0 || (address==0x40008904 && value!=0))return false;
                engine.WriteDoubleWord(address==0x40008904 ? 0x108 : (long)(address-0x40008800),address==0x40008904 ? 0x1fffu : value);
            }
            else engine.WriteDoubleWord((long)(address-0x40008800),value);
            Writes++;return true;
        }
        public void Reset() {engine.Reset();Reads=Writes=0;}
        public uint Config=>engine.ReadDoubleWord(0);
        public uint Counter=>engine.Value;
        public ulong Frequency=>(Config&15)==0 ? 0 : engine.Frequency;
        public uint Enable=>engine.ReadDoubleWord(0x100);
        public uint Status=>engine.ReadDoubleWord(0x104);
        public bool Pending=>(Enable&Status)!=0;
        public int Reads {get;private set;}public int Writes {get;private set;}
        public GPIO IRQA=>engine.IRQA;public GPIO IRQB=>engine.IRQB;public GPIO IRQC=>engine.IRQC;
        public GPIO IRQD=>engine.IRQD;public GPIO IRQE=>engine.IRQE;public GPIO IRQF=>engine.IRQF;
        public GPIO IRQG=>engine.IRQG;public GPIO IRQH=>engine.IRQH;public GPIO IRQI=>engine.IRQI;
        private readonly BlackwallStimerEngine engine;
    }
}

namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    // MSPI1 field storage only. Does not generate a clock or implement a bus engine.
    public sealed class BlackwallMspi1ClockStorage : IBlackwallMspi1Clock
    {
        public BlackwallMspi1ClockStorage(string profile,bool mspi0Storage=false)
        {
            if(profile!="source-reset-storage") throw new System.ArgumentException("Explicit MSPI1 clock profile required");
            Mspi0Storage=mspi0Storage;
            Reset();
        }
        public void Reset() { Value=0xa4214; Reads=Writes=ChangeEpoch=0; }
        public uint Read() { Reads++; return Value; }
        public bool TryWrite(uint value)
        {
            // Unselected modules and reserved bits must retain their source reset values.
            var selection=(value>>6)&15;
            var mask=Mspi0Storage ? 0x3ffu : 0x3e0u;
            var selection0=(value>>1)&15;
            if((value&~mask)!=(0xa4214u&~mask) || (selection!=7 && selection!=8)
                || (Mspi0Storage && (selection0<7 || selection0>10))) return false;
            if(Mspi0Storage && ((Value^value)&0x1fu)!=0 && ((Value^value)&0x3e0u)!=0)return false;
            if(Value!=value)ChangeEpoch++;
            Value=value; Writes++; return true;
        }
        public uint Value { get; private set; }
        public uint ChangeEpoch { get; private set; }
        public uint Reads { get; private set; }
        public uint Writes { get; private set; }
        public bool Enabled => (Value&0x20)!=0;
        public uint Selection => (Value>>6)&15;
        public bool Mspi0Storage {get;}
        public bool Mspi0Enabled => (Value&1)!=0;
        public uint Mspi0Selection => (Value>>1)&15;
    }
}

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
            BlackwallMspi1ClockStorage clock,BlackwallMspi1Interrupts interrupts,bool completeTransactions=true,string diagnosticRxHex="",bool completeReceive=true)
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
            else if(offset==0x1c && diagnostic!=null)value=rxReady ? 1u:0u;
            else if(offset==0x14 && diagnostic!=null && rxReady)
            {
                value=(uint)(diagnostic[0]|diagnostic[1]<<8|diagnostic[2]<<16|diagnostic[3]<<24);
                rxReady=false;RxReads++;RxBytesDelivered+=4;
            }
            else return false;
            Reads++;return true;
        }
        public bool TryWrite(uint value,uint instruction,uint configuration,uint address,uint control1,uint ddr)
        {
            SyncTime();if(!Ready || busy || rxReady)return false;
            if(value==2) { Control&=~2u;Writes++;return true; }
            bool receive=value==0x40441u && instruction==0x9fu && diagnostic!=null;
            if(receive)
            {
                if((configuration&31u)!=1u || control1!=0 || (ddr&31u)!=0 || receiveFrames.Count>=4096)return false;
                requestControl=value;requestInstruction=instruction;requestAddress=0;requestConfiguration=configuration;
                clockField=clock.Value&31u;receiving=true;rxReady=false;busy=true;RxStarts++;Writes++;
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
                    receiveFrames.Add(new BlackwallMspi0TxFrame(requestControl,requestInstruction,requestAddress,requestConfiguration,diagnostic));
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
        private readonly byte[] diagnostic;
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

//
// Copyright (c) 2010-2026 Antmicro
//
// This file is licensed under the MIT License.
// Full license text is available in 'licenses/MIT.txt'.
//
namespace Antmicro.Renode.Peripherals.Timers
{
using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Linq;

using Antmicro.Renode.Core;
using Antmicro.Renode.Core.Structure.Registers;
using Antmicro.Renode.Logging;
using Antmicro.Renode.Time;

    public class BlackwallApolloTimerEngine : BasicDoubleWordPeripheral, INumberedGPIOOutput, IKnownSize
    {
        public BlackwallApolloTimerEngine(IMachine machine) : base(machine)
        {
            var innerConnections = new Dictionary<int, IGPIO>();
            internalTimers = new InternalTimer[TimersCount];
            for(var i = 0; i < TimersCount; ++i)
            {
                internalTimers[i] = new InternalTimer(this, machine.ClockSource, i);
                internalTimers[i].OnCompare += UpdateInterrupts;
                innerConnections[i] = new GPIO();
            }

            padOutput = new IEnumRegisterField<PadOutput>[OutputConfigRegisters * OutputConfigFieldsPerRegister];
            timerEnabled = new IFlagRegisterField[TimersCount];
            functionSelect = new IEnumRegisterField<FunctionSelect>[TimersCount];
            triggerMode = new IEnumRegisterField<TriggerMode>[TimersCount];
            triggerSource = new IEnumRegisterField<TriggerSource>[TimersCount];

            Connections = new ReadOnlyDictionary<int, IGPIO>(innerConnections);

            DefineRegisters();
            Reset();
        }

        public override void Reset()
        {
            base.Reset();
            for(var i = 0; i < TimersCount; ++i)
            {
                internalTimers[i].Reset();
                Connections[i].Unset();
                if(i == 7) { internalTimers[i].Frequency = HFRCFrequency; internalTimers[i].Divider = 4; }
            }
        }

        public IReadOnlyDictionary<int, IGPIO> Connections { get; }

        public long Size => 0x800;

        private ulong GetFrequencyAndDivider(ClockSelect clockSelect, out uint divider)
        {
            divider = 1;
            var frequency = 1UL;

            switch(clockSelect)
            {
            case (ClockSelect)0: // Internal inactive reset clock; not exposed as an enabled adapter profile.
                frequency = HFRCFrequency;
                divider = 4;
                break;
            case ClockSelect.HFRCDiv16:
                frequency = HFRCFrequency;
                divider = 16;
                break;
            case ClockSelect.HFRCDiv64:
                frequency = HFRCFrequency;
                divider = 64;
                break;
            case ClockSelect.HFRCDiv256:
                frequency = HFRCFrequency;
                divider = 256;
                break;
            case ClockSelect.HFRCDiv1024:
                frequency = HFRCFrequency;
                divider = 1024;
                break;
            case ClockSelect.HFRCDiv4K:
                frequency = HFRCFrequency;
                divider = 4096;
                break;
            case ClockSelect.LFRC:
                frequency = LFRCFrequency;
                break;
            case ClockSelect.LFRCDiv2:
                frequency = LFRCFrequency;
                divider = 2;
                break;
            case ClockSelect.LFRCDiv32:
                frequency = LFRCFrequency;
                divider = 32;
                break;
            case ClockSelect.LFRCDiv1K:
                frequency = LFRCFrequency;
                divider = 1024;
                break;
            case ClockSelect.XT:
                frequency = XTFrequency;
                break;
            case ClockSelect.XTDiv2:
                frequency = XTFrequency;
                divider = 2;
                break;
            case ClockSelect.XTDiv4:
                frequency = XTFrequency;
                divider = 4;
                break;
            case ClockSelect.XTDiv8:
                frequency = XTFrequency;
                divider = 8;
                break;
            case ClockSelect.XTDiv16:
                frequency = XTFrequency;
                divider = 16;
                break;
            case ClockSelect.XTDiv32:
                frequency = XTFrequency;
                divider = 32;
                break;
            case ClockSelect.XTDiv128:
                frequency = XTFrequency;
                divider = 128;
                break;
            case ClockSelect.RTC_100HZ:
                frequency = 100;
                break;
            default:
                this.Log(LogLevel.Warning, "{0} is not supported; set default frequency of 1Hz", clockSelect);
                break;
            }
            return frequency;
        }

        private void UpdateTimerActiveStatus()
        {
            for(var i = 0; i < TimersCount; ++i)
            {
                internalTimers[i].Enabled = timerEnabled[i].Value && globalTimerEnabled[i].Value;
            }
        }

        private void UpdateInterrupts()
        {
            for(var i = 0; i < TimersCount; ++i)
            {
                var interrupt = false;
                interrupt |= internalTimers[i].Compare0Event && internalTimers[i].Compare0Interrupt;
                interrupt |= internalTimers[i].Compare1Event && internalTimers[i].Compare1Interrupt;

                if(Connections[i].IsSet != interrupt)
                {
                    this.NoisyLog("Changing Interrupt{0} from {1} to {2}", i, Connections[i].IsSet, interrupt);
                }

                Connections[i].Set(interrupt);
            }
        }

        private void DefineRegisters()
        {
            Registers.Control.Define(this)
                .WithReservedBits(0, 31)
                .WithFlag(31, FieldMode.WriteOneToClear, name: "RESET",
                    writeCallback: (_, value) => { if(value) Reset(); })
            ;

            Registers.Status.Define(this)
                .WithValueField(0, 16, FieldMode.Read, name: "ACTIVE",
                    valueProviderCallback: _ => (uint)internalTimers.Count(timer => timer.Enabled))
                .WithValueField(16, 5, FieldMode.Read, name: "NTIMERS",
                    valueProviderCallback: _ => TimersCount)
                .WithReservedBits(21, 11)
            ;

            Registers.GlobalEnable.Define(this, 0xffff)
                .WithFlags(0, 16, out globalTimerEnabled, name: "ENB")
                .WithChangeCallback((_, __) => UpdateTimerActiveStatus())
            ;
            {
                var interruptEnable = Registers.InterruptEnable.Define(this)
                    .WithWriteCallback((_, __) => UpdateInterrupts());
                var interruptStatus = Registers.InterruptStatus.Define(this)
                    .WithWriteCallback((_, __) => UpdateInterrupts());
                var interruptClear = Registers.InterruptClear.Define(this)
                    .WithWriteCallback((_, __) => UpdateInterrupts());
                var interruptSet = Registers.InterruptSet.Define(this)
                    .WithWriteCallback((_, __) => UpdateInterrupts());

                for(var i = 0; i < TimersCount; ++i)
                {
                    var index = i;

                    interruptEnable
                        .WithFlag(2 * index, name: $"TMR{index}0INT",
                            valueProviderCallback: _ => internalTimers[index].Compare0Interrupt,
                            writeCallback: (_, value) => internalTimers[index].Compare0Interrupt = value)
                        .WithFlag(2 * index + 1, name: $"TMR{index}1INT",
                            valueProviderCallback: _ => internalTimers[index].Compare1Interrupt,
                            writeCallback: (_, value) => internalTimers[index].Compare1Interrupt = value)
                    ;

                    interruptStatus
                        .WithFlag(2 * index, name: $"TMR{index}0INTSTAT",
                            valueProviderCallback: _ => internalTimers[index].Compare0Event,
                            writeCallback: (_, value) => internalTimers[index].Compare0Event = value)
                        .WithFlag(2 * index + 1, name: $"TMR{index}1INTSTAT",
                            valueProviderCallback: _ => internalTimers[index].Compare1Event,
                            writeCallback: (_, value) => internalTimers[index].Compare1Event = value)
                    ;

                    interruptClear
                        .WithFlag(2 * index, name: $"TMR{index}0INTCLR",
                            valueProviderCallback: _ => internalTimers[index].Compare0Event,
                            writeCallback: (_, value) => { if(value) internalTimers[index].Compare0Event = false; })
                        .WithFlag(2 * index + 1, name: $"TMR{index}1INTCLR",
                            valueProviderCallback: _ => internalTimers[index].Compare1Event,
                            writeCallback: (_, value) => { if(value) internalTimers[index].Compare1Event = false; })
                    ;

                    interruptSet
                        .WithFlag(2 * index, name: $"TMR{index}0INTSET",
                            valueProviderCallback: _ => internalTimers[index].Compare0Event,
                            writeCallback: (_, value) => { if(value) internalTimers[index].Compare0Event = true; })
                        .WithFlag(2 * index + 1, name: $"TMR{index}1INTSET",
                            valueProviderCallback: _ => internalTimers[index].Compare1Event,
                            writeCallback: (_, value) => { if(value) internalTimers[index].Compare1Event = true; })
                    ;
                }
            }

            Registers.OutputConfig0.DefineMany(this, OutputConfigRegisters, (register, index) =>
            {
                register
                    .WithEnumField(0, 6, out padOutput[index * 4], name: $"OUTCFG{index * 4}")
                    .WithReservedBits(6, 2)
                    .WithEnumField(8, 6, out padOutput[index * 4 + 1], name: $"OUTCFG{index * 4 + 1}")
                    .WithReservedBits(14, 2)
                    .WithEnumField(16, 6, out padOutput[index * 4 + 2], name: $"OUTCFG{index * 4 + 2}")
                    .WithReservedBits(22, 2)
                    .WithEnumField(24, 6, out padOutput[index * 4 + 3], name: $"OUTCFG{index * 4 + 3}")
                    .WithReservedBits(30, 2)
                ;
            });

            Registers.Timer0Control.DefineMany(this, TimersCount, (register, index) =>
            {
                register
                    .WithFlag(0, out timerEnabled[index], name: $"TMR{index}EN",
                        writeCallback: (_, value) =>
                        {
                            UpdateTimerActiveStatus();
                        })
                    .WithFlag(1, FieldMode.WriteOneToClear, name: $"TMR{index}CLR",
                        writeCallback: (_, value) => { if(value) internalTimers[index].Reset(); })
                    .WithTaggedFlag($"TMR{index}POL0", 2)
                    .WithTaggedFlag($"TMR{index}POL1", 3)
                    .WithEnumField(4, 4, out functionSelect[index], name: $"TMR{index}FN",
                        writeCallback: (_, value) =>
                        {
                            internalTimers[index].Pwm = value == FunctionSelect.PWM;
                            switch(value)
                            {
                            case FunctionSelect.Edge: // Adapter restricts primary comparator to UINT32_MAX.
                            case FunctionSelect.Continous:
                                internalTimers[index].OneShot = false;
                                break;
                            case FunctionSelect.PWM:
                                internalTimers[index].OneShot = false;
                                break;
                            case FunctionSelect.Upcount:
                                internalTimers[index].OneShot = true;
                                break;
                            default:
                                this.Log(LogLevel.Error, "Timer{0}: {1} function mode is not supported", index, value);
                                break;
                            }
                        })
                    .WithEnumField<DoubleWordRegister, ClockSelect>(8, 9, name: $"TMR{index}CLK",
                        changeCallback: (_, newValue) =>
                        {
                            var frequency = GetFrequencyAndDivider(newValue, out var divider);
                            internalTimers[index].Frequency = frequency;
                            internalTimers[index].Divider = divider;
                        })
                    .WithEnumField(17, 2, out triggerMode[index], name: $"TMR{index}TMODE")
                    .WithReservedBits(19, 5)
                    .WithTag($"TMR{index}LMT", 24, 8)
                ;
            }, stepInBytes: TimerStructureSize);

            Registers.Timer0.DefineMany(this, TimersCount, (register, index) =>
            {
                register
                    .WithValueField(0, 32, name: $"TIMER{index}",
                        valueProviderCallback: _ =>
                        {
                            if(machine.SystemBus.TryGetCurrentCPU(out var cpu))
                            {
                                cpu.SyncTime();
                            }
                            return (uint)internalTimers[index].Value;
                        },
                        writeCallback: (_, value) => internalTimers[index].Value = (ulong)value)
                ;
            }, stepInBytes: TimerStructureSize);

            Registers.Timer0Compare0.DefineMany(this, TimersCount, (register, index) =>
            {
                register
                    .WithValueField(0, 32, name: $"TMR{index}CMP0",
                        valueProviderCallback: _ => (uint)internalTimers[index].Compare0,
                        writeCallback: (_, value) => internalTimers[index].Compare0 = (ulong)value)
                ;
            }, stepInBytes: TimerStructureSize);

            Registers.Timer0Compare1.DefineMany(this, TimersCount, (register, index) =>
            {
                register
                    .WithValueField(0, 32, name: $"TMR{index}CMP1",
                        valueProviderCallback: _ => (uint)internalTimers[index].Compare1,
                        writeCallback: (_, value) => internalTimers[index].Compare1 = (ulong)value)
                ;
            }, stepInBytes: TimerStructureSize);

            Registers.Timer0Mode.DefineMany(this, TimersCount, (register, index) =>
            {
                register
                    .WithReservedBits(0, 8)
                    .WithEnumField(8, 9, out triggerSource[index], name: $"TMR{index}TRIGSEL")
                    .WithReservedBits(17, 15)
                ;
            }, stepInBytes: TimerStructureSize);
        }

        private IFlagRegisterField[] globalTimerEnabled;

        private readonly IFlagRegisterField[] timerEnabled;

        private readonly IEnumRegisterField<PadOutput>[] padOutput;

        private readonly IEnumRegisterField<FunctionSelect>[] functionSelect;
        private readonly IEnumRegisterField<TriggerMode>[] triggerMode;
        private readonly IEnumRegisterField<TriggerSource>[] triggerSource;

        private readonly InternalTimer[] internalTimers;

        private const int TimerStructureSize = 0x20;
        private const int TimersCount = 16;
        private const long HFRCFrequency = 96000000;
        private const long LFRCFrequency = 900;
        private const long XTFrequency = 32768;
        private const int OutputConfigRegisters = 32;
        private const int OutputConfigFieldsPerRegister = 4;

        private class InternalTimer
        {
            public InternalTimer(IPeripheral parent, IClockSource clockSource, int index)
            {
                compare0Timer = new ComparingTimer(clockSource, 1, parent, $"timer{index}cmp0", limit: 0x100000000UL, compare: 0xFFFFFFFF, enabled: false, eventEnabled: true);
                compare1Timer = new ComparingTimer(clockSource, 1, parent, $"timer{index}cmp1", limit: 0x100000000UL, compare: 0xFFFFFFFF, enabled: false, eventEnabled: true);

                compare0Timer.CompareReached += () =>
                {
                    Compare0Event = true;
                    CompareReached(true);
                };
                compare1Timer.CompareReached += () =>
                {
                    Compare1Event = true;
                    CompareReached(false);
                };
            }

            public void Reset()
            {
                Enabled = false;
                Value = 0;Compare0 = Compare1 = 0;
                Compare0Interrupt = Compare1Interrupt = false;OneShot = Pwm = false;
                Compare0Event = false;
                Compare1Event = false;
            }

            public bool Enabled
            {
                get => compare0Timer.Enabled;
                set
                {
                    if(Enabled == value)
                    {
                        return;
                    }

                    compare0Timer.Enabled = value;
                    compare1Timer.Enabled = value;
                }
            }

            public bool OneShot { get; set; }
            public bool Pwm { get; set; }

            public ulong Value
            {
                get => compare0Timer.Value;
                set
                {
                    compare0Timer.Value = value;
                    compare1Timer.Value = value;
                }
            }

            public ulong Frequency
            {
                get => compare0Timer.Frequency;
                set
                {
                    compare0Timer.Frequency = value;
                    compare1Timer.Frequency = value;
                }
            }

            public ulong Divider
            {
                get => compare0Timer.Divider;
                set
                {
                    compare0Timer.Divider = value;
                    compare1Timer.Divider = value;
                }
            }

            public ulong Compare0
            {
                get => compare0Timer.Compare;
                set => compare0Timer.Compare = value;
            }

            public ulong Compare1
            {
                get => compare1Timer.Compare;
                set => compare1Timer.Compare = value;
            }

            public bool Compare0Event { get; set; }

            public bool Compare1Event { get; set; }

            public bool Compare0Interrupt
            {
                get => compare0Interrupt;
                set => compare0Interrupt = value;
            }

            public bool Compare1Interrupt
            {
                get => compare1Interrupt;
                set => compare1Interrupt = value;
            }

            public Action OnCompare;

            private void CompareReached(bool primary)
            {
                if(Pwm && primary) Value = 0;
                OnCompare?.Invoke();

                if(!Pwm && OneShot)
                {
                    Value = 0;
                }
            }

            private bool compare0Interrupt,compare1Interrupt;
            private readonly ComparingTimer compare0Timer;
            private readonly ComparingTimer compare1Timer;
        }

        private enum TriggerSource
        {
            Timer0Output0 = 0x00,  // Trigger source is TIMER 0 Output 0
            Timer0Output1 = 0x01,  // Trigger source is TIMER 0 Output 1
            Timer1Output0 = 0x02,  // Trigger source is TIMER 1 Output 0
            Timer1Output1 = 0x03,  // Trigger source is TIMER 1 Output 1
            Timer2Output0 = 0x04,  // Trigger source is TIMER 2 Output 0
            Timer2Output1 = 0x05,  // Trigger source is TIMER 2 Output 1
            Timer3Output0 = 0x06,  // Trigger source is TIMER 3 Output 0
            Timer3Output1 = 0x07,  // Trigger source is TIMER 3 Output 1
            Timer4Output0 = 0x08,  // Trigger source is TIMER 4 Output 0
            Timer4Output1 = 0x09,  // Trigger source is TIMER 4 Output 1
            Timer5Output0 = 0x0A,  // Trigger source is TIMER 5 Output 0
            Timer5Output1 = 0x0B,  // Trigger source is TIMER 5 Output 1
            Timer6Output0 = 0x0C,  // Trigger source is TIMER 6 Output 0
            Timer6Output1 = 0x0D,  // Trigger source is TIMER 6 Output 1
            Timer7Output0 = 0x0E,  // Trigger source is TIMER 7 Output 0
            Timer7Output1 = 0x0F,  // Trigger source is TIMER 7 Output 1
            Timer8Output0 = 0x10,  // Trigger source is TIMER 8 Output 0
            Timer8Output1 = 0x11,  // Trigger source is TIMER 8 Output 1
            Timer9Output0 = 0x12,  // Trigger source is TIMER 9 Output 0
            Timer9Output1 = 0x13,  // Trigger source is TIMER 9 Output 1
            Timer10Output0 = 0x14, // Trigger source is TIMER 10 Output 0
            Timer10Output1 = 0x15, // Trigger source is TIMER 10 Output 1
            Timer11Output0 = 0x16, // Trigger source is TIMER 11 Output 0
            Timer11Output1 = 0x17, // Trigger source is TIMER 11 Output 1
            Timer12Output0 = 0x18, // Trigger source is TIMER 12 Output 0
            Timer12Output1 = 0x19, // Trigger source is TIMER 12 Output 1
            Timer13Output0 = 0x1A, // Trigger source is TIMER 13 Output 0
            Timer13Output1 = 0x1B, // Trigger source is TIMER 13 Output 1
            Timer14Output0 = 0x1C, // Trigger source is TIMER 14 Output 0
            Timer14Output1 = 0x1D, // Trigger source is TIMER 14 Output 1
            Timer15Output0 = 0x1E, // Trigger source is TIMER 15 Output 0
            Timer15Output1 = 0x1F, // Trigger source is TIMER 15 Output 1
            STimerCompare0 = 0x30, // Trigger source is STIMER Compare 0
            STimerCompare1 = 0x31, // Trigger source is STIMER Compare 1
            STimerCompare2 = 0x32, // Trigger source is STIMER Compare 2
            STimerCompare3 = 0x33, // Trigger source is STIMER Compare 3
            STimerCompare4 = 0x34, // Trigger source is STIMER Compare 4
            STimerCompare5 = 0x35, // Trigger source is STIMER Compare 5
            STimerCompare6 = 0x36, // Trigger source is STIMER Compare 6
            STimerCompare7 = 0x37, // Trigger source is STIMER Compare 7
            STimerCapture0 = 0x38, // Trigger source is STIMER Capture 0
            STimerCapture1 = 0x39, // Trigger source is STIMER Capture 1
            STimerCapture2 = 0x3A, // Trigger source is STIMER Capture 2
            STimerCapture3 = 0x3B, // Trigger source is STIMER Capture 3
            STimerCapture4 = 0x3C, // Trigger source is STIMER Capture 4
            STimerCapture5 = 0x3D, // Trigger source is STIMER Capture 5
            STimerCapture6 = 0x3E, // Trigger source is STIMER Capture 6
            STimerCapture7 = 0x3F, // Trigger source is STIMER Capture 7
            GPIO0 = 0x80,          // Trigger source is GPIO #0
            GPIO127 = 0xFF,        // Trigger source is GPIO #127
        }

        private enum TriggerMode
        {
            Disable = 0x00,
            RisingEdge = 0x01,
            FallingEdge = 0x02,
            EitherEdge = 0x03,
        }

        private enum ClockSelect
        {
            HFRCDiv16 = 0x01,      // Clock source is HFRC / 16
            HFRCDiv64 = 0x02,      // Clock source is HFRC / 64
            HFRCDiv256 = 0x03,     // Clock source is HFRC / 256
            HFRCDiv1024 = 0x04,    // Clock source is HFRC / 1024
            HFRCDiv4K = 0x05,      // Clock source is HFRC / 4096
            LFRC = 0x06,           // Clock source is LFRC
            LFRCDiv2 = 0x07,       // Clock source is LFRC / 2
            LFRCDiv32 = 0x08,      // Clock source is LFRC / 32
            LFRCDiv1K = 0x09,      // Clock source is LFRC / 1024
            XT = 0x0A,             // Clock source is the XT (uncalibrated).
            XTDiv2 = 0x0B,         // Clock source is XT / 2
            XTDiv4 = 0x0C,         // Clock source is XT / 4
            XTDiv8 = 0x0D,         // Clock source is XT / 8
            XTDiv16 = 0x0E,        // Clock source is XT / 16
            XTDiv32 = 0x0F,        // Clock source is XT / 32
            XTDiv128 = 0x10,       // Clock source is XT / 128
            RTC_100HZ = 0x11,      // Clock source is 100 Hz from the current RTC oscillator.
            BuckC = 0x1C,          // Clock source is Buck VDDC TON pulses.
            BuckF = 0x1D,          // Clock source is Buck VDDF TON pulses.
            BuckS = 0x1E,          // Clock source is Buck VDDS TON pulses.
            BuckCLV = 0x1F,        // Clock source is Buck VDDC_LV TON pulses.
            Timer0Output0 = 0x20,  // Clock source is TIMER 0 Output 0
            Timer0Output1 = 0x21,  // Clock source is TIMER 0 Output 1
            Timer1Output0 = 0x22,  // Clock source is TIMER 1 Output 0
            Timer1Output1 = 0x23,  // Clock source is TIMER 1 Output 1
            Timer2Output0 = 0x24,  // Clock source is TIMER 2 Output 0
            Timer2Output1 = 0x25,  // Clock source is TIMER 2 Output 1
            Timer3Output0 = 0x26,  // Clock source is TIMER 3 Output 0
            Timer3Output1 = 0x27,  // Clock source is TIMER 3 Output 1
            Timer4Output0 = 0x28,  // Clock source is TIMER 4 Output 0
            Timer4Output1 = 0x29,  // Clock source is TIMER 4 Output 1
            Timer5Output0 = 0x2A,  // Clock source is TIMER 5 Output 0
            Timer5Output1 = 0x2B,  // Clock source is TIMER 5 Output 1
            Timer6Output0 = 0x2C,  // Clock source is TIMER 6 Output 0
            Timer6Output1 = 0x2D,  // Clock source is TIMER 6 Output 1
            Timer7Output0 = 0x2E,  // Clock source is TIMER 7 Output 0
            Timer7Output1 = 0x2F,  // Clock source is TIMER 7 Output 1
            Timer8Output0 = 0x30,  // Clock source is TIMER 8 Output 0
            Timer8Output1 = 0x31,  // Clock source is TIMER 8 Output 1
            Timer9Output0 = 0x32,  // Clock source is TIMER 9 Output 0
            Timer9Output1 = 0x33,  // Clock source is TIMER 9 Output 1
            Timer10Output0 = 0x34, // Clock source is TIMER 10 Output 0
            Timer10Output1 = 0x35, // Clock source is TIMER 10 Output 1
            Timer11Output0 = 0x36, // Clock source is TIMER 11 Output 0
            Timer11Output1 = 0x37, // Clock source is TIMER 11 Output 1
            Timer12Output0 = 0x38, // Clock source is TIMER 12 Output 0
            Timer12Output1 = 0x39, // Clock source is TIMER 12 Output 1
            Timer13Output0 = 0x3A, // Clock source is TIMER 13 Output 0
            Timer13Output1 = 0x3B, // Clock source is TIMER 13 Output 1
            Timer14Output0 = 0x3C, // Clock source is TIMER 14 Output 0
            Timer14Output1 = 0x3D, // Clock source is TIMER 14 Output 1
            Timer15Output0 = 0x3E, // Clock source is TIMER 15 Output 0
            Timer15Output1 = 0x3F, // Clock source is TIMER 15 Output 1
            GPIO0 = 0x80,          // GPIO #0 is clock source
            GPIO63 = 0xBF,         // GPIO #63 is clock source
            GPIO95 = 0xDF,         // GPIO #95 is clock source
            GPIO127 = 0xFF,        // GPIO #127 is clock source
        }

        private enum FunctionSelect
        {
            Continous = 0x00,
            Edge = 0x01,
            Upcount = 0x02,
            PWM = 0x04,
            Downcount = 0x06,
            SinglePattern = 0x0C,
            RepeatPattern = 0x0D,
            EventTimer = 0x0E,
        }

        private enum PadOutput
        {
            Timer0Output0 = 0x00,  // Output is Timer 0, output 0
            Timer0Output1 = 0x01,  // Output is Timer 0, output 1
            Timer1Output0 = 0x02,  // Output is Timer 1, output 0
            Timer1Output1 = 0x03,  // Output is Timer 1, output 1
            Timer2Output0 = 0x04,  // Output is Timer 2, output 0
            Timer2Output1 = 0x05,  // Output is Timer 2, output 1
            Timer3Output0 = 0x06,  // Output is Timer 3, output 0
            Timer3Output1 = 0x07,  // Output is Timer 3, output 1
            Timer4Output0 = 0x08,  // Output is Timer 4, output 0
            Timer4Output1 = 0x09,  // Output is Timer 4, output 1
            Timer5Output0 = 0x0A,  // Output is Timer 5, output 0
            Timer5Output1 = 0x0B,  // Output is Timer 5, output 1
            Timer6Output0 = 0x0C,  // Output is Timer 6, output 0
            Timer6Output1 = 0x0D,  // Output is Timer 6, output 1
            Timer7Output0 = 0x0E,  // Output is Timer 7, output 0
            Timer7Output1 = 0x0F,  // Output is Timer 7, output 1
            Timer8Output0 = 0x10,  // Output is Timer 8, output 0
            Timer8Output1 = 0x11,  // Output is Timer 8, output 1
            Timer9Output0 = 0x12,  // Output is Timer 9, output 0
            Timer9Output1 = 0x13,  // Output is Timer 9, output 1
            Timer10Output0 = 0x14, // Output is Timer 10, output 0
            Timer10Output1 = 0x15, // Output is Timer 10, output 1
            Timer11Output0 = 0x16, // Output is Timer 11, output 0
            Timer11Output1 = 0x17, // Output is Timer 11, output 1
            Timer12Output0 = 0x18, // Output is Timer 12, output 0
            Timer12Output1 = 0x19, // Output is Timer 12, output 1
            Timer13Output0 = 0x1A, // Output is Timer 13, output 0
            Timer13Output1 = 0x1B, // Output is Timer 13, output 1
            Timer14Output0 = 0x1C, // Output is Timer 14, output 0
            Timer14Output1 = 0x1D, // Output is Timer 14, output 1
            Timer15Output0 = 0x1E, // Output is Timer 15, output 0
            Timer15Output1 = 0x1F, // Output is Timer 15, output 1
            STimer0 = 0x20,        // Output is STimer 0
            STimer1 = 0x21,        // Output is STimer 1
            STimer2 = 0x22,        // Output is STimer 2
            STimer3 = 0x23,        // Output is STimer 3
            STimer4 = 0x24,        // Output is STimer 4
            STimer5 = 0x25,        // Output is STimer 5
            STimer6 = 0x26,        // Output is STimer 6
            STimer7 = 0x27,        // Output is STimer 7
            Pattern0 = 0x20,       // Output is Pattern Output 0
            Pattern1 = 0x21,       // Output is Pattern Output 1
            Pattern2 = 0x22,       // Output is Pattern Output 2
            Pattern3 = 0x23,       // Output is Pattern Output 3
            Pattern4 = 0x24,       // Output is Pattern Output 4
            Pattern5 = 0x25,       // Output is Pattern Output 5
            Pattern6 = 0x26,       // Output is Pattern Output 6
            Pattern7 = 0x27,       // Output is Pattern Output 7
            Disabled = 0x3F,       // Output is disabled
        }

        private enum Registers : long
        {
            Control = 0x000,         // Counter/Timer Control
            Status = 0x004,          // Counter/Timer Status
            GlobalEnable = 0x010,    // Counter/Timer Global Enable
            InterruptEnable = 0x060, // Counter/Timer Interrupts: Enable
            InterruptStatus = 0x064, // Counter/Timer Interrupts: Status
            InterruptClear = 0x068,  // Counter/Timer Interrupts: Clear
            InterruptSet = 0x06C,    // Counter/Timer Interrupts: Set
            OutputConfig0 = 0x080,   // Counter/Timer Output Config 0
            OutputConfig1 = 0x084,   // Counter/Timer Output Config 0
            OutputConfig2 = 0x088,   // Counter/Timer Output Config 0
            OutputConfig3 = 0x08C,   // Counter/Timer Output Config 0
            OutputConfig4 = 0x090,   // Counter/Timer Output Config 0
            OutputConfig5 = 0x094,   // Counter/Timer Output Config 0
            OutputConfig6 = 0x098,   // Counter/Timer Output Config 0
            OutputConfig7 = 0x09C,   // Counter/Timer Output Config 0
            OutputConfig8 = 0x0A0,   // Counter/Timer Output Config 0
            OutputConfig9 = 0x0A4,   // Counter/Timer Output Config 0
            OutputConfig10 = 0x0A8,  // Counter/Timer Output Config 0
            OutputConfig11 = 0x0AC,  // Counter/Timer Output Config 0
            OutputConfig12 = 0x0B0,  // Counter/Timer Output Config 0
            OutputConfig13 = 0x0B4,  // Counter/Timer Output Config 0
            OutputConfig14 = 0x0B8,  // Counter/Timer Output Config 0
            OutputConfig15 = 0x0BC,  // Counter/Timer Output Config 0
            OutputConfig16 = 0x0C0,  // Counter/Timer Output Config 0
            OutputConfig17 = 0x0C4,  // Counter/Timer Output Config 0
            OutputConfig18 = 0x0C8,  // Counter/Timer Output Config 0
            OutputConfig19 = 0x0CC,  // Counter/Timer Output Config 0
            OutputConfig20 = 0x0D0,  // Counter/Timer Output Config 0
            OutputConfig21 = 0x0D4,  // Counter/Timer Output Config 0
            OutputConfig22 = 0x0D8,  // Counter/Timer Output Config 0
            OutputConfig23 = 0x0DC,  // Counter/Timer Output Config 0
            OutputConfig24 = 0x0E0,  // Counter/Timer Output Config 0
            OutputConfig25 = 0x0E4,  // Counter/Timer Output Config 0
            OutputConfig26 = 0x0E8,  // Counter/Timer Output Config 0
            OutputConfig27 = 0x0EC,  // Counter/Timer Output Config 0
            OutputConfig28 = 0x0F0,  // Counter/Timer Output Config 0
            OutputConfig29 = 0x0F4,  // Counter/Timer Output Config 0
            OutputConfig30 = 0x0F8,  // Counter/Timer Output Config 0
            OutputConfig31 = 0x0FC,  // Counter/Timer Output Config 0
            PatternAddress = 0x104,  // Pattern Address
            Timer0Control = 0x200,   // Counter/Timer Control
            Timer0 = 0x204,          // Counter/Timer
            Timer0Compare0 = 0x208,  // Counter/Timer 0 Primary Comparator
            Timer0Compare1 = 0x20C,  // Counter/Timer 0 Secondary Compare
            Timer0Mode = 0x210,      // Counter/Timer 0 Mode
            Timer1Control = 0x220,   // Counter/Timer Control
            Timer1 = 0x224,          // Counter/Timer
            Timer1Compare0 = 0x228,  // Counter/Timer 1 Primary Comparator
            Timer1Compare1 = 0x22C,  // Counter/Timer 1 Secondary Compare
            Timer1Mode = 0x230,      // Counter/Timer 1 Mode
            Timer2Control = 0x240,   // Counter/Timer Control
            Timer2 = 0x244,          // Counter/Timer
            Timer2Compare0 = 0x248,  // Counter/Timer 2 Primary Comparator
            Timer2Compare1 = 0x24C,  // Counter/Timer 2 Secondary Compare
            Timer2Mode = 0x250,      // Counter/Timer 2 Mode
            Timer3Control = 0x260,   // Counter/Timer Control
            Timer3 = 0x264,          // Counter/Timer
            Timer3Compare0 = 0x268,  // Counter/Timer 3 Primary Comparator
            Timer3Compare1 = 0x26C,  // Counter/Timer 3 Secondary Compare
            Timer3Mode = 0x270,      // Counter/Timer 3 Mode
            Timer4Control = 0x280,   // Counter/Timer Control
            Timer4 = 0x284,          // Counter/Timer
            Timer4Compare0 = 0x288,  // Counter/Timer 4 Primary Comparator
            Timer4Compare1 = 0x28C,  // Counter/Timer 4 Secondary Compare
            Timer4Mode = 0x290,      // Counter/Timer 4 Mode
            Timer5Control = 0x2A0,   // Counter/Timer Control
            Timer5 = 0x2A4,          // Counter/Timer
            Timer5Compare0 = 0x2A8,  // Counter/Timer 5 Primary Comparator
            Timer5Compare1 = 0x2AC,  // Counter/Timer 5 Secondary Compare
            Timer5Mode = 0x2B0,      // Counter/Timer 5 Mode
            Timer6Control = 0x2C0,   // Counter/Timer Control
            Timer6 = 0x2C4,          // Counter/Timer
            Timer6Compare0 = 0x2C8,  // Counter/Timer 6 Primary Comparator
            Timer6Compare1 = 0x2CC,  // Counter/Timer 6 Secondary Compare
            Timer6Mode = 0x2D0,      // Counter/Timer 6 Mode
            Timer7Control = 0x2E0,   // Counter/Timer Control
            Timer7 = 0x2E4,          // Counter/Timer
            Timer7Compare0 = 0x2E8,  // Counter/Timer 7 Primary Comparator
            Timer7Compare1 = 0x2EC,  // Counter/Timer 7 Secondary Compare
            Timer7Mode = 0x2F0,      // Counter/Timer 7 Mode
            Timer8Control = 0x300,   // Counter/Timer Control
            Timer8 = 0x304,          // Counter/Timer
            Timer8Compare0 = 0x308,  // Counter/Timer 8 Primary Comparator
            Timer8Compare1 = 0x30C,  // Counter/Timer 8 Secondary Compare
            Timer8Mode = 0x310,      // Counter/Timer 8 Mode
            Timer9Control = 0x320,   // Counter/Timer Control
            Timer9 = 0x324,          // Counter/Timer
            Timer9Compare0 = 0x328,  // Counter/Timer 9 Primary Comparator
            Timer9Compare1 = 0x32C,  // Counter/Timer 9 Secondary Compare
            Timer9Mode = 0x330,      // Counter/Timer 9 Mode
            Timer10Control = 0x340,  // Counter/Timer Control
            Timer10 = 0x344,         // Counter/Timer
            Timer10Compare0 = 0x348, // Counter/Timer 10 Primary Comparator
            Timer10Compare1 = 0x34C, // Counter/Timer 10 Secondary Compare
            Timer10Mode = 0x350,     // Counter/Timer 10 Mode
            Timer11Control = 0x360,  // Counter/Timer Control
            Timer11 = 0x364,         // Counter/Timer
            Timer11Compare0 = 0x368, // Counter/Timer 11 Primary Comparator
            Timer11Compare1 = 0x36C, // Counter/Timer 11 Secondary Compare
            Timer11Mode = 0x370,     // Counter/Timer 11 Mode
            Timer12Control = 0x380,  // Counter/Timer Control
            Timer12 = 0x384,         // Counter/Timer
            Timer12Compare0 = 0x388, // Counter/Timer 12 Primary Comparator
            Timer12Compare1 = 0x38C, // Counter/Timer 12 Secondary Compare
            Timer12Mode = 0x390,     // Counter/Timer 12 Mode
            Timer13Control = 0x3A0,  // Counter/Timer Control
            Timer13 = 0x3A4,         // Counter/Timer
            Timer13Compare0 = 0x3A8, // Counter/Timer 13 Primary Comparator
            Timer13Compare1 = 0x3AC, // Counter/Timer 13 Secondary Compare
            Timer13Mode = 0x3B0,     // Counter/Timer 13 Mode
            Timer14Control = 0x3C0,  // Counter/Timer Control
            Timer14 = 0x3C4,         // Counter/Timer
            Timer14Compare0 = 0x3C8, // Counter/Timer 14 Primary Comparator
            Timer14Compare1 = 0x3CC, // Counter/Timer 14 Secondary Compare
            Timer14Mode = 0x3D0,     // Counter/Timer 14 Mode
            Timer15Control = 0x3E0,  // Counter/Timer Control
            Timer15 = 0x3E4,         // Counter/Timer
            Timer15Compare0 = 0x3E8, // Counter/Timer 15 Primary Comparator
            Timer15Compare1 = 0x3EC, // Counter/Timer 15 Secondary Compare
            Timer15Mode = 0x3F0,     // Counter/Timer 15 Mode
        }
    }
}
namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals.Timers;
    // Shared engine; optional Timer7 requires the explicit PWM engine candidate.
    public sealed class BlackwallTimer14 : IBlackwallTimer14
    {
        public BlackwallTimer14(IMachine machine,string profile,string timer0Profile="none",string timer7Profile="none",bool idleChannelControls=false)
        {
            if(profile!="nominal-xt-lfrc")throw new ArgumentException("Explicit Timer14 profile required");
            if(timer0Profile!="none" && timer0Profile!="nominal-hfrc96-upcount")throw new ArgumentException("Explicit nominal Timer0 profile required");
            Timer0Enabled=timer0Profile!="none";
            if(timer7Profile!="none" && timer7Profile!="nominal-hfrc96-pwm")throw new ArgumentException("Explicit nominal Timer7 profile required");
            Timer7Enabled=timer7Profile!="none";
            IdleChannelControls=idleChannelControls;engine=new BlackwallApolloTimerEngine(machine);Reset();
        }
        public bool Owns(ulong a)=>IsIdleControl(a) || a==0x40008010 || (a>=0x40008060 && a<=0x4000806c && (a&3)==0) || (a>=0x400083c0 && a<=0x400083d0 && (a&3)==0) || (Timer0Enabled && a>=0x40008200 && a<=0x40008210 && (a&3)==0) || (Timer7Enabled && (a==0x40008110 || (a>=0x400082e0 && a<=0x400082f0 && (a&3)==0)));
        public bool TryRead(ulong a,out uint value)
        {
            value=0;if(!Owns(a) || a==0x40008068 || a==0x4000806c)return false;
            if(IsIdleControl(a))
            {
                value=engine.ReadDoubleWord((long)(a-0x40008000));
                if(value!=0)return false;
                IdleControlReads[(a-0x40008200)/0x20]++;Reads++;return true;
            }
            value=a==0x400083c0 ? Control : a==0x40008200 ? Timer0Control : a==0x400082e0 ? Timer7Control : a==0x40008110 ? Timer7OutputConfig : engine.ReadDoubleWord((long)(a-0x40008000));Reads++;return true;
        }
        public bool TryWrite(ulong a,uint value)
        {
            if(!Owns(a) || IsIdleControl(a))return false;
            var offset=(long)(a-0x40008000);
            if(Timer7Enabled && offset==0x110)
            {
                if((value&~0x7f00u)!=(Timer7OutputConfig&~0x7f00u) || (((value>>8)&0x7f)!=14 && ((value>>8)&0x7f)!=63))return false;
                Timer7OutputConfig=value;Writes++;return true;
            }
            if(Timer7Enabled && offset>=0x2e0 && offset<=0x2f0)
            {
                if(!TryWriteTimer7(offset,value))return false;
                Writes++;return true;
            }
            if(Timer0Enabled && offset>=0x200 && offset<=0x210)
            {
                if(!TryWriteTimer0(offset,value))return false;
                Writes++;return true;
            }
            if(offset==0x3c0)
            {
                var clock=(value>>8)&0x1ff;var fn=(value>>4)&15;
                if(value!=0 && ((value&~0x1ff13u)!=0 || fn!=1 || (clock!=6 && clock!=10)))return false;
                if((value&1)!=0 && !Timer14ConfigurationValid)return false;
                if(Running && clock!=((Control>>8)&0x1ff) && (value&3)!=2 && (value&3)!=3)return false;
                Control=value;
                var effective=value&~2u;if((value&2)!=0)effective&=~1u;
                engine.WriteDoubleWord(offset,effective);
                if((value&2)!=0)engine.WriteDoubleWord(0x3c4,0);
            }
            else if(offset==0x3c4)
            {
                if(Running || (Control&2)!=0)return false;
                engine.WriteDoubleWord(offset,value);
            }
            else if(offset==0x3c8)
            {
                if(Running && value!=0xffffffffu)return false;
                engine.WriteDoubleWord(offset,value);
            }
            else if(offset==0x3cc)
            {
                if(Running && value==0)return false;
                engine.WriteDoubleWord(offset,value);
            }
            else if(offset==0x3d0)
            {if(value!=0)return false;engine.WriteDoubleWord(offset,0);}
            else if(offset==0x10)
            {
                var mask=0x4000u | (Timer0Enabled ? 1u:0u) | (Timer7Enabled ? 0x80u:0u);
                if((value&~mask)!=(0xffffu&~mask))return false;
                if(Timer0Enabled && (value&1)!=0 && (Timer0Control&3)==1 && !Timer0ConfigurationValid)return false;
                if((value&0x4000)!=0 && (Control&3)==1 && !Timer14ConfigurationValid)return false;
                if(Timer7Enabled && (value&0x80)!=0 && (Timer7Control&3)==1 && !Timer7ConfigurationValid)return false;
                engine.WriteDoubleWord(offset,value);
            }
            else
            {var mask=0x30000000u | (Timer0Enabled ? 3u:0u) | (Timer7Enabled ? 0xc000u:0u);if((value&~mask)!=0 || offset==0x64)return false;engine.WriteDoubleWord(offset,value);}
            Writes++;return true;
        }
        private bool TryWriteTimer0(long offset,uint value)
        {
            if(offset==0x200)
            {
                if(value!=0 && (value<0x120 || value>0x123))return false;
                if(value==0 && Timer0Running)return false;
                if((value&1)!=0 && !Timer0ConfigurationValid)return false;
                Timer0Control=value;
                var effective=value&~2u;if((value&2)!=0)effective&=~1u;
                engine.WriteDoubleWord(offset,effective);
                if((value&2)!=0)engine.WriteDoubleWord(0x204,0);
                return true;
            }
            if(offset==0x204) {if(Timer0Running || (Timer0Control&2)!=0)return false;}
            else if(offset==0x208) {if((value!=0 && value!=6000) || (Timer0Running && value!=6000))return false;}
            else if(offset==0x20c) {if((value!=0 && value!=0xffffffff) || (Timer0Running && value!=0xffffffff))return false;}
            else if(offset==0x210) {if((value!=0 && value!=0x100) || (Timer0Running && value!=Timer0Mode))return false;}
            else return false;
            engine.WriteDoubleWord(offset,value);return true;
        }
        private bool TryWriteTimer7(long offset,uint value)
        {
            if(offset==0x2e0)
            {
                if(value!=0 && (value<0x40 || value>0x43))return false;
                if(value==0 && Timer7Running)return false;
                if((value&3)==1 && !Timer7ConfigurationValid)return false;
                Timer7Control=value;
                var effective=value&~2u;if((value&2)!=0)effective&=~1u;
                engine.WriteDoubleWord(offset,effective);
                if((value&2)!=0)engine.WriteDoubleWord(0x2e4,0);
                return true;
            }
            if(offset==0x2e4) {if(Timer7Running || (Timer7Control&2)!=0)return false;}
            else if(offset==0x2e8) {if(Timer7Running && value!=Timer7Compare0)return false;}
            else if(offset==0x2ec) {if(Timer7Running && value!=Timer7Compare1)return false;}
            else if(offset==0x2f0) {if((value!=0 && value!=0x100) || (Timer7Running && value!=Timer7Mode))return false;}
            else return false;
            engine.WriteDoubleWord(offset,value);return true;
        }
        public void Reset() {System.Array.Clear(IdleControlReads,0,16);engine.Reset();Control=Timer0Control=Timer7Control=0;Timer7OutputConfig=0x3f3f3f3f;Reads=Writes=0;}
        private bool Timer7ConfigurationValid=>Timer7Compare0>0 && Timer7Compare0<0xffffffffu && Timer7Compare1>0 && Timer7Compare1<Timer7Compare0 && Timer7Mode==0x100 && Timer7Counter<Timer7Compare0;
        public bool Timer7Enabled {get;}
        public uint Timer7Control {get;private set;}
        public uint Timer7Counter=>engine.ReadDoubleWord(0x2e4);
        public uint Timer7Compare0=>engine.ReadDoubleWord(0x2e8);
        public uint Timer7Compare1=>engine.ReadDoubleWord(0x2ec);
        public uint Timer7Mode=>engine.ReadDoubleWord(0x2f0);
        public uint Timer7OutputConfig {get;private set;}
        public uint Timer7Pad145Selector=>(Timer7OutputConfig>>8)&0x7f;
        public bool Timer7Running=>(Timer7Control&3)==1 && (GlobalEnable&0x80)!=0;
        // Sampled logical phase only; no physical pin/electrical signal is modeled.
        public bool Timer7Output0=>Timer7Running && Timer7Counter>=Timer7Compare1;
        public bool Timer7Output1=>Timer7Running && !Timer7Output0;
        public ulong Timer7Frequency=>((Timer7Control>>4)&15)==4 ? 24000000UL:0UL;
        public GPIO Timer7IRQ=>(GPIO)engine.Connections[7];
        private bool Timer0ConfigurationValid=>Timer0Compare0==6000 && Timer0Compare1==0xffffffff && Timer0Mode==0x100;
        private bool Timer14ConfigurationValid=>Compare0==0xffffffffu && Compare1!=0;
        public bool Timer0Enabled {get;}
        public uint Timer0Control {get;private set;}
        public uint Timer0Counter=>engine.ReadDoubleWord(0x204);
        public uint Timer0Compare0=>engine.ReadDoubleWord(0x208);
        public uint Timer0Compare1=>engine.ReadDoubleWord(0x20c);
        public uint Timer0Mode=>engine.ReadDoubleWord(0x210);
        public bool Timer0Running=>(Timer0Control&3)==1 && (GlobalEnable&1)!=0;
        public ulong Timer0Frequency=>((Timer0Control>>8)&0x1ff)==1 ? 6000000UL:0UL;
        public GPIO Timer0IRQ=>(GPIO)engine.Connections[0];
        public uint Control {get;private set;}
        public uint Counter=>engine.ReadDoubleWord(0x3c4);
        public uint Compare0=>engine.ReadDoubleWord(0x3c8);
        public uint Compare1=>engine.ReadDoubleWord(0x3cc);
        public uint GlobalEnable=>engine.ReadDoubleWord(0x10);
        public uint Enable=>engine.ReadDoubleWord(0x60);
        public uint Status=>engine.ReadDoubleWord(0x64);
        public ulong Frequency=>((Control>>8)&0x1ff)==6 ? 900UL : ((Control>>8)&0x1ff)==10 ? 32768UL : 0UL;
        public bool Running=>(Control&3)==1 && (GlobalEnable&0x4000)!=0;
        public GPIO IRQ=>(GPIO)engine.Connections[14];
        public uint Reads {get;private set;}
        public uint Writes {get;private set;}
        public bool IdleChannelControls {get;}
        public uint[] IdleControlReads {get;}=new uint[16];
        private bool IsIdleControl(ulong a)
        {
            if(!IdleChannelControls || a<0x40008200 || a>0x400083e0 || ((a-0x40008200)&31)!=0)return false;
            var n=(a-0x40008200)/32;
            return n!=14 && (n!=0 || !Timer0Enabled) && (n!=7 || !Timer7Enabled);
        }
        private readonly BlackwallApolloTimerEngine engine;
    }
}

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
                    program.ResetValue();program.Enabled=CompletePageProgram;
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
        public void Reset()
        {
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
            uint page=address&~255u;
            for(uint i=0;i<(uint)bytes.Length;i++)contents[(page|(((address&255u)+i)&255u))-Start]&=bytes[i];
            return true;
        }
        // This emulator reset preserves committed NOR bytes, as distinct from volatile controller state.
        public void Reset() { }
        private readonly byte[] contents;
        public bool AllowSectorErase {get;}
        public bool AllowPageProgram {get;}
        public BlackwallNorReadWindow AdditionalWindow {get;}
        public string Profile {get;}
        public uint Start {get;}
        public uint Length {get;}
    }
}

namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using Antmicro.Renode.Core;

    public sealed class BlackwallUartDmaTx : IBlackwallUartDmaTx
    {
        public BlackwallUartDmaTx(IMachine machine,string profile="sram-tx-complete")
        {
            if(profile!="sram-tx-complete" && profile!="sram-tx-stalled")throw new ArgumentException("Unknown SRAM UART DMA TX profile");
            this.machine=machine;Profile=profile;Reset();
        }
        public void Bind(BlackwallUartAdapter adapter)
        {
            if(owner!=null || adapter==null || adapter.Module!=0 || !adapter.InterruptsEnabled || !adapter.IdleDmaInterrupts)throw new ArgumentException("One UART0 DMA owner required");
            owner=adapter;
        }
        public bool Owns(long offset) => offset==4 || offset==0x48 || offset==0x4c || offset==0x50;
        public bool TryRead(long offset,out uint value)
        {
            value=0;
            if(offset==4)value=Status;
            else if(offset==0x48)value=Control;
            else if(offset==0x4c)value=Target;
            else if(offset==0x50)value=Count;
            else return false;
            return true;
        }
        public bool TryWrite(long offset,uint value)
        {
            if(offset==4)
            {
                if((value&~0x3fu)!=0 || ((value&0x30u)&~Status)!=0)return false;
                Status=value&0x30u;return true;
            }
            if(offset==0x4c)
            {
                if((Control&2)!=0 || Busy || value<0x20000000 || value>=0x20380000)return false;
                Target=value;targetSet=true;return true;
            }
            if(offset==0x50)
            {
                if((Control&2)!=0 || Busy || value>4095)return false;
                Count=value;countSet=true;return true;
            }
            if(offset!=0x48 || (value!=0 && value!=8 && value!=2 && value!=10))return false;
            if(value==0)
            {
                if(Busy) { Cancellations++;Phase="cancelled"; }
                else Phase="stopped";
                Control=0;targetSet=countSet=false;return true;
            }
            if(value==8)
            {
                if((Control&2)!=0 || Busy)return false;
                Control=8;return true;
            }
            if((Control!=0 && Control!=8) || Busy || owner==null || !targetSet || !countSet || Count==0
                || (ulong)Target+Count>0x20380000 || Status!=0 || RawInterrupts!=0 || !owner.CanDmaTransmit(Count))return false;
            if(Profile=="sram-tx-stalled") { Control=value;Starts++;Phase="running";return true; }
            var bytes=new byte[Count];
            for(uint index=0;index<Count;index++)bytes[index]=machine.SystemBus.ReadByte(Target+index);
            if(!owner.TransmitDma(bytes))return false;
            Transfers.Add(new Transfer(Target,bytes));
            Control=value;Starts++;TransferredBytes+=Count;Completions++;Status=0x10;RawInterrupts=0x800;Phase="completed";
            return true;
        }
        public void ClearInterrupts(uint mask) { RawInterrupts&=~(mask&0x1800u); }
        private void ClearState()
        {
            Target=Count=Control=Status=RawInterrupts=0;targetSet=countSet=false;Phase="idle";
        }
        public void Reset() { Starts=Completions=Cancellations=0;TransferredBytes=0;Transfers.Clear();ClearState(); }
        public void PowerDown() { if(Busy)Cancellations++;ClearState(); }
        public string Profile { get; }
        public string Phase { get; private set; }
        public bool Busy => Phase=="running";
        public uint Control { get; private set; }
        public uint Target { get; private set; }
        public uint Count { get; private set; }
        public uint Status { get; private set; }
        public uint RawInterrupts { get; private set; }
        public uint Starts { get; private set; }
        public uint Completions { get; private set; }
        public uint Cancellations { get; private set; }
        public ulong TransferredBytes { get; private set; }
        public System.Collections.Generic.List<Transfer> Transfers { get; } = new System.Collections.Generic.List<Transfer>();
        public sealed class Transfer
        {
            public Transfer(uint target,byte[] data) { Target=target;Data=data; }
            public uint Target { get; }
            public byte[] Data { get; }
        }
        private bool targetSet,countSet;
        private readonly IMachine machine;
        private BlackwallUartAdapter owner;
    }
}

namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using Antmicro.Renode.Peripherals.I2C;

    // Explicit synthetic version/config and optional one-frame input; no physical defaults or DFU.
    public sealed class BlackwallIomRegisterProbe : II2CPeripheral
    {
        public BlackwallIomRegisterProbe(BlackwallStrictIom owner,string profile,int initialGestureThreshold=-1,bool eventPointerProbe=false,string eventFrameHex=null)
        {
            if(owner==null || owner.Module!=5 || (profile!="pointer-01-only" && profile!="package-version-only" && profile!="touch-startup-config"))throw new ArgumentException("Explicit IOM5 diagnostic profile required");
            if(profile=="touch-startup-config" ? initialGestureThreshold<0 || initialGestureThreshold>65535 : initialGestureThreshold!=-1)throw new ArgumentException("Explicit startup threshold required only for touch-startup-config");
            if(eventPointerProbe && profile!="touch-startup-config")throw new ArgumentException("Event pointer probe requires explicit startup profile");
            if(eventFrameHex!=null)
            {
                if(!eventPointerProbe || eventFrameHex.Length!=32)throw new ArgumentException("One explicit 16-byte event requires the startup event profile");
                foreach(var c in eventFrameHex)if(!Uri.IsHexDigit(c))throw new ArgumentException("Event frame must be hexadecimal");
                eventFrame=new byte[16];
                for(var i=0;i<16;i++)eventFrame[i]=Convert.ToByte(eventFrameHex.Substring(i*2,2),16);
            }
            this.owner=owner;Profile=profile;InitialGestureThreshold=initialGestureThreshold;EventPointerProbe=eventPointerProbe;Reset();
        }
        public void Reset()
        {
            PointerSelected=false;Pointer=0;PointerWrites=ReadAttempts=Finishes=LastReadCount=VersionReads=ReturnedBytes=GestureReads=ConfigWrites=StatusReads=0;LastReadPointer=-1;readConsumed=false;ConfigReplyPending=false;GestureThreshold=InitialGestureThreshold<0 ? (ushort)0:(ushort)InitialGestureThreshold;
            EventReadOffset=EventReadChunks=EventFramesCompleted=0;
        }
        public void Write(byte[] data)
        {
            if(EventFrameEnabled && ((EventReadOffset>0 && EventReadOffset<16) ||
                (data!=null && data.Length==1 && data[0]==3 && EventFramesCompleted!=0)))
            { owner.RejectDiagnosticPeerAccess("peer-write",data==null ? 0u:(uint)data.Length);return; }
            if(Profile=="touch-startup-config" && !ConfigReplyPending && data!=null && data.Length==3 && data[0]==7)
            {
                var threshold=(ushort)(data[1]|(data[2]<<8));
                if(threshold==0) {owner.RejectDiagnosticPeerAccess("peer-write",3);return;}
                GestureThreshold=threshold;ConfigWrites++;ConfigReplyPending=true;Pointer=7;PointerSelected=true;readConsumed=false;return;
            }
            if(ConfigReplyPending || data==null || data.Length!=1 || (data[0]!=1 && !(Profile=="touch-startup-config" && (data[0]==8 || (EventPointerProbe && data[0]==3)))))
            {
                owner.RejectDiagnosticPeerAccess("peer-write",data==null ? 0u:(uint)data.Length);return;
            }
            Pointer=data[0];PointerSelected=true;PointerWrites++;readConsumed=false;
        }
        public byte[] Read(int count=1)
        {
            ReadAttempts++;LastReadCount=count;LastReadPointer=PointerSelected ? (int)Pointer:-1;
            if(EventFrameEnabled && PointerSelected && Pointer==3 && !readConsumed && count==4)
            {
                // Inspect the existing engine's read-only CMDSTATUS, without adding a guest read.
                var status=((Antmicro.Renode.Peripherals.SPI.BlackwallPollingIomEngine)owner).ReadDoubleWord(0x12c);
                if((status&31)!=2 || ((status>>8)&0xfff)!=(uint)(16-EventReadOffset))
                { owner.RejectDiagnosticPeerAccess("peer-read",unchecked((uint)count));return new byte[0]; }
                var chunk=new byte[4];Array.Copy(eventFrame,EventReadOffset,chunk,0,4);
                EventReadOffset+=4;EventReadChunks++;ReturnedBytes+=4;
                if(EventReadOffset==16) { readConsumed=true;EventFramesCompleted++; }
                return chunk;
            }
            if(ConfigReplyPending && count==3)
            {
                ConfigReplyPending=false;readConsumed=true;StatusReads++;ReturnedBytes+=3;
                return new byte[] {7,0,0x17};
            }
            if(Profile=="touch-startup-config" && PointerSelected && Pointer==8 && !readConsumed && count==2)
            {
                readConsumed=true;GestureReads++;ReturnedBytes+=2;
                return new byte[] {(byte)GestureThreshold,(byte)(GestureThreshold>>8)};
            }
            if(Profile!="pointer-01-only" && PointerSelected && Pointer==1 && !readConsumed && count==4)
            {
                readConsumed=true;VersionReads++;ReturnedBytes+=4;
                return new byte[] {2,2,9,0};
            }
            owner.RejectDiagnosticPeerAccess("peer-read",unchecked((uint)count));
            return new byte[0];
        }
        public void FinishTransmission() { Finishes++; }
        public bool PointerSelected {get;private set;}
        public byte Pointer {get;private set;}
        public int PointerWrites {get;private set;}
        public int ReadAttempts {get;private set;}
        public int LastReadCount {get;private set;}
        public int LastReadPointer {get;private set;}
        public int Finishes {get;private set;}
        public string Profile {get;}
        public int VersionReads {get;private set;}
        public int ReturnedBytes {get;private set;}
        public int InitialGestureThreshold {get;}
        public ushort GestureThreshold {get;private set;}
        public int GestureReads {get;private set;}
        public int ConfigWrites {get;private set;}
        public int StatusReads {get;private set;}
        public bool ConfigReplyPending {get;private set;}
        public bool EventPointerProbe {get;}
        public bool EventFrameEnabled=>eventFrame!=null;
        public int EventReadOffset {get;private set;}
        public int EventReadChunks {get;private set;}
        public int EventFramesCompleted {get;private set;}
        private readonly byte[] eventFrame;
        private bool readConsumed;
        private readonly BlackwallStrictIom owner;
    }
}

namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals.CPU;
    using Antmicro.Renode.Time;
    using System.Linq;

    // Original host expectations with explicit, unmeasured timing fixtures. No SPI peer.
    public sealed class BlackwallEm9305ResetHypothesis : IBlackwallEm9305Reset
    {
        public BlackwallEm9305ResetHypothesis(IMachine machine,string profile,uint fallPc,uint risePc,uint headerPc,
            uint minimumResetMicroseconds,uint busyAfterMicroseconds,uint readyAfterMicroseconds,BlackwallEm9305EventPeer hciPeer=null,uint payloadPc=0,uint idlePc=0,uint writePc=0,uint writeConfirmPc=0,uint replyWaitPc=0,uint applicationIdlePc=0,uint applicationReplyDrainPc=0)
        {
            if(machine==null || (profile!="nominal-reset-hypothesis" && profile!="never-low" && profile!="never-ready")
                || minimumResetMicroseconds==0 || minimumResetMicroseconds>1000000
                || busyAfterMicroseconds==0 || readyAfterMicroseconds<=busyAfterMicroseconds || readyAfterMicroseconds>1000000
                || !ValidPc(fallPc) || !ValidPc(risePc) || !ValidPc(headerPc)
                || fallPc==risePc || fallPc==headerPc || risePc==headerPc)
                throw new ArgumentException("Explicit original GPIO consumers and bounded unmeasured reset timing required");
            if(hciPeer!=null && (!ValidPc(payloadPc) || !ValidPc(idlePc) || payloadPc==idlePc || payloadPc==headerPc || idlePc==headerPc))throw new ArgumentException("Distinct original HCI phase consumers required");
            if(hciPeer!=null && hciPeer.HasReadScenario && (!ValidPc(writePc) || !ValidPc(writeConfirmPc) || !ValidPc(replyWaitPc) || new uint[]{fallPc,risePc,headerPc,payloadPc,idlePc,writePc,writeConfirmPc,replyWaitPc}.Distinct().Count()!=8))throw new ArgumentException("Distinct pinned write/reply consumers required");
            if(applicationIdlePc!=0 && (hciPeer==null || !hciPeer.HasVersionScenario || !ValidPc(applicationIdlePc)
                || new uint[]{fallPc,risePc,headerPc,payloadPc,idlePc,writePc,writeConfirmPc,replyWaitPc}.Contains(applicationIdlePc)))
                throw new ArgumentException("Application idle requires the explicit completed version scenario and distinct source PC");
            if(applicationReplyDrainPc!=0 && (applicationIdlePc==0 || !hciPeer.HasApplicationResetScenario || !ValidPc(applicationReplyDrainPc)
                || new uint[]{fallPc,risePc,headerPc,payloadPc,idlePc,writePc,writeConfirmPc,replyWaitPc,applicationIdlePc}.Contains(applicationReplyDrainPc)))
                throw new ArgumentException("Application reply drain requires an explicit Reset scenario and distinct source PC");
            HciPeer=hciPeer;PayloadPc=payloadPc;IdlePc=idlePc;WritePc=writePc;WriteConfirmPc=writeConfirmPc;ReplyWaitPc=replyWaitPc;
            ApplicationIdlePc=applicationIdlePc;ApplicationReplyDrainPc=applicationReplyDrainPc;
            this.machine=machine;Profile=profile;FallPc=fallPc;RisePc=risePc;HeaderPc=headerPc;
            MinimumResetMicroseconds=minimumResetMicroseconds;BusyAfterMicroseconds=busyAfterMicroseconds;ReadyAfterMicroseconds=readyAfterMicroseconds;
            Reset();
        }
        private static bool ValidPc(uint pc)=>pc>=0x438000 && pc<0x800000 && (pc&1)==0;
        public void Attach(BlackwallGpioOutputLatch output)
        {
            if(attached || output==null)throw new ArgumentException("Reset output must attach exactly once");
            attached=true;
            output.OutputWritten+=(pin,high)=>{if(pin==93)SetReset(high,Now());};
            HciPeer?.Attach(output);
        }
        private ulong Now()
        {
            if(machine.SystemBus.TryGetCurrentCPU(out var cpu))cpu.SyncTime();
            return machine.ElapsedVirtualTime.TimeElapsed.Ticks/(TimeInterval.TicksPerMillisecond/1000);
        }
        public void SetReset(bool high,ulong microseconds)
        {
            if(microseconds<LastMicroseconds)throw new ArgumentException("Reset time cannot go backwards");
            LastMicroseconds=microseconds;ResetWrites++;
            if(!high)
            {
                if(!Held)AssertedAt=microseconds;
                Held=true;Released=false;HciPeer?.HoldReset();Phase="held-reset";return;
            }
            if(!Held)return;
            Held=false;ReleasedAt=microseconds;
            Released=microseconds-AssertedAt>=MinimumResetMicroseconds;
            HciPeer?.QualifiedRelease(Released);
            Phase=Released ? "released" : "reset-too-short";
        }
        public bool TrySample(ulong microseconds,uint configuration,out uint value)
        {
            value=0;
            if(microseconds<LastMicroseconds || !Released || Held || (configuration!=0x2093 && configuration!=0x93))return false;
            LastMicroseconds=microseconds;var elapsed=microseconds-ReleasedAt;
            if(Profile=="never-low" || elapsed<BusyAfterMicroseconds)
            {
                Phase="high-impedance";
                if(configuration!=0x2093)return false;
                value=1u<<21;
            }
            else if(Profile=="never-ready" || elapsed<ReadyAfterMicroseconds)Phase="busy-low";
            else {Phase="ready-high";value=1u<<21;}
            Samples++;return true;
        }
        public bool TryRead(ulong address,uint configuration,out uint value)
        {
            value=0;
            if(address!=0x40010410 || !machine.SystemBus.TryGetCurrentCPU(out var current))return false;
            var cpu=current as CortexM;if(cpu==null)return false;
            var pc=(uint)cpu.PC.RawValue;
            if(ApplicationIdlePc!=0 && (pc==ApplicationIdlePc || pc==ApplicationReplyDrainPc))
            {
                if(cpu.GetRegister(0).RawValue!=address)return false;
                return TryApplicationIdleSample(pc,address,configuration,out value);
            }
            if(pc==FallPc || pc==RisePc)
            {
                if(cpu.GetRegister(6).RawValue!=address)return false;
                LastReadPc=pc;return TrySample(Now(),configuration,out value);
            }
            var writeConsumer=HciPeer!=null && HciPeer.HasReadScenario && (pc==WritePc || pc==WriteConfirmPc || pc==ReplyWaitPc);
            if(cpu.GetRegister(writeConsumer?0:8).RawValue!=address)return false;
            if(HciPeer!=null)
            {
                if((pc!=HeaderPc && pc!=PayloadPc && pc!=IdlePc && !writeConsumer) || !Released || Held || configuration!=0x93)return false;
                var level=HciPeer.ReadyLevel;if(level<0)return false;
                LastReadPc=pc;value=level==1?1u<<21:0;Samples++;Phase="hci-"+HciPeer.State;return true;
            }
            if(pc!=HeaderPc)return false;
            LastReadPc=pc;return TrySample(Now(),configuration,out value);
        }
        public bool TryApplicationIdleSample(uint pc,ulong address,uint configuration,out uint value)
        {
            value=0;
            if(ApplicationIdlePc==0 || (pc!=ApplicationIdlePc && (ApplicationReplyDrainPc==0 || pc!=ApplicationReplyDrainPc)) || address!=0x40010410 || configuration!=0x93
                || !Released || Held || HciPeer==null || !HciPeer.HasVersionScenario
                || !HciPeer.CsKnown || !HciPeer.CsHigh)return false;
            var reset=HciPeer.HasApplicationResetScenario;
            if(HciPeer.RuntimeEventPending && HciPeer.ReadyLevel==1)
            {
                value=1u<<21;Phase="application-runtime-event-ready";Samples++;LastReadPc=pc;return true;
            }
            if(pc==ApplicationReplyDrainPc)
            {
                if(reset && HciPeer.PendingP256Completion)
                {
                    value=1u<<21;Phase="application-reply-pending";
                }
                else
                {
                    if(!reset || (HciPeer.State!="Complete" && HciPeer.State!="Consumed") || HciPeer.CommandsAccepted<3
                        || HciPeer.CommandsAccepted>HciPeer.CommandLimit || HciPeer.Replies!=HciPeer.ExpectedReplyEvents || HciPeer.ReadyLevel!=0)return false;
                    Phase="application-reply-drained";
                }
                ApplicationDrainReads++;
            }
            else
            {
                var idle=HciPeer.State=="Complete" && HciPeer.ReadyLevel==0;
                var beforeReset=reset && HciPeer.State=="Consumed" && HciPeer.CommandsAccepted>=2
                    && HciPeer.CommandsAccepted<HciPeer.CommandLimit && HciPeer.Replies==HciPeer.ExpectedReplyEvents && HciPeer.ReadyLevel==0;
                var replyReady=reset && HciPeer.State=="ReplyQueued" && HciPeer.CommandsAccepted>=3
                    && HciPeer.CommandsAccepted<=HciPeer.CommandLimit
                    && HciPeer.Replies==(HciPeer.HasP256PublicKeyScenario && HciPeer.CommandsAccepted==22?21+HciPeer.P256EventsConsumed:HciPeer.ExpectedReplyEvents-1)
                    && HciPeer.ReadyLevel==1;
                if(!idle && !beforeReset && !replyReady)return false;
                value=replyReady?1u<<21:0;ApplicationIdleReads++;Phase=replyReady?"application-reply-ready":"application-idle-no-rx";
            }
            Samples++;LastReadPc=pc;return true;
        }
        public void Reset()
        {
            HciPeer?.Reset();
            Held=Released=false;AssertedAt=ReleasedAt=LastMicroseconds=0;ResetWrites=Samples=LastReadPc=ApplicationIdleReads=ApplicationDrainReads=0;Phase="unknown";
        }
        public BlackwallEm9305EventPeer HciPeer {get;}
        public uint ApplicationIdlePc {get;}
        public uint ApplicationIdleReads {get;private set;}
        public uint ApplicationReplyDrainPc {get;}
        public uint ApplicationDrainReads {get;private set;}
        public uint WritePc {get;}
        public uint WriteConfirmPc {get;}
        public uint ReplyWaitPc {get;}
        public uint PayloadPc {get;}
        public uint IdlePc {get;}
        public string Profile { get; }
        public uint FallPc { get; }
        public uint RisePc { get; }
        public uint HeaderPc { get; }
        public uint MinimumResetMicroseconds { get; }
        public uint BusyAfterMicroseconds { get; }
        public uint ReadyAfterMicroseconds { get; }
        public bool Held { get; private set; }
        public bool Released { get; private set; }
        public ulong AssertedAt { get; private set; }
        public ulong ReleasedAt { get; private set; }
        public ulong LastMicroseconds { get; private set; }
        public uint ResetWrites { get; private set; }
        public uint Samples { get; private set; }
        public uint LastReadPc { get; private set; }
        public string Phase { get; private set; }
        private readonly IMachine machine;
        private bool attached;
    }
}

namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using System.Linq;
    using Antmicro.Renode.Peripherals;

    public sealed class BlackwallEm9305RuntimeLink : IPeripheral
    {
        public BlackwallEm9305RuntimeLink(BlackwallEm9305EventPeer peer,BlackwallG2StartupFixture owner)
        {
            if(peer==null || owner==null || owner.GpioConfig==null || owner.GpioInterrupts==null || !owner.GpioInterrupts.RuntimePin117)
                throw new ArgumentException("Runtime link requires the existing configured GPIO owner and explicit pin117 IRQ profile");
            this.peer=peer;this.owner=owner;
            peer.AttachRuntimeInput(Configured,high=>{
                if(!owner.GpioInterrupts.TrySetPin117(high,!high || Configured()))throw new InvalidOperationException("Runtime ready input lost its configured owner");
            });
        }
        private bool Configured()
        {
            uint cfg;
            return owner.GpioConfig.Values.TryGetValue(0x400101d4,out cfg) && cfg==0x93 && (owner.GpioInterrupts.EnableWords[3]&(1u<<21))!=0;
        }
        public bool TryQueueConnection()=>peer.TryQueueRuntimeConnection();
        public void Reset() { }
        private readonly BlackwallEm9305EventPeer peer;
        private readonly BlackwallG2StartupFixture owner;
    }

    // Explicit source-supported active-event scenario. Not controller firmware,
    // physical CS wiring, or RDY timing. IOM finish and GPIO release are distinct.
    public sealed class BlackwallEm9305EventPeer : IBlackwallReceiveSpiPeer
    {
        public BlackwallEm9305EventPeer(string eventHex,bool payloadReady=true,string readDataHex=null,int writeCapacity=9,string versionDataHex=null,int versionStatus=0,bool applicationReset=false,string vendorStartupHex=null,bool standardInitialization=false,string controllerInformationProfile=null,string privacyInitializationProfile=null,string p256PublicKeyProfile=null,string aesInitializationHex=null,string advertisingInitializationHex=null,string runtimeConnectionEventHex=null,string runtimeAttPacketsHex=null,string runtimeHostAclHex=null,string runtimeRandHex=null,int runtimeRssi=-129,string runtimeRemoteFeaturesHex=null,string runtimeDisconnectEventHex=null)
        {
            bytes=Parse(eventHex,4);PayloadReady=payloadReady;
            if(writeCapacity<0 || writeCapacity>32)throw new ArgumentException("Explicit capacity 0..32 required");
            WriteCapacity=writeCapacity;
            if(readDataHex!=null)
            {
                data=Parse(readDataHex,8);reply=new byte[15];new byte[]{4,14,12,1,1,253,0}.CopyTo(reply,0);data.CopyTo(reply,7);
            }
            if(versionStatus<0 || versionStatus>255 || versionDataHex==null && versionStatus!=0 || versionDataHex!=null && data==null)
                throw new ArgumentException("Version response requires explicit first read and byte status");
            VersionStatus=versionStatus;
            if(versionDataHex!=null)
            {
                versionData=Parse(versionDataHex,4);versionReply=new byte[11];new byte[]{4,14,8,1,1,253,(byte)versionStatus}.CopyTo(versionReply,0);versionData.CopyTo(versionReply,7);
            }
            if(applicationReset && (versionData==null || versionStatus!=0))throw new ArgumentException("Application Reset requires a successful explicit version scenario");
            HasApplicationResetScenario=applicationReset;
            if(vendorStartupHex!=null)
            {
                var packed=Parse(vendorStartupHex,27);
                var features=new byte[]{255,packed[15],1,15,184,25,0,0};
                if(!applicationReset || !packed.Take(4).SequenceEqual(new byte[]{1,67,252,6}) || !packed.Skip(4).Take(6).Any(b=>b!=0)
                    || !packed.Skip(10).Take(4).SequenceEqual(new byte[]{1,242,255,8}) || (packed[15]!=124 && packed[15]!=125)
                    || !packed.Skip(14).Take(8).SequenceEqual(features) || !packed.Skip(22).Take(5).SequenceEqual(new byte[]{1,196,252,1,6}))
                    throw new ArgumentException("Explicit source-supported address/feature/power startup sequence required");
                startupCommands=new byte[][]{packed.Take(10).ToArray(),packed.Skip(10).Take(12).ToArray(),packed.Skip(22).Take(5).ToArray()};
            }
            if(standardInitialization)
            {
                if(startupCommands==null)throw new ArgumentException("Standard initialization requires the explicit vendor/address scenario");
                var identityReply=new byte[13];new byte[]{4,14,10,1,9,16,0}.CopyTo(identityReply,0);
                startupCommands[0].Skip(4).Take(6).ToArray().CopyTo(identityReply,7);
                standardReplies=new byte[][]{Parse("040e0401010c00",7),Parse("040e0401012000",7),Parse("040e0401630c00",7),identityReply};
            }
            if(controllerInformationProfile!=null)
            {
                if(standardReplies==null || (controllerInformationProfile!="le-basic-27x4" && controllerInformationProfile!="le-large-251x8"))
                    throw new ArgumentException("Explicit source-supported mock controller information profile required");
                ControllerInformationProfile=controllerInformationProfile;
                MockAclLength=controllerInformationProfile=="le-basic-27x4"?27:251;
                MockAclPackets=controllerInformationProfile=="le-basic-27x4"?4:8;
                var features=new byte[15];new byte[]{4,14,12,1,3,32,0}.CopyTo(features,0);
                startupCommands[1].Skip(4).Take(8).ToArray().CopyTo(features,7);
                informationReplies=new byte[][]{
                    new byte[]{4,14,7,1,2,32,0,(byte)MockAclLength,(byte)(MockAclLength>>8),(byte)MockAclPackets},
                    Parse("040e0c011c2000ff01000000000000",15),Parse("040e05010f200004",8),features};
            }
            if(privacyInitializationProfile!=null)
            {
                if(informationReplies==null || (privacyInitializationProfile!="test-max-251" && privacyInitializationProfile!="test-min-27"))
                    throw new ArgumentException("Privacy initialization requires explicit mock information and a test-only profile");
                PrivacyInitializationProfile=privacyInitializationProfile;
                var minimum=privacyInitializationProfile=="test-min-27";
                var length=minimum?27:251;var time=minimum?328:2120;
                privacyCommands=new byte[][]{Parse("012a2000",4),Parse("012f2000",4),
                    new byte[]{1,36,32,4,(byte)length,0,(byte)time,(byte)(time>>8)},
                    Parse("01182000",4),Parse("01182000",4),Parse("01182000",4),Parse("01182000",4)};
                var maxima=new byte[]{(byte)length,0,(byte)time,(byte)(time>>8)};
                var maximumReply=new byte[15];new byte[]{4,14,12,1,47,32,0}.CopyTo(maximumReply,0);
                maxima.CopyTo(maximumReply,7);maxima.CopyTo(maximumReply,11);
                privacyReplies=new byte[7][];
                privacyReplies[0]=new byte[]{4,14,5,1,42,32,0,(byte)(minimum?1:4)};
                privacyReplies[1]=maximumReply;privacyReplies[2]=Parse("040e0401242000",7);
                for(var n=0;n<4;n++)
                {
                    // Public deterministic fixture, never production entropy or device secrets.
                    var randomReply=new byte[15];new byte[]{4,14,12,1,24,32,0}.CopyTo(randomReply,0);
                    for(var j=0;j<8;j++)randomReply[7+j]=(byte)(1+n*8+j);
                    privacyReplies[3+n]=randomReply;
                }
            }
            if(p256PublicKeyProfile!=null)
            {
                if(privacyReplies==null || (p256PublicKeyProfile!="test-generator" && p256PublicKeyProfile!="test-error"))
                    throw new ArgumentException("P256 events require explicit test-only privacy and public-point profiles");
                P256PublicKeyProfile=p256PublicKeyProfile;
                var failed=p256PublicKeyProfile=="test-error";
                var completion=new byte[69];new byte[]{4,62,66,8,(byte)(failed?1:0)}.CopyTo(completion,0);
                if(!failed)Parse("96c298d84539a1f4a033eb2d817d0377f240a463e5e6bcf847422ce1f2d1176bf551bf376840b6cbce5e316b5733ce2b169e0f7c4aebe78e9b7f1afee242e34f",64).CopyTo(completion,5);
                p256Replies=new byte[][]{Parse("040f0400012520",7),completion};
            }
            if(aesInitializationHex!=null)
            {
                if(P256PublicKeyProfile!="test-generator")throw new ArgumentException("AES initialization requires the explicit public test-point scenario");
                var packed=Parse(aesInitializationHex,32*59);
                aesCommands=new byte[32][];aesReplies=new byte[32][];
                for(var n=0;n<32;n++)
                {
                    var request=packed.Skip(n*59).Take(36).ToArray();var response=packed.Skip(n*59+36).Take(23).ToArray();
                    if(!request.Take(4).SequenceEqual(new byte[]{1,23,32,32}) || !response.Take(7).SequenceEqual(new byte[]{4,14,20,1,23,32,0}))
                        throw new ArgumentException("Exact 32 AES requests and successful fixed-size responses required");
                    using(var aes=System.Security.Cryptography.Aes.Create())
                    {
                        aes.Mode=System.Security.Cryptography.CipherMode.ECB;aes.Padding=System.Security.Cryptography.PaddingMode.None;
                        aes.Key=request.Skip(4).Take(16).Reverse().ToArray();
                        using(var encryptor=aes.CreateEncryptor())
                            if(!encryptor.TransformFinalBlock(request.Skip(20).Take(16).Reverse().ToArray(),0,16).Reverse().SequenceEqual(response.Skip(7)))
                                throw new ArgumentException("AES response does not match the command input");
                    }
                    aesCommands[n]=request;aesReplies[n]=response;
                }
            }
            if(advertisingInitializationHex!=null)
            {
                if(aesCommands==null)throw new ArgumentException("Advertising requires the explicit AES initialization scenario");
                var packed=Parse(advertisingInitializationHex,141);
                var sizes=new int[]{10,19,36,36,5};var opcodes=new byte[]{5,6,8,9,10};var offset=0;
                advertisingCommands=new byte[5][];advertisingReplies=new byte[5][];
                for(var n=0;n<5;n++)
                {
                    var request=packed.Skip(offset).Take(sizes[n]).ToArray();offset+=sizes[n];
                    var response=packed.Skip(offset).Take(7).ToArray();offset+=7;
                    if(!request.Take(4).SequenceEqual(new byte[]{1,opcodes[n],32,(byte)(sizes[n]-4)})
                        || !response.SequenceEqual(new byte[]{4,14,4,1,opcodes[n],32,0}))
                        throw new ArgumentException("Exact ordered advertising commands and successful completions required");
                    advertisingCommands[n]=request;advertisingReplies[n]=response;
                }
                var address=advertisingCommands[0].Skip(4).ToArray();
                if(!address.SequenceEqual(startupCommands[0].Skip(4)) || (address[5]&192)!=192
                    || address.Take(5).All(b=>b==0) && (address[5]&63)==0
                    || address.Take(5).All(b=>b==255) && (address[5]&63)==63)
                    throw new ArgumentException("Explicit startup address with static-random format required");
                if(!advertisingCommands[1].Skip(4).SequenceEqual(new byte[]{160,0,160,0,0,1,0,0,0,0,0,0,0,7,0})
                    || advertisingCommands[4][4]!=1)
                    throw new ArgumentException("Source-supported advertising parameters and enable required");
                ValidateAdvertisingData(advertisingCommands[2],28,new byte[]{1,255});
                ValidateAdvertisingData(advertisingCommands[3],21,new byte[]{9});
            }
            if(runtimeConnectionEventHex!=null)
            {
                runtimeEvent=Parse(runtimeConnectionEventHex,22);
                if(!HasAdvertisingInitializationScenario || runtimeEvent[0]!=4 || runtimeEvent[1]!=0x3e || runtimeEvent[2]!=19 || runtimeEvent[3]!=1 || runtimeEvent[4]!=0 || runtimeEvent[7]!=1 || runtimeEvent[8]>1
                    || (runtimeEvent[5]|runtimeEvent[6]<<8)>0x0eff)
                    throw new ArgumentException("One explicit successful peripheral LE connection event requires completed advertising profile");
            }
            if(runtimeAttPacketsHex!=null)
            {
                if(runtimeEvent==null)throw new ArgumentException("ATT packets require the explicit connection event");
                var frames=runtimeAttPacketsHex.Split(';');
                if(frames.Length!=2)throw new ArgumentException("Explicit MTU and time-write ACL frames required");
                runtimeAcls=frames.Select(v=>Parse(v,v.Length/2)).ToArray();
                var handle=runtimeEvent[5]|runtimeEvent[6]<<8;
                foreach(var f in runtimeAcls)
                    if(f.Length<12 || f.Length>255 || f[0]!=2 || (f[1]|f[2]<<8)!=(handle|0x2000) || (f[3]|f[4]<<8)!=f.Length-5 || (f[5]|f[6]<<8)!=f.Length-9 || f[7]!=4 || f[8]!=0)
                        throw new ArgumentException("Bounded original-handle H4/L2CAP ATT frames required");
                if(runtimeAcls[0].Length!=12 || runtimeAcls[0][9]!=3 || runtimeAcls[1][9]!=0x52)throw new ArgumentException("MTU response and Write Command required");
            }
            if(runtimeHostAclHex!=null)
            {
                runtimeHostAcl=Parse(runtimeHostAclHex,runtimeHostAclHex.Length/2);
                if(runtimeAcls==null || runtimeHostAcl.Length!=12 || runtimeHostAcl[0]!=2 || runtimeHostAcl[9]!=2)throw new ArgumentException("Explicit 12-byte H4 MTU request required");
            }
            if(runtimeRandHex!=null)
            {
                var data=Parse(runtimeRandHex,8);
                if(runtimeHostAcl==null)throw new ArgumentException("Runtime Rand fixtures require the MTU workflow");
                runtimeRandReplies=new byte[1][];
                for(var k=0;k<runtimeRandReplies.Length;k++)runtimeRandReplies[k]=new byte[]{4,14,12,1,24,32,0}.Concat(data.Skip(8*k).Take(8)).ToArray();
            }
            if(runtimeRssi!=-129)
            {
                if(runtimeAcls==null || runtimeRssi< -127 || runtimeRssi>20)throw new ArgumentException("Explicit bounded virtual RSSI requires runtime ATT workflow");
                runtimeRssiCommand=new byte[]{1,5,20,2,runtimeEvent[5],runtimeEvent[6]};
                runtimeRssiReply=new byte[]{4,14,7,1,5,20,0,runtimeEvent[5],runtimeEvent[6],unchecked((byte)(sbyte)runtimeRssi)};
            }
            if(runtimeRemoteFeaturesHex!=null)
            {
                var features=Parse(runtimeRemoteFeaturesHex,8);
                if(runtimeRssiReply==null)throw new ArgumentException("Remote feature fixture requires the explicit RSSI workflow");
                runtimeRemoteCommand=new byte[]{1,22,32,2,runtimeEvent[5],runtimeEvent[6]};
                runtimeRemoteReplies=new byte[][]{new byte[]{4,15,4,0,1,22,32},new byte[]{4,62,12,4,0,runtimeEvent[5],runtimeEvent[6]}.Concat(features).ToArray()};
            }
            if(runtimeDisconnectEventHex!=null)
            {
                runtimeDisconnect=Parse(runtimeDisconnectEventHex,7);
                if(runtimeRemoteReplies==null || runtimeDisconnect[0]!=4 || runtimeDisconnect[1]!=5 || runtimeDisconnect[2]!=4 || runtimeDisconnect[3]!=0
                    || runtimeDisconnect[4]!=runtimeEvent[5] || runtimeDisconnect[5]!=runtimeEvent[6] || (runtimeDisconnect[6]!=8 && runtimeDisconnect[6]!=19))
                    throw new ArgumentException("Declared successful disconnect for original handle, reason timeout or remote termination, requires completed time workflow");
            }
            Reset();
        }
        public bool TryQueueRuntimeDisconnect()
        {
            if(runtimeDisconnect==null || runtimeConfigured==null || !runtimeConfigured() || RuntimeEventPending || RuntimeEventsConsumed!=3 || RuntimeRemoteRepliesConsumed!=2 || phase!=Phase.Complete || !CsKnown || !CsHigh)return false;
            runtimeCurrent=runtimeDisconnect;runtimeActive=true;phase=Phase.ReplyQueued;runtimeLevel(true);return true;
        }
        public bool TryQueueRuntimeAtt(int index)
        {
            if(runtimeAcls==null || index<0 || index>=runtimeAcls.Length || runtimeConfigured==null || !runtimeConfigured() || runtimeActive || RuntimeEventsConsumed!=index+1 || phase!=Phase.Complete || !CsKnown || !CsHigh || RuntimeHostAclConsumed!=1)return false;
            runtimeCurrent=runtimeAcls[index];runtimeActive=true;phase=Phase.ReplyQueued;runtimeLevel(true);return true;
        }
        public int RuntimeHostAclConsumed {get;private set;}
        public int RuntimeRandCommandsAccepted {get;private set;}
        public int RuntimeRandRepliesConsumed {get;private set;}
        public int RuntimeRssiCommandsAccepted {get;private set;}
        public int RuntimeRssiRepliesConsumed {get;private set;}
        public int RuntimeRemoteCommandsAccepted {get;private set;}
        public int RuntimeRemoteRepliesConsumed {get;private set;}
        public void AttachRuntimeInput(Func<bool> configured,Action<bool> level)
        {
            if(runtimeConfigured!=null || configured==null || level==null || runtimeEvent==null)throw new ArgumentException("Runtime input attaches exactly once to an explicit event profile");
            runtimeConfigured=configured;runtimeLevel=level;
        }
        public bool TryQueueRuntimeConnection()
        {
            if(runtimeEvent==null || runtimeConfigured==null || !runtimeConfigured() || runtimeActive || RuntimeEventsConsumed!=0 || phase!=Phase.Complete || !CsKnown || !CsHigh)return false;
            runtimeCurrent=runtimeEvent;runtimeActive=true;phase=Phase.ReplyQueued;runtimeLevel(true);return true;
        }
        public bool RuntimeEventPending=>runtimeActive || runtimeRandPending || runtimeRssiPending || runtimeRemotePending;
        public bool HasRuntimeConnectionScenario=>runtimeEvent!=null;
        public int RuntimeEventsConsumed {get;private set;}
        private static void ValidateAdvertisingData(byte[] command,int expectedLength,byte[] types)
        {
            if(command[4]!=expectedLength || command.Skip(5+expectedLength).Any(b=>b!=0))
                throw new ArgumentException("Explicit padded advertising data length required");
            var offset=5;var index=0;
            while(offset<5+expectedLength)
            {
                var size=command[offset];
                if(size<1 || offset+size+1>5+expectedLength || index>=types.Length || command[offset+1]!=types[index++])
                    throw new ArgumentException("Source-supported advertising data structures required");
                offset+=size+1;
            }
            if(index!=types.Length)throw new ArgumentException("Incomplete advertising data structures");
        }
        private static byte[] Parse(string hex,int size)
        {
            if(hex==null || hex.Length!=size*2 || hex.Any(c=>!Uri.IsHexDigit(c)))throw new ArgumentException("Explicit fixed-size hex required");
            return Enumerable.Range(0,size).Select(i=>Convert.ToByte(hex.Substring(2*i,2),16)).ToArray();
        }
        public void Attach(BlackwallGpioOutputLatch output)
        {
            if(attached || output==null)throw new ArgumentException("Event CS attaches once");
            attached=true;output.OutputWritten+=(pin,high)=>{if(pin==149)SetChipSelect(high);};
        }
        public void Reset()
        {
            phase=Phase.Unreleased;CsKnown=false;CsHigh=true;headerUsed=false;
            Position=Headers=Payloads=Frames=PayloadBytes=Aborts=CommandsAccepted=Replies=WriteHeaders=chunkSize=0;
            p256Event=0;
            runtimeActive=runtimeRandPending=runtimeRssiPending=runtimeRemotePending=false;runtimeWriteKind=0;runtimeCurrent=null;RuntimeEventsConsumed=RuntimeHostAclConsumed=RuntimeRandCommandsAccepted=RuntimeRandRepliesConsumed=RuntimeRssiCommandsAccepted=RuntimeRssiRepliesConsumed=RuntimeRemoteCommandsAccepted=RuntimeRemoteRepliesConsumed=0;runtimeLevel?.Invoke(false);
            transmitted.Clear();written.Clear();accepted.Clear();
        }
        public void HoldReset()
        {
            phase=HasReadScenario && Frames>0?Phase.Exhausted:Phase.Unreleased;Position=0;headerUsed=false;
            runtimeActive=runtimeRandPending=runtimeRssiPending=runtimeRemotePending=false;runtimeWriteKind=0;runtimeLevel?.Invoke(false);
        }
        public void QualifiedRelease(bool valid) { if(phase!=Phase.Exhausted)phase=valid?Phase.Queued:Phase.Unreleased; }
        private void SetChipSelect(bool high)
        {
            var rising=high && (!CsKnown || !CsHigh);CsKnown=true;CsHigh=high;
            if(!high && phase==Phase.Complete && runtimeRandReplies!=null && (RuntimeEventsConsumed==1 || RuntimeEventsConsumed==3))
            {
                if(runtimeWriteKind==0)
                {
                    runtimeWriteKind=RuntimeEventsConsumed==1?(RuntimeRandCommandsAccepted<runtimeRandReplies.Length?1:RuntimeRandRepliesConsumed==runtimeRandReplies.Length && RuntimeHostAclConsumed==0?2:0):(runtimeRssiCommand!=null && RuntimeRssiCommandsAccepted==0?3:runtimeRemoteCommand!=null && RuntimeRssiRepliesConsumed==1 && RuntimeRemoteCommandsAccepted==0?4:0);
                    if(runtimeWriteKind!=0)written.Clear();
                }
                if(runtimeWriteKind!=0)phase=Phase.WriteHeaderReady;
            }
            if(!high && phase==Phase.Consumed && HasReadScenario && CommandsAccepted<CommandLimit)phase=Phase.WriteHeaderReady;
            if(!rising)return;
            if(phase==Phase.AwaitRelease) { phase=Phase.Consumed;Frames++; }
            else if(phase==Phase.AwaitWriteRelease)
            {
                Frames++;
                if(runtimeWriteKind!=0)
                {
                    if(written.Count==CurrentCommand.Length)
                    {
                        if(runtimeWriteKind==1) { RuntimeRandCommandsAccepted++;runtimeRandPending=true;phase=Phase.ReplyQueued;runtimeLevel(true); }
                        else if(runtimeWriteKind==3) { RuntimeRssiCommandsAccepted++;runtimeRssiPending=true;phase=Phase.ReplyQueued;runtimeLevel(true); }
                        else if(runtimeWriteKind==4) { RuntimeRemoteCommandsAccepted++;runtimeRemotePending=true;phase=Phase.ReplyQueued;runtimeLevel(true); }
                        else { RuntimeHostAclConsumed++;phase=Phase.Complete; }
                        var wasMtu=runtimeWriteKind==2;runtimeWriteKind=0;written.Clear();
                        if(wasMtu && !TryQueueRuntimeAtt(0))throw new InvalidOperationException("MTU response workflow lost preconditions");
                    }
                    else phase=Phase.Complete;
                    return;
                }
                if(written.Count==CurrentCommand.Length) { accepted.Add(Hex(written));CommandsAccepted++;phase=Phase.ReplyQueued; }
                else phase=Phase.Consumed;
            }
            else if(phase==Phase.AwaitReplyRelease)
            {
                Frames++;
                if(runtimeActive)
                {
                    runtimeActive=false;RuntimeEventsConsumed++;phase=Phase.Complete;runtimeLevel(false);
                    if(runtimeAcls!=null && RuntimeEventsConsumed==2 && !TryQueueRuntimeAtt(1))throw new InvalidOperationException("Time write workflow lost preconditions");
                    return;
                }
                if(runtimeRandPending) { runtimeRandPending=false;RuntimeRandRepliesConsumed++;phase=Phase.Complete;runtimeLevel(false);return; }
                if(runtimeRssiPending) { runtimeRssiPending=false;RuntimeRssiRepliesConsumed++;phase=Phase.Complete;runtimeLevel(false);return; }
                if(runtimeRemotePending)
                {
                    RuntimeRemoteRepliesConsumed++;runtimeLevel(false);
                    if(RuntimeRemoteRepliesConsumed<2) { phase=Phase.ReplyQueued;runtimeLevel(true); }
                    else { runtimeRemotePending=false;phase=Phase.Complete; }
                    return;
                }
                Replies++;
                if(HasP256PublicKeyScenario && CommandsAccepted==22 && ++p256Event<2)phase=Phase.ReplyQueued;
                else if(CommandsAccepted<CommandLimit) { written.Clear();phase=Phase.Consumed; }
                else phase=Phase.Complete;
            }
            else if(phase==Phase.HeaderActive || phase==Phase.PayloadReady) { phase=Phase.Queued;Aborts++; }
            else if(phase==Phase.ReplyHeaderActive || phase==Phase.ReplyPayloadReady) { phase=Phase.ReplyQueued;Aborts++; }
            else if(phase==Phase.WriteHeaderReady || phase==Phase.WriteHeaderActive || phase==Phase.WritePayloadReady) { phase=Phase.Consumed;Aborts++; }
            else if(phase==Phase.PayloadActive || phase==Phase.ReplyPayloadActive || phase==Phase.WritePayloadActive) { phase=Phase.Fault;Aborts++; }
        }
        public bool CanBegin(int length)
        {
            if(!CsKnown || CsHigh)return false;
            if(phase==Phase.Queued)return !headerUsed && length==2;
            if(phase==Phase.ReplyQueued)return HasReadScenario && length==2;
            if(phase==Phase.WriteHeaderReady)return HasReadScenario && WriteHeaders<16*CommandLimit && length==2;
            return phase==Phase.WritePayloadReady && WriteCapacity>0 && length==Math.Min(WriteCapacity,CurrentCommand.Length-written.Count);
        }
        public void BeginTransaction(int length)
        {
            if(!CanBegin(length))throw new ArgumentException("HCI phase/length mismatch");
            Position=0;
            if(phase==Phase.Queued) { headerUsed=true;phase=Phase.HeaderActive; }
            else if(phase==Phase.ReplyQueued)phase=Phase.ReplyHeaderActive;
            else if(phase==Phase.WriteHeaderReady)phase=Phase.WriteHeaderActive;
            else { chunkSize=length;phase=Phase.WritePayloadActive; }
        }
        public bool CanReceive(int length)=>CsKnown && !CsHigh && PayloadReady &&
            (phase==Phase.PayloadReady && length==4 || phase==Phase.ReplyPayloadReady && length==CurrentReply.Length);
        public void BeginReceive(int length)
        {
            if(!CanReceive(length))throw new ArgumentException("HCI payload phase mismatch");
            Position=0;phase=phase==Phase.PayloadReady?Phase.PayloadActive:Phase.ReplyPayloadActive;
        }
        public bool CanExchange(uint word,int length)
        {
            if(CsHigh || length<1 || length>4)return false;
            if(phase==Phase.HeaderActive || phase==Phase.ReplyHeaderActive || phase==Phase.WriteHeaderActive)
                return Position+length<=2 && Enumerable.Range(0,length).All(i=>(byte)(word>>(8*i))==(Position+i==0?(phase==Phase.WriteHeaderActive?0x42:0x81):0));
            if(phase==Phase.WritePayloadActive)
                return Position+length<=chunkSize && written.Count+length<=CurrentCommand.Length && Enumerable.Range(0,length).All(i=>(byte)(word>>(8*i))==CurrentCommand[written.Count+i]);
            return (phase==Phase.PayloadActive && Position+length<=4 || phase==Phase.ReplyPayloadActive && Position+length<=CurrentReply.Length) && Enumerable.Range(0,length).All(i=>(byte)(word>>(8*i))==0);
        }
        public byte Transmit(byte value)
        {
            if(!CanExchange(value,1))throw new ArgumentException("HCI phase/byte mismatch");
            transmitted.Add(value);
            if(phase==Phase.HeaderActive || phase==Phase.ReplyHeaderActive || phase==Phase.WriteHeaderActive)
                return Position++==0?(byte)0xc0:(byte)(phase==Phase.WriteHeaderActive?WriteCapacity:phase==Phase.ReplyHeaderActive?CurrentReply.Length:4);
            if(phase==Phase.WritePayloadActive) { written.Add(value);Position++;return 0; }
            PayloadBytes++;return phase==Phase.ReplyPayloadActive?CurrentReply[Position++]:bytes[Position++];
        }
        public void FinishTransmission()
        {
            if(phase==Phase.HeaderActive && Position==2) { Headers++;phase=Phase.PayloadReady; }
            else if(phase==Phase.ReplyHeaderActive && Position==2) { Headers++;phase=Phase.ReplyPayloadReady; }
            else if(phase==Phase.WriteHeaderActive && Position==2) { Headers++;WriteHeaders++;phase=Phase.WritePayloadReady; }
            else if(phase==Phase.PayloadActive && Position==4) { Payloads++;phase=Phase.AwaitRelease; }
            else if(phase==Phase.ReplyPayloadActive && Position==CurrentReply.Length) { Payloads++;phase=Phase.AwaitReplyRelease; }
            else if(phase==Phase.WritePayloadActive && Position==chunkSize) { Payloads++;phase=Phase.AwaitWriteRelease; }
            else throw new ArgumentException("Incomplete HCI IOM transaction");
        }
        public void AbortTransaction()
        {
            if(phase==Phase.HeaderActive) { phase=Phase.Queued;Aborts++; }
            else if(phase==Phase.PayloadActive || phase==Phase.ReplyHeaderActive || phase==Phase.ReplyPayloadActive || phase==Phase.WriteHeaderActive || phase==Phase.WritePayloadActive) { phase=Phase.Fault;Aborts++; }
        }
        public int ReadyLevel
        {
            get
            {
                if(!CsKnown || phase==Phase.Unreleased || phase==Phase.Fault || phase==Phase.Exhausted)return -1;
                if(phase==Phase.Complete)return CsHigh?0:-1;
                if(phase==Phase.Queued || phase==Phase.HeaderActive || phase==Phase.ReplyQueued || phase==Phase.ReplyHeaderActive || phase==Phase.WriteHeaderReady || phase==Phase.WriteHeaderActive)return 1;
                if(phase==Phase.PayloadReady || phase==Phase.ReplyPayloadReady)return PayloadReady?1:0;
                if(phase==Phase.WritePayloadReady)return WriteCapacity>0?1:0;
                return 0;
            }
        }
        public bool HasReadScenario=>data!=null;
        public bool HasVersionScenario=>versionData!=null;
        public bool HasApplicationResetScenario {get;}
        public bool HasVendorStartupScenario=>startupCommands!=null;
        public int VendorCommandsAccepted=>Math.Min(3,Math.Max(0,CommandsAccepted-3));
        public string VendorAcceptedHex=>string.Join(",",accepted.Skip(3).Take(3));
        public bool HasStandardInitializationScenario=>standardReplies!=null;
        public int StandardCommandsAccepted=>Math.Min(4,Math.Max(0,CommandsAccepted-6));
        public string StandardAcceptedHex=>string.Join(",",accepted.Skip(6).Take(4));
        public bool HasControllerInformationScenario=>informationReplies!=null;
        public string ControllerInformationProfile {get;}
        public int MockAclLength {get;}
        public int MockAclPackets {get;}
        public int InformationCommandsAccepted=>Math.Min(4,Math.Max(0,CommandsAccepted-10));
        public string InformationAcceptedHex=>string.Join(",",accepted.Skip(10).Take(4));
        public bool HasPrivacyInitializationScenario=>privacyReplies!=null;
        public string PrivacyInitializationProfile {get;}
        public int PrivacyCommandsAccepted=>Math.Min(7,Math.Max(0,CommandsAccepted-14));
        public string PrivacyAcceptedHex=>string.Join(",",accepted.Skip(14).Take(7));
        public bool HasP256PublicKeyScenario=>p256Replies!=null;
        public string P256PublicKeyProfile {get;}
        public int P256EventsConsumed=>p256Event;
        public bool PendingP256Completion=>HasP256PublicKeyScenario && CommandsAccepted==22 && Replies==22 && p256Event==1 && phase==Phase.ReplyQueued;
        public int ExpectedReplyEvents=>CommandsAccepted+(HasP256PublicKeyScenario && CommandsAccepted>=22?1:0);
        public bool HasAesInitializationScenario=>aesReplies!=null;
        public int AesCommandsAccepted=>Math.Min(32,Math.Max(0,CommandsAccepted-22));
        public int AesRepliesConsumed=>Math.Min(32,Math.Max(0,Replies-23));
        public bool HasAdvertisingInitializationScenario=>advertisingCommands!=null;
        public int AdvertisingCommandsAccepted=>Math.Min(5,Math.Max(0,CommandsAccepted-54));
        public int AdvertisingRepliesConsumed=>Math.Min(5,Math.Max(0,Replies-55));
        public string ApplicationResetCommandHex=>accepted.Count>2?accepted[2]:"";
        public int VersionStatus {get;}
        public string VersionDataHex=>versionData==null?"":Hex(versionData);
        public string VersionCommandHex=>accepted.Count>1?accepted[1]:HasVersionScenario && CommandsAccepted==1 && Replies==1?Hex(written):"";
        public string State=>phase.ToString();
        public bool CsKnown {get;private set;}
        public bool CsHigh {get;private set;}
        public bool PayloadReady {get;}
        public int WriteCapacity {get;}
        public int Position {get;private set;}
        public int Headers {get;private set;}
        public int Payloads {get;private set;}
        public int Frames {get;private set;}
        public int PayloadBytes {get;private set;}
        public int Aborts {get;private set;}
        public int CommandsAccepted {get;private set;}
        public int Replies {get;private set;}
        public int WriteHeaders {get;private set;}
        public int CommandBytes=>written.Count;
        public string CommandHex=>accepted.Count>0?accepted[0]:Hex(written);
        public string ReadDataHex=>data==null?"":string.Concat(data.Select(b=>b.ToString("x2")));
        public string Transmitted=>string.Concat(transmitted.Select(b=>b.ToString("x2")));
        public int Finished=>Headers+Payloads;
        public string EventHex=>string.Concat(bytes.Select(b=>b.ToString("x2")));
        private enum Phase { Unreleased,Queued,HeaderActive,PayloadReady,PayloadActive,AwaitRelease,Consumed,Fault,
            WriteHeaderReady,WriteHeaderActive,WritePayloadReady,WritePayloadActive,AwaitWriteRelease,
            ReplyQueued,ReplyHeaderActive,ReplyPayloadReady,ReplyPayloadActive,AwaitReplyRelease,Complete,Exhausted }
        private Phase phase;
        private int chunkSize,p256Event;
        private readonly byte[] runtimeEvent,runtimeHostAcl,runtimeDisconnect;
        private readonly byte[][] runtimeAcls,runtimeRandReplies;
        private bool runtimeRandPending,runtimeRssiPending,runtimeRemotePending;
        private readonly byte[] runtimeRemoteCommand;
        private readonly byte[][] runtimeRemoteReplies;
        private readonly byte[] runtimeRssiCommand,runtimeRssiReply;
        private int runtimeWriteKind;
        private static readonly byte[] runtimeRandCommand={1,24,32,0};
        private byte[] runtimeCurrent;
        private bool runtimeActive;
        private Func<bool> runtimeConfigured;
        private Action<bool> runtimeLevel;
        private bool headerUsed,attached;
        private readonly System.Collections.Generic.List<byte> transmitted=new System.Collections.Generic.List<byte>();
        private readonly System.Collections.Generic.List<byte> written=new System.Collections.Generic.List<byte>();
        private static string Hex(System.Collections.Generic.IEnumerable<byte> values)=>string.Concat(values.Select(b=>b.ToString("x2")));
        public int CommandLimit=>HasAdvertisingInitializationScenario?59:HasAesInitializationScenario?54:HasP256PublicKeyScenario?22:HasPrivacyInitializationScenario?21:HasControllerInformationScenario?14:HasStandardInitializationScenario?10:HasVendorStartupScenario?6:HasApplicationResetScenario?3:HasVersionScenario?2:1;
        private byte[] CurrentCommand
        {
            get
            {
                if(runtimeWriteKind==1)return runtimeRandCommand;
                if(runtimeWriteKind==2)return runtimeHostAcl;
                if(runtimeWriteKind==3)return runtimeRssiCommand;
                if(runtimeWriteKind==4)return runtimeRemoteCommand;
                if(HasAdvertisingInitializationScenario && CommandsAccepted>=54)return advertisingCommands[Math.Min(CommandsAccepted-54,4)];
                if(HasAesInitializationScenario && CommandsAccepted>=22)return aesCommands[Math.Min(CommandsAccepted-22,31)];
                if(HasP256PublicKeyScenario && CommandsAccepted>=21)return p256Command;
                if(HasPrivacyInitializationScenario && CommandsAccepted>=14)return privacyCommands[Math.Min(CommandsAccepted-14,6)];
                if(HasControllerInformationScenario && CommandsAccepted>=10)return informationCommands[Math.Min(CommandsAccepted-10,3)];
                if(HasStandardInitializationScenario && CommandsAccepted>=6)return standardCommands[Math.Min(CommandsAccepted-6,3)];
                if(CommandsAccepted==0)return command;
                if(CommandsAccepted==1)return versionCommand;
                if(HasVendorStartupScenario && CommandsAccepted>=3)return startupCommands[Math.Min(CommandsAccepted-3,2)];
                return resetCommand;
            }
        }
        private byte[] CurrentReply
        {
            get
            {
                if(runtimeActive)return runtimeCurrent;
                if(runtimeRandPending)return runtimeRandReplies[RuntimeRandRepliesConsumed];
                if(runtimeRssiPending)return runtimeRssiReply;
                if(runtimeRemotePending)return runtimeRemoteReplies[RuntimeRemoteRepliesConsumed];
                if(HasAdvertisingInitializationScenario && CommandsAccepted>=55)return advertisingReplies[Math.Min(CommandsAccepted-55,4)];
                if(HasAesInitializationScenario && CommandsAccepted>=23)return aesReplies[Math.Min(CommandsAccepted-23,31)];
                if(HasP256PublicKeyScenario && CommandsAccepted>=22)return p256Replies[Math.Min(p256Event,1)];
                if(HasPrivacyInitializationScenario && CommandsAccepted>=15)return privacyReplies[Math.Min(CommandsAccepted-15,6)];
                if(HasControllerInformationScenario && CommandsAccepted>=11)return informationReplies[Math.Min(CommandsAccepted-11,3)];
                if(HasStandardInitializationScenario && CommandsAccepted>=7)return standardReplies[Math.Min(CommandsAccepted-7,3)];
                if(CommandsAccepted<=1)return reply;
                if(CommandsAccepted==2)return versionReply;
                if(HasVendorStartupScenario && CommandsAccepted>=4)return startupReplies[Math.Min(CommandsAccepted-4,2)];
                return resetReply;
            }
        }
        private readonly System.Collections.Generic.List<string> accepted=new System.Collections.Generic.List<string>();
        private readonly byte[] bytes,data,reply,versionData,versionReply;
        private readonly byte[][] startupCommands;
        private readonly byte[][] standardReplies;
        private readonly byte[][] informationReplies;
        private readonly byte[][] privacyCommands,privacyReplies;
        private readonly byte[][] p256Replies;
        private readonly byte[][] aesCommands,aesReplies;
        private readonly byte[][] advertisingCommands,advertisingReplies;
        private static readonly byte[] p256Command={1,37,32,0};
        private static readonly byte[][] informationCommands={Parse("01022000",4),Parse("011c2000",4),Parse("010f2000",4),Parse("01032000",4)};
        private static readonly byte[][] standardCommands={Parse("01010c089088000200800020",12),Parse("01012008ffff7f0000000000",12),Parse("01630c080000800000000000",12),Parse("01091000",4)};
        private static readonly byte[][] startupReplies={new byte[]{4,14,4,1,67,252,0},new byte[]{4,14,4,1,242,255,0},new byte[]{4,14,6,1,196,252,0,6,6}};
        private static readonly byte[] command={1,1,253,5,136,75,240,0,8};
        private static readonly byte[] versionCommand={1,1,253,5,0,32,64,0,4};
        private static readonly byte[] resetCommand={1,3,12,0};
        private static readonly byte[] resetReply={4,14,4,1,3,12,0};
    }
}

namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using System.Linq;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals;
    using Antmicro.Renode.Peripherals.CPU;
    using Antmicro.Renode.Peripherals.Bus;

    // Explicit synthetic slot contents; scanner-only is the default.
    // This is neither actual pairing data nor a writable persistent MRAM model.
    public sealed class BlackwallKeyDbSlotStorage : IBytePeripheral,IWordPeripheral,
        IDoubleWordPeripheral,IQuadWordPeripheral,IKnownSize
    {
        public BlackwallKeyDbSlotStorage(IMachine machine,CortexM cpu,long size,ulong baseAddress,
            string profile="unknown",uint uniformPc=0,uint loopPc=0,uint callerPc=0,bool readOnlySlots=false,BlackwallOtaMarkerRead otaMarker=null)
        {
            var pcs=new uint[]{uniformPc,loopPc,callerPc};
            if(machine==null || cpu==null || size!=0x8000 || baseAddress!=0x7f8000
                || profile!="unknown" && profile!="zero" && profile!="uninit-ff" || readOnlySlots && profile=="unknown"
                || (profile!="unknown" || pcs.Any(p=>p!=0)) && (pcs.Any(p=>p<0x438000 || p>=0x800000 || (p&1)!=0) || pcs.Distinct().Count()!=3))
                throw new ArgumentException("Explicit bounded keydb profile and distinct original consumers required");
            this.machine=machine;this.cpu=cpu;this.baseAddress=baseAddress;
            Profile=profile;UniformPc=uniformPc;LoopPc=loopPc;CallerPc=callerPc;ReadOnlySlots=readOnlySlots;OtaMarker=otaMarker;
            denied=new BlackwallStrictMMIO(size,baseAddress);Size=size;Reset();
        }
        public void Reset()
        {
            denied.Reset();Reads=CompletedSlots=SlotPosition=LastReadPc=0;
            DataReads=DataBytes=DataWordReads=DataByteReads=0;LastDataAddress=0;
            OtaMarker?.Reset();
        }
        public bool TrySample(uint pc,uint r0,uint r4,uint r7,ulong address,out byte value)
        {
            value=0;
            if(Profile=="unknown" || CompletedSlots>=10)return false;
            var slot=0x7ff000u+CompletedSlots*256u;
            if(pc==UniformPc && SlotPosition==0 && r0==slot && address==slot)SlotPosition=1;
            else if(pc==LoopPc && SlotPosition>=1 && SlotPosition<256 && r0==slot && r4==SlotPosition && address==slot+SlotPosition)SlotPosition++;
            else if(pc==CallerPc && SlotPosition==256 && r0==1 && r7==slot && address==slot) { CompletedSlots++;SlotPosition=0; }
            else return false;
            Reads++;LastReadPc=pc;value=Profile=="zero"?(byte)0:(byte)255;return true;
        }
        public byte ReadByte(long offset)
        {
            if(machine.SystemBus.TryGetCurrentCPU(out var current) && current==cpu
                && TrySample((uint)cpu.PC.RawValue,(uint)cpu.GetRegister(0).RawValue,
                    (uint)cpu.GetRegister(4).RawValue,(uint)cpu.GetRegister(7).RawValue,
                    baseAddress+(ulong)offset,out var value))return value;
            if(TryReadBacked(offset,1,out var data))return (byte)data;
            return denied.ReadByte(offset);
        }
        private bool TryReadBacked(long offset,int width,out ulong value)
        {
            value=0;
            if(!ReadOnlySlots || offset<0x7000 || offset>=0x7a00 || offset+width>0x7a00)return false;
            if(Profile=="uninit-ff")value=width==8?ulong.MaxValue:(1UL<<(width*8))-1;
            DataReads++;DataBytes+=(uint)width;LastDataAddress=baseAddress+(ulong)offset;
            if(width==4)DataWordReads++;
            if(width==1)DataByteReads++;
            return true;
        }
        public ushort ReadWord(long offset)=>TryReadBacked(offset,2,out var value)?(ushort)value:denied.ReadWord(offset);
        public uint ReadDoubleWord(long offset)
        {
            if(TryReadBacked(offset,4,out var data))return (uint)data;
            if(OtaMarker!=null && machine.SystemBus.TryGetCurrentCPU(out var current) && current==cpu
                && OtaMarker.TrySample((uint)cpu.PC.RawValue,(uint)cpu.GetRegister(0).RawValue,
                    (uint)cpu.GetRegister(4).RawValue,baseAddress+(ulong)offset,out var value))return value;
            return denied.ReadDoubleWord(offset);
        }
        public ulong ReadQuadWord(long offset)=>TryReadBacked(offset,8,out var value)?value:denied.ReadQuadWord(offset);
        public void WriteByte(long offset,byte value)=>denied.WriteByte(offset,value);
        public void WriteWord(long offset,ushort value)=>denied.WriteWord(offset,value);
        public void WriteDoubleWord(long offset,uint value)=>denied.WriteDoubleWord(offset,value);
        public void WriteQuadWord(long offset,ulong value)=>denied.WriteQuadWord(offset,value);
        public long Size {get;}
        public string Profile {get;}
        public bool ReadOnlySlots {get;}
        public BlackwallOtaMarkerRead OtaMarker {get;}
        public uint DataReads {get;private set;}
        public uint DataBytes {get;private set;}
        public uint DataWordReads {get;private set;}
        public uint DataByteReads {get;private set;}
        public ulong LastDataAddress {get;private set;}
        public uint UniformPc {get;}
        public uint LoopPc {get;}
        public uint CallerPc {get;}
        public uint Reads {get;private set;}
        public uint CompletedSlots {get;private set;}
        public uint SlotPosition {get;private set;}
        public uint LastReadPc {get;private set;}
        public int AccessCount=>denied.AccessCount;
        public ulong LastAddress=>denied.LastAddress;
        public int LastWidth=>denied.LastWidth;
        public string LastOperation=>denied.LastOperation;
        public ulong LastValue=>denied.LastValue;
        private readonly IMachine machine;
        private readonly CortexM cpu;
        private readonly ulong baseAddress;
        private readonly BlackwallStrictMMIO denied;
    }
}

namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using Antmicro.Renode.Peripherals;

    // One immutable synthetic word. Not a write authorization or device evidence.
    public sealed class BlackwallOtaMarkerRead : IPeripheral
    {
        public BlackwallOtaMarkerRead(string profile="unknown",uint startupPc=0,uint setterEntry=0)
        {
            if(profile!="unknown" && profile!="cleared" && profile!="pending"
                || (profile!="unknown" || startupPc!=0 || setterEntry!=0)
                    && (!Valid(startupPc) || !Valid(setterEntry) || !Valid(setterEntry+0x56) || startupPc>=setterEntry && startupPc<=setterEntry+0x56))
                throw new ArgumentException("Explicit marker profile and distinct original read consumers required");
            Profile=profile;StartupPc=startupPc;SetterEntry=setterEntry;Reset();
        }
        private static bool Valid(uint pc)=>pc>=0x438000 && pc<0x800000 && (pc&1)==0;
        public void Reset() { Reads=StartupReads=SetterReads=LastReadPc=0; }
        public bool TrySample(uint pc,uint r0,uint r4,ulong address,out uint value)
        {
            value=0;
            if(Profile=="unknown" || address!=0x7fe000)return false;
            if(pc==StartupPc && r0==address)StartupReads++;
            else if((pc==SetterEntry+0x12 || pc==SetterEntry+0x3e || pc==SetterEntry+0x56) && r4==address)SetterReads++;
            else return false;
            Reads++;LastReadPc=pc;value=Profile=="cleared"?0xffffffffu:0x55555555u;return true;
        }
        public string Profile {get;}
        public uint StartupPc {get;}
        public uint SetterEntry {get;}
        public uint Reads {get;private set;}
        public uint StartupReads {get;private set;}
        public uint SetterReads {get;private set;}
        public uint LastReadPc {get;private set;}
    }
}

namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using System.Collections.Generic;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals.I2C;
    using Antmicro.Renode.Peripherals.Timers;
    using Antmicro.Renode.Time;

    // Declared identity and optional bounded reset fixtures; not physical register defaults.
    public interface IBlackwallImuIndirectExtension
    {
        bool Contains(int address);
        bool BeginRead(int address);
        byte Read(int address);
        bool TryWrite(int address,byte[] data);
        void Reset();
    }
    public sealed class BlackwallImuIdentity : II2CPeripheral
    {
        public BlackwallImuIdentity(BlackwallStrictIom owner, string profile, int identityByte=0x81)
            :this(owner,profile,identityByte,null,-1,-1,1000,true) { }
        public BlackwallImuIdentity(BlackwallStrictIom owner, string profile, int identityByte,
            IMachine machine, int initialInterface, int initialDrive, int resetMicroseconds=1000, bool completeReset=true,
            int sregControl=-1, int iregMicroseconds=4, int fsyncConfig=-1, int int1Config2=-1,
            string edmpConfigurationHex="", int edmpIdleMicroseconds=1000, bool completeEdmpIdle=true,
            string powerConfigurationHex="", int fifoFlushMicroseconds=1000, bool completeFifoFlush=true,
            string auxiliaryConfigurationHex="", string magnetometerFixtureHex="", int masterMicroseconds=1000,
            bool completeMaster=true,int masterError=0,string odrConfigurationHex="",
            string edmpServiceFixtureHex="",int edmpRamFill=165,int edmpServiceMicroseconds=1000,bool completeEdmpService=true,string patchDispatcherHex="",string patchFeatureHex="",long patchKeyOverride=-1,bool b2sParameters=false,string womConfigurationHex="",string powerSaveTimeHex="",string gafParametersHex="",bool gafConfiguration=false,int gafClockVariationByte=-1,bool gafOnDemandControl=false,int gafOnDemandMicroseconds=1000)
        {
            if(owner==null || owner.Module!=4 || (profile!="icm45608-whoami-only" && profile!="icm45608-reset-lifecycle") || identityByte<0 || identityByte>255)
                throw new ArgumentException("Explicit IOM4 identity fixture required");
            var lifecycle=profile=="icm45608-reset-lifecycle";
            if(lifecycle ? machine==null || initialInterface<0 || initialInterface>255 || initialDrive<0 || initialDrive>255 || resetMicroseconds<1 || resetMicroseconds>1000000
                         : initialInterface!=-1 || initialDrive!=-1 || resetMicroseconds!=1000 || !completeReset)
                throw new ArgumentException("Explicit reset fixture requires machine, initial bytes and bounded virtual delay");
            if(sregControl < -1 || sregControl>255 || (sregControl>=0 && !lifecycle) || iregMicroseconds<1 || iregMicroseconds>1000000 || (sregControl<0 && iregMicroseconds!=4))
                throw new ArgumentException("Explicit indirect fixture requires reset profile, byte and bounded virtual delay");
            if(fsyncConfig < -1 || fsyncConfig>255 || (fsyncConfig>=0 && sregControl<0))
                throw new ArgumentException("Explicit FSYNC fixture requires indirect bootstrap and a byte");
            if(int1Config2 < -1 || int1Config2>255 || (int1Config2>=0 && fsyncConfig<0))
                throw new ArgumentException("Explicit INT1 fixture requires FSYNC bootstrap and a byte");
            if(edmpConfigurationHex==null || (edmpConfigurationHex.Length!=0 && int1Config2<0) ||
               (edmpConfigurationHex.Length==0 && (edmpIdleMicroseconds!=1000 || !completeEdmpIdle)))
                throw new ArgumentException("Explicit EDMP fixture requires INT1 bootstrap");
            if(powerConfigurationHex==null || (powerConfigurationHex.Length!=0 && edmpConfigurationHex.Length==0) ||
               (powerConfigurationHex.Length==0 && (fifoFlushMicroseconds!=1000 || !completeFifoFlush)))
                throw new ArgumentException("Explicit power fixture requires EDMP bootstrap");
            if(auxiliaryConfigurationHex==null || (auxiliaryConfigurationHex.Length!=0 && powerConfigurationHex.Length==0))
                throw new ArgumentException("Explicit auxiliary fixture requires power bootstrap");
            if(magnetometerFixtureHex==null || (magnetometerFixtureHex.Length!=0 && auxiliaryConfigurationHex.Length==0) ||
               (magnetometerFixtureHex.Length==0 && (masterMicroseconds!=1000 || !completeMaster || masterError!=0)))
                throw new ArgumentException("Explicit master fixture requires auxiliary bootstrap");
            if(odrConfigurationHex==null || (odrConfigurationHex.Length!=0 && magnetometerFixtureHex.Length==0))throw new ArgumentException("ODR fixture requires master bootstrap");
            if(edmpServiceFixtureHex==null || (edmpServiceFixtureHex.Length!=0 && odrConfigurationHex.Length==0) || (edmpServiceFixtureHex.Length==0 && (edmpRamFill!=165 || edmpServiceMicroseconds!=1000 || !completeEdmpService)))throw new ArgumentException("EDMP service requires ODR bootstrap");
            if(patchDispatcherHex==null || patchFeatureHex==null || (patchDispatcherHex.Length!=0 && edmpServiceFixtureHex.Length==0) || (patchDispatcherHex.Length==0 && (patchFeatureHex.Length!=0 || patchKeyOverride!=-1 || b2sParameters)))throw new ArgumentException("Patch requires explicit service and both payloads");
            if(womConfigurationHex==null || (womConfigurationHex.Length!=0 && !b2sParameters))throw new ArgumentException("WOM requires explicit B2S parameter stage");
            if(powerSaveTimeHex==null || (powerSaveTimeHex.Length!=0 && womConfigurationHex.Length==0))throw new ArgumentException("Power-save fixture requires WOM bootstrap");
            if(gafParametersHex==null || (gafParametersHex.Length!=0 && powerSaveTimeHex.Length==0))throw new ArgumentException("GAF field fixture requires power-save bootstrap");
            this.owner=owner; Profile=profile; IdentityByte=identityByte;
            InitialInterface=initialInterface; InitialDrive=initialDrive; ResetMicroseconds=resetMicroseconds; CompleteReset=completeReset;
            SregControl=sregControl;IregMicroseconds=iregMicroseconds;
            FsyncConfig=fsyncConfig;
            InitialInt1Config2=int1Config2;
            if(edmpConfigurationHex.Length!=0)Edmp=new BlackwallImuEdmpQuiesce(machine,edmpConfigurationHex,edmpIdleMicroseconds,completeEdmpIdle);
            if(powerConfigurationHex.Length!=0)Configuration=new BlackwallImuPowerConfiguration(machine,powerConfigurationHex,fifoFlushMicroseconds,completeFifoFlush);
            if(auxiliaryConfigurationHex.Length!=0)Auxiliary=new BlackwallImuAuxiliarySetup(auxiliaryConfigurationHex);
            if(magnetometerFixtureHex.Length!=0)Master=new BlackwallImuI2cMaster(machine,magnetometerFixtureHex,masterMicroseconds,completeMaster,masterError);
            if(odrConfigurationHex.Length!=0)Odr=new BlackwallImuOdrConfiguration(odrConfigurationHex);
            if(edmpServiceFixtureHex.Length!=0)Service=new BlackwallImuEdmpService(machine,Edmp,edmpServiceFixtureHex,edmpRamFill,edmpServiceMicroseconds,completeEdmpService);
            if(patchDispatcherHex.Length!=0)Patch=new BlackwallImuPatchRam(Service,patchDispatcherHex,patchFeatureHex,patchKeyOverride,b2sParameters);
            if(womConfigurationHex.Length!=0)Wom=new BlackwallImuWomConfiguration(womConfigurationHex);
            if(powerSaveTimeHex.Length!=0)PowerSave=new BlackwallImuPowerSave(Service,powerSaveTimeHex);
            if(gafClockVariationByte < -1 || gafClockVariationByte>255 || (gafClockVariationByte>=0 && !gafConfiguration))throw new ArgumentException("Clock variation requires explicit configuration and a byte or unknown -1");
            if(gafConfiguration && gafParametersHex.Length==0)throw new ArgumentException("GAF configuration requires explicit field fixture");
            if(gafParametersHex.Length!=0)GafParameters=new BlackwallImuGafParameters(Service,PowerSave,gafParametersHex,gafConfiguration,gafClockVariationByte);
            if(gafOnDemandControl)OnDemand=new BlackwallImuGafBootstrap(machine,Service,GafParameters,gafOnDemandMicroseconds,Odr);
            else if(gafOnDemandMicroseconds!=1000)throw new ArgumentException("On-demand observation window requires explicit control profile");
            if(lifecycle)
            {
                timer=new LimitTimer(machine.ClockSource,1000000,this,"IMU-reset",(ulong)resetMicroseconds,Direction.Ascending,enabled:false,workMode:WorkMode.OneShot,eventEnabled:true);
                timer.LimitReached+=()=> {ResetPending=false;ResetElapsed=true;if(CompleteReset) {ResetDone=true;ResetCompletions++;}};
            }
            if(sregControl>=0)
            {
                iregTimer=new LimitTimer(machine.ClockSource,1000000,this,"IMU-IREG",(ulong)iregMicroseconds,Direction.Ascending,enabled:false,workMode:WorkMode.OneShot,eventEnabled:true);
                iregTimer.LimitReached+=()=> {IregPending=false;IregReady=true;IregCompletions++;};
            }
            Reset();
        }
        public void Reset()
        {
            IndirectExtension?.Reset();
            timer?.Reset();
            Edmp?.Reset();
            Configuration?.Reset();
            Auxiliary?.Reset();
            Master?.Reset();
            Odr?.Reset();
            Service?.Reset();serviceWriteCursor=-1;Patch?.Reset();patchWriteCursor=-1;Wom?.Reset();womWriteCursor=-1;PowerSave?.Reset();powerSaveWriteCursor=-1;GafParameters?.Reset();OnDemand?.Reset();gafWriteCursor=-1;gafWriteBase=-1;gafWriteReadEpoch=-1;
            masterWriteCursor=-1;
            iregTimer?.Reset();IregAddress=-1;IregPending=IregReady=false;IregStarts=IregCompletions=IregReads=0;
            FsyncReads=0;
            Int1Config2Value=InitialInt1Config2;Int1Reads=Int1Writes=0;
            Pointer=-1; PointerWrites=IdentityReads=ReturnedBytes=Finishes=ReadAttempts=WriteAttempts=0;
            LastWriteHex=""; LastReadCount=0; pending=false;
            InterfaceValue=InitialInterface;DriveValue=InitialDrive;
            ResetPending=ResetElapsed=ResetDone=false;ResetRequests=ResetCompletions=DriveRestores=InterfaceRestores=StatusReads=ConfigurationReads=0;
        }
        public void Write(byte[] data)
        {
            WriteAttempts++; LastWriteHex=data==null ? "null":BitConverter.ToString(data).Replace("-", "").ToLowerInvariant();
            if(PowerSave!=null && PowerSave.Active && PowerSave.ReadBytes==4 && !PowerSave.Complete && data!=null && data.Length>0 && data[0]==0x2a)
            {
                if(data.Length==1 && PowerSave.ControlReads<2) {Pointer=0x2a;PointerWrites++;pending=true;return;}
                if(data.Length==2 && PowerSave.TryWriteControl(data[1])) {Pointer=0x2a;pending=false;return;}
                owner.RejectDiagnosticPeerAccess("peer-write",(uint)data.Length);return;
            }
            if(Wom!=null && Patch.ParameterBytes==20 && Wom.ThresholdWrites==3 && data!=null && data.Length>0 && data[0]==0x23)
            {
                if(data.Length==1) {Pointer=0x23;PointerWrites++;pending=true;return;}
                if(data.Length==2 && Wom.TryWriteControl(data[1])) {Pointer=0x23;pending=false;return;}
                owner.RejectDiagnosticPeerAccess("peer-write",(uint)data.Length);return;
            }
            if(OnDemand!=null && data!=null && data.Length>0 && OnDemand.MaskRegister(data[0]))
            {
                if(data.Length==1){Pointer=data[0];PointerWrites++;pending=true;return;}
                var values=new byte[data.Length-1];Array.Copy(data,1,values,0,values.Length);
                if(OnDemand.TryWriteMask(data[0],values)){Pointer=data[0];pending=false;return;}
                owner.RejectDiagnosticPeerAccess("apex-mask-write",(uint)data.Length);return;
            }
            if(OnDemand!=null && OnDemand.Active && data!=null && data.Length>0 && OnDemand.DirectRegister(data[0]))
            {
                if(data.Length==1 && OnDemand.CanSelectRead(data[0])) {Pointer=data[0];PointerWrites++;pending=true;return;}
                if(data.Length==2 && OnDemand.TryWriteRegister(data[0],data[1])) {Pointer=data[0];pending=false;return;}
                owner.RejectDiagnosticPeerAccess("gaf-control-write",(uint)data.Length);return;
            }
            if(Service!=null && Service.ProgramWrites==7 && data!=null && data.Length>0 && (data[0]==0x29 || data[0]==0x2a || data[0]==0x73))
            {
                if(data.Length==1) {Pointer=data[0];PointerWrites++;pending=true;return;}
                if(data.Length==2 && Service.TryWrite(data[0],new byte[] {data[1]})) {Pointer=data[0];pending=false;return;}
                owner.RejectDiagnosticPeerAccess("peer-write",(uint)data.Length);return;
            }
            if(Odr!=null && Master.IdentityReads>0 && data!=null && data.Length>0 && Odr.Contains(data[0]))
            {
                if(data.Length==1) {Pointer=data[0];PointerWrites++;pending=true;return;}
                if(data.Length==2 && Odr.TryWrite(data[0],data[1])) {Pointer=data[0];pending=false;return;}
            }
            if(Auxiliary!=null && Configuration.Status0Reads>0 && Configuration.StatusApexReads>0 && data!=null && data.Length>0)
            {
                if(data.Length==1 && (data[0]==0x30 || data[0]==0x16)) {Pointer=data[0];PointerWrites++;pending=true;return;}
                if((data.Length==2 && data[0]==0x30 && Auxiliary.TryWritePad(data[1])) ||
                    (data.Length==3 && data[0]==0x16 && Auxiliary.TryWriteInterrupt(data[1],data[2],OnDemand!=null && OnDemand.Phase=="disabled")))
                {Pointer=data[0];pending=false;return;}
            }
            if(Configuration!=null && Edmp.Idle && data!=null && data.Length>0)
            {
                if(data.Length==1 && (data[0]==0x10 || data[0]==0x20 ||
                    (Configuration.FlushDone && (data[0]==0x19 || data[0]==0x3b))))
                {
                    Pointer=data[0];PointerWrites++;pending=true;return;
                }
                if(data.Length==2 && Configuration.TryWriteRegister(data[0],data[1])) {Pointer=data[0];pending=false;return;}
            }
            if(Edmp!=null && Int1Writes>0 && data!=null && data.Length>0 && (data[0]==0x29 || data[0]==0x2a))
            {
                if(data.Length==1) {Pointer=data[0];PointerWrites++;pending=true;return;}
                if(data.Length==2 && Edmp.TryWriteRegister(data[0],data[1])) {Pointer=data[0];pending=false;return;}
            }
            if(InitialInt1Config2>=0 && FsyncReads>0 && data!=null)
            {
                if(data.Length==1 && data[0]==0x18)
                {
                    Pointer=0x18;PointerWrites++;pending=true;return;
                }
                if(data.Length==2 && data[0]==0x18 && Int1Reads>0 && (data[1]&0xf8)==(Int1Config2Value&0xf8))
                {
                    Int1Config2Value=data[1];Int1Writes++;pending=false;Pointer=0x18;return;
                }
            }
            if(FsyncConfig>=0 && IregReads>0 && data!=null && data.Length==1 && data[0]==0x24)
            {
                Pointer=0x24;PointerWrites++;pending=true;return;
            }
            if(iregTimer!=null && TryIndirectWrite(data))return;
            if(timer!=null && TryLifecycleWrite(data))return;
            if(data==null || data.Length!=1 || data[0]!=0x72 || ResetPending)
            {
                owner.RejectDiagnosticPeerAccess("peer-write",data==null ? 0u:(uint)data.Length); return;
            }
            Pointer=0x72; PointerWrites++; pending=true;
        }
        private int gafWriteCursor=-1,gafWriteBase=-1,gafWriteReadEpoch=-1;
        private bool TryIndirectWrite(byte[] data)
        {
            if(data==null || !ResetElapsed || DriveRestores!=1 || InterfaceRestores!=1)return false;
            if(OnDemand!=null && OnDemand.Active && !IregPending && !IregReady && data.Length>=2 && data[0]==0x7e && gafWriteCursor>=0 && gafWriteBase==IregAddress && gafWriteReadEpoch==IregStarts)
            {
                var bytes=new byte[data.Length-1];Array.Copy(data,1,bytes,0,bytes.Length);
                if(!OnDemand.TryWriteRam(gafWriteCursor,bytes))return false;
                gafWriteCursor+=bytes.Length;Pointer=0x7e;pending=false;return true;
            }
            if(OnDemand!=null && OnDemand.GuestReadActive && !IregPending && !pending && data.Length>=3 && data[0]==0x7c)
            {OnDemand.EndGuestRead();IregReady=false;}
            if(OnDemand!=null && !IregPending && !IregReady && data.Length>=3 && data[0]==0x7c)
            {
                int address=(data[1]<<8)|data[2];
                if(address==4 && data.Length==4)
                {
                    if(!OnDemand.TryRequest(address,new byte[]{data[3]}))return false;
                    gafWriteCursor=gafWriteBase=gafWriteReadEpoch=powerSaveWriteCursor=womWriteCursor=patchWriteCursor=masterWriteCursor=serviceWriteCursor=-1;
                    IregAddress=address;Pointer=0x7c;pending=false;return true;
                }
                if(OnDemand.Active && (address<0x2000 || OnDemand.OwnsRegister(address)))
                {
                    if(data.Length>=4 && address<0x2000)
                    {
                        var bytes=new byte[data.Length-3];Array.Copy(data,3,bytes,0,bytes.Length);
                        if(!OnDemand.TryWriteRam(address,bytes))return false;
                        gafWriteBase=IregAddress=address;gafWriteCursor=address+bytes.Length;gafWriteReadEpoch=IregStarts;
                        powerSaveWriteCursor=womWriteCursor=patchWriteCursor=masterWriteCursor=serviceWriteCursor=-1;
                        Pointer=0x7c;pending=false;return true;
                    }
                    if(data.Length==3 && address<0x2000 && OnDemand.BeginRamRead(address))
                    {IregAddress=address;IregPending=true;IregStarts++;pending=false;Pointer=0x7c;iregTimer.ResetValue();iregTimer.Enabled=true;return true;}
                    if(data.Length==3 && OnDemand.CanSelectRead(address))
                    {IregAddress=address;IregPending=true;IregStarts++;pending=false;Pointer=0x7c;iregTimer.ResetValue();iregTimer.Enabled=true;return true;}
                    if(data.Length==4 && OnDemand.TryWriteRegister(address,data[3])) {IregAddress=address;Pointer=0x7c;pending=false;return true;}
                    return false;
                }
            }
            if(IndirectExtension!=null && data.Length>=3 && data[0]==0x7c)
            {
                var address=(data[1]<<8)|data[2];
                if(IndirectExtension.Contains(address))
                {
                    if(IregPending || IregReady || (data.Length!=3 && data.Length!=4))
                    { owner.RejectDiagnosticPeerAccess("peer-write",(uint)data.Length);return true; }
                    if(data.Length==3)
                    {
                        if(!IndirectExtension.BeginRead(address))
                        { owner.RejectDiagnosticPeerAccess("peer-write",(uint)data.Length);return true; }
                        IregAddress=address;IregPending=true;IregStarts++;pending=false;Pointer=0x7c;
                        iregTimer.ResetValue();iregTimer.Enabled=true;return true;
                    }
                    if(!IndirectExtension.TryWrite(address,new byte[]{data[3]}))
                    { owner.RejectDiagnosticPeerAccess("peer-write",(uint)data.Length);return true; }
                    IregAddress=address;pending=false;Pointer=0x7c;return true;
                }
            }
            if(GafParameters!=null && GafParameters.ConfigurationEnabled && !IregPending && !IregReady)
            {
                if(data.Length>=4 && data[0]==0x7c)
                {
                    int address=(data[1]<<8)|data[2];var values=new byte[data.Length-3];Array.Copy(data,3,values,0,values.Length);
                    if(GafParameters.TryWrite(address,values))
                    {
                        gafWriteBase=IregAddress=address;gafWriteCursor=address+values.Length;gafWriteReadEpoch=IregStarts;
                        powerSaveWriteCursor=womWriteCursor=patchWriteCursor=masterWriteCursor=serviceWriteCursor=-1;
                        Pointer=0x7c;pending=false;return true;
                    }
                }
                if(data.Length>=2 && data[0]==0x7e && gafWriteCursor>=0 && gafWriteBase==IregAddress && gafWriteReadEpoch==IregStarts)
                {
                    var values=new byte[data.Length-1];Array.Copy(data,1,values,0,values.Length);
                    if(!GafParameters.TryWrite(gafWriteCursor,values))return false;
                    gafWriteCursor+=values.Length;Pointer=0x7e;pending=false;return true;
                }
            }
            if(GafParameters!=null && (!GafParameters.Complete || (data.Length==3 && data[1]==0xa2 && data[2]==0xa2)) && PowerSave.Complete && !IregPending && !IregReady && data.Length==3 && data[0]==0x7c)
            {
                int address=(data[1]<<8)|data[2];
                if(address==0xa2a2 ? !GafParameters.BeginClockRead():!GafParameters.BeginRead(address))return false;
                powerSaveWriteCursor=womWriteCursor=patchWriteCursor=masterWriteCursor=serviceWriteCursor=-1;
                IregAddress=address;IregPending=true;IregStarts++;pending=false;Pointer=0x7c;iregTimer.ResetValue();iregTimer.Enabled=true;return true;
            }
            if(PowerSave!=null && Wom.ControlWrites==2 && !IregPending && !IregReady)
            {
                if(data.Length==2 && data[0]==0x7e && powerSaveWriteCursor>=0)
                {
                    if(!PowerSave.TryWriteTime(powerSaveWriteCursor,data[1]))return false;
                    powerSaveWriteCursor=PowerSave.Complete ? -1:powerSaveWriteCursor+1;Pointer=0x7e;pending=false;return true;
                }
                if(data.Length>=3 && data[0]==0x7c && data[1]==0 && data[2]==0x40)
                {
                    if(data.Length==3 && PowerSave.BeginRead(0x40))
                    {powerSaveWriteCursor=womWriteCursor=patchWriteCursor=masterWriteCursor=serviceWriteCursor=-1;IregAddress=0x40;IregPending=true;IregStarts++;pending=false;Pointer=0x7c;iregTimer.ResetValue();iregTimer.Enabled=true;return true;}
                    if(data.Length==4 && PowerSave.TryWriteTime(0x40,data[3]))
                    {powerSaveWriteCursor=0x41;womWriteCursor=patchWriteCursor=masterWriteCursor=serviceWriteCursor=-1;IregAddress=0x40;Pointer=0x7c;pending=false;return true;}
                    return false;
                }
            }
            if(Wom!=null && Patch.ParameterBytes==20 && !IregPending && !IregReady)
            {
                if(data.Length==2 && data[0]==0x7e && womWriteCursor>=0)
                {
                    if(!Wom.TryWriteThreshold(womWriteCursor,data[1]))return false;
                    womWriteCursor++;Pointer=0x7e;pending=false;return true;
                }
                if(data.Length==4 && data[0]==0x7c && ((data[1]<<8)|data[2])>=0xa27e && ((data[1]<<8)|data[2])<=0xa280)
                {
                    var address=(data[1]<<8)|data[2];if(!Wom.TryWriteThreshold(address,data[3]))return false;
                    womWriteCursor=address+1;patchWriteCursor=masterWriteCursor=serviceWriteCursor=-1;IregAddress=address;Pointer=0x7c;pending=false;return true;
                }
            }
            if(Patch!=null && !IregPending && (!IregReady || Patch.ReadRemaining>0))
            {
                if(data.Length==2 && data[0]==0x7e && patchWriteCursor>=0)
                {
                    if(!Patch.TryWrite(patchWriteCursor,data[1]))return false;
                    patchWriteCursor++;Pointer=0x7e;pending=false;return true;
                }
                if(data.Length==3 && data[0]==0x7c && Patch.SupportsReadStart((data[1]<<8)|data[2]) && Patch.BeginRead((data[1]<<8)|data[2]))
                {patchWriteCursor=masterWriteCursor=serviceWriteCursor=-1;IregAddress=(data[1]<<8)|data[2];IregReady=false;IregPending=true;IregStarts++;pending=false;Pointer=0x7c;iregTimer.ResetValue();iregTimer.Enabled=true;return true;}
                if(data.Length==4 && data[0]==0x7c && Patch.ContainsWrite((data[1]<<8)|data[2]))
                {
                    var address=(data[1]<<8)|data[2];if(!Patch.TryWrite(address,data[3]))return false;
                    patchWriteCursor=address+1;masterWriteCursor=serviceWriteCursor=-1;IregAddress=address;IregReady=false;Pointer=0x7c;pending=false;return true;
                }
            }
            if(Service!=null && Odr.Writes>=6 && !IregPending && !IregReady)
            {
                if(data.Length==2 && data[0]==0x7e && serviceWriteCursor>=0)
                {
                    if(!Service.TryWrite(serviceWriteCursor,new byte[] {data[1]}))return false;
                    serviceWriteCursor++;Pointer=0x7e;pending=false;return true;
                }
                if(data.Length>=3 && data[0]==0x7c && Service.Contains((data[1]<<8)|data[2]))
                {
                    var address=(data[1]<<8)|data[2];
                    if(data.Length==4 && Service.TryWrite(address,new byte[] {data[3]}))
                    {IregAddress=address;masterWriteCursor=-1;serviceWriteCursor=address+1;Pointer=0x7c;pending=false;return true;}
                    if(data.Length==3 && Service.SupportsRead(address))
                    {masterWriteCursor=serviceWriteCursor=-1;IregAddress=address;IregPending=true;IregStarts++;pending=false;Pointer=0x7c;iregTimer.ResetValue();iregTimer.Enabled=true;return true;}
                    return false;
                }
            }
            if(Odr!=null && Master.IdentityReads>0 && !IregPending && !IregReady && data.Length==4 && data[0]==0x7c && Odr.Contains((data[1]<<8)|data[2]))
            {
                var address=(data[1]<<8)|data[2];
                if(Odr.TryWrite(address,data[3])) {IregAddress=address;masterWriteCursor=-1;Pointer=0x7c;pending=false;return true;}
            }
            if(Odr!=null && Master.IdentityReads>0 && !IregPending && !IregReady && data.Length==3 && data[0]==0x7c && Odr.Contains((data[1]<<8)|data[2]))
            {
                masterWriteCursor=-1;IregAddress=(data[1]<<8)|data[2];IregPending=true;IregStarts++;pending=false;Pointer=0x7c;
                iregTimer.ResetValue();iregTimer.Enabled=true;return true;
            }
            if(Master!=null && !IregPending && !IregReady && masterWriteCursor>=0 && (Pointer==0x7c || Pointer==0x7e) && data.Length>=2 && data[0]==0x7e)
            {
                var payload=new byte[data.Length-1];Array.Copy(data,1,payload,0,payload.Length);
                if(Master.TryWriteContinuation(masterWriteCursor,payload,(Auxiliary.Interrupt1&0x20)!=0))
                {masterWriteCursor+=payload.Length;Pointer=0x7e;pending=false;return true;}
            }
            if(Master!=null && Auxiliary.InterruptWrites>0 && !IregPending && !IregReady && data.Length>=4 && data[0]==0x7c && data[1]==0xa2)
            {
                var payload=new byte[data.Length-3];Array.Copy(data,3,payload,0,payload.Length);
                if(Master.TryWriteIreg(0xa200|data[2],payload,(Auxiliary.Interrupt1&0x20)!=0))
                {IregAddress=0xa200|data[2];masterWriteCursor=IregAddress+payload.Length;Pointer=0x7c;pending=false;return true;}
            }
            if(data.Length==3 && data[0]==0x7c && data[1]==0xa2 &&
                (data[2]==0x67 || (data[2]==0x97 && Edmp!=null && Int1Writes>0) ||
                 (Master!=null && Auxiliary.InterruptWrites>0 && Master.SupportsRead(0xa200|data[2]))) && !IregPending && !IregReady)
            {
                masterWriteCursor=-1;IregAddress=0xa200|data[2];IregPending=true;IregStarts++;pending=false;Pointer=0x7c;
                iregTimer.ResetValue();iregTimer.Enabled=true;return true;
            }
            if(data.Length==1 && data[0]==0x7e && (IregPending || IregReady))
            {
                Pointer=0x7e;PointerWrites++;pending=true;return true;
            }
            return false;
        }
        private bool TryLifecycleWrite(byte[] data)
        {
            if(data==null)return false;
            if(data.Length==1 && ((data[0]==0x19 && ResetRequests>0) || (data[0]==0x2d && InterfaceValue>=0) || (data[0]==0x32 && DriveValue>=0)))
            {
                Pointer=data[0];PointerWrites++;pending=true;return true;
            }
            if(data.Length!=2)return false;
            if(data[0]==0x7f && data[1]==2 && ResetRequests==0)
            {
                ResetRequests++;ResetPending=true;ResetElapsed=ResetDone=false;InterfaceValue=DriveValue=-1;
                pending=false;Pointer=0x7f;timer.ResetValue();timer.Enabled=true;return true;
            }
            if(!ResetElapsed || ResetPending)return false;
            if(data[0]==0x32 && data[1]==InitialDrive && DriveRestores==0)
            {
                DriveValue=data[1];DriveRestores++;pending=false;Pointer=0x32;return true;
            }
            if(data[0]==0x2d && data[1]==InitialInterface && DriveRestores==1 && InterfaceRestores==0)
            {
                InterfaceValue=data[1];InterfaceRestores++;pending=false;Pointer=0x2d;return true;
            }
            return false;
        }
        public byte[] Read(int count=1)
        {
            ReadAttempts++; LastReadCount=count;
            if(PowerSave!=null && PowerSave.Active && PowerSave.ReadBytes==4 && !PowerSave.Complete && pending && Pointer==0x2a && count==1)
            {var value=PowerSave.ReadControl();pending=false;ReturnedBytes++;return new byte[] {value};}
            if(Wom!=null && Wom.ThresholdWrites==3 && pending && Pointer==0x23 && count==1)
            {var value=Wom.ReadControl();pending=false;ReturnedBytes++;return new byte[] {value};}
            if(OnDemand!=null && pending && OnDemand.MaskRegister(Pointer))
            {
                var values=OnDemand.ReadMask(Pointer,count);
                if(values==null){owner.RejectDiagnosticPeerAccess("apex-mask-read",(uint)count);return new byte[0];}
                pending=false;ReturnedBytes+=values.Length;return values;
            }
            if(OnDemand!=null && OnDemand.Active && pending && count==1 && OnDemand.DirectRegister(Pointer))
            {
                if(!OnDemand.TryReadRegister(Pointer,out var controlValue)) {owner.RejectDiagnosticPeerAccess("gaf-control-read",(uint)count);return new byte[0];}
                pending=false;ReturnedBytes++;return new byte[]{controlValue};
            }
            if(Service!=null && Service.ProgramWrites==7 && pending && count==1 && (Pointer==0x29 || Pointer==0x2a || Pointer==0x73))
            {var value=Service.Read(Pointer);pending=false;ReturnedBytes++;return new byte[] {(byte)value};}
            if(Odr!=null && pending && count==1 && Odr.Contains(Pointer)) {pending=false;ReturnedBytes++;return new byte[] {Odr.Read(Pointer)};}
            if(Auxiliary!=null && pending)
            {
                if(count==1 && Pointer==0x30) {pending=false;ReturnedBytes++;return new byte[] {Auxiliary.ReadPad()};}
                if(count==2 && Pointer==0x16) {pending=false;ReturnedBytes+=2;return Auxiliary.ReadInterrupt();}
            }
            if(Configuration!=null && Edmp.Idle && pending)
            {
                if(count==1 && (Pointer==0x10 || Pointer==0x20))
                {
                    var value=Configuration.ReadRegister(Pointer);pending=false;ReturnedBytes++;return new byte[] {value};
                }
                if(count==2 && Configuration.FlushDone && (Pointer==0x19 || Pointer==0x3b))
                {
                    var value=Configuration.ReadStatusPair(Pointer);
                    if(Pointer==0x19 && Master!=null && Master.Starts>0)
                        value[1]=(byte)((value[1]&0xdf)|(Master.TakeDoneInterrupt() ? 0x20:0));
                    pending=false;ReturnedBytes+=2;return value;
                }
            }
            if(Edmp!=null && pending && count==1 && (Pointer==0x29 || Pointer==0x2a))
            {
                var value=Edmp.ReadRegister(Pointer);pending=false;ReturnedBytes++;return new byte[] {value};
            }
            if(InitialInt1Config2>=0 && pending && Pointer==0x18 && count==1)
            {
                pending=false;Int1Reads++;ReturnedBytes++;return new byte[] {(byte)Int1Config2Value};
            }
            if(FsyncConfig>=0 && pending && Pointer==0x24 && count==1)
            {
                pending=false;FsyncReads++;ReturnedBytes++;return new byte[] {(byte)FsyncConfig};
            }
            if(iregTimer!=null && pending && Pointer==0x7e && count==1 && IregReady)
            {
                byte[] value;
                if(IndirectExtension!=null && IndirectExtension.Contains(IregAddress))value=new byte[]{IndirectExtension.Read(IregAddress)};
                else if(OnDemand!=null && OnDemand.Active && OnDemand.OwnsRegister(IregAddress))
                {
                    if(!OnDemand.TryReadRegister(IregAddress,out var controlValue)) {owner.RejectDiagnosticPeerAccess("gaf-result-read",(uint)count);return new byte[0];}
                    value=new byte[]{controlValue};
                }
                else if(GafParameters!=null && GafParameters.ReadRemaining>0)value=new byte[] {GafParameters.ReadNext()};
                else if(PowerSave!=null && PowerSave.ReadRemaining>0)value=new byte[] {PowerSave.ReadNext()};
                else if(Patch!=null && Patch.ReadRemaining>0)value=new byte[] {(byte)Patch.ReadNext()};
                else if(IregAddress==0xa267)value=new byte[] {(byte)SregControl};
                else if(Service!=null && Service.ProgramWrites>0 && Service.SupportsRead(IregAddress))value=new byte[] {(byte)Service.Read(IregAddress)};
                else if(IregAddress==0xa297)value=new byte[] {Edmp.ReadIdleByte()};
                else if(Odr!=null && Odr.Contains(IregAddress))value=new byte[] {Odr.Read(IregAddress)};
                else value=Master?.ReadIreg(IregAddress,count);
                if(value!=null) {IregReady=(OnDemand!=null && OnDemand.RamReadRemaining>0) || (Patch!=null && Patch.ReadRemaining>0) || (PowerSave!=null && PowerSave.ReadRemaining>0) || (GafParameters!=null && GafParameters.ReadRemaining>0);pending=false;IregReads++;ReturnedBytes+=value.Length;return value;}
            }
            if(timer!=null && pending && count==1 && (Pointer==0x19 || Pointer==0x2d || Pointer==0x32))
            {
                byte value;
                if(Pointer==0x19) {value=(byte)(ResetDone ? 0x80:0);ResetDone=false;StatusReads++;}
                else {value=(byte)(Pointer==0x2d ? InterfaceValue:DriveValue);ConfigurationReads++;}
                pending=false;ReturnedBytes++;return new byte[] {value};
            }
            if(!pending || count!=1 || Pointer!=0x72 || ResetPending)
            {
                owner.RejectDiagnosticPeerAccess("peer-read",unchecked((uint)count)); return new byte[0];
            }
            pending=false; IdentityReads++; ReturnedBytes++;
            return new byte[] {(byte)IdentityByte};
        }
        public void FinishTransmission() { Finishes++; }
        public void AttachIndirectExtension(IBlackwallImuIndirectExtension extension)
        {
            if(extension==null || IndirectExtension!=null || iregTimer==null || IregPending || IregReady)
                throw new ArgumentException("One extension on an idle timed indirect transport required");
            IndirectExtension=extension;
        }
        public IBlackwallImuIndirectExtension IndirectExtension {get;private set;}
        public bool HasIndirectTransport => iregTimer!=null;

        public string Profile {get;}
        public int IdentityByte {get;}
        public int Pointer {get;private set;}
        public int PointerWrites {get;private set;}
        public int IdentityReads {get;private set;}
        public int ReturnedBytes {get;private set;}
        public int Finishes {get;private set;}
        public int ReadAttempts {get;private set;}
        public int WriteAttempts {get;private set;}
        public string LastWriteHex {get;private set;}
        public int LastReadCount {get;private set;}
        public int InitialInterface {get;}
        public int InitialDrive {get;}
        public int ResetMicroseconds {get;}
        public bool CompleteReset {get;}
        public int InterfaceValue {get;private set;}
        public int DriveValue {get;private set;}
        public bool ResetPending {get;private set;}
        public bool ResetElapsed {get;private set;}
        public bool ResetDone {get;private set;}
        public int ResetRequests {get;private set;}
        public int ResetCompletions {get;private set;}
        public int DriveRestores {get;private set;}
        public int InterfaceRestores {get;private set;}
        public int StatusReads {get;private set;}
        public int ConfigurationReads {get;private set;}
        public int SregControl {get;}
        public int IregMicroseconds {get;}
        public int IregAddress {get;private set;}
        public bool IregPending {get;private set;}
        public bool IregReady {get;private set;}
        public int IregStarts {get;private set;}
        public int IregCompletions {get;private set;}
        public int IregReads {get;private set;}
        public int FsyncConfig {get;}
        public int FsyncReads {get;private set;}
        public int InitialInt1Config2 {get;}
        public int Int1Config2Value {get;private set;}
        public int Int1Reads {get;private set;}
        public int Int1Writes {get;private set;}
        public BlackwallImuEdmpQuiesce Edmp {get;}
        public BlackwallImuPowerConfiguration Configuration {get;}
        public BlackwallImuAuxiliarySetup Auxiliary {get;}
        public BlackwallImuI2cMaster Master {get;}
        public BlackwallImuOdrConfiguration Odr {get;}
        public BlackwallImuEdmpService Service {get;}
        public BlackwallImuPatchRam Patch {get;}
        public BlackwallImuWomConfiguration Wom {get;}
        public BlackwallImuPowerSave PowerSave {get;}
        public BlackwallImuGafParameters GafParameters {get;}
        public BlackwallImuGafBootstrap OnDemand {get;}
        private int powerSaveWriteCursor;
        private int womWriteCursor;
        private int patchWriteCursor;
        private int serviceWriteCursor;
        private bool pending;
        private int masterWriteCursor;
        private readonly BlackwallStrictIom owner;
        private readonly LimitTimer timer;
        private readonly LimitTimer iregTimer;
    }

    // Bounded host-visible EDMP services; no EDMP instruction set or fusion DSP.
    // Explicit input bytes for the source-matched GAF getter, not physical ROM defaults.
    public sealed class BlackwallImuGafParameters : Antmicro.Renode.Peripherals.IPeripheral
    {
        public BlackwallImuGafParameters(BlackwallImuEdmpService owner,BlackwallImuPowerSave powerSave,string parametersHex,bool enableConfiguration=false,int clockVariationByte=-1)
        {
            if(owner==null || powerSave==null || parametersHex==null || parametersHex.Length!=306)throw new ArgumentException("153 explicit GAF field bytes required");
            foreach(var c in parametersHex)if(!Uri.IsHexDigit(c))throw new ArgumentException("Hex GAF field fixture required");
            if(clockVariationByte < -1 || clockVariationByte>255 || (clockVariationByte>=0 && !enableConfiguration))throw new ArgumentException("Clock variation byte requires configuration");
            ClockVariationByte=clockVariationByte;
            this.owner=owner;this.powerSave=powerSave;ConfigurationEnabled=enableConfiguration;FixtureHex=parametersHex.ToLowerInvariant();
            for(int k=0;k<initial.Length;k++)initial[k]=Convert.ToByte(parametersHex.Substring(k*2,2),16);
            Reset();
        }
        public void Reset() {index=cursor=FieldsStarted=ReadBytes=ReadRemaining=ProfileApplications=0;WrittenBytes=WriteTransactions=ClockReads=ClockSelections=0;clockReadPending=false;history.Clear();}
        public bool TryWrite(int address,byte[] data)
        {
            if(!ConfigurationEnabled || !Complete || ReadRemaining!=0 || !powerSave.Complete || owner.Completions!=2 || owner.Pending || data==null || data.Length==0)return false;
            if(address<0 || (long)address+data.Length>8192)return false;
            for(int k=0;k<data.Length;k++)
            {
                int current=address+k;bool known=false;
                for(int j=0;j<addresses.Length;j++)if(current>=addresses[j] && current<addresses[j]+lengths[j]) {known=true;break;}
                if(!known)for(int j=0;j<writeAddresses.Length;j++)if(current>=writeAddresses[j] && current<writeAddresses[j]+writeLengths[j]) {known=true;break;}
                if(!known)return false;
            }
            for(int k=0;k<data.Length;k++) {owner.StoreRamByte(address+k,data[k]);history.Add((address+k).ToString("x")+":"+data[k].ToString("x2"));}
            WrittenBytes+=data.Length;WriteTransactions++;return true;
        }
        public bool BeginClockRead()
        {
            if(!ConfigurationEnabled || ClockVariationByte<0 || !Complete || !powerSave.Complete || owner.Completions!=2 || owner.Pending || ReadRemaining!=0)return false;
            clockReadPending=true;ReadRemaining=1;ClockSelections++;return true;
        }
        public int ClockVariationByte {get;}
        public int ClockReads {get;private set;}
        public int ClockSelections {get;private set;}
        private bool clockReadPending;
        public bool ConfigurationEnabled {get;}
        public int WrittenBytes {get;private set;}
        public int WriteTransactions {get;private set;}
        public string History=>string.Join("|",history);
        private readonly List<string> history=new List<string>();
        private static readonly int[] writeAddresses={0x774,0x974,0x770,0x76c,0x780,0x78c,0x288,0x290,0x28c,0x818};
        private static readonly int[] writeLengths={12,12,4,4,12,12,4,4,4,4};
        public bool BeginRead(int address)
        {
            if(!powerSave.Complete || owner.Completions!=2 || owner.Pending || ReadRemaining!=0 || Complete || address!=addresses[index])return false;
            if(ProfileApplications==0)
            {
                int k=0;for(int j=0;j<addresses.Length;j++)for(int n=0;n<lengths[j];n++)owner.StoreRamByte(addresses[j]+n,initial[k++]);
                ProfileApplications++;
            }
            cursor=0;ReadRemaining=lengths[index];FieldsStarted++;return true;
        }
        public byte ReadNext()
        {
            if(ReadRemaining==0)throw new InvalidOperationException("No GAF field read selected");
            if(clockReadPending) {clockReadPending=false;ReadRemaining=0;ClockReads++;return (byte)ClockVariationByte;}
            byte value=(byte)owner.RamByte(addresses[index]+cursor);cursor++;ReadBytes++;ReadRemaining--;
            if(ReadRemaining==0)index++;
            return value;
        }
        public string ValuesHex
        {
            get {var data=new byte[153];int k=0;for(int j=0;j<addresses.Length;j++)for(int n=0;n<lengths[j];n++)data[k++]=(byte)owner.RamByte(addresses[j]+n);return BitConverter.ToString(data).Replace("-", "").ToLowerInvariant();}
        }
        public int DeclaredFieldLength(int address) {for(int k=0;k<addresses.Length;k++)if(address==addresses[k])return lengths[k];return 0;}
        public bool Complete=>index==addresses.Length;
        public string FixtureHex {get;}
        public int FieldsStarted {get;private set;}
        public int ReadBytes {get;private set;}
        public int ReadRemaining {get;private set;}
        public int ProfileApplications {get;private set;}
        private int index,cursor;
        private readonly byte[] initial=new byte[153];
        private readonly BlackwallImuEdmpService owner;
        private readonly BlackwallImuPowerSave powerSave;
        private static readonly int[] addresses={0x2ae,0x2ac,0x294,0x2ad,0x298,0x29c,0x2a0,0x5cc,0x5ec,0x5dc,0x6b8,0x6bc,0x6c8,0x5e0,0x6b4,0x6b0,0x6c0,0x6c4,0x4f8,0x2a4,0x4d8,0x4f4,0x4a8,0x4b8,0x4bc,0x4d0,0x4d4,0x820,0x824,0x828,0x82c,0x830,0x834,0x838,0x83c,0x840,0x844,0x848,0x84c,0x4c4,0x850};
        private static readonly int[] lengths={1,1,4,1,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,2};
    }

    public sealed class BlackwallImuPowerSave : Antmicro.Renode.Peripherals.IPeripheral
    {
        public BlackwallImuPowerSave(BlackwallImuEdmpService owner,string timeHex)
        {
            if(owner==null || timeHex==null || timeHex.Length!=8)throw new ArgumentException("Explicit power-save ROM-result fixture required");
            foreach(var c in timeHex)if(!Uri.IsHexDigit(c))throw new ArgumentException("Hex time fixture required");
            this.owner=owner;FixtureHex=timeHex.ToLowerInvariant();for(var k=0;k<4;k++)initial[k]=Convert.ToByte(timeHex.Substring(k*2,2),16);Reset();
        }
        public void Reset() {ProfileApplications=ReadBytes=ReadRemaining=WriteBytes=ControlReads=ControlWrites=0;lease=false;}
        public bool BeginRead(int address)
        {
            if(address!=0x40 || Active || owner.Completions!=2 || owner.Pending)return false;
            for(var k=0;k<4;k++)owner.StoreRamByte(0x40+k,initial[k]);
            ProfileApplications++;ReadRemaining=4;return true;
        }
        public byte ReadNext()
        {
            if(ReadRemaining==0)throw new InvalidOperationException("No power-save RAM read selected");
            var value=(byte)owner.RamByte(0x40+4-ReadRemaining);ReadRemaining--;ReadBytes++;return value;
        }
        public byte ReadControl()
        {
            if(ReadBytes!=4 || Complete || ControlReads>=2)throw new InvalidOperationException("Power-save control outside declared flow");
            ControlReads++;lease=true;return owner.ReadPowerControl();
        }
        public bool TryWriteControl(byte value)
        {
            if(!lease || ControlReads!=2 || ControlWrites!=0 || value!=(owner.PowerControl&~4))return false;
            owner.WritePowerControl(value);ControlWrites++;lease=false;return true;
        }
        public bool TryWriteTime(int address,byte value)
        {
            if(ControlWrites!=1 || WriteBytes>=4 || address!=0x40+WriteBytes || value!=owner.RamByte(address))return false;
            owner.StoreRamByte(address,value);WriteBytes++;return true;
        }
        public string ValuesHex {get {var bytes=new byte[4];for(var k=0;k<4;k++)bytes[k]=(byte)owner.RamByte(0x40+k);return BitConverter.ToString(bytes).Replace("-", "").ToLowerInvariant();}}
        public bool Active {get {return ProfileApplications!=0;}}
        public bool Complete {get {return WriteBytes==4;}}
        public string FixtureHex {get;}
        public int ProfileApplications {get;private set;}
        public int ReadBytes {get;private set;}
        public int ReadRemaining {get;private set;}
        public int WriteBytes {get;private set;}
        public int ControlReads {get;private set;}
        public int ControlWrites {get;private set;}
        private bool lease;
        private readonly byte[] initial=new byte[4];
        private readonly BlackwallImuEdmpService owner;
    }

    public sealed class BlackwallImuWomConfiguration : Antmicro.Renode.Peripherals.IPeripheral
    {
        public BlackwallImuWomConfiguration(string configurationHex)
        {
            if(configurationHex==null || configurationHex.Length!=8)throw new ArgumentException("Four explicit WOM fixture bytes required");
            foreach(var c in configurationHex)if(!Uri.IsHexDigit(c))throw new ArgumentException("Hex WOM fixture required");
            FixtureHex=configurationHex.ToLowerInvariant();for(var k=0;k<4;k++)initial[k]=Convert.ToByte(configurationHex.Substring(k*2,2),16);Reset();
        }
        public void Reset() {Array.Copy(initial,values,4);ThresholdWrites=ControlWrites=ControlReads=0;lease=false;}
        public bool TryWriteThreshold(int address,byte value)
        {
            if(ThresholdWrites>=3 || address!=0xa27e+ThresholdWrites)return false;
            values[ThresholdWrites]=value;ThresholdWrites++;return true;
        }
        public byte ReadControl() {if(ThresholdWrites!=3)throw new InvalidOperationException("Thresholds not initialized");ControlReads++;lease=true;return values[3];}
        public bool TryWriteControl(byte value)
        {
            if(ThresholdWrites!=3 || !lease || ControlWrites>=2)return false;
            if(ControlWrites==0 ? (value&0xf0)!=(values[3]&0xf0) || (value&8)==0 : value!=(values[3]|0x10))return false;
            values[3]=value;ControlWrites++;lease=false;return true;
        }
        public string FixtureHex {get;}
        public string ValuesHex {get {return BitConverter.ToString(values).Replace("-", "").ToLowerInvariant();}}
        public int Control {get {return values[3];}}
        public int ThresholdWrites {get;private set;}
        public int ControlWrites {get;private set;}
        public int ControlReads {get;private set;}
        private bool lease;
        private readonly byte[] initial=new byte[4],values=new byte[4];
    }

    public sealed class BlackwallImuPatchRam : Antmicro.Renode.Peripherals.IPeripheral
    {
        public BlackwallImuPatchRam(BlackwallImuEdmpService owner,string dispatcherHex,string featureHex,long markerOverride=-1,bool enableParameters=false)
        {
            if(owner==null || markerOverride < -1 || markerOverride>0xffffffffL)throw new ArgumentException("Explicit RAM owner/marker required");
            this.owner=owner;dispatcher=Parse(dispatcherHex,25);feature=Parse(featureHex,375);MarkerOverride=markerOverride;EnableParameters=enableParameters;Reset();
        }
        private static byte[] Parse(string text,int length)
        {
            if(text==null || text.Length!=length*2)throw new ArgumentException("Explicit exact patch payload required");
            foreach(var c in text)if(!Uri.IsHexDigit(c))throw new ArgumentException("Hex payload required");
            var data=new byte[length];for(var k=0;k<length;k++)data[k]=Convert.ToByte(text.Substring(k*2,2),16);return data;
        }
        public void Reset() {ReadRemaining=ReadBytes=WrittenBytes=DispatcherBytes=KeyBytes=FeatureBytes=ParameterBytes=0;markerRead=false;initialMarker=0;}
        public bool SupportsReadStart(int address) {return address==0x48 || (Loaded && address>=0x1600 && address<0x1777);}
        public bool BeginRead(int address)
        {
            if(owner.Completions!=2 || owner.Pending)return false;
            if(address!=0x48)
            {
                if(!Loaded || address<0x1600 || address>=0x1777)return false;
                readAddress=address;ReadRemaining=0x1777-address;return true;
            }
            if(ReadRemaining!=0 || markerRead)return false;
            if(MarkerOverride>=0)for(var k=0;k<4;k++)owner.StoreRamByte(0x48+k,(byte)((ulong)MarkerOverride>>(k*8)));
            initialMarker=0;for(var k=0;k<4;k++)initialMarker|=(uint)owner.RamByte(0x48+k)<<(k*8);
            readAddress=0x48;ReadRemaining=4;return true;
        }
        public int ReadNext()
        {
            if(ReadRemaining==0)throw new InvalidOperationException("No RAM read selected");
            var value=owner.RamByte(readAddress++);ReadRemaining--;ReadBytes++;
            if(readAddress==0x4c)markerRead=true;return value;
        }
        public bool ContainsWrite(int address) {return (address>=0x1580 && address<0x1599) || (address>=0x48 && address<0x4c) || (address>=0x1600 && address<0x1777);}
        public bool TryWrite(int address,byte value)
        {
            if(!markerRead || owner.Completions!=2 || owner.Pending)return false;
            if(EnableParameters && Loaded && ParameterBytes<parameterAddresses.Length && address==parameterAddresses[ParameterBytes])
            {
                owner.StoreRamByte(address,value);ParameterBytes++;WrittenBytes++;ReadRemaining=0;return true;
            }
            if(ReadRemaining!=0)return false;
            if(address>=0x1580 && address<0x1599)
            {
                var offset=address-0x1580;if(initialMarker!=0 || offset!=DispatcherBytes || value!=dispatcher[offset])return false;
                owner.StoreRamByte(address,value);DispatcherBytes++;
            }
            else if(address>=0x48 && address<0x4c)
            {
                var offset=address-0x48;
                if(initialMarker!=0 || DispatcherBytes!=25 || offset!=KeyBytes || value!=(byte)(0x801570f1U>>(offset*8)))return false;
                owner.StoreRamByte(address,value);KeyBytes++;
            }
            else if(address>=0x1600 && address<0x1777)
            {
                var offset=address-0x1600;
                if(offset!=FeatureBytes || value!=feature[offset] || (initialMarker==0 && (DispatcherBytes!=25 || KeyBytes!=4)))return false;
                owner.StoreRamByte(address,value);FeatureBytes++;
            }
            else return false;
            WrittenBytes++;return true;
        }
        public bool Loaded
        {
            get
            {
                if(FeatureBytes!=375)return false;
                for(var k=0;k<4;k++)if(owner.RamByte(0x48+k)!=(byte)(0x801570f1U>>(k*8)))return false;
                for(var k=0;k<dispatcher.Length;k++)if(owner.RamByte(0x1580+k)!=dispatcher[k])return false;
                return true;
            }
        }
        public string ParameterHex {get {var data=new byte[parameterAddresses.Length];for(var k=0;k<data.Length;k++)data[k]=(byte)owner.RamByte(parameterAddresses[k]);return BitConverter.ToString(data).Replace("-", "").ToLowerInvariant();}}
        public int ParameterBytes {get;private set;}
        public bool EnableParameters {get;}
        private static readonly int[] parameterAddresses={0x1618,0x1619,0x161a,0x161b,0x161c,0x161d,0x161e,0x161f,0x1614,0x1615,0x163c,0x163d,0x163e,0x163f,0x1640,0x1641,0x1642,0x1643,0x1638,0x1639};
        public long MarkerOverride {get;}
        public int ReadRemaining {get;private set;}
        public int ReadBytes {get;private set;}
        public int WrittenBytes {get;private set;}
        public int DispatcherBytes {get;private set;}
        public int KeyBytes {get;private set;}
        public int FeatureBytes {get;private set;}
        private int readAddress;
        private bool markerRead;
        private uint initialMarker;
        private readonly BlackwallImuEdmpService owner;
        private readonly byte[] dispatcher,feature;
    }

    public sealed class BlackwallImuEdmpService : Antmicro.Renode.Peripherals.IPeripheral
    {
        public BlackwallImuEdmpService(IMachine machine,BlackwallImuEdmpQuiesce bank,string fixtureHex,int ramFill,int microseconds,bool complete)
        {
            if(machine==null || bank==null || fixtureHex==null || fixtureHex.Length!=10 || ramFill<0 || ramFill>255 || microseconds<1 || microseconds>1000000)throw new ArgumentException("Explicit EDMP service fixture required");
            foreach(var c in fixtureHex)if(!Uri.IsHexDigit(c))throw new ArgumentException("Hex fixture required");
            this.bank=bank;FixtureHex=fixtureHex.ToLowerInvariant();RamFill=ramFill;Microseconds=microseconds;Complete=complete;
            timer=new LimitTimer(machine.ClockSource,1000000,this,"IMU-EDMP-service",(ulong)microseconds,Direction.Ascending,enabled:false,workMode:WorkMode.OneShot,eventEnabled:true);
            timer.LimitReached+=()=>
            {
                if(!Complete)return;
                if(Starts==1) {Array.Clear(ram,0,0x1800);ClearedBytes+=0x1800;}
                else DecimationCompletions++;
                Pending=false;Completions++;bank.ServiceIdle(true);
            };
            Reset();
        }
        public void Reset()
        {
            timer.Reset();for(var k=0;k<ram.Length;k++)ram[k]=(byte)RamFill;
            values.Clear();leases.Clear();for(var k=0;k<fixtureRegisters.Length;k++)values[fixtureRegisters[k]]=Convert.ToByte(FixtureHex.Substring(k*2,2),16);
            ProgramWrites=ParameterWrites=Starts=Completions=ClearedBytes=DecimationCompletions=Reads=Writes=IdleReads=0;
            Pending=false;saved0=saved1=-1;restored0=restored1=false;
        }
        public bool Contains(int address)
        {
            return (address>=0xa24f && address<=0xa255) || address==0xa2a7 || (address>=0xa271 && address<=0xa273) || address==0x73 || address==0x29 || address==0x2a || address==0xa297 || Array.IndexOf(parameterAddresses,address)>=0;
        }
        public bool SupportsRead(int address) {return values.ContainsKey(address) || address==0x29 || address==0x2a || address==0xa297;}
        public int Read(int address)
        {
            if(!SupportsRead(address))throw new ArgumentException("Unsupported service read");
            Reads++;leases.Add(address);
            if(address==0xa297) {IdleReads++;return Pending ? 0:bank.ReadIdleByte();}
            if(address==0x29) {var b=bank.ReadRegister(address);if(saved0<0)saved0=b;return b;}
            if(address==0x2a) {var b=bank.ReadRegister(address);if(saved1<0)saved1=b;return b;}
            return values[address];
        }
        public bool TryWrite(int address,byte[] data)
        {
            if(data==null || data.Length!=1 || Pending)return false;
            var value=data[0];
            if(address>=0xa24f && address<=0xa255)
            {
                var offset=address-0xa24f;
                if(offset!=ProgramWrites || value!=program[offset])return false;
                ProgramWrites++;Writes++;return true;
            }
            if(ProgramWrites!=7)return false;
            if(Array.IndexOf(parameterAddresses,address)>=0)
            {
                if(ParameterWrites>=parameterAddresses.Length || address!=parameterAddresses[ParameterWrites] || value!=parameters[ParameterWrites] || saved0<0 || saved1<0 || (saved1&0x40)!=0)return false;
                ram[address]=value;ParameterWrites++;Writes++;return true;
            }
            if(address==0x29 || address==0x2a)
            {
                if(saved0<0 || saved1<0)return false;
                bool valid;
                if(address==0x29)valid=(Completions==1 && value==saved0) || (Completions==1 && restored0 && restored1 && value==0) || (Completions==2 && value==saved0);
                else valid=(Starts==0 && ParameterWrites==9 && value==(saved1|0x40) && leases.Contains(address)) || (Completions==1 && value==saved1) || (Completions==1 && restored0 && restored1 && value==0x42) || (Completions==2 && value==saved1);
                if(!valid)return false;
                bank.ServiceWrite(address,value);leases.Remove(address);Writes++;
                if(address==0x29 && value==saved0)restored0=true;
                if(address==0x2a && value==saved1)restored1=true;
                return true;
            }
            if(!values.ContainsKey(address))return false;
            var previous=values[address];
            if(address==0x73)
            {
                if(!leases.Contains(address) || value!=(previous|0x20) || Starts!=Completions || Starts>=2 || (values[0xa2a7]&3)!=3)return false;
                if(Starts==0)
                {
                    if(ParameterWrites!=9 || bank.Enable0!=saved0 || bank.Enable1!=(saved1|0x40) || (values[0xa273]&0x20)!=0)return false;
                }
                else if(!restored0 || !restored1 || bank.Enable0!=0 || bank.Enable1!=0x42 || values[0xa271]!=0x3f || values[0xa272]!=0x1f || values[0xa273]!=0x3f)return false;
                values[address]=value;leases.Remove(address);Writes++;Starts++;Pending=true;bank.ServiceIdle(false);timer.ResetValue();timer.Enabled=true;return true;
            }
            bool accepted=false;
            if(address==0xa2a7)accepted=leases.Contains(address) && value==(previous|3) && Starts==0;
            else if(address>=0xa271 && address<=0xa273)
                accepted=(Completions==1 && value==0x3f) || (leases.Contains(address) && ((value==(previous&~0x20)) || (value==(previous|0x20)) || (address==0xa271 && Completions==2 && value==(previous&~3))));
            if(!accepted)return false;
            values[address]=value;leases.Remove(address);Writes++;return true;
        }
        internal bool GafControlIdle=>bank.Idle;
        internal byte GafControlValue(int address)
        {
            if(address==0x29)return bank.Enable0;
            if(address==0x2a)return bank.Enable1;
            if(address==0xa272 || address==0x73)return values[address];
            throw new ArgumentException("Unsupported GAF control register");
        }
        internal void GafControlStore(int address,byte value)
        {
            if(address==0x29 || address==0x2a)bank.ServiceWrite(address,value);
            else if(address==0xa272 || address==0x73)values[address]=value;
            else throw new ArgumentException("Unsupported GAF control register");
        }
        internal void GafControlBusy()=>bank.ServiceIdle(false);
        internal void GafControlReady()=>bank.ServiceIdle(true);
        internal byte ReadPowerControl() {return bank.ReadRegister(0x2a);}
        internal int PowerControl {get {return bank.Enable1;}}
        internal void WritePowerControl(byte value) {bank.ServiceWrite(0x2a,value);}
        internal void StoreRamByte(int address,byte value) {if(address<0 || address>=ram.Length)throw new ArgumentOutOfRangeException();ram[address]=value;}
        public int RamByte(int address) {if(address<0 || address>=ram.Length)throw new ArgumentOutOfRangeException();return ram[address];}
        public string FixtureHex {get;}
        public int RamFill {get;}
        public int Microseconds {get;}
        public bool Complete {get;}
        public int ProgramWrites {get;private set;}
        public int ParameterWrites {get;private set;}
        public int Starts {get;private set;}
        public int Completions {get;private set;}
        public int DecimationCompletions {get;private set;}
        public int ClearedBytes {get;private set;}
        public int Reads {get;private set;}
        public int Writes {get;private set;}
        public int IdleReads {get;private set;}
        public bool Pending {get;private set;}
        private int saved0,saved1;
        private bool restored0,restored1;
        private readonly byte[] ram=new byte[0x2000];
        private readonly Dictionary<int,byte> values=new Dictionary<int,byte>();
        private readonly HashSet<int> leases=new HashSet<int>();
        private readonly BlackwallImuEdmpQuiesce bank;
        private readonly LimitTimer timer;
        private static readonly int[] fixtureRegisters={0xa2a7,0xa271,0xa272,0xa273,0x73};
        private static readonly byte[] program={0,0x40,4,0x40,8,0x40,2};
        private static readonly int[] parameterAddresses={0x118,0x119,0x11a,0x11b,0x11c,0x11d,0x120,0x121,0x11e};
        private static readonly byte[] parameters={1,0,0,0,0,0,0,0x18,0};
    }

    public sealed class BlackwallImuOdrConfiguration : Antmicro.Renode.Peripherals.IPeripheral
    {
        public BlackwallImuOdrConfiguration(string hex)
        {
            if(hex==null || hex.Length!=16)throw new ArgumentException("Explicit eight-byte ODR/filter fixture required");
            foreach(var c in hex)if(!Uri.IsHexDigit(c))throw new ArgumentException("ODR fixture must be hex");
            FixtureHex=hex.ToLowerInvariant();for(var i=0;i<8;i++)initial[i]=Convert.ToByte(hex.Substring(2*i,2),16);Reset();
        }
        public void Reset() {Array.Copy(initial,values,8);Array.Clear(leases,0,8);Reads=Writes=0;history.Clear();}
        public bool Contains(int address) {return Array.IndexOf(addresses,address)>=0;}
        public byte Read(int address)
        {
            var i=Array.IndexOf(addresses,address);if(i<0)throw new ArgumentException("Unknown ODR register");
            Reads++;leases[i]=true;return values[i];
        }
        public byte PeekRegister(int address)
        {
            var i=Array.IndexOf(addresses,address);if(i<0)throw new ArgumentException("Unknown ODR register");
            return values[i];
        }
        internal bool TryWriteFifoTimestamp(byte value)
        {
            var i=Array.IndexOf(addresses,0xa258);
            if(!leases[i] || ((values[i]^value)&~3)!=0)return false;
            history.Add("a258:"+values[i].ToString("x2")+">"+value.ToString("x2"));
            values[i]=value;leases[i]=false;Writes++;return true;
        }
        public bool TryWrite(int address,byte value)
        {
            var i=Array.IndexOf(addresses,address);if(i<0 || !leases[i])return false;
            var delta=values[i]^value;var valid=false;
            foreach(var mask in masks[i])if((delta&~mask)==0)valid=true;
            if(!valid)return false;
            history.Add(address.ToString("x")+":"+values[i].ToString("x2")+">"+value.ToString("x2"));
            values[i]=value;leases[i]=false;Writes++;return true;
        }
        public string FixtureHex {get;}
        public string ValuesHex => BitConverter.ToString(values).Replace("-", "").ToLowerInvariant();
        public string History => string.Join("|",history);
        public int Reads {get;private set;}
        public int Writes {get;private set;}
        private static readonly int[] addresses={0x27,0x1b,0x1c,0xa258,0xa581,0xa583,0xa4aa,0xa4ac};
        private static readonly int[][] masks={new[] {7},new[] {15,0x70},new[] {15,0xf0},new[] {0x10},new[] {15},new[] {7},new[] {0x1e},new[] {7}};
        private readonly byte[] initial=new byte[8],values=new byte[8];
        private readonly bool[] leases=new bool[8];
        private readonly List<string> history=new List<string>();
    }

    public sealed class BlackwallImuI2cMaster : Antmicro.Renode.Peripherals.IPeripheral
    {
        public BlackwallImuI2cMaster(IMachine machine,string fixtureHex,int microseconds,bool complete,int error)
        {
            if(machine==null || fixtureHex==null || fixtureHex.Length!=10 || microseconds<1 || microseconds>1000000 || error<0 || (error&~0x3c)!=0)
                throw new ArgumentException("Explicit master control/MAG fixture, timing and error mask required");
            foreach(var c in fixtureHex)if(!Uri.IsHexDigit(c))throw new ArgumentException("Master fixture must be hex");
            initial=new byte[5];for(var i=0;i<5;i++)initial[i]=Convert.ToByte(fixtureHex.Substring(2*i,2),16);
            if((initial[0]&1)!=0 || (initial[2]&0x80)!=0 || (initial[3]&~3)!=0)throw new ArgumentException("Master fixture must start idle");
            FixtureHex=fixtureHex;Complete=complete;Error=error;Microseconds=microseconds;
            timer=new LimitTimer(machine.ClockSource,1000000,this,"IMU-I2CM",(ulong)microseconds,Direction.Ascending,enabled:false,workMode:WorkMode.OneShot,eventEnabled:true);
            timer.LimitReached+=Finish;Reset();
        }
        public void Reset()
        {
            timer.Reset();Control=initial[0];Sequencer=initial[2];Mode=initial[3];Unlocked=false;Pending=false;done=false;
            profile=false;addressSet=false;commandSet=false;controlRead=false;dataMask=0;resultReady=false;lastRead=false;
            Starts=Completions=IdentityReads=SoftResets=StatusPolls=DoneReads=Reads=Writes=0;status=0;history.Clear();
            Array.Clear(wdata,0,wdata.Length);
        }
        public bool SupportsRead(int address) {return address==0xa216 || address==0xa218 || address==0xa21b;}
        public byte[] ReadIreg(int address,int count)
        {
            if(count!=1)return null;
            if(address==0xa216) {controlRead=true;return new byte[] {Control};}
            if(address==0xa218)return new byte[] {status};
            if(address==0xa21b && resultReady) {resultReady=false;return new byte[] {result};}
            return null;
        }
        public bool TryWriteIreg(int address,byte[] data,bool interruptEnabled)
        {
            if(data==null || data.Length==0 || Pending || done)return false;
            if(address==0xa20f && data.Length==1 && data[0]==0x1e && !resultReady)
            {profile=true;addressSet=commandSet=controlRead=false;dataMask=0;return true;}
            if(address==0xa20e && data.Length==2 && data[1]==0x1e && !resultReady)
            {profile=true;readAddress=data[0];addressSet=true;commandSet=controlRead=false;dataMask=0;return true;}
            if(!profile)return false;
            if(address==0xa20e && data.Length==1) {readAddress=data[0];addressSet=true;return true;}
            if(address>=0xa233 && address+data.Length<=0xa239)
            {var off=address-0xa233;for(var i=0;i<data.Length;i++) {wdata[off+i]=data[i];dataMask|=1<<(off+i);}return true;}
            if((address==0xa206 || address==0xa207) && data.Length==1 && (data[0]&0x60)==0 && (data[0]&15)>0)
            {if(address==0xa206) {command=data[0];commandSet=true;}return true;}
            if(address!=0xa216 || data.Length!=1 || !controlRead || (data[0]&1)==0 || (data[0]&0xf6)!=(Control&0xf6) || !commandSet || !interruptEnabled)return false;
            var read=(command&0x30)==0x10;
            var reg=read ? readAddress:wdata[0];var value=wdata[1];
            if((command&0xc0)!=0x80 || (command&15)!=(read ? 1:2) || (read ? !addressSet || !CanReadMag(reg):(dataMask&3)!=3 || !CanWriteMag(reg,value)))return false;
            Control=data[0];controlRead=false;lastRead=read;requestRegister=reg;requestValue=value;Pending=true;status=1;resultReady=false;Starts++;
            timer.ResetValue();timer.Enabled=true;return true;
        }
        public bool TryWriteContinuation(int address,byte[] data,bool interruptEnabled)
        {
            if(address==0xa20f && data!=null && data.Length==1 && data[0]==0x1e && profile && addressSet && !Pending && !done && !resultReady)return true;
            return TryWriteIreg(address,data,interruptEnabled);
        }
        private bool CanReadMag(byte reg) {return reg==1 || reg==0x7c || reg==4 || reg==5 || reg==6;}
        private bool CanWriteMag(byte reg,byte value)
        {return (reg==0x7f && (value==0xca || value==0)) || (reg==0x7c && Unlocked && value==((Sequencer&0x7f)|0x80)) || (reg==4 && (value&0xfc)==(Mode&0xfc));}
        private void Finish()
        {
            if(!Complete)return;
            Pending=false;done=true;status=(byte)(2|Error);Completions++;
            if(lastRead)
            {
                result=Error!=0 ? (byte)0:requestRegister==1 ? initial[1]:requestRegister==0x7c ? Sequencer:requestRegister==6 ? initial[4]:(byte)(Mode&3);
                resultReady=true;Reads++;if(requestRegister==1)IdentityReads++;
                history.Add("r"+requestRegister.ToString("x2")+"="+result.ToString("x2"));
            }
            else
            {
                if(Error==0)
                {
                    if(requestRegister==0x7f)Unlocked=requestValue==0xca;
                    else if(requestRegister==0x7c) {Sequencer=(byte)(initial[2]&0x7f);Mode=0;SoftResets++;}
                    else if(requestRegister==4)Mode=requestValue;
                }
                Writes++;history.Add("w"+requestRegister.ToString("x2")+"="+requestValue.ToString("x2"));
            }
        }
        public bool TakeDoneInterrupt() {StatusPolls++;if(!done)return false;done=false;DoneReads++;return true;}
        public string FixtureHex {get;}
        public bool Complete {get;}
        public int Error {get;}
        public int Microseconds {get;}
        public byte Control {get;private set;}
        public byte Sequencer {get;private set;}
        public byte Mode {get;private set;}
        public bool Unlocked {get;private set;}
        public bool Pending {get;private set;}
        public int Starts {get;private set;}
        public int Completions {get;private set;}
        public int IdentityReads {get;private set;}
        public int SoftResets {get;private set;}
        public int StatusPolls {get;private set;}
        public int DoneReads {get;private set;}
        public int Reads {get;private set;}
        public int Writes {get;private set;}
        public string History => string.Join("|",history);
        private readonly byte[] initial,wdata=new byte[6];
        private readonly LimitTimer timer;
        private readonly List<string> history=new List<string>();
        private bool profile,addressSet,commandSet,controlRead,done,resultReady,lastRead;
        private int dataMask;
        private byte readAddress,command,status,result,requestRegister,requestValue;
    }

    public sealed class BlackwallImuAuxiliarySetup : Antmicro.Renode.Peripherals.IPeripheral
    {
        public BlackwallImuAuxiliarySetup(string configurationHex)
        {
            if(configurationHex==null || configurationHex.Length!=6)throw new ArgumentException("Explicit auxiliary pad/INT1 three-byte fixture required");
            foreach(var c in configurationHex)if(!Uri.IsHexDigit(c))throw new ArgumentException("Auxiliary fixture must be hex");
            ConfigurationHex=configurationHex;
            InitialPad=Convert.ToByte(configurationHex.Substring(0,2),16);
            InitialInterrupt0=Convert.ToByte(configurationHex.Substring(2,2),16);
            InitialInterrupt1=Convert.ToByte(configurationHex.Substring(4,2),16);
            Reset();
        }
        public void Reset()
        {
            PadValue=InitialPad;Interrupt0=InitialInterrupt0;Interrupt1=InitialInterrupt1;
            PadReads=PadWrites=InterruptReads=InterruptWrites=0;padRead=interruptRead=false;
        }
        public byte ReadPad() {PadReads++;padRead=true;return PadValue;}
        public bool TryWritePad(byte value)
        {
            if(!padRead || value!=((PadValue&0xf3)|0x14))return false;
            padRead=false;PadValue=value;PadWrites++;return true;
        }
        public byte[] ReadInterrupt() {InterruptReads++;interruptRead=true;return new byte[] {Interrupt0,Interrupt1};}
        public bool TryWriteInterrupt(byte first,byte second,bool fifoMask=false)
        {
            if((second&0x80)!=0 || (!fifoMask && (!interruptRead || first!=Interrupt0 || (second&0x5f)!=(Interrupt1&0x5f))))return false;
            interruptRead=false;Interrupt0=first;Interrupt1=second;InterruptWrites++;return true;
        }
        public string ConfigurationHex {get;}
        public byte InitialPad {get;}
        public byte InitialInterrupt0 {get;}
        public byte InitialInterrupt1 {get;}
        public byte PadValue {get;private set;}
        public byte Interrupt0 {get;private set;}
        public byte Interrupt1 {get;private set;}
        public int PadReads {get;private set;}
        public int PadWrites {get;private set;}
        public int InterruptReads {get;private set;}
        public int InterruptWrites {get;private set;}
        private bool padRead,interruptRead;
    }

    public sealed class BlackwallImuPowerConfiguration : Antmicro.Renode.Peripherals.IPeripheral
    {
        public BlackwallImuPowerConfiguration(IMachine machine,string configurationHex,int flushMicroseconds,bool completeFlush)
        {
            if(machine==null || configurationHex==null || configurationHex.Length!=12 || flushMicroseconds<1 || flushMicroseconds>1000000)
                throw new ArgumentException("Explicit power/FIFO/status six-byte/time fixture required");
            foreach(var c in configurationHex)if(!Uri.IsHexDigit(c))throw new ArgumentException("Configuration fixture must be hex");
            InitialPower=Convert.ToByte(configurationHex.Substring(0,2),16);
            InitialFifo=Convert.ToByte(configurationHex.Substring(2,2),16);
            if((InitialFifo&0x80)!=0)throw new ArgumentException("Initial FIFO flush must be idle");
            status=new byte[4];for(var i=0;i<4;i++)status[i]=Convert.ToByte(configurationHex.Substring(4+2*i,2),16);
            ConfigurationHex=configurationHex;CompleteFlush=completeFlush;FlushMicroseconds=flushMicroseconds;
            timer=new LimitTimer(machine.ClockSource,1000000,this,"IMU-FIFO-flush",(ulong)flushMicroseconds,Direction.Ascending,enabled:false,workMode:WorkMode.OneShot,eventEnabled:true);
            timer.LimitReached+=()=> {FlushPending=false;if(CompleteFlush) {FifoValue=(byte)(FifoValue&0x7f);FlushDone=true;FlushCompletions++;}};
            Reset();
        }
        public void Reset()
        {
            timer.Reset();PowerValue=InitialPower;FifoValue=InitialFifo;FlushPending=FlushDone=false;
            PowerReads=PowerWrites=FifoReads=FifoWrites=FlushRequests=FlushCompletions=Status0Reads=StatusApexReads=0;
            powerRead=fifoRead=false;
        }
        public byte ReadRegister(int register)
        {
            if(register==0x10) {PowerReads++;powerRead=true;return PowerValue;}
            if(register==0x20) {FifoReads++;fifoRead=true;return FifoValue;}
            throw new ArgumentException("Unsupported power/FIFO register");
        }
        public bool TryWriteRegister(int register,byte value)
        {
            if(register==0x10)
            {
                var delta=PowerValue^value;
                if(!powerRead || (delta&0xf0)!=0 || ((delta&3)!=0 && (delta&12)!=0))return false;
                PowerValue=value;PowerWrites++;powerRead=false;return true;
            }
            if(register==0x20 && fifoRead && FlushRequests==0 && value==(FifoValue|0x80))
            {
                fifoRead=false;FifoValue=value;FifoWrites++;FlushRequests++;FlushPending=true;FlushDone=false;
                timer.ResetValue();timer.Enabled=true;return true;
            }
            return false;
        }
        internal bool CanWriteFifoComparator(byte value)
        { return fifoRead && FlushDone && !FlushPending && ((value^FifoValue)&~8)==0; }
        internal bool TryWriteFifoComparator(byte value)
        {
            if(!CanWriteFifoComparator(value))return false;
            FifoValue=value;fifoRead=false;FifoWrites++;return true;
        }
        public byte[] ReadStatusPair(int register)
        {
            if(!FlushDone || (register!=0x19 && register!=0x3b))throw new ArgumentException("Explicit status pair requires completed FIFO flush");
            var offset=register==0x19 ? 0:2;
            if(offset==0)Status0Reads++;else StatusApexReads++;
            return new byte[] {status[offset],status[offset+1]};
        }
        public string ConfigurationHex {get;}
        public byte InitialPower {get;}
        public byte InitialFifo {get;}
        public byte PowerValue {get;private set;}
        public byte FifoValue {get;private set;}
        public bool CompleteFlush {get;}
        public int FlushMicroseconds {get;}
        public bool FlushPending {get;private set;}
        public bool FlushDone {get;private set;}
        public int PowerReads {get;private set;}
        public int PowerWrites {get;private set;}
        public int FifoReads {get;private set;}
        public int FifoWrites {get;private set;}
        public int FlushRequests {get;private set;}
        public int FlushCompletions {get;private set;}
        public int Status0Reads {get;private set;}
        public int StatusApexReads {get;private set;}
        private readonly byte[] status;
        private readonly LimitTimer timer;
        private bool powerRead,fifoRead;
    }

    // Only the original five-call clear sequence and a declared IPREG_MISC idle bit.
    public sealed class BlackwallImuEdmpQuiesce : Antmicro.Renode.Peripherals.IPeripheral
    {
        public BlackwallImuEdmpQuiesce(IMachine machine,string configurationHex,int idleMicroseconds,bool completeIdle)
        {
            if(machine==null || configurationHex==null || configurationHex.Length!=4 || idleMicroseconds<1 || idleMicroseconds>1000000)
                throw new ArgumentException("Explicit EDMP two-byte/time fixture required");
            foreach(var c in configurationHex)if(!Uri.IsHexDigit(c))throw new ArgumentException("EDMP fixture must be hex");
            Initial0=Convert.ToByte(configurationHex.Substring(0,2),16);Initial1=Convert.ToByte(configurationHex.Substring(2,2),16);
            CompleteIdle=completeIdle;IdleMicroseconds=idleMicroseconds;
            timer=new LimitTimer(machine.ClockSource,1000000,this,"IMU-EDMP-idle",(ulong)idleMicroseconds,Direction.Ascending,enabled:false,workMode:WorkMode.OneShot,eventEnabled:true);
            timer.LimitReached+=()=> {Pending=false;if(CompleteIdle) {Idle=true;IdleCompletions++;}};
            Reset();
        }
        public void Reset()
        {
            timer.Reset();Enable0=Initial0;Enable1=Initial1;Idle=CompleteIdle && (Enable1&0x40)==0;Pending=false;
            Reads0=Reads1=Writes=DisableRequests=IdleCompletions=IdleReads=0;read0=read1=false;
        }
        public byte ReadRegister(int register)
        {
            if(register==0x29) {Reads0++;read0=true;return Enable0;}
            if(register==0x2a) {Reads1++;read1=true;return Enable1;}
            throw new ArgumentException("Unknown EDMP register");
        }
        public bool TryWriteRegister(int register,byte value)
        {
            if(register!=0x29 && register!=0x2a)return false;
            var previous=register==0x29 ? Enable0:Enable1;
            var allowed=register==0x29 ? 0x0d:0x70;
            var delta=previous^value;
            if(!(register==0x29 ? read0:read1) || (value|previous)!=previous ||
                (delta!=0 && ((delta&allowed)==0 || (delta&(delta-1))!=0)))return false;
            if(register==0x29) {Enable0=value;read0=false;}
            else
            {
                Enable1=value;read1=false;
                if((previous&0x40)!=0 && (value&0x40)==0)
                {
                    DisableRequests++;Idle=false;Pending=true;timer.ResetValue();timer.Enabled=true;
                }
            }
            Writes++;return true;
        }
        internal void ServiceWrite(int register,byte value) {if(register==0x29) {Enable0=value;read0=false;} else {Enable1=value;read1=false;} Writes++;}
        internal void ServiceIdle(bool idle) {Idle=idle;Pending=!idle;}
        public byte ReadIdleByte() {IdleReads++;return (byte)(Idle ? 2:0);}
        public byte Initial0 {get;}
        public byte Initial1 {get;}
        public bool CompleteIdle {get;}
        public int IdleMicroseconds {get;}
        public byte Enable0 {get;private set;}
        public byte Enable1 {get;private set;}
        public bool Idle {get;private set;}
        public bool Pending {get;private set;}
        public int Reads0 {get;private set;}
        public int Reads1 {get;private set;}
        public int Writes {get;private set;}
        public int DisableRequests {get;private set;}
        public int IdleCompletions {get;private set;}
        public int IdleReads {get;private set;}
        private bool read0,read1;
        private readonly LimitTimer timer;
    }
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

}

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
}

namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using System.Collections.Generic;
    // Functional binary-solid L8 profile, not a shader ISA or physical raster implementation.
    public sealed class NemaRingConsumer
    {
        public NemaRingConsumer(uint start,uint size,Func<uint,int,byte[]> read,Action<uint,byte[]> write,bool areaCoverage=false,bool packingReference=false,bool textureReference=false)
        {
            Require((start&7)==0 && size>=16 && size<=65536 && size%16==0,"Invalid ring configuration");
            Range(start,size);this.start=start;this.size=size;this.read=read;this.write=write;this.areaCoverage=areaCoverage;this.packingReference=packingReference;this.textureReference=textureReference;Reset();
        }
        public void Submit(uint doorbell)
        {
            Require((doorbell&7)==4,"Unsupported doorbell flags");
            uint end=doorbell&~7U;
            Require(end>=start && (ulong)end<(ulong)start+size,"Doorbell outside ring");
            Require(end>Cursor,"Empty or wrapped ring is unsupported in this profile");
            var bytes=Read(Cursor,end-Cursor);var ring=new uint[bytes.Length/4];
            Buffer.BlockCopy(bytes,0,ring,0,bytes.Length);
            int position=0;
            if(!initialized)
            {
                var prefix=InitialWords();Require(ring.Length>=prefix.Length,"Incomplete GPU initialization");
                for(int i=0;i<prefix.Length;i++)Require(ring[i]==prefix[i],"Unsupported IMEM/register initialization");
                position=prefix.Length;
            }
            uint lists=0,words=0,pixels=0,draws=0,id=CompletedId,pending=uncompletedLists;
            bool irq=InterruptPending;var effects=new List<Effect>();var inputs=new List<Span>();
            var state=new Dictionary<uint,uint>(registers);
            while(position<ring.Length)
            {
                uint command=ring[position];
                if(command==0xf0)
                {
                    Require(position+4<=ring.Length && ring[position+2]==0x200f4,"Invalid list packet");
                    uint address=ring[position+1],length=ring[position+3];
                    Require((address&3)==0 && length>=2 && length<=4096 && length%2==0,"Unsupported command list size/alignment");
                    var listBytes=Read(address,length*4);var list=new uint[length];
                    Buffer.BlockCopy(listBytes,0,list,0,listBytes.Length);
                    inputs.Add(new Span(address,length*4));Render(list,state,effects,ref draws,ref pixels);
                    lists++;words+=length;pending++;position+=4;
                }
                else if(command==0x148)
                {
                    Require(position+8==ring.Length && pending>0,"Completion requires prior work and final hold");
                    uint next=(id+pending)&0xffffff;
                    Require(next!=0 && ring[position+1]==next && ring[position+2]==0xf8 && ring[position+3]==1
                        && ring[position+4]==0xff0000f0 && ring[position+5]==end
                        && ring[position+6]==0xff0000f4 && ring[position+7]==size,"Unsupported completion footer");
                    id=next;irq=true;pending=0;position+=8;
                }
                else throw new InvalidOperationException("Unsupported ring opcode: "+command.ToString("x"));
            }
            foreach(var effect in effects)
            {
                Require(!Overlap(effect.Address,(uint)effect.Bytes.Length,start,size),"Framebuffer overlaps ring");
                foreach(var input in inputs)Require(!Overlap(effect.Address,(uint)effect.Bytes.Length,input.Address,input.Length),"Framebuffer overlaps list");
            }
            for(int i=0;i<effects.Count;i++)for(int j=0;j<i;j++)
                Require(!Overlap(effects[i].Address,(uint)effects[i].Bytes.Length,effects[j].Address,(uint)effects[j].Bytes.Length),"Overlapping draws in one doorbell are unsupported");
            // All guest-controlled ranges, commands and footer validation precede DMA/state effects.
            foreach(var effect in effects)
            {
                write(effect.Address,effect.Bytes);
                LastSurfaceAddress=effect.Address;LastSurfaceStride=effect.Stride;LastSurfaceWidth=effect.Width;LastSurfaceHeight=effect.Height;
                if(effect.PackingSource!=0){LastPackingSource=effect.PackingSource;LastPackingStride=effect.PackingStride;LastPackingWidth=effect.Width*2;LastPackingHeight=effect.Height;PackingSubmits++;}
            }
            initialized=true;Cursor=end;CompletedId=id;InterruptPending=irq;uncompletedLists=pending;
            registers=state;ListsConsumed+=lists;Draws+=draws;ConsumedWords+=words;PixelsWritten+=pixels;
        }
        private void Render(uint[] list,Dictionary<uint,uint> state,List<Effect> effects,ref uint draws,ref uint pixels)
        {
            for(int i=0;i<list.Length;i+=2)
            {
                uint command=list[i],value=list[i+1];
                switch(command)
                {
                    case 0:case 4:case 8:case 0x110:case 0x114:case 0x1d0:case 0x118:case 0x11c:case 0x12c:case 0x104:case 0x108:
                    case 0x120:case 0x124:case 0x130:case 0x134:case 0x140:case 0x144:case 0x150:case 0x154:
                        state[command]=value;break;
                    case 0x10:case 0x14:case 0x18:case 0x1c:case 0x20:case 0x24:case 0x28:
                    case 0x160:case 0x164:case 0x168:case 0x16c:case 0x170:case 0x174:
                    case 0xc4:case 0xc8:case 0xcc:case 0x204:case 0x1d8:
                        Require(packingReference || textureReference,"Texture state requires explicit reference profile");state[command]=value;break;
                    case 0xff000100:
                        Raster(state,value,effects,ref pixels);draws++;break;
                    default:throw new InvalidOperationException("Unsupported command opcode: "+command.ToString("x"));
                }
            }
        }
        private static uint Get(Dictionary<uint,uint> state,uint key)
        {
            uint value;Require(state.TryGetValue(key,out value),"Draw before required GPU state");return value;
        }
        private static int X(uint packed) {return (short)(packed&65535);}
        private static int Y(uint packed) {return (short)(packed>>16);}
        private void Raster(Dictionary<uint,uint> s,uint command,List<Effect> effects,ref uint pixels)
        {
            if(packingReference && s.ContainsKey(0x11c) && Get(s,0x11c)==0x181f8000)
            {RasterPacking(s,command,effects,ref pixels);return;}
            if(textureReference && s.ContainsKey(0x11c) && (Get(s,0x11c)==0x141f801f || Get(s,0x11c)==0x141f8000))
            {RasterTexture(s,command,effects,ref pixels);return;}
            Require((Get(s,0x1d0)==0x504 || (textureReference && Get(s,0x1d0)==1)) && Get(s,0x118)==0x90000000 && Get(s,0x11c)==0x141f001f,"Unsupported shader/raster profile");
            uint color=Get(s,0x12c);uint red=(color>>16)&255,green=(color>>8)&255,blue=color&255;
            Require(color==0xff000000 || color==0xffffffff || (textureReference && red==green && green==blue),"Only binary or explicit reference grayscale colors are supported");
            int alpha=(int)(color>>24);bool sourceCopy=Get(s,0x1d0)==1;
            uint address=Get(s,0),format=Get(s,4),stride=format&65535,res=Get(s,8),width=res&65535,height=res>>16;
            Require((format>>16)==0x0900 && width>0 && height>0 && width<=1024 && height<=1024
                && stride>=width && stride<=4096,"Unsupported L8 surface");
            if((command&~0x07800000U)==5)
            {
                Require(areaCoverage,"Quad coverage requires explicit area-reference profile");
                RasterQuad(s,command,effects,address,stride,width,height,(byte)color,alpha,sourceCopy,ref pixels);return;
            }
            uint startXY=Get(s,0x104),endXY=Get(s,0x108),clipMin=Get(s,0x110),clipMax=Get(s,0x114);
            int x0=X(startXY),y0=Y(startXY),x1=X(endXY),y1=Y(endXY);
            int cx0=X(clipMin),cy0=Y(clipMin),cx1=X(clipMax),cy1=Y(clipMax);
            if(command==2)Require(x0<=x1 && y0<=y1,"Invalid rectangle bounds");
            else if(command==1)
            {
                Require(x0==x1 || y0==y1,"Diagonal lines are unsupported");
                int a=x0,b=y0;x0=Math.Min(x0,x1);y0=Math.Min(y0,y1);x1=Math.Max(a,x1)+1;y1=Math.Max(b,y1)+1;
            }
            else throw new InvalidOperationException("Unsupported raster command: "+command);
            x0=Math.Max(0,Math.Max(x0,cx0));y0=Math.Max(0,Math.Max(y0,cy0));
            x1=Math.Min((int)width,Math.Min(x1,cx1));y1=Math.Min((int)height,Math.Min(y1,cy1));
            uint count=(uint)(Math.Max(0,x1-x0)*Math.Max(0,y1-y0));
            Require((ulong)pixels+count<=16777216,"Pixel operation budget exceeded");
            Effect effect=Surface(effects,address,stride,width,height);
            for(int y=y0;y<y1;y++)for(int x=x0;x<x1;x++){int at=y*(int)stride+x;effect.Bytes[at]=sourceCopy?(byte)color:(byte)(((byte)color*alpha+effect.Bytes[at]*(255-alpha)+127)/255);}
            pixels+=count;
        }
        // Nominal identity/translation point-sampled texture policy; missing matrix axes are identity.
        private void RasterTexture(Dictionary<uint,uint> s,uint command,List<Effect> effects,ref uint pixels)
        {
            uint blend=Get(s,0x1d0);Require(command==2 && (blend==1 || blend==0x504) && Get(s,0x118)==0,"Unsupported texture shader");
            uint address=Get(s,0),format=Get(s,4),stride=format&65535,res=Get(s,8),width=res&65535,height=res>>16;
            uint src=Get(s,0x10),sf=Get(s,0x14),ss=sf&65535,sr=Get(s,0x18),sw=sr&65535,sh=sr>>16;
            uint textureFormat=sf>>24,sampling=(sf>>16)&255;bool a4=textureFormat==0x34,l4=textureFormat==0x35;Require(format>>16==0x0900 && width>0 && height>0 && width<=1024 && height<=1024 && stride>=width && stride<=4096 &&
                ((sampling==0 || sampling==9) && (a4 || l4 || textureFormat==9)) && sw>0 && sh>0 && sw<=2048 && sh<=1024 && ss>0 && ss<=4096 && ss>=((a4 || l4)?(sw+1)/2:sw),"Unsupported texture surface");
            foreach(uint axis in new uint[]{0x160,0x170})if(s.ContainsKey(axis))Require(Get(s,axis)==0x3f800000,"Unsupported texture scale");
            foreach(uint axis in new uint[]{0x164,0x16c})if(s.ContainsKey(axis))Require(Get(s,axis)==0,"Unsupported texture shear");
            float tx=BitConverter.ToSingle(BitConverter.GetBytes(Get(s,0x168)),0),ty=BitConverter.ToSingle(BitConverter.GetBytes(Get(s,0x174)),0);
            Require(!float.IsNaN(tx) && !float.IsInfinity(tx) && !float.IsNaN(ty) && !float.IsInfinity(ty) && Math.Abs(tx)<4096 && Math.Abs(ty)<4096,"Invalid texture translation");
            Require(sampling!=9 || (tx==Math.Floor(tx) && ty==Math.Floor(ty)),"Filtered texture requires integer reference alignment");
            uint length=ss*sh;Require((src>=0x20000000 && (ulong)src+length<=0x20380000) || (src>=0x438000 && (ulong)src+length<=0x7c0000),"Texture source outside declared memory");
            Require(!Overlap(src,length,address,stride*height),"Texture source/destination overlap");
            foreach(var e in effects)Require(!Overlap(src,length,e.Address,(uint)e.Bytes.Length),"Texture source aliases pending draw");
            var input=read(src,(int)length);Require(input!=null && input.Length==length,"Incomplete texture source");var target=Surface(effects,address,stride,width,height);
            uint a=Get(s,0x104),b=Get(s,0x108),c=Get(s,0x110),d=Get(s,0x114);
            int x0=Math.Max(0,Math.Max(X(a),X(c))),y0=Math.Max(0,Math.Max(Y(a),Y(c)));
            int x1=Math.Min((int)width,Math.Min(X(b),X(d))),y1=Math.Min((int)height,Math.Min(Y(b),Y(d)));
            Require(X(a)<=X(b) && Y(a)<=Y(b),"Invalid texture rectangle");
            uint count=(uint)(Math.Max(0,x1-x0)*Math.Max(0,y1-y0));Require((ulong)pixels+count<=16777216,"Pixel operation budget exceeded");
            uint color=a4?Get(s,0x1c):0;
            if(Get(s,0x11c)==0x141f8000)
                Require(blend==0x504 && Get(s,0xc4)==0 && Get(s,0xc8)==0x080c0002 && Get(s,0xcc)==0x80076187 &&
                    (!a4 || Get(s,0x204)==color) && Get(s,0x1d8)==Get(s,0x204),"Unsupported dynamic A4 color shader");
            if(a4)Require(((color>>16)&255)==((color>>8)&255) && ((color>>8)&255)==(color&255),"Unsupported non-grayscale A4 color");
            for(int y=y0;y<y1;y++)for(int x=x0;x<x1;x++)
            {
                int ix=(int)Math.Floor(x+0.5+tx),iy=(int)Math.Floor(y+0.5+ty);
                // At integer translation, center-based bilinear reduces to one texel; transparent border stays untouched.
                if(sampling==9 && (ix<0 || iy<0 || ix>=sw || iy>=sh))continue;
                int sx=Math.Max(0,Math.Min((int)sw-1,ix)),sy=Math.Max(0,Math.Min((int)sh-1,iy));
                int sample=(a4 || l4)?((input[sy*(int)ss+sx/2]>>(sx%2==0?4:0))&15)*17:input[sy*(int)ss+sx];
                int alpha=a4?(sample*(int)(color>>24)+127)/255:(Get(s,0x11c)==0x141f8000?(int)(Get(s,0x204)>>24):255);
                int value=a4?(byte)color:sample;int at=y*(int)stride+x;
                target.Bytes[at]=(byte)((value*alpha+(blend==1?0:target.Bytes[at]*(255-alpha))+127)/255);
            }
            pixels+=count;
        }
        // center-msb-alpha-high-reference-v1: declared functional policy, not physical GPU validation.
        private void RasterPacking(Dictionary<uint,uint> s,uint command,List<Effect> effects,ref uint pixels)
        {
            uint blend=Get(s,0x1d0),shader=Get(s,0xcc);bool first=blend==1;
            Require(command==2 && (first || blend==0x101) && Get(s,0x118)==0 && Get(s,0xc4)==0 && Get(s,0xc8)==0x080c0102 &&
                shader==(first ? 0x8a0761c7U:0x80076185U) && Get(s,0x1c)==0xff000000,"Unsupported packing shader");
            Require(Get(s,0x160)==0x40800000 && Get(s,0x164)==0 && Get(s,0x168)==(first ? 0xc0000000U:0U) &&
                Get(s,0x16c)==0 && Get(s,0x170)==0x3f800000 && Get(s,0x174)==0,"Unsupported packing matrix");
            if(!first)Require(Get(s,0x204)==0 && Get(s,0x1d8)==0,"Unsupported packing constants");
            uint address=Get(s,0x20),format=Get(s,0x24),stride=format&65535,res=Get(s,0x28),width=res&65535,height=res>>16;
            uint source=Get(s,0x10),sf=Get(s,0x14),ss=sf&65535,sr=Get(s,0x18),sw=sr&65535,sh=sr>>16;
            Require(format>>16==0x4500 && width>0 && height>0 && width<=512 && height<=1024 && stride>=width && stride<=4096 &&
                sf>>16==(first ? 0x3400U:0x3500U) && sw==width*4 && sh==height && ss==width*2,"Unsupported packing surfaces");
            Require(Get(s,0)==address && Get(s,4)==(0x35000000U|stride) && Get(s,8)==((height<<16)|(width*2)),"Packing target alias mismatch");
            Require(!Overlap(source,ss*sh,address,stride*height),"Packing source/destination overlap");
            foreach(var e in effects)Require(!Overlap(source,ss*sh,e.Address,(uint)e.Bytes.Length),"Packing source aliases pending draw");
            var packed=Read(source,ss*sh);var target=Surface(effects,address,stride,width,height);target.PackingSource=source;target.PackingStride=ss;
            uint a=Get(s,0x104),b=Get(s,0x108),c=Get(s,0x110),d=Get(s,0x114);
            int x0=Math.Max(0,Math.Max(X(a),X(c))),y0=Math.Max(0,Math.Max(Y(a),Y(c)));
            int x1=Math.Min((int)width,Math.Min(X(b),X(d))),y1=Math.Min((int)height,Math.Min(Y(b),Y(d)));
            Require(X(a)<=X(b) && Y(a)<=Y(b),"Invalid packing rectangle");
            uint count=(uint)(Math.Max(0,x1-x0)*Math.Max(0,y1-y0));Require((ulong)pixels+count<=16777216,"Pixel operation budget exceeded");
            for(int y=y0;y<y1;y++)for(int x=x0;x<x1;x++)
            {
                int src=y*(int)ss+x*2+(first ? 0:1),dst=y*(int)stride+x;
                byte high=(byte)(packed[src]>>4);
                target.Bytes[dst]=first ? (byte)(high<<4):(byte)Math.Min(255,target.Bytes[dst]+high);
            }
            pixels+=count;
        }
        private Effect Surface(List<Effect> effects,uint address,uint stride,uint width,uint height)
        {
            Effect effect=effects.Find(e=>e.Address==address);
            if(effect==null)
            {
                foreach(var previous in effects)Require(!Overlap(address,stride*height,previous.Address,(uint)previous.Bytes.Length),"Overlapping surface views are unsupported");
                effect=new Effect(address,Read(address,stride*height),stride,width,height);effects.Add(effect);
            }
            Require(effect.Stride==stride && effect.Width==width && effect.Height==height,"Surface layout changed within a doorbell");
            return effect;
        }
        private void RasterQuad(Dictionary<uint,uint> s,uint command,List<Effect> effects,uint address,uint stride,uint width,uint height,byte color,int alpha,bool sourceCopy,ref uint pixels)
        {
            var vertices=new Point[4];
            for(uint i=0;i<4;i++)vertices[i]=new Point((int)Get(s,0x120+i*16)/65536.0,(int)Get(s,0x124+i*16)/65536.0);
            double area=0;for(int i=0;i<4;i++)area+=Cross(vertices[i],vertices[(i+1)%4]);
            Require(area!=0,"Degenerate quad is unsupported");double orientation=area>0?1:-1;
            for(int i=0;i<4;i++)Require(orientation*Edge(vertices[i],vertices[(i+1)%4],vertices[(i+2)%4])>=0,"Non-convex quad is unsupported");
            double minX=vertices[0].X,maxX=minX,minY=vertices[0].Y,maxY=minY;
            foreach(var v in vertices){minX=Math.Min(minX,v.X);maxX=Math.Max(maxX,v.X);minY=Math.Min(minY,v.Y);maxY=Math.Max(maxY,v.Y);}
            uint low=Get(s,0x110),high=Get(s,0x114);
            int x0=Math.Max(0,Math.Max(X(low),(int)Math.Floor(minX))),y0=Math.Max(0,Math.Max(Y(low),(int)Math.Floor(minY)));
            int x1=Math.Min((int)width,Math.Min(X(high),(int)Math.Ceiling(maxX))),y1=Math.Min((int)height,Math.Min(Y(high),(int)Math.Ceiling(maxY)));
            uint count=(uint)(Math.Max(0,x1-x0)*Math.Max(0,y1-y0));Require((ulong)pixels+count<=16777216,"Pixel operation budget exceeded");
            var surface=Surface(effects,address,stride,width,height);
            for(int y=y0;y<y1;y++)for(int x=x0;x<x1;x++)
            {
                double coverage=Coverage(vertices,orientation,command,x,y);
                if(coverage<=0)continue;
                double effective=coverage*(sourceCopy ? 1.0:alpha/255.0);
                int index=y*(int)stride+x;surface.Bytes[index]=(byte)Math.Floor(color*effective+surface.Bytes[index]*(1-effective)+0.5);
            }
            pixels+=count;
        }
        private static double Coverage(Point[] vertices,double orientation,uint command,int x,int y)
        {
            var polygon=new List<Point>{new Point(x,y),new Point(x+1,y),new Point(x+1,y+1),new Point(x,y+1)};
            var center=new Point(x+0.5,y+0.5);
            for(int i=0;i<4;i++)
            {
                var a=vertices[i];var b=vertices[(i+1)%4];
                if(a.X==b.X && a.Y==b.Y)continue;
                if((command&(1U<<(26-i)))==0)
                {
                    double distance=orientation*Edge(a,b,center);double dx=orientation*(b.X-a.X),dy=orientation*(b.Y-a.Y);
                    if(distance<0 || distance==0 && !(dy<0 || dy==0 && dx>0))return 0;
                    continue;
                }
                var clipped=new List<Point>();
                for(int j=0;j<polygon.Count;j++)
                {
                    var p=polygon[j];var q=polygon[(j+1)%polygon.Count];double dp=orientation*Edge(a,b,p),dq=orientation*Edge(a,b,q);
                    if(dp>=0)clipped.Add(p);
                    if((dp>=0)!=(dq>=0)){double t=dp/(dp-dq);clipped.Add(new Point(p.X+t*(q.X-p.X),p.Y+t*(q.Y-p.Y)));}
                }
                polygon=clipped;if(polygon.Count==0)return 0;
            }
            double area=0;for(int i=0;i<polygon.Count;i++)area+=Cross(polygon[i],polygon[(i+1)%polygon.Count]);
            return Math.Min(1,Math.Max(0,Math.Abs(area)*0.5));
        }
        private static double Cross(Point a,Point b){return a.X*b.Y-a.Y*b.X;}
        private static double Edge(Point a,Point b,Point p){return (b.X-a.X)*(p.Y-a.Y)-(b.Y-a.Y)*(p.X-a.X);}
        private struct Point {public Point(double x,double y){X=x;Y=y;}public readonly double X,Y;}
        private byte[] Read(uint address,uint length)
        {
            Range(address,length);var value=read(address,(int)length);
            Require(value!=null && value.Length==length,"Incomplete guest memory read");return value;
        }
        private static void Range(uint address,uint length)
        {
            Require(length>0 && address>=0x20000000 && (ulong)address+length<=0x20380000,"Outside guest SRAM");
        }
        private static bool Overlap(uint a,uint n,uint b,uint m) {return (ulong)a<(ulong)b+m && (ulong)b<(ulong)a+n;}
        private static void Require(bool condition,string reason) {if(!condition)throw new InvalidOperationException(reason);}
        // Canonical initial uploads observed in all three original native captures.
        // Register names/addresses: pinned Think Silicon Nema headers, NOTICE.md.
        private static uint[] InitialWords()
        {
            var v=new List<uint>{0xf8,0};
            for(uint slot=0x18;slot<=0x1f;slot++)v.AddRange(new uint[]{0xc4,slot,0xc8,slot==0x1f?0x08000002U:0,0xcc,slot==0x1f?0x80000009U:0});
            v.AddRange(new uint[]{0x1d0,1,0x200,0,0x204,0xffffffff,
                0xc4,0x16,0xc8,0x080c0182,0xcc,0x8a9f5a24,
                0xc4,0x17,0xc8,0x080c0182,0xcc,0x8a9f5a34,0x388,1,
                0xc4,0x15,0xc8,0x080c0182,0xcc,0x8a8761c6,
                0xc4,0x14,0xc8,0x004e0002,0xcc,0x800b0286,
                0xc4,0x13,0xc8,0x0a980002,0xcc,0x8081a046});
            return v.ToArray();
        }
        public void AcknowledgeInterrupt() {InterruptPending=false;}
        public void Reset() {Cursor=start;CompletedId=0;InterruptPending=false;initialized=false;uncompletedLists=0;ListsConsumed=Draws=ConsumedWords=PixelsWritten=0;LastSurfaceAddress=LastSurfaceStride=LastSurfaceWidth=LastSurfaceHeight=LastPackingSource=LastPackingStride=LastPackingWidth=LastPackingHeight=PackingSubmits=0;registers.Clear();}
        public uint Cursor { get; private set; }
        public uint CompletedId { get; private set; }
        public bool InterruptPending { get; private set; }
        public uint ListsConsumed { get; private set; }
        public uint Draws { get; private set; }
        public uint ConsumedWords { get; private set; }
        public uint PixelsWritten { get; private set; }
        public uint LastSurfaceAddress {get;private set;}
        public uint LastSurfaceStride {get;private set;}
        public uint LastSurfaceWidth {get;private set;}
        public uint LastSurfaceHeight {get;private set;}
        public uint LastPackingSource {get;private set;}
        public uint LastPackingStride {get;private set;}
        public uint LastPackingWidth {get;private set;}
        public uint LastPackingHeight {get;private set;}
        public uint PackingSubmits {get;private set;}
        public bool HasPendingWork=>uncompletedLists>0;
        private sealed class Span {public Span(uint address,uint length){Address=address;Length=length;}public readonly uint Address,Length;}
        private sealed class Effect {public Effect(uint address,byte[] bytes,uint stride,uint width,uint height){Address=address;Bytes=bytes;Stride=stride;Width=width;Height=height;}public uint PackingSource,PackingStride;public readonly uint Address,Stride,Width,Height;public readonly byte[] Bytes;}
        private readonly uint start,size;
        private readonly Func<uint,int,byte[]> read;
        private readonly Action<uint,byte[]> write;
        private readonly bool areaCoverage,packingReference,textureReference;
        private bool initialized;
        private uint uncompletedLists;
        private Dictionary<uint,uint> registers=new Dictionary<uint,uint>();
    }
}

namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals.CPU;

    public sealed class BlackwallNemaRingDevice : IBlackwallGpuCommandDevice
    {
        public BlackwallNemaRingDevice(IMachine machine,CortexM cpu,BlackwallG2StartupFixture owner,bool referenceCoverage=false,bool packingReference=false,bool textureReference=false)
        {
            this.machine=machine;this.cpu=cpu;this.referenceCoverage=referenceCoverage;this.packingReference=packingReference;this.textureReference=textureReference;owner.AttachGpuCommandDevice(this);
        }
        public void Submit(uint ringBase,uint ringBytes,uint doorbell)
        {
            try
            {
                if(consumer==null)
                {
                    start=ringBase;size=ringBytes;
                    consumer=new NemaRingConsumer(start,size,
                        (address,count)=>machine.SystemBus.ReadBytes(address,count),
                        (address,data)=>machine.SystemBus.WriteBytes(data,address),referenceCoverage,packingReference,textureReference);
                }
                if(start!=ringBase || size!=ringBytes)throw new InvalidOperationException("Ring changed without GPU reset");
                var packs=consumer.PackingSubmits;var lists=consumer.ListsConsumed;var words=consumer.ConsumedWords;var pixels=consumer.PixelsWritten;var id=consumer.CompletedId;var draws=consumer.Draws;
                consumer.Submit(doorbell);Doorbells++;LastDoorbell=doorbell;
                ListsConsumed+=consumer.ListsConsumed-lists;ConsumedWords+=consumer.ConsumedWords-words;PixelsWritten+=consumer.PixelsWritten-pixels;
                Draws+=consumer.Draws-draws;
                if(consumer.LastSurfaceAddress!=0)
                {
                    FrameAddress=consumer.LastSurfaceAddress;FrameStride=consumer.LastSurfaceStride;FrameWidth=consumer.LastSurfaceWidth;FrameHeight=consumer.LastSurfaceHeight;
                    FrameBytes=machine.SystemBus.ReadBytes(FrameAddress,(int)(FrameStride*FrameHeight));
                    NonzeroPixels=0;foreach(var pixel in FrameBytes)if(pixel!=0)NonzeroPixels++;
                    if(FrameWidth==576 && FrameHeight==288)
                    {
                        ScreenFrameBytes=new byte[576*288];byte min=255,max=0;ScreenNonzeroPixels=0;
                        for(int y=0;y<288;y++)Array.Copy(FrameBytes,y*(int)FrameStride,ScreenFrameBytes,y*576,576);
                        foreach(var pixel in ScreenFrameBytes){if(pixel!=0)ScreenNonzeroPixels++;if(pixel<min)min=pixel;if(pixel>max)max=pixel;}
                        ScreenHasDetail=min!=max;ScreenFrameAddress=FrameAddress;ScreenSourceStride=FrameStride;ScreenCaptures++;
                    }
                }
                if(consumer.PackingSubmits>packs && consumer.LastPackingWidth==576 && consumer.LastPackingHeight==288)
                {
                    CompleteScreenFrameBytes=machine.SystemBus.ReadBytes(consumer.LastPackingSource,576*288);
                    byte min=255,max=0;CompleteScreenNonzero=0;
                    foreach(var pixel in CompleteScreenFrameBytes){if(pixel!=0)CompleteScreenNonzero++;if(pixel<min)min=pixel;if(pixel>max)max=pixel;}
                    CompleteScreenHasDetail=min!=max;CompleteScreenAddress=consumer.LastPackingSource;CompleteScreenCaptures++;
                }
                if(consumer.CompletedId!=id){CompletionEvents++;LastCompletedId=consumer.CompletedId;IrqAssertions++;}
                IRQ.Set(consumer.InterruptPending);
            }
            catch(InvalidOperationException e)
            {
                Fault=e.Message;Rejections++;cpu.IsHalted=true;
                throw new CpuAbortException("BLACKWALL Nema ring: "+e.Message);
            }
        }
        public void AcknowledgeInterrupt() {if(consumer!=null){if(consumer.InterruptPending)IrqAcks++;consumer.AcknowledgeInterrupt();}IRQ.Set(false);}
        public void BeginEpoch() {consumer=null;IRQ.Set(false);Fault="";Epochs++;}
        public void Reset() {consumer=null;IRQ.Set(false);Doorbells=LastDoorbell=Rejections=ListsConsumed=ConsumedWords=PixelsWritten=CompletionEvents=LastCompletedId=IrqAssertions=IrqAcks=Epochs=Draws=0;CompleteScreenFrameBytes=new byte[0];CompleteScreenHasDetail=false;CompleteScreenNonzero=CompleteScreenAddress=CompleteScreenCaptures=0;ScreenFrameBytes=new byte[0];ScreenHasDetail=false;ScreenNonzeroPixels=ScreenFrameAddress=ScreenSourceStride=ScreenCaptures=0;NonzeroPixels=0;FrameAddress=FrameStride=FrameWidth=FrameHeight=0;FrameBytes=new byte[0];Fault="";}
        public uint CompletedId=>consumer==null?0:consumer.CompletedId;
        public bool HasPendingWork=>consumer!=null && consumer.HasPendingWork;
        public uint ListsConsumed {get;private set;}
        public uint ConsumedWords {get;private set;}
        public uint PixelsWritten {get;private set;}
        public uint CompletionEvents {get;private set;}
        public uint LastCompletedId {get;private set;}
        public uint IrqAssertions {get;private set;}
        public uint IrqAcks {get;private set;}
        public uint Epochs {get;private set;}
        public uint Draws {get;private set;}
        public uint FrameAddress {get;private set;}
        public uint FrameStride {get;private set;}
        public uint FrameWidth {get;private set;}
        public uint FrameHeight {get;private set;}
        public byte[] CompleteScreenFrameBytes {get;private set;}=new byte[0];
        public bool CompleteScreenHasDetail {get;private set;}
        public uint CompleteScreenNonzero {get;private set;}
        public uint CompleteScreenAddress {get;private set;}
        public uint CompleteScreenCaptures {get;private set;}
        public byte[] ScreenFrameBytes {get;private set;}=new byte[0];
        public bool ScreenHasDetail {get;private set;}
        public uint ScreenNonzeroPixels {get;private set;}
        public uint ScreenFrameAddress {get;private set;}
        public uint ScreenSourceStride {get;private set;}
        public uint ScreenCaptures {get;private set;}
        public uint NonzeroPixels {get;private set;}
        public byte[] FrameBytes {get;private set;}=new byte[0];
        public string CoverageProfile=>referenceCoverage?"area-reference":"strict";
        public bool InterruptPending=>consumer!=null && consumer.InterruptPending;
        public uint Doorbells {get;private set;}
        public uint LastDoorbell {get;private set;}
        public uint Rejections {get;private set;}
        public string Fault {get;private set;}="";
        public GPIO IRQ {get;}=new GPIO();
        private NemaRingConsumer consumer;
        private uint start,size;
        private readonly IMachine machine;
        private readonly CortexM cpu;
        private readonly bool referenceCoverage,packingReference,textureReference;
    }
}

namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using Antmicro.Renode.Peripherals.I2C;
    // TI SBOS864 register interface with an explicit instant, constant-light scenario.
    // No optical response, analog conversion timing, thresholds, or interrupt delivery.
    public sealed class BlackwallOpt3007Bootstrap : II2CPeripheral
    {
        public BlackwallOpt3007Bootstrap(BlackwallStrictIom owner,int resultWord=0)
        {
            if(owner==null || owner.Module!=2 || resultWord<0 || resultWord>0xbfff)throw new ArgumentException("IOM2 and explicit bounded OPT3007 light sample required");
            this.owner=owner;ResultWord=(ushort)resultWord;Reset();
        }
        public void Reset(){Pointer=cursor=0;configuration=0xc810;low=0xc000;high=0xbfff;Reads=Writes=Rejections=0;}
        private static bool Known(int address)=>address>=0 && address<=3 || address==0x7e || address==0x7f;
        public bool TryWrite(byte[] data)
        {
            if(data==null || (data.Length!=1 && data.Length!=3) || !Known(data[0]))return false;
            if(data.Length==3)
            {
                if(data[0]<1 || data[0]>3)return false;
                ushort value=(ushort)((data[1]<<8)|data[2]);
                if(data[0]==1)configuration=(ushort)(value&0xfe1f);
                else if(data[0]==2)low=value;else high=value;
            }
            Pointer=data[0];cursor=0;Writes++;return true;
        }
        public bool TryRead(int count,out byte[] data)
        {
            data=null;if(count<1 || count>2 || cursor+count>2)return false;
            ushort value=Pointer==0 ? ResultWord:Pointer==1 ? (ushort)(configuration|((configuration&0x600)!=0 ? 0x80:0)):
                Pointer==2 ? low:Pointer==3 ? high:Pointer==0x7e ? (ushort)0x5449:(ushort)0x3001;
            data=new byte[count];for(int k=0;k<count;k++)data[k]=(byte)(value>>(8*(1-cursor-k)));
            cursor+=count;Reads++;return true;
        }
        public void Write(byte[] data){if(!TryWrite(data)){Rejections++;owner.RejectDiagnosticPeerAccess("opt3007-write",data==null?0u:(uint)data.Length);}}
        public byte[] Read(int count=1){if(TryRead(count,out var data))return data;Rejections++;owner.RejectDiagnosticPeerAccess("opt3007-read",(uint)count);return new byte[0];}
        public void FinishTransmission(){cursor=0;}
        public string FunctionalProfile=>"constant-light-instant-conversion-v1";
        public ushort ResultWord {get;}
        public int Pointer {get;private set;}
        public int Reads {get;private set;}
        public int Writes {get;private set;}
        public int Rejections {get;private set;}
        private int cursor;private ushort configuration,low,high;
        private readonly BlackwallStrictIom owner;
    }
}

namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using System.Collections.Generic;
    using Antmicro.Renode.Peripherals;

    public sealed class BlackwallImuRawFifo : IPeripheral
    {
        public BlackwallImuRawFifo(bool enabled=false,bool bigEndian=false,int capacityPackets=128,int frameBytes=16)
        {
            if((frameBytes!=16 && frameBytes!=32) || capacityPackets<1 || capacityPackets>2048/frameBytes)
                throw new ArgumentException("Explicit raw16/raw32 packet capacity within the 2KB profile required");
            Enabled=enabled;BigEndian=bigEndian;CapacityPackets=capacityPackets;FrameBytes=frameBytes;
        }

        public bool TryEnqueueFrame(byte[] frame)
        {
            if(!Enabled || (EnqueueGate!=null && !EnqueueGate()) || frame==null || frame.Length!=FrameBytes || frames.Count==CapacityPackets)
                return false;
            if(FrameBytes==16 ? frame[0]!=0x68 : (frame[0]&0xf0)!=0xe0 || (frame[1]&0xf3)!=0x13)
                return false;
            frames.Enqueue((byte[])frame.Clone());PacketsEnqueued++;FrameEnqueued?.Invoke();return true;
        }

        public bool TryBeginRead(int register,int byteCount)
        {
            if(!Enabled || ReadActive)return false;
            byte[] selected;
            int packets;
            if(register==0x12 && byteCount==2)
            {
                var count=frames.Count;
                selected=BigEndian ? new byte[]{(byte)(count>>8),(byte)count}
                                   : new byte[]{(byte)count,(byte)(count>>8)};
                packets=0;
            }
            else if(register==0x14 && byteCount>0 && byteCount%FrameBytes==0 && byteCount/FrameBytes<=frames.Count)
            {
                selected=new byte[byteCount];packets=byteCount/FrameBytes;
                var prefix=frames.ToArray();
                for(var index=0;index<packets;index++)Array.Copy(prefix[index],0,selected,index*FrameBytes,FrameBytes);
            }
            else return false;
            readBuffer=selected;readCursor=0;reservedPackets=packets;return true;
        }

        public byte[] ReadChunk(int count)
        {
            if(!ReadActive || count<1 || count>ReadRemaining)return null;
            var result=new byte[count];Array.Copy(readBuffer,readCursor,result,0,count);
            readCursor+=count;ReadBytes+=count;return result;
        }

        public bool TryFinishRead()
        {
            if(!ReadActive || ReadRemaining!=0)return false;
            for(var index=0;index<reservedPackets;index++)frames.Dequeue();
            PacketsConsumed+=reservedPackets;ReadsCompleted++;ClearRead();return true;
        }

        public bool TryFlush()
        {
            if(!Enabled || ReadActive)return false;
            frames.Clear();Flushes++;return true;
        }

        public void Reset()
        {
            frames.Clear();ClearRead();PacketsEnqueued=PacketsConsumed=ReadBytes=ReadsCompleted=Flushes=0;
            DeviceReset?.Invoke();
        }

        private void ClearRead() { readBuffer=null;readCursor=reservedPackets=0; }
        public bool Enabled {get;}
        public bool BigEndian {get;}
        public int CapacityPackets {get;}
        public int FrameBytes {get;}
        public int PacketCount => frames.Count;
        public bool ReadActive => readBuffer!=null;
        public int ReadRemaining => ReadActive ? readBuffer.Length-readCursor : 0;
        public long PacketsEnqueued {get;private set;}
        public long PacketsConsumed {get;private set;}
        public long ReadBytes {get;private set;}
        public long ReadsCompleted {get;private set;}
        public long Flushes {get;private set;}
        public event Action FrameEnqueued;
        public event Action DeviceReset;
        internal Func<bool> EnqueueGate {get;set;}
        private readonly Queue<byte[]> frames=new Queue<byte[]>();
        private byte[] readBuffer;
        private int readCursor,reservedPackets;
    }
}

namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using Antmicro.Renode.Peripherals.I2C;

    public interface IBlackwallImuFifoRegisters
    {
        bool HandlesRegister(int register);
        bool TryWrite(byte[] data);
        bool TryBeginRead(int register,int bytes);
        byte[] ReadChunk(int bytes);
        bool TryFinishRead();
        bool ReadActive {get;}
        void Reset();
    }

    public sealed class BlackwallImuFifoTransport : II2CPeripheral
    {
        public BlackwallImuFifoTransport(BlackwallStrictIom owner,II2CPeripheral startupPeer,BlackwallImuRawFifo rawFifo=null,BlackwallImuFifoThreshold threshold=null,IBlackwallImuFifoRegisters configuration=null)
        {
            if(owner==null || owner.Module!=4 || startupPeer==null)
                throw new ArgumentException("IOM4 and an existing startup peer required");
            if(threshold!=null && !Object.ReferenceEquals(threshold.RawFifo,rawFifo))
                throw new ArgumentException("Threshold and transport must share the same FIFO");
            this.owner=owner;StartupPeer=startupPeer;RawFifo=rawFifo;Threshold=threshold;Configuration=configuration;
        }

        public void Write(byte[] data)
        {
            if(writeBuffer!=null)
            { AppendConfigurationWrite(data);return; }
            if(statusLease || (RawFifo!=null && RawFifo.ReadActive) || (Configuration!=null && Configuration.ReadActive))
            { Reject("peer-write",data==null ? 0 : data.Length);return; }
            if(Configuration!=null && data!=null && data.Length>0 && Configuration.HandlesRegister(data[0]))
            {
                var command=owner.RegistersCollection.Read(0x120);
                var remaining=(int)((owner.RegistersCollection.Read(0x12c)>>8)&0xfff);
                if((command&0xff)!=1 || remaining<1 || remaining>7 || data.Length!=Math.Min(4,remaining))
                {Reject("peer-write",data.Length);return;}
                if(remaining==1) {selected=data[0];Selections++;return;}
                writeBuffer=new byte[remaining];writeCursor=0;writeCommand=command;
                AppendConfigurationWrite(data);return;
            }
            if(FifoEnabled && RawFifo.PacketCount!=0 && data!=null && data.Length>=2 && data[0]==0x20 && (data[1]&0x80)!=0)
            { Reject("peer-write",data.Length);return; }
            if(FifoEnabled && data!=null && data.Length==1 && (data[0]==0x12 || data[0]==0x14))
            { selected=data[0];Selections++;return; }
            if(FifoEnabled && Threshold!=null && (RawFifo.PacketCount!=0 || Threshold.EventsRaised!=0)
                && data!=null && data.Length==1 && data[0]==0x19)
            { StartupPeer.Write(data);selected=0x19;Selections++;return; }
            StartupPeer.Write(data);selected=-1;
        }

        public byte[] Read(int count=1)
        {
            if(!FifoEnabled || selected<0)return StartupPeer.Read(count);
            if(Configuration!=null && Configuration.HandlesRegister(selected))
            {
                if(!Configuration.ReadActive)
                {
                    var command=owner.RegistersCollection.Read(0x120);
                    var remaining=(int)((owner.RegistersCollection.Read(0x12c)>>8)&0xfff);
                    if(count<1 || count>remaining || (command&0x80)!=0 || !Configuration.TryBeginRead(selected,remaining))
                    {Reject("peer-read",count);return null;}
                }
                var result=Configuration.ReadChunk(count);
                if(result==null) {Reject("peer-read",count);return null;}
                ChunksRead++;BytesRead+=result.Length;return result;
            }
            if(selected==0x19)
            {
                var command=owner.RegistersCollection.Read(0x120);
                var remaining=(int)((owner.RegistersCollection.Read(0x12c)>>8)&0xfff);
                if(statusLease || count!=2 || remaining!=2 || (command&0x80)!=0)
                { Reject("peer-read",count);return null; }
                var snapshot=Threshold.Snapshot();
                var baseline=StartupPeer.Read(count);
                if(baseline==null || baseline.Length!=2 || (baseline[0]&2)!=0)
                { Reject("peer-read",count);return null; }
                var result=(byte[])baseline.Clone();
                if(snapshot!=0)result[0]|=2;
                statusSnapshot=snapshot;statusLease=true;ChunksRead++;BytesRead+=2;return result;
            }
            if(!RawFifo.ReadActive)
            {
                // These pinned engine fields are read-only metadata, not a guest register write.
                var command=owner.RegistersCollection.Read(0x120);
                var remaining=(int)((owner.RegistersCollection.Read(0x12c)>>8)&0xfff);
                if(count<1 || count>remaining || (command&0x80)!=0 || !RawFifo.TryBeginRead(selected,remaining))
                { Reject("peer-read",count);return null; }
            }
            var data=RawFifo.ReadChunk(count);
            if(data==null) { Reject("peer-read",count);return null; }
            ChunksRead++;BytesRead+=data.Length;return data;
        }

        public void FinishTransmission()
        {
            if(writeBuffer!=null)
            {Reject("peer-finish",writeBuffer.Length-writeCursor);return;}
            if(Configuration!=null && Configuration.ReadActive)
            {
                if(!Configuration.TryFinishRead()) {Reject("peer-finish",0);return;}
                selected=-1;TransactionsCompleted++;
            }
            if(statusLease)
            {
                Threshold.Acknowledge(statusSnapshot);statusLease=false;selected=-1;TransactionsCompleted++;
            }
            if(FifoEnabled && selected>=0 && RawFifo.ReadActive)
            {
                if(!RawFifo.TryFinishRead()) { Reject("peer-finish",RawFifo.ReadRemaining);return; }
                selected=-1;TransactionsCompleted++;
            }
            StartupPeer.FinishTransmission();
        }

        public void Reset()
        {
            StartupPeer.Reset();RawFifo?.Reset();selected=-1;statusLease=false;statusSnapshot=0;
            Configuration?.Reset();
            writeBuffer=null;writeCursor=0;writeCommand=0;
            Selections=ChunksRead=BytesRead=TransactionsCompleted=0;
        }

        private void Reject(string operation,int value)
        { owner.RejectDiagnosticPeerAccess(operation=="peer-finish" ? "peer-read" : operation,(uint)Math.Max(0,value)); }
        public II2CPeripheral StartupPeer {get;}
        public BlackwallImuRawFifo RawFifo {get;}
        public BlackwallImuFifoThreshold Threshold {get;}
        public IBlackwallImuFifoRegisters Configuration {get;}
        public bool FifoEnabled => RawFifo!=null && RawFifo.Enabled;
        public int SelectedRegister => selected;
        public long Selections {get;private set;}
        public long ChunksRead {get;private set;}
        public long BytesRead {get;private set;}
        public long TransactionsCompleted {get;private set;}
        private int selected=-1;
        private bool statusLease;
        private ulong statusSnapshot;
        private byte[] writeBuffer;
        private int writeCursor;
        private uint writeCommand;
        private void AppendConfigurationWrite(byte[] data)
        {
            var remaining=(int)((owner.RegistersCollection.Read(0x12c)>>8)&0xfff);
            if(data==null || owner.RegistersCollection.Read(0x120)!=writeCommand || remaining!=writeBuffer.Length-writeCursor || data.Length!=Math.Min(4,remaining))
            {Reject("peer-write",data==null ? 0:data.Length);return;}
            Array.Copy(data,0,writeBuffer,writeCursor,data.Length);writeCursor+=data.Length;
            if(writeCursor!=writeBuffer.Length)return;
            var complete=writeBuffer;writeBuffer=null;writeCursor=0;writeCommand=0;selected=-1;
            if(!Configuration.TryWrite(complete))Reject("peer-write",complete.Length);
        }
        private readonly BlackwallStrictIom owner;
    }
}

namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals;

    // Explicit packet watermark profile, not guest register configuration or a physical pin.
    public sealed class BlackwallImuFifoThreshold : IPeripheral
    {
        public BlackwallImuFifoThreshold(BlackwallImuRawFifo rawFifo,int watermarkPackets=0,bool interruptEnabled=false,bool greaterOrEqual=true)
        {
            if(rawFifo==null || watermarkPackets<0 || watermarkPackets>rawFifo.CapacityPackets)
                throw new ArgumentException("A raw FIFO and watermark within its packet capacity required");
            RawFifo=rawFifo;initialWatermark=watermarkPackets;initialEnabled=interruptEnabled;initialGreater=greaterOrEqual;
            IRQ=new GPIO();rawFifo.FrameEnqueued+=OnFrameEnqueued;rawFifo.DeviceReset+=Reset;
        }

        private void OnFrameEnqueued()
        {
            if(!RawFifo.Enabled || !InterruptEnabled || WatermarkPackets==0)return;
            var count=RawFifo.PacketCount;
            if(GreaterOrEqual ? count>=WatermarkPackets : count==WatermarkPackets)
            { generation++;Pending=true;EventsRaised++;IRQ.Set(); }
        }

        public ulong Snapshot() => Pending ? generation : 0;

        public void Acknowledge(ulong snapshot)
        {
            if(!Pending || snapshot!=generation)return;
            Pending=false;StatusClears++;IRQ.Unset();
        }

        public void Reset()
        { generation++;Pending=false;EventsRaised=StatusClears=0;IRQ.Unset(); }

        public BlackwallImuRawFifo RawFifo {get;}
        public int WatermarkPackets => WatermarkProvider!=null ? WatermarkProvider():initialWatermark;
        public bool InterruptEnabled => InterruptProvider!=null ? InterruptProvider():initialEnabled;
        public bool GreaterOrEqual => GreaterProvider!=null ? GreaterProvider():initialGreater;
        public bool Pending {get;private set;}
        public long EventsRaised {get;private set;}
        public long StatusClears {get;private set;}
        public GPIO IRQ {get;}
        private ulong generation;
        private readonly int initialWatermark;
        private readonly bool initialEnabled,initialGreater;
        internal Func<int> WatermarkProvider {get;set;}
        internal Func<bool> InterruptProvider {get;set;}
        internal Func<bool> GreaterProvider {get;set;}
    }
}

namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;

    // Raw32 stop-on-full configuration. Register storage does not generate samples or GAF results.
    public sealed class BlackwallImuFifoConfiguration : IBlackwallImuFifoRegisters, IBlackwallImuIndirectExtension
    {
        public BlackwallImuFifoConfiguration(BlackwallImuIdentity startupPeer,BlackwallImuRawFifo rawFifo,BlackwallImuFifoThreshold threshold,int timestampControl=0x60)
        {
            if(startupPeer==null || startupPeer.Configuration==null || startupPeer.Auxiliary==null || !startupPeer.HasIndirectTransport || startupPeer.IndirectExtension!=null ||
               rawFifo==null || rawFifo.FrameBytes!=32 || rawFifo.EnqueueGate!=null || threshold==null || !Object.ReferenceEquals(threshold.RawFifo,rawFifo) || threshold.WatermarkProvider!=null || timestampControl<0 || timestampControl>255)
                throw new ArgumentException("One raw32 FIFO, threshold, shared power configuration and timed startup peer required");
            startup=startupPeer;raw=rawFifo;this.threshold=threshold;initialTimestamp=(byte)timestampControl;
            Reset();startup.AttachIndirectExtension(this);raw.DeviceReset+=Reset;
            raw.EnqueueGate=()=>Ready;
            threshold.WatermarkProvider=()=>Watermark;
            threshold.GreaterProvider=()=> (startup.Configuration.FifoValue&8)!=0;
            threshold.InterruptProvider=()=> (startup.Auxiliary.Interrupt0&2)!=0;
        }

        public bool HandlesRegister(int register)
        { return register==0x1d || (Active && ((register>=0x1d && register<=0x22) || register==0x28)); }

        public bool TryBeginRead(int register,int bytes)
        {
            if(ReadActive || !startup.Configuration.FlushDone || startup.Configuration.FlushPending || bytes<1 ||
               !(register>=0x1d && register+bytes<=0x23 || register==0x28 && bytes==1))return false;
            var snapshot=new byte[bytes];
            for(var k=0;k<bytes;k++)snapshot[k]=register+k==0x20 ? startup.Configuration.ReadRegister(0x20):register+k==0x28 ? decimation:registers[register+k-0x1d];
            buffer=snapshot;cursor=0;Active=true;Reads++;return true;
        }

        public byte[] ReadChunk(int bytes)
        {
            if(!ReadActive || bytes<1 || cursor+bytes>buffer.Length)return null;
            var result=new byte[bytes];Array.Copy(buffer,cursor,result,0,bytes);cursor+=bytes;return result;
        }

        public bool TryFinishRead()
        {
            if(!ReadActive || cursor!=buffer.Length)return false;
            buffer=null;cursor=0;return true;
        }

        public bool TryWrite(byte[] data)
        {
            if(!CanReconfigure || data==null || data.Length<2 || !HandlesRegister(data[0]))return false;
            var address=(int)data[0];var bytes=data.Length-1;
            if(address==0x28)
            {
                if(bytes!=1)return false;
                decimation=data[1];Writes++;return true;
            }
            if(address<0x1d || address+bytes>0x23)return false;
            var trial=(byte[])registers.Clone();var low=lowWritten;var watermark=Watermark;bool comparator=false;
            byte comparatorValue=startup.Configuration.FifoValue;
            for(var k=0;k<bytes;k++)
            {
                var reg=address+k;var value=data[k+1];trial[reg-0x1d]=value;
                if(reg==0x1e)low=true;
                if(reg==0x1f)
                {
                    if(!low)return false;
                    watermark=(trial[2]<<8)|trial[1];low=false;
                }
                if(reg==0x20) {comparator=true;comparatorValue=value;}
            }
            if((trial[0]!=0 && trial[0]!=7 && trial[0]!=0x87) || (trial[4]!=0 && trial[4]!=0x36 && trial[4]!=0x37) || (trial[5]&~3)!=0 ||
               ((trial[4]&1)!=0 && (trial[0]!=0x87 || (trial[5]&1)==0)))return false;
            if(comparator && ((trial[0]&0xc0)!=0 || !startup.Configuration.CanWriteFifoComparator(comparatorValue)))return false;
            if(comparator && !startup.Configuration.TryWriteFifoComparator(comparatorValue))
                throw new InvalidOperationException("Validated shared FIFO comparator changed during transaction");
            registers=trial;lowWritten=low;Watermark=watermark;Writes++;return true;
        }

        public bool Contains(int address) => Active && address==0xa258;

        public bool BeginRead(int address)
        {
            if(!Active || !Contains(address) || indirectPending || ReadActive)return false;
            indirectPending=true;timestampRead=false;return true;
        }

        public byte Read(int address)
        {
            if(!Contains(address) || !indirectPending)throw new ArgumentException("No matching FIFO timestamp read");
            indirectPending=false;timestampRead=true;IndirectReads++;
            return startup.Odr!=null ? startup.Odr.Read(address):timestampStorage;
        }

        public bool TryWrite(int address,byte[] data)
        {
            if(!Contains(address) || !CanReconfigure || !timestampRead || data==null || data.Length!=1)return false;
            var delta=data[0]^TimestampControl;
            if((delta&~3)==0)
            {
                if(startup.Odr!=null)
                { if(!startup.Odr.TryWriteFifoTimestamp(data[0]))return false; }
                else timestampStorage=data[0];
            }
            else if(startup.Odr==null || (delta&~0x10)!=0 || !startup.Odr.TryWrite(address,data[0]))return false;
            timestampRead=false;IndirectWrites++;return true;
        }

        public void Reset()
        {
            registers=new byte[]{0,0,0,0,0,0};decimation=0;Watermark=0;timestampStorage=initialTimestamp;
            Active=lowWritten=indirectPending=timestampRead=false;buffer=null;cursor=0;Reads=Writes=IndirectReads=IndirectWrites=0;
        }

        private bool CanReconfigure => Active && !ReadActive && !raw.ReadActive && raw.PacketCount==0 && !threshold.Pending;
        public bool Ready => Active && registers[0]==0x87 && registers[4]==0x37 && (registers[5]&1)!=0;
        public bool Active {get;private set;}
        public bool ReadActive => buffer!=null;
        public int Watermark {get;private set;}
        public byte TimestampControl => startup.Odr!=null ? startup.Odr.PeekRegister(0xa258):timestampStorage;
        public int Reads {get;private set;}
        public int Writes {get;private set;}
        public int IndirectReads {get;private set;}
        public int IndirectWrites {get;private set;}
        private readonly BlackwallImuIdentity startup;
        private readonly BlackwallImuRawFifo raw;
        private readonly BlackwallImuFifoThreshold threshold;
        private readonly byte initialTimestamp;
        private byte[] registers,buffer;
        private byte decimation;
        private byte timestampStorage;
        private int cursor;
        private bool lowWritten,indirectPending,timestampRead;
    }
}
