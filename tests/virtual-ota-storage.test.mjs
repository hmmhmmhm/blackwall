import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const base=process.env.BLACKWALL_COMPONENT_DIR;
const bootPath=process.env.BLACKWALL_BOOT24_COMPONENT;
const component=kind=>new Uint8Array(readFileSync(kind==='boot-24'?bootPath:`${base}/${kind}.bin`));
async function implementation(){
  const module=await import('../web/virtual-ota-storage.mjs').catch(()=>null);
  assert.ok(module?.VirtualTemple,'A virtual temple must connect the real OTA session to address-bounded RAM storage');
  return module;
}
const check=(name,fn)=>test(name,{skip:!base||!bootPath},fn);
check('real OTA installs CFW then restores stock main without changing boot or other temple',async()=>{
  const {VirtualTemple,installVirtual}=await implementation();
  const left=new VirtualTemple('left'),right=new VirtualTemple('right');
  await installVirtual(left,{side:'left',kind:'boot-24',bytes:component('boot-24')});
  const boot=left.read(0x410000,0x28000),other=right.read(0x410000,0x3e8000);
  const cfw=component('main-cfw');
  const result=await installVirtual(left,{side:'left',kind:'main-cfw',bytes:cfw});
  assert.equal(result.readbackVerified,false);
  assert.deepEqual(left.read(0x438000,cfw.length-160),cfw.slice(160));
  assert.deepEqual(left.read(0x410000,0x28000),boot);
  const stock=component('main-stock');
  await installVirtual(left,{side:'left',kind:'main-stock',bytes:stock});
  assert.deepEqual(left.read(0x438000,stock.length-160),stock.slice(160));
  assert.deepEqual(left.read(0x410000,0x28000),boot);
  assert.deepEqual(right.read(0x410000,0x3e8000),other);
  assert.equal(left.state,'applied-unverified');
});
check('disconnect before END leaves modeled staging only, no retries or active image changes',async()=>{
  const {VirtualTemple,installVirtual}=await implementation();const temple=new VirtualTemple('left');
  const before=temple.read(0x410000,0x3e8000);
  await assert.rejects(()=>installVirtual(temple,{side:'left',kind:'main-cfw',bytes:component('main-cfw'),fault:{disconnectBlock:1}}),/disconnect/i);
  assert.deepEqual(temple.read(0x410000,0x3e8000),before);
  assert.equal(temple.state,'staging-interrupted');
  assert.equal(temple.log.filter(x=>x.event==='block').length,1);
});
check('interrupted in-place apply remains damaged until a separate explicit stock transfer',async()=>{
  const {VirtualTemple,installVirtual}=await implementation();const temple=new VirtualTemple('left');
  const stock=component('main-stock'),cfw=component('main-cfw');
  await installVirtual(temple,{side:'left',kind:'main-stock',bytes:stock});
  await assert.rejects(()=>installVirtual(temple,{side:'left',kind:'main-cfw',bytes:cfw,fault:{applyBytes:4096}}),/interrupt/i);
  assert.equal(temple.state,'apply-interrupted');
  const damaged=temple.read(0x438000,stock.length-160);
  assert.notDeepEqual(damaged,stock.slice(160));
  assert.deepEqual(damaged.slice(0,4096),cfw.slice(160,4256));
  await installVirtual(temple,{side:'left',kind:'main-stock',bytes:stock});
  assert.deepEqual(temple.read(0x438000,stock.length-160),stock.slice(160));
});
check('wire corruption and side/version mismatch cannot write RAM',async()=>{
  const {VirtualTemple,installVirtual}=await implementation();const temple=new VirtualTemple('left');
  for(const change of [{side:'right'},{kind:'boot',bytes:component('boot-24')},{fault:{corruptBlock:0}}]){
    const before=temple.read(0x410000,0x3e8000);
    await assert.rejects(()=>installVirtual(temple,{side:'left',kind:'main-cfw',bytes:component('main-cfw'),...change}));
    assert.deepEqual(temple.read(0x410000,0x3e8000),before);
  }
});
check('lost END acknowledgement preserves applied bytes but reports unknown outcome',async()=>{
  const {VirtualTemple,installVirtual}=await implementation();const temple=new VirtualTemple('left'),cfw=component('main-cfw');
  await assert.rejects(()=>installVirtual(temple,{side:'left',kind:'main-cfw',bytes:cfw,fault:{loseEndAck:true}}),/acknowledgement/i);
  assert.equal(temple.state,'applied-acknowledgement-lost');
  assert.deepEqual(temple.read(0x438000,cfw.length-160),cfw.slice(160));
});
check('boot interruption, busy operation and RAM read bounds stay explicit',async()=>{
  const {VirtualTemple,installVirtual}=await implementation();const temple=new VirtualTemple('left');
  const boot=component('boot-24');
  await assert.rejects(()=>installVirtual(temple,{side:'left',kind:'boot-24',bytes:boot,fault:{applyBytes:4096}}),/interrupt/i);
  assert.deepEqual(temple.read(0x410000,4096),boot.slice(128,4224));
  assert.ok(temple.read(0x411000,4096).every(v=>v===255));
  assert.ok(temple.read(0x438000,4096).every(v=>v===255));
  const first=installVirtual(temple,{side:'left',kind:'main-stock',bytes:component('main-stock')});
  await assert.rejects(()=>installVirtual(temple,{side:'left',kind:'main-cfw',bytes:component('main-cfw')}),/busy/);
  await first;
  for(const [address,length] of [[0x40ffff,1],[0x7f8000,1],[0x410000,-1],[0x410000,Infinity]])assert.throws(()=>temple.read(address,length),/range/);
  const copy=temple.read(0x410000,1);copy[0]^=255;
  assert.notEqual(temple.read(0x410000,1)[0],copy[0]);
});
check('corrupted wire ends the receiving state without writing or retrying',async()=>{
  const {VirtualTemple,installVirtual}=await implementation();const temple=new VirtualTemple('left');
  await assert.rejects(()=>installVirtual(temple,{side:'left',kind:'main-cfw',bytes:component('main-cfw'),fault:{corruptBlock:0}}),/CRC/);
  assert.equal(temple.state,'staging-rejected');
  assert.equal(temple.sessionState,'outcome-unknown');
  assert.equal(temple.log.filter(v=>v.event==='apply').length,0);
});
check('offline driver exports installed bytes and damaged states for ARM verification',async()=>{
  const {spawnSync}=await import('node:child_process');
  const {mkdtempSync,rmSync}=await import('node:fs');
  const {tmpdir}=await import('node:os');const {join,dirname}=await import('node:path');
  const directory=mkdtempSync(join(tmpdir(),'blackwall-virtual-'));
  try{
    const result=spawnSync(process.execPath,['tools/simulate_web_install.mjs',dirname(bootPath),base,join(directory,'run')],{encoding:'utf8'});
    assert.equal(result.status,0,result.stderr);
    const report=JSON.parse(readFileSync(join(directory,'run/report.json')));
    assert.equal(report.hardwareAccessed,false);assert.equal(report.fullStockRestored,false);
    assert.equal(report.snapshots.length,4);
    const image=new Uint8Array(readFileSync(join(directory,'run/cfw.mram.bin')));
    assert.deepEqual(image.slice(0x28000,0x28000+component('main-cfw').length-160),component('main-cfw').slice(160));
  }finally{rmSync(directory,{recursive:true,force:true});}
});
