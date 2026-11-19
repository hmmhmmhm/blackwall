import {unwrap} from './ota-packets.mjs';

// Receives one already-connected device and its resolved GATT characteristics.
// Device selection, compatibility checks and operation authorization belong to the caller.
export class GattTransport {
  #device;
  #channels;
  #busy=false;
  #closed=false;
  constructor(device, channels) { this.#device=device; this.#channels=channels; }

  async exchange(channel, packets, accept, timeout) {
    if(this.#closed) throw new Error('Transport closed; outcome may be unknown');
    if(this.#busy) throw new Error('Transport busy');
    const pair=this.#channels[channel];
    if(!pair || !Array.isArray(packets) || !packets.length
        || !packets.every(p=>p instanceof Uint8Array && p.length>=10 && p.length<=240)
        || typeof accept!=='function' || !Number.isFinite(timeout) || timeout<=0) {
      throw new Error('Invalid exchange');
    }
    if(!this.#device.gatt.connected) throw new Error('Device disconnected');
    packets=packets.map(p=>p.slice());
    this.#busy=true;
    try {
      return await new Promise((resolve,reject)=>{
        let done=false, sending=false, sent=false, response=null;
        const cleanup=()=>{
          clearTimeout(timer);
          pair.notify.removeEventListener('characteristicvaluechanged',onReply);
          this.#device.removeEventListener('gattserverdisconnected',onDisconnect);
        };
        const fail=error=>{
          if(done) return;
          done=true; this.#closed=true; cleanup(); reject(error);
        };
        const finish=()=>{
          if(done || !sent || response===null) return;
          done=true; cleanup(); resolve(response);
        };
        const onDisconnect=()=>fail(new Error('Device disconnected; no retry'));
        const onReply=event=>{
          if(done || !sending) return;
          const value=event.target.value;
          if(!(value instanceof DataView)) return;
          const reply=unwrap(new Uint8Array(value.buffer,value.byteOffset,value.byteLength));
          try {
            if(reply && accept(reply)) { response=reply.payload; finish(); }
          } catch(error) { fail(error); }
        };
        const timer=setTimeout(()=>fail(new Error('OTA reply timeout; no retry')),timeout);
        pair.notify.addEventListener('characteristicvaluechanged',onReply);
        this.#device.addEventListener('gattserverdisconnected',onDisconnect);
        const send=async()=>{
          await pair.notify.startNotifications();
          for(const packet of packets) {
            if(done) return;
            if(!this.#device.gatt.connected) { onDisconnect(); return; }
            sending=true;
            await pair.write.writeValueWithoutResponse(packet);
          }
          sent=true; finish();
        };
        send().catch(fail);
      });
    } finally { this.#busy=false; }
  }
}
