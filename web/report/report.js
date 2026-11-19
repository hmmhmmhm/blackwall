'use strict';
const data = window.BLACKWALL_REPORT;
const el = id => document.getElementById(id);
const svg = name => { const s=document.createElementNS('http://www.w3.org/2000/svg','svg'); const u=document.createElementNS('http://www.w3.org/2000/svg','use'); s.classList.add('icon'); s.setAttribute('aria-hidden','true'); u.setAttribute('href','icons.svg#'+name); s.append(u); return s; };
const time = n => '+' + String(n).padStart(9,'0') + ' µs';
const checkpoints = ['boot-reset','boot-main','boot-manager','stock-handoff','main-reset','ui-dispatch','renderer-entry'];
const reached = new Set(data.points.map(p=>p.name));
const done = checkpoints.filter(x=>reached.has(x)).length;
const expectedStop = data.scenario === 'unknown-boot-marker';
const summary = data.boundary === 'host-error' ? 'Execution failed' : expectedStop ? (data.passed ? 'Expected rejection' : 'Rejection validation failed') : (data.passed ? 'Verified' : 'Validation failed');
el('report-status').textContent = summary;
el('report-status').title = 'Scenario assessment; not hardware certification';
const ranges = document.querySelector('input[type=range]');
ranges.min=0; ranges.max=String(Math.max(data.virtual_us,1)); ranges.value=ranges.max;
const image=document.querySelector('.guest');
image.alt='Final guest framebuffer captured by the emulator';
let enhanced = Boolean(data.enhanced);
let activeFrame = null;
const frames = data.frames || [];
function showFrameMode() {
  const src = activeFrame ? (enhanced ? activeFrame.enhanced : activeFrame.raw) : (enhanced ? 'screen-enhanced.png' : 'screen.png');
  if (image.getAttribute('src') !== src) image.src = src;
  el('frame-mode').textContent = enhanced ? 'View raw' : 'View adjusted';
}
if (data.screen) {el('frame-controls').hidden=false; el('frame-mode').hidden=!data.enhanced; showFrameMode();}
el('frame-mode').onclick=()=>{enhanced=!enhanced;showFrameMode();};
if (!data.screen) { image.hidden=true; const note=document.createElement('p'); note.className='empty-frame'; note.textContent='NO DISPLAY DATA'; image.after(note); }
const events = [
 ...(data.device_events || []).map(p=>({us:p.time_us,text:p.text})),
 ...(data.firmware_events || []).map(p=>({us:p.time_us,text:`[UART1 / LINE END] ${p.text}`})),
 ...(data.uart_tx || []).map(p=>({us:p.time_us,text:`[UART0 TX / CAPTURE] ${p.data}`})),
 ...data.points.filter(p=>Number.isInteger(p.time_us)).map(p=>({us:p.time_us,text:`[BOOT] ${p.name} · PC 0x${p.pc.toString(16)}`})),
 ...frames.map((f,i)=>({us:f.time_us,text:`[FRAME] ${i+1}/${frames.length} · 576 × 288`})),
 ...(data.timed || []).map(p=>({us:p.time_us,text:p.text})),
 ...data.replies.map(p=>({us:p.time_us, text:`[${p.direction}] ${p.channel} ${p.data}`})),
 ...(data.screen ? [{us:data.virtual_us,text:'[FRAME] 576 × 288 guest framebuffer'}] : [{us:data.virtual_us,text:'[STOP] '+(data.boundary==='host-error'?'Host execution failed':expectedStop?'Unknown boot marker · strict boundary':(data.failure || 'Capture ended'))}])
].sort((a,b)=>a.us-b.us);
const formatEvents = () => events.filter(e=>e.us<=Number(ranges.value)).map(e=>`${time(e.us)}   ${e.text}`).join('\n');
function update(){
 const current=Number(ranges.value);
 el('clock').textContent=(current/1e6).toFixed(3)+' / '+(data.virtual_us/1e6).toFixed(3)+' s';
 el('events').textContent=formatEvents();
 updateStages(current);
 const logBody=document.querySelector('.log-body');
 logBody.scrollTop=logBody.scrollHeight;
 const openLog=panel.querySelector('pre[data-timeline-log]');
 if(openLog){openLog.textContent=formatEvents();openLog.scrollTop=openLog.scrollHeight;}
 if(data.screen){
  activeFrame=frames.filter(f=>f.time_us<=current).at(-1) || null;
  const ready=frames.length ? Boolean(activeFrame) : current>=data.virtual_us;
  image.style.visibility=ready?'visible':'hidden';el('frame-wait').hidden=ready;el('frame-controls').hidden=!ready;
  if(ready) showFrameMode();
 }
}
ranges.oninput=update;
let timer; el('play').onclick=()=>{if(timer){clearInterval(timer);timer=null;el('play').replaceChildren(svg('play'));return;} if(Number(ranges.value)>=data.virtual_us)ranges.value=0; el('play').replaceChildren(svg('pause')); timer=setInterval(()=>{ranges.value=Math.min(data.virtual_us,Number(ranges.value)+100000);update();if(Number(ranges.value)>=data.virtual_us){clearInterval(timer);timer=null;el('play').replaceChildren(svg('play'));}},100);};
const panels={Emulator:['simulator'],Firmware:['chip'],Tools:['tools'],Logs:['logs']};
const panel=el('panel');
function show(name){el('section').textContent=name; for(const b of el('tabs').children)b.setAttribute('aria-pressed',b.dataset.name===name); panel.replaceChildren();panel.hidden=name==='Emulator';if(panel.hidden)return;const h=document.createElement('h2');h.textContent=name;const pre=document.createElement('pre');if(name==='Firmware')pre.textContent='Pinned stock 2.4 boot / main\n'+Object.entries(data.identity).map(([k,v])=>`${k}: ${v}`).join('\n');else if(name==='Tools')pre.textContent=`${summary}\nScenario: ${data.scenario}\nBoundary: ${data.boundary}\nObserved checkpoints: ${done}/${checkpoints.length}\n\nCapture coverage:\n${(data.trace_quality || []).map(x=>JSON.stringify(x)).join('\n') || 'No timestamped UART capture'}\n\n${data.limitations.join('\n')}`;else {pre.dataset.timelineLog='true';pre.textContent=formatEvents();}panel.append(h,pre);if(name==='Logs')pre.scrollTop=pre.scrollHeight;}
for(const [name,[icon]] of Object.entries(panels)){const b=document.createElement('button');b.dataset.name=name;b.append(svg(icon),name);b.onclick=()=>show(name);el('tabs').append(b);}
const stagesList=el('stages-list');
const pointTime=name=>data.points.find(p=>p.name===name && Number.isInteger(p.time_us))?.time_us;
const timedEvent=prefix=>(data.timed||[]).find(p=>p.text.startsWith(prefix))?.time_us;
const firmwareTime=part=>(data.firmware_events||[]).find(p=>p.text.includes(part))?.time_us;
const stages=[
 {name:'Reset vector entry',at:pointTime('boot-reset'),soc:true},
 {name:'Runtime initialization entry',at:pointTime('boot-crt'),soc:true},
 {name:'FPU initialization entry',at:pointTime('boot-fpu'),soc:true},
 {name:'C data initialization entry',at:pointTime('boot-c-init'),soc:true},
 {name:'Bootloader main entry',at:pointTime('boot-main'),soc:true},
 {name:'Board initialization entry',at:pointTime('boot-board-init'),soc:true},
 {name:'NOR interface initialized (log)',at:firmwareTime('Nor flash mSPI interface initialized'),nor:true},
 {name:'Filesystem boot count (log)',at:firmwareTime('littlefs_init)boot_count')},
 {name:'Boot manager entry',at:pointTime('boot-manager'),soc:true},
 {name:'Stock main handoff',at:pointTime('stock-handoff'),soc:true},
 {name:'Main reset entry',at:pointTime('main-reset'),soc:true},
 {name:'IMU modeled service trigger',at:(data.device_events||[]).find(p=>p.device==='IMU')?.time_us},
 {name:'BLE initialization (log)',at:firmwareTime('am_devices_em9305_init status')},
 {name:'Virtual touch accepted',at:timedEvent('[INPUT]')},
 {name:'UART0 response received',at:data.replies.find(p=>Number.isInteger(p.time_us))?.time_us},
 {name:'UI dispatch entry',at:pointTime('ui-dispatch'),soc:true},
 {name:'Renderer entry',at:pointTime('renderer-entry'),soc:true},
 {name:'Display frame observed',at:frames[0]?.time_us ?? (data.screen ? data.virtual_us : undefined)}
];
stages.sort((a,b)=>(a.at ?? Infinity)-(b.at ?? Infinity));
if(expectedStop || !data.passed){stages.push({name:expectedStop?'Boot metadata boundary':(data.failure || 'Execution validation boundary'),at:data.virtual_us,stopped:true});}
const stageNodes=stages.map(item=>{const li=document.createElement('li');li.className='stage';const dot=document.createElement('span');dot.className='dot';dot.setAttribute('aria-hidden','true');const body=document.createElement('span');const title=document.createElement('strong');title.textContent=item.name;const meta=document.createElement('small');body.append(title,meta);li.append(dot,body);stagesList.append(li);return {li,meta};});
let latestStage=-1;
const visualWindowUs=700000;
const visualSources=[
 {key:'SoC',side:'Back',material:'Blackwall observed SoC',times:[...data.points.map(p=>p.time_us),...(data.firmware_events||[]).map(p=>p.time_us),...(data.uart_tx||[]).map(p=>p.time_us),...frames.map(p=>p.time_us)]},
 {key:'NOR',side:'Front',material:'Blackwall observed NOR',times:(data.firmware_events||[]).filter(p=>p.text.toLowerCase().includes('norflash')).map(p=>p.time_us)},
 {key:'Touch*',side:'Front',material:'Blackwall observed Touch',times:(data.timed||[]).filter(p=>p.text.startsWith('[INPUT]')).map(p=>p.time_us)},
 {key:'IMU*',side:'Back',material:'Blackwall illustrative IMU',times:(data.device_events||[]).filter(p=>p.device==='IMU').map(p=>p.time_us)},
 {key:'BLE*',side:'Back',material:'Blackwall illustrative BLE',times:(data.firmware_events||[]).filter(p=>/em9305|ble fw ver/i.test(p.text)).map(p=>p.time_us)},
 {key:'Display*',side:'Front',material:'Blackwall illustrative Display',times:frames.map(p=>p.time_us)}
];
let recentComponents=[];
let observedComponents=[];
const componentList=el('component-list');
const componentButtons=visualSources.map(item=>{
 const button=document.createElement('button');
 button.type='button';button.className='component-badge';button.textContent=item.key;
 button.title=item.key+(item.key.includes('*')?' · illustrative position':' · approximate sample position');
 button.setAttribute('aria-label',button.title);
 button.onclick=()=>{el(item.side==='Front'?'board-front-model':'board-back-model').focus();};
 componentList.append(button);return button;
});
function updateStages(current){
 const eligible=stages.map((x,i)=>({x,i})).filter(({x})=>Number.isInteger(x.at)&&x.at<=current);
 const currentIndex=eligible.length ? eligible.at(-1).i : -1;
 const terminal=current>=data.virtual_us;
 stages.forEach((item,i)=>{
  let state='pending',label='Pending';
  if(Number.isInteger(item.at) && item.at<=current){
   if(item.stopped && terminal){state='stopped';label=expectedStop?'Expected stop':'Validation failed';}
   else if(i===currentIndex && !terminal){state='current';label='Latest observed';}
   else {state='observed';label='Observed';}
  } else if(terminal && !Number.isInteger(item.at)){label='Not observed';}
  stageNodes[i].li.dataset.state=state;
  stageNodes[i].meta.textContent=label+(Number.isInteger(item.at)&&item.at<=current?' · '+time(item.at):'');
 });
 if(currentIndex!==latestStage){latestStage=currentIndex;if(currentIndex>=0){const target=stageNodes[currentIndex].li;stagesList.scrollTop=target.offsetTop-stagesList.offsetTop-stagesList.clientHeight/2+target.offsetHeight/2;}}
 observedComponents=visualSources.filter(item=>item.times.some(t=>Number.isInteger(t)&&t<=current));
 recentComponents=observedComponents.filter(item=>item.times.some(t=>Number.isInteger(t)&&t<=current&&current-t<=visualWindowUs));
 componentButtons.forEach((button,i)=>{const item=visualSources[i];button.dataset.state=recentComponents.includes(item)?'recent':observedComponents.includes(item)?'observed':'pending';});
 el('board-component').textContent='Observed to playhead';
 el('board-component').title='Green: observed up to this time; pulsing: event in the past 0.7 seconds. Not measured activity duration. * indicates illustrative placement.';
 el('board-component').dataset.active=observedComponents.length?'true':'false';
}
const boards=[el('board-front-model'),el('board-back-model')];
const materialsByBoard=new Map();
for(const board of boards)board.addEventListener('load',()=>{materialsByBoard.set(board,board.model?.materials || []);});
const reduced=window.matchMedia('(prefers-reduced-motion: reduce)');
function animateSoc(now){for(const materials of materialsByBoard.values()){for(const item of visualSources){const material=materials.find(m=>m.name===item.material);if(material){const glow=recentComponents.includes(item) ? (reduced.matches ? .14 : .06+.08*(1+Math.sin(now/550))) : observedComponents.includes(item) ? .09 : 0;material.setEmissiveFactor([0,glow*3,0]);}}}requestAnimationFrame(animateSoc);}
requestAnimationFrame(animateSoc);
el('board-toggle').onclick=e=>{const bare=e.currentTarget.getAttribute('aria-pressed')!=='true';e.currentTarget.setAttribute('aria-pressed',String(bare));for(const board of boards){materialsByBoard.delete(board);board.src=bare?'board-model-bw590/g2-temple-board.glb':'board-model-bw590/g2-temple-assembly.glb';}};
show('Emulator'); update();
