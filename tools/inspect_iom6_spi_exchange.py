"""Read saved native first SPI exchange and actual original RX stack buffer."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
from inspect_ambiq_target import decode

BASE=0x438000


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve prior evidence')
    rows=[]
    for case in ['stock24','stock23','cfw']:
        source=a.simulator/('iom6-spi-word-main-explore-01' if case=='stock24' else 'iom6-spi-word-main-01')/case
        r=json.loads((source/'report.json').read_text());raw=(source/'main.bin').read_bytes();plan=json.loads((source/'plan.json').read_text());baseline=a.simulator/'iom6-full-duplex-main-01'/case
        if not r['passed'] or not r['execution_passed'] or not r['semantic_validation']['passed']:raise ValueError('Unverified native exchange')
        if sha(source/'main.bin')!=sha(baseline/'main.bin') or plan['runtime_edits']:raise ValueError('Changed original main or runtime')
        d=r['diagnostics'];expected=dict(commands=1,completed=1,bytes_exchanged=2,rx_words=0,last_rx_word=192,peer_tx='8100',peer_finished=1)
        if any(d[k]!=v for k,v in expected.items()):raise ValueError('Incorrect native exchange')
        if 'responseHex: "c000"' not in plan['board_append'] or 'expectedHex: "8100"' not in plan['board_append']:raise ValueError('Unknown synthetic peer')
        guards=[g for g in r['observed']['guards'] if g['accesses']]
        if len(guards)!=1 or guards[0]['operation']!='spi-peer-script-unavailable' or guards[0]['value']!=0x201:raise ValueError('Second request did not stop before exchange')
        regs=r['observed']['register_context'];stack=r['observed']['stack_context'];data=struct.pack('<'+'I'*len(stack['words']),*stack['words']);sp=stack['base']
        def get(address,n):
            start=address-sp
            if start<0 or start+n>len(data):raise ValueError('Outside captured original stack')
            return data[start:start+n]
        rx=get(regs['r5'],4);tx=get(regs['r4'],4)
        if rx!=b'\xc0\0\0\0' or tx[:2]!=b'\x81\0':raise ValueError('Original buffers differ from completed exchange')
        returned_to=stack['words'][19]&~1;call=decode(raw,returned_to-4,4)
        if len(call)!=1 or call[0].mnemonic!='bl':raise ValueError('Missing original saved HAL return caller')
        hal=call[0].operands[0].imm;head=decode(raw,hal,6)
        if [(i.mnemonic,i.op_str) for i in head]!=[('push.w','{r3, r4, r5, r6, r7, r8, sb, sl, fp, lr}'),('sub','sp, #0x28')]:raise ValueError('Saved return frame layout differs')
        if not hal<regs['r15']<hal+0x400:raise ValueError('Not same HAL second invocation')
        caller=decode(raw,returned_to,0x28);ops=[(i.mnemonic,i.op_str) for i in caller]
        if ('ldrb.w','r0, [sp]') not in ops or ('cmp','r0, #0xc0') not in ops or ('ldrb.w','r0, [sp, #1]') not in ops:raise ValueError('Missing original HCI header checks')
        rows.append(dict(case=case,capture=str(source),source_report_sha256=sha(source/'report.json'),raw_sha256=sha(source/'main.bin'),
                         diagnostics=d,rx_pointer=regs['r5'],rx_word=rx.hex(),tx_pointer=regs['r4'],tx_storage_word=tx.hex(),
                         original_hal=hal,original_hal_saved_return=returned_to,next_command_blocked_before_peer=True,
                         header_check_source=[dict(pc=i.address,op=i.mnemonic+' '+i.op_str) for i in caller]))
    a.output.mkdir(parents=True);(a.output/'inspector.py').write_bytes(Path(__file__).read_bytes());result=dict(passed=True,cases=rows,guest_executed=False,
        original_native_reset_main_captures=True,explicit_peer_scenario='one 8100/c000 exchange; zero pending HCI bytes',
        real_em9305_behavior_verified=False,ble_boot_verified=False,display_verified=False,hardware_accessed=False,
        source_header_checks_not_new_execution_trace=True)
    (a.output/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,cases=len(rows),actual_original_rx_buffer='c0000000',spi_exchanges_per_case=1)))


if __name__=='__main__':main()
