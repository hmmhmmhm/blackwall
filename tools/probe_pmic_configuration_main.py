"""Replay immutable original ARM startup with optional PMIC config storage, without physical devices."""
import argparse,json,shutil,re
from pathlib import Path
from native_replay import FILES,IMAGE,digest,parse_log,validate_assets,boundary_state
from pinned_main import load_pinned_main
from run_renode_m55_probe import execute
ROOT=Path(__file__).resolve().parents[1]
def queued_board(board,samples,result_reset):
 if len(samples)!=6 or any(v<0 or v>1023 for v in samples) or result_reset not in (None,'source-reset'):raise ValueError('Invalid queued sample fixture')
 old='    measurementProfile: "discharging-vbat-ibat-fixture"\n'
 if board.count(old)!=1:raise ValueError('Previous conversion profile differs')
 selected=board.replace(old,'    measurementProfile: "queued-six-channel-fixture"\n').replace('    sharedResultBitsZeroMock: 0\n','')
 for name,value in [('vbatCode',samples[0]),('ibatCode',samples[2])]:
  selected,count=re.subn(r'^    '+name+r': -?\d+\n','    '+name+': '+str(value)+'\n',selected,flags=re.M)
  if count!=1:raise ValueError('Inherited sample field differs: '+name)
 node=''.join('    '+name+': '+str(value)+'\n' for name,value in [('ntcCode',samples[1]),('dieTempCode',samples[3]),('vsysCode',samples[4]),('vbusCode',samples[5])])
 if result_reset:node+='    resultResetProfile: "source-reset"\n'
 marker='    timerProfile: "fast-reset-stopped"\n'
 if selected.count(marker)!=1:raise ValueError('Timer node differs')
 return selected.replace(marker,marker+node)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--case',action='append',dest='cases');p.add_argument('--ntc-code',type=int,default=-1);p.add_argument('--die-temp-code',type=int,default=-1);p.add_argument('--vsys-code',type=int,default=-1);p.add_argument('--vbus-code',type=int,default=-1);p.add_argument('--result-reset-profile',choices=['source-reset']);p.add_argument('--vbat-code',type=int,default=-1);p.add_argument('--ibat-code',type=int,default=-1);p.add_argument('--shared-result-zero-mock',action='store_true');p.add_argument('--scratch0-zero-mock',action='store_true');p.add_argument('--component',choices=['vbus','adc','scratch','adc-reset','conversion','queued'],default='vbus');p.add_argument('simulator',type=Path);p.add_argument('output',type=Path);a=p.parse_args();s=a.simulator.resolve();o=a.output.resolve()
 if o.exists():raise ValueError('Fresh evidence directory required')
 o.mkdir(mode=0o700);base=s/({'vbus':'pmic-timed-main-03','adc':'pmic-vbus-main-01','scratch':'pmic-adc-storage-main-01','adc-reset':'pmic-scratch-main-01','conversion':'pmic-adc-reset-main-01','queued':'pmic-adc-conversion-main-01'}[a.component]);old=(base/'root.cs').read_bytes()+b'\n'+(base/'timed.cs').read_bytes();root=(ROOT/'tools/renode-pmic-restore-probe.cs').read_bytes();timed=(ROOT/'tools/renode-pmic-timed-probe.cs').read_bytes()
 for n,b in [('runner.py',Path(__file__).read_bytes()),('root.cs',root),('timed.cs',timed)]: (o/n).write_bytes(b)
 rows=[]
 if a.component not in ('conversion','queued') and (a.vbat_code!=-1 or a.ibat_code!=-1 or a.shared_result_zero_mock):raise ValueError('Sample parameters require conversion component')
 if a.component=='queued' and a.shared_result_zero_mock:raise ValueError('Queued model uses result-reset-profile, not shared-result-zero-mock')
 if a.component=='queued' and not all(0<=v<=1023 for v in [a.vbat_code,a.ibat_code,a.ntc_code,a.die_temp_code,a.vsys_code,a.vbus_code]):raise ValueError('Explicit six raw10 samples required')
 if a.component!='queued' and (any(v!=-1 for v in [a.ntc_code,a.die_temp_code,a.vsys_code,a.vbus_code]) or a.result_reset_profile is not None):raise ValueError('Queued parameters require queued component')
 if a.component=='conversion' and not(0<=a.vbat_code<=1023 and 0<=a.ibat_code<=1023):raise ValueError('Explicit raw10 samples required')
 if a.scratch0_zero_mock and a.component!='scratch':raise ValueError('Scratch mock requires scratch component')
 plans=[('stock24','stock24',True),('stock23','stock23',True),('cfw','cfw',True),('stock24-no-'+a.component,'stock24',False)]
 if a.component=='queued' and a.result_reset_profile:plans.append(('stock24-results-unknown','stock24',True))
 if a.component=='conversion' and a.shared_result_zero_mock:plans.append(('stock24-shared-bits-unknown','stock24',True))
 if a.component=='scratch' and a.scratch0_zero_mock:plans.append(('stock24-scratch-unknown','stock24',True))
 if a.cases:
  if set(a.cases)-{x[0] for x in plans}:raise ValueError('Unknown replay case')
  plans=[x for x in plans if x[0] in a.cases]
 for name,key,enabled in plans:
  src=base/key;before=json.loads((src/'report.json').read_text());v0=parse_log((src/'renode.log').read_text());bundle={'stock24':'stock-2.4.0.24.bin','stock23':'stock-2.3.0.24.bin','cfw':'faceclaw-38-research-only.bin'}[key];_,raw=load_pinned_main((s/'inputs/verified-01'/bundle).read_bytes())
  if raw!=(src/'main.bin').read_bytes() or before['observed']!=v0 or before['image_id']!=IMAGE:raise ValueError('Frozen input differs')
  d=o/name;d.mkdir(mode=0o700);original={f:digest(src/f) for f in FILES}
  for f in FILES:shutil.copyfile(src/f,d/f)
  validate_assets(d,original);strict=(d/'strict.cs').read_bytes()
  if not strict.endswith(old):raise ValueError('Frozen PMIC source differs')
  (d/'strict.cs').write_bytes(strict[:-len(old)]+root+b'\n'+timed)
  board=(d/'board.repl').read_text();needle='    timerProfile: "fast-reset-stopped"\n'
  if board.count(needle)!=1:raise ValueError('Timer attachment differs')
  fixture=0 if a.component in ('adc-reset','conversion','queued') or (a.component=='scratch' and a.scratch0_zero_mock and enabled and name!='stock24-scratch-unknown') else -1
  if enabled:
   if a.component=='queued':
    reset=a.result_reset_profile if name!='stock24-results-unknown' else None
    (d/'board.repl').write_text(queued_board(board,[a.vbat_code,a.ntc_code,a.ibat_code,a.die_temp_code,a.vsys_code,a.vbus_code],reset))
   elif a.component=='conversion':
    mock=a.shared_result_zero_mock and name!='stock24-shared-bits-unknown'
    node='    measurementProfile: "discharging-vbat-ibat-fixture"\n    vbatCode: '+str(a.vbat_code)+'\n    ibatCode: '+str(a.ibat_code)+'\n'+('    sharedResultBitsZeroMock: 0\n' if mock else '')
    (d/'board.repl').write_text(board.replace(needle,needle+node))
   elif a.component=='adc-reset':
    old_adc='    adcState: "guest-storage"\n'
    if board.count(old_adc)!=1:raise ValueError('ADC attachment differs')
    (d/'board.repl').write_text(board.replace(old_adc,'    adcState: "source-reset-storage"\n'))
   else:(d/'board.repl').write_text(board.replace(needle,needle+'    '+a.component+'State: "guest-storage"\n'+('    scratch0InitialMock: 0\n' if fixture==0 else '')))
  text=(d/'run.py').read_text();needle='except Exception as error:\n'
  if text.count(needle)!=1:raise ValueError('Runtime boundary differs')
  extra="    Console.WriteLine('BLACKWALL_PMIC_ADC_CONFIG '+json.dumps(dict(enabled=bool(peer.GuestAdcStorage),addresses=[int(x) for x in peer.AdcConfigAddresses],values=[int(x) for x in peer.AdcConfigValues],writes=int(peer.AdcConfigWrites))))\n" if a.component=='adc' else "    Console.WriteLine('BLACKWALL_PMIC_VBUS '+json.dumps(dict(enabled=bool(peer.GuestVbusStorage),current_known=bool(peer.VbusCurrentKnown),current=int(peer.VbusCurrent),suspend_known=bool(peer.VbusSuspendKnown),suspend=int(peer.VbusSuspend),writes=int(peer.VbusWrites),apply_requests=int(peer.VbusApplyRequests))))\n"
  if a.component=='scratch':extra="    Console.WriteLine('BLACKWALL_PMIC_SCRATCH '+json.dumps(dict(enabled=bool(peer.GuestScratchStorage),initial_mock=int(peer.Scratch0InitialMock),values=[int(x) for x in peer.ScratchValues],known_masks=[int(x) for x in peer.ScratchKnownMasks],writes=int(peer.ScratchWrites))))\n"
  if a.component=='adc-reset':extra="    Console.WriteLine('BLACKWALL_PMIC_ADC_UPDATE '+json.dumps(dict(source_reset=bool(peer.AdcSourceReset),addresses=[int(x) for x in peer.AdcConfigAddresses],values=[int(x) for x in peer.AdcConfigValues],writes=int(peer.AdcConfigWrites),update_writes=int(peer.AdcAutoUpdateWrites),update_requests=int(peer.AdcAutoUpdateRequests),last_request=int(peer.AdcAutoUpdateLastRequest))))\n"
  if a.component=='conversion':extra="    conversion=m['sysbus.iom7.pointerProbe'].AdcConversion\n    if conversion is None:state=dict(enabled=False)\n    else:state=dict(enabled=True,vbat_code=int(conversion.VbatCode),ibat_code=int(conversion.IbatCode),conversion_us=int(conversion.ConversionMicroseconds),zero_bits_mock=int(conversion.SharedBitsZeroMock),phase=str(conversion.Phase),requests=int(conversion.Requests),repeated_drops=int(conversion.RepeatedDrops),vbat_done=int(conversion.VbatCompletions),ibat_done=int(conversion.IbatCompletions),values=[int(x) for x in conversion.Values],known_masks=[int(x) for x in conversion.KnownMasks])\n    Console.WriteLine('BLACKWALL_PMIC_CONVERSION '+json.dumps(state))\n"
  if a.component=='queued':extra="    queued=m['sysbus.iom7.pointerProbe'].QueuedAdc\n    if queued is None:queued_state=dict(enabled=False)\n    else:queued_state=dict(enabled=True,samples=[int(x) for x in queued.Samples],result_reset=None if queued.ResultResetProfile is None else str(queued.ResultResetProfile),active=str(queued.Active),pending=int(queued.PendingMask),requests=int(queued.Requests),drops=int(queued.RepeatedDrops),auto_ibat=int(queued.AutomaticIbatRequests),completed=[int(x) for x in queued.Completed],order=[int(x) for x in queued.CompletionOrder],values=[int(x) for x in queued.Values],known_masks=[int(x) for x in queued.KnownMasks])\n    queued_state.update(result_reads=int(peer.AdcResultReads),result_bytes=int(peer.AdcResultBytes),result_addresses=[int(x) for x in peer.AdcResultAddresses],result_payloads=[str(x) for x in peer.AdcResultPayloads])\n    Console.WriteLine('BLACKWALL_PMIC_QUEUED '+json.dumps(queued_state))\n"
  text=text.replace(needle,extra+needle);compile(text,'run.py','exec');(d/'run.py').write_text(text);derived={f:digest(d/f) for f in FILES};(d/'derived-inputs.json').write_text(json.dumps(dict(base=original,derived=derived,component=a.component,scratch0_initial_mock=fixture,storage=('source-reset-storage' if a.component=='adc-reset' else 'discharging-vbat-ibat-fixture' if a.component=='conversion' else 'queued-six-channel-fixture' if a.component=='queued' else 'guest-storage') if enabled else None,actual_measurement_profile=(re.findall(r'^    measurementProfile: \"([^\"]+)\"', (d/'board.repl').read_text(),re.M) or [None])[0],actual_result_reset_profile=(re.findall(r'^    resultResetProfile: \"([^\"]+)\"',(d/'board.repl').read_text(),re.M) or [None])[0],actual_adc_state=('source-reset-storage' if '    adcState: \"source-reset-storage\"' in (d/'board.repl').read_text() else 'guest-storage' if '    adcState: \"guest-storage\"' in (d/'board.repl').read_text() else None)),indent=2)+'\n')
  cmd=['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--mount',f'type=bind,source={d},target=/work,readonly',IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'];(d/'command.json').write_text(json.dumps(cmd,indent=2)+'\n');log=execute(cmd,d,'renode');v=parse_log(log);validate_assets(d,derived)
  def marker(name):
   matches=[json.loads(x.split(name+' ',1)[1]) for x in log.splitlines() if x.startswith(name+' ')]
   if len(matches)!=1:raise ValueError('Missing '+name)
   return matches[0]
  state=marker('BLACKWALL_PMIC_RESTORE');timer=marker('BLACKWALL_PMIC_TIMER');vbus=marker('BLACKWALL_PMIC_VBUS');adc=marker('BLACKWALL_PMIC_ADC_CONFIG') if a.component in ('adc','scratch','adc-reset','conversion','queued') else None;scratch=marker('BLACKWALL_PMIC_SCRATCH') if a.component in ('scratch','adc-reset','conversion','queued') else None;update=marker('BLACKWALL_PMIC_ADC_UPDATE') if a.component in ('adc-reset','conversion','queued') else None;conversion=marker('BLACKWALL_PMIC_CONVERSION') if a.component in ('conversion','queued') else None;queued=marker('BLACKWALL_PMIC_QUEUED') if a.component=='queued' else None;r=dict(name=name,observed=v,peer=state,timer=timer,vbus=vbus,adc=adc,scratch=scratch,update=update,conversion=conversion,queued=queued,image_id=IMAGE,raw_main_sha256=digest(d/'main.bin'),boot_verified=False,hardware_validated=False,installable=False,selected_hypotheses=before['selected_hypotheses']);(d/'report.json').write_text(json.dumps(r,indent=2)+'\n')
  if enabled:
   if a.component=='queued':
    if not queued['enabled'] or queued['requests']<2:raise ValueError('Queued request not reached')
   elif a.component=='conversion':
    if not conversion['enabled'] or conversion['requests']<1:raise ValueError('Conversion request not reached')
   elif a.component=='adc-reset':
    if not update['source_reset']:raise ValueError('ADC source reset profile missing')
   elif a.component=='scratch':
    if scratch['writes']<1:raise ValueError('Scratch write did not complete')
   elif a.component=='adc':
    if adc['writes']<1:raise ValueError('PMIC ADC setup did not complete')
   elif not vbus['current_known'] or vbus['writes']<1:raise ValueError('VBUS setup did not complete')
  elif boundary_state(v)!=boundary_state(v0):raise ValueError('Default VBUS strict boundary changed')
  row=dict(name=name,pc=hex(v['pc']),vbus=vbus,adc=adc,scratch=scratch,update=update,conversion=conversion,queued=queued,timer=timer,guards=[g for g in v['guards'] if g['accesses']]);rows.append(row);print(json.dumps(row),flush=True)
 compare_stock_cfw={'stock23','cfw'}.issubset({x[0] for x in plans})
 if compare_stock_cfw:
  for f in ['board.repl','strict.cs','result.py','probe.resc']:
   if (o/'stock23'/f).read_bytes()!=(o/'cfw'/f).read_bytes():raise ValueError('Stock/CFW models differ')
  if (o/'stock23/run.py').read_text().replace('3758688','3829832')!=(o/'cfw/run.py').read_text():raise ValueError('Stock/CFW runtime differs')
 (o/'report.json').write_text(json.dumps(dict(passed=True,cases=rows,stock_cfw_compared=compare_stock_cfw,scope='explicit PMIC subsets/fixtures; inspect per-case assumptions; no physical or full boot proof'),indent=2)+'\n')
if __name__=='__main__':main()
