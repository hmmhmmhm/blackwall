"""Compose only declared runtime-event/GPIO changes into the retained native model."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def gpio_class(text):
    begin=text.index('    public sealed class BlackwallGpioInterruptIdle')
    end=text.index('    public sealed class BlackwallGpioConfig',begin)
    return text[begin:end]


def compose(s,base):
    research=s/'runtime-event-research-01'
    old_peer=(research/'before-renode-em9305-reset.cs').read_text()
    new_peer=(ROOT/'tools/renode-em9305-reset.cs').read_text()
    old_core=(research/'before-renode-strict-mmio.cs').read_text()
    new_core=(ROOT/'tools/renode-strict-mmio.cs').read_text()
    result=base
    for before,after in [
        (old_peer,new_peer),
        (gpio_class(old_core),gpio_class(new_core)),
        ('BlackwallCpuNormalSleep cpuNormalSleep = null)','BlackwallCpuNormalSleep cpuNormalSleep = null, BlackwallGpioInterruptIdle gpioInterruptController = null)'),
        ('            GpioInterrupts = gpioInterruptIdle ? new BlackwallGpioInterruptIdle() : null;',
         '            if(gpioInterruptController!=null && !gpioInterruptIdle) throw new System.ArgumentException("Explicit GPIO interrupt owner requires GPIO interrupt profile");\n            GpioInterrupts = gpioInterruptIdle ? (gpioInterruptController ?? new BlackwallGpioInterruptIdle()) : null;'),
    ]:
        assert result.count(before)==1,'Retained model component does not match'
        result=result.replace(before,after)
    return result


def imu_span(model):
    marker='namespace Antmicro.Renode.Peripherals.Miscellaneous'
    position=model.index('    public sealed class BlackwallImuIdentity')
    begin=model.rfind(marker,0,position);end=model.find(marker,position)
    return begin,len(model) if end<0 else end


def gaf_control_component(candidate,fragment):
    import hashlib
    assert hashlib.sha256(candidate.encode()).hexdigest()=='3ddefc4c7d372cd5c8bd42da9819bc290e1f52ca898ea865bf3e7e86f5c8c883'
    def replace(before,after):
        nonlocal candidate
        assert candidate.count(before)==1,'Pinned GAF integration anchor changed'
        candidate=candidate.replace(before,after,1)
    replace('bool gafConfiguration=false,int gafClockVariationByte=-1)',
            'bool gafConfiguration=false,int gafClockVariationByte=-1,bool gafOnDemandControl=false,int gafOnDemandMicroseconds=1000)')
    anchor='            if(gafParametersHex.Length!=0)GafParameters=new BlackwallImuGafParameters(Service,PowerSave,gafParametersHex,gafConfiguration,gafClockVariationByte);'
    replace(anchor,anchor+'\n            if(gafOnDemandControl)OnDemand=new BlackwallImuGafOnDemand(machine,Service,GafParameters,gafOnDemandMicroseconds);\n            else if(gafOnDemandMicroseconds!=1000)throw new ArgumentException("On-demand observation window requires explicit control profile");')
    replace('GafParameters?.Reset();gafWriteCursor=-1;', 'GafParameters?.Reset();OnDemand?.Reset();gafWriteCursor=-1;')
    replace('        public BlackwallImuGafParameters GafParameters {get;}',
            '        public BlackwallImuGafParameters GafParameters {get;}\n        public BlackwallImuGafOnDemand OnDemand {get;}')
    anchor='            if(Service!=null && Service.ProgramWrites==7 && data!=null && data.Length>0 && (data[0]==0x29 || data[0]==0x2a || data[0]==0x73))'
    replace(anchor,'''            if(OnDemand!=null && OnDemand.Active && data!=null && data.Length>0 && OnDemand.DirectRegister(data[0]))
            {
                if(data.Length==1 && OnDemand.CanSelectRead(data[0])) {Pointer=data[0];PointerWrites++;pending=true;return;}
                if(data.Length==2 && OnDemand.TryWriteRegister(data[0],data[1])) {Pointer=data[0];pending=false;return;}
                owner.RejectDiagnosticPeerAccess("gaf-control-write",(uint)data.Length);return;
            }
'''+anchor)
    anchor='            if(GafParameters!=null && GafParameters.ConfigurationEnabled && !IregPending && !IregReady)'
    replace(anchor,'''            if(OnDemand!=null && !IregPending && !IregReady && data.Length>=3 && data[0]==0x7c)
            {
                int address=(data[1]<<8)|data[2];
                if(address==4 && data.Length==4)
                {
                    if(!OnDemand.TryRequest(address,new byte[]{data[3]}))return false;
                    gafWriteCursor=gafWriteBase=gafWriteReadEpoch=powerSaveWriteCursor=womWriteCursor=patchWriteCursor=masterWriteCursor=serviceWriteCursor=-1;
                    IregAddress=address;Pointer=0x7c;pending=false;return true;
                }
                if(OnDemand.Active)
                {
                    if(data.Length==3 && OnDemand.CanSelectRead(address))
                    {IregAddress=address;IregPending=true;IregStarts++;pending=false;Pointer=0x7c;iregTimer.ResetValue();iregTimer.Enabled=true;return true;}
                    if(data.Length==4 && OnDemand.TryWriteRegister(address,data[3])) {IregAddress=address;Pointer=0x7c;pending=false;return true;}
                    return false;
                }
            }
'''+anchor)
    anchor='            if(Service!=null && Service.ProgramWrites==7 && pending && count==1 && (Pointer==0x29 || Pointer==0x2a || Pointer==0x73))'
    replace(anchor,'''            if(OnDemand!=null && OnDemand.Active && pending && count==1 && OnDemand.DirectRegister(Pointer))
            {
                if(!OnDemand.TryReadRegister(Pointer,out var controlValue)) {owner.RejectDiagnosticPeerAccess("gaf-control-read",(uint)count);return new byte[0];}
                pending=false;ReturnedBytes++;return new byte[]{controlValue};
            }
'''+anchor)
    anchor='                if(GafParameters!=null && GafParameters.ReadRemaining>0)value=new byte[] {GafParameters.ReadNext()};'
    replace(anchor,'''                if(OnDemand!=null && OnDemand.Active && OnDemand.OwnsRegister(IregAddress))
                {
                    if(!OnDemand.TryReadRegister(IregAddress,out var controlValue)) {owner.RejectDiagnosticPeerAccess("gaf-result-read",(uint)count);return new byte[0];}
                    value=new byte[]{controlValue};
                }
                else '''+anchor.lstrip())
    anchor='        internal byte ReadPowerControl() {return bank.ReadRegister(0x2a);}'
    replace(anchor,'''        internal bool GafControlIdle=>bank.Idle;
        internal byte GafControlValue(int address)
        {
            if(address==0x2a)return bank.Enable1;
            if(address==0xa272 || address==0x73)return values[address];
            throw new ArgumentException("Unsupported GAF control register");
        }
        internal void GafControlStore(int address,byte value)
        {
            if(address==0x2a)bank.ServiceWrite(address,value);
            else if(address==0xa272 || address==0x73)values[address]=value;
            else throw new ArgumentException("Unsupported GAF control register");
        }
        internal void GafControlBusy()=>bank.ServiceIdle(false);
'''+anchor)
    assert candidate.rstrip().endswith('}')
    return candidate.rstrip()[:-1]+fragment+'\n}\n'


def integrate_gaf(s,model,on_demand_control=False,on_demand_microseconds=1000):
    """Reuse the pinned bw353 IMU component; no other model component changes."""
    import hashlib
    import json
    assert 1<=on_demand_microseconds<=1000000 and (on_demand_control or on_demand_microseconds==1000)
    digest=lambda data:hashlib.sha256(data).hexdigest()
    prefix=s/'imu-clock-variation-source-01'
    manifest=json.loads((prefix/'verification-manifest.json').read_text())
    plan_path=s/'imu-clock-variation-plan-01.json'
    assert digest(plan_path.read_bytes())==manifest['files']['imu-clock-variation-plan-01.json']
    plan=json.loads(plan_path.read_text())
    path=prefix/'frozen/tools/renode-imu-identity.cs';candidate=path.read_text()
    assert digest(path.read_bytes())==manifest['frozen_sources']['tools/renode-imu-identity.cs']=='3ddefc4c7d372cd5c8bd42da9819bc290e1f52ca898ea865bf3e7e86f5c8c883'
    begin,end=imu_span(model)
    baseline=model[begin:end]
    assert digest(baseline.encode())=='fabd6fd5e0758e98861cf20ced4c10484b9389514f231babd4c86c6763580039'
    assert model.count(baseline)==1 and len(bytes.fromhex(plan['gaf_parameters_hex']))==153
    parent_sha=digest(candidate.encode())
    control_sha=None
    if on_demand_control:
        fragment=(ROOT/'tools/renode-gaf-ondemand.cs').read_text()
        control_sha=digest(fragment.encode())
        candidate=gaf_control_component(candidate,fragment)
    transformed=model[:begin]+candidate+model[end:]
    assert transformed.replace(candidate,baseline)==model
    profile=dict(baseline_sha256=digest(baseline.encode()),candidate_sha256=digest(candidate.encode()),plan_sha256=digest(plan_path.read_bytes()),source_manifest_sha256=digest((prefix/'verification-manifest.json').read_bytes()),parameters_hex=plan['gaf_parameters_hex'],clock_variation_byte=plan['clock_variation_byte'],fixture_profile=plan['gaf_profile'],fixture_sha256=plan['gaf_profile_sha256'],physical_trim_verified=False)
    if on_demand_control:profile.update(parent_component_sha256=parent_sha,on_demand_control=True,control_fragment_sha256=control_sha,calculation_supported=False,on_demand_observation_microseconds=on_demand_microseconds)
    return transformed,profile
