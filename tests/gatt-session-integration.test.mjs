import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {GattTransport} from '../web/gatt-transport.mjs';
import {ComponentOtaSession} from '../web/component-ota-session.mjs';

// Independent wire decoder/encoder, never invokes the production packet helpers.
function checksum(bytes) {
  let value=65535;
  for(const byte of bytes) {
    value^=byte*256;
    for(let i=0;i<8;i++) value=((value*2)^((value&32768)?4129:0))&65535;
  }
  return [value&255,value>>8];
}
function fakeDevice(disconnectBlock=-1) {
  const device=new EventTarget(); device.gatt={connected:true};
  let phase='auth', header=null, marker=null, writes=0;
  const blocks=[], channels={};
  for(const name of ['data','control']) {
    const notify=new EventTarget(); notify.startNotifications=async()=>notify;
    let partial=[], expectedIndex=1, sequence=null, sid=null, count=null;
    const reply=(service,payload,seq)=>{
      const data=Uint8Array.of(170,18,seq,payload.length+2,1,1,service,0,...payload,...checksum(payload));
      notify.value=new DataView(data.buffer);
      notify.dispatchEvent(new Event('characteristicvaluechanged'));
    };
    const write={async writeValueWithoutResponse(frame) {
      writes++;
      assert.equal(frame[0],170);assert.equal(frame[1],33);
      assert.equal(frame[3],frame.length-8);assert.equal(frame[5],expectedIndex);
      if(expectedIndex===1) {sequence=frame[2];sid=frame[6];count=frame[4];}
      assert.equal(frame[2],sequence);assert.equal(frame[6],sid);assert.equal(frame[4],count);
      partial.push(...frame.slice(8)); expectedIndex++;
      if(frame[5]!==count) return;
      const payload=partial.slice(0,-2);
      assert.deepEqual(partial.slice(-2),checksum(payload));
      partial=[];expectedIndex=1;
      if(name==='control') {
        assert.ok(phase==='auth'||phase==='ended');
        assert.equal(sid,128);assert.deepEqual(payload.slice(-6),[26,4,8,1,16,4]);
        reply(128,[...payload.slice(0,-6),26,0],sequence);
        if(phase==='auth') phase='begin';
        return;
      }
      if(sid===193) {
        assert.equal(phase,'blocks');assert.equal(marker,sequence);
        assert.ok(payload.length>0&&payload.length<=4096);
        if(blocks.length===disconnectBlock) {
          device.gatt.connected=false;device.dispatchEvent(new Event('gattserverdisconnected'));return;
        }
        blocks.push(Buffer.from(payload));marker=null;reply(192,[2,0],sequence);return;
      }
      assert.equal(sid,192);
      const op=payload[0];
      if(op===0) {assert.equal(phase,'begin');phase='header';}
      else if(op===1) {assert.equal(phase,'header');header=Buffer.from(payload.slice(1));phase='blocks';}
      else if(op===2) {assert.equal(phase,'blocks');assert.equal(marker,null);marker=sequence;return;}
      else if(op===3) {
        assert.equal(phase,'blocks');assert.equal(marker,null);
        assert.equal(Buffer.concat(blocks).length,header.readUInt32LE(8));phase='ended';
      } else assert.fail(`Unknown opcode ${op}`);
      reply(192,[op,0],sequence);
    }};
    channels[name]={write,notify};
  }
  return {device,channels,blocks,get header(){return header;},get writes(){return writes;},get phase(){return phase;}};
}

for(const [kind,path] of [
  ['main-cfw',process.env.BLACKWALL_COMPONENT_DIR&&`${process.env.BLACKWALL_COMPONENT_DIR}/main-cfw.bin`],
  ['main-stock',process.env.BLACKWALL_COMPONENT_DIR&&`${process.env.BLACKWALL_COMPONENT_DIR}/main-stock.bin`],
  ['boot',process.env.BLACKWALL_BOOT_COMPONENT],
  ['boot-24',process.env.BLACKWALL_BOOT24_COMPONENT],
]) {
  test(`${kind}: full session through GATT and independent simulated wire endpoint`,{skip:!path},async()=>{
    const raw=readFileSync(path);
    const fake=fakeDevice();
    const session=new ComponentOtaSession(new GattTransport(fake.device,fake.channels),kind);
    const result=await session.transfer({header:new Uint8Array(raw.slice(0,128)),payload:new Uint8Array(raw.slice(128))});
    assert.deepEqual(fake.header,raw.slice(0,128));
    assert.deepEqual(Buffer.concat(fake.blocks),raw.slice(128));
    assert.equal(fake.phase,'ended');assert.equal(result.readbackVerified,false);
    assert.equal(session.state,'awaiting-verification');
  });
}
for(const [kind,path] of [['boot',process.env.BLACKWALL_BOOT_COMPONENT],['boot-24',process.env.BLACKWALL_BOOT24_COMPONENT]]) {
test(`${kind}: disconnect after one block stops integrated transfer without END or retries`,{skip:!path},async()=>{
  const raw=new Uint8Array(readFileSync(path));
  const header=raw.slice(0,128),payload=raw.slice(128);
  const fake=fakeDevice(1), session=new ComponentOtaSession(new GattTransport(fake.device,fake.channels),kind);
  await assert.rejects(()=>session.transfer({header,payload}),/disconnect/);
  const writes=fake.writes;
  await new Promise(resolve=>setTimeout(resolve,0));
  assert.equal(fake.writes,writes);assert.equal(fake.blocks.length,1);
  assert.equal(fake.phase,'blocks');assert.equal(session.state,'outcome-unknown');
});

}
