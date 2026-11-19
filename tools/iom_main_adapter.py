"""Split strict guards only around explicitly selected IOM instances."""
import re
SUPPORTED=(2,4,5,6,7)

def power_profiles(modules,default,overrides=None,iom4_profile=None):
    if default not in ('active','stuck-off'):raise ValueError('Unknown IOM power profile')
    overrides=dict(overrides or {})
    if iom4_profile is not None:
        if 4 in overrides:raise ValueError('Duplicate IOM4 override')
        overrides[4]=iom4_profile
    if any(n not in modules or value not in ('active','stuck-off') for n,value in overrides.items()):
        raise ValueError('Power override requires selected module and known profile')
    return {n:overrides.get(n,default) for n in modules}

def connect_ioms(board,profile,off_profile,modules=(2,),iom4_profile=None,cq_input_levels=None,profile_overrides=None):
    if cq_input_levels is not None and not 0<=cq_input_levels<=31:raise ValueError("CQ mock input levels require five-bit value")
    modules=tuple(sorted(modules))
    if not modules or len(set(modules))!=len(modules) or any(n not in SUPPORTED for n in modules):
        raise ValueError('Explicit unique IOM module set must be within 2,4,5,6,7')
    if profile not in ('active','stuck-off') or off_profile not in (None,'off','stuck-on'):
        raise ValueError('Unknown IOM power profile')
    profiles=power_profiles(modules,profile,profile_overrides,iom4_profile)
    marker='    baseAddress: 0x40001000'
    if board.count(marker)!=1:raise ValueError('IOM needs one reset-controller low bank')
    pattern=r'(?m)^guard_high: Miscellaneous.BlackwallG2StartupFixture @ sysbus 0x40025000\n(?:[ \t]+[^\n]*\n|\n)*'
    matches=list(re.finditer(pattern,board))
    if len(matches)!=1:raise ValueError('IOM needs one owned high guard')
    m=matches[0];high=m.group()
    if high.count('    size: 0x1ffdb000')!=1 or high.count('    baseAddress: 0x40025000')!=1 or '    gpuControlOwner: guard' not in high:
        raise ValueError('Unreviewed high guard geometry/owner')
    def guard(name,start,end):
        if start>=end:raise ValueError('Invalid guard span')
        return high.replace('guard_high:',name+':',1).replace('0x40025000',hex(start)).replace('0x1ffdb000',hex(end-start))
    cursor=0x40025000;name='guard_high';regions=[]
    for module in modules:
        address=0x40050000+module*0x1000
        regions.append(guard(name,cursor,address));cursor=address+0x400;name='guard_iom%s_tail'%module
    regions.append(guard(name,cursor,0x60000000))
    board=board[:m.start()]+''.join(regions)+board[m.end():]
    board=board.replace(marker,marker+'\n'+'\n'.join('    iom%sPower: iom%s_power'%(n,n) for n in modules))
    for module in modules:
        actual_profile=profiles[module]
        board+='\niom%s_power: Miscellaneous.BlackwallPeripheralPower\n    mask: %s\n    profile: %s\n'%(module,hex(1<<(module+1)),1 if actual_profile=='active' else 0)
        if off_profile is not None:board+='    offProfile: '+str(0 if off_profile=='off' else 1)+'\n'
        board+='\niom%s: Miscellaneous.BlackwallStrictIom @ sysbus %s\n    power: iom%s_power\n    module: %s\n    IRQ -> nvic@%s\n'%(module,hex(0x40050000+module*0x1000),module,module,6+module)
        if cq_input_levels is not None:board+='    cqInputLevels: '+str(cq_input_levels)+'\n'
    return board

def connect_iom2(board,profile,off_profile):
    return connect_ioms(board,profile,off_profile)
