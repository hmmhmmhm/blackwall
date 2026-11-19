// UUID mapping: pinned g2flash g2flash.py DATA/CTRL constants (see research docs).
const uuid=tail=>`00002760-08c2-11e1-9073-0e8ac72e${tail}`;
const services={data:{service:uuid('1001'),write:uuid('0001'),notify:uuid('0002')},control:{service:uuid('5450'),write:uuid('5401'),notify:uuid('5402')}};
let active=null;

// Must only be invoked from an explicitly authorized user gesture.
// A name is a routing hint, not authenticated identity or firmware compatibility.
export async function selectTemple(bluetooth,side,expectedName){
  if(!['left','right'].includes(side))throw new Error('Choose exactly one side');
  const match=/^(?:Even )?G2_\d+_([LR])_[0-9a-f]{6}$/i.exec(expectedName??'');
  if(!match || match[1].toUpperCase()!==(side==='left'?'L':'R'))throw new Error('Name does not identify the selected side');
  if(!bluetooth?.requestDevice)throw new Error('Web Bluetooth unavailable');
  if(active)throw new Error('A temple connection is already active');
  const token={};active=token;
  let device,owned=false,closed=false;
  const release=()=>{if(active===token)active=null;};
  const onDisconnect=()=>{closed=true;device.removeEventListener('gattserverdisconnected',onDisconnect);release();};
  const close=()=>{
    if(closed)return;
    if(owned&&device.gatt.connected)device.gatt.disconnect();
    closed=true;
    device?.removeEventListener('gattserverdisconnected',onDisconnect);
    release();
  };
  try{
    device=await bluetooth.requestDevice({filters:[{name:expectedName}],optionalServices:Object.values(services).map(s=>s.service)});
    if(device.name!==expectedName)throw new Error('Selected device identity differs from expected name');
    if(device.gatt?.connected)throw new Error('Device already connected; refusing to take over');
    if(!device.gatt)throw new Error('GATT unavailable');
    owned=true;
    device.addEventListener('gattserverdisconnected',onDisconnect);
    const server=await device.gatt.connect();
    const channels={};
    for(const [name,ids] of Object.entries(services)){
      if(closed||!server.connected)throw new Error('Device disconnected during discovery');
      const service=await server.getPrimaryService(ids.service);
      const write=await service.getCharacteristic(ids.write);
      const notify=await service.getCharacteristic(ids.notify);
      if(!write.properties.writeWithoutResponse||!notify.properties.notify)throw new Error('Required GATT properties unavailable');
      channels[name]={write,notify};
    }
    if(closed||!server.connected)throw new Error('Device disconnected during discovery');
    return Object.freeze({device,side,channels,close});
  }catch(error){close();throw error;}
}
