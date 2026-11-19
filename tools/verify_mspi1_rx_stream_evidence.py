"""Audit FIFO-paced reads, pinned HAL order and unchanged original-main execution."""
import argparse
import hashlib
import json
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_MCLASS
from native_replay import parse_log, validate_assets, boundary_state
from pinned_main import load_pinned_main
from verify_mspi1_pio_reset import models


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();s=a.simulator;a.output.mkdir(mode=0o700);checks=[];cases=[]
    def check(n,v):
        if not v:raise ValueError(n)
        checks.append(n)
    def marker(log,tag):
        rows=[json.loads(l.split(' ',1)[1]) for l in log.splitlines() if l.startswith(tag+' ')]
        check(tag+'-unique',len(rows)==1);return rows[0]
    src=s/'mspi1-source-research-01'
    manifest=json.loads((src/'sources.json').read_text())
    check('HAL-commit',manifest['commit']=='61b293a49db34030c545f99101f7ebf6a3050314')
    for name,sha in [('am_hal_mspi.c','5a91ab0c67bda4bd61c7d436b94b5a7c81693b948a331d282ae10e88cc5bf85f'),('am_hal_mspi.h','2a682bb7c1618982d6a802f3220a38696cd594c89d90e64b1a698d226b0a557b')]:
        check(name+'-pin',hashlib.sha256((src/name).read_bytes()).hexdigest()==sha)
    hal=(src/'am_hal_mspi.c').read_text();start=hal.index('MSPIn(ui32Module)->CTRL = ui32Control;',hal.index('am_hal_mspi_blocking_transfer'))
    drain=hal.index('ui32Status = mspi_fifo_read',start);wait=hal.index('// Wait for the command to complete.',drain)
    check('HAL-start-drain-before-complete-wait',start<drain<wait)
    check('HAL-word-and-leftover-read', 'ui32NumWords = ui32NumBytes / 4;' in hal and 'sTempBuffer.words[0] = MSPIn(ui32Module)->RXFIFO;' in hal)
    check('HAL-FIFO16', '#define AM_HAL_MSPI_MAX_FIFO_SIZE               16' in (src/'am_hal_mspi.h').read_text())
    unit_names=[('mspi1-rx-stream-unit-03','BLACKWALL_RX_STREAM'),('mspi1-rx-stream-padding-01','BLACKWALL_RX_STREAM'),
                ('mspi1-rx-stream-boundary65-01','BLACKWALL_RX_STREAM'),('mspi1-rx-stream-boundary256-01','BLACKWALL_RX_STREAM'),('mspi1-rx-stream-stuck-01','BLACKWALL_RX_STREAM'),
                ('mspi1-rx-stream-array-regression-01','BLACKWALL_ARRAY_UNIT'),('mspi1-rx-stream-program-regression-01','BLACKWALL_PROGRAM_UNIT'),('mspi1-rx-stream-status-regression-01','BLACKWALL_CONTINUOUS_STATUS_UNIT')]
    total=0
    for folder,tag in unit_names:
        d=s/folder;r=json.loads((d/'report.json').read_text())
        check(folder+'-log-report',marker((d/'renode.log').read_text(),tag)==r)
        check(folder+'-count',r['passed'] and r['count']==len(r['checks']));total+=r['count']
        check(folder+'-current-model',(d/'strict.cs').read_bytes()==models(s))
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS)
    for key,bundle,delta in [('stock24','stock-2.4.0.24.bin',0),('stock23','stock-2.3.0.24.bin',0xd3d4),('cfw','faceclaw-38-research-only.bin',0xd3d4),('stock24-default','stock-2.4.0.24.bin',0)]:
        active=key!='stock24-default';prior_key='stock24' if key.startswith('stock24') else key
        d=s/'mspi1-rx-stream-main-01'/key;old=s/'nvdb-blank-main-02'/prior_key
        log=(d/'renode.log').read_text();r=json.loads((d/'report.json').read_text());v=parse_log(log)
        validate_assets(d,json.loads((d/'derived-inputs.json').read_text())['derived'])
        check(key+'-report',v==r['observed']);check(key+'-current-model',(d/'strict.cs').read_bytes()==models(s))
        _,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes());check(key+'-original-main',(d/'main.bin').read_bytes()==raw)
        store,read,wait=0x4e8a46-delta,0x4e8a5a-delta,0x4e8a98-delta
        code={i.address:(i.mnemonic,i.op_str) for i in md.disasm(raw[store-0x438000:wait+4-0x438000],store)}
        check(key+'-original-CTRL-RX-helper-wait',code.get(store)==('str.w','lr, [r2]') and code.get(read)==('bl','#'+hex(0x4e6468-delta)) and code.get(wait)==('bl','#0x495f0e' if not delta else '#0x48a026'))
        obs=marker(log,'BLACKWALL_OBSERVATION');previous=json.loads((old/'report.json').read_text())
        check(key+'-all-selected-events-preserved',obs==previous['selected_observation'] and not obs['dropped_events'])
        arr=marker(log,'BLACKWALL_NOR_ARRAY');oldlog=(old/'renode.log').read_text();oldarr=marker(oldlog,'BLACKWALL_NOR_ARRAY')
        check(key+'-bounded-backing',arr['start']==0x1fc0000 and arr['length']==0x40000 and not arr['physical_contents_known'])
        check(key+'-program-history-preserved',marker(log,'BLACKWALL_NOR_PROGRAM')==marker(oldlog,'BLACKWALL_NOR_PROGRAM'))
        check(key+'-erase-history-preserved',marker(log,'BLACKWALL_NOR_ERASE')==marker(oldlog,'BLACKWALL_NOR_ERASE'))
        off=marker(log,'BLACKWALL_MSPI_CONTROLLER_OFF')
        if active:
            check(key+'-172-byte-transfer-consumed',arr['reads']==oldarr['reads']+1 and arr['bytes']==oldarr['bytes']+172 and arr['last_address']==0x1ff80a1 and arr['rx_entries']==0)
            guards=[g for g in v['guards'] if g['accesses']]
            check(key+'-next-power-guard',len(guards)==1 and guards[0]['address']==0x40021004 and guards[0]['value']==0x08000400)
            check(key+'-controller-off-after-read',off['count']==off['power_cycles']==874 and off['xip_restores']==873 and off['phase']=='powered-off')
            check(key+'-opt-in-limit','    maxArrayReadBytes: 256\n' in (d/'board.repl').read_text())
        else:
            check('default-old-boundary',boundary_state(v)==boundary_state(previous['observed']) and arr==oldarr)
            check('default-board-identical',(d/'board.repl').read_bytes()==(old/'board.repl').read_bytes())
        check(key+'-no-boot-display-hardware-claim',not r['boot_verified'] and not r['display_verified'] and not r['hardware_validated'])
        cases.append(dict(case=key,pc=hex(v['pc']),array=arr,off=off))
    result=dict(passed=True,count=len(checks),checks=checks,unit_checks=total,cases=cases,scope='Bounded logical RX streaming and consumed 172-byte original read; whole factory init, boot, display and physical timing unverified')
    (a.output/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks),unit_checks=total)))


if __name__=='__main__':main()
