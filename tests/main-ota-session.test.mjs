import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {ComponentOtaSession} from '../web/component-ota-session.mjs';

for(const kind of ['main-cfw','main-stock']) {
  test(`${kind}: exact private artifact survives complete simulated transfer`, {skip: !process.env.BLACKWALL_COMPONENT_DIR}, async()=>{
    const raw=new Uint8Array(readFileSync(`${process.env.BLACKWALL_COMPONENT_DIR}/${kind}.bin`));
    let current=[], blocks=[], calls=0;
    const io={async exchange(channel,packets,accept) {
      calls++;
      const first=packets[0], request=first.slice(8,-2);
      if(channel==='control') {
        const payload=Uint8Array.of(...request.slice(0,-6),26,0);
        assert.ok(accept({sid:0x80,payload})); return payload;
      }
      if(request[0]===2) {
        current=packets.slice(1).flatMap(p=>Array.from(p.slice(8)));
        blocks.push(Uint8Array.from(current.slice(0,-2)));
      }
      const payload=Uint8Array.of(request[0],0);
      assert.ok(accept({sid:0xc0,payload})); return payload;
    }};
    const session=new ComponentOtaSession(io,kind);
    const result=await session.transfer({header:raw.slice(0,128),payload:raw.slice(128)});
    assert.deepEqual(Buffer.concat(blocks.map(b=>Buffer.from(b))),Buffer.from(raw.slice(128)));
    assert.equal(blocks.at(-1).length,kind==='main-cfw'?104:1412);
    assert.equal(calls,blocks.length+5);
    assert.equal(result.readbackVerified,false);
    const corrupt=raw.slice();corrupt[140]^=1;
    const before=calls;
    await assert.rejects(()=>new ComponentOtaSession(io,kind).transfer({header:corrupt.slice(0,128),payload:corrupt.slice(128)}),/SHA256/);
    assert.equal(calls,before);
    const other=kind==='main-cfw'?'main-stock':'main-cfw';
    await assert.rejects(()=>new ComponentOtaSession(io,other).transfer({header:raw.slice(0,128),payload:raw.slice(128)}),/size/);
    assert.equal(calls,before);
  });
}
