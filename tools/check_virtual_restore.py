"""Classify component hashes without asserting boot, installation, or physical recovery."""
import argparse
import json
from pathlib import Path
import re


def region(value):
    if not isinstance(value,dict) or set(value)!={'space','address','bytes'}:
        raise ValueError('Explicit address space, address and byte extent required')
    space,address,length=value['space'],value['address'],value['bytes']
    if not isinstance(space,str) or not space or type(address) is not int or type(length) is not int or address<0 or length<=0 or address+length>1<<64:
        raise ValueError('Invalid persistent byte extent')
    return space,address,address+length


def uncovered_regions(changes,known):
    result=[]
    for space,start,end in changes:
        pieces=[(start,end)]
        for other,left,right in known:
            if other!=space:continue
            remaining=[]
            for a,b in pieces:
                if right<=a or left>=b:remaining.append((a,b));continue
                if a<left:remaining.append((a,left))
                if right<b:remaining.append((right,b))
            pieces=remaining
        result.extend(dict(space=space,address=a,bytes=b-a) for a,b in pieces)
    return result


def assess(stock,observed,modified_components,inventory_complete=False,*,stock_extents=None,modified_regions=None):
    if type(inventory_complete) is not bool or not isinstance(modified_components,list) or not modified_components:
        raise ValueError('Explicit nonempty unique persistent component inventory required')
    if any(not isinstance(n,str) or not n for n in modified_components) or len(set(modified_components))!=len(modified_components):raise ValueError('Unique named components required')
    for mapping in (stock,observed):
        if not isinstance(mapping,dict) or any(not isinstance(v,str) or re.fullmatch('[0-9a-f]{64}',v) is None for v in mapping.values()):
            raise ValueError('Component SHA256 required')
    missing=sorted(n for n in modified_components if n not in stock or n not in observed)
    mismatched=sorted(n for n in modified_components if n in stock and n in observed and stock[n]!=observed[n])
    application='main' in stock and observed.get('main')==stock['main']
    named_match=not missing and not mismatched
    errors=[];uncovered=[]
    if stock_extents is None:errors.append('canonical-stock-extents-missing')
    elif not isinstance(stock_extents,dict) or any(n not in stock for n in stock_extents):raise ValueError('Extent names must reference canonical stock components')
    if modified_regions is None:errors.append('modified-byte-inventory-missing')
    elif not isinstance(modified_regions,list) or not modified_regions:raise ValueError('Nonempty modified byte inventory required')
    if stock_extents is not None:
        known=[region(v) for n,v in stock_extents.items() if n in observed and observed[n]==stock[n]]
        for value in stock_extents.values():region(value)
        if modified_regions is not None:uncovered=uncovered_regions([region(v) for v in modified_regions],known)
    covered=not errors and not uncovered
    full=inventory_complete and named_match and application and 'boot' in modified_components and 'main' in modified_components and covered
    return dict(stock_application_bytes=application,declared_components_match=named_match,full_stock_bytes=full,inventory_complete=inventory_complete,missing=missing,mismatched=mismatched,
                modified_bytes_covered=covered,uncovered_modified_regions=uncovered,coverage_errors=errors,
                reboot_verified=False,hardware_validated=False,installable=False,
                scope='Declared component hashes and byte extents only; source provenance and actual reboot require separate evidence')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('manifest',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();d=json.loads(a.manifest.read_text());r=assess(d['stock'],d['observed'],d['modified_components'],d.get('inventory_complete',False),stock_extents=d.get('stock_extents'),modified_regions=d.get('modified_regions'))
    with a.output.open('x') as f:json.dump(r,f,indent=2);f.write('\n')
    print(json.dumps(r))

if __name__=='__main__':main()
