"""Original record memcpy/empty-head/cache-poll fragments on explicit inputs."""
import argparse,json,hashlib,struct
from pathlib import Path
from unicorn import UC_HOOK_CODE
import unicorn.arm_const as arm
from inspect_nema_blocking_wait import cpu,WORK,STOP
from inspect_ambiq_target import decode
from inspect_em9305_hci_framing import literal

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def run(u,entry,ends):
    trace=[]
    def hook(c,pc,size,user):
        trace.append(pc)
        if pc in ends:c.emu_stop()
    u.hook_add(UC_HOOK_CODE,hook);u.emu_start(entry|1,STOP,count=200000)
    pc=u.reg_read(arm.UC_ARM_REG_PC)
    if pc not in ends and pc!=STOP:raise ValueError('Original fragment escaped boundary')
    return dict(stop=pc,instructions=len(trace),trace_sha256=hashlib.sha256(struct.pack('<'+'I'*len(trace),*trace)).hexdigest())

def inspect(s,case):
    audit=json.loads((s/'keydb-slot-saved-audit-01'/case/'report.json').read_text());f=s/'keydb-slot-zero-main-01'/case
    if not audit['passed']:raise ValueError('Unverified source')
    for n,h in audit['capture_hashes'].items():
        if sha(f/n)!=h:raise ValueError('Changed source '+n)
    r=json.loads((f/'report.json').read_text());raw=(f/'main.bin').read_bytes();h=r['diagnostics']['keydb_last_pc']+0x87c;out=[]
    for data in [bytes(200),b'\xff'*200,bytes(range(200))]:
        u=cpu(raw,bytes(0x80000),WORK+0xf000);u.mem_map(0x7ff000,4096);u.mem_write(0x7ff000,data+b'\x5a'*56);u.mem_write(WORK+0x2f0,b'\xa5'*232)
        for n,v in [(0,WORK+0x300),(1,0x7ff000),(2,200)]:u.reg_write(getattr(arm,'UC_ARM_REG_R'+str(n)),v)
        t=run(u,0x439be4,[])
        if bytes(u.mem_read(WORK+0x300,200))!=data or bytes(u.mem_read(WORK+0x2f0,16))!=b'\xa5'*16 or bytes(u.mem_read(WORK+0x3c8,16))!=b'\xa5'*16 or u.reg_read(arm.UC_ARM_REG_SP)!=WORK+0xf000:raise ValueError('Original 200-byte memcpy differs')
        out.append(dict(kind='record-copy',input_sha256=hashlib.sha256(data).hexdigest(),bytes=200,neighbors_preserved=True,execution=t))
    for head in [0,0xffffffff,1,0x01020304]:
        u=cpu(raw,bytes(0x80000),WORK+0xf000);u.mem_write(WORK+0xf034,struct.pack('<I',head));empty=h-0x232;nonempty=h-0x450;t=run(u,h-0x464,[empty,nonempty])
        if t['stop']!=(empty if head in [0,0xffffffff] else nonempty):raise ValueError('Different empty-record exit')
        out.append(dict(kind='empty-head',head=head,empty=head in [0,0xffffffff],execution=t))
    prior=json.loads((s/'mram-keydb-contract-01/report.json').read_text());callee=next(x for x in prior['cases'] if x['case']==case)['program_argument_samples'][0]['callee'];calls=[i for i in decode(raw,callee-0x54,0x54) if i.mnemonic=='bl'];cache=int(calls[1].op_str[1:],16)
    for ready in [False,True]:
        entry=cache+0x22;timeout=cache+0x4a;success=cache+0x4e;u=cpu(raw,bytes(0x80000),WORK+0xf000);u.mem_map(0x40021000,4096);u.mem_write(0x40021014,struct.pack('<II',0x1f,128 if ready else 0));u.reg_write(arm.UC_ARM_REG_R4,0x40021018)
        control=literal(raw,decode(raw,entry,4)[0])
        if control!=0x40021014:raise ValueError('Different cache control literal')
        t=run(u,entry,[timeout,success]);counter=u.reg_read(arm.UC_ARM_REG_R1)
        if t['stop']!=(success if ready else timeout) or counter!=(0 if ready else 10000) or struct.unpack('<I',u.mem_read(0x40021014,4))[0]!=0x3f:raise ValueError('Original cache poll differs')
        after=decode(raw,calls[1].address+4,0xe)
        if any(i.mnemonic.startswith('b') and i.mnemonic!='bl' for i in after):raise ValueError('Unexamined cache result branch')
        out.append(dict(kind='cache-poll',ready=ready,poll_counter=counter,prepared_return=0 if ready else 4,control=0x3f,caller_has_no_local_cache_error_branch=True,execution=t))
    return dict(case=case,raw_sha256=sha(f/'main.bin'),source_audit_sha256=sha(s/'keydb-slot-saved-audit-01'/case/'report.json'),record_loader_call=h-0x468,cache_entry=cache,samples=out)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve prior evidence')
    rows=[inspect(a.simulator,c) for c in ['stock24','stock23','cfw']];count=sum(len(x['samples']) for x in rows);a.output.mkdir(parents=True);(a.output/'inspector.py').write_bytes(Path(__file__).read_bytes());(a.output/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,original_fragment_scenarios=count,native_main_rerun=False,hardware_accessed=False,physical_cache_ready_verified=False,mram_program_executed=False),indent=2)+'\n');print('original record/cache scenarios: '+str(count)+' passed')
if __name__=='__main__':main()
