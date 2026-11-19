// MIT protocol adaptation; see NOTICE.md. No device discovery or connection here.
import {frames} from './ota-packets.mjs';
import {inspectArtifact} from './artifact-catalog.mjs';

export class ComponentOtaSession {
  #io;
  #state = 'idle';
  #sequence = 0;
  #kind;
  constructor(transport, kind = 'boot') {
    if(!['boot','boot-24','main-cfw','main-stock'].includes(kind)) throw new Error('Unknown component operation');
    this.#io = transport; this.#kind=kind;
  }
  get state() { return this.#state; }
  #next() { this.#sequence = (this.#sequence + 1) & 255; return this.#sequence; }

  async #authenticate() {
    const magic = this.#next();
    const prefix = [8,4,16,...(magic < 128 ? [magic] : [(magic & 127)|128, magic >> 7])];
    const request = Uint8Array.of(...prefix,26,4,8,1,16,4);
    const reply = await this.#io.exchange('control', frames(0x80,request,magic),
      r => r.sid === 0x80 && prefix.every((b,i)=>r.payload[i]===b), 10000);
    if(reply.length !== prefix.length + 2 || reply.at(-2)!==26 || reply.at(-1)!==0) {
      throw new Error('Authentication rejected');
    }
  }

  async #command(operation, data = new Uint8Array()) {
    const reply = await this.#io.exchange('data',
      frames(0xc0, Uint8Array.of(operation,...data),this.#next()),
      r => r.payload.length >= 2 && r.payload[0] === operation,
      operation === 3 ? 30000 : 10000);
    const status = reply[1];
    if(!(operation === 3 ? [0,8,9] : [0]).includes(status)) {
      throw new Error(`OTA operation ${operation} rejected: ${status}`);
    }
    return status;
  }

  // Caller must validate device compatibility and specific operation approval.
  // Transport.exchange must register notifications before sending, enforce timeout,
  // discard stale replies, and never retry writes. This primitive is not an installer.
  async transfer({header, payload}) {
    if(this.#state !== 'idle') throw new Error('OTA session is single-use');
    if(!(header instanceof Uint8Array) || header.length !== 128
        || !(payload instanceof Uint8Array) || !payload.length
        || payload.length > 0x7f8000-0x438000+32) throw new Error('Invalid component bounds');
    const boot=this.#kind==='boot'||this.#kind==='boot-24';
    if(boot && (payload.length % 4096 || payload.length>0x28000)) throw new Error('Invalid boot component bounds');
    const view = new DataView(header.buffer,header.byteOffset,header.byteLength);
    const name = new TextDecoder().decode(header.subarray(48)).split('\0')[0];
    if(view.getUint32(8,true)!==payload.length || view.getUint32(36,true)!==(boot?1:0)
        || name!==(boot?'ota/s200_bootloader.bin':'ota/s200_firmware_ota.bin')) throw new Error('Unexpected component type');
    // Snapshot before the first await so caller mutation cannot change bytes in flight.
    header=header.slice(); payload=payload.slice();
    this.#state='validating';
    try {
      const component=new Uint8Array(128+payload.length);
      component.set(header); component.set(payload,128);
      await inspectArtifact(this.#kind,component);
      if(!boot) {
        const pre=new DataView(payload.buffer,payload.byteOffset,payload.byteLength);
        if((pre.getUint32(0,true)&0xffffff)!==payload.length || pre.getUint32(20,true)!==0x438000) {
          throw new Error('Main preamble size/destination mismatch');
        }
      }
      this.#state='transferring';
      await this.#authenticate();
      await this.#command(0);
      await this.#command(1,header);
      for(let offset=0;offset<payload.length;offset+=4096) {
        const sequence=this.#next();
        const packets=[...frames(0xc0,Uint8Array.of(2),sequence),
          ...frames(0xc1,payload.subarray(offset,offset+4096),sequence)];
        const reply=await this.#io.exchange('data',packets,
          r=>r.payload.length>=2 && r.payload[0]===2,4000);
        if(reply[1]!==0) throw new Error(`Block rejected: ${reply[1]}`);
      }
      const endStatus=await this.#command(3);
      await this.#authenticate();
      this.#state='awaiting-verification';
      return {endStatus,readbackVerified:false};
    } catch(error) {
      this.#state=this.#state==='validating'?'rejected':'outcome-unknown';
      throw error;
    }
  }
}
