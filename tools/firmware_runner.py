"""Offline, bounded main-reset execution. No peripheral model or device access."""
import argparse
from collections import deque
import hashlib
import json
from pathlib import Path
import struct

import unicorn as u
from unicorn import arm_const as arm
from audit_assets import PINS
from blackwall_package import parse_bundle
from simulator_info_fixture import InvalidInfo1Fixture
from simulator_buck_start import BuckStartStorage
from simulator_coreldo import CoreLdoReduction
from simulator_memldo import MemLdoSetup
from simulator_vddf_tempco import VddfTempcoStorage
from simulator_clocks import ClockGateStorage
from simulator_mcu_clock import McuClockResponse
from simulator_trim_fixture import TrimResetFixture
from simulator_scenarios import load_scenario
from simulator_watchdog import StepWatchdog
from simulator_delay import summarize_delay
from simulator_registers import CpacrStorage, PowerModeRead, ResetLatchScenario, DisabledWatchdog, ResetConfigStorage, DebugPortOff, CoreDomainsOn

BASE = 0x438000
RAM = 0x20000000
RAM_BYTES = 0x80000
ACCESS = {
    u.UC_MEM_READ_UNMAPPED: 'read-unmapped', u.UC_MEM_WRITE_UNMAPPED: 'write-unmapped',
    u.UC_MEM_FETCH_UNMAPPED: 'fetch-unmapped', u.UC_MEM_READ_PROT: 'read-protected',
    u.UC_MEM_WRITE_PROT: 'write-protected', u.UC_MEM_FETCH_PROT: 'fetch-protected',
}


def run_main(raw, instructions=10000, *, cpacr_storage=False, vtor_storage=False, system_sram=False, timeout_us=2000000, itcm=False, power_mode=None, fast_delay=False, reset_latch=None, watchdog_disabled=False, reset_config=False, watchdog_step_clock=False, fp_context_storage=False, trace_control_storage=False, devices_off=False, debug_port_off=False, cpu_caches_off=False, core_domains_on=False, wic_config=False, shadow_info1=None, trim_revision_fixture=None, info1_metadata_fixture=None, chip_revision_fixture=None, spot_control_storage=False, memory_domains_on=False, rom_powerdown_model=False, memory_retention_storage=False, shared_sram_on=False, shared_sram_retention_storage=False, shared_sram_override_storage=False, clock_gate_storage=False, adc_power_delay_storage=False, trim_reset_fixture=False, power_switch_storage=False, ton_configuration_storage=False, hal_state_storage=False, mram_auto_wakeup_storage=False, buck_override_storage=False, buck_start_storage=False, coreldo_reduction_storage=False, memldo_setup_storage=False, buck_status_fixture=None, coherent_icache_model=False, prefetch_control_storage=False, coherent_dcache_model=False, buck_response_model=None, vddf_tempco_storage=False, mcu_clock_response=None):
    if mcu_clock_response not in (None,'nominal','hfrc2-unready','no-ack','denied'):
        raise ValueError('Unknown MCU clock response')
    if mcu_clock_response is not None and (not clock_gate_storage or buck_response_model!='active' or not vddf_tempco_storage or power_mode is None):
        raise ValueError('MCU clock response requires clock storage, active buck response and VDDF startup storage')
    if buck_response_model not in (None,'active','stuck-off'):
        raise ValueError('Unknown buck response model')
    if buck_response_model is not None and (not memldo_setup_storage or buck_status_fixture is not None):
        raise ValueError('Buck response requires memory LDO setup and excludes single samples')
    if vddf_tempco_storage and buck_response_model is None:
        raise ValueError('VDDF tempco storage requires explicit buck response')
    if coherent_dcache_model and not coherent_icache_model:
        raise ValueError('Coherent data cache requires coherent instruction cache')
    if prefetch_control_storage and not core_domains_on:
        raise ValueError('Prefetch storage requires core domain adapter')
    if coherent_icache_model and (not cpacr_storage or not cpu_caches_off):
        raise ValueError('Coherent instruction cache requires CPACR and cache-off baseline')
    if trim_revision_fixture is not None and info1_metadata_fixture is not None:
        raise ValueError('Choose one Info1 fixture scope')
    if spot_control_storage and not debug_port_off:
        raise ValueError('SPOT control storage requires MCUCTRL model')
    if buck_status_fixture not in (None,'off','lp','active'):
        raise ValueError('Unknown buck status fixture')
    if buck_status_fixture is not None and not memldo_setup_storage:
        raise ValueError('Buck status fixture requires memory LDO setup')
    if memldo_setup_storage and not coreldo_reduction_storage:
        raise ValueError('Memory LDO setup requires core LDO reduction storage')
    if coreldo_reduction_storage and (not buck_start_storage or not trim_reset_fixture):
        raise ValueError('Core LDO reduction requires buck start and public trim fixtures')
    if buck_start_storage and (not buck_override_storage or power_mode is None):
        raise ValueError('Buck start requests require explicit override storage and power mode')
    if buck_override_storage and (not debug_port_off or not spot_control_storage):
        raise ValueError('Buck override storage requires explicit MCUCTRL and SPOT storage')
    if mram_auto_wakeup_storage and power_mode is None:
        raise ValueError('MRAM control storage requires an explicit power mode fixture')
    if hal_state_storage and reset_latch is None:
        raise ValueError('HAL state storage requires STIMER page adapter with explicit reset latch fixture')
    if ton_configuration_storage and power_mode is None:
        raise ValueError('TON configuration storage requires power mode model')
    if power_switch_storage and not debug_port_off:
        raise ValueError('Power switch storage requires MCUCTRL model')
    if trim_reset_fixture and (not debug_port_off or power_mode is None):
        raise ValueError('Trim reset fixture requires MCUCTRL and power models')
    if adc_power_delay_storage and not debug_port_off:
        raise ValueError('ADC delay storage requires MCUCTRL model')
    if chip_revision_fixture is not None and not debug_port_off:
        raise ValueError('Chip revision fixture requires MCUCTRL model')
    if shadow_info1 is not None and not debug_port_off:
        raise ValueError("Shadow source scenario requires MCUCTRL debug-port scenario")
    if wic_config and not debug_port_off:
        raise ValueError("WIC config requires MCUCTRL debug-port scenario")
    if (shared_sram_on or shared_sram_retention_storage or shared_sram_override_storage) and (power_mode is None or not system_sram):
        raise ValueError('Shared SRAM register fixtures require power and System SRAM models')
    if memory_retention_storage and power_mode is None:
        raise ValueError('Memory retention storage requires power mode model')
    if rom_powerdown_model and not memory_domains_on:
        raise ValueError('ROM powerdown model requires memory power fixture')
    if memory_domains_on and power_mode is None:
        raise ValueError('Memory power fixture requires a power mode')
    if devices_off and power_mode is None:
        raise ValueError("Device power scenario requires a power mode")
    if (fp_context_storage or trace_control_storage or cpu_caches_off) and not cpacr_storage:
        raise ValueError("FPCCR storage requires CPACR storage")
    if watchdog_disabled and watchdog_step_clock:
        raise ValueError("Choose one watchdog model")
    if fast_delay and not itcm:
        raise ValueError("Delay summarization requires guest-written ITCM")
    if vtor_storage and not cpacr_storage:
        raise ValueError('VTOR storage requires the explicit CPACR storage model')
    if not 1 <= instructions <= 10000000 or not 1 <= timeout_us <= 30000000 or len(raw) < 10:
        raise ValueError('Invalid instruction budget or truncated main')
    stack, reset = struct.unpack_from('<II', raw)
    if stack % 8 or not RAM < stack <= RAM + RAM_BYTES:
        raise ValueError('Stack outside the provisional SRAM model')
    if not reset & 1 or not BASE + 8 <= reset & ~1 < BASE + len(raw):
        raise ValueError('Invalid reset vector')
    cpu = u.Uc(u.UC_ARCH_ARM, u.UC_MODE_THUMB | u.UC_MODE_MCLASS)
    cpu.ctl_set_cpu_model(arm.UC_CPU_ARM_CORTEX_M4)
    cpu.mem_map(BASE, (len(raw) + 4095) & ~4095)
    cpu.mem_write(BASE, raw)
    cpu.mem_protect(BASE, (len(raw) + 4095) & ~4095, u.UC_PROT_READ | u.UC_PROT_EXEC)
    cpu.mem_map(RAM, RAM_BYTES)
    cpu.mem_write(RAM, b'\xa5' * RAM_BYTES)
    if system_sram:
        cpu.mem_map(0x20080000, 0x300000)
        cpu.mem_write(0x20080000, b'\xa5' * 0x300000)
    cpu.reg_write(arm.UC_ARM_REG_SP, stack)
    cpu.reg_write(arm.UC_ARM_REG_LR, 0xffffffff)
    written = bytearray(0x40000)
    pending_writes = []
    if itcm:
        cpu.mem_map(0, 0x40000)
        cpu.mem_write(0, b"\xa5" * 0x40000)
    recent = deque(maxlen=32)
    report = {'mode': 'isolated-main-reset', 'unicorn_version': u.__version__,
              'cpu_model': 'Cortex-M4 approximation, not Apollo510B hardware model',
              'raw_main_sha256': hashlib.sha256(raw).hexdigest(),
              'initial_sp': hex(stack), 'reset_vector': hex(reset),
              'ram_base': hex(RAM), 'ram_bytes': RAM_BYTES, 'ram_initial_fill': '0xa5',
              'instruction_budget': instructions, 'wall_timeout_us': timeout_us,
              'instruction_boundaries': 0, 'reason': None, 'access': None,
              'boot_verified': False, 'hardware_validated': False, 'installable': False,
              'models': [], 'stubbed_functions': [],
              'assumptions': ['Provisional 512 KiB SRAM range; remaining regions unmodeled',
                              'No bootloader initialization or peripheral state supplied',
                              'CPU model does not establish full target ISA support']}
    if cpacr_storage:
        CpacrStorage(cpu, report, vtor_storage=vtor_storage, fp_context_storage=fp_context_storage, trace_control_storage=trace_control_storage, cpu_caches_off=cpu_caches_off, coherent_icache_model=coherent_icache_model, coherent_dcache_model=coherent_dcache_model)
        report['assumptions'].append('CPACR storage only: FPU permissions and exception behavior unmodeled')
    if system_sram:
        report['models'].append('system-sram-storage')
        report['system_sram'] = {'base': '0x20080000', 'end_exclusive': '0x20380000',
                                 'initial_fill': '0xa5', 'power_and_security': 'not-modeled'}

    if itcm:
        report["models"].append("itcm-written-code")
        report["itcm"] = {"bytes": 0x40000, "initial_fill": "0xa5", "alias_security_power": "not-modeled"}

    trim_fixture = TrimResetFixture(report) if trim_reset_fixture else None

    clock_response=McuClockResponse(report,power_mode,mcu_clock_response,{'value':0}) if mcu_clock_response is not None else None
    if clock_gate_storage:
        ClockGateStorage(cpu, report, clock_response)

    buck_start_fixture=BuckStartStorage(report,status_fixture=buck_status_fixture,response_model=buck_response_model) if buck_start_storage else None
    coreldo_reduction=CoreLdoReduction(report,trim_fixture) if coreldo_reduction_storage else None
    memldo_setup=MemLdoSetup(report,trim_fixture) if memldo_setup_storage else None
    vddf_tempco=VddfTempcoStorage(report,trim_fixture) if vddf_tempco_storage else None
    if power_mode is not None:
        PowerModeRead(cpu, report, power_mode, devices_off=devices_off, memory_domains_on=memory_domains_on, rom_powerdown_model=rom_powerdown_model, memory_retention_storage=memory_retention_storage, shared_sram_on=shared_sram_on, shared_sram_retention_storage=shared_sram_retention_storage, shared_sram_override_storage=shared_sram_override_storage, trim_fixture=trim_fixture, ton_configuration_storage=ton_configuration_storage, mram_auto_wakeup_storage=mram_auto_wakeup_storage, buck_start_fixture=buck_start_fixture, mcu_clock_response=clock_response)

    if fast_delay:
        report["models"].append("exact-delay-loop-summary")
        report["delay_summaries"] = []

    if reset_latch is not None:
        ResetLatchScenario(cpu, report, reset_latch, hal_state_storage=hal_state_storage)

    if watchdog_disabled:
        DisabledWatchdog(cpu, report)

    if reset_config:
        ResetConfigStorage(cpu, report)

    step_watchdog = StepWatchdog(cpu, report) if watchdog_step_clock else None

    if debug_port_off:
        DebugPortOff(cpu, report, wic_config=wic_config, shadow_info1=shadow_info1, chip_revision_fixture=chip_revision_fixture, spot_control_storage=spot_control_storage, adc_power_delay_storage=adc_power_delay_storage, trim_fixture=trim_fixture, power_switch_storage=power_switch_storage, buck_override_storage=buck_override_storage, buck_start_fixture=buck_start_fixture, coreldo_reduction=coreldo_reduction, memldo_setup=memldo_setup,vddf_tempco=vddf_tempco)

    if core_domains_on:
        CoreDomainsOn(cpu, report, prefetch_control_storage=prefetch_control_storage)

    if trim_revision_fixture is not None:
        InvalidInfo1Fixture(cpu, report, trim_revision_fixture)
    if info1_metadata_fixture is not None:
        InvalidInfo1Fixture(cpu, report, info1_metadata_fixture, metadata=True)

    def track_write(uc, access, address, size, value, _):
        end = min(address + size, len(written))
        pending_writes.append((address, bytes(uc.mem_read(address, end-address))))

    def confirm_writes(uc):
        for address, before in pending_writes:
            after = bytes(uc.mem_read(address, len(before)))
            for index, (old, new) in enumerate(zip(before, after)):
                if old != new:
                    written[address+index] = 1
        pending_writes.clear()

    def instruction(uc, address, size, _):
        if pending_writes:
            confirm_writes(uc)
        if step_watchdog:
            step_watchdog.advance(1)
            if report["reason"]:
                return
        recent.append(hex(address))
        opcode = raw[address-BASE:address-BASE+size] if BASE <= address < BASE+len(raw) else bytes(uc.mem_read(address, size))
        if opcode in (b"\x20\xbf", b"\x30\xbf", bytes.fromhex("aff30280"), bytes.fromhex("aff30380")):
            report["reason"] = "unsupported-sleep-boundary"
            report["sleep_opcode"] = opcode.hex()
            uc.emu_stop()
            return
        report['instruction_boundaries'] += 1
        if itcm and 0 <= address < 0x40000:
            if size <= 0 or address+size > 0x40000 or not all(written[address:address+size]):
                report["reason"] = "uninitialized-itcm-execution"
                uc.emu_stop()
            elif fast_delay and address == 0x40 and not (step_watchdog and step_watchdog.cfg & 1):
                summary = summarize_delay(uc)
                if summary is not None:
                    report["delay_summaries"].append(summary)
                    if step_watchdog:
                        step_watchdog.advance(summary["guest_instructions_summarized"] - 1)
            return
        if not BASE <= address < BASE + len(raw):
            report['reason'] = 'unsupported-execution'
            uc.emu_stop()

    def invalid(uc, access, address, size, value, _):
        report['reason'] = 'unsupported-memory-access'
        report['access'] = {'kind': ACCESS[access], 'address': hex(address),
                            'bytes': size, 'pc': hex(uc.reg_read(arm.UC_ARM_REG_PC))}
        return False

    if itcm:
        cpu.hook_add(u.UC_HOOK_MEM_WRITE, track_write, begin=0, end=0x3ffff)
    cpu.hook_add(u.UC_HOOK_CODE, instruction)
    cpu.hook_add(u.UC_HOOK_MEM_INVALID, invalid)
    try:
        cpu.emu_start(reset, 0, count=instructions, timeout=timeout_us)
    except u.UcError as error:
        report['emulator_error'] = str(error)
        if report['reason'] is None:
            report['reason'] = 'unsupported-execution'
    if report['reason'] is None:
        report['reason'] = ('time-limit' if cpu.query(u.UC_QUERY_TIMEOUT)
                            else 'instruction-limit' if report['instruction_boundaries'] == instructions
                            else 'unexpected-stop')
    if itcm:
        confirm_writes(cpu)
        report["itcm"]["proof"] = "Observed byte change after guest write; unchanged bytes remain unproven"
        report["itcm"]["written_bytes"] = sum(written)
        report["itcm"]["diagnostic_0x40"] = bytes(cpu.mem_read(0x40, 24)).hex()
        report["itcm"]["sha256"] = hashlib.sha256(cpu.mem_read(0, 0x40000)).hexdigest()
    report['final_pc'] = hex(cpu.reg_read(arm.UC_ARM_REG_PC))
    report['registers'] = {f'r{i}': hex(cpu.reg_read(getattr(arm, f'UC_ARM_REG_R{i}'))) for i in range(13)}
    report['ram_sha256'] = hashlib.sha256(cpu.mem_read(RAM, RAM_BYTES)).hexdigest()
    if system_sram:
        report['system_sram']['sha256'] = hashlib.sha256(cpu.mem_read(0x20080000, 0x300000)).hexdigest()
    report['final_sp'] = hex(cpu.reg_read(arm.UC_ARM_REG_SP))
    report['recent_instruction_addresses'] = list(recent)
    return report


def inspect_bundle(path, instructions, *, cpacr_storage=False, vtor_storage=False, system_sram=False, timeout_us=2000000, itcm=False, power_mode=None, fast_delay=False, reset_latch=None, watchdog_disabled=False, reset_config=False, watchdog_step_clock=False, fp_context_storage=False, trace_control_storage=False, devices_off=False, debug_port_off=False, cpu_caches_off=False, core_domains_on=False, wic_config=False, shadow_info1=None, trim_revision_fixture=None, info1_metadata_fixture=None, chip_revision_fixture=None, spot_control_storage=False, memory_domains_on=False, rom_powerdown_model=False, memory_retention_storage=False, shared_sram_on=False, shared_sram_retention_storage=False, shared_sram_override_storage=False, clock_gate_storage=False, adc_power_delay_storage=False, trim_reset_fixture=False, power_switch_storage=False, ton_configuration_storage=False, hal_state_storage=False, mram_auto_wakeup_storage=False, buck_override_storage=False, buck_start_storage=False, coreldo_reduction_storage=False, memldo_setup_storage=False, buck_status_fixture=None, coherent_icache_model=False, prefetch_control_storage=False, coherent_dcache_model=False, buck_response_model=None, vddf_tempco_storage=False, mcu_clock_response=None):
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    matches = [key for key in ('stock_base', 'stock_current', 'cfw') if PINS[key] == digest]
    if len(matches) != 1:
        raise ValueError('Input is not a pinned stock/Faceclaw bundle')
    parts = parse_bundle(data)
    raw = next(part for part in parts if part.type_id == 0).payload[32:]
    report = run_main(raw, instructions, cpacr_storage=cpacr_storage, vtor_storage=vtor_storage, system_sram=system_sram, timeout_us=timeout_us, itcm=itcm, power_mode=power_mode, fast_delay=fast_delay, reset_latch=reset_latch, watchdog_disabled=watchdog_disabled, reset_config=reset_config, watchdog_step_clock=watchdog_step_clock, fp_context_storage=fp_context_storage, trace_control_storage=trace_control_storage, devices_off=devices_off, debug_port_off=debug_port_off, cpu_caches_off=cpu_caches_off, core_domains_on=core_domains_on, wic_config=wic_config, shadow_info1=shadow_info1, trim_revision_fixture=trim_revision_fixture, info1_metadata_fixture=info1_metadata_fixture, chip_revision_fixture=chip_revision_fixture, spot_control_storage=spot_control_storage, memory_domains_on=memory_domains_on, rom_powerdown_model=rom_powerdown_model, memory_retention_storage=memory_retention_storage, shared_sram_on=shared_sram_on, shared_sram_retention_storage=shared_sram_retention_storage, shared_sram_override_storage=shared_sram_override_storage, clock_gate_storage=clock_gate_storage, adc_power_delay_storage=adc_power_delay_storage, trim_reset_fixture=trim_reset_fixture, power_switch_storage=power_switch_storage, ton_configuration_storage=ton_configuration_storage, hal_state_storage=hal_state_storage, mram_auto_wakeup_storage=mram_auto_wakeup_storage, buck_override_storage=buck_override_storage, buck_start_storage=buck_start_storage, coreldo_reduction_storage=coreldo_reduction_storage, memldo_setup_storage=memldo_setup_storage, buck_status_fixture=buck_status_fixture, coherent_icache_model=coherent_icache_model, prefetch_control_storage=prefetch_control_storage, coherent_dcache_model=coherent_dcache_model, buck_response_model=buck_response_model, vddf_tempco_storage=vddf_tempco_storage, mcu_clock_response=mcu_clock_response)
    report.update({'profile': matches[0], 'bundle_sha256': digest})
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--scenario', help='Named repository-defined simulation assumptions')
    parser.add_argument('--timeout-us', type=int)
    parser.add_argument('--instructions', type=int)
    parser.add_argument('--cpacr-storage', action='store_true', help='Experimental register storage; not CPU permission enforcement')
    parser.add_argument('--vtor-storage', action='store_true', help='Store main vector base only; no interrupt dispatch')
    parser.add_argument('--prefetch-control-storage', action='store_true', help='PFCR defined-field storage after explicit write; no reset/prefetch timing model')
    parser.add_argument('--coherent-dcache-model', action='store_true', help='Documented Apollo510 geometry and coherent data memory; no timing/dirty-line model')
    parser.add_argument('--coherent-icache-model', action='store_true', help='Functional coherent instruction memory; no cache timing/eviction')
    parser.add_argument('--mcu-clock-response', choices=('nominal','hfrc2-unready','no-ack','denied'), help='Digital HFRC2 and MCU response profile; no physical timing/frequency')
    parser.add_argument('--buck-response-model', choices=('active','stuck-off'), help='Explicit post-enable digital response, zero latency after setup; not analog power')
    parser.add_argument('--vddf-tempco-storage', action='store_true', help='One observed initial VDDF field reduction; no voltage or calibration effects')
    parser.add_argument('--buck-status-fixture', choices=('off','lp','active'), help='One explicit post-enable status sample; no analog transition model')
    parser.add_argument('--memldo-setup-storage', action='store_true', help='Ordered post-enable memory LDO field storage; no analog/readiness model')
    parser.add_argument('--coreldo-reduction-storage', action='store_true', help='One saturated core-LDO field reduction at the observed phase; no voltage model')
    parser.add_argument('--buck-start-storage', action='store_true', help='Ordered trim latch/compensation/enable requests only; power-ready reads remain blocked')
    parser.add_argument('--buck-override-storage', action='store_true', help='Ordered observed VRCTRL setup only; no voltage/deep-sleep behavior')
    parser.add_argument('--mram-auto-wakeup-storage', action='store_true', help='Synthetic MRAMEXTCTRL 2-to-6 storage only; no wakeup behavior')
    parser.add_argument('--hal-state-storage', action='store_true', help='HALSTATES zero/signature storage only; no clock mux recovery')
    parser.add_argument('--ton-configuration-storage', action='store_true', help='Observed TON configuration storage only; no counters, comparators or voltage effects; LP override enable unsupported')
    parser.add_argument('--power-switch-storage', action='store_true', help='Observed PWRSW0/1 static-select values only; no rail switching or voltage response')
    parser.add_argument('--trim-reset-fixture', action='store_true', help='Read-only public reset words for the observed cache prefix; not device calibration')
    parser.add_argument('--adc-power-delay-storage', action='store_true', help='Observed AUDADCPWRDLY values only; no ADC timing or conversion')
    parser.add_argument('--clock-gate-storage', action='store_true', help='Observed CLKGEN MISC/CLKCTRL values only; no real clock model')
    parser.add_argument('--shared-sram-override-storage', action='store_true', help='Observed MMSOVERRIDE values only; no power-domain or retention effects')
    parser.add_argument('--shared-sram-on', action='store_true', help='Three synthetic 1 MiB SRAM banks already on; power transitions unsupported')
    parser.add_argument('--shared-sram-retention-storage', action='store_true', help='SSRAMRETCFG bit storage only; no actual sleep/retention')
    parser.add_argument('--memory-retention-storage', action='store_true', help='MEMRETCFG two-bit storage only; no sleep or retention simulation')
    parser.add_argument('--rom-powerdown-model', action='store_true', help='One synthetic ROM-disable transition with zero latency; requires memory domains fixture')
    parser.add_argument('--memory-domains-on', action='store_true', help='Hypothetical stable TCM/NVM/ROM power bits; transitions unsupported')
    parser.add_argument('--spot-control-storage', action='store_true', help='ACRG/VRCTRL observed control values only; no analog power model')
    parser.add_argument('--chip-revision-fixture', type=lambda v:int(v,0), choices=(0x21,0x22,0x23,0x24), help='Synthetic CHIPREV, not detected hardware identity')
    parser.add_argument('--info1-metadata-fixture', choices=['zero', 'erased'], help='Three invalid boot metadata words only; no device calibration')
    parser.add_argument('--trim-revision-fixture', choices=['zero', 'erased'], help='Invalid trim revision for error-path testing; not device calibration')
    parser.add_argument('--shadow-info1', choices=['mram', 'otp'], help='Hypothetical Info1 source bit only; no OTP or device data')
    parser.add_argument('--wic-config', action='store_true', help='WIC mode storage only; sleep/wakeup unsupported')
    parser.add_argument('--core-domains-on', action='store_true', help='Hypothetical CPDLPSTATE all-ON; retention and OFF transitions stop')
    parser.add_argument('--cpu-caches-off', action='store_true', help='Hypothetical CCR read with cache bits off; CCR writes unsupported')
    parser.add_argument('--debug-port-off', action='store_true', help='Hypothetical TPIU debug port off; other MCUCTRL registers stop')
    parser.add_argument('--devices-off', action='store_true', help='Hypothetical peripheral domains off; power-up requests stop')
    parser.add_argument('--trace-control-storage', action='store_true', help='DEMCR TRCENA storage only; no trace/counter emulation')
    parser.add_argument('--fp-context-storage', action='store_true', help='FPCCR control storage; exception context preservation unmodeled')
    parser.add_argument('--watchdog-step-clock', action='store_true', help='Instruction-clock LFRC/64 hypothesis; expiry stops execution')
    parser.add_argument('--reset-config', action='store_true', help='Hypothetical CFG storage only; reset operations stop')
    parser.add_argument('--watchdog-disabled', action='store_true', help='Hypothetical disabled watchdog; activation and timeout unsupported')
    parser.add_argument('--reset-latch', type=lambda value: int(value, 0), help='Explicit hypothetical 13-bit reset latch state')
    parser.add_argument('--fast-delay', action='store_true', help='Summarize the exact observed counter loop; no timing simulation')
    parser.add_argument('--power-mode', choices=['lp', 'hp'], help='Hypothetical stable power state; not measured device state')
    parser.add_argument('--itcm', action='store_true', help='Allow execution only of guest-written ITCM bytes')
    parser.add_argument('--system-sram', action='store_true', help='Map documented System SRAM; power/security unmodeled')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output already exists; preserve previous evidence')
    values = vars(args)
    manual = {name: value for name, value in values.items()
              if name not in ('image', 'output', 'scenario', 'instructions', 'timeout_us')}
    scenario = None
    if args.scenario:
        if any(value is not None and value is not False for value in manual.values()):
            parser.error('Named scenarios cannot be mixed with manual model switches')
        try:
            options, scenario = load_scenario(args.scenario)
        except ValueError as error:
            parser.error(str(error))
    else:
        options = manual
    instructions = args.instructions if args.instructions is not None else (scenario['instructions'] if scenario else 10000)
    timeout = args.timeout_us if args.timeout_us is not None else (scenario['timeout_us'] if scenario else 2000000)
    report = inspect_bundle(args.image, instructions, timeout_us=timeout, **options)
    if scenario:
        report['execution_scenario'] = {**scenario, 'resolved_options': options,
                                        'instructions': instructions, 'timeout_us': timeout}

    with args.output.open('x') as output:
        json.dump(report, output, indent=2)
        output.write('\n')
    print(json.dumps({key: report[key] for key in ('profile', 'reason', 'final_pc', 'access')}))


if __name__ == '__main__':
    main()
