import test from 'node:test';
import assert from 'node:assert/strict';
import {ComponentOtaSession} from '../web/component-ota-session.mjs';

import {readFileSync} from 'node:fs';
for(const [kind,bootPath] of [['boot',process.env.BLACKWALL_BOOT_COMPONENT],['boot-24',process.env.BLACKWALL_BOOT24_COMPONENT]]) {
const check=(name,fn)=>test(`${kind}: ${name}`,{skip:!bootPath},fn);
function component() {
  const raw=new Uint8Array(readFileSync(bootPath));
  return {header:raw.slice(0,128),payload:raw.slice(128)};
}

function transport(failAt = -1) {
  return {
    calls: [],
    async exchange(channel, packets, accept, timeout) {
      this.calls.push({channel, packets, timeout});
      if(this.calls.length === failAt) throw new Error('timeout');
      const first = packets[0];
      const request = first.slice(8,-2);
      const payload = channel === 'control'
        ? Uint8Array.of(...request.slice(0,-6),0x1a,0)
        : Uint8Array.of(request[0],0);
      const reply = {sid:first[6], payload};
      assert.equal(accept(reply),true);
      if(channel==='control') assert.equal(accept({...reply,sid:0x55}),false);
      else assert.equal(accept({...reply,payload:Uint8Array.of(0x7f,0)}),false);
      return payload;
    }
  };
}

check('boot component follows authenticate, begin, header, blocks, end, liveness',async()=>{
  const io=transport(), session=new ComponentOtaSession(io,kind);
  const result=await session.transfer(component());
  assert.deepEqual(io.calls.map(c=>c.channel),['control',...Array(42).fill('data'),'control']);
  assert.deepEqual(io.calls.slice(1,-1).map(c=>c.packets[0][8]),[0,1,...Array(39).fill(2),3]);
  for(const call of io.calls.slice(3,-2)) {
    assert.equal(call.packets.length,19);
    assert.ok(call.packets.every(p=>p[2]===call.packets[0][2]));
  }
  assert.equal(result.readbackVerified,false);
  assert.equal(session.state,'awaiting-verification');
  await assert.rejects(()=>session.transfer(component()),/single-use/);
});

check('every exchange failure stops without retry or subsequent packets',async()=>{
  for(let failAt=1;failAt<=44;failAt++) {
    const io=transport(failAt), session=new ComponentOtaSession(io,kind);
    await assert.rejects(()=>session.transfer(component()),/timeout/);
    assert.equal(io.calls.length,failAt);
    assert.equal(session.state,'outcome-unknown');
    await assert.rejects(()=>session.transfer(component()),/single-use/);
  }
});

check('main and unaligned images are rejected before any transport access',async()=>{
  for(const bad of ['main','length','header']) {
    const io=transport(), session=new ComponentOtaSession(io,kind), image=component();
    if(bad==='main') new DataView(image.header.buffer).setUint32(36,0,true);
    if(bad==='length') image.payload=image.payload.slice(1);
    if(bad==='header') image.header=image.header.slice(1);
    await assert.rejects(()=>session.transfer(image));
    assert.equal(io.calls.length,0);
  }
});

check('concurrent second call is rejected while first is active',async()=>{
  const io=transport(); let release, reached;
  const started=new Promise(resolve=>reached=resolve);
  const exchange=io.exchange.bind(io);
  io.exchange=async(...args)=>{ if(!release) { reached(); await new Promise(r=>release=r); } return exchange(...args); };
  const session=new ComponentOtaSession(io,kind), first=session.transfer(component());
  await started;
  await assert.rejects(()=>session.transfer(component()),/single-use/);
  release(); await first;
});

check('negative acknowledgments stop at the rejected operation',async()=>{
  for(const failAt of [2,3,4,42,43]) {
    const io=transport(), original=io.exchange.bind(io);
    io.exchange=async(...args)=>{
      const result=await original(...args);
      if(io.calls.length===failAt) result[1]=7;
      return result;
    };
    const session=new ComponentOtaSession(io,kind);
    await assert.rejects(()=>session.transfer(component()),/rejected/);
    assert.equal(io.calls.length,failAt);
    assert.equal(session.state,'outcome-unknown');
  }
});

check('OTA response matching follows upstream channel/opcode contract with trailing bytes',async()=>{
  const io=transport();
  const original=io.exchange.bind(io);
  io.exchange=async(channel,packets,accept,timeout)=>{
    const result=await original(channel,packets,accept,timeout);
    if(channel==='data') {
      const payload=Uint8Array.of(...result,0x42);
      assert.equal(accept({sid:0x55,payload}),true);
      assert.equal(accept({sid:0x55,payload:Uint8Array.of(0x7f,0)}),false);
      return payload;
    }
    return result;
  };
  await new ComponentOtaSession(io,kind).transfer(component());
});

}

test('boot versions cannot be substituted before transport access',
  {skip:!process.env.BLACKWALL_BOOT_COMPONENT||!process.env.BLACKWALL_BOOT24_COMPONENT},async()=>{
    for(const [kind,path] of [['boot',process.env.BLACKWALL_BOOT24_COMPONENT],['boot-24',process.env.BLACKWALL_BOOT_COMPONENT]]) {
      const raw=new Uint8Array(readFileSync(path));
      let calls=0;
      const session=new ComponentOtaSession({exchange(){calls++;throw new Error('must not send');}},kind);
      await assert.rejects(()=>session.transfer({header:raw.slice(0,128),payload:raw.slice(128)}),/SHA256/);
      assert.equal(calls,0);
      assert.equal(session.state,'rejected');
    }
  });
