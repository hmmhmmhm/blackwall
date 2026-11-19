"""Audit pinned BLE references and pure packet helpers without importing BLE or using devices."""
import argparse,ast,binascii,hashlib,json,re,struct,subprocess,types
from pathlib import Path
PIN='b227335f5fbecb7d4ede3748c36e098ef88850fa'
PURE=['crc16_ccitt','add_crc','encode_varint','build_packet','build_auth_packets','build_display_config','build_teleprompter_init','build_content_page','build_marker','build_sync','format_text']
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator;r=s/'even-g2-protocol-research-01';src=r/'source';o=a.output;o.mkdir(mode=0o700);checks=[]
 def check(n,v):
  if not v:raise ValueError(n)
  checks.append(n)
 man=json.loads((r/'sources.json').read_text());tree=json.loads((r/'tree.json').read_text())['tree'];check('commit-pin',man['commit']==PIN and not man['executed_upstream_ble'])
 for f in man['files']:
  raw=(src/f['path']).read_bytes();blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest();check(f['path']+'-pin',hashlib.sha256(raw).hexdigest()==f['sha256'] and blob==f['git_blob']==next(x['sha'] for x in tree if x['path']==f['path']))
 source=(src/'examples/teleprompter/teleprompter.py').read_text();parsed=ast.parse(source);functions=[x for x in parsed.body if isinstance(x,ast.FunctionDef) and x.name in PURE];check('pure-helper-selection',{x.name for x in functions}==set(PURE))
 # Only inspected synchronous encoding functions are evaluated. Imports, BLE code and entrypoint are excluded.
 namespace={'time':types.SimpleNamespace(time=lambda:1760000000)};exec(compile(ast.Module(body=functions,type_ignores=[]),'pinned-pure-packet-helpers','exec'),namespace)
 for data in [b'',b'123456789',bytes(range(256))]:check('CRC-'+str(len(data)),namespace['crc16_ccitt'](data)==binascii.crc_hqx(data,0xffff))
 def packet_valid(b):return len(b)>=10 and b[:2]==b'\xaa\x21' and b[3]==len(b)-8 and int.from_bytes(b[-2:],'little')==binascii.crc_hqx(b[8:-2],0xffff)
 for length in [0,1,128,253]:check('packet-length-'+str(length),packet_valid(namespace['build_packet'](1,6,0x20,b'x'*length)))
 try:namespace['build_packet'](1,6,0x20,b'x'*254)
 except ValueError:checks.append('single-byte-length-overflow-observed')
 else:raise ValueError('Expected length limit differs')
 auth=namespace['build_auth_packets']();check('seven-auth-frames-codec-only',len(auth)==7 and all(packet_valid(b) for b in auth))
 display=namespace['build_display_config'](8,20);check('display-config-transport',packet_valid(display))
 # The helper uses a literal protobuf length for the field4 configuration.
 payload=display[8:-2];check('display-config-field-length',payload[:6]==bytes([8,2,16,20,0x22,106]) and len(payload[6:])==106)
 check('small-text-codec',packet_valid(namespace['build_content_page'](10,22,0,'Blackwall')))
 overflow=[]
 for label,text in [('ascii-full-page',('\n'.join(['x'*25]*10))),('korean-full-page','\n'.join(['가'*25]*10))]:
  page=namespace['format_text'](text)[0]
  try:namespace['build_content_page'](10,22,0,page)
  except ValueError:overflow.append(label)
 check('text-pages-exceed-single-byte-frame',len(overflow)==2)
 check('responses-ignored','start_notify(CHAR_NOTIFY, lambda s, d: None)' in source)
 check('side-selection-fallback','g2_devices[0]' in source)
 proto=src/'proto/g2_protocol.proto';cmd=['/opt/homebrew/bin/protoc','--proto_path='+str(proto.parent),'--descriptor_set_out='+str(o/'schema.pb'),str(proto.name)];result=subprocess.run(cmd,capture_output=True,text=True,timeout=30);(o/'protoc.log').write_text(result.stdout+result.stderr);check('schema-duplicate-field-reproduced',result.returncode!=0 and 'Field number 2 has already been used' in result.stderr)
 key=namespace['encode_varint']((128<<3)|2);check('time-sync-tag-is-field128',key==b'\x82\x08' and 'TimeSyncData sync = 16;' in proto.read_text())
 capture=(src/'captures/teleprompter-session.log').read_bytes();magic,version,linktype=struct.unpack_from('>8sII',capture);check('capture-btsnoop-header',magic==b'btsnoop\0' and version==1)
 # Do not repair an unfamiliar capture format or treat it as a validated wire transcript.
 check('capture-linktype-observation',linktype==768)
 licenses=[x['path'] for x in tree if x['type']=='blob' and '/' not in x['path'] and re.search(r'license|copying|notice',x['path'],re.I)];check('root-license-not-found',not licenses)
 report=dict(passed=True,count=len(checks),checks=checks,commit=PIN,pure_functions_executed=PURE,ble_imported=False,hardware_accessed=False,physical_validated=False,firmware_2_4_0_24_compatibility_verified=False,capture=dict(file='captures/teleprompter-session.log',bytes=len(capture),btsnoop_version=version,linktype=linktype,decoded=False,wire_crc_verified=False),findings=dict(single_frame_payload_max=253,text_overflow_cases=overflow,protobuf_schema_builds=False,time_sync_tag_field=128,proto_declared_sync_field=16),scope='offline reference/codec checks only; no auth completion, connection, stock display or full emulator BLE proof')
 (o/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(passed=True,count=len(checks),schema_builds=False,text_overflow=overflow,capture_decoded=False)))
if __name__=='__main__':main()
