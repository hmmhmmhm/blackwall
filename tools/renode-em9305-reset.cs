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
