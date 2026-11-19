"""Explicit cache candidate composition; never changes historical model assembly."""
import hashlib
from pathlib import Path
from verify_mspi1_pio_reset import models as baseline_models

BASELINE_SHA='f56920dba6aae3d85b743afcc20d190f8f0132cb8d1c25b1ae91c29848040e91'

def assemble(simulator):
    baseline=(simulator/'dcache-address-contract-01/base-system-control.cs').read_bytes()
    if hashlib.sha256(baseline).hexdigest()!=BASELINE_SHA:raise ValueError('Cache baseline differs')
    original=baseline_models(simulator);replacement=Path(__file__).with_name('renode-system-control.cs').read_bytes()
    if original.count(baseline)!=1:raise ValueError('Expected one frozen cache component')
    candidate=original.replace(baseline,replacement)
    sha=lambda b:hashlib.sha256(b).hexdigest()
    return candidate,dict(schema=1,kind='explicit-component-replacement',baseline_model_sha256=sha(original),candidate_model_sha256=sha(candidate),components=[dict(name='system-control',before_sha256=sha(baseline),after_sha256=sha(replacement))],default_profile_changed=False)

def models(simulator):
    return assemble(simulator)[0]

def bind_dccmvau(model):
    """Add clean-to-PoU to the existing opt-in coherent SRAM address contract."""
    if 'public int AddressUnificationCleans' in model:return model
    edits=[
        ('new long[]{0xf5c,0xf60,0xf68,0xf6c,0xf70,0xf74}','new long[]{0xf5c,0xf60,0xf64,0xf68,0xf6c,0xf70,0xf74}'),
        ('AddressInvalidations=AddressCleans=AddressCleanInvalidations=0;','AddressInvalidations=AddressCleans=AddressCleanInvalidations=AddressUnificationCleans=0;'),
        ('if(offset==0xf5c || offset==0xf68 || offset==0xf70)','if(offset==0xf5c || offset==0xf64 || offset==0xf68 || offset==0xf70)'),
        ('else if(offset==0xf68)AddressCleans++;','else if(offset==0xf64)AddressUnificationCleans++;\n                else if(offset==0xf68)AddressCleans++;'),
        ('        public int AddressCleans { get; private set; }','        public int AddressUnificationCleans { get; private set; }\n        public int AddressCleans { get; private set; }')]
    for old,new in edits:
        if old=='AddressInvalidations=AddressCleans=AddressCleanInvalidations=0;' and old not in model:continue
        if model.count(old)!=1:raise ValueError('Unique coherent cache address boundary required: '+old)
        model=model.replace(old,new)
    return model
