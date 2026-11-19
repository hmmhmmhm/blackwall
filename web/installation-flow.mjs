import {inspectArtifact} from './artifact-catalog.mjs';
import {selectTemple} from './temple-connection.mjs';
import {GattTransport} from './gatt-transport.mjs';
import {ComponentOtaSession} from './component-ota-session.mjs';

const prepared=new WeakMap();
export async function prepareInstallation({kind,bytes,side,expectedName}){
  const match=/^(?:Even )?G2_\d+_([LR])_[0-9a-f]{6}$/i.exec(expectedName??'');
  if(!['left','right'].includes(side)||!match||match[1].toUpperCase()!==(side==='left'?'L':'R')){
    throw new Error('Exactly one matching side is required');
  }
  if(!(bytes instanceof Uint8Array))throw new Error('Expected component bytes');
  const snapshot=bytes.slice();
  const report=await inspectArtifact(kind,snapshot);
  const confirmation=`${kind} ${side} ${expectedName} ${report.sha256}`;
  const plan=Object.freeze({...report,side,expectedName,confirmation});
  prepared.set(plan,snapshot);
  return plan;
}

// Current catalog has no installable profile. Do not replace this with a UI checkbox.
// An approved compatibility profile and hardware-specific evidence are prerequisites.
export async function executeInstallation(plan,confirmation,bluetooth){
  const bytes=prepared.get(plan);
  if(!bytes)throw new Error('Unknown or consumed installation plan');
  if(!plan.installable)throw new Error('Hardware compatibility is unverified; installation blocked');
  if(confirmation!==plan.confirmation)throw new Error('Confirmation does not match this exact operation');
  prepared.delete(plan);
  const connection=await selectTemple(bluetooth,plan.side,plan.expectedName);
  try{
    const session=new ComponentOtaSession(new GattTransport(connection.device,connection.channels),plan.kind);
    const result=await session.transfer({header:bytes.slice(0,128),payload:bytes.slice(128)});
    return Object.freeze({...result,kind:plan.kind,side:plan.side,sha256:plan.sha256});
  }finally{
    connection.close();
  }
}
