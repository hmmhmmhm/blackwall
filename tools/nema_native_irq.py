"""Captured semaphore inputs and bounded native IRQ expectations for draw replay."""
import hashlib
import json
import struct

from inspect_nema_irq_contract import discover_irq
from inspect_ambiq_target import decode
from native_replay import validate_assets


def prepare(simulator, case, raw, base_sram):
    source = simulator / 'nema-irq-semaphore-main-01' / case
    manifest = json.loads((source/'derived-inputs.json').read_text())
    validate_assets(source, manifest['derived'])
    report = json.loads((source/'report.json').read_text())
    if not report['passed'] or not report['semantic_validation']['passed'] or (source/'main.bin').read_bytes() != raw:
        raise ValueError('Unverified original semaphore capture')
    lines = (source/'renode.log').read_text().splitlines()
    plan = json.loads((source/'plan.json').read_text())
    rows = [json.loads(line.split(' ',1)[1]) for line in lines if line.startswith('BLACKWALL_CANDIDATE_'+plan['id']+' ')]
    if rows != [report['diagnostics']]:
        raise ValueError('Semaphore capture disagrees with native log')
    contract = discover_irq(raw)
    state, = report['diagnostics']['records']
    q = state['handle']
    if not state['valid_queue'] or not 0x20000000 <= q <= 0x20080000-96 or state['callback'] != 0 or state['queue_words'][14:17] != [0,1,0] or state['queue_words'][9] != 0:
        raise ValueError('Only captured empty binary semaphore without waiters is supported')
    sram = bytearray(base_sram)
    regions = [(contract['slots']['semaphore'],struct.pack('<2I',q,state['callback'])),
               (contract['slots']['last_id'],struct.pack('<I',state['last_id'])),
               (q,struct.pack('<24I',*state['queue_words']))]
    for address, data in regions:
        sram[address-0x20000000:address-0x20000000+len(data)] = data
    def instruction(address, length, mnemonic, operands):
        matches = [i for i in decode(raw,address,length) if i.mnemonic==mnemonic and i.op_str==operands]
        if len(matches) != 1:
            raise ValueError('Unexpected original IRQ instruction contract')
        return matches[0].address
    details = dict(handler=contract['vector']&~1,pendsv=contract['pendsv'],
                   read_pc=instruction(contract['read'],10,'ldr','r0, [r0]'),
                   write_pc=instruction(contract['write'],10,'str','r1, [r0]'),
                   last_store_pc=instruction(contract['core'],0x5e,'str','r4, [r5]'),
                   last_address=contract['slots']['last_id'],
                   count_store_pc=instruction(contract['give'],0x100,'str','r0, [r4, #0x38]'),
                   count_address=q+0x38,queue=q,
                   restored_regions=[dict(address=a,bytes=len(d),sha256=hashlib.sha256(d).hexdigest()) for a,d in regions],
                   source=str(source),source_hashes={n:hashlib.sha256((source/n).read_bytes()).hexdigest() for n in ['report.json','renode.log','plan.json','derived-inputs.json']},
                   synthetic_msp_thread=True,inactive_psp=0x2100d000,full_rtos_context=False)
    return bytes(sram), details


def setup_text(profile, enabled=True):
    keys = ['handler','pendsv','read_pc','write_pc','last_store_pc','last_address','count_store_pc','count_address']
    return "f.ConfigureGpuIrq("+','.join(str(profile[k]) for k in keys)+")\nf.SeedRegister(20,0x438000)\nf.SeedRegister(22,"+str(profile['inactive_psp'])+")\nb.WriteByte(0xe000e41c,0x40)\n"+("b.WriteDoubleWord(0xe000e100,0x10000000)\n" if enabled else '')


def observation_text(profile):
    return ("r['gpu_completion']=dict(irq_entries=int(f.IrqEntries),pendsv_entries=int(f.PendSvEntries),pendsv_entry_r0=int(f.PendSvEntryR0),entry_r3=int(f.IrqEntryR3),entry_xpsr=int(f.IrqEntryXpsr),clid_reads=int(gpu.ClidReads),acks=int(gpu.IrqAcks),line=bool(gpu.IRQ.IsSet),last_id=int(b.ReadDoubleWord("+str(profile['last_address'])+")),messages=int(b.ReadDoubleWord("+str(profile['count_address'])+")))\n")


def checks(actual, before_sram, after_sram, profile, enabled=True):
    c = actual['gpu_completion']
    if not enabled:
        return dict(disabled_irq_not_delivered=c['irq_entries']==c['pendsv_entries']==c['clid_reads']==c['acks']==0 and c['line'],
                    no_original_publication=c['last_id']==0xffffffff and c['messages']==0 and before_sram==after_sram,
                    uninterrupted_return=actual['boundary']=='return' and actual['violations']==0)
    expected = bytearray(before_sram)
    struct.pack_into('<I',expected,profile['last_address']-0x20000000,8)
    struct.pack_into('<I',expected,profile['count_address']-0x20000000,1)
    nonzero = c['entry_r3'] != 0
    return dict(actual_irq28=c['irq_entries']==1 and c['entry_xpsr']&0x1ff==44,
                original_clid_stabilization=c['clid_reads']==2 and c['acks']==1 and not c['line'],
                original_id_and_give=c['last_id']==8 and c['messages']==1,
                only_declared_sram_publication=bytes(expected)==after_sram,
                original_pendsv_decision=c['pendsv_entries']==int(nonzero) and actual['boundary']==('rtos-context-required' if nonzero else 'return') and actual['violations']==0,
                pendsv_first_instruction_unexecuted=not nonzero or c['pendsv_entry_r0']==actual['registers'][0]!=profile['inactive_psp'])
