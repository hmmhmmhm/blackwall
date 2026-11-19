"""Observed CLKGEN control storage only; no oscillator, frequency or readiness model."""
from unicorn import arm_const as arm


class ClockGateStorage:
    def __init__(self, cpu, report, response=None):
        registers = {0x44: {'name': 'MISC', 'value': 0, 'allowed': (0, 0xfbbfc0), 'reads': 0, 'writes': 0},
                     0x120: {'name': 'CLKCTRL', 'value': 0, 'allowed': (0,), 'reads': 0, 'writes': 0}}
        report['models'].append('clock-gate-control-storage-only')
        report['clock_gate_storage'] = {
            'registers': {hex(0x40004000+offset): item for offset,item in registers.items()},
            'initial_state': 'synthetic zero control values, not observed device state',
            'frequency_and_readiness': 'not-modeled', 'hardware_verified': False}
        if response is not None:
            response.misc=registers[0x44];response.refresh()
            report['clock_gate_storage']['frequency_and_readiness']='explicit digital response; physical frequency unmodeled'

        def reject(uc, offset, size, kind, value=None):
            report['reason'] = 'unsupported-clock-access'
            report['access'] = {'kind': kind, 'address': hex(0x40004000+offset),
                                'bytes': size, 'pc': hex(uc.reg_read(arm.UC_ARM_REG_PC))}
            if value is not None:
                report['access']['value'] = hex(value)
            uc.emu_stop()

        def read(uc, offset, size, _):
            if response is not None and offset==0x30:
                value=response.read_clock(size)
                if value is not None:return value
            if offset not in registers or size != 4:
                reject(uc, offset, size, 'read-unmodeled-clock-register')
                return 0
            registers[offset]['reads'] += 1
            return registers[offset]['value']

        def write(uc, offset, size, value, _):
            if response is not None and offset==0x44 and response.write_misc(size,value):
                registers[offset]['writes']+=1
                return
            if offset not in registers or size != 4 or value not in registers[offset]['allowed']:
                reject(uc, offset, size, 'write-unmodeled-clock-register-or-value', value)
                return
            registers[offset]['value'] = value
            registers[offset]['writes'] += 1
            if response is not None:response.refresh()

        cpu.mmio_map(0x40004000, 0x1000, read, None, write, None)
