import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
test('UI reviews exact file and side, and invalidates review on target change',{skip:!process.env.BLACKWALL_COMPONENT_DIR},async()=>{
 const ids=['operation','artifact','inspect','result','side','device-name','review','plan','confirmation','install'];
 const elements=Object.fromEntries(ids.map(id=>[id,{value:'',disabled:false,textContent:'',files:[],listeners:{},addEventListener(type,fn){this.listeners[type]=fn;}}]));
 globalThis.document={querySelector:selector=>elements[selector.slice(1)]};
 try{
  await import('../web/app.mjs');
  elements.operation.value='main-cfw';elements.side.value='left';elements['device-name'].value='Even G2_32_L_ABCDEF';
  const raw=readFileSync(`${process.env.BLACKWALL_COMPONENT_DIR}/main-cfw.bin`);
  elements.artifact.files=[{size:raw.length,arrayBuffer:async()=>raw.buffer.slice(raw.byteOffset,raw.byteOffset+raw.byteLength)}];
  assert.equal(typeof elements.review.listeners.click,'function');
  await elements.review.listeners.click();
  assert.match(elements.plan.textContent,/Even G2_32_L_ABCDEF/);
  assert.match(elements.plan.textContent,/unverified/);
  assert.equal(elements.install.disabled,true);
  elements['device-name'].value='Even G2_32_R_ABCDEF';
  elements['device-name'].listeners.input();
  assert.match(elements.plan.textContent,/invalid/);
  assert.equal(elements.confirmation.value,'');
  assert.equal(elements.install.disabled,true);
 }finally{delete globalThis.document;}
});

test('UI reports a missing file in English',async()=>{
 const ids=['operation','artifact','inspect','result','side','device-name','review','plan','confirmation','install'];
 const elements=Object.fromEntries(ids.map(id=>[id,{value:'',disabled:false,textContent:'',files:[],listeners:{},addEventListener(type,fn){this.listeners[type]=fn;}}]));
 globalThis.document={querySelector:selector=>elements[selector.slice(1)]};
 try{
  await import('../web/app.mjs?missing-file-test');
  await elements.inspect.listeners.click();
  assert.equal(elements.result.textContent,'Select a file to verify.');
  await elements.review.listeners.click();
  assert.equal(elements.plan.textContent,'First select a supported single component file.');
  assert.equal(elements.install.disabled,true);
 }finally{delete globalThis.document;}
});
