// Adapted from g2-bootloader-patch tools/g2patch/ble_ota.py (MIT); see NOTICE.md.
function crc16(bytes) {
  let crc = 0xffff;
  for (const byte of bytes) {
    crc ^= byte << 8;
    for (let bit = 0; bit < 8; bit++) {
      crc = ((crc << 1) ^ ((crc & 0x8000) ? 0x1021 : 0)) & 0xffff;
    }
  }
  return crc;
}

export function frames(sid, payload, sequence) {
  if (![sid, sequence].every(v => Number.isInteger(v) && v >= 0 && v <= 255)) {
    throw new RangeError('SID and sequence must be bytes');
  }
  if (!(payload instanceof Uint8Array)) throw new TypeError('Payload must be Uint8Array');
  const count = Math.ceil((payload.length + 2) / 232);
  if (count > 255) throw new RangeError('Fragment count exceeds wire format');
  const body = new Uint8Array(payload.length + 2);
  body.set(payload);
  const crc = crc16(payload);
  body[payload.length] = crc & 255;
  body[payload.length + 1] = crc >> 8;
  const packets = [];
  for (let index = 0; index < count; index++) {
    const part = body.subarray(index * 232, (index + 1) * 232);
    const packet = new Uint8Array(8 + part.length);
    packet.set([0xaa, 0x21, sequence, part.length, count, index + 1, sid, 0]);
    packet.set(part, 8);
    packets.push(packet);
  }
  return packets;
}

// OTA ACKs are single-fragment replies. Fragmented messages require a separate reassembler.
export function unwrap(frame) {
  if (!(frame instanceof Uint8Array) || frame.length < 10 || frame.length > 240
      || frame[0] !== 0xaa || frame[1] !== 0x12 || frame[3] !== frame.length - 8
      || frame[4] !== 1 || frame[5] !== 1 || frame[7] !== 0) return null;
  const payload = frame.slice(8, -2);
  if (crc16(payload) !== (frame.at(-2) | (frame.at(-1) << 8))) return null;
  return {sid: frame[6], sequence: frame[2], payload};
}
