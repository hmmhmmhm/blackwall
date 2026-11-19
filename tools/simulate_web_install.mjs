// Host-only driver for the browser-compatible virtual transport. Proprietary output stays outside Git.
import {readFileSync,writeFileSync,mkdirSync,realpathSync} from 'node:fs';
import {resolve,dirname,join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
import {VirtualTemple,installVirtual} from '../web/virtual-ota-storage.mjs';
const [candidate,components,destination]=process.argv.slice(2);
if(!candidate||!components||!destination||process.argv.length!==5)throw new Error('Usage: node tools/simulate_web_install.mjs <private-boot24-candidate> <components> <new-private-output>');
const root=realpathSync(fileURLToPath(new URL('..',import.meta.url)));
const output=join(realpathSync(dirname(resolve(destination))),resolve(destination).split('/').at(-1));
// Output must be outside the repository even when a parent path is a symlink.
if(output===root||output.startsWith(root+'/'))throw new Error('Firmware output must remain outside Git');
mkdirSync(output,{mode:0o700});
const bytes=kind=>new Uint8Array(readFileSync(kind==='boot-24'?join(candidate,'boot-2.4-research-component.bin'):join(components,kind+'.bin')));
const boot=bytes('boot-24'),stock=bytes('main-stock'),cfw=bytes('main-cfw');
const hash=data=>createHash('sha256').update(data).digest('hex');
const left=new VirtualTemple('left'),right=new VirtualTemple('right'),snapshots=[];
const rightBefore=right.read(0x410000,0x3e8000);
async function install(kind,fault){return installVirtual(left,{side:'left',kind,bytes:kind==='boot-24'?boot:kind==='main-stock'?stock:cfw,fault});}
function snapshot(name,temple=left){
  const raw=temple.read(0x410000,0x3e8000),file=name+'.mram.bin';
  writeFileSync(join(output,file),raw,{mode:0o600});
  snapshots.push({name,file,bytes:raw.length,sha256:hash(raw),state:temple.state,sessionState:temple.sessionState});
}
await install('boot-24');await install('main-stock');
const installedBoot=left.read(0x410000,0x28000);
await install('main-cfw');assert.deepEqual(left.read(0x438000,cfw.length-160),cfw.slice(160));snapshot('cfw');
await assert.rejects(()=>install('main-stock',{applyBytes:4096}),/interrupted/);snapshot('interrupted-stock');
assert.notDeepEqual(left.read(0x438000,stock.length-160),stock.slice(160));
await install('main-stock');assert.deepEqual(left.read(0x438000,stock.length-160),stock.slice(160));snapshot('restored-stock');
assert.deepEqual(left.read(0x410000,0x28000),installedBoot);assert.deepEqual(right.read(0x410000,0x3e8000),rightBefore);
const broken=new VirtualTemple('left');
await assert.rejects(()=>installVirtual(broken,{side:'left',kind:'boot-24',bytes:boot,fault:{applyBytes:4096}}),/interrupted/);snapshot('interrupted-boot',broken);
const tail=left.read(0x438000+stock.length-160,cfw.length-stock.length);
assert.deepEqual(tail,cfw.slice(stock.length));
writeFileSync(join(output,'transcript.json'),JSON.stringify(left.log,null,2)+'\n',{mode:0o600});
const report={model:'virtual-staging-then-in-place-apply-v1',side:'left',snapshots,inputs:{boot24:hash(boot),stock:hash(stock),cfw:hash(cfw)},mainBodyRestored:true,fullStockRestored:false,retainedCfwTailBytes:tail.length,bootUnchanged:true,otherTempleUnchanged:true,hardwareAccessed:false,bootVerified:false,limitations:['OTA staging/application timing is a synthetic fault model','Main preamble is metadata; raw main begins at component byte160','Stock restoration preserves the prior longer image tail','ARM execution must be verified separately']};
writeFileSync(join(output,'report.json'),JSON.stringify(report,null,2)+'\n',{mode:0o600});
console.log(JSON.stringify({snapshots:snapshots.length,mainBodyRestored:true,fullStockRestored:false,hardwareAccessed:false}));
