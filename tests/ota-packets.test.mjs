import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {frames, unwrap} from '../web/ota-packets.mjs';

const fixtures = JSON.parse(readFileSync(new URL('./fixtures/ota-packets.json', import.meta.url)));
for (const fixture of fixtures) {
  test(`matches upstream Python frames for ${fixture.length} bytes`, () => {
    const payload = Uint8Array.from({length: fixture.length}, (_, i) => i % 256);
    assert.deepEqual(frames(fixture.sid, payload, fixture.sequence).map(p => Buffer.from(p).toString('hex')), fixture.packets);
  });
}
test('valid reply is decoded, corruption and fragmented replies are rejected', () => {
  const reply = frames(0xc0, Uint8Array.of(2,0), 4)[0];
  reply[1] = 0x12;
  assert.deepEqual(unwrap(reply), {sid: 0xc0, sequence: 4, payload: Uint8Array.of(2,0)});
  for (const index of [0,1,3,4,5,7,8,10]) {
    const damaged = reply.slice(); damaged[index] ^= 1;
    assert.equal(unwrap(damaged), null);
  }
});
test('invalid headers and excessive fragment count fail before allocation', () => {
  for (const value of [-1,256,1.5,NaN]) {
    assert.throws(() => frames(value, new Uint8Array(), 1));
    assert.throws(() => frames(1, new Uint8Array(), value));
  }
  assert.throws(() => frames(1, new Uint8Array(59159), 1));
  assert.throws(() => frames(1, [1,2], 1));
  assert.equal(unwrap(new Uint8Array(9)), null);
});
