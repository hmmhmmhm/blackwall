"""Bounded UART checksum and nonzero recovery using pinned upstream ARM payloads."""
import hashlib,struct,zlib
from pathlib import Path
PAYLOAD_SHA='4bbd4bfbd4f403b9da4967da4a88b23d61f99f00e523cd527262ce10347fc4ac'
def request(op,payload=b''):
 if len(payload)>22:raise ValueError('Bounded request payload required')
 b=bytes([0x7e,0,1,27])+b'RQST'+bytes([op])+payload.ljust(22,b'\0');return list(b+bytes([(32+0x7d+sum(b))&255]))
def reply(kind,status=0,data=b''):
 b=bytes([0,1,3,23])+b'RESP'+bytes([kind,status])+data.ljust(16,b'\0')+b'\0';return list(bytes([90,165,255,27])+b+bytes([(25+sum(b))&255]))
def block(kind,data=b''):
 b=struct.pack('<4sHH',b'BLK2',kind,len(data))+data
 return list(b+struct.pack('<I',zlib.crc32(b)))

def recover_plan(root):
 import json
 root=Path(root);code=(root/'source/build/recover.bin').read_bytes();m=json.loads((root/'source/build/recover.json').read_text());expected='f046754b6ecba4dd4e3c8e7aa568a713e0961e7f286e98a6f96f955882408732'
 if len(code)!=264 or hashlib.sha256(code).hexdigest()!=expected or m!=dict(bytes=264,sha256=expected,functions={'entry':{'offset':0,'bytes':264}},base=0):raise ValueError('Exact upstream nonzero recover payload required')
 main=(root/'main-2.3.2.14.bin').read_bytes()
 if hashlib.sha256(main).hexdigest()!='69f9ef63997c9bb53e5b97f83cc330e93651577ab1595ac57dcb481c3e513b9c':raise ValueError('Exact recovery source image required')
 packets=[request(1,struct.pack('<HHIII',264,0,0x438010,16,zlib.crc32(code)))]+[request(2,bytes([len(code[i:i+16])])+code[i:i+16]) for i in range(0,len(code),16)]+[request(3)]
 responses=[reply(0)]*(len(packets)-2)+[reply(3),reply(2,0,struct.pack('<I',0))]
 return dict(mode='recover16',wire_payload_sha256=expected,payload_sha256=expected,payload_bytes=list(code),entry_offset=0,address=0x438010,length=16,expected_crc32=None,packets=packets,responses=responses,restore_bytes=list(main[16:32]),block_request=block(4,struct.pack('<H',16)),block_input=block(2,main[16:32]),block_output=block(1,struct.pack('<I',16)),block_ack=block(3),upstream_readonly_example=False)

def plan(build,mode):
 import json
 if mode=='recover16':return recover_plan(build)
 if mode not in ('checksum','bad-crc','tamper'):raise ValueError('Explicit checksum recovery mode required')
 root=Path(build);code=(root/'source/build/checksum.bin').read_bytes();m=json.loads((root/'source/build/checksum.json').read_text());main=(root/'main-2.3.2.14.bin').read_bytes()
 if len(code)!=48 or hashlib.sha256(code).hexdigest()!=PAYLOAD_SHA or m!=dict(bytes=48,sha256=PAYLOAD_SHA,functions={'entry':{'offset':0,'bytes':48}},base=0):raise ValueError('Exact upstream checksum payload required')
 if hashlib.sha256(main).hexdigest()!='69f9ef63997c9bb53e5b97f83cc330e93651577ab1595ac57dcb481c3e513b9c':raise ValueError('Exact checksum source image required')
 wire=bytearray(code)
 if mode=='tamper':wire[0]^=1
 wire=bytes(wire)
 crc=zlib.crc32(wire)^(1 if mode=='bad-crc' else 0);expected=zlib.crc32(main[:4096])
 packets=[request(1,struct.pack('<HHIII',48,0,0x438000,4096,crc))]+[request(2,bytes([16])+wire[i:i+16]) for i in range(0,48,16)]+[request(3)]
 responses=[reply(0),reply(0),reply(0),reply(3),reply(2,0,struct.pack('<I',expected))] if mode!='bad-crc' else [reply(0),reply(0),reply(0),reply(4,3),reply(4,1)]
 return dict(mode=mode,wire_payload_sha256=hashlib.sha256(wire).hexdigest(),payload_sha256=PAYLOAD_SHA,payload_bytes=list(code),entry_offset=0,address=0x438000,length=4096,expected_crc32=expected,packets=packets,responses=responses,upstream_readonly_example=True)

HELPER='''RECOVERY_INDEX=0;RECOVERY_CURSOR=50;RECOVERY_COMPLETED=False;RECOVERY_REPLIES=[];RELEASE_OFFSET=50;RECOVERY_INPUT_SENT=False;RECOVERY_OUTPUT_ACKED=False;RECOVERY_FAILURE=None
def advance_recovery(tx):
 global RECOVERY_INDEX,RECOVERY_CURSOR,RECOVERY_COMPLETED,RELEASE_OFFSET,peer_stage,RECOVERY_INPUT_SENT,RECOVERY_OUTPUT_ACKED,RECOVERY_FAILURE
 if peer_stage!='recovery':return
 if RECOVERY_PLAN['mode']=='recover16' and (not RECOVERY_INPUT_SENT or RECOVERY_PLAN.get('expect_progress',True)) and RECOVERY_INDEX==len(RECOVERY_PLAN['packets'])-1:
  if not RECOVERY_INPUT_SENT or not RECOVERY_OUTPUT_ACKED:
   field='block_request' if not RECOVERY_INPUT_SENT else 'block_output';expected=RECOVERY_PLAN[field]
   if len(tx)<RECOVERY_CURSOR+len(expected):return
   if tx[RECOVERY_CURSOR:RECOVERY_CURSOR+len(expected)]!=expected:
    RECOVERY_FAILURE=dict(phase=field,bytes=tx[RECOVERY_CURSOR:RECOVERY_CURSOR+32]);peer_stage='recovery-error';return
   RECOVERY_CURSOR+=len(expected);event(field,bytes=len(expected))
   if not RECOVERY_INPUT_SENT:RECOVERY_INPUT_SENT=True;queue('block-input',RECOVERY_PLAN['block_input'])
   else:RECOVERY_OUTPUT_ACKED=True;queue('block-ack',RECOVERY_PLAN['block_ack'])
   return
 if len(tx)<RECOVERY_CURSOR+32:return
 frame=tx[RECOVERY_CURSOR:RECOVERY_CURSOR+32]
 if frame!=RECOVERY_PLAN['responses'][RECOVERY_INDEX]:
  RECOVERY_FAILURE=dict(phase='response',index=RECOVERY_INDEX,bytes=frame,expected=RECOVERY_PLAN['responses'][RECOVERY_INDEX]);peer_stage='recovery-error';return
 RECOVERY_REPLIES.append(dict(index=RECOVERY_INDEX,kind=frame[12],status=frame[13],tick=tick()))
 event('recovery-response',index=RECOVERY_INDEX,reply_kind=frame[12],status=frame[13])
 RECOVERY_CURSOR+=32;RECOVERY_INDEX+=1
 if RECOVERY_INDEX<len(RECOVERY_PLAN['packets']):queue('recovery-'+str(RECOVERY_INDEX),RECOVERY_PLAN['packets'][RECOVERY_INDEX])
 else:
  RECOVERY_COMPLETED=RECOVERY_PLAN['mode'] in ('checksum','recover16') and RECOVERY_PLAN.get('expected_return',0)==0;RELEASE_OFFSET=RECOVERY_CURSOR
  peer_stage='continue';queue('continue',request('CONT'))
'''
def bind_peer(source,p):
 anchor='def advance_peer():'
 if source.count(anchor)!=1:raise ValueError('Unique peer function required')
 source=source.replace(anchor,'RECOVERY_PLAN='+repr(p)+'\n'+HELPER+'\n'+anchor)
 edits=[("peer_stage='continue';queue('continue',request('CONT'))", "peer_stage='recovery';queue('recovery-0',RECOVERY_PLAN['packets'][0])"),('len(tx)>=63','len(tx)>=RELEASE_OFFSET+13'),('tx[50:63]','tx[RELEASE_OFFSET:RELEASE_OFFSET+13]')]
 # The helper contains its own CONT completion; replace only the original OKAY line.
 old,new=edits[0];line="  peer_accepted=True;held_snapshot=session();event('okay',session=held_snapshot);"+old
 if source.count(line)!=1:raise ValueError('Unique original OKAY continuation required')
 source=source.replace(line,"  peer_accepted=True;held_snapshot=session();event('okay',session=held_snapshot);"+new)
 for old,new in edits[1:]:
  if source.count(old)!=1:raise ValueError('Unique release frame offset required')
  source=source.replace(old,new)
 anchor='start=int(m.ElapsedVirtualTime'
 if source.count(anchor)!=1:raise ValueError('Unique peer start boundary required')
 source=source.replace(anchor,' advance_recovery(tx)\n'+anchor)
 if p['mode']=='recover16':
  source=source.replace(' advance_peer()\n EmulationManager.Instance.CurrentEmulation.StartAll()'," advance_peer()\n if peer_stage=='recovery-error':break\n EmulationManager.Instance.CurrentEmulation.StartAll()")
 anchor="result['machine_aborted']="
 source=source.replace(anchor,"result['recovery_command']=dict(mode=RECOVERY_PLAN['mode'],expected_return=RECOVERY_PLAN.get('expected_return',0),protocol_completed=RECOVERY_INDEX==len(RECOVERY_PLAN['packets']),completed=RECOVERY_COMPLETED,failure=RECOVERY_FAILURE,input_sent=RECOVERY_INPUT_SENT,output_acked=RECOVERY_OUTPUT_ACKED,replies=RECOVERY_REPLIES,expected_crc32=RECOVERY_PLAN['expected_crc32'],payload_sha256=RECOVERY_PLAN['payload_sha256'])\n"+anchor)
 return source
