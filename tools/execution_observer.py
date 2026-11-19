"""Generate read-only point/capture instrumentation shared by original-main runners."""
import re

def requests(point_args,capture_args,main_length):
    points=[];captures=[];labels=set();addresses=set()
    for item in point_args:
        fields=item.split(':')
        if len(fields)!=2 or not re.fullmatch('[a-z0-9][a-z0-9-]{0,47}',fields[0]):raise ValueError('Observation requires LABEL:ADDRESS')
        label=fields[0];address=int(fields[1],0)
        if label in labels or address in addresses or address%2 or not 0x438000<=address<0x438000+main_length:raise ValueError('Observation point must be unique/aligned/in original main')
        points.append(dict(label=label,address=address));labels.add(label);addresses.add(address)
    if len(points)>128:raise ValueError('At most 128 observation points')
    captured=set()
    for item in capture_args:
        fields=item.split(':')
        if len(fields)!=3:raise ValueError('Snapshot requires LABEL:ADDRESS:WORDS')
        label=fields[0];address=int(fields[1],0);words=int(fields[2],0)
        if label not in labels or label in captured or address%4 or not 1<=words<=16 or not 0x20000000<=address<=0x20380000-4*words:raise ValueError('Snapshot requires a declared point and bounded G2 SRAM words')
        captures.append(dict(label=label,address=address,words=words));captured.add(label)
    return points,captures

def instrument(base,points,captures=()):
    setup="""clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallExecutionObserver').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallExecutionObserver
observer=BlackwallExecutionObserver(m['sysbus.cpu'],128)
"""
    for p in points:setup+='observer.AddPoint('+repr(p['label'])+','+str(p['address'])+')\n'
    for c in captures:setup+='observer.CaptureSram(m,'+repr(c['label'])+','+str(c['address'])+','+str(c['words'])+')\n'
    marker='    e.StartAll()'
    if base.count(marker)!=1:raise ValueError('Ambiguous observer attachment')
    result=base.replace(marker,''.join('    '+line+'\n' for line in setup.splitlines())+marker)
    result+='''\nConsole.WriteLine('BLACKWALL_OBSERVATION '+json.dumps(dict(sequence=int(observer.Sequence),dropped_events=int(observer.DroppedEvents),capacity=int(observer.Capacity),points=[dict(label=str(p.Label),address=int(p.Address),hits=int(p.Hits),first_sequence=int(p.FirstSequence),snapshot=(dict(sequence=int(p.Snapshot.Sequence),address=int(p.Snapshot.Address),words=[int(x) for x in p.Snapshot.Words]) if p.Snapshot is not None else None)) for p in observer.Points],events=[dict(sequence=int(e.Sequence),label=str(e.Label),address=int(e.Address),pc=int(e.PC),r0=int(e.R0),r2=int(e.R2)) for e in observer.Events])))\n'''
    compile(result,'observed-run.py','exec')
    return result
