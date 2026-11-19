import {VirtualTemple,installVirtual} from './virtual-ota-storage.mjs';
const ids=['virtual-side','virtual-kind','virtual-artifact','virtual-fault','virtual-install','virtual-result','virtual-summary'];
const [side,kind,file,fault,button,result,summary]=ids.map(id=>document.querySelector('#'+id));
const temples={left:new VirtualTemple('left'),right:new VirtualTemple('right')};
function refresh(){summary.textContent=Object.entries(temples).map(([side,t])=>`${side}: ${t.state} · OTA ${t.sessionState??'idle'}`).join('\n');}
refresh();
button.addEventListener('click',async()=>{
 const selected=file.files[0],target=side.value,operation=kind.value;
 if(!selected||selected.size>4000000){result.textContent='Select a supported component file.';return;}
 const faults={none:{},disconnect:{disconnectBlock:1},corrupt:{corruptBlock:0},apply:{applyBytes:4096},ack:{loseEndAck:true}};
 if(!Object.hasOwn(faults,fault.value)||!Object.hasOwn(temples,target)){result.textContent='Check the virtual target and fault condition.';return;}
 const options=faults[fault.value];
 for(const e of [side,kind,file,fault,button])e.disabled=true;
 result.textContent='Running local virtual OTA…';
 try{
  const bytes=new Uint8Array(await selected.arrayBuffer());
  await installVirtual(temples[target],{side:target,kind:operation,bytes,fault:options});
  const expected=bytes.subarray(operation==='boot-24'?128:160),actual=temples[target].read(operation==='boot-24'?0x410000:0x438000,expected.length);
  if(!expected.every((b,i)=>actual[i]===b))throw new Error('Virtual RAM readback mismatch');
  const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',actual)),v=>v.toString(16).padStart(2,'0')).join('');
  result.textContent=`${target} · ${operation}\nRAM readback matches · ${actual.length} bytes\nSHA256 ${hash}\nNormal ARM boot not verified · physical device installation compatibility unconfirmed\nRestoring the stock main body is not a full stock restoration of boot and remaining regions.`;
 }catch(error){result.textContent=`Virtual operation stopped: ${error.message}\n${target}: ${temples[target].state} · OTA ${temples[target].sessionState??'idle'}\nNo automatic retry or stock restoration is performed.`;}
 finally{refresh();for(const e of [side,kind,file,fault,button])e.disabled=false;}
});
