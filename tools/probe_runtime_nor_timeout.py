"""Run a one-shot virtual program timeout after an original main hold."""
import argparse
import json
from pathlib import Path

from inspect_nor_error_propagation import discover_chain
from native_replay import IMAGE
from probe_runtime_kv_restart import build as build_model, digest
from run_renode_m55_probe import execute
from run_runtime_connection_m55 import pin_capture, inspect
from runtime_event_models import integrate_gaf
from verify_kv_persistence_cycle import validate_capture


def timeout_return_chain(result):
    values=[row[:3:2] for row in result['rows'] if row[0] in (1,2,3,4)]
    expected=[[1,4],[2,0],[3,0],[4,0]]
    return any(values[n:n+4]==expected for n in range(len(values)-3))


def build(simulator, source, output, fault, gaf_profile=False):
    build_model(source,output,simulator,False)
    p=json.loads((output/'connection-profile.json').read_text())
    if gaf_profile:
        model,gaf=integrate_gaf(simulator,(output/'strict.cs').read_text())
        (output/'strict.cs').write_text(model)
        (output/'gaf-profile.json').write_text(json.dumps(gaf,indent=2)+'\n')
        board=(output/'board.repl').read_text();anchor='    profile: "icm45608-reset-lifecycle"\n'
        if board.count(anchor)!=1:raise ValueError('Unknown IMU owner')
        board=board.replace(anchor,anchor+'    gafParametersHex: "'+gaf['parameters_hex']+'"\n    gafConfiguration: true\n    gafClockVariationByte: '+str(gaf['clock_variation_byte'])+'\n')
        (output/'board.repl').write_text(board)
        p.update(gaf_profile=gaf,gaf_profile_sha256=digest(output/'gaf-profile.json'),model_sha256=digest(output/'strict.cs'))
        (output/'connection-profile.json').write_text(json.dumps(p,indent=2)+'\n')
    chain,bodies=discover_chain((source/'main.bin').read_bytes(),
        (source/'exports/sram-full.bin').read_bytes(),p)
    fdb,part,adapter,nor,poll=bodies
    sites=[x[-1].address for x in (poll,nor,adapter,part,fdb)]
    code=Path(__file__).with_name('renode-nor-error-observer.cs').read_bytes()
    (output/'nor-error-observer.cs').write_bytes(code)
    with (output/'activation.cs').open('ab') as f:f.write(b'\n'+code)
    runtime=(output/'run.py').read_text()
    anchor="    nor_before=nor_snapshot('before')\n"
    diagnostic_source=None
    if gaf_profile and '    def gaf_snapshot():\n' not in runtime:
        # Old peer captures predate the diagnostic snapshot. Reuse the saved,
        # pinned implementation rather than replacing their whole runner.
        reference=simulator/'runtime-kv-commit-native-01/stock24'
        validate_capture(reference)
        saved=(reference/'run.py').read_text()
        begin=saved.index('    def gaf_snapshot():\n');end=saved.index('    started_ticks=',begin)
        runtime=runtime.replace(anchor,anchor+saved[begin:end])
        export_ram="    File.WriteAllBytes('/work-output/connection-sram.bin'"
        if runtime.count(export_ram)!=1:raise ValueError('Missing peer result boundary')
        runtime=runtime.replace(export_ram,"    if p.get('gaf_profile'):result['imu_gaf']=gaf_snapshot()\n"+export_ram)
        diagnostic_source=digest(reference/'capture-files.json')
    install="""    from System import Array,UInt32
    clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallNorErrorObserver').Assembly)
    from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallNorErrorObserver
    nor_error=BlackwallNorErrorObserver(m,cpu,g.Mspi1Config.Pio,p['tcb_slot'],Array[UInt32](SITES))
    if FAULT:g.Mspi1Config.Pio.HoldNextProgramCompletion()
""".replace('SITES',repr(sites)).replace('FAULT',repr(fault))
    export="    File.WriteAllText('/work-output/connection.json'"
    save="""    nq=g.Mspi1Config.Pio
    nor_error_result=dict(fault_requested=FAULT,held_programs=int(nq.HeldProgramCompletions),armed=bool(nq.ProgramCompletionHeld),program_busy=bool(nq.ProgramBusy),overflow=bool(nor_error.Overflow),rows=[[int(v) for v in row] for row in nor_error.Rows],app_returned=bool(app.Stopped))
    File.WriteAllText('/work-output/nor-error.json',json.dumps(nor_error_result))
    Console.WriteLine('BLACKWALL_RUNTIME_NOR_ERROR '+json.dumps(nor_error_result))
""".replace('FAULT',repr(fault))
    if runtime.count(anchor)!=1 or runtime.count(export)!=1:raise ValueError('Unknown time action boundary')
    (output/'run.py').write_text(runtime.replace(anchor,anchor+install).replace(export,save+export))
    (output/'nor-error-source.json').write_text(json.dumps(dict(source_capture_sha256=digest(source/'capture-files.json'),
        fault_requested=fault,return_sites=sites,chain=chain,guest_context_forced=False,
        actual_nor_status_and_poll=True,gaf_diagnostic_source_sha256=diagnostic_source),indent=2)+'\n')
    inputs=json.loads((output/'connection-inputs.json').read_text())
    names=['activation.cs','run.py','nor-error-observer.cs','nor-error-source.json','strict.cs','board.repl','connection-profile.json']
    if gaf_profile:names.append('gaf-profile.json')
    for name in names:
        inputs[name]=digest(output/name)
    (output/'connection-inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('simulator',type=Path)
    p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--fault',action='store_true')
    p.add_argument('--gaf-profile',action='store_true');a=p.parse_args()
    if a.fault and not a.gaf_profile:
        p.error('Runtime timeout requires --gaf-profile; legacy IMU 0x02ae stops before the NOR return path')
    build(a.simulator,a.source,a.output,a.fault,a.gaf_profile)
    execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1','--pids-limit','128',
             '--cap-drop','ALL','--security-opt','no-new-privileges',
             '--mount',f'type=bind,source={a.output},target=/work,readonly',
             '--mount',f'type=bind,source={a.output}/exports,target=/work-output',IMAGE,
             '--disable-gui','--console','-p','-e','quit','/work/probe.resc'],a.output,'renode',timeout=180)
    pin_capture(a.output)
    result=json.loads((a.output/'exports/nor-error.json').read_text())
    observed=timeout_return_chain(result)
    print(json.dumps(dict(fault_requested=a.fault,held_programs=result['held_programs'],
                         rows=len(result['rows']),app_returned=result['app_returned'],
                         native_timeout_return_chain=observed)))
    if not a.fault:
        if not inspect(a.output)['passed']:raise SystemExit(1)
    elif result['held_programs']!=1 or result['overflow'] or not observed:
        raise SystemExit(1)


if __name__=='__main__':main()
