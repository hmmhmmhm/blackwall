namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using System.Collections.Generic;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals.I2C;
    using Antmicro.Renode.Peripherals.Timers;
    using Antmicro.Renode.Time;

    public interface IBlackwallImuIndirectExtension
    {
        bool Contains(int address);
        bool BeginRead(int address);
        byte Read(int address);
        bool TryWrite(int address,byte[] data);
        void Reset();
    }

    // Declared identity and optional bounded reset fixtures; not physical register defaults.
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
            string edmpServiceFixtureHex="",int edmpRamFill=165,int edmpServiceMicroseconds=1000,bool completeEdmpService=true,string patchDispatcherHex="",string patchFeatureHex="",long patchKeyOverride=-1,bool b2sParameters=false,string womConfigurationHex="",string powerSaveTimeHex="",string gafParametersHex="",bool gafConfiguration=false,int gafClockVariationByte=-1,bool initialIregReady=false)
        {
            if(owner==null || owner.Module!=4 || (profile!="icm45608-whoami-only" && profile!="icm45608-reset-lifecycle") || identityByte<0 || identityByte>255)
                throw new ArgumentException("Explicit IOM4 identity fixture required");
            var lifecycle=profile=="icm45608-reset-lifecycle";
            if(initialIregReady && sregControl<0)throw new ArgumentException("Initial indirect readiness requires explicit indirect fixture");
            InitialIregReady=initialIregReady;
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
            Service?.Reset();serviceWriteCursor=-1;Patch?.Reset();patchWriteCursor=-1;Wom?.Reset();womWriteCursor=-1;PowerSave?.Reset();powerSaveWriteCursor=-1;GafParameters?.Reset();gafWriteCursor=-1;gafWriteBase=-1;gafWriteReadEpoch=-1;
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
                    (data.Length==3 && data[0]==0x16 && Auxiliary.TryWriteInterrupt(data[1],data[2])))
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
            if(InitialInt1Config2>=0 && !ResetPending && data!=null)
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
            bool initialReady=InitialIregReady && ResetRequests==0 && InterfaceValue>=0 && DriveValue>=0;
            if(data==null || ResetPending || (!initialReady && (!ResetElapsed || DriveRestores!=1 || InterfaceRestores!=1)))return false;
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
            if(GafParameters!=null && PowerSave.Complete && !IregPending && !IregReady && data.Length==3 && data[0]==0x7c)
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
                else if(GafParameters!=null && GafParameters.ReadRemaining>0)value=new byte[] {GafParameters.ReadNext()};
                else if(PowerSave!=null && PowerSave.ReadRemaining>0)value=new byte[] {PowerSave.ReadNext()};
                else if(Patch!=null && Patch.ReadRemaining>0)value=new byte[] {(byte)Patch.ReadNext()};
                else if(IregAddress==0xa267)value=new byte[] {(byte)SregControl};
                else if(Service!=null && Service.ProgramWrites>0 && Service.SupportsRead(IregAddress))value=new byte[] {(byte)Service.Read(IregAddress)};
                else if(IregAddress==0xa297)value=new byte[] {Edmp.ReadIdleByte()};
                else if(Odr!=null && Odr.Contains(IregAddress))value=new byte[] {Odr.Read(IregAddress)};
                else value=Master?.ReadIreg(IregAddress,count);
                if(value!=null) {IregReady=(Patch!=null && Patch.ReadRemaining>0) || (PowerSave!=null && PowerSave.ReadRemaining>0) || (GafParameters!=null && GafParameters.ReadRemaining>0);pending=false;IregReads++;ReturnedBytes+=value.Length;return value;}
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
        public bool InitialIregReady {get;}
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
        public bool TryWriteInterrupt(byte first,byte second)
        {
            if(!interruptRead || first!=Interrupt0 || (second&0x80)!=0 || (second&0x5f)!=(Interrupt1&0x5f))return false;
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
}
