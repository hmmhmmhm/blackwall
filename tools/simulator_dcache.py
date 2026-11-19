"""Optional coherent data memory with documented Apollo510 geometry; no cache timing."""


class CoherentDCache:
    def __init__(self, report):
        self.initialized = set()
        self.state = dict(selector=None, enabled=False, ccsidr=0xf03fe019,
                          selector_reads=0, selector_writes=0, geometry_reads=0,
                          initialized_lines=0, invalidate_set_way=0, clean_set_way=0,
                          clean_invalidate_set_way=0, hardware_verified=False,
                          memory='engine coherent memory; no separate dirty lines',
                          latency_eviction_dma_incoherence_and_power='not-modeled',
                          geometry_source='Apollo510 datasheet 1.1.0 section 3.2; G2 register value unmeasured')
        report['coherent_dcache'] = self.state
        report['models'].append('functional-coherent-data-memory-apollo510-64k-4way-32byte')

    def can_set_enabled(self, enabled):
        return not enabled or self.state['enabled'] or len(self.initialized) == 2048

    def read(self, offset, size):
        if size != 4:
            return None
        if offset == 0xd14:
            return 0x10000 if self.state['enabled'] else 0
        if self.state['selector'] is None:
            return None
        if offset == 0xd84:
            self.state['selector_reads'] += 1
            return 0
        if offset == 0xd80:
            self.state['geometry_reads'] += 1
            return self.state['ccsidr']
        return None

    def write(self, offset, size, value):
        if size != 4:
            return False
        if offset == 0xd14 and value in (0, 0x10000) and self.can_set_enabled(bool(value)):
            if self.state['enabled'] and not value:
                self.initialized.clear()
                self.state['initialized_lines'] = 0
            self.state['enabled'] = bool(value)
            return True
        if offset == 0xd84 and value == 0:
            self.state['selector'] = 0
            self.state['selector_writes'] += 1
            return True
        operations = {0xf60: 'invalidate_set_way', 0xf6c: 'clean_set_way', 0xf74: 'clean_invalidate_set_way'}
        if offset in operations and self.state['selector'] == 0 and value & ~0xc0003fe0 == 0:
            self.state[operations[offset]] += 1
            if offset != 0xf6c:
                self.initialized.add(((value >> 5) & 511) * 4 + (value >> 30))
                self.state['initialized_lines'] = len(self.initialized)
            return True
        return False
