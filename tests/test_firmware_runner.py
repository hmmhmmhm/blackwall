import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from firmware_runner import run_main


def fixture(code, address=0x40000000):
    return struct.pack('<II', 0x2007fb00, 0x438009) + bytes.fromhex(code) + struct.pack('<I', address)


def buck_fixture(values):
    code=bytes.fromhex('0449054a')+bytes((len(values),0x23))+bytes.fromhex('106804320860013bfad10868fee7')
    return (struct.pack('<II',0x2007fb00,0x438009)+code
            +struct.pack('<II',0x40020060,0x438024)
            +struct.pack('<'+'I'*len(values),*values))


def register_pair_fixture(pairs,ready_read=False):
    code=bytes.fromhex('054a')+bytes((len(pairs),0x23))+bytes.fromhex('11680432106804320860013bf8d1')+bytes.fromhex('08310868fee7' if ready_read else '0868fee700bf')
    return (struct.pack('<II',0x2007fb00,0x438009)+code+struct.pack('<I',0x438024)
            +b''.join(struct.pack('<II',*pair) for pair in pairs))


class RunnerTests(unittest.TestCase):
    def test_mcu_clock_requires_explicit_dependencies_before_image_execution(self):
        for options in ({'mcu_clock_response':'nominal'},
                        {'mcu_clock_response':'unknown'},
                        {'mcu_clock_response':'nominal','clock_gate_storage':True,
                         'buck_response_model':'active','vddf_tempco_storage':True},
                        {'mcu_clock_response':'nominal','clock_gate_storage':True,
                         'buck_response_model':'stuck-off','vddf_tempco_storage':True,'power_mode':'lp'}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                run_main(b'', **options)

    def test_buck_response_and_vddf_options_require_explicit_dependencies(self):
        for options in ({'buck_response_model':'active'},
                        {'buck_response_model':'lp'},
                        {'buck_response_model':'active','memldo_setup_storage':True,'buck_status_fixture':'lp'},
                        {'vddf_tempco_storage':True}):
            with self.assertRaises(ValueError):run_main(fixture('fee7'),20,**options)

    def test_coherent_dcache_requires_instruction_memory_and_full_sweep(self):
        with self.assertRaisesRegex(ValueError, 'data cache'):
            run_main(fixture('fee7'), 20, coherent_dcache_model=True)
        pairs=[(0xe000ef50,0),(0xe000ed84,0),(0xe000ef60,0),(0xe000ed14,0x30000)]
        report=run_main(register_pair_fixture(pairs),100,cpacr_storage=True,cpu_caches_off=True,
                        coherent_icache_model=True,coherent_dcache_model=True)
        self.assertEqual(report['reason'],'unsupported-register-access')
        self.assertFalse(report['coherent_dcache']['enabled'])
        self.assertEqual(report['coherent_dcache']['initialized_lines'],1)
        self.assertEqual(report['coherent_icache']['ccr'],0)

    def test_prefetch_requires_core_adapter_and_roundtrips_explicit_zero(self):
        with self.assertRaisesRegex(ValueError, 'Prefetch'):
            run_main(fixture('fee7'),20,prefetch_control_storage=True)
        r=run_main(register_pair_fixture([(0xe001e004,0x369),(0xe001e004,0)]),100,
                   core_domains_on=True,prefetch_control_storage=True)
        self.assertEqual(r['prefetch_storage']['value'],0)
        self.assertEqual(r['prefetch_storage']['writes'],2)
        self.assertEqual(r['prefetch_storage']['reads'],1)
        self.assertEqual(r['registers']['r0'],'0x0')

    def test_coherent_icache_requires_explicit_cpacr_and_baseline(self):
        for options in ({},{'cpacr_storage':True},{'cpu_caches_off':True}):
            with self.assertRaisesRegex(ValueError, 'Coherent instruction cache'):
                run_main(fixture('fee7'),20,coherent_icache_model=True,**options)

    def test_buck_status_requires_explicit_memory_setup(self):
        with self.assertRaisesRegex(ValueError, 'Buck status'):
            run_main(fixture('fee7'),20,buck_status_fixture='active')

    def test_memldo_setup_requires_core_reduction_model(self):
        with self.assertRaisesRegex(ValueError, 'Memory LDO'):
            run_main(fixture('fee7'),20,memldo_setup_storage=True)

    def test_coreldo_reduction_requires_explicit_start_and_trim_models(self):
        with self.assertRaises(ValueError):run_main(fixture('fee7'),20,coreldo_reduction_storage=True)
        with self.assertRaises(ValueError):run_main(fixture('fee7'),20,coreldo_reduction_storage=True,buck_start_storage=True)

    def test_buck_start_observed_requests_keep_readiness_unmodeled(self):
        vr=(0xe000,0x2e000,0x6e000,0xee000,0xfe000,0xfe000,0xfe00e,0xfe00f,0xfe00f,0xfe1cf,0xfe1ef)
        pairs=[(0x40020060,v) for v in vr]+[(0x40020378,0x80000000),(0x4002033c,0xf),(0x40021100,1)]
        r=run_main(register_pair_fixture(pairs),500,debug_port_off=True,spot_control_storage=True,
                   buck_override_storage=True,power_mode='lp',buck_start_storage=True)
        self.assertEqual(r['registers']['r0'],'0x1')
        self.assertEqual(r['buck_start_storage']['steps_completed'],3)
        self.assertTrue(r['buck_start_storage']['enable_requested'])
        self.assertFalse(r['buck_start_storage']['hardware_verified'])

    def test_buck_start_prefixes_and_wrong_requests_do_not_mutate_rejected_state(self):
        vr=(0xe000,0x2e000,0x6e000,0xee000,0xfe000,0xfe000,0xfe00e,0xfe00f,0xfe00f,0xfe1cf,0xfe1ef)
        prime=[(0x40020060,v) for v in vr]
        steps=[(0x40020378,0x80000000),(0x4002033c,0xf),(0x40021100,1)]
        options=dict(debug_port_off=True,spot_control_storage=True,buck_override_storage=True,power_mode='lp',buck_start_storage=True)
        for count in (1,2,3):
            r=run_main(register_pair_fixture(prime+steps[:count]),500,**options)
            self.assertEqual(r['buck_start_storage']['steps_completed'],count)
            self.assertEqual(r['buck_start_storage']['enable_requested'],count==3)
        for prefix,count,bad in [([],0,steps[0]),(prime,0,steps[1]),(prime,1,steps[2]),
                                  (prime,0,(0x40020378,0x80000001)),(prime,1,(0x4002033c,0x1f)),
                                  (prime,3,(0x40021100,0))]:
            r=run_main(register_pair_fixture(prefix+steps[:count]+[bad]),500,**options)
            self.assertIn(r['reason'],('unsupported-mcuctrl-access','unsupported-power-access'))
            state=r['buck_start_storage'];self.assertEqual(state['steps_completed'],count)
            self.assertEqual(sum(v['writes'] for v in state['registers'].values()),count)

    def test_buck_start_blocks_reset_fixture_as_ready_after_enable(self):
        vr=(0xe000,0x2e000,0x6e000,0xee000,0xfe000,0xfe000,0xfe00e,0xfe00f,0xfe00f,0xfe1cf,0xfe1ef)
        pairs=[(0x40020060,v) for v in vr]+[(0x40020378,0x80000000),(0x4002033c,0xf),(0x40021100,1)]
        r=run_main(register_pair_fixture(pairs,ready_read=True),500,debug_port_off=True,spot_control_storage=True,
                   buck_override_storage=True,power_mode='lp',buck_start_storage=True,trim_reset_fixture=True)
        self.assertEqual(r['access']['address'],'0x40021108')
        self.assertEqual(r['access']['kind'],'read-buck-readiness-unmodeled')
        self.assertEqual(r['trim_reset_fixture']['registers']['0x40021108']['reads'],0)
        self.assertTrue(r['buck_start_storage']['enable_requested'])
        with self.assertRaises(ValueError):run_main(fixture('fee7'),20,buck_start_storage=True)

    def test_buck_override_follows_complete_observed_sequence(self):
        values=(0xe000,0x2e000,0x6e000,0xee000,0xfe000,0xfe000,0xfe00e,0xfe00f,0xfe00f,0xfe1cf,0xfe1ef)
        r=run_main(buck_fixture(values),200,debug_port_off=True,spot_control_storage=True,buck_override_storage=True)
        self.assertEqual(r['registers']['r0'],'0xfe1ef')
        self.assertEqual(r['buck_override_storage']['steps_completed'],10)
        self.assertEqual(r['spot_control_storage']['registers']['0x40020060']['writes'],11)

    def test_buck_override_each_prefix_and_out_of_order_requests(self):
        sequence=(0x2e000,0x6e000,0xee000,0xfe000,0xfe000,0xfe00e,0xfe00f,0xfe00f,0xfe1cf,0xfe1ef)
        for count in range(1,11):
            r=run_main(buck_fixture((0xe000,)+sequence[:count]),200,
                       debug_port_off=True,spot_control_storage=True,buck_override_storage=True)
            self.assertEqual(r['buck_override_storage']['steps_completed'],count)
            self.assertEqual(r['registers']['r0'],hex(sequence[count-1]))
        for prefix,bad in [((),0x2e000),((0xe000,),0xfe000),((0xe000,0x2e000),0xee000),
                           ((0xe000,0x2e000),0x20000),((0xe000,)+sequence[:4],0xfe00e),
                           ((0xe000,)+sequence,0xfe1ef)]:
            r=run_main(buck_fixture(prefix+(bad,)),200,debug_port_off=True,
                       spot_control_storage=True,buck_override_storage=True)
            self.assertEqual(r['reason'],'unsupported-mcuctrl-access')
            self.assertEqual(r['access']['value'],hex(bad))
            reg=r['spot_control_storage']['registers']['0x40020060']
            self.assertEqual(reg['value'],prefix[-1] if prefix else 0)
            self.assertEqual(reg['writes'],len(prefix))

    def test_buck_override_requires_explicit_models_and_default_stays_guarded(self):
        with self.assertRaises(ValueError):run_main(fixture('fee7'),20,buck_override_storage=True)
        with self.assertRaises(ValueError):run_main(fixture('fee7'),20,debug_port_off=True,buck_override_storage=True)
        r=run_main(buck_fixture((0xe000,0x2e000)),100,debug_port_off=True,spot_control_storage=True)
        self.assertEqual(r['reason'],'unsupported-mcuctrl-access')
        self.assertNotIn('buck_override_storage',r)
        r=run_main(fixture('01490878fee700bf',0x40020060),20,debug_port_off=True,
                   spot_control_storage=True,buck_override_storage=True)
        self.assertEqual(r['reason'],'unsupported-mcuctrl-access')
        self.assertEqual(r['buck_override_storage']['steps_completed'],0)

    def test_rejected_mcuctrl_write_records_actual_requested_value(self):
        raw=(struct.pack('<II',0x2007fb00,0x438009)
             +bytes.fromhex('0349044808600868fee700bf00bf00bf')
             +struct.pack('<II',0x40020060,0x2e000))
        r=run_main(raw,20,debug_port_off=True,spot_control_storage=True)
        self.assertEqual(r['reason'],'unsupported-mcuctrl-access')
        self.assertEqual(r['access']['value'],'0x2e000')
        self.assertEqual(r['spot_control_storage']['registers']['0x40020060']['writes'],0)

    def test_mram_control_initial_word_is_explicit_reset_fixture(self):
        r=run_main(fixture('01490868fee700bf',0x400211c8),20,
                   power_mode='lp',mram_auto_wakeup_storage=True)
        self.assertEqual(r['registers']['r0'],'0x2')
        self.assertEqual(r['mram_auto_wakeup_storage']['reads'],1)
        self.assertFalse(r['mram_auto_wakeup_storage']['hardware_verified'])

    def test_mram_control_writes_only_unchanged_or_observed_disable(self):
        for value in (2,6):
            raw=(struct.pack('<II',0x2007fb00,0x438009)
                 +bytes.fromhex('0349044808600868fee700bf00bf00bf')
                 +struct.pack('<II',0x400211c8,value))
            r=run_main(raw,20,power_mode='lp',mram_auto_wakeup_storage=True)
            self.assertEqual(r['registers']['r0'],hex(value))
            self.assertEqual(r['mram_auto_wakeup_storage']['writes'],1)
        for value in (0,3,0xa,0x12,0x20):
            raw=(struct.pack('<II',0x2007fb00,0x438009)
                 +bytes.fromhex('0349044808600868fee700bf00bf00bf')
                 +struct.pack('<II',0x400211c8,value))
            r=run_main(raw,20,power_mode='lp',mram_auto_wakeup_storage=True)
            self.assertEqual(r['reason'],'unsupported-power-access')
            self.assertEqual(r['mram_auto_wakeup_storage']['value'],'0x2')
            self.assertEqual(r['mram_auto_wakeup_storage']['writes'],0)

    def test_mram_control_repeat_and_restore_boundary(self):
        for second in (6,2):
            raw=(struct.pack('<II',0x2007fb00,0x438009)
                 +bytes.fromhex('034904480860044808600868fee700bf')
                 +struct.pack('<III',0x400211c8,6,second))
            r=run_main(raw,30,power_mode='lp',mram_auto_wakeup_storage=True)
            self.assertEqual(r['mram_auto_wakeup_storage']['value'],'0x6')
            self.assertEqual(r['mram_auto_wakeup_storage']['writes'],2 if second==6 else 1)
            if second==2:self.assertEqual(r['reason'],'unsupported-power-access')

    def test_mram_control_partial_neighbor_default_and_missing_power_stop(self):
        for code,address in [('01490878fee700bf',0x400211c8),('01490868fee700bf',0x400211cc)]:
            r=run_main(fixture(code,address),20,power_mode='lp',mram_auto_wakeup_storage=True)
            self.assertEqual(r['reason'],'unsupported-power-access')
            self.assertEqual(r['mram_auto_wakeup_storage']['reads'],0)
        r=run_main(fixture('01490868fee700bf',0x400211c8),20,power_mode='lp')
        self.assertEqual(r['reason'],'unsupported-power-access')
        self.assertNotIn('mram_auto_wakeup_storage',r)
        with self.assertRaises(ValueError):run_main(fixture('fee7'),20,mram_auto_wakeup_storage=True)

    def test_hal_state_signature_storage_and_latch_remain_separate(self):
        r = run_main(fixture('01490868fee700bf', 0x40008858), 20,
                     reset_latch=2, hal_state_storage=True)
        self.assertEqual(r['registers']['r0'], '0x0')
        for value in (0, 0x5af00000):
            raw = (struct.pack('<II', 0x2007fb00, 0x438009)
                   + bytes.fromhex('0349044808600868fee700bf00bf00bf')
                   + struct.pack('<II', 0x40008858, value))
            r = run_main(raw, 20, reset_latch=2, hal_state_storage=True)
            self.assertEqual(r['registers']['r0'], hex(value))
            self.assertEqual(r['hal_state_storage']['writes'], 1)
            self.assertEqual(r['hal_state_storage']['clock_mux_recovery'], 'not-modeled')
            self.assertEqual(r['reset_latch_scenario']['final'], '0x2')
            self.assertEqual(r['reset_latch_scenario']['writes'], 0)

    def test_hal_state_rejects_clock_flags_wrong_signature_and_partial_access(self):
        for value in (1, 0x5af00001, 0x5af00040, 0xffff0000):
            raw = (struct.pack('<II', 0x2007fb00, 0x438009)
                   + bytes.fromhex('0349044808600868fee700bf00bf00bf')
                   + struct.pack('<II', 0x40008858, value))
            r = run_main(raw, 20, reset_latch=2, hal_state_storage=True)
            self.assertEqual(r['reason'], 'unsupported-latch-access')
            self.assertEqual(r['hal_state_storage']['value'], '0x0')
        for code, address in [('01490878fee700bf', 0x40008858),
                              ('01490868fee700bf', 0x40008860)]:
            r = run_main(fixture(code, address), 20, reset_latch=2, hal_state_storage=True)
            self.assertEqual(r['reason'], 'unsupported-latch-access')
        r = run_main(fixture('01490868fee700bf', 0x40008858), 20, reset_latch=2)
        self.assertEqual(r['reason'], 'unsupported-latch-access')
        with self.assertRaises(ValueError):
            run_main(fixture('fee7'), 20, hal_state_storage=True)

    def test_ton_configuration_stores_only_observed_setup(self):
        values = [(0x400211a0, 0x3e80000), (0x400211a4, 0x320), (0x400211a8, 0),
                  (0x400211ac, 0x1c2), (0x400211b4, 0x258), (0x400211bc, 0xfa)]
        for address, value in values:
            with self.subTest(address=hex(address)):
                r = run_main(fixture('01490868fee700bf', address), 20,
                             power_mode='lp', ton_configuration_storage=True)
                self.assertEqual(r['registers']['r0'], '0x0')
                raw = (struct.pack('<II', 0x2007fb00, 0x438009)
                       + bytes.fromhex('0349044808600868fee700bf00bf00bf')
                       + struct.pack('<II', address, value))
                r = run_main(raw, 20, power_mode='lp', ton_configuration_storage=True)
                self.assertEqual(r['registers']['r0'], hex(value))
                self.assertEqual(r['ton_configuration']['registers'][hex(address)]['writes'], 1)
                self.assertFalse(r['ton_configuration']['hardware_verified'])

    def test_ton_configuration_rejects_enable_status_and_unknown_values(self):
        for address, value in [(0x400211a0, 1), (0x400211a0, 2), (0x400211a0, 0x3e80003),
                               (0x400211a0, 0x1f00), (0x400211a8, 1), (0x400211a4, 801)]:
            raw = (struct.pack('<II', 0x2007fb00, 0x438009)
                   + bytes.fromhex('0349044808600868fee700bf00bf00bf')
                   + struct.pack('<II', address, value))
            r = run_main(raw, 20, power_mode='lp', ton_configuration_storage=True)
            self.assertEqual(r['reason'], 'unsupported-power-access')
        for code, address in [('01490878fee700bf', 0x400211a0),
                              ('01490868fee700bf', 0x400211c4)]:
            r = run_main(fixture(code, address), 20, power_mode='lp', ton_configuration_storage=True)
            self.assertEqual(r['reason'], 'unsupported-power-access')
        r = run_main(fixture('01490868fee700bf', 0x400211a0), 20, power_mode='lp')
        self.assertEqual(r['reason'], 'unsupported-power-access')
        with self.assertRaises(ValueError):
            run_main(fixture('fee7'), 20, ton_configuration_storage=True)

    def test_power_switch_storage_preserves_observed_static_select_values(self):
        for address, initial, value in [(0x4002037c, '0x80', 0x40000080), (0x40020380, '0x0', 0x11000)]:
            r = run_main(fixture('01490868fee700bf', address), 20, debug_port_off=True, power_switch_storage=True)
            self.assertEqual(r['registers']['r0'], initial)
            raw = (struct.pack('<II', 0x2007fb00, 0x438009)
                   + bytes.fromhex('0349044808600868fee700bf00bf00bf')
                   + struct.pack('<II', address, value))
            r = run_main(raw, 20, debug_port_off=True, power_switch_storage=True)
            self.assertEqual(r['registers']['r0'], hex(value))
            self.assertEqual(r['power_switch_storage']['rail_switching_voltage_and_readiness'], 'not-modeled')

    def test_power_switch_storage_rejects_unobserved_overrides_and_partial_access(self):
        for address, value in [(0x4002037c, 0x80000080), (0x40020380, 0x80000)]:
            raw = (struct.pack('<II', 0x2007fb00, 0x438009)
                   + bytes.fromhex('0349044808600868fee700bf00bf00bf')
                   + struct.pack('<II', address, value))
            r = run_main(raw, 20, debug_port_off=True, power_switch_storage=True)
            self.assertEqual(r['reason'], 'unsupported-mcuctrl-access')
        r = run_main(fixture('01490878fee700bf', 0x4002037c), 20, debug_port_off=True, power_switch_storage=True)
        self.assertEqual(r['reason'], 'unsupported-mcuctrl-access')
        with self.assertRaises(ValueError):
            run_main(fixture('fee7'), 20, power_switch_storage=True)

    def test_trim_reset_fixture_is_read_only_and_not_device_calibration(self):
        from simulator_trim_fixture import TrimResetFixture
        probe = {'models': []}
        provider = TrimResetFixture(probe)
        for address, row in provider.registers.items():
            r = run_main(fixture('01490868fee700bf', address), 20, debug_port_off=True,
                         power_mode='lp', trim_reset_fixture=True)
            self.assertEqual(r['registers']['r0'], row['value'])
            self.assertFalse(r['trim_reset_fixture']['valid_device_calibration'])
            r = run_main(fixture('01490860fee700bf', address), 20, debug_port_off=True,
                         power_mode='lp', trim_reset_fixture=True)
            self.assertIn(r['reason'], ('unsupported-mcuctrl-access', 'unsupported-power-access'))

    def test_trim_reset_fixture_rejects_partial_access_and_missing_adapters(self):
        r = run_main(fixture('01490878fee700bf', 0x4002036c), 20, debug_port_off=True,
                     power_mode='lp', trim_reset_fixture=True)
        self.assertEqual(r['reason'], 'unsupported-mcuctrl-access')
        with self.assertRaises(ValueError):
            run_main(fixture('fee7'), 20, trim_reset_fixture=True)

    def test_trim_reset_catalog_changes_require_a_new_pin(self):
        import tempfile
        from unittest.mock import patch
        from simulator_trim_fixture import TrimResetFixture
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'changed.json'
            path.write_text('{}')
            with patch('simulator_trim_fixture.CATALOG', path):
                with self.assertRaisesRegex(ValueError, 'SHA256'):
                    TrimResetFixture({'models': []})

    def test_trim_reset_derivation_rejects_different_public_source(self):
        import tempfile
        from verify_trim_reset_catalog import verify
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory)/'apollo510.h').write_text('different header')
            with self.assertRaisesRegex(ValueError, 'Public source SHA256'):
                verify(Path(directory))

    def test_adc_delay_storage_only_accepts_observed_values(self):
        r = run_main(fixture('01490868fee700bf', 0x40020448), 20, debug_port_off=True, adc_power_delay_storage=True)
        self.assertEqual(r['registers']['r0'], '0x200')
        for value in (0x400, 0x10000, 0x500):
            raw = (struct.pack('<II', 0x2007fb00, 0x438009)
                   + bytes.fromhex('0349044808600868fee700bf00bf00bf')
                   + struct.pack('<II', 0x40020448, value))
            r = run_main(raw, 20, debug_port_off=True, adc_power_delay_storage=True)
            if value == 0x400:
                self.assertEqual(r['registers']['r0'], '0x400')
                self.assertEqual(r['adc_power_delay']['adc_power_conversion_and_timing'], 'not-modeled')
            else:
                self.assertEqual(r['reason'], 'unsupported-mcuctrl-access')

    def test_adc_delay_storage_requires_mcuctrl_and_rejects_partial_reads(self):
        with self.assertRaises(ValueError):
            run_main(fixture('fee7'), 20, adc_power_delay_storage=True)
        r = run_main(fixture('01490878fee700bf', 0x40020448), 20, debug_port_off=True, adc_power_delay_storage=True)
        self.assertEqual(r['reason'], 'unsupported-mcuctrl-access')

    def test_clock_gate_control_values_are_stored_without_clock_effects(self):
        for address, value in [(0x40004044, 0xfbbfc0), (0x40004120, 0)]:
            raw = (struct.pack('<II', 0x2007fb00, 0x438009)
                   + bytes.fromhex('0349044808600868fee700bf00bf00bf')
                   + struct.pack('<II', address, value))
            r = run_main(raw, 20, clock_gate_storage=True)
            self.assertEqual(r['registers']['r0'], hex(value))
            self.assertEqual(r['clock_gate_storage']['frequency_and_readiness'], 'not-modeled')
            self.assertFalse(r['clock_gate_storage']['hardware_verified'])

    def test_clock_model_rejects_unobserved_enables_and_other_registers(self):
        for address, value in [(0x40004044, 0x1000000), (0x40004120, 1)]:
            raw = (struct.pack('<II', 0x2007fb00, 0x438009)
                   + bytes.fromhex('0349044808600868fee700bf00bf00bf')
                   + struct.pack('<II', address, value))
            r = run_main(raw, 20, clock_gate_storage=True)
            self.assertEqual(r['reason'], 'unsupported-clock-access')
        for code, address in [('01490868fee700bf', 0x40004030), ('01490878fee700bf', 0x40004044)]:
            r = run_main(fixture(code, address), 20, clock_gate_storage=True)
            self.assertEqual(r['reason'], 'unsupported-clock-access')

    def test_shared_sram_override_stores_only_observed_control_values(self):
        r = run_main(fixture('01490868fee700bf', 0x40021040), 20, power_mode='lp', system_sram=True, shared_sram_override_storage=True)
        self.assertEqual(r['registers']['r0'], '0x1b0c')
        for value in (0x30c, 0xc, 0xe, 0x400c):
            raw = (struct.pack('<II', 0x2007fb00, 0x438009)
                   + bytes.fromhex('0349044808600868fee700bf00bf00bf')
                   + struct.pack('<II', 0x40021040, value))
            r = run_main(raw, 20, power_mode='lp', system_sram=True, shared_sram_override_storage=True)
            if value in (0xe, 0x400c):
                self.assertEqual(r['reason'], 'unsupported-power-access')
            else:
                self.assertEqual(r['registers']['r0'], hex(value))
                self.assertEqual(r['shared_sram_override']['power_and_retention_effects'], 'not-modeled')

    def test_shared_sram_override_rejects_partial_access_and_missing_models(self):
        r = run_main(fixture('01490878fee700bf', 0x40021040), 20, power_mode='lp', system_sram=True, shared_sram_override_storage=True)
        self.assertEqual(r['reason'], 'unsupported-power-access')
        with self.assertRaises(ValueError):
            run_main(fixture('fee7'), 20, power_mode='lp', shared_sram_override_storage=True)

    def test_shared_sram_power_is_on_only_with_existing_sram_model(self):
        for address in (0x40021024, 0x40021028):
            r = run_main(fixture('01490868fee700bf', address), 20, power_mode='lp', system_sram=True, shared_sram_on=True)
            self.assertEqual(r['registers']['r0'], '0x7')
            self.assertFalse(r['shared_sram_power']['hardware_verified'])
        with self.assertRaises(ValueError):
            run_main(fixture('fee7'), 20, power_mode='lp', shared_sram_on=True)

    def test_shared_sram_power_changes_and_status_writes_are_rejected(self):
        for code, address in [('01490860fee700bf', 0x40021024),
                              ('01490860fee700bf', 0x40021028),
                              ('01490878fee700bf', 0x40021028)]:
            r = run_main(fixture(code, address), 20, power_mode='lp', system_sram=True, shared_sram_on=True)
            self.assertEqual(r['reason'], 'unsupported-power-access')

    def test_shared_sram_retention_storage_respects_documented_fields(self):
        r = run_main(fixture('01490868fee700bf', 0x4002102c), 20, power_mode='lp', system_sram=True, shared_sram_retention_storage=True)
        self.assertEqual(r['registers']['r0'], '0x7e38')
        for value in (0, 7, 0x7e3f, 0x40, 0x8000):
            raw = (struct.pack('<II', 0x2007fb00, 0x438009)
                   + bytes.fromhex('0349044808600868fee700bf00bf00bf')
                   + struct.pack('<II', 0x4002102c, value))
            r = run_main(raw, 20, power_mode='lp', system_sram=True, shared_sram_retention_storage=True)
            if value in (0x40, 0x8000):
                self.assertEqual(r['reason'], 'unsupported-power-access')
            else:
                self.assertEqual(r['registers']['r0'], hex(value))
                self.assertEqual(r['shared_sram_retention']['sleep_and_retention'], 'not-modeled')

    def test_memory_retention_storage_handles_only_two_config_bits(self):
        r = run_main(fixture('01490868fee700bf', 0x4002101c), 20, power_mode='lp', memory_retention_storage=True)
        self.assertEqual(r['registers']['r0'], '0x2')
        for value in (0, 1, 2, 3):
            raw = (struct.pack('<II', 0x2007fb00, 0x438009)
                   + bytes.fromhex('0349044808600868fee700bf00bf00bf')
                   + struct.pack('<II', 0x4002101c, value))
            r = run_main(raw, 20, power_mode='lp', memory_retention_storage=True)
            self.assertEqual(r['registers']['r0'], hex(value))
            self.assertEqual(r['memory_retention']['sleep_and_retention'], 'not-modeled')

    def test_retention_config_reserved_bits_partial_access_and_missing_model_stop(self):
        raw = (struct.pack('<II', 0x2007fb00, 0x438009)
               + bytes.fromhex('0349044808600868fee700bf00bf00bf')
               + struct.pack('<II', 0x4002101c, 4))
        r = run_main(raw, 20, power_mode='lp', memory_retention_storage=True)
        self.assertEqual(r['reason'], 'unsupported-power-access')
        r = run_main(fixture('01490878fee700bf', 0x4002101c), 20, power_mode='lp', memory_retention_storage=True)
        self.assertEqual(r['reason'], 'unsupported-power-access')
        with self.assertRaises(ValueError):
            run_main(fixture('fee7'), 20, memory_retention_storage=True)

    def test_retention_config_does_not_make_sleep_supported(self):
        raw = (struct.pack('<II', 0x2007fb00, 0x438009)
               + bytes.fromhex('03490448086030bffee700bf00bf00bf')
               + struct.pack('<II', 0x4002101c, 3))
        r = run_main(raw, 20, power_mode='lp', memory_retention_storage=True)
        self.assertEqual(r['reason'], 'unsupported-sleep-boundary')
        self.assertEqual(r['memory_retention']['value'], '0x3')

    def test_single_rom_disable_model_updates_only_rom_status(self):
        raw = (struct.pack('<II', 0x2007fb00, 0x438009)
               + bytes.fromhex('0349044808604868fee700bf00bf00bf')
               + struct.pack('<II', 0x40021014, 0x1f))
        r = run_main(raw, 20, power_mode='lp', memory_domains_on=True, rom_powerdown_model=True)
        self.assertEqual(r['registers']['r0'], '0x4f')
        self.assertEqual(r['memory_power']['enable'], '0x1f')
        self.assertEqual(r['memory_power']['rom_disable_events'], 1)
        self.assertFalse(r['memory_power']['hardware_verified'])

    def test_rom_reenable_and_other_memory_power_changes_are_unsupported(self):
        raw = (struct.pack('<II', 0x2007fb00, 0x438009)
               + bytes.fromhex('0349044808603f200860fee700bf00bf')
               + struct.pack('<II', 0x40021014, 0x1f))
        r = run_main(raw, 20, power_mode='lp', memory_domains_on=True, rom_powerdown_model=True)
        self.assertEqual(r['reason'], 'unsupported-power-access')
        self.assertEqual(r['access']['value'], '0x3f')
        self.assertEqual(r['memory_power']['enable'], '0x1f')
        r = run_main(raw[:-4]+struct.pack('<I', 0xf), 20, power_mode='lp', memory_domains_on=True, rom_powerdown_model=True)
        self.assertEqual(r['reason'], 'unsupported-power-access')
        self.assertEqual(r['access']['value'], '0xf')
        self.assertEqual(r['memory_power']['enable'], '0x3f')
        with self.assertRaises(ValueError):
            run_main(fixture('fee7'), 20, power_mode='lp', rom_powerdown_model=True)

    def test_memory_power_fixture_reports_stable_on_state_only(self):
        for address, value in [(0x40021014, '0x3f'), (0x40021018, '0xcf')]:
            r = run_main(fixture('01490868fee700bf', address), 20, power_mode='lp', memory_domains_on=True)
            self.assertEqual(r['registers']['r0'], value)
            self.assertFalse(r['memory_power']['hardware_verified'])
            self.assertEqual(r['memory_power']['transitions'], 'not-modeled')
        raw = (struct.pack('<II', 0x2007fb00, 0x438009)
               + bytes.fromhex('0349044808600868fee700bf00bf00bf')
               + struct.pack('<II', 0x40021014, 0x3f))
        r = run_main(raw, 20, power_mode='lp', memory_domains_on=True)
        self.assertEqual(r['memory_power']['unchanged_enable_writes'], 1)

    def test_memory_power_transitions_status_writes_and_partial_reads_stop(self):
        for code, address in [('01490860fee700bf', 0x40021014),
                              ('01490860fee700bf', 0x40021018),
                              ('01490878fee700bf', 0x40021018)]:
            r = run_main(fixture(code, address), 20, power_mode='lp', memory_domains_on=True)
            self.assertEqual(r['reason'], 'unsupported-power-access')
        with self.assertRaises(ValueError):
            run_main(fixture('fee7'), 20, memory_domains_on=True)

    def test_spot_control_storage_preserves_trim_reset_fixture(self):
        for address, value in [(0x40020028, 0x79), (0x40020060, 0xe000)]:
            raw = (struct.pack('<II', 0x2007fb00, 0x438009)
                   + bytes.fromhex('0349044808600868fee700bf00bf00bf')
                   + struct.pack('<II', address, value))
            r = run_main(raw, 20, debug_port_off=True, spot_control_storage=True)
            self.assertEqual(r['registers']['r0'], hex(value))
            self.assertEqual(r['spot_control_storage']['analog_power'], 'not-modeled')
            self.assertFalse(r['spot_control_storage']['hardware_verified'])
        r = run_main(fixture('01490868fee700bf', 0x40020028), 20, debug_port_off=True, spot_control_storage=True)
        self.assertEqual(r['registers']['r0'], '0x78')

    def test_spot_control_storage_rejects_other_values_widths_and_registers(self):
        for code, address in [('01490860fee700bf', 0x40020028),
                              ('01490878fee700bf', 0x40020028),
                              ('01490868fee700bf', 0x40020044)]:
            r = run_main(fixture(code, address), 20, debug_port_off=True, spot_control_storage=True)
            self.assertEqual(r['reason'], 'unsupported-mcuctrl-access')
        for address, value in [(0x40020028, 0x7b), (0x40020060, 0x10000)]:
            raw = (struct.pack('<II', 0x2007fb00, 0x438009)
                   + bytes.fromhex('0349044808600868fee700bf00bf00bf')
                   + struct.pack('<II', address, value))
            r = run_main(raw, 20, debug_port_off=True, spot_control_storage=True)
            self.assertEqual(r['reason'], 'unsupported-mcuctrl-access')
        with self.assertRaises(ValueError):
            run_main(fixture('fee7'), 20, spot_control_storage=True)

    def test_chip_revision_fixture_is_explicit_and_read_only(self):
        for value in (0x21, 0x22, 0x23, 0x24):
            r = run_main(fixture('01490868fee700bf', 0x4002000c), 20,
                         debug_port_off=True, chip_revision_fixture=value)
            self.assertEqual(r['registers']['r0'], hex(value))
            self.assertFalse(r['chip_revision_fixture']['hardware_verified'])
        for code in ('01490878fee700bf', '01490860fee700bf'):
            r = run_main(fixture(code, 0x4002000c), 20, debug_port_off=True, chip_revision_fixture=0x23)
            self.assertEqual(r['reason'], 'unsupported-mcuctrl-access')

    def test_chip_revision_fixture_requires_mcuctrl_model(self):
        with self.assertRaises(ValueError):
            run_main(fixture('fee7'), 20, chip_revision_fixture=0x23)
        for value in (True, 0, 0xff):
            with self.assertRaises(ValueError):
                run_main(fixture('fee7'), 20, debug_port_off=True, chip_revision_fixture=value)

    def test_invalid_boot_metadata_words_are_sparse(self):
        for kind, value in [('zero', '0x0'), ('erased', '0xffffffff')]:
            for address, name in [(0x42003310, 'TRIM_REV'), (0x42003240, 'PATCH_TRACKER0'), (0x42003314, 'FT1_GDR1')]:
                r = run_main(fixture('01490868fee700bf', address), 20, info1_metadata_fixture=kind)
                self.assertEqual(r['registers']['r0'], value)
                self.assertGreater(r['info1_metadata_fixture']['word_reads'][name], 0)
                self.assertFalse(r['info1_metadata_fixture']['device_data'])
                self.assertFalse(r['info1_metadata_fixture']['valid_calibration'])

    def test_boot_metadata_fixture_rejects_other_words_widths_and_writes(self):
        for code, address in [('01490868fee700bf', 0x42003318),
                              ('01490878fee700bf', 0x42003310),
                              ('01490860fee700bf', 0x42003240)]:
            r = run_main(fixture(code, address), 20, info1_metadata_fixture='zero')
            self.assertEqual(r['reason'], 'unsupported-information-access')

    def test_information_fixture_scopes_cannot_be_mixed(self):
        with self.assertRaisesRegex(ValueError, 'Choose one Info1'):
            run_main(fixture('fee7'), 20, info1_metadata_fixture='zero', trim_revision_fixture='zero')

    def test_invalid_trim_revision_is_explicit(self):
        for kind, value in [('zero', '0x0'), ('erased', '0xffffffff')]:
            r = run_main(fixture('01490868fee700bf', 0x42003310), 20, trim_revision_fixture=kind)
            self.assertEqual(r['registers']['r0'], value)
            self.assertFalse(r['trim_revision_fixture']['valid_calibration'])

    def test_trim_fixture_cannot_supply_other_data_or_accept_writes(self):
        for code, address in [('01490868fee700bf', 0x42003314), ('01490860fee700bf', 0x42003310)]:
            r = run_main(fixture(code, address), 20, trim_revision_fixture='zero')
            self.assertEqual(r['reason'], 'unsupported-information-access')

    def test_shadow_info_source_is_hypothetical_metadata_only(self):
        for source, value in [('mram', '0x1'), ('otp', '0x9')]:
            r = run_main(fixture('01490868fee700bf', 0x400201bc), 20, debug_port_off=True, shadow_info1=source)
            self.assertEqual(r['registers']['r0'], value)
            self.assertFalse(r['shadow_info1']['hardware_verified'])
            self.assertEqual(r['shadow_info1']['otp_and_information_data'], 'not-provided')

    def test_shadow_register_write_and_other_info_reads_stop(self):
        for code, address in [('01490860fee700bf', 0x400201bc), ('01490868fee700bf', 0x400201b8)]:
            r = run_main(fixture(code, address), 20, debug_port_off=True, shadow_info1='otp')
            self.assertEqual(r['reason'], 'unsupported-mcuctrl-access')

    def test_wic_mode_storage_readback(self):
        raw = (struct.pack('<II', 0x2007fb00, 0x438009)
               + bytes.fromhex('0349044808600868fee700bf00bf00bf')
               + struct.pack('<II', 0x4002021c, 1))
        r = run_main(raw, 20, debug_port_off=True, wic_config=True)
        self.assertEqual(r['registers']['r0'], '0x1')
        self.assertEqual(r['wic_config']['sleep_wakeup'], 'not-modeled')

    def test_sleep_boundaries_never_fabricate_wakeup(self):
        for code in ('20bffee7', '30bffee7', 'aff30280fee7', 'aff30380fee7'):
            raw = struct.pack('<II', 0x2007fb00, 0x438009) + bytes.fromhex(code)
            r = run_main(raw, 20)
            self.assertEqual(r['reason'], 'unsupported-sleep-boundary')
            self.assertEqual(r['final_pc'], '0x438008')
    def test_core_domains_on_store_and_read(self):
        raw = (struct.pack('<II', 0x2007fb00, 0x438009)
               + bytes.fromhex('0349044808600868fee700bf00bf00bf')
               + struct.pack('<II', 0xe001e300, 0))
        r = run_main(raw, 20, core_domains_on=True)
        self.assertEqual(r['core_domains']['writes'], 1)
        self.assertEqual(r['core_domains']['reads'], 1)

    def test_retention_off_and_other_core_power_registers_stop(self):
        for address, value in [(0xe001e300, 2), (0xe001e300, 3), (0xe001e300, 0x300), (0xe001e304, 0)]:
            raw = (struct.pack('<II', 0x2007fb00, 0x438009)
                   + bytes.fromhex('0349044808600868fee700bf00bf00bf')
                   + struct.pack('<II', address, value))
            r = run_main(raw, 20, core_domains_on=True)
            self.assertEqual(r['reason'], 'unsupported-core-power-access')
            self.assertEqual(r['core_domains']['writes'], 0)

    def test_ccr_cache_off_read_is_explicit(self):
        r = run_main(fixture('01490868fee700bf', 0xe000ed14), 20, cpacr_storage=True, cpu_caches_off=True)
        self.assertEqual(r['registers']['r0'], '0x0')
        self.assertEqual(r['ccr_scenario']['cache_behavior'], 'not-modeled')

    def test_ccr_writes_remain_unsupported(self):
        r = run_main(fixture('01490860fee700bf', 0xe000ed14), 20, cpacr_storage=True, cpu_caches_off=True)
        self.assertEqual(r['reason'], 'unsupported-register-access')

    def test_debug_port_off_readback(self):
        r = run_main(fixture('01490868fee700bf', 0x40020250), 20, debug_port_off=True)
        self.assertEqual(r['registers']['r0'], '0x0')
        self.assertEqual(r['debug_port']['reads'], 1)

    def test_other_mcuctrl_register_and_debug_enable_stop(self):
        enable = (struct.pack('<II', 0x2007fb00, 0x438009)
                  + bytes.fromhex('0349044808600868fee700bf00bf00bf')
                  + struct.pack('<II', 0x40020250, 1))
        for raw in [enable, fixture('01490868fee700bf', 0x40020000)]:
            r = run_main(raw, 20, debug_port_off=True)
            self.assertEqual(r['reason'], 'unsupported-mcuctrl-access')

    def test_device_off_enable_and_status_reads(self):
        for address in (0x40021004, 0x40021008):
            r = run_main(fixture('01490868fee700bf', address), 20, power_mode='lp', devices_off=True)
            self.assertEqual(r['registers']['r0'], '0x0')
            self.assertFalse(r['device_power']['device_state_verified'])

    def test_device_power_up_is_not_acknowledged(self):
        raw = (struct.pack('<II', 0x2007fb00, 0x438009)
               + bytes.fromhex('0349044808600868fee700bf00bf00bf')
               + struct.pack('<II', 0x40021004, 1))
        r = run_main(raw, 20, power_mode='lp', devices_off=True)
        self.assertEqual(r['reason'], 'unsupported-power-access')
        self.assertEqual(r['device_power']['status'], '0x0')

    def test_demcr_trace_enable_storage(self):
        raw = (struct.pack('<II', 0x2007fb00, 0x438009)
               + bytes.fromhex('0349044808600868fee700bf00bf00bf')
               + struct.pack('<II', 0xe000edfc, 0x1000000))
        r = run_main(raw, 20, cpacr_storage=True, trace_control_storage=True)
        self.assertEqual(r['registers']['r0'], '0x1000000')
        self.assertEqual(r['demcr']['trace_and_cycle_counter'], 'not-modeled')

    def test_demcr_other_control_bits_stop(self):
        raw = (struct.pack('<II', 0x2007fb00, 0x438009)
               + bytes.fromhex('0349044808600868fee700bf00bf00bf')
               + struct.pack('<II', 0xe000edfc, 1))
        r = run_main(raw, 20, cpacr_storage=True, trace_control_storage=True)
        self.assertEqual(r['reason'], 'unsupported-register-access')
        self.assertEqual(r['demcr']['final'], '0x0')

    def test_fpccr_control_roundtrip(self):
        for value in (0x80000000, 0xc0000000):
            raw = (struct.pack('<II', 0x2007fb00, 0x438009)
                   + bytes.fromhex('0349044808600868fee700bf00bf00bf')
                   + struct.pack('<II', 0xe000ef34, value))
            r = run_main(raw, 20, cpacr_storage=True, fp_context_storage=True)
            self.assertEqual(r['registers']['r0'], hex(value))
            self.assertEqual(r['fpccr']['exception_context_preservation'], 'not-modeled')

    def test_fpccr_status_bits_cannot_be_invented(self):
        raw = (struct.pack('<II', 0x2007fb00, 0x438009)
               + bytes.fromhex('0349044808600868fee700bf00bf00bf')
               + struct.pack('<II', 0xe000ef34, 1))
        r = run_main(raw, 20, cpacr_storage=True, fp_context_storage=True)
        self.assertEqual(r['reason'], 'unsupported-register-access')
        self.assertEqual(r['fpccr']['final'], '0x0')

    def test_reset_config_roundtrip(self):
        raw = (struct.pack('<II', 0x2007fb00, 0x438009)
               + bytes.fromhex('0349044808600868fee700bf00bf00bf')
               + struct.pack('<II', 0x40000000, 2))
        r = run_main(raw, 20, reset_config=True)
        self.assertEqual(r['reset_config']['final_cfg'], '0x2')
        self.assertEqual(r['registers']['r0'], '0x2')

    def test_software_reset_requests_stop(self):
        for address, key in [(0x40000004, 0x1b), (0x40000008, 0xd4), (0x40000000, 4)]:
            raw = (struct.pack('<II', 0x2007fb00, 0x438009)
                   + bytes.fromhex('0349044808600868fee700bf00bf00bf')
                   + struct.pack('<II', address, key))
            r = run_main(raw, 20, reset_config=True)
            self.assertEqual(r['reason'], 'unsupported-reset-access')
            self.assertEqual(r['reset_config']['final_cfg'], '0x0')

    def test_disabled_watchdog_config_roundtrip(self):
        raw = (struct.pack('<II', 0x2007fb00, 0x438009)
               + bytes.fromhex('0349044808600868fee700bf00bf00bf')
               + struct.pack('<II', 0x40024000, 0))
        r = run_main(raw, 20, watchdog_disabled=True)
        self.assertEqual(r['reason'], 'instruction-limit')
        self.assertEqual(r['watchdog']['writes'], 1)
        self.assertFalse(r['watchdog']['device_state_verified'])

    def test_inactive_watchdog_configuration_is_retained(self):
        raw = (struct.pack('<II', 0x2007fb00, 0x438009)
               + bytes.fromhex('0349044808600868fee700bf00bf00bf')
               + struct.pack('<II', 0x40024000, 0x01000504))
        r = run_main(raw, 20, watchdog_disabled=True)
        self.assertEqual(r['registers']['r0'], '0x1000504')
        self.assertEqual(r['watchdog']['final_cfg'], '0x1000504')

    def test_watchdog_activation_and_neighbor_reads_stop(self):
        enable = (struct.pack('<II', 0x2007fb00, 0x438009)
                  + bytes.fromhex('0349044808600868fee700bf00bf00bf')
                  + struct.pack('<II', 0x40024000, 1))
        for raw in [enable, fixture('01490868fee700bf', 0x40024004)]:
            r = run_main(raw, 20, watchdog_disabled=True)
            self.assertEqual(r['reason'], 'unsupported-watchdog-access')

    def test_reset_latch_is_explicit_and_hypothetical(self):
        r = run_main(fixture('01490868fee700bf', 0x4000885c), 20, reset_latch=2)
        self.assertEqual(r['registers']['r0'], '0x2')
        self.assertFalse(r['reset_latch_scenario']['hardware_verified'])

    def test_observed_latch_bit_clear_and_readback(self):
        raw = (struct.pack('<II', 0x2007fb00, 0x438009)
               + bytes.fromhex('0349044808600868fee700bf00bf00bf')
               + struct.pack('<II', 0x4000885c, 2))
        r = run_main(raw, 20, reset_latch=6)
        self.assertEqual(r['reset_latch_scenario']['final'], '0x2')
        self.assertEqual(r['reset_latch_scenario']['writes'], 1)
        self.assertEqual(r['registers']['r0'], '0x2')

    def test_unobserved_latch_writes_and_neighbor_reads_stop(self):
        for code, address in [('01490860fee700bf', 0x4000885c), ('01490868fee700bf', 0x40008860)]:
            r = run_main(fixture(code, address), 20, reset_latch=2)
            self.assertEqual(r['reason'], 'unsupported-latch-access')

    def test_power_state_is_explicit_hypothesis(self):
        for mode, value in [('lp', '0xd'), ('hp', '0x16')]:
            r = run_main(fixture('01490868fee700bf', 0x40021000), 20, power_mode=mode)
            self.assertEqual(r['registers']['r0'], value)
            self.assertEqual(r['power_mode']['reads'], 1)
            self.assertFalse(r['power_mode']['device_state_verified'])

    def test_power_write_and_neighbor_access_stop(self):
        for code, address in [('01490860fee700bf', 0x40021000), ('01490868fee700bf', 0x40021004)]:
            r = run_main(fixture(code, address), 20, power_mode='lp')
            self.assertEqual(r['reason'], 'unsupported-power-access')

    def test_guest_written_itcm_code_executes(self):
        raw = (struct.pack('<II', 0x2007fb00, 0x438009)
               + bytes.fromhex('4021024808600131084700bf') + struct.pack('<I', 0x0000e7fe))
        result = run_main(raw, 20, itcm=True)
        self.assertEqual(result['reason'], 'instruction-limit')
        self.assertEqual(result['final_pc'], '0x40')
        self.assertEqual(result['itcm']['written_bytes'], 4)

    def test_uninitialized_itcm_execution_stops(self):
        result = run_main(fixture('01490847fee700bf', 0x41), 20, itcm=True)
        self.assertEqual(result['reason'], 'uninitialized-itcm-execution')
        self.assertEqual(result['itcm']['written_bytes'], 0)

    def test_unchanged_store_is_not_execution_proof(self):
        raw = (struct.pack('<II', 0x2007fb00, 0x438009)
               + bytes.fromhex('4021024808600131084700bf') + struct.pack('<I', 0xa5a5a5a5))
        result = run_main(raw, 20, itcm=True)
        self.assertEqual(result['reason'], 'uninitialized-itcm-execution')
        self.assertEqual(result['itcm']['written_bytes'], 0)

    def test_execution_budgets_reject_unbounded_values(self):
        for count, timeout in ((0, 1), (10000001, 1), (20, 0), (20, 30000001)):
            with self.subTest(count=count, timeout=timeout), self.assertRaises(ValueError):
                run_main(fixture('fee7'), count, timeout_us=timeout)

    def test_system_sram_write_is_supported_only_when_selected(self):
        data = fixture('01490860fee700bf', 0x2013519c)
        self.assertEqual(run_main(data, 20)['reason'], 'unsupported-memory-access')
        self.assertEqual(run_main(data, 20, system_sram=True)['reason'], 'instruction-limit')

    def test_reserved_memory_after_system_sram_still_rejected(self):
        result = run_main(fixture('01490860fee700bf', 0x20380000), 20, system_sram=True)
        self.assertEqual(result['access']['kind'], 'write-unmapped')

    def test_vtor_roundtrip_and_interrupt_limit_reported(self):
        raw = (struct.pack('<II', 0x2007fb00, 0x438009)
               + bytes.fromhex('0349044808600868fee700bf00bf00bf')
               + struct.pack('<II', 0xe000ed08, 0x438000))
        result = run_main(raw, 20, cpacr_storage=True, vtor_storage=True)
        self.assertEqual(result['reason'], 'instruction-limit')
        self.assertEqual(result['vtor']['events'], [
            {'operation': 'write', 'value': '0x438000'},
            {'operation': 'read', 'value': '0x438000'}])
        self.assertEqual(result['vtor']['interrupt_dispatch'], 'not-modeled')

    def test_other_vector_bases_are_unsupported(self):
        raw = (struct.pack('<II', 0x2007fb00, 0x438009)
               + bytes.fromhex('0349044808600868fee700bf00bf00bf')
               + struct.pack('<II', 0xe000ed08, 0x438004))
        result = run_main(raw, 20, cpacr_storage=True, vtor_storage=True)
        self.assertEqual(result['reason'], 'unsupported-register-access')
        self.assertEqual(result['vtor']['final'], '0x0')

    def test_unmapped_read(self):
        result = run_main(fixture('01490868fee700bf'), 20)
        self.assertEqual(result['reason'], 'unsupported-memory-access')
        self.assertEqual(result['access']['kind'], 'read-unmapped')
        self.assertEqual(result['access']['address'], '0x40000000')

    def test_unmapped_write(self):
        result = run_main(fixture('01490860fee700bf'), 20)
        self.assertEqual(result['access']['kind'], 'write-unmapped')

    def test_unmapped_fetch(self):
        result = run_main(fixture('01490847fee700bf', 0x100001), 20)
        self.assertEqual(result['access']['kind'], 'fetch-unmapped')

    def test_code_write_rejected(self):
        result = run_main(fixture('01490860fee700bf', 0x438000), 20)
        self.assertEqual(result['access']['kind'], 'write-protected')

    def test_loop_is_not_reported_as_success(self):
        result = run_main(fixture('fee7'), 20)
        self.assertEqual(result['reason'], 'instruction-limit')
        self.assertEqual(result['instruction_boundaries'], 20)
        self.assertFalse(result['boot_verified'])

    def test_repeat_has_same_execution_evidence(self):
        data = fixture('01490868fee700bf')
        self.assertEqual(run_main(data, 20), run_main(data, 20))

    def test_invalid_reset_vector_rejected(self):
        data = struct.pack('<II', 0x2007fb00, 0x438008) + bytes.fromhex('fee7')
        with self.assertRaises(ValueError):
            run_main(data, 20)

    def test_cpacr_roundtrip_full_access_storage(self):
        raw = (struct.pack('<II', 0x2007fb00, 0x438009)
               + bytes.fromhex('0349044808600868fee700bf00bf00bf')
               + struct.pack('<II', 0xe000ed88, 0xf00000))
        result = run_main(raw, 20, cpacr_storage=True)
        self.assertEqual(result['reason'], 'instruction-limit')
        self.assertEqual(result['cpacr']['final'], '0xf00000')
        self.assertEqual([(e['operation'], e['value']) for e in result['cpacr']['events']],
                         [('write', '0xf00000'), ('read', '0xf00000')])
        self.assertEqual(result['cpacr']['access_permission_enforcement'], 'not-modeled')

    def test_neighbor_register_not_silently_mapped(self):
        result = run_main(fixture('01490868fee700bf', 0xe000ed8c), 20, cpacr_storage=True)
        self.assertEqual(result['reason'], 'unsupported-register-access')
        self.assertEqual(result['instruction_boundaries'], 2)
        self.assertEqual(result['cpacr']['events'], [])

    def test_cpacr_short_access_stops(self):
        result = run_main(fixture('01490878fee700bf', 0xe000ed88), 20, cpacr_storage=True)
        self.assertEqual(result['reason'], 'unsupported-register-access')
        self.assertEqual(result['access']['bytes'], 1)

    def test_cpacr_unmodeled_value_does_not_change_state(self):
        raw = (struct.pack('<II', 0x2007fb00, 0x438009)
               + bytes.fromhex('0349044808600868fee700bf00bf00bf')
               + struct.pack('<II', 0xe000ed88, 0xffffffff))
        result = run_main(raw, 20, cpacr_storage=True)
        self.assertEqual(result['reason'], 'unsupported-register-access')
        self.assertEqual(result['cpacr']['final'], '0x0')
        self.assertEqual(result['cpacr']['events'], [])
