"""Optional digital HFRC2/performance response; no physical frequency or time model."""


class McuClockResponse:
    def __init__(self,report,mode,profile,misc):
        if mode not in ('lp','hp') or profile not in ('nominal','hfrc2-unready','no-ack','denied'):
            raise ValueError('Unsupported initial MCU mode or clock response profile')
        self.report=report
        self.misc=misc
        self.state={'profile':profile,'phase':'initial','mode_word':13 if mode=='lp' else 22,
                    'force_writes':0,'clock_reads':0,'mode_reads':0,'mode_writes':0,'transitions':0,
                    'hardware_verified':False,'completion_latency':'assumed-zero',
                    'other_clock_status_fields':'assumed zero except HFRC2 enabled/ready',
                    'physical_frequency_voltage_and_time':'not-modeled'}
        report['mcu_clock_response']=self.state
        report['models'].append('explicit-hfrc2-and-mcu-performance-response')
        self.refresh()

    def refresh(self):
        enabled=bool(self.misc['value']&0x20) or (self.state['mode_word']>>3)&3==2
        self.state['misc_word']=self.misc['value']
        self.state['hfrc2_enabled']=enabled
        self.state['hfrc2_ready']=enabled and self.state['profile']!='hfrc2-unready'

    def read_clock(self,size):
        if size!=4:return None
        self.refresh();self.state['clock_reads']+=1
        return (0x80000000 if self.state['hfrc2_enabled'] else 0)|(0x1000000 if self.state['hfrc2_ready'] else 0)

    def read_mode(self,size):
        if size!=4:return None
        self.state['mode_reads']+=1
        return self.state['mode_word']

    def write_misc(self,size,value):
        if (size!=4 or self.report.get('buck_response',{}).get('phase')!='active'
            or (value^self.misc['value'])&~0x20):return False
        self.misc['value']=value;self.state['force_writes']+=1
        if self.state['phase']=='initial':self.state['phase']='clock-requested'
        self.refresh();return True

    def write_mode(self,size,value):
        self.refresh();old=self.state['mode_word']
        if (size!=4 or self.report.get('buck_response',{}).get('phase')!='active'
            or value&3!=2 or value&~3!=old&~3 or not self.state['hfrc2_ready']):return False
        status=(old>>3)&3
        ack=self.state['profile']!='no-ack'
        target=status if self.state['profile'] in ('no-ack','denied') else 2
        self.state['mode_word']=2|(4 if ack else 0)|(target<<3)
        self.state['mode_writes']+=1
        self.state['transitions']+=int(target!=status)
        self.state['phase']='pending' if not ack else 'acked' if target==2 else 'denied'
        self.refresh();return True
