"""Read-only operation-specific compatibility planning; never runs firmware or hardware."""
import argparse,hashlib,json
from pathlib import Path
MATRIX_PATH=Path(__file__).resolve().parents[1]/'docs/data/bootloader-validation-matrix.json'
MODEL='synthetic-chip23-trim0'


def check(boot,main,operation,*,model=MODEL):
    if model!=MODEL:raise ValueError('Reviewed virtual model required; physical hardware is unverified')
    matrix=json.loads(MATRIX_PATH.read_text())
    if matrix['schema']!='blackwall-boot-validation-matrix/1' or matrix['installable'] is not False or matrix['hardware_validated'] is not False:raise ValueError('Invalid offline matrix')
    if operation not in matrix['operations']:raise ValueError('Unknown operation; no execution is authorized')
    if not isinstance(boot,bytes) or not isinstance(main,bytes):raise ValueError('Exact firmware bytes required')
    b,m=(hashlib.sha256(x).hexdigest() for x in (boot,main));artifacts=matrix['artifacts']
    pairs=[p for p in matrix['profiles'] if p['model']==model and artifacts[p['boot']]['sha256']==b and artifacts[p['main']]['sha256']==m]
    if len(pairs)!=1:raise ValueError('Unknown boot/main pair; compatibility is unverified')
    profile=pairs[0];cap=profile['capabilities'].get(operation,{'status':'unknown','reason':'No evidence for this operation'})
    if cap['status']!='verified-compatible':raise ValueError(cap['status']+': '+cap['reason'])
    return dict(schema='blackwall-boot-compatibility-check/1',profile=profile['id'],operation=operation,model=model,boot_sha256=b,main_sha256=m,capability_status=cap['status'],evidence=cap['evidence'],virtual_planning_match=True,installable=False,hardware_validated=False,execution_performed=False,limitations=['The executor must still validate its exact frozen model and state inputs','A virtual result does not authorize physical firmware operations'])


def read_firmware(path):
    path=Path(path)
    if not path.is_file() or not 8<=path.stat().st_size<=0x800000:raise ValueError('Bounded regular firmware file required')
    return path.read_bytes()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--boot',type=Path,required=True);p.add_argument('--main',type=Path,required=True);p.add_argument('--operation',required=True);p.add_argument('--model',default=MODEL);a=p.parse_args()
    try:print(json.dumps(check(read_firmware(a.boot),read_firmware(a.main),a.operation,model=a.model),indent=2))
    except (OSError,ValueError) as error:p.exit(2,str(error)+'\n')
