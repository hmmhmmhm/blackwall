const element = id => document.getElementById(id);
function makeIcon(name) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
  svg.classList.add('icon');
  svg.setAttribute('aria-hidden', 'true');
  use.setAttribute('href', 'icons.svg#' + name);
  svg.append(use);
  return svg;
}
function setPlayIcon(name) { element('play').replaceChildren(makeIcon(name)); }
const panels = {
  Emulator: ['simulator'],
  Firmware: ['chip', 'Stock firmware 2.3', 'The display contains a captured 576 × 288 guest frame from the stock 2.3 simulator.'],
  Tools: ['tools', 'Preview tools', 'Inspect the board categories or scrub the local preview timeline.'],
  Logs: ['logs', 'Session logs']
};
const layers = {
  'Layout (G2)': 'Approximate 3D model. The FCC connector-side sample shows U25643 and CY8C40 markings. The opposite side shows AP510BFA.',
  'Power': 'Power-management chip placement has not been identified on this sample.',
  'Sensor I/O': 'Firmware references an IMU. Its physical position on the photographed board is unconfirmed.',
  'Display I/F': 'The preview uses a 576 × 288 guest frame. The physical display interface is unmarked in this illustration.',
  'Audio': 'The FCC sample reads GX8002D. Firmware analysis references GX8002B. The photographed unit’s exact variant is unconfirmed.'
};
// Illustrative protocol frames, not a live connection or a captured device session.
const previewStarted = performance.now();
// Recorded virtual timestamps from original-boot-cli-native-bw548-02, not hardware time.
const logs = [
  '+000000000 µs   [BOOT]  Stock bootloader reset',
  '+020129100 µs   [RX]    UART0  01 80 0D 00 01 00 00 01 73 0A 07 80',
  '+020229100 µs   [RX]    UART0  01 80 10 00 01 00 00 03 9F 02 C1 81',
  '+020739792 µs   [FRAME] 576 × 288'
];
const panel = element('panel');
const range = document.querySelector('input[type=range]');
let seconds = 0;
let timer;
let selected = '';
function record(message) {
  logs.push('+' + String(Math.round((performance.now() - previewStarted) * 1e3)).padStart(9, '0') + ' µs   [UI]   ' + message);
  element('events').textContent = logs.slice(-4).join('\n');
  if (selected === 'Logs') panel.querySelector('pre').textContent = logs.join('\n');
}
function showTab(name) {
  selected = name;
  element('section').textContent = name;
  for (const button of element('tabs').children) button.setAttribute('aria-pressed', button.dataset.name === name);
  panel.replaceChildren();
  panel.hidden = name === 'Emulator';
  if (!panel.hidden) {
    const heading = document.createElement('h2');
    heading.textContent = panels[name][1];
    const body = document.createElement(name === 'Logs' ? 'pre' : 'p');
    body.textContent = name === 'Logs' ? logs.join('\n') : panels[name][2];
    panel.append(heading, body);
  }
}
for (const [name, [icon]] of Object.entries(panels)) {
  const button = document.createElement('button');
  button.dataset.name = name;
  const glyph = makeIcon(icon);
  button.append(glyph, name);
  button.onclick = () => {showTab(name); record(name + ' opened');};
  element('tabs').append(button);
}
const detail = element('detail');
function closeDetail() {
  detail.hidden = true;
  for (const button of element('layers').children) button.setAttribute('aria-pressed', 'false');
}
for (const [name, note] of Object.entries(layers)) {
  const button = document.createElement('button');
  button.textContent = name;
  button.setAttribute('aria-pressed', 'false');
  button.onclick = () => {
    const wasOpen = button.getAttribute('aria-pressed') === 'true';
    closeDetail();
    if (wasOpen) return;
    button.setAttribute('aria-pressed', 'true');
    const close = document.createElement('button');
    close.textContent = '×';
    close.setAttribute('aria-label','Close board detail');
    close.onclick = () => {closeDetail();button.focus();};
    detail.replaceChildren(close,note);
    detail.hidden = false;
    record(name + ' inspected');
  };
  element('layers').append(button);
}
function updateClock() {
  range.value = seconds;
  element('clock').textContent = [Math.floor(seconds/60), seconds%60].map(n => String(n).padStart(2,'0')).join(':') + ' / 05:00';
}
function stop() {
  clearInterval(timer);
  timer = undefined;
  setPlayIcon('play');
  element('play').setAttribute('aria-label','Play preview timeline');
}
range.oninput = () => {seconds = Number(range.value);updateClock();if(seconds === 300) stop();};
range.onchange = () => record('Timeline moved to ' + seconds + ' s');
element('play').onclick = () => {
  if (timer) {stop(); record('Timeline paused');return;}
  if (seconds === 300) seconds = 0;
  updateClock();
  record('Preview timeline playing · still frame');
  setPlayIcon('pause');
  element('play').setAttribute('aria-label','Pause preview timeline');
  timer = setInterval(() => {seconds++;updateClock();if(seconds === 300) {stop(); record('Timeline ended');}},1000);
};
showTab('Emulator');
element('events').textContent = logs.join('\n');

const board = element('board-model');
element('board-front').onclick = () => { board.cameraOrbit = '0deg 90deg auto'; record('Board front view selected'); };
element('board-back').onclick = () => { board.cameraOrbit = '180deg 90deg auto'; record('Board back view selected'); };
element('board-toggle').onclick = event => {
  const bare = event.currentTarget.getAttribute('aria-pressed') !== 'true';
  event.currentTarget.setAttribute('aria-pressed', String(bare));
  board.src = bare ? 'board-model-bw590/g2-temple-board.glb' : 'board-model-bw590/g2-temple-assembly.glb';
  record(bare ? 'Bare PCB model selected' : 'Assembly model selected');
};
