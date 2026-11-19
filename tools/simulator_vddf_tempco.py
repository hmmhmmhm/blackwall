"""One observed initial VDDF trim reduction in virtual registers; no voltage model."""


class VddfTempcoStorage:
    ADDRESS=0x4002004c
    MASK=0x7f

    def __init__(self,report,fixture):
        self.report=report
        self.fixture=fixture
        original=int(fixture.registers[self.ADDRESS]['value'],16)
        self.state={'applied':False,'original_word':original,'reduced_trim':max((original&self.MASK)-10,0),
                    'hardware_verified':False,'voltage_temperature_and_valid_calibration':'not-modeled'}
        report['vddf_tempco_storage']=self.state
        report['models'].append('one-time-vddf-tempco-startup-storage')
        if 'trim_reset_fixture' in report:
            report['trim_reset_fixture']['write_exception']='selected core/memory LDO setup and one initial VDDF reduction only'

    def write(self,address,size,value):
        if (address!=self.ADDRESS or size!=4 or self.state['applied']
            or self.report.get('buck_response',{}).get('phase')!='active'
            or self.report.get('memldo_setup_storage',{}).get('steps_completed')!=2):return False
        row=self.fixture.registers[self.ADDRESS]
        current=int(row['value'],16)
        expected=(self.state['original_word']&~self.MASK)|self.state['reduced_trim']
        if row['reads']<2 or current!=self.state['original_word'] or value!=expected:return False
        row['value']=hex(value);row['writes']+=1;self.state['applied']=True
        return True
