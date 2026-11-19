"""Exercise XIP diagnostic CPU context gates using a synthetic M55 load, not firmware."""
import argparse,json,struct
from pathlib import Path
from native_replay import IMAGE
from run_renode_m55_probe import execute
from verify_mspi1_pio_reset import models


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s,o=a.simulator,a.output;o.mkdir(mode=0o700);results=[]
    for variant in ['valid','wrong-pc','wrong-r4']:
        d=o/variant;d.mkdir(mode=0o700);start=0x476056+(2 if variant=='wrong-pc' else 0);literal=(start+10+3)&~3
        first=(literal-((start+4)&~3))//4;second=(literal+4-((start+6)&~3))//4
        code=struct.pack('<5H',0x4c00|first,0x4800|second,0x6801,0x225a,0xe7fe)
        code+=b'\0'*(literal-start-len(code))+struct.pack('<2I',0x80100004 if variant=='wrong-r4' else 0x80100000,0x80100000)
        (d/'guest.bin').write_bytes(code);(d/'vectors.bin').write_bytes(struct.pack('<2I',0x20001000,start|1))
        board=(s/'timer0-shared-main-02/stock24-low/board.repl').read_text();needle='xip_guard: Miscellaneous.BlackwallMspi1XipGuard @ sysbus 0x80000000\n'
        if board.count(needle)!=1:raise ValueError('Unexpected XIP owner')
        board=board.replace(needle,needle+'    fontHeaderProfile: "missing-font-magic-only"\n    primaryHeaderReadPc: 0x47605a\n    secondaryHeaderReadPc: 0x476134\n')
        (d/'board.repl').write_text(board);(d/'strict.cs').write_bytes(models(s))
        (d/'setup.py').write_text("from Antmicro.Renode.Core import EmulationManager\nfrom Antmicro.Renode.Time import TimeInterval\nm=monitor.Machine;g=m['sysbus.guard'];x=m['sysbus.xip_guard'];c=m['sysbus.cpu']\nif not g.Mspi1Power.TryWrite(0x8000,True):raise Exception('ready mock')\ng.Mspi1Power.ReadStatus()\ng.WriteDoubleWord(0x3110,0xa4234)\nif not x.TryEnable(0x19):raise Exception('XIP enable')\n")
        (d/'advance.py').write_text('EmulationManager.Instance.CurrentEmulation.RunFor(TimeInterval.FromMicroseconds(100))\n')
        expected=variant=='valid'
        (d/'result.py').write_text("import json\nfrom System import Console\nEmulationManager.Instance.CurrentEmulation.PauseAll()\nvalid="+str(expected)+"\nif valid:\n    if x.FontHeaderReads!=1 or x.AccessCount!=0 or int(c.GetRegister(1).RawValue)!=0xffffffff or int(c.GetRegister(2).RawValue)!=0x5a:raise Exception('valid CPU context rejected')\nelse:\n    if x.FontHeaderReads!=0 or x.AccessCount!=1 or x.LastAddress!=0x80100000 or int(c.GetRegister(2).RawValue)!=0 or int(c.PC.RawValue)!="+str(start+4)+":raise Exception('wrong CPU context accepted')\nConsole.WriteLine('BLACKWALL_MISSING_FONT_CPU '+json.dumps(dict(passed=True,variant='"+variant+"',reads=int(x.FontHeaderReads),guard_accesses=int(x.AccessCount),pc=int(c.PC.RawValue),original_firmware=False)))\n")
        (d/'probe.resc').write_text('include @/work/strict.cs\nmach create "font-cpu-context"\nmachine LoadPlatformDescription @/work/board.repl\nsysbus LoadBinary @/work/vectors.bin 0x10000\nsysbus LoadBinary @/work/guest.bin '+hex(start)+'\ncpu VectorTableOffset 0x10000\ninclude @/work/setup.py\ninclude @/work/advance.py\ninclude @/work/result.py\nquit\n')
        log=execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={d},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],d,'renode')
        rows=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith('BLACKWALL_MISSING_FONT_CPU ')]
        if len(rows)!=1:raise ValueError('Missing CPU context result '+variant)
        (d/'report.json').write_text(json.dumps(rows[0],indent=2)+'\n');results.append(rows[0])
    (o/'report.json').write_text(json.dumps(dict(passed=True,cases=results,count=3),indent=2)+'\n');print(json.dumps(dict(passed=True,count=3)))


if __name__=='__main__':main()
