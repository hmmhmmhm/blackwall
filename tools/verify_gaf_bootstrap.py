"""Check an explicit cold GAF service scenario, not the sensor's numerical algorithm."""
import argparse,json,sys
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute
from verify_imu_gaf_ondemand import DRIVER
R=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();S=a.simulator.resolve();O=a.output.resolve()
if O.exists() or not O.is_relative_to(S) or O.is_relative_to(R):p.error('New private output required')
O.mkdir(mode=0o700);(O/'runner-source.py').write_bytes(Path(__file__).read_bytes())
base=(S/'gaf-render-scheduler-native-01/stock24/strict.cs').read_text();old=(R/'tools/renode-gaf-frozen-core.cs').read_text();new=R/'tools/renode-gaf-bootstrap.cs'
if new.exists():
 if base.count(old)!=1:raise ValueError('Changed frozen GAF component')
 base=base.replace(old,new.read_text()).replace('BlackwallImuGafFrozenCore','BlackwallImuGafBootstrap')
 anchor='        internal void GafControlBusy()=>bank.ServiceIdle(false);'
 if base.count(anchor)!=1:raise ValueError('Changed shared EDMP idle owner')
 base=base.replace(anchor,anchor+'\n        internal void GafControlReady()=>bank.ServiceIdle(true);')
 base=base.replace('data.Length==3 && address==0x5bc && OnDemand.BeginRamRead(address)','data.Length==3 && address<0x2000 && OnDemand.BeginRamRead(address)')
base=base.replace('        public bool Complete=>index==addresses.Length;','        public int DeclaredFieldLength(int address) {for(int k=0;k<addresses.Length;k++)if(address==addresses[k])return lengths[k];return 0;}\n        public bool Complete=>index==addresses.Length;')
base=base.replace('            if(OnDemand!=null && !IregPending && !IregReady && data.Length>=3 && data[0]==0x7c)','            if(OnDemand!=null && OnDemand.GuestReadActive && !IregPending && !pending && data.Length>=3 && data[0]==0x7c)\n            {OnDemand.EndGuestRead();IregReady=false;}\n            if(OnDemand!=null && !IregPending && !IregReady && data.Length>=3 && data[0]==0x7c)')
from screen_native_gpu import types
current=types((R/'tools/renode-imu-identity.cs').read_text())['BlackwallImuOdrConfiguration'][2]
base=base.replace(types(base)['BlackwallImuOdrConfiguration'][2],current,1)
base=base.replace('if(address==0x2a)return bank.Enable1;', 'if(address==0x29)return bank.Enable0;\n            if(address==0x2a)return bank.Enable1;').replace('if(address==0x2a)bank.ServiceWrite(address,value);','if(address==0x29 || address==0x2a)bank.ServiceWrite(address,value);')
base=base.replace('TryWriteInterrupt(byte first,byte second)', 'TryWriteInterrupt(byte first,byte second,bool fifoMask=false)').replace('if(!interruptRead || first!=Interrupt0 || (second&0x80)!=0 || (second&0x5f)!=(Interrupt1&0x5f))return false;', 'if((second&0x80)!=0 || (!fifoMask && (!interruptRead || first!=Interrupt0 || (second&0x5f)!=(Interrupt1&0x5f))))return false;').replace('Auxiliary.TryWriteInterrupt(data[1],data[2])', 'Auxiliary.TryWriteInterrupt(data[1],data[2],OnDemand!=null && OnDemand.Phase=="disabled")')
base=base.replace('            if(OnDemand!=null && OnDemand.Active && data!=null && data.Length>0 && OnDemand.DirectRegister(data[0]))','            if(OnDemand!=null && data!=null && data.Length>0 && OnDemand.MaskRegister(data[0]))\n            {\n                if(data.Length==1){Pointer=data[0];PointerWrites++;pending=true;return;}\n                var values=new byte[data.Length-1];Array.Copy(data,1,values,0,values.Length);\n                if(OnDemand.TryWriteMask(data[0],values)){Pointer=data[0];pending=false;return;}\n                owner.RejectDiagnosticPeerAccess("apex-mask-write",(uint)data.Length);return;\n            }\n            if(OnDemand!=null && OnDemand.Active && data!=null && data.Length>0 && OnDemand.DirectRegister(data[0]))').replace('            if(OnDemand!=null && OnDemand.Active && pending && count==1 && OnDemand.DirectRegister(Pointer))','            if(OnDemand!=null && pending && OnDemand.MaskRegister(Pointer))\n            {\n                var values=OnDemand.ReadMask(Pointer,count);\n                if(values==null){owner.RejectDiagnosticPeerAccess("apex-mask-read",(uint)count);return new byte[0];}\n                pending=false;ReturnedBytes+=values.Length;return values;\n            }\n            if(OnDemand!=null && OnDemand.Active && pending && count==1 && OnDemand.DirectRegister(Pointer))')
(O/'strict.cs').write_text(base)
(O/'board.repl').write_text('power: Miscellaneous.BlackwallPeripheralPower\n    mask: 32\n    profile: 1\n    offProfile: 0\niom: Miscellaneous.BlackwallStrictIom @ sysbus 0x40054000\n    power: power\n    module: 4\n')
profile=json.loads((S/'imu-clock-variation-plan-01.json').read_text());fields=json.loads((R/'docs/data/imu-gaf-default-profile.json').read_text())['fields'];prior=json.loads((S/'runtime-gaf-delay-1000-native-01/stock24/exports/disconnect.json').read_text())['imu_gaf']['history'];writes=[(int(t.split(':')[0],16),int(t.split(':')[1],16)) for t in prior.split('|')]
helper=DRIVER.split('for request in (2,4):')[0].replace('BlackwallImuGafOnDemand','BlackwallImuGafBootstrap')
test='''
owner,config=ready();configure(config);c=BlackwallImuGafBootstrap(m,owner,config,1000,BlackwallImuOdrConfiguration("0300000000000000"))
check('cold-profile-explicit',c.FunctionalProfile=='cold-bootstrap-v1' and not c.FaultInjected and not c.CalculationSupported)
check('request4-first-rejected',not c.TryRequest(4,Array[Byte]([4])))
def trigger(request):
 check('request-'+str(request),c.TryRequest(4,Array[Byte]([request])))
 for address,mask in [(0xa272,0x20),(0x2a,0x40),(0x73,0x20)]:
  ok,value=c.TryReadRegister(address);check('control-read-'+hex(address),ok)
  check('control-write-'+hex(address),c.TryWriteRegister(address,value&~mask if address==0xa272 else value|mask))
 ok,value=c.TryReadRegister(0xa297);check('busy',ok and value==0 and c.Pending)
 advance(999);check('not-early',c.Pending)
 advance(2);ok,value=c.TryReadRegister(0xa297);check('simulated-idle',ok and value==2 and not c.Pending)
trigger(2);check('first-service-only',c.CompletedServices==1 and not c.TryWriteRam(0x6a0,Array[Byte]([0]*4)))
trigger(4);check('two-services-no-claim',c.CompletedServices==2 and c.CompletedCalculations==0 and not c.CalculationSupported and c.AccuracyAssumed)
for address,mask in [(0xa272,0x20),(0x2a,0x40)]:
 ok,value=c.TryReadRegister(address);check('cleanup-read',ok)
 check('cleanup-write',c.TryWriteRegister(address,value|mask if address==0xa272 else value&~mask))
check('cleanup-idle',c.TryReadRegister(0xa297)[1]==2 and c.Phase=='disabled')
ok,v=c.TryReadRegister(0x29);check('runtime-enable0-read',ok)
check('runtime-enable0-write',c.TryWriteRegister(0x29,v^3))
ok,v2=c.TryReadRegister(0x29);check('runtime-enable0-shared-readback',ok and v2==v^3)
check('runtime-enable0-end-lease',c.TryWriteRegister(0x29,v2))
check('unwritten-apex-mask-rejected',c.ReadMask(0x39,2) is None)
check('apex-mask-write',c.TryWriteMask(0x39,Array[Byte]([0xcf,0x15])) and list(c.ReadMask(0x39,2))==[0xcf,0x15])
check('apex-reserved-atomic',not c.TryWriteMask(0x39,Array[Byte]([0,0x88])) and list(c.ReadMask(0x39,2))==[0xcf,0x15])
check('accuracy-scenario-read',c.BeginRamRead(0x5bc) and [c.TryReadRegister(0x5bc)[1] for _ in range(4)]==[0]*4)
check('unknown-ram-rejected',not c.BeginRamRead(0x600) and not c.TryWriteRam(0x2000,Array[Byte]([0])))
check('guest-upload',c.TryWriteRam(0xa00,Array[Byte]([0x12,0x56,0xab])))
check('guest-upload-readback',c.BeginRamRead(0xa00) and [c.TryReadRegister(0xa00)[1] for _ in range(3)]==[0x12,0x56,0xab])
check('guest-storage-partial-read',c.BeginRamRead(0xa00) and c.TryReadRegister(0xa00)[1]==0x12 and c.GuestReadActive)
c.EndGuestRead();check('guest-storage-reselect',not c.GuestReadActive and c.BeginRamRead(0xa01) and [c.TryReadRegister(0xa01)[1] for _ in range(2)]==[0x56,0xab])
check('unwritten-read-rejected',not c.BeginRamRead(0xa03))
check('known-host-writes',c.TryWriteRam(0x6a0,Array[Byte]([0,0,0xef,0xfe])))
check('guest-mounting-matrix-storage',c.TryWriteRam(0x1ac,Array[Byte]([150,0,0,0,150,0,0,0,150])) and owner.RamByte(0x1ac)==150)
check('observed-mode-write',c.TryWriteRam(0x1be,Array[Byte]([1])) and owner.RamByte(0x1be)==1)
check('decimation-source-encoding',c.BeginRamRead(0x188) and [c.TryReadRegister(0x188)[1] for _ in range(4)]==[0x80,0,0,0])
check('declared-mag-dt-read',c.BeginRamRead(0x4a8) and [c.TryReadRegister(0x4a8)[1] for _ in range(4)]==[owner.RamByte(0x4a8+n) for n in range(4)])
check('nominal-clock-gyrdt',c.BeginRamRead(0x4a0) and [c.TryReadRegister(0x4a0)[1] for _ in range(4)]==[owner.RamByte(0x294+n) for n in range(4)])
c.Reset();check('reset',not c.Active and not c.Pending and c.Requests==c.CompletedServices==0)
owner,config=ready();configure(config);c=BlackwallImuGafBootstrap(m,owner,config,1000,BlackwallImuOdrConfiguration("0300000000000000"))
c.TryRequest(4,Array[Byte]([2]))
for address,mask in [(0xa272,0x20),(0x2a,0x40),(0x73,0x20)]:
 ok,value=c.TryReadRegister(address);c.TryWriteRegister(address,value&~mask if address==0xa272 else value|mask)
advance(50);c.Reset();advance(2000);check('reset-cancels-completion',c.CompletedServices==0 and not c.Pending)
for selection,encoded in enumerate([1,2,8,0x80,0x8000,0x80000000]):
 owner,config=ready();configure(config);c=BlackwallImuGafBootstrap(m,owner,config,1000,BlackwallImuOdrConfiguration(('%02x'%selection)+'00'*7))
 check('odr-map-'+str(selection),c.TryRequest(4,Array[Byte]([2])) and [owner.RamByte(0x188+k) for k in range(4)]==[(encoded>>(8*k))&255 for k in range(4)])
aux=BlackwallImuAuxiliarySetup('000040');aux.ReadInterrupt()
check('strict-int-mask-rejected',not aux.TryWriteInterrupt(2,0x40))
check('functional-fifo-int-mask',aux.TryWriteInterrupt(2,0x40,True) and list(aux.ReadInterrupt())==[2,0x40])
check('reserved-int-mask-rejected',not aux.TryWriteInterrupt(3,0x80,True))
aux=BlackwallImuAuxiliarySetup('a5b6d7');check('runtime-full-mask-without-read',aux.TryWriteInterrupt(2,0x40,True) and list(aux.ReadInterrupt())==[2,0x40])
Console.WriteLine('BLACKWALL_GAF_BOOTSTRAP '+json.dumps(dict(passed=True,checks=checks,count=len(checks),numerical_gaf_validated=False)))
'''
code='fixture='+repr(profile['gaf_parameters_hex'])+'\nfields='+repr([(f['address'],f['length']) for f in fields])+'\nwrites='+repr(writes)+'\n'+helper+'from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallImuOdrConfiguration,BlackwallImuAuxiliarySetup\n'+test
(O/'test.py').write_text(code);(O/'probe.resc').write_text('include @/work/strict.cs\nmach create "bootstrap-unit"\nmachine LoadPlatformDescription @/work/board.repl\ninclude @/work/test.py\nquit\n')
log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={O},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],O,'renode',timeout=90)
rows=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith('BLACKWALL_GAF_BOOTSTRAP ')]
if len(rows)!=1:raise ValueError('Bootstrap unit failed; inspect saved log')
(O/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');print(json.dumps(dict(passed=True,count=rows[0]['count'])))
