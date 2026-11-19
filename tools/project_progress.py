"""Evidence-based scope coverage and append-only task tracking; no hardware access."""
import argparse
import csv
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re

COLUMNS=['ts','phase','decision','why','evidence','result','task_key','input_sha256','event','scope_ids','inputs']
STATUSES={'done','partial','pending','in-progress','requires-device-evidence'}


def data_file(root,name):
    directory=root/'docs/data'
    return (directory if directory.is_dir() else root/'docs')/name


def resolve(reference,root,private):
    base=private if reference.startswith('private:') else root
    relative=reference.removeprefix('private:') if reference.startswith('private:') else reference
    path=(base/relative).resolve()
    if base == root and not path.exists():
        index=data_file(root,'document-path-map.json')
        if index.is_file():
            mapped=json.loads(index.read_text()).get('paths',{}).get(relative)
            if mapped is not None:path=(root/mapped).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(base.resolve()):
        raise ValueError('Path must be inside the project or private root')
    return path


def fingerprint(inputs,root,private):
    if not inputs:raise ValueError('An input path is required')
    pairs=[]
    for reference in sorted(set(inputs)):
        path=resolve(reference,root,private)
        if not path.is_file():raise ValueError('Input file not found: '+reference)
        pairs.append((reference,hashlib.sha256(path.read_bytes()).hexdigest()))
    return hashlib.sha256(json.dumps(pairs,separators=(',',':')).encode()).hexdigest()


def check_evidence(item,root,private):
    path=resolve(item['path'],root,private)
    if not path.is_file():return False
    raw=path.read_bytes()
    if not item.get('sha256') or hashlib.sha256(raw).hexdigest()!=item['sha256']:return False
    if item.get('checks') or item.get('manifest'):
        data=json.loads(raw)
        for check in item.get('checks',[]):
            value=data
            for key in check['path']:value=value[key]
            if 'eq' in check and (type(value) is not type(check['eq']) or value!=check['eq']):return False
            if 'min_length' in check and len(value)<check['min_length']:return False
        if item.get('manifest'):
            for relative,metadata in data['files'].items():
                child=(path.parent/relative).resolve()
                if not child.is_relative_to(path.parent.resolve()) or not child.is_file():return False
                payload=child.read_bytes()
                if len(payload)!=metadata['bytes'] or hashlib.sha256(payload).hexdigest()!=metadata['sha256']:return False
    return True


def evaluate(scope,root,private):
    if scope.get('metric')!='verified-criteria-ratio':raise ValueError('Unsupported progress metric')
    rows=[];seen=set()
    for criterion in scope['criteria']:
        if (criterion['id'] in seen or criterion['group'] not in scope['groups'] or criterion['status'] not in STATUSES
                or criterion.get('kind','delivery') not in ('delivery','operation')):
            raise ValueError('Duplicate criterion or invalid scope definition')
        seen.add(criterion['id']);row=dict(criterion)
        valid=False
        if criterion['status']=='done':
            try:valid=bool(criterion['evidence']) and all(check_evidence(e,root,private) for e in criterion['evidence'])
            except (OSError,ValueError,KeyError,IndexError,TypeError):valid=False
        row['effective_status']='done' if valid else 'stale' if criterion['status']=='done' else criterion['status']
        rows.append(row)
    if not rows:raise ValueError('Scope has no acceptance criteria')
    delivery=[row for row in rows if row.get('kind','delivery')=='delivery']
    operations=[row for row in rows if row.get('kind')=='operation']
    if not delivery:raise ValueError('No product acceptance criteria')
    completed=sum(row['effective_status']=='done' for row in delivery)
    groups={key:dict(title=title,completed=sum(r['effective_status']=='done' for r in delivery if r['group']==key),
                     total=sum(r['group']==key for r in delivery)) for key,title in scope['groups'].items()}
    result=dict(version=scope['version'],completed=completed,total=len(delivery),percent=round(100*completed/len(delivery),1),
                operational_completed=sum(r['effective_status']=='done' for r in operations),operational_total=len(operations),criteria=rows,groups=groups)
    if scope.get('current_outcome'):
        stage=scope['current_outcome']
        # Independent acceptance gates, evaluated by the same evidence rules.
        # Their count never enters the product numerator or denominator.
        result['current_outcome']=evaluate(dict(version=scope['version'],metric=scope['metric'],groups={'M':stage['title']},
            criteria=[dict(gate,group='M',kind='delivery') for gate in stage['gates']]),root,private)
    return result


def read_ledger(root):
    path=data_file(root,'work-log.tsv')
    if not path.exists():return []
    with path.open(newline='') as handle:
        fcntl.flock(handle,fcntl.LOCK_SH)
        reader=csv.DictReader(handle,delimiter='\t')
        if reader.fieldnames!=COLUMNS:raise ValueError('Work-log columns do not match')
        return list(reader)


def latest(rows):
    states={}
    for row in rows:
        if row['event'] in ('start','finish','import'):states[row['phase']]=row
    return states


def cell(value):
    text=str(value).replace('\t',' ').replace('\r',' ').replace('\n',' ')
    return "'"+text if text.startswith(('=','+','-','@')) else text


def append(handle,row):
    handle.seek(0,2)
    writer=csv.DictWriter(handle,fieldnames=COLUMNS,delimiter='\t',lineterminator='\n')
    if handle.tell()==0:writer.writeheader()
    writer.writerow({key:cell(row.get(key,'')) for key in COLUMNS})
    handle.flush();os.fsync(handle.fileno())


def locked_rows(root):
    path=data_file(root,'work-log.tsv');path.parent.mkdir(parents=True,exist_ok=True)
    handle=path.open('a+',newline='');fcntl.flock(handle,fcntl.LOCK_EX);handle.seek(0)
    reader=csv.DictReader(handle,delimiter='\t');rows=list(reader)
    if reader.fieldnames not in (None,COLUMNS):handle.close();raise ValueError('Work-log format mismatch')
    return handle,rows


def start_task(root,private,key,description,why,inputs,scope_ids,repeat_reason=None):
    if not re.fullmatch('[a-z0-9][a-z0-9-]{0,79}',key):raise ValueError('Task key must be lowercase kebab-case')
    catalog=data_file(root,'project-scope.json')
    if catalog.exists():
        valid={item['id'] for item in json.loads(catalog.read_text())['criteria']}
        if not scope_ids or set(scope_ids)-valid:raise ValueError('Valid scope IDs are required')
    digest=fingerprint(inputs,root,private)
    handle,rows=locked_rows(root)
    with handle:
        states=latest(rows);matches=[r for r in states.values() if r['task_key']==key]
        previous=matches[-1] if matches else None
        active=next((r for r in reversed(matches) if r['result']=='in-progress'),None)
        completed=next((r for r in reversed(matches) if r['result']=='done' and r['input_sha256']==digest),None)
        changed_list=previous if previous and previous['result']=='done' and set(json.loads(previous['inputs']))!=set(inputs) else None
        blocked=active or ((completed or changed_list) if not repeat_reason else None)
        if blocked:
            note=dict(blocked,ts=datetime.now(timezone.utc).isoformat(),event='reuse',decision='Duplicate start blocked; reuse existing evidence',why=why)
            append(handle,note)
            raise ValueError('Existing task '+blocked['phase']+' status and evidence should be reused. Reverification requires --repeat-reason')
        if previous and previous['result'] in ('failed','deferred'):
            task_id=previous['phase'];description='Resume: '+description
        else:
            number=max((int(r['phase'][3:]) for r in rows if re.fullmatch('bw-[0-9]+',r['phase'])),default=0)+1
            task_id=f'bw-{number:04d}'
        append(handle,dict(ts=datetime.now(timezone.utc).isoformat(),phase=task_id,decision=description,
            why=why+(' / Reverification: '+repeat_reason if repeat_reason else ''),evidence='',result='in-progress',task_key=key,
            input_sha256=digest,event='start',scope_ids=','.join(scope_ids),inputs=json.dumps(sorted(set(inputs)))))
    return task_id


def finish_task(root,private,task_id,result,evidence,why):
    if result not in ('done','failed','deferred'):raise ValueError('Invalid result status')
    if result=='done' and not evidence:raise ValueError('Completion requires evidence')
    for reference in evidence:
        if not resolve(reference,root,private).is_file():raise ValueError('Evidence file not found: '+reference)
    handle,rows=locked_rows(root)
    with handle:
        previous=latest(rows).get(task_id)
        if previous is None or previous['result']!='in-progress':raise ValueError('Only an in-progress task can be finished')
        append(handle,dict(previous,ts=datetime.now(timezone.utc).isoformat(),decision='Record work results',why=why,
            evidence='; '.join(evidence),result=result,event='finish',input_sha256=fingerprint(json.loads(previous['inputs']),root,private)))


def record_progress(root,private,task_id,description,why,evidence):
    for reference in evidence:
        if not resolve(reference,root,private).is_file():raise ValueError('Evidence file not found: '+reference)
    handle,rows=locked_rows(root)
    with handle:
        previous=latest(rows).get(task_id)
        if previous is None or previous['result']!='in-progress':raise ValueError('Only an in-progress task can record progress')
        append(handle,dict(previous,ts=datetime.now(timezone.utc).isoformat(),decision=description,
            why=why,evidence='; '.join(evidence),event='progress'))


def render(scope,score,rows,path_map=None):
    labels={'done':'Done','partial':'Partial','pending':'Pending','in-progress':'In progress',
            'requires-device-evidence':'Device evidence and separate approval required','stale':'Evidence changed or missing: review required'}
    states={row['id']:row['effective_status'] for row in score['criteria']}
    key_states=' · '.join(title+': '+labels[states.get(id,'pending')] for id,title in
        scope.get('dashboard_states',[('W6','Web device path (W6)'),('S6','Integrated main (S6)'),('D3','Integrated display (D3)')]))
    lines=['# Blackwall Functional Verification Dashboard','',
        'See the [project entry document](../README.md) for the current research goal dashboard. The v3 100% below records completion of the earlier functional verification scope, not a new Goal or overall chipset precision.','',scope['objective'],'',
        f"**{scope.get('metric_label','Product acceptance criteria met')}: {score['percent']}% ({score['completed']}/{score['total']}) — scope v{score['version']}**",'',
        f"Operational requirements: {score['operational_completed']}/{score['operational_total']} (excluded from product progress).",'',
        'This percentage counts verified acceptance criteria; it does not estimate workload or remaining time. Partial and unverified criteria are excluded from the numerator.',
        'Each criterion has equal weight. More small tests do not increase progress until the corresponding acceptance criterion is met.',
        key_states+'. Hardware approval boundaries remain separate.','',
        '| Area | Acceptance criteria | Completion |','| --- | ---: | ---: |']
    for group in score['groups'].values():
        lines.append(f"| {group['title']} | {group['completed']}/{group['total']} | {round(100*group['completed']/group['total'],1) if group['total'] else 0}% |")
    lines+=['','## All acceptance criteria','','| ID | Acceptance criteria | Status | Evidence |','| --- | --- | --- | --- |']
    for row in score['criteria']:
        document=row.get('document')
        mapped=(path_map or {}).get(document,document) if document else None
        link=f"[{document}]({os.path.relpath(mapped,'docs')})" if mapped else ''
        kind=' (operational; excluded from progress)' if row.get('kind')=='operation' else ''
        lines.append(f"| {row['id']} | {row['title']+kind} | {labels[row['effective_status']]} | {link} |")
    if 'current_outcome' in score:
        stage=score['current_outcome'];title=scope['current_outcome']['title']
        lines+=['','## Current integration stage','',f"**{title}: {stage['completed']}/{stage['total']} ({stage['percent']}%)**",'',
                'This stage percentage is not added to overall acceptance progress. Stage completion is verified using evidence hashes and verdicts.','',
                '| Stage | Acceptance criteria | Status |','| --- | --- | --- |']
        for gate in stage['criteria']:
            lines.append(f"| {gate['id']} | {gate['title']} | {labels[gate['effective_status']]} |")
    lines+=['','## Current work and next steps','']
    task_states=list(latest(rows).values())
    for row in task_states:
        if row['result']=='in-progress':
            lines.append(f"- {row['phase']} · {row['task_key']} · {row['result']}: {row['why']}")
    lines+=['']+['- '+step for step in scope.get('next_steps',[])]
    history=[row for row in task_states if row['result'] in ('deferred','failed')]
    if history:
        lines+=['','## Deferred and failed work history','',
                'These records are deferred or failed. Their progress and scope reflect the time recorded and are not added to current progress.','']
        for row in history:
            lines.append(f"- {row['phase']} · {row['task_key']} · {row['result']}: {row['why']}")
    lines+=['','## Verification and scope notes','']+['- '+note for note in scope.get('notes',[])]
    lines+=['','## Avoiding duplication and records','',
        '`data/project-scope.json` defines the acceptance criteria, and `data/work-log.tsv` is an append-only work record.',
        'Check existing task keys and input SHA-256 values before starting. Reuse completed inputs and repeat explicitly only when there is a reason to reverify.',
        'Record scope changes with their version and reason. Registering a past baseline is an import at the current time and does not create a past execution timestamp.',
        'Procedures and commands: [Progress tracking](project/progress-tracking.md). The [existing completion audit](project/completion-audit.md) is preserved as evidence of earlier decisions.','']
    return '\n'.join(lines)


def dashboard(root,private,write=False):
    scope=json.loads((data_file(root,'project-scope.json')).read_text());score=evaluate(scope,root,private)
    if write:
        target=root/'docs/project-dashboard.md';temporary=target.with_suffix('.tmp')
        index=data_file(root,'document-path-map.json')
        path_map=json.loads(index.read_text()).get('paths',{}) if index.exists() else {}
        temporary.write_text(render(scope,score,read_ledger(root),path_map));os.replace(temporary,target)
    return score


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--private-root',type=Path,default=Path.home()/'Library/Application Support/Blackwall')
    sub=parser.add_subparsers(dest='command',required=True)
    report=sub.add_parser('report');report.add_argument('--write',action='store_true')
    start=sub.add_parser('start');start.add_argument('--key',required=True);start.add_argument('--description',required=True)
    start.add_argument('--why',required=True);start.add_argument('--input',action='append',required=True);start.add_argument('--scope',action='append',required=True)
    start.add_argument('--repeat-reason')
    finish=sub.add_parser('finish');finish.add_argument('task_id');finish.add_argument('--result',choices=('done','failed','deferred'),required=True)
    finish.add_argument('--evidence',action='append',default=[]);finish.add_argument('--why',required=True)
    progress=sub.add_parser('progress');progress.add_argument('task_id');progress.add_argument('--description',required=True)
    progress.add_argument('--why',required=True);progress.add_argument('--evidence',action='append',default=[])
    args=parser.parse_args()
    try:
        if args.command=='start':
            task=start_task(args.root,args.private_root,args.key,args.description,args.why,args.input,args.scope,args.repeat_reason)
            dashboard(args.root,args.private_root,True);print(task)
        elif args.command=='finish':
            finish_task(args.root,args.private_root,args.task_id,args.result,args.evidence,args.why)
            dashboard(args.root,args.private_root,True);print(args.task_id,args.result)
        elif args.command=='progress':
            record_progress(args.root,args.private_root,args.task_id,args.description,args.why,args.evidence)
            print(args.task_id,'progress')
        else:
            score=dashboard(args.root,args.private_root,args.write)
            print(json.dumps({key:score[key] for key in ('version','completed','total','percent','operational_completed','operational_total','groups')},ensure_ascii=False))
    except (ValueError,KeyError,OSError) as error:parser.exit(2,str(error)+'\n')


if __name__=='__main__':main()
