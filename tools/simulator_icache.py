"""Functional coherent instruction memory; no cache latency or eviction model."""


class CoherentICache:
    def __init__(self, report):
        self.state={'ccr':0,'ccr_reads':0,'ccr_writes':0,'invalidations':0,
                    'hardware_verified':False,'cache_latency_eviction_and_power':'not-modeled',
                    'instruction_memory':'engine coherent memory; no separate instruction cache'}
        report['coherent_icache']=self.state
        report['models'].append('functional-coherent-instruction-memory')

    def read(self, offset, size):
        if offset==0xd14 and size==4:
            self.state['ccr_reads']+=1
            return self.state['ccr']
        return None

    def write(self, offset, size, value):
        if size!=4:return False
        if offset==0xf50 and value==0:
            self.state['invalidations']+=1
            return True
        if offset==0xd14 and value in (0,0x20000):
            if value and not self.state['invalidations']:return False
            self.state['ccr']=value
            self.state['ccr_writes']+=1
            return True
        return False
