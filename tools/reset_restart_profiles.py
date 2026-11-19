"""Validate original version-specific sleep ABI against immutable source evidence."""
import hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
STAGING_PIN='e963eba901edde5f8dcedb6a78495c26d3f44d9436ed95971e7bacf34abaa547'
PREPARATION_PIN='11b15e887cb163f5d64d20b99af1848047e74d1bc6acc7fddecbf0eef402851b'
ATT_PIN='a139c04c4c277f183d9ef9a8f7ab612bd3cc59cc5ed2beb6cfc9cbe7cca6fa3c'
RENODE_IMAGE='sha256:e840c2b9a83dbf9be060047839aaaf6d434e7d4c52635191319afc14f4217649'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def pin(s,manifest,path):
    expected=manifest['files'][str(path.relative_to(s))]
    digest=expected if isinstance(expected,str) else expected['sha256']
    if sha(path)!=digest or isinstance(expected,dict) and path.stat().st_size!=expected['bytes']:raise ValueError('Changed pinned source '+str(path))

def profile(s,case,raw):
    if case not in ('stock24','stock23','cfw'):raise ValueError('Unknown original reset profile')
    parent=s/'cpu-retention-staging-research-01/manifest.json'
    if sha(parent)!=STAGING_PIN:raise ValueError('Changed retention source acceptance')
    m=read(parent);source=s/'cpu-retention-staging-research-01/original-contract.json';pin(s,m,source)
    c=next(x for x in read(source)['cases'] if x['case']==case)
    if hashlib.sha256(raw).hexdigest()!=c['main_sha256']:raise ValueError('Not the pinned original main')
    for x in c['code']+c['setter_code']:
        data=bytes.fromhex(x['bytes']);offset=x['pc']-0x438000
        if raw[offset:offset+len(data)]!=data:raise ValueError('Changed original retention code')
    provenance=s/'cpu-retention-staging-research-01/source-contract.json';pin(s,m,provenance)
    prior_manifest=s/'cpu-sleep-verification-01/manifest.json'
    if sha(prior_manifest)!=read(provenance)['manifest_sha256']:raise ValueError('Changed original sleep verification')
    original=s/'cpu-sleep-source-02/report.json';pin(s,read(prior_manifest),original)
    old=next(x for x in read(original)['cases'] if x['case']==case)
    decoder=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS);decoder.detail=True
    def instruction(pc,length=4):
        values=list(decoder.disasm(raw[pc-0x438000:pc-0x438000+length],pc))
        if not values:raise ValueError('Missing original instruction')
        return values[0]
    normal=instruction(old['parent_return']-4);deep=instruction(old['parent_return']+4);arg=instruction(old['parent_return']+2,2)
    if normal.mnemonic!=deep.mnemonic or deep.mnemonic!='bl' or normal.operands[0].imm!=old['normal_sleep_entry'] or deep.operands[0].imm!=old['normal_sleep_entry'] or (arg.mnemonic,arg.op_str)!=('movs','r0, #1'):raise ValueError('Unverified original deep sleep caller')
    returned=instruction(deep.address+deep.size,2)
    if (returned.mnemonic,returned.op_str)!=('movs','r0, #0'):raise ValueError('Unverified sleep return boundary')
    wfi=instruction(old['wfi_boundary'],2);barrier=instruction(old['wfi_boundary']+2)
    if wfi.mnemonic!='wfi' or barrier.mnemonic!='isb':raise ValueError('Unverified WFI/return')
    flush=instruction(old['wfi_boundary']-6,2);load=instruction(old['wfi_boundary']-10)
    if (flush.mnemonic,flush.op_str)!=('ldr','r0, [r0]') or not load.op_str.startswith('r0, [pc,'):raise ValueError('Unverified flush instruction')
    literal=((load.address+4)&~3)+load.operands[1].mem.disp
    if struct.unpack_from('<I',raw,literal-0x438000)[0]!=0x47ff0000:raise ValueError('Different flush peripheral')
    timer_isr=struct.unpack_from('<I',raw,0xc0)[0]&~1
    if timer_isr<0x438000 or timer_isr>=0x438000+len(raw):raise ValueError('Unverified TIMER IRQ32 vector')
    return dict(case=case,main_sha256=c['main_sha256'],retention_store=c['store'],retention_return=c['returned'],sleep_entry=old['normal_sleep_entry'],sleep_return=returned.address,wfi=old['wfi_boundary'],wfi_return=barrier.address,flush_read=flush.address,timer32_isr=timer_isr,source_pin=STAGING_PIN,normal_caller=old['parent_return'],deep_call=dict(pc=deep.address,bytes=deep.bytes.hex()),fields=c['fields'])
