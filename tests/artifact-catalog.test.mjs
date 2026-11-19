import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {inspectArtifact} from '../web/artifact-catalog.mjs';
for(const [kind,path] of [
  ['main-cfw',process.env.BLACKWALL_COMPONENT_DIR&&`${process.env.BLACKWALL_COMPONENT_DIR}/main-cfw.bin`],
  ['main-stock',process.env.BLACKWALL_COMPONENT_DIR&&`${process.env.BLACKWALL_COMPONENT_DIR}/main-stock.bin`],
  ['boot',process.env.BLACKWALL_BOOT_COMPONENT],
  ['boot-24',process.env.BLACKWALL_BOOT24_COMPONENT],
]) {
  test(`${kind} exact file accepted for inspection; corruption and wrong operation rejected`,{skip:!path},async()=>{
    const bytes=new Uint8Array(readFileSync(path));
    const report=await inspectArtifact(kind,bytes);
    assert.equal(report.kind,kind);assert.equal(report.installable,false);
    assert.equal(report.payloadBytes,bytes.length-128);
    const broken=bytes.slice();broken[broken.length-1]^=1;
    await assert.rejects(()=>inspectArtifact(kind,broken),/SHA256/);
    await assert.rejects(()=>inspectArtifact(kind==='boot'?'main-cfw':'boot',bytes));
  });
}
test('invalid kind and oversized or truncated input rejected',async()=>{
  await assert.rejects(()=>inspectArtifact('anything',new Uint8Array(128)),/operation/);
  await assert.rejects(()=>inspectArtifact('boot',new Uint8Array(10)),/size/);
  await assert.rejects(()=>inspectArtifact('boot',new Uint8Array(5000000)),/size/);
});

test('2.4 recovery component is inspection-only and cannot be confused with 2.3', {skip:!process.env.BLACKWALL_BOOT24_COMPONENT||!process.env.BLACKWALL_BOOT_COMPONENT},async()=>{
  const bytes=new Uint8Array(readFileSync(process.env.BLACKWALL_BOOT24_COMPONENT));
  const report=await inspectArtifact('boot-24',bytes);
  assert.equal(report.installable,false);
  await assert.rejects(()=>inspectArtifact('boot',bytes),/SHA256/);
  await assert.rejects(()=>inspectArtifact('boot-24',new Uint8Array(readFileSync(process.env.BLACKWALL_BOOT_COMPONENT))),/SHA256/);
  const {prepareInstallation,executeInstallation}=await import('../web/installation-flow.mjs');
  const plan=await prepareInstallation({kind:'boot-24',bytes,side:'left',expectedName:'G2_123_L_abcdef'});
  let calls=0;
  await assert.rejects(()=>executeInstallation(plan,plan.confirmation,{async requestDevice(){calls++;}}),/blocked/);
  assert.equal(calls,0);
});

for(const [kind,path] of [['boot',process.env.BLACKWALL_BOOT_COMPONENT],['boot-24',process.env.BLACKWALL_BOOT24_COMPONENT]]) {
test(`${kind}: direct session rejects modified pinned payload before authentication`,{skip:!path},async()=>{
  const {ComponentOtaSession}=await import('../web/component-ota-session.mjs');
  const bytes=new Uint8Array(readFileSync(path));
  bytes[200]^=1;
  let calls=0;
  const io={async exchange(){calls++;throw new Error('transport reached');}};
  await assert.rejects(()=>new ComponentOtaSession(io,kind).transfer({header:bytes.slice(0,128),payload:bytes.slice(128)}),/SHA256/);
  assert.equal(calls,0);
});

}
