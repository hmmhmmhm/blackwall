"""PFCR control storage after an explicit write; no prefetch execution or reset assumption."""


class PrefetchStorage:
    def __init__(self, report):
        self.state={'value':None,'reads':0,'writes':0,'fields':None,
                    'initial_state':'unknown until first explicit write',
                    'prefetch_timing_and_transactions':'not-modeled','hardware_verified':False}
        report['prefetch_storage']=self.state
        report['models'].append('pfcr-defined-field-storage-no-reset-assumption')

    def read(self, address, size):
        if address==0xe001e004 and size==4 and self.state['value'] is not None:
            self.state['reads']+=1
            return self.state['value']
        return None

    def write(self, address, size, value):
        if address==0xe001e004 and size==4 and value&~0x3ff==0:
            self.state['value']=value
            self.state['writes']+=1
            self.state['fields']=dict(enable=bool(value&1),max_outstanding=(value>>7)&7,
                                      max_lookahead=(value>>4)&7,min_lookahead=(value>>1)&7)
            return True
        return False
