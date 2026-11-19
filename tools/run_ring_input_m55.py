"""Run original ring relay→app→UI entry on an offline Renode M55 virtual board."""
import argparse
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('simulator', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--case', choices=['stock24','stock23','cfw'], required=True)
    parser.add_argument('--firmware-manifest', type=Path)
    parser.add_argument('--firmware-baseline', type=Path)
    parser.add_argument('--audit-existing', action='store_true')
    parser.add_argument('--audit-output', type=Path)
    args = parser.parse_args()
    if (args.firmware_manifest is None) != (args.firmware_baseline is None):
        parser.error('Candidate selection requires --firmware-manifest and --firmware-baseline')
    if args.audit_existing and (args.firmware_manifest is not None or args.firmware_baseline is not None):
        parser.error('Saved audit uses captured registration; omit candidate selection')
    if args.audit_existing != (args.audit_output is not None):
        parser.error('Saved audit requires --audit-existing and --audit-output together')
    s = args.simulator.resolve(); out = args.output.resolve()
    if (s.is_relative_to(ROOT) or any((parent/'.git').exists() for parent in [s, *s.parents])
            or not out.is_relative_to(s) or out == s):
        parser.error('Use a private simulator root and a distinct output inside it')
    destination = args.audit_output.resolve() if args.audit_existing else out/'verification'
    if args.audit_existing:
        if (not destination.is_relative_to(s) or destination == s or destination.exists()
                or destination.is_relative_to(out) or out.is_relative_to(destination)):
            parser.error('--audit-output must be a new directory outside the capture')
    elif out.exists():
        parser.error('Capture output must be a new directory')
    from simulator_cli_readiness import python_packages, native_tools
    python_packages()
    from ring_input_scenario import build, inspect
    from run_runtime_connection_m55 import pin_capture
    from run_renode_m55_probe import execute
    from native_replay import IMAGE
    if not args.audit_existing:
        native_tools()
        try:
            build(s, out, args.case, args.firmware_manifest, args.firmware_baseline)
        except ValueError as error:
            parser.error(str(error))
        execute(['docker','run','--rm','--network','none','--memory','512m','--cpus','1',
                 '--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges',
                 '--mount',f'type=bind,source={out},target=/work,readonly',
                 '--mount',f'type=bind,source={out/"exports"},target=/work-output',
                 IMAGE,'--disable-gui','--console','-p','-e','quit','/work/probe.resc'],
                out, 'renode', timeout=210)
        pin_capture(out)
    saved = json.loads((out/'ring-profile.json').read_text())
    if saved['case'] != args.case:
        parser.error('Saved ring case differs')
    try:
        result = inspect(out, destination)
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(dict(passed=result['passed'], case=args.case,
                          ui_callback_entry=result['semantic'].get('ui_callback_entry', False),
                          pixels_verified=False, report=str(destination/'report.json'))))
    if not result['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    from simulator_cli_readiness import run_cli
    run_cli(main)
