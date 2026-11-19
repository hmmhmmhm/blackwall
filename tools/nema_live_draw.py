"""Cold command buffer + original five draw calls + original submission caller."""
import hashlib,json,struct
from prepare_draw_command_batch import batch_calls
from prepare_nema_state_captures import validate_region
from inspect_nema_submission import discover_submission
from inspect_glyph_itcm_read import read_contract


def sha(data):return hashlib.sha256(data).hexdigest()


def prepare(simulator,case,raw,submission_sram,submission_work,character=65,omit_letter=False):
    if character not in (65,87):raise ValueError('Only reviewed uppercase A/W fit this diagnostic surface')
    folder=simulator/'nema-state-batch-inputs-01/captures'/case/'full-letter'
    snapshot=json.loads((folder/'snapshot.json').read_text());sram=(folder/'sram.bin').read_bytes();cold=(folder/'work.bin').read_bytes()
    if snapshot['raw_sha256']!=sha(raw) or snapshot['image_hashes']!={'sram.bin':sha(sram),'work.bin':sha(cold)}:
        raise ValueError('Cold draw fixture differs')
    validate_region(simulator,case,raw,snapshot,sram)
    if cold[0x4000:0x5000]!=b'\xa5'*4096 or struct.unpack_from('<I',cold,0x2014)[0]!=0:
        raise ValueError('Live draw must begin without a populated command list')
    contract=discover_submission(raw);offset=contract['ring_table']-0x20000000
    merged=bytearray(sram);merged[offset:offset+20]=submission_sram[offset:offset+20]
    if bytes(merged)!=submission_sram:raise ValueError('Submission SRAM differs outside declared synthetic ring table')
    work=bytearray(cold)
    for start,end in [(0xafe0,0xb120),(0xb400,0xb440)]:work[start:end]=submission_work[start:end]
    calls=batch_calls(raw,snapshot,64);calls[3]['stack']=list(snapshot['batch']['calls'][3]['stack'])
    if calls!=snapshot['batch']['calls']:raise ValueError('Original draw entries or arguments differ')
    calls[3]['stack'][0]=character
    if omit_letter:calls=[c for c in calls if c['name']!='letter']
    calls.append(dict(name='submit',entry=contract['submit'],args=[0x21002000,0,0,0],stack=[]))
    native=simulator/'nema-state-batch-m55-01'/(case+'-full-letter')
    report=json.loads((native/'report.json').read_text());itcm=(native/'itcm.bin').read_bytes()
    if not report['passed'] or (native/'main.bin').read_bytes()!=raw or sha(itcm)!=report['itcm_profile']['image_sha256']:
        raise ValueError('Canonical ITCM input changed')
    font=snapshot['registers']['R3'];bitmap=struct.unpack_from('<I',sram,font-0x20000000+4)[0]&~1
    proof=read_contract(raw,bitmap)
    if proof['read_pc']!=report['itcm_profile']['raw_read_pc']:raise ValueError('Unexpected original raw bitmap read')
    evidence=dict(character=character,omit_letter=omit_letter,source=str(folder.relative_to(simulator)),
                  source_hashes={name:sha((folder/name).read_bytes()) for name in ['snapshot.json','work.bin','sram.bin']},
                  itcm_source=str(native.relative_to(simulator)),itcm_sha256=sha(itcm),read_contract=proof,
                  initial_used_words=0,command_buffer_poison=True,phases=calls,raw_sha256=sha(raw))
    return dict(work=bytes(work),snapshot=snapshot,calls=calls,itcm=itcm,itcm_read_pc=proof['read_pc'],evidence=evidence)
