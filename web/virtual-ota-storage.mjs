// Simulator-only model. No Web Bluetooth, hardware transport, filesystem, or durable writes.
import {ComponentOtaSession} from './component-ota-session.mjs';
import {inspectArtifact} from './artifact-catalog.mjs';
const BASE=0x410000, MAIN=0x438000, END=0x7f8000;
function checksum(bytes){
  let crc=65535;
  for(const value of bytes){crc^=value<<8;for(let bit=0;bit<8;bit++)crc=((crc<<1)^((crc&32768)?0x1021:0))&65535;}
  return crc;
}
function decode(packets){
  const messages=[];
  for(let i=0;i<packets.length;){
    const first=packets[i],count=first[4],sid=first[6],sequence=first[2],parts=[];
    if(!count||i+count>packets.length)throw new Error('Incomplete virtual wire message');
    for(let n=0;n<count;n++){
      const frame=packets[i+n];
      if(!(frame instanceof Uint8Array)||frame.length<10||frame.length>240||frame[0]!==170||frame[1]!==33||frame[2]!==sequence||frame[3]!==frame.length-8||frame[4]!==count||frame[5]!==n+1||frame[6]!==sid||frame[7]!==0)throw new Error('Invalid virtual wire fragment');
      parts.push(...frame.slice(8));
    }
    const payload=Uint8Array.from(parts.slice(0,-2));
    if(parts.length<2||checksum(payload)!==(parts.at(-2)|(parts.at(-1)<<8)))throw new Error('Virtual wire CRC mismatch');
    messages.push({sid,sequence,payload});i+=count;
  }
  return messages;
}
export class VirtualTemple {
  #side;#ram=new Uint8Array(END-BASE).fill(255);#active=false;#state='empty';#log=[];#sessionState=null;
  constructor(side){if(!['left','right'].includes(side))throw new Error('One virtual side required');this.#side=side;}
  get side(){return this.#side;}
  get state(){return this.#state;}
  get sessionState(){return this.#sessionState;}
  get log(){return this.#log.map(entry=>({...entry}));}
  read(address,length){
    if(!Number.isSafeInteger(address)||!Number.isSafeInteger(length)||length<0||address<BASE||address+length>END)throw new Error('Virtual MRAM range rejected');
    return this.#ram.slice(address-BASE,address-BASE+length);
  }
  async install({side,kind,bytes,fault={}}){
    if(side!==this.#side)throw new Error('Virtual side mismatch');
    if(!['boot-24','main-cfw','main-stock'].includes(kind))throw new Error('Virtual research profile version mismatch');
    if(this.#active)throw new Error('Virtual temple busy');
    for(const key of Object.keys(fault))if(!['disconnectBlock','corruptBlock','applyBytes','loseEndAck'].includes(key))throw new Error('Unknown virtual fault');
    for(const key of ['disconnectBlock','corruptBlock','applyBytes'])if(key in fault&&(!Number.isSafeInteger(fault[key])||fault[key]<0))throw new Error('Invalid virtual fault');
    if('loseEndAck' in fault&&typeof fault.loseEndAck!=='boolean')throw new Error('Invalid virtual fault');
    this.#active=true;fault={...fault};let session;
    try{
      if(!(bytes instanceof Uint8Array))throw new Error('Virtual component bytes required');
      bytes=bytes.slice();await inspectArtifact(kind,bytes);
      const raw=bytes.slice(kind==='boot-24'?128:160),destination=kind==='boot-24'?BASE:MAIN;
      if(destination+raw.length>(kind==='boot-24'?MAIN:END))throw new Error('Virtual component crosses partition');
      if('applyBytes' in fault&&fault.applyBytes>=raw.length)throw new Error('Apply interruption must occur inside image');
      let phase='auth',header=null,blocks=[],received=0,block=0;
      this.#log.push({event:'session',kind,side});
      const io={exchange:async(channel,packets,accept)=>{
        const messages=decode(packets);let reply,sid;
        if(channel==='control'){
          if(!['auth','ended'].includes(phase)||messages.length!==1||messages[0].sid!==128)throw new Error('Virtual authentication order rejected');
          const {payload,sequence}=messages[0],magic=sequence<128?[sequence]:[(sequence&127)|128,sequence>>7];
          if(payload.toString()!==Uint8Array.of(8,4,16,...magic,26,4,8,1,16,4).toString())throw new Error('Virtual authentication request rejected');
          reply=Uint8Array.of(8,4,16,...magic,26,0);sid=128;if(phase==='auth')phase='begin';
        }else if(channel==='data'){
          const command=messages[0];if(command.sid!==192||!command.payload.length)throw new Error('Virtual command rejected');
          const op=command.payload[0];sid=192;
          if(op===0&&phase==='begin'&&messages.length===1&&command.payload.length===1){phase='header';this.#state='receiving-header';}
          else if(op===1&&phase==='header'&&messages.length===1&&command.payload.length===129){header=command.payload.slice(1);phase='blocks';this.#state='staging';}
          else if(op===2&&phase==='blocks'&&command.payload.length===1&&messages.length===2&&messages[1].sid===193&&messages[1].sequence===command.sequence){
            if(block===fault.disconnectBlock){this.#state='staging-interrupted';throw new Error('Virtual disconnect; no retry');}
            let data=messages[1].payload;
            if(!data.length||data.length>4096||received+data.length>bytes.length-128)throw new Error('Virtual block bounds rejected');
            if(block===fault.corruptBlock){
              const corrupted=packets.map(p=>p.slice());corrupted.at(-1)[8]^=1;decode(corrupted);
            }
            blocks.push(data);received+=data.length;this.#log.push({event:'block',index:block,bytes:data.length});block++;
          }else if(op===3&&phase==='blocks'&&command.payload.length===1&&messages.length===1){
            const staged=new Uint8Array(128+received);staged.set(header);let offset=128;
            for(const data of blocks){staged.set(data,offset);offset+=data.length;}
            await inspectArtifact(kind,staged);
            const applied=staged.subarray(kind==='boot-24'?128:160);
            const count=fault.applyBytes??applied.length;
            this.#ram.set(applied.subarray(0,count),destination-BASE);
            this.#log.push({event:'apply',address:destination,bytes:count,kind});
            if('applyBytes' in fault){this.#state='apply-interrupted';throw new Error('Virtual apply interrupted; partial image retained');}
            phase='ended';this.#state='applied-unverified';
            if(fault.loseEndAck){this.#state='applied-acknowledgement-lost';throw new Error('Virtual END acknowledgement lost');}
          }else throw new Error('Virtual OTA phase or opcode rejected');
          reply=Uint8Array.of(op,0);
        }else throw new Error('Unknown virtual channel');
        if(!accept({sid,payload:reply}))throw new Error('Virtual response did not match session');
        return reply;
      }};
      session=new ComponentOtaSession(io,kind);
      return await session.transfer({header:bytes.slice(0,128),payload:bytes.slice(128)});
    }catch(error){
      if(session&&['receiving-header','staging'].includes(this.#state))this.#state='staging-rejected';
      throw error;
    }finally{this.#active=false;if(session)this.#sessionState=session.state;}
  }
}
export async function installVirtual(temple,operation){
  if(!(temple instanceof VirtualTemple))throw new Error('Simulator-only temple required');
  return temple.install(operation);
}
