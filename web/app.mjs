import {inspectArtifact} from './artifact-catalog.mjs';
import {prepareInstallation,executeInstallation} from './installation-flow.mjs';
const operation=document.querySelector('#operation');
const artifact=document.querySelector('#artifact');
const button=document.querySelector('#inspect');
const result=document.querySelector('#result');
const side=document.querySelector('#side');
const deviceName=document.querySelector('#device-name');
const review=document.querySelector('#review');
const planText=document.querySelector('#plan');
const confirmation=document.querySelector('#confirmation');
const install=document.querySelector('#install');
let reviewedPlan=null;
let revision=0;
function invalidatePlan(){reviewedPlan=null;confirmation.value='';confirmation.disabled=true;install.disabled=true;planText.textContent='The previous plan is invalid. Review the target and file again.';}
side.addEventListener('change',reset);
deviceName.addEventListener('input',reset);
function reset(){revision++;invalidatePlan();review.disabled=false;button.disabled=false;result.textContent='Selection changed. Verify the file again.';}
operation.addEventListener('change',reset);
artifact.addEventListener('change',reset);
button.addEventListener('click',async()=>{
  const request=++revision, file=artifact.files[0], kind=operation.value;
  if(!file){result.textContent='Select a file to verify.';return;}
  if(file.size>4000000){result.textContent='The file is larger than a supported single component.';return;}
  button.disabled=true;result.textContent='Checking local SHA256…';
  try{
    const report=await inspectArtifact(kind,new Uint8Array(await file.arrayBuffer()));
    if(request!==revision)return;
    result.textContent=`File verification passed · ${report.label}\nPayload ${report.payloadBytes.toLocaleString()} bytes\nSHA256 ${report.sha256}\n\nInstallation eligibility: unverified\n${report.reason}`;
  }catch(error){if(request===revision)result.textContent=`File verification failed: ${error.message}`;}
  finally{if(request===revision)button.disabled=false;}
});

review.addEventListener('click',async()=>{
  const request=++revision;
  invalidatePlan();
  const file=artifact.files[0],kind=operation.value,selectedSide=side.value,expectedName=deviceName.value.trim();
  if(!file||file.size>4000000){planText.textContent='First select a supported single component file.';return;}
  review.disabled=true;planText.textContent='Reviewing installation plan…';
  try{
    const plan=await prepareInstallation({kind,side:selectedSide,expectedName,bytes:new Uint8Array(await file.arrayBuffer())});
    if(request!==revision)return;
    reviewedPlan=plan;
    planText.textContent=`${plan.label} · ${plan.side==='left'?'Left':'Right'}\nTarget: ${plan.expectedName}\nSHA256 ${plan.sha256}\n\nCompatibility: unverified · actual transfer blocked\n${plan.reason}`;
    confirmation.disabled=!plan.installable;
    if(plan.installable)planText.textContent+=`\nConfirmation phrase: ${plan.confirmation}`;
  }catch(error){if(request===revision)planText.textContent=`Plan review failed: ${error.message}`;}
  finally{if(request===revision)review.disabled=false;}
});
confirmation.addEventListener('input',()=>{
  install.disabled=!(reviewedPlan?.installable && confirmation.value===reviewedPlan.confirmation);
});
install.addEventListener('click',async()=>{
  if(!reviewedPlan?.installable){planText.textContent='Actual transfer is blocked because compatibility is unverified.';return;}
  const plan=reviewedPlan,phrase=confirmation.value;
  reviewedPlan=null;install.disabled=true;confirmation.disabled=true;
  try{
    const outcome=await executeInstallation(plan,phrase,navigator.bluetooth);
    planText.textContent=`Transfer response received · ${outcome.side}\nAwaiting actual image readback and recovery verification`;
  }catch(error){planText.textContent=`Operation stopped: ${error.message}\nNo automatic retransmission is performed.`;}
});
