"""Ordered post-enable memory-LDO field storage; no analog power response."""


class MemLdoSetup:
    def __init__(self, report, fixture):
        self.report = report
        self.fixture = fixture
        self.state = {'steps_completed': 0, 'hardware_verified': False,
                      'effects': 'ordered field storage only; analog power and readiness unprovided'}
        report['memldo_setup_storage'] = self.state
        report['trim_reset_fixture']['write_exception'] = 'selected core-LDO reduction and ordered memory-LDO setup only'
        report['models'].append('ordered-post-enable-memldo-field-storage')

    def write(self, address, size, value):
        steps = ((0x40020088, 0x3f, 1), (0x400201b0, 0x18000, 0x10000))
        stage = self.state['steps_completed']
        if (size != 4 or stage >= len(steps)
                or self.report.get('buck_start_storage', {}).get('steps_completed') != 3
                or not self.report.get('coreldo_reduction_storage', {}).get('applied')):
            return False
        expected_address, mask, field = steps[stage]
        if address != expected_address:
            return False
        row = self.fixture.registers[address]
        if value != ((int(row['value'], 16) & ~mask) | field):
            return False
        row['value'] = hex(value)
        row['writes'] += 1
        self.state['steps_completed'] += 1
        return True
