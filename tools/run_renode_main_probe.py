"""Execute one pinned G2 main on a minimal Renode M55 board with aborting MMIO guards."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess

from pinned_main import load_pinned_main
from execution_observer import requests as observer_requests,instrument as instrument_execution
from iom_main_adapter import connect_ioms,power_profiles,SUPPORTED
from run_renode_m55_probe import execute
from iom_engine_source import load_engine,UPSTREAM_SHA
from rtc_engine_source import load_engine as load_rtc_engine,UPSTREAM_SHA as RTC_UPSTREAM_SHA

ROOT = Path(__file__).resolve().parents[1]
BASE = 0x438000


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--image', default='blackwall-renode:1.17.0-local')
    parser.add_argument('--wall-run-seconds', type=float, default=2)
    parser.add_argument('--power-mode', choices=('lp', 'hp'))
    parser.add_argument('--reset-latch', type=lambda value: int(value, 0))
    parser.add_argument('--watchdog-model', action='store_true', help='Nominal LFRC watchdog; pause at reset request without reset propagation')
    parser.add_argument('--reset-controller', action='store_true', help='Synthetic CFG=0, two-bit storage and WDREN gate; no system reset')
    parser.add_argument('--startup-controls', action='store_true', help='Synthetic peripherals/debug off, core domains on, WIC bit storage; no power transitions')
    parser.add_argument('--shadow-info1', choices=('mram', 'otp'), help='Hypothetical VALID/source bits only; no OTP contents')
    parser.add_argument('--adc-constant-channel3', type=int, help='Explicit constant12bit digital input; source-reset slots, zero-latency scan; no physical sensor or IRQ')
    parser.add_argument('--adc-trigger-source-hz', type=int, help='Explicit virtual ADC trigger clock hypothesis; first event pauses before unsupported conversion')
    parser.add_argument('--adc-enable-latch', action='store_true', help='Known disabled CFG bit0 transition only; no physical ready, conversion or timer operation')
    parser.add_argument('--adc-disabled-config-storage', action='store_true', help='Guest-written disabled ADC CFG and eight slot latches only; no ADC operation')
    parser.add_argument('--adc-trigger-config-storage', action='store_true', help='Store disabled timer configuration only after ADC power on; initial value unknown; no timer execution')
    parser.add_argument('--uart-modules', default='1', help='Explicit UART modules0..3, comma separated; selected profiles applied independently')
    parser.add_argument('--uart-off-response','--uart1-off-response',dest='uart1_off_response', choices=('off','stuck-on'), help='Quiescent UART power-off/reset and subsequent guest restore; explicit digital response')
    parser.add_argument('--uart-interrupts','--uart1-interrupts',dest='uart1_interrupts', action='store_true', help='Explicit instant-TX Ambiq IRQ model wired to NVIC16; no RX input/DMA')
    parser.add_argument('--uart-model','--uart1-model',dest='uart1_model', choices=('active','stuck-off'), help='Strict pollingTX PL011 adapter with explicit UART1 power response; no RX/DMA/IRQ')
    parser.add_argument('--adc-power-off-response', choices=('off','stuck-on'), help='Explicit quiescent ADC off response; no physical rail/reset or re-enable')
    parser.add_argument('--adc-power-response', choices=('active','stuck-off'), help='Explicit ADC request/status bit response composed with GPU; no physical power or ADC conversion')
    parser.add_argument('--adc-calibration-control', action='store_true', help='ADCCAL bit0 storage with source initial1 and calibrated status0; no ADC execution')
    parser.add_argument('--adc-info-zero-fixture', action='store_true', help='Five sparse zero ADC calibration words for fallback research; not valid device calibration')
    parser.add_argument('--capture-sram-window', action='append', default=[], metavar='ADDRESS:BYTES', help='Read-only aligned virtual SRAM window, max four windows of 256 bytes')
    parser.add_argument('--info1-metadata-fixture', choices=('zero', 'erased'), help='Sparse invalid metadata only; no valid calibration')
    parser.add_argument('--chip-revision-fixture', type=lambda value: int(value,0), choices=(0x21,0x22,0x23,0x24))
    parser.add_argument('--spot-control-storage', action='store_true', help='Observed ACRG/VRCTRL values only; no analog power')
    parser.add_argument('--memory-startup-fixture', action='store_true', help='Synthetic memory domains on, one zero-latency ROM disable and limited retention storage')
    parser.add_argument('--hal-startup-storage', action='store_true', help='Observed clock/ADC/TON/switch/HAL values and public read-only reset words; no analog behavior')
    parser.add_argument('--mram-control-storage', action='store_true', help='MRAMEXTCTRL synthetic reset 2 and observed 2-to-6 storage only; no wakeup behavior')
    parser.add_argument('--buck-override-storage', action='store_true', help='Ordered observed VRCTRL setup only; no voltage/deep-sleep behavior')
    parser.add_argument('--buck-start-storage', action='store_true', help='Ordered trim latch/compensation/enable requests only; no power-ready feedback')
    parser.add_argument('--prefetch-control-storage', action='store_true', help='PFCR defined-field storage; initial read blocked, no prefetch timing model')
    parser.add_argument('--coherent-dcache-model', action='store_true', help='Documented Apollo510 geometry and coherent data memory; no timing/dirty-line model')
    parser.add_argument('--coherent-icache-model', action='store_true', help='Functional coherent instruction memory; no cache timing/eviction')
    parser.add_argument('--gpu-initial-status-hypothesis', choices=('zero','nonzero'), help='Explicit unverified initial STATUS 0/1 for differential observation, no work completion')
    parser.add_argument('--gpu-config-low-response', action='store_true', help='Trace-only documented CONFIG low word; not implemented GPU feature support')
    parser.add_argument('--gpu-config-high-hypothesis', choices=('zero','bit9'), help='Explicit unverified CONFIGH scenario, default read remains blocked')
    parser.add_argument('--gpu-raster-init-storage', action='store_true', help='Trace-only one observed RAST_BYPASS=1 initialization word; rendering effect unimplemented')
    parser.add_argument('--gpu-initial-resets', action='store_true', help='Quiescent initial command-processor/GPU reset sequence only; ring validity becomes unknown, no engine execution')
    parser.add_argument('--gpu-identity-response', choices=('source-reset','absent'), help='Explicit public ID or synthetic missing-ID response, not measured hardware capabilities')
    parser.add_argument('--gpu-ring-configuration', action='store_true', help='Ordered initial ring config latches only; no GPU DMA, commands or completion')
    parser.add_argument('--gpu-id-initialization', action='store_true', help='One observed initial ID0 write, no ID reads/completion; capture bounded guest SRAM at next blocked ring request')
    parser.add_argument('--gpu-interrupt-clear', action='store_true', help='Power-gated idle IRQ clear only; no GPU commands, reset or completion')
    parser.add_argument('--capture-itcm-prefix', action='store_true', help='Read-only bounded ITCM/register/SRAM-stack snapshot after stop; no guest state mutation')
    parser.add_argument('--gpio-output-latch', action='store_true', help='Output latch for known GPIO push-pull pins only; no pad voltages or devices')
    parser.add_argument('--gpio-interrupt-idle', action='store_true', help='Explicit idle GPIO IRQ state: EN storage, zero STAT and CLR request trace, no events or IRQ generation')
    parser.add_argument('--gpio-config-storage', action='store_true', help='PADKEY and guest-written PINCFG readback only; no initial pin values, signals or interrupts')
    parser.add_argument('--gpu-off-sequence-storage', action='store_true', help='One PCM2 active-buck post-off trim sequence, no analog timing or re-enable')
    parser.add_argument('--gpu-power-off-response', choices=('off','stuck-on'), help='Explicit digital off response; retires GPU epoch and blocks re-enable, no retention/timing claim')
    parser.add_argument('--gpu-power-response', choices=('active','stuck-off'), help='Explicit GPU request/status response; no physical power, GPU engine or on-to-off sequence')
    parser.add_argument('--gpu-power-preparation', action='store_true', help='One ordered PCM2 GPU HP preparation storage sequence; no analog rails or GPU engine')
    parser.add_argument('--hfrc-force-control', action='store_true', help='Explicit MISC.FRCHFRC control and zero-latency derived HFRC enable; no physical clock model')
    parser.add_argument('--gfx-power-storage', action='store_true', help='GFX VDD select and legacy LP/HP request storage; no GPU execution or voltage model')
    parser.add_argument('--jedec-mock-part',type=lambda v:int(v,0),help='Explicit synthetic 12bit JEDEC part number; requires paired mock CID and chip info profile')
    parser.add_argument('--jedec-mock-cid',type=lambda v:int(v,0),help='Explicit synthetic 32bit CoreSight CID; never inferred as real chip identity')
    parser.add_argument('--observe-pc',action='append',default=[],metavar='LABEL:ADDRESS',help='Read-only instruction point in original main; caller verifies instruction boundaries')
    parser.add_argument('--observe-sram',action='append',default=[],metavar='LABEL:ADDRESS:WORDS',help='First-hit snapshot of 1..16 G2 SRAM words at a declared observation point')
    parser.add_argument('--chip-info-profile',choices=('source-reset-zero-ids',),help='Read-only source PN/SKU plus shared explicit revision and synthetic zero unique/vendor IDs; no real identity or JEDEC values')
    parser.add_argument('--rtc-model',choices=('epoch2000-100hz',),help='Explicit virtual epoch/100Hz RTC adapter; no hardware oscillator or century rollover validation')
    parser.add_argument('--rtc-counter-writes',choices=('hal-low-upper',),help='Explicit staged LOW/UP virtual write profile; source conflict, not hardware-verified')
    parser.add_argument('--rtc-osel-storage',choices=('xt','lfrc'),help='Explicit initial OCTRL request latch; effective oscillator, silicon revision behavior and RTC time unknown')
    parser.add_argument('--mcu-clock-response', choices=('nominal','hfrc2-unready','no-ack','denied'), help='Digital HFRC2/performance response profile; no physical timing/frequency')
    parser.add_argument('--buck-response-model', choices=('active','stuck-off'), help='Explicit post-enable digital response profile; zero-latency assumption after setup')
    parser.add_argument('--vddf-tempco-storage', action='store_true', help='One observed virtual initial VDDF trim reduction; no voltage/calibration model')
    parser.add_argument('--buck-status-fixture', choices=('off','lp','active'), help='One explicit post-enable status sample; no analog transition model')
    parser.add_argument('--memldo-setup-storage', action='store_true', help='Ordered post-enable memory LDO field storage; no analog/readiness model')
    parser.add_argument('--coreldo-reduction-storage', action='store_true', help='One saturated core-LDO field reduction; no voltage/calibration model')
    parser.add_argument('--iom2-model', choices=('active','stuck-off'), help='Strict mapped IOM2 with explicit power response; no attached peer/DMA; bounded CQ')
    parser.add_argument('--iom-cq-input-levels',type=lambda v:int(v,0),help='Explicit mock CQ inputs bits0..4: MSPI0,MSPI1,GPIO,IOM,BLE; no physical signal proof')
    parser.add_argument('--iom-modules',default='2',help='Explicit IOM2/4/5/6/7 instances; bounded CQ, DMA unsupported')
    parser.add_argument('--iom-power-profile',action='append',default=[],metavar='MODULE:PROFILE',help='Independent selected IOM power override; active or stuck-off')
    parser.add_argument('--iom4-model',choices=('active','stuck-off'),help='Independent module4 power response override')
    parser.add_argument('--iom2-off-response', choices=('off','stuck-on'))
    args = parser.parse_args()
    if (args.jedec_mock_part is None)!=(args.jedec_mock_cid is None):raise ValueError("JEDEC mock part and CID must be explicitly paired")
    if args.jedec_mock_part is not None and (args.chip_info_profile is None or not 0<=args.jedec_mock_part<=0xfff or not 0<=args.jedec_mock_cid<=0xffffffff):raise ValueError("JEDEC mock requires chip info, 12bit part and 32bit CID")
    if args.chip_info_profile is not None and args.chip_revision_fixture is None:raise ValueError("Chip info requires explicit chip revision fixture")
    if args.rtc_counter_writes is not None and args.rtc_model is None:raise ValueError("RTC counter writes require explicit RTC model")
    if args.iom_cq_input_levels is not None and (args.iom2_model is None or not 0<=args.iom_cq_input_levels<=31):raise ValueError('CQ mock inputs require IOM model and a five-bit vector')
    iom_modules=tuple(sorted(int(n) for n in args.iom_modules.split(',')))
    if not iom_modules or len(set(iom_modules))!=len(iom_modules) or any(n not in SUPPORTED for n in iom_modules):
        raise ValueError('IOM modules must be unique selected 2,4,5,7')
    if args.iom2_model is None and (iom_modules!=(2,) or args.iom4_model is not None or args.iom_power_profile):
        raise ValueError('IOM module selection requires power model')
    iom_overrides={}
    for item in args.iom_power_profile:
        parts=item.split(':')
        if len(parts)!=2:raise ValueError('IOM power override requires MODULE:PROFILE')
        module=int(parts[0],0)
        if module in iom_overrides:raise ValueError('Duplicate IOM power override')
        iom_overrides[module]=parts[1]
    if args.iom2_model is not None:power_profiles(iom_modules,args.iom2_model,iom_overrides,args.iom4_model)
    if args.iom2_off_response is not None and args.iom2_model!='active':
        raise ValueError('IOM2 off response requires active model')
    if args.iom2_model is not None and not (args.adc_power_response and args.watchdog_model and args.reset_controller and args.gpu_ring_configuration):
        raise ValueError('IOM2 requires shared ADC/power bank, watchdog/reset and owned high GPU guard')
    if not 0.01 <= args.wall_run_seconds <= 15:
        raise ValueError('Guest execution window must be 0.01..15 host seconds')
    if args.reset_latch is not None and not 0 <= args.reset_latch <= 0x1fff:
        raise ValueError('Reset shadow fixture must fit thirteen bits')
    if args.startup_controls and args.power_mode is None:
        raise ValueError('Startup controls require an explicit stable power-mode hypothesis')
    if args.shadow_info1 is not None and not args.startup_controls:
        raise ValueError('Info1 source requires explicit startup controls')
    if args.info1_metadata_fixture is not None and args.shadow_info1 != 'mram':
        raise ValueError('Sparse invalid metadata requires explicit MRAM source')
    if (args.chip_revision_fixture is not None or args.spot_control_storage) and not args.startup_controls:
        raise ValueError('Silicon fixtures require explicit startup controls')
    if args.memory_startup_fixture and not args.startup_controls:
        raise ValueError('Memory startup fixture requires explicit startup controls')
    if args.prefetch_control_storage and not args.startup_controls:
        raise ValueError('Prefetch storage requires startup controls')
    if args.hal_startup_storage and (not args.memory_startup_fixture or args.reset_latch is None):
        raise ValueError('HAL storage requires explicit memory startup and reset shadow fixtures')
    if args.mram_control_storage and not args.hal_startup_storage:
        raise ValueError('MRAM control storage requires explicit HAL startup storage')
    if args.buck_override_storage and (not args.spot_control_storage or not args.mram_control_storage):
        raise ValueError('Buck override storage requires explicit SPOT and MRAM control fixtures')
    if args.buck_start_storage and not args.buck_override_storage:
        raise ValueError('Buck start requests require explicit ordered override storage')
    if args.buck_status_fixture is not None and not args.memldo_setup_storage:
        raise ValueError('Buck status fixture requires memory LDO setup')
    if args.memldo_setup_storage and not args.coreldo_reduction_storage:
        raise ValueError('Memory LDO setup requires core LDO reduction storage')
    if args.coreldo_reduction_storage and not args.buck_start_storage:
        raise ValueError('Core LDO reduction requires explicit buck start fixtures')
    if args.coherent_dcache_model and not args.coherent_icache_model:
        raise ValueError('Data cache requires coherent instruction cache')
    if args.buck_response_model is not None and (not args.memldo_setup_storage or args.buck_status_fixture is not None):
        raise ValueError('Buck response requires setup and excludes single samples')
    if args.vddf_tempco_storage and args.buck_response_model is None:
        raise ValueError('VDDF storage requires buck response')
    if args.mcu_clock_response is not None and (args.power_mode is None or args.buck_response_model!='active' or not args.vddf_tempco_storage or not args.hal_startup_storage):
        raise ValueError('MCU clock response requires explicit mode, active buck and HAL/VDDF storage')
    if args.adc_power_response is not None and (args.gpu_power_response is None or not args.adc_calibration_control):
        raise ValueError('ADC power response requires GPU power and ADC calibration control')
    if args.adc_trigger_config_storage and args.adc_power_response is None:
        raise ValueError('ADC trigger config requires ADC power response')
    if args.adc_disabled_config_storage and args.adc_power_response is None:
        raise ValueError('ADC disabled config requires ADC power response')
    if args.adc_enable_latch and not (args.adc_disabled_config_storage and args.adc_trigger_config_storage):
        raise ValueError('ADC enable latch requires config bank and timer config storage')
    if args.adc_trigger_source_hz is not None and (not args.adc_enable_latch or not 1<=args.adc_trigger_source_hz<=48000000):
        raise ValueError('ADC trigger source requires enable latch and Hz1..48000000')
    if args.adc_constant_channel3 is not None and (args.adc_trigger_source_hz is None or not 0<=args.adc_constant_channel3<=4095):
        raise ValueError('ADC constant channel3 requires trigger source and code0..4095')
    if args.adc_power_off_response is not None and args.adc_constant_channel3 is None:
        raise ValueError('ADC power off requires constant scan profile')
    try:
        uart_modules=[int(x) for x in args.uart_modules.split(',')]
    except ValueError:
        raise ValueError('UART modules must be comma separated integers0..3')
    if not uart_modules or len(set(uart_modules))!=len(uart_modules) or any(x not in range(4) for x in uart_modules):
        raise ValueError('UART modules must be unique values0..3')
    if args.uart1_model is None:
        if uart_modules!=[1]:raise ValueError('UART modules require explicit model')
        uart_modules=[]
    uart_modules.sort()
    if args.uart1_off_response is not None and not args.uart1_interrupts:
        raise ValueError('UART1 off response requires interrupt model')
    if args.uart1_interrupts and args.uart1_model is None:
        raise ValueError('UART1 interrupts require explicit UART1 model')
    if args.uart1_model is not None and args.adc_power_response is None:
        raise ValueError('UART1 model requires ADC/GPU shared power bank')
    capture_windows=[]
    if len(args.capture_sram_window)>4:raise ValueError('At most four virtual SRAM windows')
    for window in args.capture_sram_window:
        parts=window.split(':')
        if len(parts)!=2:raise ValueError('SRAM window must be ADDRESS:BYTES')
        address,size=(int(part,0) for part in parts)
        if address%4 or size%4 or not 4<=size<=256 or not 0x20000000<=address<=0x20380000-size:
            raise ValueError('Capture window must be bounded aligned virtual SRAM')
        capture_windows.append((address,size))
    if args.adc_info_zero_fixture and (args.shadow_info1!='mram' or args.info1_metadata_fixture!='zero'):
        raise ValueError('ADC info fixture requires MRAM source and zero metadata')
    if args.gpio_output_latch and not args.gpio_config_storage:
        raise ValueError('GPIO output latch requires GPIO config storage')
    if args.gpio_interrupt_idle and not args.gpio_config_storage:
        raise ValueError('GPIO interrupt idle requires GPIO config storage')
    if args.gpu_off_sequence_storage and args.gpu_power_off_response!='off':
        raise ValueError('GPU off sequence requires explicit off response')
    if args.gpu_power_off_response is not None and (args.gpu_power_response!='active' or args.gpu_initial_status_hypothesis!='zero'):
        raise ValueError('GPU off observation requires active power and explicit zero initial STATUS')
    if args.gpu_initial_status_hypothesis is not None and args.gpu_config_high_hypothesis is None:
        raise ValueError('Initial STATUS hypothesis requires explicit CONFIGH hypothesis')
    if args.gpu_config_high_hypothesis is not None and not args.gpu_config_low_response:
        raise ValueError('CONFIGH hypothesis requires low response')
    if args.gpu_config_low_response and not args.gpu_raster_init_storage:
        raise ValueError('CONFIG low response requires raster trace storage')
    if args.gpu_raster_init_storage and not args.gpu_initial_resets:
        raise ValueError('Raster init storage requires initial reset controls')
    if args.gpu_initial_resets and args.gpu_identity_response!='source-reset':
        raise ValueError('Initial GPU resets require source identity response')
    if args.gpu_identity_response is not None and not args.gpu_ring_configuration:
        raise ValueError('GPU identity response requires ring configuration')
    if args.gpu_ring_configuration and not args.gpu_id_initialization:
        raise ValueError('GPU ring configuration requires ID initialization')
    if args.gpu_id_initialization and not args.gpu_interrupt_clear:
        raise ValueError('GPU ID initialization requires IRQ clear')
    if args.gpu_interrupt_clear and args.gpu_power_response is None:
        raise ValueError('GPU IRQ clear requires explicit power response')
    if args.gpu_power_response is not None and not args.gpu_power_preparation:
        raise ValueError('GPU power response requires preparation')
    if args.gpu_power_preparation and (not args.gfx_power_storage or not args.hfrc_force_control or args.mcu_clock_response!='nominal'):
        raise ValueError('GPU preparation requires GFX selection and nominal HFRC controls')
    if args.hfrc_force_control and args.mcu_clock_response is None:
        raise ValueError('HFRC force control requires explicit clock response')
    if args.gfx_power_storage and not args.startup_controls:
        raise ValueError('GFX power storage requires startup controls')
    data = args.bundle.read_bytes()
    profile,raw = load_pinned_main(data)
    observation_points,observation_captures=observer_requests(args.observe_pc,args.observe_sram,len(raw))
    digest = hashlib.sha256(data).hexdigest()
    stack, vector = struct.unpack_from('<II', raw)
    if (not 0x20000000 < stack <= 0x20080000 or stack % 8 or not vector & 1
            or not BASE+8 <= vector & ~1 < BASE+len(raw) or len(raw) > 0x3c0000):
        raise ValueError('Main vector or extent outside selected memory fixture')
    result = subprocess.run(['docker', 'image', 'inspect', args.image], capture_output=True,
                            text=True, check=True, timeout=15)
    image = json.loads(result.stdout)[0]
    if image['Architecture'] != 'arm64' or image['Os'] != 'linux':
        raise ValueError('A reviewed Linux ARM64 Renode image is required')
    output = args.output.resolve()
    output.mkdir(mode=0o700)
    host_source=output/'host-source'; host_source.mkdir()
    for name in ['run_renode_main_probe.py','pinned_main.py','revalidate_research_assets.py','run_renode_m55_probe.py','iom_main_adapter.py','iom_engine_source.py','rtc_engine_source.py','execution_observer.py']:
        shutil.copy2(ROOT/'tools'/name,host_source/name)
    (output/'main.bin').write_bytes(raw)
    (output/'sram-fill.bin').write_bytes(b'\xa5'*0x380000)
    (output/'itcm-fill.bin').write_bytes(b'\xa5'*0x40000)
    shutil.copy2(ROOT/'tools/renode-strict-mmio.cs', output/'strict.cs')
    with (output/'strict.cs').open('a') as source:
        source.write('\n'+(ROOT/'tools/renode-memory-policy.cs').read_text()+'\n'+(ROOT/'tools/renode-system-control.cs').read_text())
    if args.watchdog_model or args.reset_controller:
        with (output/'strict.cs').open('a') as source:
            source.write('\n'+(ROOT/'tools/renode-reset-controller.cs').read_text())
    if args.watchdog_model:
        with (output/'strict.cs').open('a') as source:
            source.write('\n'+(ROOT/'tools/renode-watchdog.cs').read_text())
    if args.iom2_model is not None:
        with (output/'strict.cs').open('a') as source:
            source.write('\n'+load_engine()+'\n'+(ROOT/'tools/renode-iom-command-queue.cs').read_text()+'\n'+(ROOT/'tools/renode-iom.cs').read_text())
    rtc_engine=load_rtc_engine() if args.rtc_model is not None else None
    if rtc_engine is not None:
        with (output/'strict.cs').open('a') as source:source.write('\n'+rtc_engine+'\n'+(ROOT/'tools/renode-rtc.cs').read_text())
    if observation_points:
        with (output/'strict.cs').open('a') as source:source.write('\n'+(ROOT/'tools/renode-execution-observer.cs').read_text())
    shutil.copy2(ROOT/'tests/fixtures/renode-main-base.repl', output/'board.repl')
    if args.power_mode is not None or args.reset_latch is not None or args.startup_controls or args.gpio_config_storage or args.adc_calibration_control or args.rtc_osel_storage is not None or args.rtc_model is not None:
        board = (output/'board.repl').read_text().replace(
            'guard: Miscellaneous.BlackwallStrictMMIO @ sysbus 0x40000000',
            'guard: Miscellaneous.BlackwallG2StartupFixture @ sysbus 0x40000000')
        board = board.replace('    baseAddress: 0x40000000',
            '    baseAddress: 0x40000000\n    powerMode: "'+(args.power_mode or 'none')+'"\n'
            '    resetLatch: '+str(args.reset_latch if args.reset_latch is not None else -1))
        (output/'board.repl').write_text(board)
    if args.startup_controls:
        board = (output/'board.repl').read_text().replace('    baseAddress: 0x40000000',
            '    baseAddress: 0x40000000\n    startupControls: true')
        board = board.replace('ppb_guard: Miscellaneous.BlackwallStrictMMIO',
                              'ppb_guard: Miscellaneous.BlackwallG2StartupFixture')
        board = board.replace('    baseAddress: 0xe0010000',
                              '    baseAddress: 0xe0010000\n    startupControls: true')
        (output/'board.repl').write_text(board)
    guard_names = ['guard', 'ppb_guard']
    if args.watchdog_model:
        board = (output/'board.repl').read_text().replace('    size: 0x20000000', '    size: 0x24000')
        board += '''
wdt: Miscellaneous.BlackwallApollo510Watchdog @ sysbus 0x40024000
    -> nvic@1

guard_high: Miscellaneous.BlackwallStrictMMIO @ sysbus 0x40025000
    baseAddress: 0x40025000
    size: 0x1ffdb000
'''
        (output/'board.repl').write_text(board)
        guard_names = ['guard', 'wdt', 'guard_high', 'ppb_guard']
    if args.reset_controller:
        board = (output/'board.repl').read_text().replace('@ sysbus 0x40000000', '@ sysbus 0x40001000')
        board = board.replace('baseAddress: 0x40000000', 'baseAddress: 0x40001000')
        board = board.replace('size: 0x24000', 'size: 0x23000').replace('size: 0x20000000', 'size: 0x1ffff000')
        board += '\nrstgen: Miscellaneous.BlackwallResetController @ sysbus 0x40000000\n'
        if args.watchdog_model:
            board = board.replace('wdt: Miscellaneous.BlackwallApollo510Watchdog @ sysbus 0x40024000\n',
                                  'wdt: Miscellaneous.BlackwallApollo510Watchdog @ sysbus 0x40024000\n    resetController: rstgen\n')
        (output/'board.repl').write_text(board)
        guard_names.insert(0, 'rstgen')
    if args.shadow_info1 is not None:
        board = (output/'board.repl').read_text()
        low_base = '0x40001000' if args.reset_controller else '0x40000000'
        board = board.replace('    baseAddress: '+low_base,
            '    baseAddress: '+low_base+'\n    shadowInfo1: "'+args.shadow_info1+'"')
        if args.info1_metadata_fixture is not None:
            name = 'guard_high' if args.watchdog_model else 'guard'
            base = '0x40025000' if args.watchdog_model else low_base
            board = board.replace(name+': Miscellaneous.BlackwallStrictMMIO',
                                  name+': Miscellaneous.BlackwallG2StartupFixture')
            board = board.replace('    baseAddress: '+base,
                '    baseAddress: '+base+'\n    info1Metadata: "'+args.info1_metadata_fixture+'"')
        if args.adc_info_zero_fixture:
            if board.count('    baseAddress: '+base)!=1:raise ValueError('ADC info target guard is ambiguous')
            board=board.replace('    baseAddress: '+base,'    baseAddress: '+base+'\n    adcInfoZeroFixture: true')
        (output/'board.repl').write_text(board)
    if args.chip_revision_fixture is not None or args.spot_control_storage:
        board = (output/'board.repl').read_text()
        low_base = '0x40001000' if args.reset_controller else '0x40000000'
        board = board.replace('    baseAddress: '+low_base,
            '    baseAddress: '+low_base+'\n    chipRevision: '+str(args.chip_revision_fixture if args.chip_revision_fixture is not None else -1)+
            '\n    spotStorage: '+('true' if args.spot_control_storage else 'false'))
        (output/'board.repl').write_text(board)
    if args.memory_startup_fixture:
        board = (output/'board.repl').read_text()
        low_base = '0x40001000' if args.reset_controller else '0x40000000'
        board = board.replace('    baseAddress: '+low_base,
            '    baseAddress: '+low_base+'\n    memoryStartup: true')
        (output/'board.repl').write_text(board)
    if args.hal_startup_storage:
        board = (output/'board.repl').read_text()
        low_base = '0x40001000' if args.reset_controller else '0x40000000'
        board = board.replace('    baseAddress: '+low_base,
            '    baseAddress: '+low_base+'\n    halStorage: true')
        (output/'board.repl').write_text(board)
    if args.mram_control_storage:
        board = (output/'board.repl').read_text()
        low_base = '0x40001000' if args.reset_controller else '0x40000000'
        board = board.replace('    baseAddress: '+low_base,
            '    baseAddress: '+low_base+'\n    mramControlStorage: true')
        (output/'board.repl').write_text(board)
    if args.buck_override_storage:
        board = (output/'board.repl').read_text()
        low_base = '0x40001000' if args.reset_controller else '0x40000000'
        board = board.replace('    baseAddress: '+low_base,
            '    baseAddress: '+low_base+'\n    buckOverrideStorage: true')
        (output/'board.repl').write_text(board)
    if args.buck_start_storage:
        board = (output/'board.repl').read_text()
        low_base = '0x40001000' if args.reset_controller else '0x40000000'
        board = board.replace('    baseAddress: '+low_base,
            '    baseAddress: '+low_base+'\n    buckStartStorage: true')
        (output/'board.repl').write_text(board)
    if args.coreldo_reduction_storage:
        board = (output/'board.repl').read_text()
        low_base = '0x40001000' if args.reset_controller else '0x40000000'
        board = board.replace('    baseAddress: '+low_base,
            '    baseAddress: '+low_base+'\n    coreLdoReduction: true')
        (output/'board.repl').write_text(board)
    if args.memldo_setup_storage:
        board = (output/'board.repl').read_text()
        low_base = '0x40001000' if args.reset_controller else '0x40000000'
        board = board.replace('    baseAddress: '+low_base,
            '    baseAddress: '+low_base+'\n    memLdoSetup: true')
        (output/'board.repl').write_text(board)
    if args.buck_status_fixture is not None:
        board = (output/'board.repl').read_text()
        low_base = '0x40001000' if args.reset_controller else '0x40000000'
        board = board.replace('    baseAddress: '+low_base,
            '    baseAddress: '+low_base+'\n    buckStatusFixture: '+str({'off':0,'lp':2,'active':3}[args.buck_status_fixture]))
        (output/'board.repl').write_text(board)

    (output/'result.py').write_text('''import json
from System import Console
m = monitor.Machine
c = m['sysbus.cpu']
guards = []
for name in ('guard', 'ppb_guard'):
    g = m['sysbus.'+name]
    guards.append(dict(name=name, accesses=int(g.AccessCount), address=int(g.LastAddress),
                       width=int(g.LastWidth), operation=str(g.LastOperation), value=int(g.LastValue)))
g = m['sysbus.guard']
def guard_node(name):return g.Rtc if name=='rtc' else m['sysbus.'+name]
if hasattr(g,'Rtc') and g.Rtc is not None:
    r=g.Rtc
    guards.append(dict(name='rtc',accesses=int(r.AccessCount),address=int(r.LastAddress),width=int(r.LastWidth),operation=str(r.LastOperation),value=int(r.LastValue)))
def uart_report(module):
    if not hasattr(g,'Uarts') or not g.Uarts.ContainsKey(module):return None
    uart=g.Uarts[module];power=g.UartPowers[module]
    return dict(module=module,base_address=int(uart.BaseAddress),irq_number=int(uart.IrqNumber),off_profile=int(power.OffProfile),off_requests=int(power.OffRequests),power_cycles=int(power.PowerCycles),power_downs=int(uart.PowerDowns),quiescent=bool(uart.Quiescent),power_profile=int(power.Profile),phase=str(power.Phase),request_word=int(power.RequestWord),status_word=int(power.StatusWord),requests=int(power.Requests),responses=int(power.Responses),reads=int(uart.Reads),writes=int(uart.Writes),power_blocks=int(uart.PowerBlocks),clock_spare_clears=int(uart.ClockSpareClears),control=int(uart.Control),virtual_baud=int(uart.VirtualBaud),tx_bytes=[int(b) for b in uart.TxBytes],clock_hypothesis_hz=24000000,tx_timing='instant-empty',interrupts_enabled=bool(uart.InterruptsEnabled),interrupt_mask=int(uart.InterruptMask),raw_interrupts=int(uart.RawInterrupts),masked_interrupts=int(uart.MaskedInterrupts),irq_level=bool(uart.IRQ.IsSet),irq_assertions=int(uart.IRQAssertions),irq_transitions=int(uart.IRQTransitions),interrupt_clears=int(uart.InterruptClears),interrupt_mask_writes=int(uart.InterruptMaskWrites),tx_completions=int(uart.TxCompletions),irq_handler_address=int(uart.IrqHandlerAddress),irq_handler_entries=int(uart.IrqHandlerEntries),irq_exception_entries=int(uart.IrqExceptionEntries),last_active_vector=int(uart.LastActiveVector),rx_dma_implemented=False,hardware_verified=False)
gpu_configured_ring_snapshot = None
if hasattr(g,'GpuRing') and g.GpuRing is not None and int(g.GpuRing.StepsCompleted)==3:
    ring_base = int(g.GpuRing.BaseAddress)
    ring_length = int(g.GpuRing.ByteLength)
    if ring_base%8==0 and ring_length%16==0 and 16<=ring_length<=65536 and 0x20000000<=ring_base<=0x20380000-ring_length:
        gpu_configured_ring_snapshot = dict(base_address=ring_base,byte_length=ring_length,
            words=[int(m.SystemBus.ReadDoubleWord(ring_base+4*i)) for i in range(ring_length//4)],
            scope='post-stop bounded host SRAM snapshot; not allocation validation or GPU execution')
gpu_ring_capture = None
if hasattr(g,'GpuIdInitialization') and g.GpuIdInitialization:
    blocked = [entry for entry in guards if entry['accesses']]
    if len(blocked)==1 and blocked[0]['address']==0x400900ec and blocked[0]['operation']=='write' and blocked[0]['width']==4:
        r4 = int(c.GetRegister(4).RawValue)
        def sram_words(address, count):
            if address % 4 or not 0x20000000 <= address <= 0x20380000-4*count:
                return None
            return [int(m.SystemBus.ReadDoubleWord(address+4*i)) for i in range(count)]
        request = blocked[0]['value']
        descriptor = sram_words(r4,8)
        tails = {}
        if descriptor is not None:
            for unit,multiplier in [('bytes',1),('words',4)]:
                length = descriptor[4]*multiplier
                if 16 <= length <= 65536 and length%4==0:
                    address = (request&~7)+length-16
                    tails[unit] = dict(hypothetical_length_bytes=length,address=address,words=sram_words(address,4))
        gpu_ring_capture = dict(descriptor_candidate_address=r4,descriptor_words=descriptor,
            request_word=request,request_low_bits=request&7,ring_candidate_address=request&~7,
            ring_prefix_words=sram_words(request&~7,16),tail_unit_hypotheses=tails,lr=int(c.GetRegister(14).RawValue),
            scope='post-abort host inspection, bounded SRAM only; inferred descriptor/ring pointers, not DMA or GPU execution')
fixture = None
if hasattr(g, 'PowerReads'):
    fixture = dict(power_mode=str(g.PowerMode), power_reads=int(g.PowerReads),
        latch_value=int(g.LatchValue), latch_reads=int(g.LatchReads), latch_writes=int(g.LatchWrites),
        hardware_verified=bool(g.HardwareVerified), power_transitions=str(g.PowerTransitions),
        latch_meaning=str(g.LatchMeaning))
watchdog = None
if 'wdt' in [item['name'] for item in guards]:
    w = m['sysbus.wdt']
    watchdog = dict(cfg=int(w.Configuration), count=int(w.ReadDoubleWord(12)),
        cfg_reads=int(w.ConfigurationReads), cfg_writes=int(w.ConfigurationWrites),
        restarts=int(w.Restarts), irq_events=int(w.InterruptEvents), pending=bool(w.InterruptPending),
        reset_due=bool(w.ResetDue), source_clock=str(w.SourceClock),reset_propagation=str(w.ResetPropagation),
        reset_gating_evaluated=bool(w.ResetGatingEvaluated),reset_allowed_by_gate=bool(w.ResetAllowedByGate),
        hardware_verified=bool(w.HardwareVerified))
reset_controller = None
if 'rstgen' in [item['name'] for item in guards]:
    r = m['sysbus.rstgen']
    reset_controller = dict(cfg=int(r.Configuration),cfg_reads=int(r.ConfigurationReads),
        cfg_writes=int(r.ConfigurationWrites),wdren=bool(r.WatchdogResetEnabled),
        propagation=str(r.ResetPropagation),hardware_verified=bool(r.HardwareVerified))
Console.WriteLine('BLACKWALL_REPORT '+json.dumps(dict(pc=int(c.PC.RawValue),
    instructions=int(c.ExecutedInstructions),
    machine_paused_before_host=globals().get('blackwall_paused_before_host',None),
    prefetch_storage=dict(initialized=bool(m['sysbus.ppb_guard'].PrefetchInitialized),
        value=int(m['sysbus.ppb_guard'].PrefetchValue) if m['sysbus.ppb_guard'].PrefetchInitialized else None,
        reads=int(m['sysbus.ppb_guard'].PrefetchReads),writes=int(m['sysbus.ppb_guard'].PrefetchWrites),
        hardware_verified=False,prefetch_timing_and_transactions="not-modeled")
        if hasattr(m['sysbus.ppb_guard'],'PrefetchStorage') and m['sysbus.ppb_guard'].PrefetchStorage else None,
    gpu_config_response=(dict(initial_status_hypothesis=int(g.GpuInitialStatusHypothesis) if g.GpuInitialStatusHypothesis!=-1 else None,initial_status_reads=int(g.GpuInitialStatusReads),initial_status_evidence='explicit-unverified-initial-state' if g.GpuInitialStatusHypothesis!=-1 else 'unknown-read-blocked',low_value=0xf4030105,low_reads=int(g.GpuConfigLowReads),high_reads=int(g.GpuConfigHighReads),high_value=int(g.GpuConfigHighHypothesis) if g.GpuConfigHighHypothesis!=-1 else None,high_evidence='explicit-unverified-hypothesis' if g.GpuConfigHighHypothesis!=-1 else 'unknown-read-blocked',trace_only=True,hardware_verified=False,implemented_gpu_features=False) if hasattr(g,'GpuConfigLowResponse') and g.GpuConfigLowResponse else None),
    gpu_raster_init_storage=(dict(stored=bool(g.GpuRasterInitStored),value=1 if g.GpuRasterInitStored else None,interpretation='opaque-observed-initial-word; rendering effect unimplemented',trace_only=True,rendering_effect_implemented=False,hardware_verified=False) if hasattr(g,'GpuRasterInitStorage') and g.GpuRasterInitStorage else None),
    gpu_initial_resets=(dict(steps_completed=int(g.GpuReset.StepsCompleted),command_processor_resets=int(g.GpuReset.CommandProcessorResets),gpu_resets=int(g.GpuReset.GpuResets),ring_requires_revalidation=bool(g.GpuReset.RingRequiresRevalidation),scope='initial quiescent control resets only; programmed ring record retained, validity unknown; no active GPU reset propagation',hardware_verified=False) if hasattr(g,'GpuReset') and g.GpuReset is not None else None),
    gpu_identity_response=(dict(profile='source-reset' if g.GpuIdentityProfile==1 else 'absent',reads=int(g.GpuIdentityReads),value=0x86362000 if g.GpuIdentityProfile==1 else 0,hardware_verified=False) if hasattr(g,'GpuIdentityProfile') and g.GpuIdentityProfile!=-1 else None),
    gpu_configured_ring_snapshot=gpu_configured_ring_snapshot,
    gpu_ring_configuration=(dict(steps_completed=int(g.GpuRing.StepsCompleted),request_word=int(g.GpuRing.RequestWord),base_address=int(g.GpuRing.BaseAddress),byte_length=int(g.GpuRing.ByteLength),effects='configuration latches only; no DMA or GPU commands',hardware_verified=False) if hasattr(g,'GpuRing') and g.GpuRing is not None else None),
    gpu_ring_capture=gpu_ring_capture,
    gpu_id_initialization=(dict(initialized=bool(g.GpuIdInitialized),semantics='assumed-initial-command-list-ID-zero-only',hardware_verified=False) if hasattr(g,'GpuIdInitialization') and g.GpuIdInitialization else None),
    gpu_interrupt_clear=(dict(clears=int(g.GpuInterruptClears),initial_irq='assumed-idle',commands_executed=0,hardware_verified=False) if hasattr(g,'GpuInterruptClear') and g.GpuInterruptClear else None),
    gpu_power_response=(dict(profile='active' if g.GpuPower.Profile==1 else 'stuck-off',phase=str(g.GpuPower.Phase),request_word=int(g.GpuPower.RequestWord),status_word=int(g.GpuPower.StatusWord),enable_reads=int(g.GpuPower.EnableReads),status_reads=int(g.GpuPower.StatusReads),enable_writes=int(g.GpuPower.EnableWrites),transitions=int(g.GpuPower.Transitions),hardware_verified=False,completion_latency='assumed-zero-at-first-status-read',effects='GPU bit18 digital response only; off requires separate option; no physical power or GPU execution') if hasattr(g,'GpuPower') and g.GpuPower is not None else None),
    adc_constant_scan=(dict(functional_scan_implemented=True,analog_conversion_implemented=False,raw_code=int(g.AdcScan.RawCode),primed=bool(g.AdcScan.Primed),scans=int(g.AdcScan.Scans),samples=int(g.AdcScan.Samples),pops=int(g.AdcScan.Pops),peeks=int(g.AdcScan.Peeks),count=int(g.AdcScan.Count),pending=int(g.AdcScan.Pending),blocked=str(g.AdcScan.Blocked),software_triggers=int(g.AdcScan.SoftwareTriggers),conversion_latency='assumed-zero',fifo_pop_count='assumed-post-pop',physical_sensor=False,irq_generation_implemented=False) if hasattr(g,'AdcScan') and g.AdcScan is not None else None),
    adc_internal_trigger=(dict(source_hz=int(g.AdcInternalTrigger.SourceHz),phase=str(g.AdcInternalTrigger.Phase),word=int(g.AdcInternalTrigger.Word) if g.AdcInternalTrigger.StartRequests else None,divider=int(g.AdcInternalTrigger.Divider),tick_limit=int(g.AdcInternalTrigger.TickLimit),start_requests=int(g.AdcInternalTrigger.StartRequests),trigger_events=int(g.AdcInternalTrigger.TriggerEvents),clock_hypothesis=True,conversion_counter_scope='simulated post-average slot results',first_interval_hypothesis='TIMERMAX ticks',adc_conversions=int(g.AdcScan.Samples) if g.AdcScan is not None else 0,fifo_generated=int(g.AdcScan.Samples) if g.AdcScan is not None else 0,adc_irq_generated=0,hardware_verified=False) if hasattr(g,'AdcInternalTrigger') and g.AdcInternalTrigger is not None else None),
    adc_enable_latch=(dict(enable_requests=int(g.AdcDisabledConfig.EnableRequests),cfg_bit_set=bool(g.AdcDisabledConfig.Enabled) if g.AdcDisabledConfig.Values.ContainsKey(0x40038000) else None,physical_adc_ready_implemented=False,adc_conversion_implemented=False,hardware_verified=False) if hasattr(g,'AdcDisabledConfig') and g.AdcDisabledConfig is not None and g.AdcDisabledConfig.EnableLatch else None),
    adc_disabled_config=(dict(scope='configuration storage only; functional scan is separate',values={hex(int(a)):int(g.AdcDisabledConfig.Values[a]) for a in g.AdcDisabledConfig.Values.Keys},reads=int(g.AdcDisabledConfig.Reads),writes=int(g.AdcDisabledConfig.Writes),power_blocks=int(g.AdcDisabledConfig.PowerBlocks),initial_values_known=bool(g.AdcDisabledConfig.SourceReset),adc_enabled=bool(g.AdcDisabledConfig.Enabled) if g.AdcDisabledConfig.Values.ContainsKey(0x40038000) else None,adc_conversion_implemented=False,hardware_verified=False) if hasattr(g,'AdcDisabledConfig') and g.AdcDisabledConfig is not None else None),
    adc_trigger_config=(dict(configured=bool(g.AdcTriggerConfigured),value=int(g.AdcTriggerConfig.Value) if g.AdcTriggerConfigured else None,reads=int(g.AdcTriggerConfig.Reads),writes=int(g.AdcTriggerConfig.Writes),power_blocks=int(g.AdcTriggerPowerBlocks),initial_value_known=False,timer_execution_implemented=bool(g.AdcInternalTrigger is not None),adc_conversion_implemented=False,hardware_verified=False) if hasattr(g,'AdcTriggerConfig') and g.AdcTriggerConfig is not None else None),
    iom2=iom_report(2),
    ioms=[iom_report(module) for module in __IOM_MODULES__],
    uart1=uart_report(1),
    uarts=([uart_report(int(module)) for module in g.Uarts.Keys] if hasattr(g,'Uarts') else []),
    adc_power_off_response=(dict(profile=int(g.AdcPower.OffProfile),requests=int(g.AdcPower.OffRequests),epoch_retired=bool(g.AdcPower.EpochRetired),physical_power_implemented=False) if hasattr(g,'AdcPower') and g.AdcPower is not None and g.AdcPower.OffProfile!=-1 else None),
    adc_power_response=(dict(profile=int(g.AdcPower.Profile),phase=str(g.AdcPower.Phase),request_word=int(g.AdcPower.RequestWord),status_word=int(g.AdcPower.StatusWord),requests=int(g.AdcPower.Requests),cancellations=int(g.AdcPower.Cancellations),transitions=int(g.AdcPower.Transitions),responses=int(g.AdcPower.Responses),hardware_verified=False,physical_power_implemented=False,adc_conversion_implemented=False,response_latency='assumed-zero-at-first-status-read') if hasattr(g,'AdcPower') and g.AdcPower is not None else None),
    adc_calibration_control=(dict(initial_word=int(g.AdcCalibrationControl.InitialValue),value=int(g.AdcCalibrationControl.Value),reads=int(g.AdcCalibrationControl.Reads),writes=int(g.AdcCalibrationControl.Writes),calibrated=False,calibration_execution_implemented=False,adc_conversion_implemented=False,hardware_verified=False) if hasattr(g,'AdcCalibrationControl') and g.AdcCalibrationControl is not None else None),
    sram_windows=[dict(base=address,bytes=[int(m['sysbus'].ReadByte(address+i)) for i in range(size)]) for address,size in __CAPTURE_SRAM_WINDOWS__],
    adc_info_zero=[dict(name=item['name'],word_reads=[int(guard_node(item['name']).AdcInfo.Reads[i]) for i in range(5)],valid_calibration=False,hardware_verified=False,profile='explicit-zero-fallback') for item in guards if hasattr(guard_node(item['name']),'AdcInfo') and guard_node(item['name']).AdcInfo is not None],
    register_context=({('r'+str(i)):int(c.GetRegister(i).RawValue) for i in range(16)} if __CAPTURE_ITCM__ else None),
    stack_context=(dict(base=int(c.GetRegister(13).RawValue),words=[int(m['sysbus'].ReadDoubleWord(int(c.GetRegister(13).RawValue)+i*4)) for i in range(32)]) if __CAPTURE_ITCM__ and 0x20000000<=int(c.GetRegister(13).RawValue)<=0x20380000-128 and int(c.GetRegister(13).RawValue)%4==0 else None),
    itcm_prefix=([int(m['sysbus'].ReadByte(i)) for i in range(256)] if __CAPTURE_ITCM__ else None),
    gpio_output_latch=(dict(words=[int(g.GpioOutput.Words[i]) for i in range(7)],reads=int(g.GpioOutput.Reads),direct_writes=int(g.GpioOutput.DirectWrites),set_writes=int(g.GpioOutput.SetWrites),clear_writes=int(g.GpioOutput.ClearWrites),hardware_verified=False,pad_behavior_implemented=False,external_devices_implemented=False,initial_words='source-diagram-zero-assumption') if hasattr(g,'GpioOutput') and g.GpioOutput is not None else None),
    gpio_interrupt_idle=(dict(enable_words=[int(g.GpioInterrupts.EnableWords[i]) for i in range(14)],clear_requests=[int(g.GpioInterrupts.ClearRequests[i]) for i in range(14)],enable_reads=int(g.GpioInterrupts.EnableReads),enable_writes=int(g.GpioInterrupts.EnableWrites),status_reads=int(g.GpioInterrupts.StatusReads),clear_writes=int(g.GpioInterrupts.ClearWrites),hardware_verified=False,events_implemented=False,irq_generation_implemented=False,profile='explicit-initial-idle') if hasattr(g,'GpioInterrupts') and g.GpioInterrupts is not None else None),
    gpio_config=(dict(unlocked=bool(g.GpioConfig.Unlocked),key_writes=int(g.GpioConfig.KeyWrites),config_writes=int(g.GpioConfig.ConfigWrites),config_reads=int(g.GpioConfig.ConfigReads),values={hex(int(a)):int(g.GpioConfig.Values[a]) for a in g.GpioConfig.Values.Keys},hardware_verified=False,effects='guest-written configuration storage only; no pin functions, signals, IRQ or electrical behavior') if hasattr(g,'GpioConfig') and g.GpioConfig is not None else None),
    gpu_off_sequence=(dict(steps_completed=int(g.GpuOffSequence.StepsCompleted),complete=bool(g.GpuOffSequence.Complete),original_core_word=int(g.GpuOffSequence.OriginalCoreWord),boost_delta=int(g.GpuOffSequence.BoostDelta),hardware_verified=False,effects='ordered digital fields only; no analog settling or GPU re-enable') if hasattr(g,'GpuOffSequence') and g.GpuOffSequence is not None else None),
    gpu_power_off_response=(dict(profile=int(g.GpuPower.OffProfile),requests=int(g.GpuPower.OffRequests),epoch_retired=bool(g.GpuPower.EpochRetired),re_enable_supported=False,retention_verified=False,hardware_verified=False) if hasattr(g,'GpuPower') and g.GpuPower is not None and int(g.GpuPower.OffProfile)!=-1 else None),
    gpu_power_preparation=(dict(steps_completed=int(g.GpuPreparation.StepsCompleted),complete=bool(g.GpuPreparation.Complete),original_core_word=int(g.GpuPreparation.OriginalCoreWord),boost_delta=int(g.GpuPreparation.BoostDelta),hardware_verified=False,effects='ordered fields only; no physical rails, settling, power or GPU engine') if hasattr(g,'GpuPreparation') and g.GpuPreparation is not None else None),
    gfx_power_storage=(dict(selection=int(g.GfxPower.Selection),request=int(g.GfxPower.Request),selection_reads=int(g.GfxPower.SelectionReads),request_reads=int(g.GfxPower.RequestReads),selection_writes=int(g.GfxPower.SelectionWrites),request_writes=int(g.GfxPower.RequestWrites),hardware_verified=False,effects='field storage only; no GPU execution, voltage, frequency or settling model') if hasattr(g,'GfxPower') and g.GfxPower is not None else None),
    chip_info=(dict(profile='source-reset-zero-ids',registers=[dict(address=hex(int(a)),value=int(g.ChipInfo.GetValue(a)),reads=int(g.ChipInfo.GetReads(a))) for a in g.ChipInfo.Addresses],unique_ids='synthetic-zero-not-device-identifiers',revision_source='shared-chip-revision-fixture',jedec_implemented=bool(g.ChipInfo.JedecMockEnabled),jedec_mock=(dict(part=int(g.ChipInfo.JedecMockPart),cid=int(g.ChipInfo.JedecMockCid),actual_device_verified=False) if g.ChipInfo.JedecMockEnabled else None),hardware_verified=False,source_reset_is_device_state=False) if hasattr(g,'ChipInfo') and g.ChipInfo is not None else None),
    rtc=(dict(profile='epoch2000-100hz',initial_epoch='2000-01-01T00:00:00.00',virtual_counter_hz=100,virtual_date=str(g.Rtc.VirtualDate),control=int(g.Rtc.Control),reads=int(g.Rtc.Reads),writes=int(g.Rtc.Writes),commits=int(g.Rtc.Commits),late_reads=int(g.Rtc.LateReads),write_pending=bool(g.Rtc.WritePending),pair_pending=bool(g.Rtc.PairPending),irq=bool(g.Rtc.IRQ.IsSet),counter_write_profile=('hal-low-upper' if g.Rtc.CounterWritesProfile else 'unsupported'),last_error=str(g.Rtc.LastError),hardware_verified=False,physical_oscillator_verified=False,century_rollover_implemented=False,read_window_assumption='10ms virtual elapsed with held upper',write_latency='staged lower; synchronous validated upper commit') if hasattr(g,'Rtc') and g.Rtc is not None else None),
    rtc_osel_storage=(dict(initial_request=int(g.RtcOsel.InitialValue),request_word=int(g.RtcOsel.Value),reads=int(g.RtcOsel.Reads),writes=int(g.RtcOsel.Writes),effective_source=None,oscillator_implemented=False,rtc_time_implemented=False,silicon_revision_effects_implemented=False,hardware_verified=False,profile='explicit-request-latch-only') if hasattr(g,'RtcOsel') and g.RtcOsel is not None else None),
    mcu_clock_response=(dict(profile=('nominal','hfrc2-unready','no-ack','denied')[int(g.McuClock.Profile)],phase=str(g.McuClock.Phase),
        mode_word=int(g.McuClock.ModeWord),misc_word=int(g.McuClock.MiscWord),hfrc_force_control=bool(g.McuClock.HfrcForceControl),hfrc_forced=bool(g.McuClock.HfrcForced),hfrc2_enabled=bool(g.McuClock.Enabled),hfrc2_ready=bool(g.McuClock.Ready),
        force_writes=int(g.McuClock.ForceWrites),clock_reads=int(g.McuClock.ClockReads),mode_reads=int(g.McuClock.ModeReads),
        mode_writes=int(g.McuClock.ModeWrites),transitions=int(g.McuClock.Transitions),hardware_verified=False,completion_latency='assumed-zero')
        if hasattr(g,'McuClock') and g.McuClock is not None else None),
    buck_response=(dict(profile='active' if g.BuckResponse==3 else 'stuck-off',phase=str(g.BuckResponsePhase),reads=int(g.BuckResponseReads),
        transitions=int(g.BuckResponseTransitions),hardware_verified=False,completion_latency='assumed-zero-after-setup')
        if hasattr(g,'BuckResponse') and g.BuckResponse!=-1 else None),
    vddf_tempco_storage=(dict(applied=bool(g.VddfTempco.Applied),original_word=int(g.VddfTempco.OriginalWord),
        reduced_trim=int(g.VddfTempco.ReducedTrim),hardware_verified=False) if hasattr(g,'VddfTempco') and g.VddfTempco is not None else None),
    coherent_dcache=(dict(enabled=bool(system_control.DataCache.Enabled),selected=bool(system_control.DataCache.Selected),
        selector_reads=int(system_control.DataCache.SelectorReads),selector_writes=int(system_control.DataCache.SelectorWrites),
        geometry_reads=int(system_control.DataCache.GeometryReads),initialized_lines=int(system_control.DataCache.InitializedLines),
        invalidate_set_way=int(system_control.DataCache.Invalidations),clean_set_way=int(system_control.DataCache.Cleans),
        clean_invalidate_set_way=int(system_control.DataCache.CleanInvalidations),ccsidr=0xf03fe019,hardware_verified=False)
        if system_control.DataCache is not None else None),
    system_control=dict(functional_icache=bool(system_control.FunctionalICache),enabled=bool(system_control.ICacheEnabled),
        invalidations=int(system_control.Invalidations),ccr_reads=int(system_control.CcrReads),ccr_writes=int(system_control.CcrWrites),
        violations=int(system_control.Violations),operation=str(system_control.LastOperation),address=int(system_control.LastAddress),
        width=int(system_control.LastWidth),value=int(system_control.LastValue),pc=int(system_control.LastPC),hardware_verified=False,
        cache_latency_eviction_and_power="not-modeled"),
    memory_policy=dict(violations=int(memory_policy.Violations),operation=str(memory_policy.LastOperation),
        address=int(memory_policy.LastAddress),width=int(memory_policy.LastWidth),pc=int(memory_policy.LastPC),
        written_bytes=int(memory_policy.WrittenBytes)), guards=guards, startup_fixture=fixture, watchdog=watchdog,
    reset_controller=reset_controller,
    buck_status_fixture=dict(value=int(g.BuckStatusFixture)<<4,reads=int(g.BuckStatusReads),budget=1,
        other_status_fields="assumed zero",hardware_verified=False,analog_transitions_and_timing="not-modeled")
        if hasattr(g,'BuckStatusFixture') and g.BuckStatusFixture != -1 else None,
    memldo_setup=dict(steps_completed=int(g.MemLdo.StepsCompleted),hardware_verified=False,
        effects="ordered field storage only; analog power and readiness unprovided")
        if hasattr(g,'MemLdo') and g.MemLdo is not None else None,
    coreldo_reduction=dict(applied=bool(g.CoreLdo.Applied),original_word=int(g.CoreLdo.OriginalWord),
        reduced_trim=int(g.CoreLdo.ReducedTrim),cache_witness=bool(g.CoreLdo.CacheWitness),hardware_verified=False,
        effects="one field reduction only; voltage and real calibration not modeled") if hasattr(g,'CoreLdo') and g.CoreLdo is not None else None,
    buck_start=dict(steps_completed=int(g.BuckStart.StepsCompleted),enable_requested=bool(g.BuckStart.EnableRequested),
        hardware_verified=False,power_ready_feedback="automatic readiness unprovided; optional single diagnostic sample reported separately",registers={
        hex(int(a)):dict(value=int(g.BuckStart.Registers[a].Value),reads=int(g.BuckStart.Registers[a].Reads),writes=int(g.BuckStart.Registers[a].Writes))
        for a in g.BuckStart.Registers.Keys}) if hasattr(g,'BuckStart') and g.BuckStart is not None else None,
    buck_override=dict(steps_completed=int(g.BuckOverrideStep),sequence_length=10,complete=bool(g.BuckOverrideComplete),
        hardware_verified=False,effects="ordered VRCTRL storage only; voltage/switching/deep-sleep not modeled")
        if hasattr(g,'BuckOverrideStorage') and g.BuckOverrideStorage else None,
    mram_control=dict(initial=2,value=int(g.MramValue),reads=int(g.MramReads),writes=int(g.MramWrites),
        hardware_verified=False,effects="storage only; MRAM wakeup/latency/power/recall/contents not modeled")
        if hasattr(g,'MramControlStorage') and g.MramControlStorage else None,
    hal_storage=dict(hardware_verified=False,valid_calibration=False,
        effects="storage only; clocks/analog voltage/TON/switching/clock-mux recovery not modeled",
        catalog_sha256=str(g.HalStorage.TrimCatalogSha256),registers={
        hex(int(address)):dict(value=int(g.HalStorage.Registers[address].Value),
            reads=int(g.HalStorage.Registers[address].Reads),writes=int(g.HalStorage.Registers[address].Writes))
        for address in g.HalStorage.Registers.Keys}) if hasattr(g,'HalStorage') and g.HalStorage is not None else None,
    memory_startup=dict(hardware_verified=False,
        transitions="one ROM disable with zero latency; other power/sleep/retention effects not modeled",
        rom_disables=int(g.MemoryStartup.RomDisables),registers={
        hex(int(address)):dict(value=int(g.MemoryStartup.Registers[address].Value),
            reads=int(g.MemoryStartup.Registers[address].Reads),writes=int(g.MemoryStartup.Registers[address].Writes))
        for address in g.MemoryStartup.Registers.Keys}) if hasattr(g,'MemoryStartup') and g.MemoryStartup is not None else None,
    silicon=dict(revision=int(g.ChipRevision),revision_reads=int(g.ChipRevisionReads),
        acrg_value=int(g.AcrgValue),acrg_reads=int(g.AcrgReads),acrg_writes=int(g.AcrgWrites),
        vrctrl_value=int(g.VrctrlValue),vrctrl_reads=int(g.VrctrlReads),vrctrl_writes=int(g.VrctrlWrites),
        analog_power=str(g.AnalogPower),hardware_verified=bool(g.HardwareVerified))
        if hasattr(g,'ChipRevision') and (g.ChipRevision != -1 or g.SpotStorage) else None,
    information=[dict(name=item['name'],source=str(guard_node(item['name']).ShadowInfo1),
        metadata=str(guard_node(item['name']).Info1Metadata),
        shadow_reads=int(guard_node(item['name']).ShadowReads),
        tracker_reads=int(guard_node(item['name']).TrackerReads),
        revision_reads=int(guard_node(item['name']).TrimRevisionReads),
        ft1_reads=int(guard_node(item['name']).Ft1Reads),
        valid_calibration=bool(guard_node(item['name']).ValidCalibration)) for item in guards
        if hasattr(guard_node(item['name']), 'ShadowInfo1') and
        (guard_node(item['name']).ShadowInfo1 != 'none' or guard_node(item['name']).Info1Metadata != 'none')],
    controls=[dict(name=name,
        device_reads=int(m['sysbus.'+name].DevicePowerReads), device_writes=int(m['sysbus.'+name].DevicePowerWrites),
        debug_reads=int(m['sysbus.'+name].DebugReads), debug_writes=int(m['sysbus.'+name].DebugWrites),
        core_reads=int(m['sysbus.'+name].CorePowerReads), core_writes=int(m['sysbus.'+name].CorePowerWrites),
        wic_reads=int(m['sysbus.'+name].WicReads), wic_writes=int(m['sysbus.'+name].WicWrites),
        wic_value=int(m['sysbus.'+name].WicValue)) for name in ('guard','ppb_guard')
        if hasattr(m['sysbus.'+name], 'StartupControls') and m['sysbus.'+name].StartupControls])))
''')
    if args.prefetch_control_storage:
        board = (output/'board.repl').read_text().replace('    baseAddress: 0xe0010000',
            '    baseAddress: 0xe0010000\n    prefetchStorage: true')
        (output/'board.repl').write_text(board)
    if args.iom2_model is not None:guard_names+=['iom'+str(n) for n in iom_modules]+['guard_iom'+str(n)+'_tail' for n in iom_modules]
    result_script = (output/'result.py').read_text().replace(
        "for name in ('guard', 'ppb_guard'):", 'for name in '+repr(tuple(guard_names))+':')
    (output/'result.py').write_text(result_script)
    runtime="""import clr
import time
from Antmicro.Renode.Utilities import TypeManager
from Antmicro.Renode.Core import EmulationManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallMemoryPolicy').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallMemoryPolicy,BlackwallSystemControl
m=monitor.Machine
memory_policy=BlackwallMemoryPolicy(m,m['sysbus.cpu'],m['sysbus.main'],m['sysbus.itcm'],%s)
memory_policy.Attach()
system_control=BlackwallSystemControl(m,m['sysbus.cpu'],m['sysbus.nvic'],%s,%s)
system_control.Attach()
e=EmulationManager.Instance.CurrentEmulation
e.StartAll()
time.sleep(%s)
blackwall_paused_before_host=bool(m.IsPaused)
e.PauseAll()
""" % (len(raw),str(args.coherent_icache_model),str(args.coherent_dcache_model),args.wall_run_seconds)
    if args.uart1_interrupts:
        hooks=[]
        for module in uart_modules:
            offset=(31+module)*4
            irq_vector=int.from_bytes(raw[offset:offset+4],'little')
            if not irq_vector&1 or not BASE<=irq_vector-1<BASE+len(raw):raise ValueError('UART IRQ vector outside main')
            hooks.append("m['sysbus.guard'].Uarts[%s].AttachIrqProbe(m['sysbus.cpu'],%s,m)" % (module,irq_vector&~1))
        runtime=runtime.replace('e=EmulationManager.Instance.CurrentEmulation', '\n'.join(hooks)+'\ne=EmulationManager.Instance.CurrentEmulation')
    result_script=(output/'result.py').read_text().replace('__CAPTURE_ITCM__',str(args.capture_itcm_prefix)).replace('__CAPTURE_SRAM_WINDOWS__',repr(capture_windows))
    iom_function="""def iom_report(module):
    if module not in __IOM_MODULES__:return None
    w=m['sysbus.iom'+str(module)];p=w.Power
    return dict(module=module,base_address=int(w.BaseAddress),irq_number=6+module,
        engine='source-derived-fifo-corrected',i2c_config_storage_only=True,
        i2c_configuration=int(w.I2CConfiguration),last_i2c_configuration=int(w.LastI2CConfiguration),i2c_configuration_writes=int(w.I2CConfigurationWrites),
        power_profile=int(p.Profile),power_phase=str(p.Phase),request_word=int(p.RequestWord),status_word=int(p.StatusWord),power_requests=int(p.Requests),power_responses=int(p.Responses),
        cq=dict(configuration=int(w.CommandQueue.Configuration),address=int(w.CommandQueue.Address),software_flags=int(w.CommandQueue.SoftwareFlags),current_index=int(w.CommandQueue.CurrentIndex),end_index=int(w.CommandQueue.EndIndex),pause_enable=int(w.CommandQueue.PauseEnable),known_flags=int(w.CommandQueue.KnownFlags),known_flags_mask=0x80ff,mock_input_levels=int(w.CommandQueue.InputLevels),effective_flags=int(w.CommandQueue.EffectiveFlags),available_flags_mask=int(w.CommandQueue.AvailableFlagsMask),unknown_external_flags_mask=(0x7f00 if w.CommandQueue.InputLevels<0 else 0),status=int(w.CommandQueue.Status),pairs=int(w.CommandQueue.Pairs),last_pair_address=int(w.CommandQueue.LastPairAddress),last_target=int(w.CommandQueue.LastTarget),last_data=int(w.CommandQueue.LastData),last_error=str(w.CommandQueue.LastError),mock_external_inputs_assumed=(w.CommandQueue.InputLevels>=0),physical_flags_verified=False,execution_scope='bounded SRAM/own IOM with explicit mock pins when set; no physical inputs/timing'),dma_trigger_storage=int(w.DmaTrigger),
        reads=int(w.Reads),writes=int(w.Writes),commands=int(w.Commands),power_downs=int(w.PowerDowns),clock_configuration=int(w.ClockConfiguration),fifo_control=int(w.FifoControl),submodule_control=int(w.SubmoduleControl),irq=bool(w.IRQ.IsSet),hardware_verified=False,peer_attached=False,dma_execution_implemented=False,dma_and_cq_implemented=False,timing_implemented=False)
"""
    result_script=result_script.replace("Console.WriteLine('BLACKWALL_REPORT ",iom_function+"\nConsole.WriteLine('BLACKWALL_REPORT ")
    result_script=result_script.replace('__IOM_MODULES__',repr(iom_modules if args.iom2_model is not None else ()))
    (output/'result.py').write_text(result_script)
    runtime+=result_script
    (output/'run.py').write_text("try:\n"+''.join('    '+line+'\n' for line in runtime.splitlines())+
        "except Exception as error:\n    from System import Console\n    Console.WriteLine('BLACKWALL_RUNTIME_ERROR '+str(error))\n")
    if observation_points:
        (output/'run.py').write_text(instrument_execution((output/'run.py').read_text(),observation_points,observation_captures))
    if args.buck_response_model is not None:
        low_base='0x40001000' if args.reset_controller else '0x40000000'
        board=(output/'board.repl').read_text()
        marker='    baseAddress: '+low_base
        if board.count(marker)!=1:raise ValueError('Buck response target guard is ambiguous or missing')
        board=board.replace(marker,
            marker+'\n    buckResponse: '+str(3 if args.buck_response_model=='active' else 0)
            +'\n    vddfTempcoStorage: '+str(args.vddf_tempco_storage).lower())
        (output/'board.repl').write_text(board)
    if args.rtc_osel_storage is not None:
        marker='    baseAddress: '+('0x40001000' if args.reset_controller else '0x40000000')
        board=(output/'board.repl').read_text()
        if board.count(marker)!=1:raise ValueError('RTC OSEL target guard is ambiguous')
        (output/'board.repl').write_text(board.replace(marker,marker+'\n    rtcOselInitial: '+str(('xt','lfrc').index(args.rtc_osel_storage))))
    if args.mcu_clock_response is not None:
        marker='    baseAddress: '+('0x40001000' if args.reset_controller else '0x40000000')
        board=(output/'board.repl').read_text()
        if board.count(marker)!=1:raise ValueError('MCU clock response target guard is ambiguous')
        (output/'board.repl').write_text(board.replace(marker,marker+'\n    mcuClockResponse: '+str(('nominal','hfrc2-unready','no-ack','denied').index(args.mcu_clock_response))))
    if args.gpu_power_response is not None:
        marker='    baseAddress: '+('0x40001000' if args.reset_controller else '0x40000000')
        board=(output/'board.repl').read_text()
        if board.count(marker)!=1:raise ValueError('GPU power response target guard is ambiguous')
        (output/'board.repl').write_text(board.replace(marker,marker+'\n    gpuPowerResponse: '+str(1 if args.gpu_power_response=='active' else 0)))
    if args.gpu_power_off_response is not None:
        marker='    baseAddress: '+('0x40001000' if args.reset_controller else '0x40000000')
        board=(output/'board.repl').read_text()
        if board.count(marker)!=1:raise ValueError('GPU off target guard is ambiguous')
        (output/'board.repl').write_text(board.replace(marker,marker+'\n    gpuPowerOffResponse: '+str(1 if args.gpu_power_off_response=='off' else 0)))
    if args.gpu_interrupt_clear:
        marker='    baseAddress: '+('0x40001000' if args.reset_controller else '0x40000000')
        board=(output/'board.repl').read_text()
        if board.count(marker)!=1:raise ValueError('GPU IRQ clear target guard is ambiguous')
        board=board.replace(marker,marker+'\n    gpuInterruptClear: true')
        if args.gpu_id_initialization:
            board=board.replace(marker,marker+'\n    gpuIdInitialization: true')
        if args.gpu_ring_configuration:
            board=board.replace(marker,marker+'\n    gpuRingConfiguration: true')
        if args.gpu_identity_response is not None:
            board=board.replace(marker,marker+'\n    gpuIdentityResponse: '+str(1 if args.gpu_identity_response=='source-reset' else 0))
        if args.gpu_initial_resets:
            board=board.replace(marker,marker+'\n    gpuInitialResets: true')
        if args.gpu_raster_init_storage:
            board=board.replace(marker,marker+'\n    gpuRasterInitStorage: true')
        if args.gpu_config_low_response:
            board=board.replace(marker,marker+'\n    gpuConfigLowResponse: true')
        if args.gpu_config_high_hypothesis is not None:
            board=board.replace(marker,marker+'\n    gpuConfigHighHypothesis: '+str(0 if args.gpu_config_high_hypothesis=='zero' else 512))
        if args.gpu_initial_status_hypothesis is not None:
            board=board.replace(marker,marker+'\n    gpuInitialStatusHypothesis: '+str(0 if args.gpu_initial_status_hypothesis=='zero' else 1))
        if args.watchdog_model:
            board=board.replace('guard_high: Miscellaneous.BlackwallStrictMMIO', 'guard_high: Miscellaneous.BlackwallG2StartupFixture')
            high='    baseAddress: 0x40025000'
            if board.count(high)!=1:raise ValueError('GPU high guard is ambiguous')
            board=board.replace(high,high+'\n    gpuControlOwner: guard')
        (output/'board.repl').write_text(board)
    if args.uart1_model is not None:
        marker='    baseAddress: '+('0x40001000' if args.reset_controller else '0x40000000')
        board=(output/'board.repl').read_text()
        if board.count(marker)!=1:raise ValueError('UART target ambiguous')
        parameters=[]
        for module in uart_modules:
            parameters+=['    uart%s: uart%s_adapter'%(module,module),'    uart%sPowerResponse: %s'%(module,1 if args.uart1_model=='active' else 0)]
            if args.uart1_off_response is not None:parameters+=['    uart%sOffResponse: %s'%(module,0 if args.uart1_off_response=='off' else 1)]
        board=board.replace(marker,marker+'\n'+'\n'.join(parameters))
        for module in uart_modules:
            board+='\nuart%s_adapter: Miscellaneous.BlackwallUartAdapter\n    module: %s\n'%(module,module)
            if args.uart1_interrupts:board+='    interrupts: true\n    IRQ -> nvic@%s\n'%(15+module)
        (output/'board.repl').write_text(board)
    if args.adc_power_off_response is not None:
        marker='    baseAddress: '+('0x40001000' if args.reset_controller else '0x40000000')
        board=(output/'board.repl').read_text()
        if board.count(marker)!=1:raise ValueError('ADC off target ambiguous')
        (output/'board.repl').write_text(board.replace(marker,marker+'\n    adcPowerOffResponse: '+str(1 if args.adc_power_off_response=='off' else 0)))
    if args.adc_constant_channel3 is not None:
        marker='    baseAddress: '+('0x40001000' if args.reset_controller else '0x40000000')
        board=(output/'board.repl').read_text()
        if board.count(marker)!=1:raise ValueError('ADC scan target ambiguous')
        (output/'board.repl').write_text(board.replace(marker,marker+'\n    adcConstantChannel3: '+str(args.adc_constant_channel3)))
    if args.adc_trigger_source_hz is not None:
        marker='    baseAddress: '+('0x40001000' if args.reset_controller else '0x40000000')
        board=(output/'board.repl').read_text()
        if board.count(marker)!=1:raise ValueError('ADC internal trigger target guard is ambiguous')
        board=board.replace(marker,marker+'\n    adcInternalTrigger: adc_trigger')
        board+='\nadc_trigger: Miscellaneous.BlackwallAdcInternalTrigger\n    sourceHz: '+str(args.adc_trigger_source_hz)+'\n'
        (output/'board.repl').write_text(board)
    if args.adc_enable_latch:
        marker='    baseAddress: '+('0x40001000' if args.reset_controller else '0x40000000')
        board=(output/'board.repl').read_text()
        if board.count(marker)!=1:raise ValueError('ADC enable target guard is ambiguous')
        (output/'board.repl').write_text(board.replace(marker,marker+'\n    adcEnableLatch: true'))
    if args.adc_disabled_config_storage:
        marker='    baseAddress: '+('0x40001000' if args.reset_controller else '0x40000000')
        board=(output/'board.repl').read_text()
        if board.count(marker)!=1:raise ValueError('ADC config target guard is ambiguous')
        (output/'board.repl').write_text(board.replace(marker,marker+'\n    adcDisabledConfigStorage: true'))
    if args.adc_trigger_config_storage:
        marker='    baseAddress: '+('0x40001000' if args.reset_controller else '0x40000000')
        board=(output/'board.repl').read_text()
        if board.count(marker)!=1:raise ValueError('ADC trigger target guard is ambiguous')
        (output/'board.repl').write_text(board.replace(marker,marker+'\n    adcTriggerConfigStorage: true'))
    if args.adc_power_response is not None:
        marker='    baseAddress: '+('0x40001000' if args.reset_controller else '0x40000000')
        board=(output/'board.repl').read_text()
        if board.count(marker)!=1:raise ValueError('ADC power response target guard is ambiguous')
        (output/'board.repl').write_text(board.replace(marker,marker+'\n    adcPowerResponse: '+str(1 if args.adc_power_response=='active' else 0)))
    if args.adc_calibration_control:
        marker='    baseAddress: '+('0x40001000' if args.reset_controller else '0x40000000')
        board=(output/'board.repl').read_text()
        if board.count(marker)!=1:raise ValueError('ADC calibration control target guard is ambiguous')
        (output/'board.repl').write_text(board.replace(marker,marker+'\n    adcCalibrationControl: true'))
    if args.gpio_output_latch:
        marker='    baseAddress: '+('0x40001000' if args.reset_controller else '0x40000000')
        board=(output/'board.repl').read_text()
        if board.count(marker)!=1:raise ValueError('GPIO output target guard is ambiguous')
        (output/'board.repl').write_text(board.replace(marker,marker+'\n    gpioOutputLatch: true'))
    if args.gpio_interrupt_idle:
        marker='    baseAddress: '+('0x40001000' if args.reset_controller else '0x40000000')
        board=(output/'board.repl').read_text()
        if board.count(marker)!=1:raise ValueError('GPIO idle target guard is ambiguous')
        (output/'board.repl').write_text(board.replace(marker,marker+'\n    gpioInterruptIdle: true'))
    if args.gpio_config_storage:
        marker='    baseAddress: '+('0x40001000' if args.reset_controller else '0x40000000')
        board=(output/'board.repl').read_text()
        if board.count(marker)!=1:raise ValueError('GPIO config target guard is ambiguous')
        (output/'board.repl').write_text(board.replace(marker,marker+'\n    gpioConfigStorage: true'))
    if args.gpu_off_sequence_storage:
        marker='    baseAddress: '+('0x40001000' if args.reset_controller else '0x40000000')
        board=(output/'board.repl').read_text()
        if board.count(marker)!=1:raise ValueError('GPU off sequence target guard is ambiguous')
        (output/'board.repl').write_text(board.replace(marker,marker+'\n    gpuOffSequenceStorage: true'))
    if args.gpu_power_preparation:
        marker='    baseAddress: '+('0x40001000' if args.reset_controller else '0x40000000')
        board=(output/'board.repl').read_text()
        if board.count(marker)!=1:raise ValueError('GPU preparation target guard is ambiguous')
        (output/'board.repl').write_text(board.replace(marker,marker+'\n    gpuPowerPreparation: true'))
    if args.hfrc_force_control:
        marker='    baseAddress: '+('0x40001000' if args.reset_controller else '0x40000000')
        board=(output/'board.repl').read_text()
        if board.count(marker)!=1:raise ValueError('HFRC force target guard is ambiguous')
        (output/'board.repl').write_text(board.replace(marker,marker+'\n    hfrcForceControl: true'))
    if args.gfx_power_storage:
        marker='    baseAddress: '+('0x40001000' if args.reset_controller else '0x40000000')
        board=(output/'board.repl').read_text()
        if board.count(marker)!=1:raise ValueError('GFX power target guard is ambiguous')
        (output/'board.repl').write_text(board.replace(marker,marker+'\n    gfxPowerStorage: true'))
    if args.iom2_model is not None:
        (output/'board.repl').write_text(connect_ioms((output/'board.repl').read_text(),args.iom2_model,args.iom2_off_response,iom_modules,args.iom4_model,args.iom_cq_input_levels,iom_overrides))
    if args.chip_info_profile is not None:
        marker='    baseAddress: '+('0x40001000' if args.reset_controller else '0x40000000')
        board=(output/'board.repl').read_text()
        if board.count(marker)!=1:raise ValueError('Chip info target guard is ambiguous')
        (output/'board.repl').write_text(board.replace(marker,marker+'\n    chipInfo: true'))
    if args.jedec_mock_part is not None:
        low='    baseAddress: '+('0x40001000' if args.reset_controller else '0x40000000');ppb='    baseAddress: 0xe0010000'
        board=(output/'board.repl').read_text()
        if board.count(low)!=1 or board.count(ppb)!=1:raise ValueError('JEDEC identity owners ambiguous')
        board=board.replace(low,low+'\n    jedecMockPart: '+str(args.jedec_mock_part)+'\n    jedecMockCid: '+str(args.jedec_mock_cid))
        board=board.replace(ppb,ppb+'\n    chipInfoOwner: guard')
        (output/'board.repl').write_text(board)
    if args.rtc_model is not None:
        marker='    baseAddress: '+('0x40001000' if args.reset_controller else '0x40000000')
        board=(output/'board.repl').read_text()
        if board.count(marker)!=1:raise ValueError('RTC adapter target guard is ambiguous')
        board=board.replace(marker,marker+'\n    rtc: rtc_model')
        board+='\nrtc_model: Miscellaneous.BlackwallRtcAdapter @ none\n    halLowUpperWrites: '+str(args.rtc_counter_writes is not None).lower()+'\n    -> nvic@2\n'
        (output/'board.repl').write_text(board)
    (output/'probe.resc').write_text("""include @/work/strict.cs
mach create "blackwall-main-probe"
machine LoadPlatformDescription @/work/board.repl
sysbus LoadBinary @/work/itcm-fill.bin 0
sysbus LoadBinary @/work/sram-fill.bin 0x20000000
sysbus LoadBinary @/work/main.bin 0x438000
cpu VectorTableOffset 0x438000
include @/work/run.py
quit
""")
    # Generated scripts must be syntactically valid before starting a native process.
    for generated in ('run.py','result.py'):
        compile((output/generated).read_text(),generated,'exec')
    command = ['docker', 'run', '--rm', '--network', 'none', '--memory', '512m', '--pids-limit', '128',
               '--cpus', '1', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
               '--mount', f'type=bind,source={output},target=/work,readonly', image['Id'],
               '--disable-gui', '--console', '-p', '-e', 'quit', '/work/probe.resc']
    log = execute(command, output, 'renode', timeout=45)
    records = [line.partition('BLACKWALL_REPORT ')[2] for line in log.splitlines()
               if line.startswith('BLACKWALL_REPORT ')]
    if len(records) != 1:
        raise ValueError('Missing or ambiguous runtime result; inspect preserved log')
    observed = json.loads(records[0])
    execution_observation=None
    if observation_points:
        observations=[json.loads(line.split('BLACKWALL_OBSERVATION ',1)[1]) for line in log.splitlines() if line.startswith('BLACKWALL_OBSERVATION ')]
        if len(observations)!=1:raise ValueError('Missing or ambiguous execution observation')
        execution_observation=observations[0]
    if args.buck_response_model is not None and (not observed.get('buck_response')
            or observed['buck_response']['profile']!=args.buck_response_model):
        raise ValueError('Requested buck response was not bound to the main guard; inspect preserved log')
    if args.mcu_clock_response is not None and (not observed.get('mcu_clock_response') or observed['mcu_clock_response']['profile']!=args.mcu_clock_response):
        raise ValueError('MCU clock response binding failed; inspect preserved log')
    if args.gfx_power_storage and not observed.get('gfx_power_storage'):
        raise ValueError('GFX power storage binding failed; inspect preserved log')
    if args.hfrc_force_control and not observed.get('mcu_clock_response',{}).get('hfrc_force_control'):
        raise ValueError('HFRC force control binding failed; inspect preserved log')
    if args.gpu_power_preparation and not observed.get('gpu_power_preparation'):
        raise ValueError('GPU preparation binding failed; inspect preserved log')
    if args.gpu_power_response is not None and (not observed.get('gpu_power_response') or observed['gpu_power_response']['profile']!=args.gpu_power_response):
        raise ValueError('GPU power response binding failed; inspect preserved log')
    if args.gpu_interrupt_clear and not observed.get('gpu_interrupt_clear'):
        raise ValueError('GPU IRQ clear binding failed')
    if args.gpu_id_initialization and not observed.get('gpu_id_initialization'):
        raise ValueError('GPU ID initialization binding failed')
    if args.gpu_ring_configuration and not observed.get('gpu_ring_configuration'):
        raise ValueError('GPU ring configuration binding failed')
    if args.gpu_identity_response is not None and (not observed.get('gpu_identity_response') or observed['gpu_identity_response']['profile']!=args.gpu_identity_response):
        raise ValueError('GPU identity response binding failed')
    if args.gpu_initial_resets and not observed.get('gpu_initial_resets'):
        raise ValueError('GPU initial reset binding failed')
    if args.gpu_raster_init_storage and not observed.get('gpu_raster_init_storage'):
        raise ValueError('GPU raster initial storage binding failed')
    if args.gpu_config_low_response and not observed.get('gpu_config_response'):
        raise ValueError('GPU CONFIG observation binding failed')
    count = sum(g['accesses'] for g in observed['guards'])
    memory_violations = observed['memory_policy']['violations']
    control_violations = observed['system_control']['violations']
    if count+memory_violations+control_violations > 1:
        raise ValueError('MMIO guard failed to stop at first access')
    unexpected = []
    for line in log.splitlines():
        lower = line.lower()
        if (('[warning]' in lower and 'translation cache size' not in lower)
                or ('[error]' in lower and not (count+memory_violations+control_violations == 1 and 'this machine has aborted' in lower))
                or any(word in lower for word in ('unhandled', 'non existing', 'non-existing', 'could not execute'))):
            unexpected.append(line)
    report = {'profile': profile, 'bundle_sha256': digest,
              'raw_main_sha256': hashlib.sha256(raw).hexdigest(), 'cpu_model': 'Renode cortex-m55',
              'image_id': image['Id'], 'initial_sp': hex(stack), 'reset_vector': hex(vector),
              'host_execution_window_seconds': args.wall_run_seconds, 'observed': observed,
              'rtc_engine_provenance': (dict(upstream_sha256=RTC_UPSTREAM_SHA,generated_sha256=hashlib.sha256(rtc_engine.encode()).hexdigest(),source_patch='rename/import scope plus disable machine wall-clock mode subscription',license='MIT') if rtc_engine is not None else None),
              'execution_observation': execution_observation,
              'selected_hypotheses': {'power_mode': args.power_mode, 'reset_latch': args.reset_latch,
                                      'nominal_lfrc_watchdog': args.watchdog_model,
                                      'synthetic_reset_controller': args.reset_controller,
                                      'startup_controls': args.startup_controls,
                                      'shadow_info1': args.shadow_info1,
                                      'invalid_info1_metadata': args.info1_metadata_fixture,
                                      'chip_revision': args.chip_revision_fixture,
                                      'spot_control_storage': args.spot_control_storage,
                                      'memory_startup_fixture': args.memory_startup_fixture,
                                      'hal_startup_storage': args.hal_startup_storage,
                                      'mram_control_storage': args.mram_control_storage,
                                      'buck_override_storage': args.buck_override_storage,
                                      'buck_start_storage': args.buck_start_storage,
                                      'coreldo_reduction_storage': args.coreldo_reduction_storage,
                                      'memldo_setup_storage': args.memldo_setup_storage,
                                      'buck_status_fixture': args.buck_status_fixture,
                                      'buck_response_model': args.buck_response_model,
                                      'mcu_clock_response': args.mcu_clock_response,
                                      'rtc_osel_storage': args.rtc_osel_storage,
                                      'rtc_model': args.rtc_model,
                                      'chip_info_profile': args.chip_info_profile,
                                      'jedec_mock_part': args.jedec_mock_part,
                                      'jedec_mock_cid': args.jedec_mock_cid,
                                      'observe_pc': args.observe_pc,
                                      'observe_sram': args.observe_sram,
                                      'rtc_counter_writes': args.rtc_counter_writes,
                                      'gfx_power_storage': args.gfx_power_storage,
                                      'hfrc_force_control': args.hfrc_force_control,
                                      'gpu_power_preparation': args.gpu_power_preparation,
                                      'gpu_power_response': args.gpu_power_response,
                                      'gpu_power_off_response': args.gpu_power_off_response,
                                      'gpu_off_sequence_storage': args.gpu_off_sequence_storage,
                                      'gpio_config_storage': args.gpio_config_storage,
                                      'gpio_interrupt_idle': args.gpio_interrupt_idle,
                                      'gpio_output_latch': args.gpio_output_latch,
                                      'capture_itcm_prefix': args.capture_itcm_prefix,
                                      'adc_info_zero_fixture': args.adc_info_zero_fixture,
                                      'adc_calibration_control': args.adc_calibration_control,
                                      'adc_power_response': args.adc_power_response,
                                      'adc_power_off_response': args.adc_power_off_response,
                                      'iom2_model': args.iom2_model,
                                      'iom_modules': iom_modules,
                                      'iom_cq_input_levels': args.iom_cq_input_levels,
                                      'iom4_model': args.iom4_model,
                                      'iom_power_profiles': iom_overrides,
                                      'iom2_off_response': args.iom2_off_response,
                                      'uart1_model': args.uart1_model,
                                      'uart_modules': uart_modules,
                                      'uart1_interrupts': args.uart1_interrupts,
                                      'uart1_off_response': args.uart1_off_response,
                                      'adc_trigger_config_storage': args.adc_trigger_config_storage,
                                      'adc_disabled_config_storage': args.adc_disabled_config_storage,
                                      'adc_enable_latch': args.adc_enable_latch,
                                      'adc_trigger_source_hz': args.adc_trigger_source_hz,
                                      'adc_constant_channel3': args.adc_constant_channel3,
                                      'capture_sram_windows': capture_windows,
                                      'gpu_interrupt_clear': args.gpu_interrupt_clear,
                                      'gpu_id_initialization': args.gpu_id_initialization,
                                      'gpu_ring_configuration': args.gpu_ring_configuration,
                                      'gpu_identity_response': args.gpu_identity_response,
                                      'gpu_initial_resets': args.gpu_initial_resets,
                                      'gpu_raster_init_storage': args.gpu_raster_init_storage,
                                      'gpu_config_low_response': args.gpu_config_low_response,
                                      'gpu_config_high_hypothesis': args.gpu_config_high_hypothesis,
                                      'gpu_initial_status_hypothesis': args.gpu_initial_status_hypothesis,
                                      'vddf_tempco_storage': args.vddf_tempco_storage,
                                      'coherent_icache_model': args.coherent_icache_model,
                                      'coherent_dcache_model': args.coherent_dcache_model,
                                      'prefetch_control_storage': args.prefetch_control_storage},
              'reason': ('unsupported-system-control' if control_violations else
                         'memory-policy-violation' if memory_violations else
                         'watchdog-reset-request' if (observed.get('watchdog') or {}).get('reset_due') else
                         'unsupported-mmio-and-adc-trigger-consumption-required' if count and (observed.get('adc_internal_trigger') or {}).get('phase') in ('trigger-consumption-required','scan-required') else
                         'unsupported-mmio' if count else
                         'adc-trigger-consumption-required' if (observed.get('adc_internal_trigger') or {}).get('phase') in ('trigger-consumption-required','scan-required') else 'host-window-ended'),
              'unmodeled_engine_messages': unexpected,
              'assumptions': ['isolated main reset, no bootloader initial state',
                              'A5-filled 512 KiB SRAM, 3 MiB System SRAM and 256 KiB ITCM',
                              'main writes denied by synthetic external permission windows before internal MPU',
                              'main padding reads and execution rejected; only guest-written ITCM instructions execute',
                              'ITCM block checks can conservatively reject code written later within the same block',
                              'Renode core/NVIC behavior is not fully verified for Apollo510B',
                              'virtual MIPS and SysTick frequency are synthetic, not hardware timing'],
              'iom_engine_provenance': (dict(upstream_sha256=UPSTREAM_SHA,generated_sha256=hashlib.sha256(load_engine().encode()).hexdigest(),kind='source-derived-fifo-corrected') if args.iom2_model is not None else None),
              'boot_verified': False, 'hardware_validated': False, 'installable': False}
    (output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    for path in output.iterdir():
        path.chmod(0o700 if path.is_dir() else 0o600)
    print(json.dumps({'profile': profile, 'reason': report['reason'], 'observed': observed,
                      'unmodeled_engine_messages': unexpected}))
    if unexpected:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
