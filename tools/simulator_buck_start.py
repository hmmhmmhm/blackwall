"""Ordered SIMOBUCK requests; explicit single samples or a digital response profile."""


class BuckStartStorage:
    SEQUENCE=((0x40020378,0x80000000),(0x4002033c,0xf),(0x40021100,1))

    def __init__(self,report,*,status_fixture=None,response_model=None):
        if response_model not in (None,'active','stuck-off'):
            raise ValueError('Unknown buck response model')
        if response_model is not None and status_fixture is not None:
            raise ValueError('Choose a response model or a single status sample')
        if status_fixture not in (None,'off','lp','active'):
            raise ValueError('Unknown buck status fixture; reserved status is unsupported')
        self.report=report
        self.status_fixture=status_fixture
        self.response_model=response_model
        if response_model is not None:
            report['buck_response']={'profile':response_model,'phase':'off','reads':0,'transitions':0,
                'transition_trigger':'accepted enable request and completed post-enable memory-LDO setup',
                'completion_latency':'assumed zero at first eligible status read',
                'other_status_fields':'assumed zero','hardware_verified':False,
                'analog_voltage_failure_probability_and_timing':'not-modeled'}
            report['models'].append('explicit-request-gated-buck-response')
        if status_fixture is not None:
            report['buck_status_fixture']={'name':status_fixture,'value':{'off':0,'lp':0x20,'active':0x30}[status_fixture],
                'reads':0,'budget':1,'other_status_fields':'assumed zero','hardware_verified':False,
                'analog_transitions_and_timing':'not-modeled'}
            report['models'].append('single-post-enable-buck-status-sample')
        self.state={'steps_completed':0,'enable_requested':False,
            'registers':{hex(a):{'value':0,'reads':0,'writes':0} for a,_ in self.SEQUENCE},
            'initial_state':'public reset words used as synthetic fixture',
            'power_ready_feedback':'unprovided; reads blocked after enable request',
            'analog_trim_compensation_and_power':'not-modeled','hardware_verified':False}
        report['buck_start_storage']=self.state
        report['models'].append('ordered-buck-start-request-storage-only')
        if status_fixture is not None:
            self.state['power_ready_feedback']='one explicit diagnostic status sample only; later reads blocked'
        if response_model is not None:
            self.state['power_ready_feedback']='explicit digital response profile; not a physical power model'

    def sample_status(self,address,size):
        if (address!=0x40021108 or size!=4
                or self.state['steps_completed']!=3
                or self.report.get('memldo_setup_storage',{}).get('steps_completed')!=2):return None
        if self.response_model is not None:
            response=self.report['buck_response']
            if response['phase']=='requested':
                response['phase']='active' if self.response_model=='active' else 'stuck-off'
                response['transitions']+=1
            response['reads']+=1
            return 0x30 if response['phase']=='active' else 0
        if self.status_fixture is None:return None
        sample=self.report['buck_status_fixture']
        if sample['reads']>=sample['budget']:return None
        sample['reads']+=1
        return sample['value']

    def read(self,address,size):
        if size!=4 or hex(address) not in self.state['registers']:return None
        register=self.state['registers'][hex(address)];register['reads']+=1
        return register['value']

    def write(self,address,size,value):
        step=self.state['steps_completed']
        if (size!=4 or not self.report.get('buck_override_storage',{}).get('complete',False)
                or step>=len(self.SEQUENCE) or (address,value)!=self.SEQUENCE[step]):return False
        register=self.state['registers'][hex(address)];register['value']=value;register['writes']+=1
        self.state['steps_completed']+=1
        self.state['enable_requested']=self.state['steps_completed']==len(self.SEQUENCE)
        if self.state['enable_requested'] and self.response_model is not None:
            self.report['buck_response']['phase']='requested'
            self.report['buck_response']['transitions']+=1
        return True

    def blocks_readiness(self,address):
        return self.state['enable_requested'] and address==0x40021108
