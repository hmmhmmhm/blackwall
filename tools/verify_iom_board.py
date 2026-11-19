"""Verify selected IOM guard geometry and profile validation without executing firmware."""
import argparse,itertools,json,re,subprocess,sys
from pathlib import Path
from iom_main_adapter import connect_ioms,power_profiles,SUPPORTED
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('board',type=Path);p.add_argument('output',type=Path);a=p.parse_args();o=a.output.resolve();o.mkdir(mode=0o700)
    board=a.board.read_text();cases=[]
    for length in range(1,len(SUPPORTED)+1):
        for modules in itertools.combinations(SUPPORTED,length):
            text=connect_ioms(board,'active','off',modules);regions=[]
            for name,address,body in re.findall(r'(?m)^((?:guard[_a-z0-9]*|iom[24567])): [^\n]+ @ sysbus (0x[0-9a-f]+)\n((?:[ \t]+[^\n]*\n|\n)*)',text):
                if name=='guard':continue
                start=int(address,16);size=int(re.search(r'    size: (0x[0-9a-f]+)',body).group(1),16) if name.startswith('guard') else 0x400
                regions.append((start,start+size,name))
            regions.sort();assert regions[0][0]==0x40025000 and regions[-1][1]==0x60000000
            assert all(x[1]==y[0] for x,y in zip(regions,regions[1:]))
            assert sorted(int(name[3:]) for x,y,name in regions if name.startswith('iom'))==list(modules)
            assert text==connect_ioms(board,'active','off',tuple(reversed(modules)))
            mock=connect_ioms(board,'active','off',modules,cq_input_levels=0)
            assert 'cqInputLevels:' not in text and mock.count('    cqInputLevels: 0')==len(modules)
            for target in modules:
                assert power_profiles(modules,'active',{target:'stuck-off'})=={n:('stuck-off' if n==target else 'active') for n in modules}
            cases.append(dict(modules=modules,regions=regions))
    failures=[]
    # Bind each invalid module set independently (avoid deferred loop capture).
    actions=[(str(m),lambda m=m:connect_ioms(board,'active','off',m)) for m in [(),(2,2),(0,),(1,),(3,),(9,),(8,),(-1,)]]
    actions += [('duplicate-profile',lambda:power_profiles((2,4),'active',{4:'active'},'active')),('unselected-profile',lambda:power_profiles((2,),'active',{5:'active'})),('unknown-profile',lambda:power_profiles((2,5),'active',{5:'on'})),('bad-geometry',lambda:connect_ioms(board.replace('0x1ffdb000','0x1ffdb004'),'active','off'))]
    for name,action in actions:
        try:action()
        except ValueError:failures.append(name)
        else:raise AssertionError('Invalid input accepted: '+name)
    commands=[]
    messages=['Duplicate IOM power override','Power override requires selected module and known profile','Duplicate IOM4 override']
    for extra in [ ['--iom-power-profile','5:active','--iom-power-profile','5:stuck-off'], ['--iom-power-profile','6:active'], ['--iom4-model','active','--iom-power-profile','4:active'] ]:
        command=[sys.executable,str(ROOT/'tools/run_renode_main_probe.py'),str(o/'absent-input.bin'),str(o/'must-not-exist'),'--iom2-model','active','--iom-modules','2,4,5,7',*extra]
        r=subprocess.run(command,capture_output=True,text=True)
        expected=messages[len(commands)]
        assert r.returncode!=0 and not (o/'must-not-exist').exists() and r.stderr.rstrip().endswith('ValueError: '+expected)
        commands.append(dict(command=command,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr))
    report=dict(passed=True,module_subsets=len(cases),selections=cases,invalid_cases=failures,invalid_cli=commands,scope='guard topology/profiles/CLI preflight only; not hardware or native controller behavior')
    (o/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(passed=True,module_subsets=len(cases),invalid_cases=len(failures),invalid_cli=len(commands))))
if __name__=='__main__':main()
