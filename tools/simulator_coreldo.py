"""One observed, saturated core-LDO field reduction; not a voltage model."""


class CoreLdoReduction:
    ADDRESS=0x40020080
    MASK=0x3ff
    REDUCTION=7

    def __init__(self,report,fixture):
        self.report=report;self.fixture=fixture
        word=int(fixture.registers[self.ADDRESS]['value'],16)
        self.state={'applied':False,'original_word':word,'cached_trim':word&self.MASK,
            'reduced_trim':max((word&self.MASK)-self.REDUCTION,0),
            'cache_witness':False,'hardware_verified':False,'voltage_and_valid_calibration':'not-modeled'}
        report['coreldo_reduction_storage']=self.state
        report['trim_reset_fixture']['write_exception']='selected one-time core-LDO initial reduction only'
        report['models'].append('one-time-saturated-coreldo-field-storage')

    def write(self,address,size,value):
        self.state['cache_witness']=all(r['reads']>0 for r in self.fixture.registers.values())
        if (address!=self.ADDRESS or size!=4 or self.state['applied'] or not self.state['cache_witness']
                or self.report.get('buck_start_storage',{}).get('steps_completed')!=2):return False
        row=self.fixture.registers[self.ADDRESS];current=int(row['value'],16)
        expected=(current&~self.MASK)|self.state['reduced_trim']
        if value!=expected:return False
        row['value']=hex(value);row['writes']+=1;self.state['applied']=True
        return True
