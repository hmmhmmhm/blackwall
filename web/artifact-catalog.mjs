const catalog = Object.freeze({
  'main-cfw': Object.freeze({label:'Faceclaw/38 main',bytes:3829992,sha256:'84bb56c16774e75158adb14b1a5429a24ee005a76b22df5b5f498998b82fb01a',type:0}),
  'main-stock': Object.freeze({label:'Restore stock 2.4.0.24 main',bytes:3700228,sha256:'320aa240affe49c2e2a0b65c284b20a05ad64423fe6a275c34b22d99c58310db',type:0}),
  boot: Object.freeze({label:'2.3.2.14 dedicated-key recovery candidate',bytes:159872,sha256:'08cdf7373de1fb60b2c2efa0afd5bec9702c0fa85ec63026b1fc1d19561b8368',type:1}),
  'boot-24': Object.freeze({label:'2.4.0.24 research recovery candidate — inspection only',bytes:159872,sha256:'b95254ec99b140e7b2cf41a66ed86ebd5375bb7f80a1d97faaf5fdbad4e04b96',type:1}),
});
export async function inspectArtifact(kind, bytes) {
  if(!Object.hasOwn(catalog,kind)) throw new Error('Unknown operation');
  const entry=catalog[kind];
  if(!(bytes instanceof Uint8Array)||bytes.length!==entry.bytes) throw new Error('Unexpected component size');
  bytes=bytes.slice();
  const hash=await crypto.subtle.digest('SHA-256',bytes);
  const sha256=Array.from(new Uint8Array(hash),b=>b.toString(16).padStart(2,'0')).join('');
  if(sha256!==entry.sha256) throw new Error('Component SHA256 mismatch');
  const view=new DataView(bytes.buffer);
  if(view.getUint32(36,true)!==entry.type || view.getUint32(8,true)!==bytes.length-128) throw new Error('Component header mismatch');
  return Object.freeze({kind,label:entry.label,sha256,payloadBytes:bytes.length-128,installable:false,
    reason:'Device-specific boot, hardware and case versions, mixed-firmware compatibility, and recovery procedures have not yet been verified.'});
}
