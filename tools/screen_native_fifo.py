from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
from importlib.machinery import SourceFileLoader
helper=SourceFileLoader('screen_gpu_helper',str(Path(__file__).with_name('screen_native_gpu.py'))).load_module()

def compose(model,root):
 current=(root/'tools/renode-imu-identity.cs').read_text();types=helper.types(model);source_types=helper.types(current)
 for name in ['BlackwallImuPowerConfiguration','BlackwallImuOdrConfiguration']:
  before=helper.types(model)[name][2];after=source_types[name][2];model=model.replace(before,after,1)
 identity=helper.types(model)['BlackwallImuIdentity'][2];patched=identity
 def patch(before,after):
  nonlocal patched
  if patched.count(before)!=1:raise ValueError('Changed FIFO identity anchor: '+before[:55])
  patched=patched.replace(before,after,1)
 patch('public void Reset()\n        {','public void Reset()\n        {\n            IndirectExtension?.Reset();')
 a=current.index('            if(IndirectExtension!=null && data.Length>=3');b=current.index('            if(GafParameters!=null && GafParameters.ConfigurationEnabled',a)
 marker='            if(GafParameters!=null && GafParameters.ConfigurationEnabled';patch(marker,current[a:b]+marker)
 marker='                if(OnDemand!=null && OnDemand.Active && OnDemand.OwnsRegister(IregAddress))'
 patch(marker,'                if(IndirectExtension!=null && IndirectExtension.Contains(IregAddress))value=new byte[]{IndirectExtension.Read(IregAddress)};\n                else '+marker.lstrip())
 a=current.index('        public void AttachIndirectExtension(');b=current.index('        public bool InitialIregReady',a);marker='        public void FinishTransmission() { Finishes++; }';patch(marker,marker+'\n'+current[a:b])
 interface=source_types['IBlackwallImuIndirectExtension'][2];model=model.replace(identity,interface+'\n'+patched,1)
 for name in ['renode-imu-raw-fifo.cs','renode-imu-fifo-transport.cs','renode-imu-fifo-threshold.cs','renode-imu-fifo-configuration.cs']:model+='\n'+(root/'tools'/name).read_text()
 return model

def board_transform(board):
 a='imu_identity: Miscellaneous.BlackwallImuIdentity @ iom4 0x69';b='imu_identity: Miscellaneous.BlackwallImuIdentity @ none'
 if board.count(a)!=1:raise ValueError('Changed IMU address registration')
 board=board.replace(a,b,1)
 return board+'''\nimu_fifo_raw: Miscellaneous.BlackwallImuRawFifo @ none
    enabled: true
    frameBytes: 32
    capacityPackets: 64
imu_fifo: Miscellaneous.BlackwallImuFifoTransport @ iom4 0x69
    owner: iom4
    startupPeer: imu_identity
    rawFifo: imu_fifo_raw
    threshold: imu_fifo_threshold
    configuration: imu_fifo_configuration
imu_fifo_threshold: Miscellaneous.BlackwallImuFifoThreshold @ none
    rawFifo: imu_fifo_raw
imu_fifo_configuration: Miscellaneous.BlackwallImuFifoConfiguration @ none
    startupPeer: imu_identity
    rawFifo: imu_fifo_raw
    threshold: imu_fifo_threshold
'''
