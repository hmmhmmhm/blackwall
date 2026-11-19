"""Load repository-defined simulation assumptions without executing config code."""
import hashlib
import json
from pathlib import Path

PATH = Path(__file__).with_name('simulator-scenarios.json')
BOOL_OPTIONS = frozenset(('cpacr_storage', 'vtor_storage', 'system_sram', 'itcm',
                         'fast_delay', 'watchdog_step_clock', 'reset_config',
                         'fp_context_storage', 'trace_control_storage', 'devices_off',
                         'debug_port_off', 'cpu_caches_off', 'core_domains_on', 'wic_config', 'spot_control_storage', 'memory_domains_on', 'rom_powerdown_model', 'memory_retention_storage', 'shared_sram_on', 'shared_sram_retention_storage', 'shared_sram_override_storage', 'clock_gate_storage', 'adc_power_delay_storage', 'trim_reset_fixture', 'power_switch_storage', 'ton_configuration_storage', 'hal_state_storage', 'mram_auto_wakeup_storage', 'buck_override_storage', 'buck_start_storage', 'coreldo_reduction_storage', 'memldo_setup_storage', 'coherent_icache_model', 'prefetch_control_storage', 'coherent_dcache_model', 'vddf_tempco_storage'))


def load_scenario(name):
    raw = PATH.read_bytes()
    data = json.loads(raw)
    if data['schema'] != 'blackwall-simulation-scenarios/1':
        raise ValueError('Unsupported simulation scenario schema')
    try:
        entry = data['scenarios'][name]
    except KeyError:
        raise ValueError('Unknown simulation scenario') from None
    options = entry['options']
    if set(options) - BOOL_OPTIONS - {'reset_latch', 'power_mode', 'shadow_info1', 'trim_revision_fixture', 'info1_metadata_fixture', 'chip_revision_fixture', 'buck_status_fixture', 'buck_response_model', 'mcu_clock_response'}:
        raise ValueError('Unknown scenario option')
    if any(type(options[k]) is not bool for k in BOOL_OPTIONS if k in options):
        raise ValueError('Scenario switches must be booleans')
    if options.get('trim_revision_fixture') not in (None, 'zero', 'erased'):
        raise ValueError('Invalid trim fixture')
    if options.get('info1_metadata_fixture') not in (None, 'zero', 'erased'):
        raise ValueError('Invalid Info1 metadata fixture')
    if options.get('trim_revision_fixture') is not None and options.get('info1_metadata_fixture') is not None:
        raise ValueError('Choose one Info1 fixture scope')
    if 'chip_revision_fixture' in options and (type(options['chip_revision_fixture']) is not int or options['chip_revision_fixture'] not in (0x21, 0x22, 0x23, 0x24)):
        raise ValueError('Invalid synthetic chip revision')
    if options.get('mcu_clock_response') not in (None,'nominal','hfrc2-unready','no-ack','denied'):
        raise ValueError('Invalid MCU clock response')
    if options.get('buck_response_model') not in (None,'active','stuck-off'):
        raise ValueError('Invalid buck response model')
    if options.get('buck_status_fixture') not in (None,'off','lp','active'):
        raise ValueError('Invalid buck status fixture')
    if options.get('shadow_info1') not in (None, 'mram', 'otp'):
        raise ValueError('Invalid shadow source scenario')
    if options.get('power_mode') not in ('lp', 'hp'):
        raise ValueError('Explicit power mode required')
    if type(options.get('reset_latch')) is not int or not 0 <= options['reset_latch'] <= 0x1fff:
        raise ValueError('Explicit 13-bit latch required')
    if type(entry['instructions']) is not int or not 1 <= entry['instructions'] <= 10000000:
        raise ValueError('Invalid scenario instruction budget')
    if type(entry['timeout_us']) is not int or not 1 <= entry['timeout_us'] <= 30000000:
        raise ValueError('Invalid scenario wall timeout')
    return dict(options), {'name': name, 'catalog_sha256': hashlib.sha256(raw).hexdigest(),
                           'description': entry['description'],
                           'instructions': entry['instructions'], 'timeout_us': entry['timeout_us']}
