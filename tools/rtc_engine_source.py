"""Pin an MIT RTC dependency and isolate it from host/machine wall-clock changes."""
import hashlib
from pathlib import Path
SOURCE=Path.home()/'Library/Application Support/Blackwall/simulator/rtc-module-research-01/AmbiqApollo4_RTC.cs'
UPSTREAM_SHA='dc22ac4df09190011dd70cce0e03b2eabace64246c4118d58e681a26d8623dc9'

def load_engine():
    data=SOURCE.read_bytes()
    if hashlib.sha256(data).hexdigest()!=UPSTREAM_SHA:raise ValueError('Unreviewed RTC engine source')
    s=data.decode();hook='            machine.RealTimeClockModeChanged += _ => SetDateTimeFromMachine();'
    if s.count('AmbiqApollo4_RTC')!=2 or s.count(hook)!=1:raise ValueError('RTC dependency isolation does not apply exactly')
    s=s.replace('AmbiqApollo4_RTC','BlackwallRtcEngine').replace(hook,'            // Blackwall supplies a fixed virtual epoch; ignore machine wall-clock mode events.')
    using=s.index('using System;');namespace=s.index('namespace Antmicro.Renode.Peripherals.Timers')
    imports=s[using:namespace];s=s[:using]+s[namespace:]
    marker='namespace Antmicro.Renode.Peripherals.Timers\n{\n'
    if s.count(marker)!=1:raise ValueError('RTC engine namespace differs')
    return s.replace(marker,marker+imports,1)
