"""Explicit register-storage models; not a full ARM system-control model."""
import unicorn as u
from unicorn import arm_const as arm
from simulator_icache import CoherentICache
from simulator_prefetch import PrefetchStorage


class CoreDomainsOn:
    """CPDLPSTATE all-ON scenario, no retention or power-off transition."""
    def __init__(self, cpu, report, *, prefetch_control_storage=False):
        prefetch=PrefetchStorage(report) if prefetch_control_storage else None
        state = {'initial': '0x0', 'final': '0x0', 'reads': 0, 'writes': 0,
                 'hardware_verified': False, 'power_transitions_security': 'not-modeled'}
        report['core_domains'] = state
        report['models'].append('hypothetical-core-epu-ram-on')

        def reject(uc, offset, size, kind):
            report['reason'] = 'unsupported-core-power-access'
            report['access'] = {'kind': kind, 'address': hex(0xe001e000+offset),
                                'bytes': size, 'pc': hex(uc.reg_read(arm.UC_ARM_REG_PC))}
            uc.emu_stop()

        def read(uc, offset, size, _):
            if prefetch is not None:
                value=prefetch.read(0xe001e000+offset,size)
                if value is not None:return value
            if offset != 0x300 or size != 4:
                reject(uc, offset, size, 'read-unmodeled-core-power-register')
                return 0
            state['reads'] += 1
            return 0

        def write(uc, offset, size, value, _):
            if prefetch is not None and prefetch.write(0xe001e000+offset,size,value):return
            if offset != 0x300 or size != 4 or value != 0:
                reject(uc, offset, size, 'core-power-transition-unmodeled')
                return
            state['writes'] += 1

        cpu.mmio_map(0xe001e000, 0x1000, read, None, write, None)


class DebugPortOff:
    """Selected MCUCTRL scenarios only, not a full MCUCTRL device model."""
    def __init__(self, cpu, report, *, wic_config=False, shadow_info1=None, chip_revision_fixture=None, spot_control_storage=False, adc_power_delay_storage=False, trim_fixture=None, power_switch_storage=False, buck_override_storage=False, buck_start_fixture=None, coreldo_reduction=None, memldo_setup=None, vddf_tempco=None):
        state = {'initial': '0x0', 'final': '0x0', 'reads': 0, 'writes': 0,
                 'hardware_verified': False, 'trace_clock': 'not-modeled'}
        report['debug_port'] = state
        report['models'].append('hypothetical-tpiu-port-off')
        switches = {0x37c: {'name': 'PWRSW0', 'value': 0x80, 'allowed': (0x80, 0x40000080), 'reads': 0, 'writes': 0},
                    0x380: {'name': 'PWRSW1', 'value': 0, 'allowed': (0, 0x10000, 0x11000), 'reads': 0, 'writes': 0}}
        if power_switch_storage:
            report['models'].append('power-switch-static-select-storage-only')
            report['power_switch_storage'] = {'registers': {hex(0x40020000+o): r for o,r in switches.items()},
                'initial_state': 'documented reset bits used as synthetic fixture',
                'rail_switching_voltage_and_readiness': 'not-modeled', 'hardware_verified': False}
        if adc_power_delay_storage:
            report['models'].append('adc-power-delay-storage-only')
            report['adc_power_delay'] = {'initial': '0x200', 'value': '0x200', 'reads': 0, 'writes': 0,
                'initial_state': 'documented reset bits used as synthetic fixture',
                'adc_power_conversion_and_timing': 'not-modeled', 'hardware_verified': False}
        spot_registers = {0x28: {'name': 'ACRG', 'value': 0x78, 'allowed': (0x78, 0x79), 'reads': 0, 'writes': 0},
                          0x60: {'name': 'VRCTRL', 'value': 0, 'allowed': (0, 0x8000, 0xc000, 0xe000), 'reads': 0, 'writes': 0}}
        if spot_control_storage:
            report['models'].append('spot-control-storage-only')
            report['spot_control_storage'] = {'registers': {hex(0x40020000+offset): item for offset,item in spot_registers.items()},
                'initial_state': 'documented reset values used as synthetic fixture, not observed device state',
                'analog_power': 'not-modeled', 'voltage_stability': 'not-modeled', 'hardware_verified': False}
        buck_steps=(0x2e000,0x6e000,0xee000,0xfe000,0xfe000,0xfe00e,0xfe00f,0xfe00f,0xfe1cf,0xfe1ef)
        buck={'steps_completed':0,'sequence_length':len(buck_steps),'complete':False,
              'analog_voltage_switching_and_deep_sleep':'not-modeled','hardware_verified':False}
        if buck_override_storage:
            report['models'].append('ordered-buck-ldo-override-storage-only')
            report['buck_override_storage']=buck
        if chip_revision_fixture is not None:
            if type(chip_revision_fixture) is not int or chip_revision_fixture not in (0x21, 0x22, 0x23, 0x24):
                raise ValueError('Unsupported synthetic chip revision')
            report['models'].append('synthetic-chiprev-read-only')
            report['chip_revision_fixture'] = {'value': hex(chip_revision_fixture), 'reads': 0,
                                                'hardware_verified': False, 'sipart': 'assumed-zero'}
        if shadow_info1 not in (None, 'mram', 'otp'):
            raise ValueError('Unknown Info1 source scenario')
        shadow_value = 1 | (8 if shadow_info1 == 'otp' else 0)
        if shadow_info1 is not None:
            report['models'].append('hypothetical-shadow-info1-source')
            report['shadow_info1'] = {'source': shadow_info1, 'value': hex(shadow_value),
                                      'reads': 0, 'hardware_verified': False,
                                      'otp_and_information_data': 'not-provided',
                                      'valid_bit': 'assumed-set', 'other_bits': 'assumed-zero'}
        wic = {'value': '0x0', 'reads': 0, 'writes': 0, 'sleep_wakeup': 'not-modeled'}
        if wic_config:
            report['wic_config'] = wic
            report['models'].append('wic-config-storage-only')

        def reject(uc, offset, size, kind):
            report['reason'] = 'unsupported-mcuctrl-access'
            report['access'] = {'kind': kind, 'address': hex(0x40020000+offset),
                                'bytes': size, 'pc': hex(uc.reg_read(arm.UC_ARM_REG_PC))}
            uc.emu_stop()

        def read(uc, offset, size, _):
            if buck_start_fixture is not None:
                result=buck_start_fixture.read(0x40020000+offset,size)
                if result is not None:return result
            if power_switch_storage and offset in switches and size == 4:
                switches[offset]['reads'] += 1
                return switches[offset]['value']
            if trim_fixture is not None:
                fixture_value = trim_fixture.read(0x40020000+offset, size)
                if fixture_value is not None:
                    return fixture_value
            if adc_power_delay_storage and offset == 0x448 and size == 4:
                report['adc_power_delay']['reads'] += 1
                return int(report['adc_power_delay']['value'], 16)
            if spot_control_storage and offset in spot_registers and size == 4:
                spot_registers[offset]['reads'] += 1
                return spot_registers[offset]['value']
            if chip_revision_fixture is not None and offset == 12 and size == 4:
                report['chip_revision_fixture']['reads'] += 1
                return chip_revision_fixture
            if shadow_info1 is not None and offset == 0x1bc and size == 4:
                report['shadow_info1']['reads'] += 1
                return shadow_value
            if wic_config and offset == 0x21c and size == 4:
                wic['reads'] += 1
                return int(wic['value'], 16)
            if offset != 0x250 or size != 4:
                reject(uc, offset, size, 'read-unmodeled-mcuctrl-register')
                return 0
            state['reads'] += 1
            return 0

        def write(uc, offset, size, value, _):
            if vddf_tempco is not None and vddf_tempco.write(0x40020000+offset,size,value):return
            if memldo_setup is not None and memldo_setup.write(0x40020000+offset,size,value):return
            if coreldo_reduction is not None and coreldo_reduction.write(0x40020000+offset,size,value):return
            if buck_start_fixture is not None and buck_start_fixture.write(0x40020000+offset,size,value):return
            if power_switch_storage and offset in switches and size == 4 and value in switches[offset]['allowed']:
                switches[offset]['value'] = value
                switches[offset]['writes'] += 1
                return
            if adc_power_delay_storage and offset == 0x448 and size == 4 and value in (0x200, 0x400):
                report['adc_power_delay']['value'] = hex(value)
                report['adc_power_delay']['writes'] += 1
                return
            if buck_override_storage and offset == 0x60 and size == 4:
                register=spot_registers[0x60];step=buck['steps_completed']
                legacy=step==0 and value in register['allowed']
                ordered=(step<len(buck_steps) and value==buck_steps[step]
                         and (step>0 or register['value']==0xe000))
                if legacy or ordered:
                    register['value']=value;register['writes']+=1
                    if ordered:
                        buck['steps_completed']+=1
                        buck['complete']=buck['steps_completed']==len(buck_steps)
                    return
                reject(uc,offset,size,'write-buck-override-order-unmodeled')
                report['access']['value']=hex(value)
                return
            if spot_control_storage and offset in spot_registers and size == 4 and value in spot_registers[offset]['allowed']:
                spot_registers[offset]['value'] = value
                spot_registers[offset]['writes'] += 1
                return
            if wic_config and offset == 0x21c and size == 4 and value in (0, 1):
                wic['value'] = hex(value)
                wic['writes'] += 1
                return
            if offset != 0x250 or size != 4 or value != 0:
                reject(uc, offset, size, 'write-unmodeled-debug-port-state')
                report['access']['value'] = hex(value)
                return
            state['writes'] += 1

        cpu.mmio_map(0x40020000, 0x1000, read, None, write, None)


class ResetConfigStorage:
    """CFG storage only; reset requests and reset propagation remain unsupported."""
    def __init__(self, cpu, report):
        state = {'initial_cfg': '0x0', 'final_cfg': '0x0', 'reads': 0, 'writes': 0,
                 'device_state_verified': False, 'reset_propagation': 'not-modeled'}
        report['reset_config'] = state
        report['models'].append('hypothetical-reset-config-storage')

        def reject(uc, offset, size, kind):
            report['reason'] = 'unsupported-reset-access'
            report['access'] = {'kind': kind, 'address': hex(0x40000000+offset),
                                'bytes': size, 'pc': hex(uc.reg_read(arm.UC_ARM_REG_PC))}
            uc.emu_stop()

        def read(uc, offset, size, _):
            if offset or size != 4:
                reject(uc, offset, size, 'read-unmodeled-reset-register')
                return 0
            state['reads'] += 1
            return int(state['final_cfg'], 16)

        def write(uc, offset, size, value, _):
            if offset or size != 4 or value & ~3:
                reject(uc, offset, size, 'reset-operation-unmodeled')
                return
            state['writes'] += 1
            state['final_cfg'] = hex(value)

        cpu.mmio_map(0x40000000, 0x1000, read, None, write, None)


class DisabledWatchdog:
    """Explicit disabled scenario; starting a timer requires a future time model."""
    def __init__(self, cpu, report):
        state = {'initial_cfg': '0x0', 'final_cfg': '0x0', 'reads': 0, 'writes': 0,
                 'device_state_verified': False, 'timeout_reset': 'not-modeled'}
        report['watchdog'] = state
        report['models'].append('hypothetical-disabled-watchdog')

        def reject(uc, offset, size, kind):
            report['reason'] = 'unsupported-watchdog-access'
            report['access'] = {'kind': kind, 'address': hex(0x40024000+offset),
                                'bytes': size, 'pc': hex(uc.reg_read(arm.UC_ARM_REG_PC))}
            uc.emu_stop()

        def read(uc, offset, size, _):
            if offset != 0 or size != 4:
                reject(uc, offset, size, 'read-unmodeled-watchdog-register')
                return 0
            state['reads'] += 1
            return int(state['final_cfg'], 16)

        def write(uc, offset, size, value, _):
            if offset != 0 or size != 4 or value & 1 or value & ~0x07ffff07 or (value >> 24) == 7:
                reject(uc, offset, size, 'watchdog-configuration-requires-time-model')
                return
            state['writes'] += 1
            state['final_cfg'] = hex(value)

        cpu.mmio_map(0x40024000, 0x1000, read, None, write, None)


class ResetLatchScenario:
    """Selected STIMER page storage; adjacent G2 reset latch remains a hypothesis."""
    def __init__(self, cpu, report, initial, *, hal_state_storage=False):
        if not 0 <= initial <= 0x1fff:
            raise ValueError('Reset latch scenario must fit the observed 13-bit mask')
        self.value = initial
        state = {'initial': hex(initial), 'final': hex(initial), 'reads': 0, 'writes': 0,
                 'hardware_verified': False, 'meaning': 'hypothesized-reset-status-shadow'}
        report['reset_latch_scenario'] = state
        report['models'].append('hypothetical-g2-reset-latch')
        hal_state = {'initial': '0x0', 'value': '0x0', 'reads': 0, 'writes': 0,
                     'initial_state': 'documented reset bits used as synthetic fixture',
                     'clock_mux_recovery': 'not-modeled', 'hardware_verified': False}
        if hal_state_storage:
            report['models'].append('hal-state-signature-storage-only')
            report['hal_state_storage'] = hal_state

        def reject(uc, offset, size, kind):
            report['reason'] = 'unsupported-latch-access'
            report['access'] = {'kind': kind, 'address': hex(0x40008000+offset),
                                'bytes': size, 'pc': hex(uc.reg_read(arm.UC_ARM_REG_PC))}
            uc.emu_stop()

        def read(uc, offset, size, _):
            if hal_state_storage and offset == 0x858 and size == 4:
                hal_state['reads'] += 1
                return int(hal_state['value'], 16)
            if offset != 0x85c or size != 4:
                reject(uc, offset, size, 'read-unmodeled-register')
                return 0
            state['reads'] += 1
            return self.value

        def write(uc, offset, size, value, _):
            if hal_state_storage and offset == 0x858 and size == 4 and value in (0, 0x5af00000):
                hal_state['value'] = hex(value)
                hal_state['writes'] += 1
                return
            if offset != 0x85c or size != 4 or not self.value & 2 or value != self.value & ~4:
                reject(uc, offset, size, 'write-unobserved-latch-transition')
                return
            self.value = value
            state['final'] = hex(value)
            state['writes'] += 1

        cpu.mmio_map(0x40008000, 0x1000, read, None, write, None)


class PowerModeRead:
    """Hypothetical power metadata; only the explicit ROM-disable model can transition."""
    def __init__(self, cpu, report, mode, *, devices_off=False, memory_domains_on=False, rom_powerdown_model=False, memory_retention_storage=False, shared_sram_on=False, shared_sram_retention_storage=False, shared_sram_override_storage=False, trim_fixture=None, ton_configuration_storage=False, mram_auto_wakeup_storage=False, buck_start_fixture=None, mcu_clock_response=None):
        if mode not in ('lp', 'hp'):
            raise ValueError('Unknown power scenario')
        value = {'lp': 0x0d, 'hp': 0x16}[mode]
        state = {'scenario': mode, 'value': hex(value), 'reads': 0,
                 'device_state_verified': False, 'transitions': 'not-modeled',
                 'other_bits': 'assumed-zero'}
        report['power_mode'] = state
        if mcu_clock_response is not None:
            state['transitions']='explicit performance response profile; not physical frequency/power'
        report['models'].append('hypothetical-stable-power-mode')
        ton = {offset: {'name': name, 'value': 0, 'allowed': (0, configured), 'reads': 0, 'writes': 0}
               for offset, name, configured in (
                   (0x1a0, 'TONCNTRCTRL', 0x3e80000), (0x1a4, 'LPOVRTHRESHVDDS', 0x320),
                   (0x1a8, 'LPOVRHYSTCNT', 0), (0x1ac, 'LPOVRTHRESHVDDF', 0x1c2),
                   (0x1b4, 'LPOVRTHRESHVDDC', 0x258), (0x1bc, 'LPOVRTHRESHVDDCLV', 0xfa))}
        if ton_configuration_storage:
            report['models'].append('ton-configuration-storage-only')
            report['ton_configuration'] = {
                'registers': {hex(0x40021000+offset): register for offset, register in ton.items()},
                'initial_state': 'documented zero reset bits used as synthetic fixture',
                'counter_clock_comparator_and_voltage_effects': 'not-modeled',
                'lp_override_enable': 'unsupported', 'hardware_verified': False}
        if shared_sram_override_storage:
            report['models'].append('shared-sram-override-storage-only')
            report['shared_sram_override'] = {'initial': '0x1b0c', 'value': '0x1b0c', 'reads': 0, 'writes': 0,
                'initial_state': 'documented reset bits used as synthetic fixture',
                'power_and_retention_effects': 'not-modeled', 'hardware_verified': False}
        if shared_sram_on:
            report['models'].append('hypothetical-shared-sram-all-on')
            report['shared_sram_power'] = {'enable': '0x7', 'status': '0x7', 'reads': 0,
                'unchanged_enable_writes': 0, 'hardware_verified': False, 'transitions': 'not-modeled'}
        if shared_sram_retention_storage:
            report['models'].append('shared-sram-retention-config-storage-only')
            report['shared_sram_retention'] = {'initial': '0x7e38', 'value': '0x7e38', 'reads': 0, 'writes': 0,
                'initial_state': 'documented reset bits used as synthetic fixture',
                'sleep_and_retention': 'not-modeled', 'hardware_verified': False}
        if memory_retention_storage:
            report['models'].append('memory-retention-config-storage-only')
            report['memory_retention'] = {'initial': '0x2', 'value': '0x2', 'reads': 0, 'writes': 0,
                'initial_state': 'documented reset bits used as synthetic fixture',
                'sleep_and_retention': 'not-modeled', 'hardware_verified': False}
        if rom_powerdown_model and not memory_domains_on:
            raise ValueError('ROM powerdown model requires memory power fixture')
        if memory_domains_on:
            report['models'].append('hypothetical-tcm-nvm-rom-on')
            report['memory_power'] = {'enable': '0x3f', 'status': '0xcf',
                'enable_reads': 0, 'status_reads': 0, 'unchanged_enable_writes': 0,
                'initial_state': 'synthetic stable TCM/NVM0/NVM1/ROM on; cache off',
                'hardware_verified': False, 'transitions': 'not-modeled',
                'rom_contents_and_system_sram_power': 'not-modeled'}
            if rom_powerdown_model:
                report['models'].append('single-rom-powerdown-zero-latency-hypothesis')
                report['memory_power']['transitions'] = 'single ROM-disable transition, zero-latency hypothesis'
                report['memory_power']['rom_disable_events'] = 0
        mram = {'initial':'0x2','value':'0x2','reads':0,'writes':0,
                'initial_state':'public reset word used as synthetic fixture',
                'wake_latency_power_recall_and_memory_contents':'not-modeled','hardware_verified':False}
        if mram_auto_wakeup_storage:
            report['models'].append('mram-auto-wakeup-control-storage-only')
            report['mram_auto_wakeup_storage'] = mram
        if devices_off:
            report['models'].append('hypothetical-peripheral-domains-off')
            report['device_power'] = {'enable': '0x0', 'status': '0x0', 'reads': 0,
                                      'device_state_verified': False, 'transitions': 'not-modeled'}

        def reject(uc, offset, size, kind):
            report['reason'] = 'unsupported-power-access'
            report['access'] = {'kind': kind, 'address': hex(0x40021000+offset),
                                'bytes': size, 'pc': hex(uc.reg_read(arm.UC_ARM_REG_PC))}
            uc.emu_stop()

        def read(uc, offset, size, _):
            if buck_start_fixture is not None:
                address=0x40021000+offset
                sample=buck_start_fixture.sample_status(address,size)
                if sample is not None:return sample
                if buck_start_fixture.blocks_readiness(address):
                    reject(uc,offset,size,'read-buck-readiness-unmodeled')
                    return 0
                result=buck_start_fixture.read(address,size)
                if result is not None:return result
            if mram_auto_wakeup_storage and offset == 0x1c8 and size == 4:
                mram['reads'] += 1
                return int(mram['value'],16)
            if ton_configuration_storage and offset in ton and size == 4:
                ton[offset]['reads'] += 1
                return ton[offset]['value']
            if trim_fixture is not None:
                fixture_value = trim_fixture.read(0x40021000+offset, size)
                if fixture_value is not None:
                    return fixture_value
            if shared_sram_override_storage and offset == 0x40 and size == 4:
                report['shared_sram_override']['reads'] += 1
                return int(report['shared_sram_override']['value'], 16)
            if shared_sram_on and offset in (0x24, 0x28) and size == 4:
                report['shared_sram_power']['reads'] += 1
                return 7
            if shared_sram_retention_storage and offset == 0x2c and size == 4:
                report['shared_sram_retention']['reads'] += 1
                return int(report['shared_sram_retention']['value'], 16)
            if memory_retention_storage and offset == 0x1c and size == 4:
                report['memory_retention']['reads'] += 1
                return int(report['memory_retention']['value'], 16)
            if memory_domains_on and offset in (0x14, 0x18) and size == 4:
                report['memory_power']['enable_reads' if offset == 0x14 else 'status_reads'] += 1
                return int(report['memory_power']['enable' if offset == 0x14 else 'status'], 16)
            if devices_off and offset in (4, 8) and size == 4:
                report['device_power']['reads'] += 1
                return 0
            if offset != 0 or size != 4:
                reject(uc, offset, size, 'read-unmodeled-power-register')
                return 0
            state['reads'] += 1
            if mcu_clock_response is not None:
                current=mcu_clock_response.read_mode(size);state['value']=hex(current)
                return current
            return value

        def write(uc, offset, size, value, _):
            if mcu_clock_response is not None and offset==0 and mcu_clock_response.write_mode(size,value):
                state['value']=hex(mcu_clock_response.state['mode_word'])
                return
            if buck_start_fixture is not None and buck_start_fixture.write(0x40021000+offset,size,value):return
            if mram_auto_wakeup_storage and offset == 0x1c8 and size == 4 and (value == 6 or value == int(mram['value'],16)):
                mram['value'] = hex(value)
                mram['writes'] += 1
                return
            if ton_configuration_storage and offset in ton and size == 4 and value in ton[offset]['allowed']:
                ton[offset]['writes'] += 1
                ton[offset]['value'] = value
                return
            if shared_sram_override_storage and offset == 0x40 and size == 4 and value in (0x1b0c, 0x30c, 0xc):
                report['shared_sram_override']['value'] = hex(value)
                report['shared_sram_override']['writes'] += 1
                return
            if shared_sram_on and offset == 0x24 and size == 4 and value == 7:
                report['shared_sram_power']['unchanged_enable_writes'] += 1
                return
            if shared_sram_retention_storage and offset == 0x2c and size == 4 and not value & ~0x7e3f:
                report['shared_sram_retention']['value'] = hex(value)
                report['shared_sram_retention']['writes'] += 1
                return
            if memory_retention_storage and offset == 0x1c and size == 4 and value in (0, 1, 2, 3):
                report['memory_retention']['value'] = hex(value)
                report['memory_retention']['writes'] += 1
                return
            if memory_domains_on and offset == 0x14 and size == 4:
                memory = report['memory_power']
                if value == int(memory['enable'], 16):
                    memory['unchanged_enable_writes'] += 1
                    return
                if rom_powerdown_model and value == 0x1f and memory['enable'] == '0x3f':
                    memory['enable'], memory['status'] = '0x1f', '0x4f'
                    memory['rom_disable_events'] += 1
                    return
            if devices_off and offset == 4 and size == 4 and value == 0:
                return
            reject(uc, offset, size, 'write-power-transition-unmodeled')
            report['access']['value'] = hex(value)

        cpu.mmio_map(0x40021000, 0x1000, read, None, write, None)


class CpacrStorage:
    PAGE = 0xe000e000
    OFFSET = 0xd88
    MASK = 0xf00000

    def __init__(self, cpu, report, *, vtor_storage=False, fp_context_storage=False, trace_control_storage=False, cpu_caches_off=False, coherent_icache_model=False, coherent_dcache_model=False):
        if coherent_dcache_model and not coherent_icache_model:
            raise ValueError('Coherent data cache requires coherent instruction cache')
        self.value = 0
        self.report = report
        self.events = []
        self.vtor_storage = vtor_storage
        self.vtor = 0
        self.fp_context_storage = fp_context_storage
        self.fpccr = 0
        self.trace_control_storage = trace_control_storage
        self.demcr = 0
        self.cpu_caches_off = cpu_caches_off
        if cpu_caches_off:
            report['models'].append('hypothetical-ccr-cache-off-read')
            report['ccr_scenario'] = {'value': '0x0', 'reads': 0,
                                      'other_fields': 'assumed-zero', 'cache_behavior': 'not-modeled'}
        self.icache=CoherentICache(report) if coherent_icache_model else None
        from simulator_dcache import CoherentDCache
        self.dcache=CoherentDCache(report) if coherent_dcache_model else None
        if self.icache is not None:
            report['ccr_scenario']['cache_behavior']='explicit coherent instruction memory model'
        if trace_control_storage:
            report['models'].append('demcr-trcena-storage-only')
            report['demcr'] = {'initial': '0x0', 'final': '0x0', 'reads': 0, 'writes': 0,
                               'trace_and_cycle_counter': 'not-modeled'}
        if fp_context_storage:
            report['models'].append('fpccr-control-storage-only')
            report['fpccr'] = {'initial': '0x0', 'final': '0x0', 'events': [],
                               'exception_context_preservation': 'not-modeled'}
        if vtor_storage:
            report['models'].append('vtor-storage-only')
            report['vtor'] = {'initial': '0x0', 'final': '0x0', 'events': [],
                              'interrupt_dispatch': 'not-modeled'}
        report['models'].append('cpacr-storage-only')
        report['cpacr'] = {'initial': '0x0', 'final': '0x0', 'events': self.events,
                           'access_permission_enforcement': 'not-modeled',
                           'exceptions_and_privilege': 'not-modeled'}
        cpu.mmio_map(self.PAGE, 0x1000, self.read, None, self.write, None)

    def reject(self, cpu, offset, size, kind):
        self.report['reason'] = 'unsupported-register-access'
        self.report['access'] = {'kind': kind, 'address': hex(self.PAGE + offset),
                                'bytes': size, 'pc': hex(cpu.reg_read(arm.UC_ARM_REG_PC))}
        cpu.emu_stop()

    def read(self, cpu, offset, size, _):
        if self.cpu_caches_off and offset == 0xd14 and size == 4:
            self.report['ccr_scenario']['reads'] += 1
            value=self.icache.read(offset,size) if self.icache is not None else 0
            if self.dcache is not None:
                value |= self.dcache.read(offset,size)
            self.report['ccr_scenario']['value']=hex(value)
            return value
        if self.dcache is not None:
            value=self.dcache.read(offset,size)
            if value is not None:return value
        if self.trace_control_storage and offset == 0xdfc and size == 4:
            self.report['demcr']['reads'] += 1
            return self.demcr
        if self.fp_context_storage and offset == 0xf34 and size == 4:
            self.report['fpccr']['events'].append({'operation': 'read', 'value': hex(self.fpccr)})
            return self.fpccr
        if self.vtor_storage and offset == 0xd08 and size == 4:
            self.report['vtor']['events'].append({'operation': 'read', 'value': hex(self.vtor)})
            return self.vtor
        if offset != self.OFFSET or size != 4:
            self.reject(cpu, offset, size, 'read-unmodeled-register')
            return 0
        self.events.append({'operation': 'read', 'value': hex(self.value),
                            'pc': hex(cpu.reg_read(arm.UC_ARM_REG_PC))})
        return self.value

    def write(self, cpu, offset, size, value, _):
        if self.dcache is not None:
            if offset==0xd14:
                if (size==4 and value & ~0x30000==0
                    and (not value & 0x20000 or self.icache.state['invalidations'])
                    and self.dcache.can_set_enabled(bool(value & 0x10000))):
                    self.icache.write(offset,size,value & 0x20000)
                    self.dcache.write(offset,size,value & 0x10000)
                    self.report['ccr_scenario']['value']=hex(value)
                    return
                self.reject(cpu,offset,size,'write-unmodeled-register-or-value')
                self.report['access']['value']=hex(value)
                return
            if self.dcache.write(offset,size,value):return
        if self.icache is not None and self.icache.write(offset,size,value):
            self.report['ccr_scenario']['value']=hex(self.icache.state['ccr'])
            return
        if self.trace_control_storage and offset == 0xdfc and size == 4 and value in (0, 0x1000000):
            self.demcr = value
            self.report['demcr']['final'] = hex(value)
            self.report['demcr']['writes'] += 1
            return
        if self.fp_context_storage and offset == 0xf34 and size == 4 and value in (0, 0x80000000, 0xc0000000):
            self.fpccr = value
            self.report['fpccr']['final'] = hex(value)
            self.report['fpccr']['events'].append({'operation': 'write', 'value': hex(value)})
            return
        if self.vtor_storage and offset == 0xd08 and size == 4 and value == 0x438000:
            self.vtor = value
            self.report['vtor']['final'] = hex(value)
            self.report['vtor']['events'].append({'operation': 'write', 'value': hex(value)})
            return
        if offset != self.OFFSET or size != 4 or value not in (0, self.MASK):
            self.reject(cpu, offset, size, 'write-unmodeled-register-or-value')
            self.report['access']['value']=hex(value)
            return
        self.value = value
        self.report['cpacr']['final'] = hex(value)
        self.events.append({'operation': 'write', 'value': hex(value),
                            'pc': hex(cpu.reg_read(arm.UC_ARM_REG_PC))})
