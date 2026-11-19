"""Build a narrowly patched, hash-pinned open-source IOM dependency for Renode."""
import hashlib
from pathlib import Path
UPSTREAM_SHA='164bf8a85ca189d2a64a71723564f0e5ab122be995a6924819e9ee1d9fb0bfad'
SOURCE=Path.home()/'Library/Application Support/Blackwall/simulator/iom-research-01/AmbiqApollo4_IOMaster.cs'

def build_engine(data):
    if hashlib.sha256(data).hexdigest()!=UPSTREAM_SHA:raise ValueError('Unreviewed Renode IOM dependency')
    source=data.decode()
    before='''                tailIndex = (tailIndex + 1) % DoubleWordCapacity;
                Count++;
                memory[tailIndex] = value;'''
    after='''                tailIndex = (tailIndex + 1) % DoubleWordCapacity;
                memory[tailIndex] = value;
                Count++;'''
    if source.count(before)!=1 or source.count('AmbiqApollo4_IOMaster')!=2:raise ValueError('IOM dependency patch does not apply exactly')
    source=source.replace(before,after).replace('AmbiqApollo4_IOMaster','BlackwallPollingIomEngine')
    using=source.index('using System;');namespace=source.index('namespace Antmicro.Renode.Peripherals.SPI')
    imports=source[using:namespace]
    source=source[:using]+source[namespace:]
    marker='namespace Antmicro.Renode.Peripherals.SPI\n{\n'
    if source.count(marker)!=1:raise ValueError('IOM namespace ambiguous')
    return source.replace(marker,marker+imports,1)

def load_engine():return build_engine(SOURCE.read_bytes())
