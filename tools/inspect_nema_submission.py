"""Execute original command-list submission against an explicit synthetic ring.

No GPU consumer, completion ID injection or semaphore return stubs. The GPU
doorbell is a passive mapped word, and GPU reads are rejected.
"""
import argparse, hashlib, json, struct
from pathlib import Path
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_PROT_READ, UC_PROT_WRITE, UC_PROT_EXEC, UC_HOOK_CODE, UC_HOOK_MEM_READ
import unicorn.arm_const as arm
from inspect_ambiq_target import inspect, decode, BASE
from prepare_nema_state_captures import validate_region
from pinned_main import load_pinned_main
from inspect_ambiq_commands import discover

WORK, SRAM, STOP = 0x21000000, 0x20000000, 0x10000000
RING, BO, PHYS, CAPACITY = WORK + 0xb000, WORK + 0xb400, 0x22000000, 64


def sha(data): return hashlib.sha256(data).hexdigest()


def literal(raw, instruction):
    address = ((instruction.address + 4) & ~3) + instruction.operands[1].mem.disp
    return struct.unpack_from('<I', raw, address - BASE)[0]


def discover_submission(raw):
    signature = bytes.fromhex('f0b581b0024619b94ff0ff3001b0f0bd')
    if raw.count(signature) != 1: raise ValueError('Ambiguous original ring submit')
    ring_submit = BASE + raw.index(signature)
    body = decode(raw, ring_submit, 0xda)
    ring_table = literal(raw, next(i for i in body if i.mnemonic.startswith('ldr') and 'pc' in i.op_str))
    calls = [i.operands[0].imm for i in body if i.mnemonic == 'bl']
    if len(calls) != 2: raise ValueError('Unexpected ring submit calls')
    reg_write = calls[-1]
    store = decode(raw, reg_write, 10)
    if [(i.mnemonic, i.op_str) for i in store[1:]] != [('ldr', 'r2, [r2]'), ('adds', 'r0, r0, r2'), ('str', 'r1, [r0]'), ('bx', 'lr')]:
        raise ValueError('Unexpected GPU writer')
    slot = literal(raw, store[0])
    if struct.unpack_from('<I', raw, slot - BASE)[0] != 0x40090000:
        raise ValueError('Unexpected GPU base')
    _, target = inspect(raw)
    postdraw = decode(raw, int(target['post_draw_call'], 0), 0x30)
    callees = [i.operands[0].imm for i in postdraw if i.mnemonic == 'bl']
    submit, wait = callees[1:3]
    submit_body = decode(raw, submit, 0xe)
    if submit_body[-1].mnemonic != 'b': raise ValueError('Expected original submit wrapper')
    wait_body = decode(raw, wait, 0x24)
    wait_id = next(i.operands[0].imm for i in wait_body if i.mnemonic == 'bl' and i.address > wait + 0x10)
    return dict(ring_submit=ring_submit, ring_table=ring_table, submit=submit, wait=wait, wait_id=wait_id,
                reg_write=reg_write, reg_store=store[3].address, flush=calls[0])


def expected_ring(cursor, submission_id, list_address, length, full_submit):
    values = [0xa5a5a5a5] * CAPACITY
    def put(value):
        nonlocal cursor
        values[cursor] = value; cursor = (cursor + 1) % CAPACITY
    if length == 0: return values, cursor, submission_id, []
    if cursor + 4 >= CAPACITY:
        while cursor: put(0x10000)
    while cursor % 4: put(0x10000)
    for value in (0xf0, list_address, 0x200f4, length): put(value)
    doorbells = [(PHYS + 4 * cursor) | 4]
    new_id = (submission_id + 1) % 0x1000000
    if full_submit and new_id > 0:
        # These chosen probes leave room for this footer. Other ID-packet wrap
        # positions remain outside this small independent expected-value check.
        if cursor not in (4, 8): raise ValueError('Unreviewed footer start')
        next_address = PHYS + (cursor + 8) * 4
        for value in (0x148, new_id, 0xf8, 1, 0xff0000f0, next_address, 0xff0000f4, 0): put(value)
        doorbells.append((PHYS + 4 * cursor) | 4)
    return values, cursor, new_id, doorbells


def run(raw, original_sram, original_work, snapshot, contract, cursor, submission_id, full_submit, observe=True, length=42):
    sram = bytearray(original_sram);work = bytearray(original_work)
    table_offset = contract['ring_table'] - SRAM
    struct.pack_into('<5I', sram, table_offset, BO, RING, PHYS, CAPACITY, 0)
    work[0xafe0:0xb120] = b'\xa5' * 0x140
    work[0xb400:0xb440] = bytes(0x40)
    struct.pack_into('<6I', work, 0xb400, CAPACITY * 4, 0, RING, PHYS, cursor, submission_id)
    if full_submit: struct.pack_into('<I', work, 0x2014, length)
    u = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    u.ctl_set_cpu_model(arm.UC_CPU_ARM_CORTEX_M7)
    u.reg_write(arm.UC_ARM_REG_C1_C0_2, 0xf00000);u.reg_write(arm.UC_ARM_REG_FPEXC, 0x40000000)
    extent = (len(raw) + 4095) & ~4095
    for address, data, size in [(BASE, raw, extent), (SRAM, bytes(sram), 0x80000), (WORK, bytes(work), 0x10000)]:
        u.mem_map(address, size);u.mem_write(address, data)
    u.mem_protect(BASE, extent, UC_PROT_READ | UC_PROT_EXEC)
    u.mem_protect(SRAM, 0x80000, UC_PROT_READ);u.mem_protect(WORK, 0x10000, UC_PROT_READ | UC_PROT_WRITE)
    u.mem_map(STOP, 0x1000, UC_PROT_READ | UC_PROT_EXEC)
    u.mem_map(0x40090000, 0x1000);u.mem_write(0x40090000, b'\x5a' * 0x1000)
    _, nema_slot = discover(raw)
    region = snapshot['nema_state_region']['contract']['region']
    readable = [(BASE, BASE+len(raw)), (SRAM, SRAM+0x6000), (WORK, WORK+0x10000),
                (contract['ring_table'], contract['ring_table']+20), (nema_slot, nema_slot+4), (region, region+64)]
    def reject_read(cpu, kind, address, size, value, user):
        if not any(a<=address and address+size<=b for a,b in readable):
            raise ValueError('Read outside restored/synthetic input: '+hex(address))
    u.hook_add(UC_HOOK_MEM_READ, reject_read)
    writes=[]
    if observe:
        def writer(cpu,address,size,user):
            reg=cpu.reg_read(arm.UC_ARM_REG_R0);value=cpu.reg_read(arm.UC_ARM_REG_R1)
            if reg != 0xec: raise ValueError('Unsupported original GPU register write')
            writes.append([reg,value])
        u.hook_add(UC_HOOK_CODE,writer,begin=contract['reg_write'],end=contract['reg_write'])
    for n in range(4,12):u.reg_write(getattr(arm,'UC_ARM_REG_R'+str(n)),0x12340000+n)
    args=[WORK+0x2000,0,0,0] if full_submit else [WORK+0x4000,length,0,0]
    for n,value in enumerate(args):u.reg_write(getattr(arm,'UC_ARM_REG_R'+str(n)),value)
    u.reg_write(arm.UC_ARM_REG_SP,WORK+0xff00);u.reg_write(arm.UC_ARM_REG_LR,STOP|1)
    entry=contract['submit'] if full_submit else contract['ring_submit']
    u.emu_start(entry|1,STOP,count=100000)
    if (u.reg_read(arm.UC_ARM_REG_PC)!=STOP or u.reg_read(arm.UC_ARM_REG_SP)!=WORK+0xff00
            or any(u.reg_read(getattr(arm,'UC_ARM_REG_R'+str(n)))!=0x12340000+n for n in range(4,12))):
        raise ValueError('Original submit did not preserve return/ABI')
    after=bytes(u.mem_read(WORK,0x10000));gpu=bytes(u.mem_read(0x40090000,0x1000))
    allowed=[(0x1000,0x1100),(0x2000,0x2040),(0xb000,0xb100),(0xb400,0xb440),(0xfc00,0xff00)]
    if any(not any(a<=i<b for a,b in allowed) for i,(x,y) in enumerate(zip(work,after)) if x!=y):
        raise ValueError('Unexpected submit memory effect')
    if (after[0xafe0:0xb000]!=b'\xa5'*32 or after[0xb100:0xb120]!=b'\xa5'*32
            or bytes(u.mem_read(SRAM,0x80000))!=bytes(sram)
            or gpu[:0xec]+gpu[0xf0:]!=b'\x5a'*(0x1000-4)):
        raise ValueError('Submit changed protected input or unknown GPU register')
    result=dict(entry=entry,args=args,returned=True,result=u.reg_read(arm.UC_ARM_REG_R0),
                ring=list(struct.unpack_from('<64I',after,0xb000)),cursor=struct.unpack_from('<I',after,0xb410)[0],
                submission_id=struct.unpack_from('<I',after,0xb414)[0],list_id=struct.unpack_from('<I',after,0x201c)[0],
                writes=writes,doorbell=struct.unpack_from('<I',gpu,0xec)[0],work_sha256=sha(after),
                commands_unchanged=after[0x4000:0x40b0]==bytes(work[0x4000:0x40b0]),
                surface_unchanged=after[0x9fe0:0xa820]==bytes(work[0x9fe0:0xa820]))
    wanted, end, identity, bells = expected_ring(cursor,submission_id,WORK+0x4000,length,full_submit)
    if (result['ring']!=wanted or result['cursor']!=end or result['submission_id']!=identity
            or (observe and result['writes']!=[[0xec,v] for v in bells])
            or result['doorbell']!=(bells[-1] if bells else 0x5a5a5a5a)
            or not result['commands_unchanged'] or not result['surface_unchanged']):
        raise ValueError('Original ring/doorbell differs from reviewed contract')
    if full_submit and length:
        # Execute original cl_wait only to its real wait-ID callee entry; do not
        # execute the semaphore path or substitute a completion return.
        u.reg_write(arm.UC_ARM_REG_R0,WORK+0x2000);u.reg_write(arm.UC_ARM_REG_SP,WORK+0xff00);u.reg_write(arm.UC_ARM_REG_LR,STOP|1)
        u.emu_start(contract['wait']|1,contract['wait_id'],count=1000)
        result['wait_boundary']=dict(pc=u.reg_read(arm.UC_ARM_REG_PC),id=u.reg_read(arm.UC_ARM_REG_R0),returned=False)
        if result['wait_boundary']['pc']!=contract['wait_id']:raise ValueError('Expected original wait-ID boundary')
    inputs=dict(sram=bytes(sram),work=bytes(work),entry=entry,args=args)
    return result,inputs


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();out=a.output.resolve()
    if any((v/'.git').exists() for v in [out,*out.parents]):raise ValueError('Private output required')
    out.mkdir(mode=0o700);cases=[]
    for case,filename in [('stock24','stock-2.4.0.24.bin'),('stock23','stock-2.3.0.24.bin'),('cfw','faceclaw-38-research-only.bin')]:
        source=a.simulator/'nema-state-batch-m55-01'/(case+'-full-letter');report=json.loads((source/'report.json').read_text());snapshot=json.loads((source/'snapshot.json').read_text())
        _,raw=load_pinned_main((a.simulator/'inputs/verified-01'/filename).read_bytes());sram=(source/'sram.bin').read_bytes();work=(source/'result/final-work.bin').read_bytes()
        if not report['passed'] or sha(work)!=report['final_hashes']['work']:raise ValueError('Unverified source batch')
        validate_region(a.simulator,case,raw,snapshot,sram);contract=discover_submission(raw);runs={}
        for name,cursor,identity,full,length in [('nominal',0,7,True,42),('unaligned',1,7,True,42),('tail60',60,7,True,42),('tail61',61,7,True,42),('tail63',63,7,True,42),('id-wrap',0,0xffffff,True,42),('empty',0,7,True,0),('direct-bytes-probe',0,7,False,168),('direct-empty',0,7,False,0)]:
            result,inputs=run(raw,sram,work,snapshot,contract,cursor,identity,full,length=length);runs[name]=result
            if name=='nominal':
                control,_=run(raw,sram,work,snapshot,contract,cursor,identity,full,observe=False,length=length)
                if result['work_sha256']!=control['work_sha256'] or result['doorbell']!=control['doorbell']:raise ValueError('Submission code observer changed execution')
                runs['observer-off']=control
                folder=out/'captures'/case;folder.mkdir(mode=0o700,parents=True)
                for filename,data in [('sram.bin',inputs['sram']),('work.bin',inputs['work'])]:(folder/filename).write_bytes(data)
                record=dict(case=case,contract=contract,entry=inputs['entry'],args=inputs['args'],raw_sha256=sha(raw),
                            image_hashes={n:sha((folder/n).read_bytes()) for n in ['sram.bin','work.bin']},expected=result,
                            synthetic_ring=True,source_report_sha256=sha((source/'report.json').read_bytes()))
                (folder/'snapshot.json').write_text(json.dumps(record,indent=2)+'\n')
        cases.append(dict(case=case,contract=contract,runs=runs))
    result=dict(passed=True,cases=cases,synthetic_ring=True,cpu='Unicorn Cortex-M7 auxiliary',gpu_executed=False,completion_injected=False,full_main_rendered=False)
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n');(out/'inspector.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps(dict(passed=True,cases=3,submission_calls=30,wait_boundaries=21,gpu_executed=False)))


if __name__=='__main__':main()
