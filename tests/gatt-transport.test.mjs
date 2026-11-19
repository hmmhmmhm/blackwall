import test from 'node:test';
import assert from 'node:assert/strict';
import {GattTransport} from '../web/gatt-transport.mjs';
import {frames} from '../web/ota-packets.mjs';
function setup(onWrite) {
  const device=new EventTarget(); device.gatt={connected:true};
  const notify=new EventTarget(); let started=false;
  notify.startNotifications=async()=>{started=true;return notify;};
  const sent=[];
  const emit=(bytes)=>{const event=new Event('characteristicvaluechanged');notify.value=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);notify.dispatchEvent(event);};
  const write={writeValueWithoutResponse:async(bytes)=>{assert.ok(started);sent.push(bytes);await onWrite?.({emit,device,bytes});}};
  const io=new GattTransport(device,{data:{write,notify},control:{write,notify}});
  return {io,sent,emit,device};
}
const request=()=>frames(0xc0,Uint8Array.of(0),1);
const reply=()=>{const b=request()[0];b[1]=0x12;return b;};
const accept=r=>r.sid===0xc0;

test('notification during write is captured after subscription',async()=>{
  const {io,sent}=setup(({emit})=>emit(reply()));
  assert.deepEqual(await io.exchange('data',request(),accept,100),Uint8Array.of(0));
  assert.equal(sent.length,1);
});
test('timeout makes transport terminal and never retries',async()=>{
  const {io,sent}=setup();
  await assert.rejects(()=>io.exchange('data',request(),accept,5),/timeout/);
  await assert.rejects(()=>io.exchange('data',request(),accept,5),/closed/);
  assert.equal(sent.length,1);
});
test('disconnect stops before sending subsequent frames',async()=>{
  const {io,sent}=setup(({device})=>device.dispatchEvent(new Event('gattserverdisconnected')));
  await assert.rejects(()=>io.exchange('data',[...request(),...request()],accept,100),/disconnect/);
  assert.equal(sent.length,1);
});
test('busy session rejects concurrent exchange',async()=>{
  const {io,emit}=setup();
  const first=io.exchange('data',request(),accept,100);
  await assert.rejects(()=>io.exchange('data',request(),accept,100),/busy/);
  emit(reply()); await first;
});
test('corrupt replies are ignored until timeout',async()=>{
  const {io}=setup(({emit})=>{const b=reply();b[8]^=1;emit(b);});
  await assert.rejects(()=>io.exchange('data',request(),accept,5),/timeout/);
});

test('timed-out pending write cannot send the remaining packets when it resolves',async()=>{
  let release;
  const {io,sent}=setup(()=>new Promise(resolve=>release=resolve));
  await assert.rejects(()=>io.exchange('data',[...request(),...request()],accept,5),/timeout/);
  release();
  await new Promise(resolve=>setTimeout(resolve,0));
  assert.equal(sent.length,1);
  await assert.rejects(()=>io.exchange('data',request(),accept,5),/closed/);
});
