"""Collect power state after the existing delayed reconnect strict stop; no model changes."""
import argparse
import json
from pathlib import Path

from probe_runtime_reconnect import build
from run_runtime_connection_m55 import pin_capture,sha
from run_renode_m55_probe import execute
from native_replay import IMAGE

POST='''
try:
    from System.IO import File
    from System import Console
    m=monitor.Machine;g=m['sysbus.guard'];cpu=m['sysbus.cpu']
    def power(v):return dict(mask=int(v.Mask),request=int(v.RequestWord),status=int(v.StatusWord),phase=str(v.Phase),profile=int(v.Profile),off_profile=int(v.OffProfile),generation=int(v.Generation),requests=int(v.Requests),responses=int(v.Responses))
    uarts=[]
    for pair in g.UartPowers:
        a=g.Uarts[pair.Key];v=power(pair.Value);v.update(module=int(pair.Key),quiescent=bool(a.Quiescent),control=int(a.Control),raw_interrupts=int(a.RawInterrupts),interrupt_mask=int(a.InterruptMask),irq=bool(a.IRQ.IsSet),dma=None if a.DmaTx is None else dict(control=int(a.DmaTx.Control),busy=bool(a.DmaTx.Busy)))
        uarts.append(v)
    ioms=[]
    for pair in g.IomPowers:
        v=power(pair.Value);v.update(module=int(pair.Key));ioms.append(v)
    extras={}
    for name in ('Mspi0Power','Mspi1Power','OtpPower','CryptoPower'):
        v=getattr(g,name);extras[name]=None if v is None else power(v)
    masks=uarts+ioms+[v for v in extras.values() if v is not None]
    request=int(g.GpuPower.RequestWord)|int(g.AdcPower.RequestWord)
    for v in masks:request|=v['request']
    proposed=int(cpu.GetRegister(1).RawValue)
    value=dict(paused=bool(m.IsPaused),pc=int(cpu.PC.RawValue),registers=[int(cpu.GetRegister(n).RawValue) for n in range(16)],request_before=request,proposed=proposed,changed_mask=request^proposed,buck_phase=str(g.BuckResponsePhase),shared_uart_gate=bool(g.UartHcpaGate),uarts=uarts,ioms=ioms,extras=extras,gpu_request=int(g.GpuPower.RequestWord),adc_request=int(g.AdcPower.RequestWord),hardware_accessed=False)
    File.WriteAllText('/work-output/reconnect-power.json',json.dumps(value));Console.WriteLine('BLACKWALL_RECONNECT_POWER '+json.dumps(value))
except Exception as error:Console.WriteLine('BLACKWALL_RECONNECT_POWER_ERROR '+str(error))
'''


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    build(a.simulator,a.output,1000)
    (a.output/'run.py').write_text((a.output/'run.py').read_text()+POST)
    inputs=json.loads((a.output/'connection-inputs.json').read_text());inputs['run.py']=sha(a.output/'run.py');(a.output/'connection-inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
    execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={a.output},target=/work,readonly','--mount',f'type=bind,source={a.output}/exports,target=/work-output',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],a.output,'renode',timeout=180)
    pin_capture(a.output);v=json.loads((a.output/'exports/reconnect-power.json').read_text())
    print(json.dumps(v))


if __name__=='__main__':main()
