import test from 'node:test';import assert from 'node:assert/strict';import {readFileSync} from 'node:fs';
test('virtual browser UI uses real OTA and RAM readback, including failure on other side',{skip:!process.env.BLACKWALL_COMPONENT_DIR},async()=>{
 const ids=['virtual-side','virtual-kind','virtual-artifact','virtual-fault','virtual-install','virtual-result','virtual-summary'];
 const elements=Object.fromEntries(ids.map(id=>[id,{value:'',disabled:false,textContent:'',files:[],listeners:{},addEventListener(type,fn){this.listeners[type]=fn;}}]));
 globalThis.document={querySelector:s=>elements[s.slice(1)]};
 try{
  await import('../web/virtual-app.mjs').catch(error=>assert.fail('Virtual UI module must exist: '+error.message));
  const raw=readFileSync(`${process.env.BLACKWALL_COMPONENT_DIR}/main-cfw.bin`);
  elements['virtual-side'].value='left';elements['virtual-kind'].value='main-cfw';elements['virtual-fault'].value='none';
  elements['virtual-artifact'].files=[{size:raw.length,arrayBuffer:async()=>raw.buffer.slice(raw.byteOffset,raw.byteOffset+raw.byteLength)}];
  await elements['virtual-install'].listeners.click();
  assert.match(elements['virtual-result'].textContent,/RAM readback matches/);
  assert.match(elements['virtual-result'].textContent,/Normal ARM boot not verified/);
  assert.match(elements['virtual-summary'].textContent,/left: applied-unverified/);
  assert.match(elements['virtual-summary'].textContent,/right: empty/);
  elements['virtual-side'].value='right';elements['virtual-fault'].value='apply';
  await elements['virtual-install'].listeners.click();
  assert.match(elements['virtual-result'].textContent,/apply-interrupted/);
  assert.match(elements['virtual-summary'].textContent,/left: applied-unverified/);
  assert.match(elements['virtual-summary'].textContent,/right: apply-interrupted/);
  assert.equal(elements['virtual-install'].disabled,false);
 }finally{delete globalThis.document;}
});

test('virtual browser UI reports invalid input in English',async()=>{
 const ids=['virtual-side','virtual-kind','virtual-artifact','virtual-fault','virtual-install','virtual-result','virtual-summary'];
 const elements=Object.fromEntries(ids.map(id=>[id,{value:'',disabled:false,textContent:'',files:[],listeners:{},addEventListener(type,fn){this.listeners[type]=fn;}}]));
 globalThis.document={querySelector:s=>elements[s.slice(1)]};
 try{
  await import('../web/virtual-app.mjs?invalid-input-test');
  await elements['virtual-install'].listeners.click();
  assert.equal(elements['virtual-result'].textContent,'Select a supported component file.');
  elements['virtual-artifact'].files=[{size:1}];
  await elements['virtual-install'].listeners.click();
  assert.equal(elements['virtual-result'].textContent,'Check the virtual target and fault condition.');
 }finally{delete globalThis.document;}
});
