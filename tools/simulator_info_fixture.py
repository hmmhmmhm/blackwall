"""Sparse invalid Info1 fixtures. Never supplies a valid device calibration image."""
from unicorn import arm_const as a


class InvalidInfo1Fixture:
    def __init__(self, cpu, report, kind, *, metadata=False):
        if kind not in ('zero', 'erased'):
            raise ValueError('Only explicit zero/erased information fixtures are supported')
        value = 0 if kind == 'zero' else 0xffffffff
        words = {0x310: 'TRIM_REV'}
        if metadata:
            words.update({0x240: 'PATCH_TRACKER0', 0x314: 'FT1_GDR1'})
        state = {'kind': kind, 'value': hex(value), 'reads': 0,
                 'scope': 'three-boot-metadata-words' if metadata else 'revision-only',
                 'word_reads': {name: 0 for name in words.values()},
                 'device_data': False, 'valid_calibration': False}
        report['info1_metadata_fixture' if metadata else 'trim_revision_fixture'] = state
        report['models'].append('invalid-info1-metadata-fixture' if metadata else 'invalid-trim-revision-fixture')
        report['assumptions'].append('Sparse zero/erased Info1 input is synthetic, not valid device calibration')
        if 'shadow_info1' in report:
            report['shadow_info1']['otp_and_information_data'] = 'Separate sparse invalid Info1 fixture only; OTP and other data unprovided'

        def stop(uc, offset, size, operation):
            report['reason'] = 'unsupported-information-access'
            report['access'] = {'kind': operation, 'address': hex(0x42003000+offset),
                                'bytes': size, 'pc': hex(uc.reg_read(a.UC_ARM_REG_PC))}
            uc.emu_stop()

        def read(uc, offset, size, _):
            if offset not in words or size != 4:
                stop(uc, offset, size, 'read-unprovided-information')
                return 0
            state['reads'] += 1
            state['word_reads'][words[offset]] += 1
            return value

        def write(uc, offset, size, value, _):
            stop(uc, offset, size, 'write-information-prohibited')

        cpu.mmio_map(0x42003000, 0x1000, read, None, write, None)
