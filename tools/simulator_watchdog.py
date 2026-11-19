"""Instruction-clock hypothesis for WDT. Expiry stops; no reset or IRQ delivery."""
import unicorn as u
from unicorn import arm_const as a


class StepWatchdog:
    def __init__(self, cpu, report, instructions_per_source_tick=100000):
        self.cpu, self.report = cpu, report
        self.cfg, self.steps = 0, 0
        self.scale = instructions_per_source_tick
        if not isinstance(self.scale, int) or self.scale < 1:
            raise ValueError('Clock scale must be a positive integer')
        self.state = {'cfg': '0x0', 'instruction_clock_scale': self.scale,
                      'clock_semantics': 'guest instructions per hypothetical LFRC tick',
                      'elapsed_device_seconds': 'not-modeled', 'restarts': 0, 'counter_ticks': 0,
                      'device_state_verified': False, 'event': None}
        report['step_watchdog'] = self.state
        report['models'].append('instruction-clock-watchdog-hypothesis')
        cpu.mmio_map(0x40024000, 0x1000, self.read, None, self.write, None)

    def stop(self, reason):
        self.report['reason'] = reason
        self.cpu.emu_stop()

    def advance(self, steps):
        if steps < 0:
            raise ValueError('Time cannot move backwards')
        if not self.cfg & 1 or self.state['event']:
            return
        self.steps += steps
        ticks = self.steps // (self.scale * 64)
        self.state['counter_ticks'] = ticks
        events = []
        if self.cfg & 2:
            events.append(((self.cfg >> 16) & 255, 'interrupt-due'))
        if self.cfg & 4:
            events.append(((self.cfg >> 8) & 255, 'reset-threshold-due'))
        events.append((256, 'counter-wrap-unmodeled'))
        threshold, event = min(events)
        if ticks >= threshold:
            self.state['event'] = event
            self.state['reset_cfg_at_event'] = self.report.get('reset_config', {}).get('final_cfg')
            self.stop('watchdog-' + event)

    def read(self, cpu, offset, size, _):
        if offset != 0 or size != 4:
            self.stop('unsupported-step-watchdog-read')
            return 0
        return self.cfg

    def write(self, cpu, offset, size, value, _):
        if offset == 4 and size == 4 and value == 0xb2:
            self.steps = 0
            self.state['counter_ticks'] = 0
            self.state['restarts'] += 1
            return
        # Current runtime uses LFRC/64. Other active clocks require their own model.
        if offset != 0 or size != 4 or value & ~0x07ffff07 or (value & 1 and value >> 24 != 2):
            self.stop('unsupported-step-watchdog-write')
            return
        if self.cfg & 1 and value & 1 and value != self.cfg:
            self.stop('active-watchdog-reconfiguration-unmodeled')
            return
        if not value & 1:
            self.steps = 0
        self.cfg = value
        self.state['cfg'] = hex(value)
