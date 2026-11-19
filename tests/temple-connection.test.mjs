import test from 'node:test';
import assert from 'node:assert/strict';
import {selectTemple} from '../web/temple-connection.mjs';
const name='Even G2_32_L_ABCDEF';
function fixture(selected=name,fail=false){
 const device=new EventTarget();device.name=selected;
 const counts={connect:0,disconnect:0,chooser:0};
 device.gatt={connected:false,async connect(){counts.connect++;this.connected=true;return this;},disconnect(){counts.disconnect++;this.connected=false;device.dispatchEvent(new Event('gattserverdisconnected'));},async getPrimaryService(){return {async getCharacteristic(uuid){if(fail)throw new Error('missing service');return {uuid,properties:{writeWithoutResponse:true,notify:true}};}};}};
 const bluetooth={async requestDevice(options){counts.chooser++;assert.deepEqual(options.filters,[{name}]);assert.equal(options.optionalServices.length,2);return device;}};
 return {bluetooth,device,counts};
}
test('single exact-name left temple connects and closes',async()=>{const f=fixture();const c=await selectTemple(f.bluetooth,'left',name);assert.equal(c.side,'left');assert.equal(f.counts.connect,1);assert.notEqual(c.channels.data.write.uuid,c.channels.control.write.uuid);c.close();assert.equal(f.counts.disconnect,1);});
test('wrong side and unrecognized names rejected before chooser',async()=>{const f=fixture();for(const [side,n] of [['right',name],['both',name],['left','other']])await assert.rejects(()=>selectTemple(f.bluetooth,side,n));assert.equal(f.counts.chooser,0);});
test('unexpected chooser device rejected before connect',async()=>{const f=fixture('Even G2_32_R_ABCDEF');await assert.rejects(()=>selectTemple(f.bluetooth,'left',name),/identity/);assert.equal(f.counts.connect,0);});
test('discovery failure disconnects owned connection and frees session',async()=>{const f=fixture(name,true);await assert.rejects(()=>selectTemple(f.bluetooth,'left',name),/missing service/);assert.equal(f.counts.disconnect,1);const next=fixture();(await selectTemple(next.bluetooth,'left',name)).close();});
test('second chooser refused while a temple is owned',async()=>{const f=fixture();const c=await selectTemple(f.bluetooth,'left',name);const next=fixture();await assert.rejects(()=>selectTemple(next.bluetooth,'left',name),/active/);assert.equal(next.counts.chooser,0);c.close();});
