"""Exact main extraction for the three hash-pinned research bundles, never generic OTA input."""
import hashlib
from revalidate_research_assets import PINS as RESEARCH_PINS

PINS={name:RESEARCH_PINS[name][1] for name in ('stock_base','stock_current','cfw')}
# offset, raw main length, bundle length, raw main SHA256.
# Independently matched against the original main saved by the prior container parser.
MAIN_LAYOUT={
    'stock_base':(779275,3758688,4537963,'fffbf74b3439bf0e4752fb620a7990d0a133898c54f6fb08005ea6b7029655c5'),
    'stock_current':(782293,3700068,4482361,'df8cfddf3bd29a8351129a8364a8e0dafb347ffc7bfcbca5b52fdd973a7cce4a'),
    'cfw':(779275,3829832,4609107,'4118af85ebb8e634493a61a3ce4a62ae37451e17cea6d0b8b08465f29538dd8f'),
}


def load_pinned_main(data):
    digest=hashlib.sha256(data).hexdigest()
    profile=next((name for name,pin in PINS.items() if pin==digest),None)
    if profile is None:raise ValueError('Only the three pinned research bundles are accepted')
    offset,size,bundle_size,expected=MAIN_LAYOUT[profile]
    if len(data)!=bundle_size or offset<0 or size<8 or offset+size!=len(data):
        raise ValueError('Pinned main extent mismatch')
    raw=data[offset:offset+size]
    if hashlib.sha256(raw).hexdigest()!=expected:
        raise ValueError('Pinned original main SHA256 mismatch')
    return profile,raw
