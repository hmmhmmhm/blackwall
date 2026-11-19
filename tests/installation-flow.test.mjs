import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {prepareInstallation,executeInstallation} from '../web/installation-flow.mjs';
test('forged plan never reaches Bluetooth',async()=>{
 let calls=0;const bluetooth={requestDevice(){calls++;}};
 await assert.rejects(()=>executeInstallation({installable:true},'yes',bluetooth),/plan/);
 assert.equal(calls,0);
});
test('actual pinned file produces immutable review plan but cannot enable unverified hardware',{skip:!process.env.BLACKWALL_COMPONENT_DIR},async()=>{
 const bytes=new Uint8Array(readFileSync(`${process.env.BLACKWALL_COMPONENT_DIR}/main-cfw.bin`));
 const plan=await prepareInstallation({kind:'main-cfw',bytes,side:'left',expectedName:'Even G2_32_L_ABCDEF'});
 assert.ok(Object.isFrozen(plan));assert.equal(plan.installable,false);
 assert.equal(plan.side,'left');
 assert.throws(()=>{plan.installable=true;});
 let calls=0;
 await assert.rejects(()=>executeInstallation(plan,plan.confirmation,{requestDevice(){calls++;}}),/compatibility/);
 assert.equal(calls,0);
 await assert.rejects(()=>executeInstallation({...plan,installable:true},plan.confirmation,{}),/plan/);
});
test('both sides or mismatched advertising side cannot create plan',async()=>{
 for(const side of ['both','right'])await assert.rejects(()=>prepareInstallation({kind:'main-cfw',bytes:new Uint8Array(),side,expectedName:'Even G2_32_L_ABCDEF'}),/side/);
});
