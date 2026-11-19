"""Run unchanged original mains with explicit controller-off / retained-NOR hypothesis."""
import argparse
import json
import shutil
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_MCLASS
from native_replay import FILES, IMAGE, parse_log, validate_assets, digest, boundary_state
from pinned_main import load_pinned_main
from verify_mspi1_pio_reset import models
from run_renode_m55_probe import execute


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('simulator', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--case', choices=['stock24', 'stock23', 'cfw'], default='stock24')
    p.add_argument('--response', choices=['off', 'stuck-on', 'unknown'], default='off')
    p.add_argument('--xip-restore', action='store_true')
    p.add_argument('--continuous-status', action='store_true')
    p.add_argument('--erased-kvdb', action='store_true')
    p.add_argument('--erased-nvdb', action='store_true', help='Explicit synthetic blank factory partition, never device data')
    p.add_argument('--array-read-limit', type=int, default=64, help='Opt-in bounded RX streaming; default is one FIFO')
    p.add_argument('--otp-power-response', choices=['unknown', 'active', 'stuck-off'], default='unknown')
    p.add_argument('--crypto-power-response', choices=['unknown', 'active', 'stuck-off'], default='unknown')
    p.add_argument('--crypto-nvm-idle', choices=['unknown', 'idle', 'busy'], default='unknown')
    p.add_argument('--crypto-host-idle', choices=['unknown', 'idle', 'busy'], default='unknown')
    p.add_argument('--otp-ptm', choices=['unknown', 'clear', 'busy'], default='unknown')
    p.add_argument('--otp-ptm-read-budget', type=int, default=0)
    p.add_argument('--otp-serial-profile', choices=['none','empty','mock-first','mock-last','invalid-prefix','invalid-digit'], default='none')
    p.add_argument('--crypto-off-response', choices=['unknown','off','stuck-on'], default='unknown')
    p.add_argument('--otp-off-response', choices=['unknown','off','stuck-on'], default='unknown')
    p.add_argument('--blank-littlefs', action='store_true', help='Explicit synthetic blank volume, read-only by default; never stock filesystem data')
    p.add_argument('--littlefs-writable', action='store_true', help='Allow erase/program only in the explicitly selected synthetic RAM volume')
    p.add_argument('--gpio-role-level', choices=['unknown','low','high'], default='unknown')
    p.add_argument('--gpio-role-read-budget', type=int, default=5)
    p.add_argument('--timer0-profile', choices=['unknown','nominal-hfrc96-upcount'], default='unknown')
    p.add_argument('--sector-erase-us', type=int, default=0)
    p.add_argument('--stuck-sector-erase', action='store_true')
    p.add_argument('--read-only-kvdb', action='store_true')
    p.add_argument('--page-program-us', type=int, default=0)
    p.add_argument('--stuck-page-program', action='store_true')
    p.add_argument('--read-only-program', action='store_true')
    p.add_argument('--compact-status', action='store_true')
    p.add_argument('--compact-storage', action='store_true')
    a = p.parse_args()
    if a.timer0_profile!='unknown' and a.gpio_role_level=='unknown':
        p.error('Timer0 profile requires explicit GPIO role input scenario')
    if (a.gpio_role_level!='unknown' and (not a.littlefs_writable or not 1<=a.gpio_role_read_budget<=64)) or (a.gpio_role_level=='unknown' and a.gpio_role_read_budget!=5):
        p.error('GPIO role input requires writable synthetic LittleFS and explicit 1..64 read budget; unknown keeps default budget')
    if a.littlefs_writable and not a.blank_littlefs:
        p.error('Writable LittleFS requires the explicit synthetic blank volume')
    if a.blank_littlefs and not (a.erased_nvdb and a.otp_serial_profile!='none' and a.crypto_off_response=='off' and a.otp_off_response=='off'):
        p.error('Blank LittleFS requires explicit blank NVdb, serial fixture and both power-off success profiles')
    crypto_otp_off_selected = a.crypto_off_response!='unknown' or a.otp_off_response!='unknown'
    if crypto_otp_off_selected and not (a.otp_power_response=='active' and a.crypto_power_response=='active' and a.crypto_host_idle=='idle' and a.otp_ptm=='clear' and a.crypto_nvm_idle=='idle'):
        p.error('CRYPTO OTP off requires explicit active powers, HOST idle, PTM clear and NVM idle')
    if a.otp_serial_profile != 'none' and not (a.crypto_host_idle == 'idle' and a.otp_ptm == 'clear' and a.crypto_nvm_idle == 'idle'):
        p.error('Synthetic serial slots require explicit HOST idle, PTM clear and NVM idle')
    readiness_selected = a.crypto_host_idle != 'unknown' or a.otp_ptm != 'unknown'
    if (readiness_selected and a.crypto_power_response != 'active') or (a.otp_ptm == 'busy' and not 1 <= a.otp_ptm_read_budget <= 4096) or (a.otp_ptm != 'busy' and a.otp_ptm_read_budget != 0):
        p.error('Read readiness requires active CRYPTO; busy PTM needs explicit 1..4096 observation budget')
    if (a.crypto_power_response != 'unknown' and a.otp_power_response != 'active') or (a.crypto_nvm_idle != 'unknown' and a.crypto_power_response == 'unknown'):
        p.error('CRYPTO response requires explicit active OTP; NVM flag requires selected CRYPTO power')
    if a.otp_power_response != 'unknown' and not (a.erased_nvdb and a.array_read_limit > 64):
        p.error('OTP power response requires explicit blank NVdb and RX streaming scenario')
    if not 64 <= a.array_read_limit <= 65535 or (a.array_read_limit > 64 and not a.erased_kvdb):
        p.error('Array read limit requires 64..65535 and explicit KVDB backing for streaming')
    if a.erased_nvdb and not (a.erased_kvdb and a.xip_restore and a.continuous_status and a.sector_erase_us > 0 and a.page_program_us > 0):
        p.error('Blank NVdb requires explicit KVDB, XIP restore, continuous status, erase and program durations')
    if not 0 <= a.sector_erase_us <= 1000000 or (a.sector_erase_us and not a.erased_kvdb) or (a.stuck_sector_erase and not a.sector_erase_us):
        p.error('Sector erase requires explicit KVDB and 1..1000000us; zero is unknown')
    if not 0 <= a.page_program_us <= 1000000 or (a.page_program_us and not a.erased_kvdb) or (a.stuck_page_program and not a.page_program_us):
        p.error('Page program requires explicit KVDB and 1..1000000us; zero is unknown')
    compact_status = a.compact_status or a.compact_storage or a.stuck_sector_erase or a.stuck_page_program
    suppressed_points = ['status-byte'] if compact_status else []
    s, out, key = a.simulator, a.output, a.case
    src = s / 'mspi1-cqflags-main-02' / key
    prior = json.loads((src / 'report.json').read_text())
    if parse_log((src / 'renode.log').read_text()) != prior['observed']:
        raise ValueError('Prior report differs')
    validate_assets(src, json.loads((src / 'derived-inputs.json').read_text())['derived'])
    bundle = {'stock24': 'stock-2.4.0.24.bin', 'stock23': 'stock-2.3.0.24.bin', 'cfw': 'faceclaw-38-research-only.bin'}[key]
    _, raw = load_pinned_main((s / 'inputs/verified-01' / bundle).read_bytes())
    if raw != (src / 'main.bin').read_bytes():
        raise ValueError('Not original main')
    delta = 0 if key == 'stock24' else 0xd3d4
    call = 0x4e935c - delta
    code = {i.address: (i.mnemonic, i.op_str) for i in Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS).disasm(raw[call - 0x438000:call + 0x10 - 0x438000], call)}
    entry = 0x494e96 if key == 'stock24' else 0x488fae
    if code.get(call) != ('bl', '#' + hex(entry)) or code.get(call + 4) != ('movs', 'r3, #0'):
        raise ValueError('Original power caller differs')
    out.mkdir(mode=0o700, parents=True)
    for f in FILES:
        shutil.copyfile(src / f, out / f)
    board = (src / 'board.repl').read_text()
    if a.timer0_profile!='unknown':
        needle='    profile: "nominal-xt-lfrc"\n'
        if board.count(needle)!=1:raise ValueError('Expected one shared Timer14 owner')
        board=board.replace(needle,needle+'    timer0Profile: "nominal-hfrc96-upcount"\n    Timer0IRQ -> nvic@67\n')
    gpio_role_meta=None
    if a.gpio_role_level!='unknown':
        contract=json.loads((s/'gpio-role-input-contract-03/report.json').read_text())
        if not contract['passed'] or contract['count']!=49:raise ValueError('Missing GPIO role source contract')
        gpio_role_meta=next(row for row in contract['cases'] if row['case']==key)
        board=board.replace('    baseAddress: 0x40001000\n','    baseAddress: 0x40001000\n    gpioRoleInput: gpio_role_input\n')
        board+='\ngpio_role_input: Miscellaneous.BlackwallGpioRoleInput @ none\n    level: '+str(int(a.gpio_role_level=='high'))+'\n    readPc: '+gpio_role_meta['input_read_pc']+'\n    readBudget: '+str(a.gpio_role_read_budget)+'\n'
    if a.otp_power_response != 'unknown':
        needle = '    baseAddress: 0x40001000\n'
        if board.count(needle) != 1 or 'otp_power:' in board:
            raise ValueError('Unexpected OTP power owner')
        board = board.replace(needle, needle + '    otpPower: otp_power\n')
        board += '\notp_power: Miscellaneous.BlackwallPeripheralPower @ none\n    mask: 0x08000000\n    profile: ' + str(int(a.otp_power_response == 'active')) + '\n'
    if a.crypto_power_response != 'unknown':
        needle = '    baseAddress: 0x40001000\n'
        board = board.replace(needle, needle + '    cryptoPower: crypto_power\n    cryptoNvmIdle: ' + str({'unknown': -1, 'busy': 0, 'idle': 1}[a.crypto_nvm_idle]) + '\n')
        board += '\ncrypto_power: Miscellaneous.BlackwallPeripheralPower @ none\n    mask: 0x200000\n    profile: ' + str(int(a.crypto_power_response == 'active')) + '\n'
    if readiness_selected:
        board = board.replace('    baseAddress: 0x40001000\n', '    baseAddress: 0x40001000\n    otpReadReadiness: otp_read_readiness\n')
        board += '\notp_read_readiness: Miscellaneous.BlackwallOtpReadReadiness @ none\n    otpPower: otp_power\n    cryptoPower: crypto_power\n    hostIdle: ' + str({'unknown': -1, 'busy': 0, 'idle': 1}[a.crypto_host_idle]) + '\n    ptmBusy: ' + str({'unknown': -1, 'clear': 0, 'busy': 1}[a.otp_ptm]) + '\n    ptmReadBudget: ' + str(a.otp_ptm_read_budget) + '\n'
    if a.otp_serial_profile != 'none':
        board = board.replace('    baseAddress: 0x40001000\n','    baseAddress: 0x40001000\n    otpSerialSlots: otp_serial_slots\n')
        board += '\notp_serial_slots: Miscellaneous.BlackwallOtpSerialSlots @ none\n    readiness: otp_read_readiness\n    profile: "' + a.otp_serial_profile + '"\n'
    if crypto_otp_off_selected:
        board = board.replace('    baseAddress: 0x40001000\n','    baseAddress: 0x40001000\n    cryptoOtpPowerLifecycle: crypto_otp_lifecycle\n')
        board += '\ncrypto_otp_lifecycle: Miscellaneous.BlackwallCryptoOtpPowerLifecycle @ none\n    readiness: otp_read_readiness\n'
        for mask, response in [('0x200000',a.crypto_off_response),('0x08000000',a.otp_off_response)]:
            if response!='unknown':
                needle='    mask: '+mask+'\n    profile: 1\n'
                if board.count(needle)!=1:raise ValueError('Unexpected lifecycle power owner')
                board=board.replace(needle,needle+'    offProfile: '+str(int(response=='stuck-on'))+'\n')
    if a.erased_kvdb:
        needle = '    profile: "idle-nor-reset"\n'
        if board.count(needle) != 1 or 'nor_read_window:' in board:
            raise ValueError('Unexpected NOR backing owner')
        board = board.replace(needle, needle + '    arrayBacking: nor_read_window\n')
        if a.array_read_limit > 64:
            board = board.replace(needle, needle + '    maxArrayReadBytes: ' + str(a.array_read_limit) + '\n')
        board += '\nnor_read_window: Miscellaneous.BlackwallNorReadWindow @ none\n    profile: "erased-range"\n    start: 0x1fc0000\n    length: ' + ('0x40000' if a.erased_nvdb else '0x38000') + '\n'
        if a.blank_littlefs:
            board+='    additionalWindow: littlefs_blank_volume\n'
        if a.sector_erase_us:
            if not a.read_only_kvdb:
                board += '    allowSectorErase: true\n'
            board = board.replace(needle, needle + '    sectorEraseMicroseconds: ' + str(a.sector_erase_us) + '\n    completeSectorErase: ' + str(not a.stuck_sector_erase).lower() + '\n')
        if a.page_program_us:
            if not a.read_only_program:
                board += '    allowPageProgram: true\n'
            board = board.replace(needle, needle + '    pageProgramMicroseconds: ' + str(a.page_program_us) + '\n    completePageProgram: ' + str(not a.stuck_page_program).lower() + '\n')
    if a.blank_littlefs:
        board+='\nlittlefs_blank_volume: Miscellaneous.BlackwallNorReadWindow @ none\n    profile: "erased-range"\n    start: 0x1400000\n    length: 0xbc0000\n'
        if a.littlefs_writable:
            board+='    allowSectorErase: true\n    allowPageProgram: true\n'
    if a.continuous_status:
        needle = '    profile: "idle-nor-reset"\n'
        if board.count(needle) != 1:
            raise ValueError('Unexpected PIO owner')
        board = board.replace(needle, needle + '    continuousStatusRead: true\n')
    if a.xip_restore:
        needle = '    profile: "source-reset-config"\n'
        if board.count(needle) != 1:
            raise ValueError('Unexpected config owner')
        board = board.replace(needle, needle + '    xipRestoreStorage: true\n')
    runtime = (src / 'run.py').read_text()
    if runtime.count('try:\n    import clr\n') != 1:
        raise ValueError('Unexpected runtime exception boundary')
    runtime = runtime.replace('try:\n    import clr\n', 'try:\n    import json\n    import clr\n')
    if compact_status:
        # Preserve every result/poll event rather than overflowing the observer's
        # bounded 4096 events with duplicate byte/result pairs in a stuck loop.
        lines = runtime.splitlines(keepends=True)
        removed = [line for line in lines if "observer.AddPoint('status-byte'," in line or "observer.CaptureSram(m,'status-byte'," in line]
        if len(removed) != 2:
            raise ValueError('Unexpected compact status observation points')
        runtime = ''.join(line for line in lines if line not in removed)
    if a.response != 'unknown':
        needle = '    mask: 0x8000\n    profile: 1\n'
        if board.count(needle) != 1:
            raise ValueError('Unexpected MSPI power owner')
        board = board.replace(needle, needle + '    offProfile: ' + str(int(a.response == 'stuck-on')) + '\n')
        if runtime.count('    e.StartAll()\n') != 1:
            raise ValueError('Unexpected runtime')
        runtime = runtime.replace('    e.StartAll()\n', "    m['sysbus.guard'].Mspi1Config.AttachRetentionPower(m['sysbus.guard'].Mspi1Power)\n    observer.AddPoint('MSPI-power-off-return'," + str(call + 4) + ')\n    e.StartAll()\n')
        if a.xip_restore:
            entry = 0x4e8f8c - delta
            post_store, restored = 0x4e9058 - delta, 0x4e9182 - delta
            restore_code = {i.address: (i.mnemonic, i.op_str) for i in Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS).disasm(raw[entry - 0x438000:restored + 2 - 0x438000], entry)}
            if restore_code.get(post_store - 4) != ('str.w', 'r2, [r1, #0x90]') or restore_code.get(restored - 4) != ('strb.w', 'r0, [r5, #0x860]') or restore_code.get(restored) != ('b', '#' + hex(0x4e91a6 - delta)):
                raise ValueError('Original restore observation sites differ')
            runtime = runtime.replace('    e.StartAll()\n', "    observer.AddPoint('XIP-retention-restored'," + str(post_store) + ")\n    observer.AddPoint('MSPI-retention-state-restored'," + str(restored) + ')\n    e.StartAll()\n')
    marker = "    c=m['sysbus.guard'].Mspi1Config\n    power=m['sysbus.guard'].Mspi1Power\n    Console.WriteLine('BLACKWALL_MSPI_CONTROLLER_OFF '+json.dumps(dict(count=int(c.ControllerPowerDowns),phase=str(power.Phase),power_cycles=int(power.PowerCycles),request=int(power.RequestWord),status=int(power.StatusWord),controller_idle=bool(c.CanPowerDown()),shutdown_gate=bool(power.CanShutdown()),external_supply='@SUPPLY@',xip_restore_selected=bool(c.XipRestoreStorage),xip_restores=int(c.XipRestoreWrites))))\n"
    if runtime.count('except Exception as error:\n') != 1:
        raise ValueError('Unexpected result insertion')
    marker = marker.replace('@SUPPLY@', 'unspecified' if a.response == 'unknown' else 'retained-hypothesis')
    marker += "    q=c.Pio\n    Console.WriteLine('BLACKWALL_CONTINUOUS_STATUS '+json.dumps(dict(selected=bool(q.ContinuousStatusRead),completed=int(q.ContinuousStatusTransfers),discarded_bytes=int(q.StatusDiscardedBytes),total_status=int(q.StatusReadTransfers),physical_pins_verified=False)))\n"
    marker += "    backing=q.ArrayBacking\n    Console.WriteLine('BLACKWALL_NOR_ARRAY '+json.dumps(dict(profile=(str(backing.Profile) if backing is not None else None),start=(int(backing.Start) if backing is not None else None),length=(int(backing.Length) if backing is not None else None),reads=int(q.ArrayReadTransfers),bytes=int(q.ArrayBytesRead),last_address=int(q.LastArrayAddress),rx_entries=int(q.RxEntries),physical_contents_known=False)))\n"
    marker += "    Console.WriteLine('BLACKWALL_NOR_ERASE '+json.dumps(dict(duration_us=int(q.SectorEraseMicroseconds),can_complete=bool(q.CompleteSectorErase),allowed=(bool(backing.AllowSectorErase) if backing is not None else False),starts=int(q.SectorEraseStarts),completions=int(q.SectorEraseCompletions),busy=bool(q.EraseBusy),last_address=int(q.LastEraseAddress),status=int(q.CurrentStatusByte),wel=bool(q.WriteEnabled),physical_latency_verified=False)))\n"
    marker += "    prefix_words=None\n    if backing is not None:\n        ok,prefix=backing.TryRead(backing.Start,16)\n        if ok:prefix_words=[sum(int(prefix[i+j])<<(8*j) for j in range(4)) for i in range(0,16,4)]\n    Console.WriteLine('BLACKWALL_NOR_PROGRAM '+json.dumps(dict(duration_us=int(q.PageProgramMicroseconds),can_complete=bool(q.CompletePageProgram),allowed=(bool(backing.AllowPageProgram) if backing is not None else False),starts=int(q.PageProgramStarts),completions=int(q.PageProgramCompletions),busy=bool(q.ProgramBusy),bytes=int(q.ProgramBytesCommitted),last_address=int(q.LastProgramAddress),tx_entries=int(q.TxEntries),tx_writes=int(q.TxFifoWrites),prefix_words=prefix_words,physical_latency_verified=False)))\n"
    if a.erased_kvdb:
        contract = json.loads((s / 'nor-kvdb-contract-02/report.json').read_text())
        meta = next(row for row in contract['cases'] if row['case'] == key)
        header_read = int(meta['header_read'], 0)
        failed_return = header_read + 0x38
        valid = header_read + 0x3c
        check_code = {i.address: (i.mnemonic, i.op_str) for i in Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS).disasm(raw[header_read - 0x438000:valid + 2 - 0x438000], header_read)}
        if check_code.get(header_read, ('', ''))[0] != 'bl' or check_code.get(failed_return - 2) != ('movs', 'r0, #8') or check_code.get(failed_return, ('', ''))[0] != 'b':
            raise ValueError('Original KV observation sites differ')
        old = json.loads((s / 'mspi1-continuous-status-main-01' / key / 'report.json').read_text())
        buffer = old['observed']['register_context']['r9']
        if buffer % 4 or not 0x20000000 <= buffer <= 0x20380000 - 16:
            raise ValueError('Header buffer not bounded SRAM')
        points = "    observer.AddPoint('KV-header-read-return'," + str(header_read + 4) + ")\n    observer.CaptureSram(m,'KV-header-read-return'," + str(buffer) + ",4)\n    observer.AddPoint('KV-header-invalid-return'," + str(failed_return) + ')\n'
        if a.page_program_us:
            if check_code.get(valid - 2) != ('movs', 'r0, #1') or check_code.get(valid) != ('strb', 'r0, [r4]'):
                raise ValueError('Original KV valid-header site differs')
            points += "    observer.AddPoint('KV-header-valid'," + str(valid) + ')\n'
        runtime = runtime.replace('    e.StartAll()\n', points + '    e.StartAll()\n')
    if a.erased_nvdb:
        marker += "    ok,nvprefix=backing.TryRead(0x1ff8000,16)\n    if not ok:raise ValueError('Declared NVdb window missing')\n    Console.WriteLine('BLACKWALL_NVDB_SCENARIO '+json.dumps(dict(profile='synthetic-blank-kvdb-and-nvdb',start=0x1ff8000,length=0x8000,prefix_words=[sum(int(nvprefix[i+j])<<(8*j) for j in range(4)) for i in range(0,16,4)],physical_factory_data_known=False)))\n"
        nvcontract = json.loads((s / 'nvdb-consumer-contract-04/report.json').read_text())
        nvmeta = next(row for row in nvcontract['cases'] if row['case'] == key)
        nventry = int(nvmeta['initializer'], 0)
        nvcode = {i.address: (i.mnemonic, i.op_str) for i in Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS).disasm(raw[nventry - 0x438000:nventry + 0x212 - 0x438000], nventry)}
        if nvcode.get(nventry + 0x54) != ('bl', '#' + nvmeta['db_init']) or nvcode.get(nventry + 0x1bc, ('', ''))[0] != 'bl' or nvcode.get(nventry + 0x20e) != ('add', 'sp, #0x30'):
            raise ValueError('Original NVdb observation sites differ')
        nvpoints = [('NVdb-initializer-entry', nventry), ('NVdb-default-tail', nventry + 2), ('NVdb-DB-init-return', nventry + 0x58),
                    ('NVdb-magic-read-return', nventry + 0xd6), ('NVdb-magic-rebuild-call', nventry + 0x1bc),
                    ('NVdb-magic-rebuild-return', nventry + 0x1c0), ('NVdb-initializer-return', nventry + 0x20e)]
        points = ''.join("    observer.AddPoint('" + label + "'," + str(address) + ')\n' for label, address in nvpoints)
        table = int(nvmeta['default_table'], 0)
        if table % 4 or not 0x20000000 <= table <= 0x20380000 - 108:
            raise ValueError('NVdb defaults not bounded SRAM')
        points += "    observer.CaptureSram(m,'NVdb-initializer-entry'," + str(table) + ',15)\n'
        points += "    observer.CaptureSram(m,'NVdb-default-tail'," + str(table + 60) + ',12)\n'
        runtime = runtime.replace('    e.StartAll()\n', points + '    e.StartAll()\n')
    if a.otp_power_response != 'unknown':
        otpcontract = json.loads((s / 'otp-power-contract-01/report.json').read_text())
        otpmeta = next(row for row in otpcontract['cases'] if row['case'] == key)
        caller = int(otpmeta['caller'], 0)
        otpcode = {i.address: (i.mnemonic, i.op_str) for i in Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS).disasm(raw[caller - 0x438000:caller + 8 - 0x438000], caller)}
        if otpcode.get(caller) != ('bl', '#' + otpmeta['entry']) or otpcode.get(caller + 4) != ('movs', 'r0, #0x17'):
            raise ValueError('Original OTP caller observation site differs')
        otppoints = [('OTP-enable-caller-return', caller + 4)]
        runtime = runtime.replace('    e.StartAll()\n', ''.join("    observer.AddPoint('" + label + "'," + str(address) + ')\n' for label, address in otppoints) + '    e.StartAll()\n')
    marker += "    otp=m['sysbus.guard'].OtpPower\n    Console.WriteLine('BLACKWALL_OTP_POWER '+json.dumps(dict(selected=otp is not None,phase=(str(otp.Phase) if otp is not None else None),request=(int(otp.RequestWord) if otp is not None else 0),status=(int(otp.StatusWord) if otp is not None else 0),requests=(int(otp.Requests) if otp is not None else 0),responses=(int(otp.Responses) if otp is not None else 0),OTP_contents_known=False,physical_power_verified=False)))\n"
    if a.crypto_power_response != 'unknown':
        contract = json.loads((s / 'crypto-power-contract-01/report.json').read_text())
        cryptometa = next(row for row in contract['cases'] if row['case'] == key)
        caller, wait_call = int(cryptometa['caller'], 0), int(cryptometa['NVM_wait_call'], 0)
        crypto_code = {i.address: (i.mnemonic, i.op_str) for i in Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS).disasm(raw[caller - 0x438000:caller + 8 - 0x438000], caller)}
        wait_code = {i.address: (i.mnemonic, i.op_str) for i in Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS).disasm(raw[wait_call - 0x438000:wait_call + 6 - 0x438000], wait_call)}
        if crypto_code.get(caller) != ('bl', '#' + cryptometa['power_entry']) or crypto_code.get(caller + 4) != ('movs', 'r0, #1') or wait_code.get(wait_call + 4) != ('cmp', 'r0, #0'):
            raise ValueError('Original CRYPTO observation sites differ')
        points = [('CRYPTO-enable-caller-return', caller + 4), ('CRYPTO-NVM-wait-return', wait_call + 4)]
        runtime = runtime.replace('    e.StartAll()\n', ''.join("    observer.AddPoint('" + label + "'," + str(address) + ')\n' for label, address in points) + '    e.StartAll()\n')
    marker += "    cp=m['sysbus.guard'].CryptoPower\n    Console.WriteLine('BLACKWALL_CRYPTO_POWER '+json.dumps(dict(selected=cp is not None,phase=(str(cp.Phase) if cp is not None else None),request=(int(cp.RequestWord) if cp is not None else 0),status=(int(cp.StatusWord) if cp is not None else 0),requests=(int(cp.Requests) if cp is not None else 0),responses=(int(cp.Responses) if cp is not None else 0),nvm_idle=int(m['sysbus.guard'].CryptoNvmIdle),nvm_reads=int(m['sysbus.guard'].CryptoNvmReads),crypto_engine=False,physical_ready_verified=False)))\n"
    readiness_points = []
    if readiness_selected:
        contract = json.loads((s / 'crypto-host-idle-contract-01/report.json').read_text())
        readmeta = next(row for row in contract['cases'] if row['case'] == key)
        entry, wrapper = int(readmeta['ready_function'], 0), int(readmeta['read_wrapper'], 0)
        readcode = {i.address: (i.mnemonic, i.op_str) for i in Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS).disasm(raw[entry - 0x438000:wrapper + 0x36 - 0x438000], entry)}
        if readcode.get(entry + 0x3a) != ('bx', 'lr') or readcode.get(wrapper + 0x34) != ('pop', '{r1, r4, r5, pc}'):
            raise ValueError('Original OTP read observation sites differ')
        points = [('OTP-read-ready-return', entry + 0x3a), ('OTP-word-read-return', wrapper + 0x34)]
        readiness_points = [label for label, _ in points]
        runtime = runtime.replace('    e.StartAll()\n', ''.join("    observer.AddPoint('" + label + "'," + str(address) + ')\n' for label, address in points) + '    e.StartAll()\n')
    marker += "    rd=m['sysbus.guard'].OtpReadReadiness\n    Console.WriteLine('BLACKWALL_OTP_READ_READY '+json.dumps(dict(selected=rd is not None,host_idle=(int(rd.HostIdle) if rd is not None else -1),ptm_busy=(int(rd.PtmBusy) if rd is not None else -1),host_reads=(int(rd.HostReads) if rd is not None else 0),ptm_reads=(int(rd.PtmReads) if rd is not None else 0),budget=(int(rd.PtmReadBudget) if rd is not None else 0),budget_exhausted=(bool(rd.PtmBudgetExhausted) if rd is not None else False),OTP_contents_known=False,physical_ready_verified=False)))\n"
    if a.otp_serial_profile != 'none':
        contract = json.loads((s / 'otp-window-consumer-contract-02/report.json').read_text())
        meta = next(row for row in contract['cases'] if row['case'] == key)
        entry = int(meta['consumer_entry'],0)
        serialcode = {i.address: (i.mnemonic,i.op_str) for i in Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS).disasm(raw[entry - 0x438000:entry + 0x1d4 - 0x438000],entry)}
        if serialcode.get(entry) != ('push.w','{r3, r4, r5, r6, r7, r8, sb, sl, fp, lr}') or serialcode.get(entry + 0x1d0) != ('movs','r0, #0x17'):
            raise ValueError('Original serial scan sites differ')
        prior_serial = json.loads((s / 'otp-read-ready-main-01' / key / 'report.json').read_text())
        output_buffer = prior_serial['observed']['register_context']['r6']
        if output_buffer % 4 or not 0x20000000 <= output_buffer <= 0x20380000 - 16:
            raise ValueError('Serial output not bounded SRAM')
        points = [('OTP-serial-scan-entry',entry),('OTP-serial-scan-end',entry + 0x1d0)]
        readiness_points += [label for label,_ in points]
        text = ''.join("    observer.AddPoint('" + label + "'," + str(address) + ")\n    observer.CaptureSram(m,'" + label + "'," + str(output_buffer) + ',4)\n' for label,address in points)
        runtime = runtime.replace('    e.StartAll()\n',text + '    e.StartAll()\n')
    marker += "    slots=m['sysbus.guard'].OtpSerialSlots\n    Console.WriteLine('BLACKWALL_OTP_SERIAL_SLOTS '+json.dumps(dict(selected=slots is not None,profile=(str(slots.Profile) if slots is not None else None),reads=(int(slots.Reads) if slots is not None else 0),last_address=(int(slots.LastAddress) if slots is not None else 0),start=(int(slots.Start) if slots is not None else None),length=(int(slots.Length) if slots is not None else None),synthetic=True,hardware_contents_known=False)))\n"
    if crypto_otp_off_selected:
        contract=json.loads((s/'crypto-otp-power-off-contract-02/report.json').read_text())
        meta=next(row for row in contract['cases'] if row['case']==key)
        cp_call,otp_call=int(meta['crypto_cleanup_call'],0),int(meta['otp_cleanup_call'],0)
        disable=int(meta['disable_entry'],0)
        code={i.address:(i.mnemonic,i.op_str) for i in Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS).disasm(raw[cp_call-0x438000:otp_call+6-0x438000],cp_call)}
        if code.get(cp_call)!=('bl','#'+hex(disable)) or code.get(cp_call+4)!=('movs','r0, #0x1d') or code.get(otp_call)!=('bl','#'+hex(disable)) or code.get(otp_call+4)!=('cmp','r7, #0'):
            raise ValueError('Original cleanup return sites differ')
        points=[('CRYPTO-disable-caller-return',cp_call+4),('OTP-disable-caller-return',otp_call+4)]
        readiness_points += [label for label,_ in points]
        runtime=runtime.replace('    e.StartAll()\n',''.join("    observer.AddPoint('"+label+"',"+str(address)+')\n' for label,address in points)+'    e.StartAll()\n')
    marker += "    def power_off_state(p):\n        return None if p is None else dict(phase=str(p.Phase),request=int(p.RequestWord),status=int(p.StatusWord),off_profile=int(p.OffProfile),off_requests=int(p.OffRequests),cycles=int(p.PowerCycles),generation=int(p.Generation))\n    lc=m['sysbus.guard'].CryptoOtpPowerLifecycle\n    Console.WriteLine('BLACKWALL_CRYPTO_OTP_OFF '+json.dumps(dict(selected=lc is not None,crypto=power_off_state(cp),otp=power_off_state(otp),host_current=(bool(rd.HostObservedForCurrentPower) if rd is not None else False),ptm_current=(bool(rd.PtmObservedForCurrentPower) if rd is not None else False),idle_only=True,physical_verified=False)))\n"
    if a.blank_littlefs:
        contract=json.loads((s/'littlefs-mount-policy-contract-01/report.json').read_text())
        meta=next(row for row in contract['cases'] if row['case']==key)
        entry=int(meta['app_init'],0)
        initcode={i.address:(i.mnemonic,i.op_str) for i in Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS).disasm(raw[entry-0x438000:entry+0x2a-0x438000],entry)}
        if initcode.get(entry+0xc)!=('bl','#'+meta['mount']) or initcode.get(entry+0x1a)!=('bl','#'+meta['format']) or initcode.get(entry+0x22)!=('bl','#'+meta['mount']):
            raise ValueError('Original LittleFS policy sites differ')
        points=[('LittleFS-mount-entry',int(meta['mount'],0)),('LittleFS-format-entry',int(meta['format'],0)),('LittleFS-read-entry',int(meta['read_callback'],0)),('LittleFS-first-mount-return',entry+0x10),('LittleFS-format-return',entry+0x1e),('LittleFS-remount-return',entry+0x26)]
        if a.littlefs_writable:
            epilogue={i.address:(i.mnemonic,i.op_str) for i in Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS).disasm(raw[entry+0x150-0x438000:entry+0x154-0x438000],entry+0x150)}
            if epilogue.get(entry+0x150)!=('add','sp, #0x28') or epilogue.get(entry+0x152)!=('pop','{r4, r5, r6, pc}'):
                raise ValueError('Original LittleFS app return differs')
            points.append(('LittleFS-app-init-return',entry+0x150))
        readiness_points += [label for label,_ in points]
        runtime=runtime.replace('    e.StartAll()\n',''.join("    observer.AddPoint('"+label+"',"+str(address)+')\n' for label,address in points)+'    e.StartAll()\n')
    marker += "    vol=backing.AdditionalWindow if backing is not None else None\n    volume_prefix=None\n    if vol is not None:\n        ok,data=vol.TryRead(vol.Start,16)\n        if not ok:raise ValueError('Missing volume prefix')\n        volume_prefix=[int(x) for x in data]\n    Console.WriteLine('BLACKWALL_LITTLEFS_VOLUME '+json.dumps(dict(selected=vol is not None,start=(int(vol.Start) if vol is not None else None),length=(int(vol.Length) if vol is not None else None),erase_allowed=(bool(vol.AllowSectorErase) if vol is not None else False),program_allowed=(bool(vol.AllowPageProgram) if vol is not None else False),prefix=volume_prefix,synthetic=True,stock_contents_known=False)))\n"
    if gpio_role_meta is not None:
        role=int(gpio_role_meta['role_function'],0);getter=int(gpio_role_meta['gpio_function'],0)
        code={i.address:(i.mnemonic,i.op_str) for i in Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS).disasm(raw[role+0x54-0x438000:role+0x5a-0x438000],role+0x54)}
        if code.get(role+0x54)!=('bl','#'+hex(getter)) or code.get(role+0x58)!=('cmp','r0, #0'):raise ValueError('Original GPIO sample return differs')
        points=[('GPIO-role-sample-return',role+0x58),('GPIO-role-return',int(gpio_role_meta['role_return'],0))]
        readiness_points += [label for label,_ in points]
        runtime=runtime.replace('    e.StartAll()\n',''.join("    observer.AddPoint('"+label+"',"+str(address)+')\n' for label,address in points)+'    e.StartAll()\n')
        prior_gpio=json.loads((s/'littlefs-format-main-01'/key/'report.json').read_text())
        output=prior_gpio['observed']['register_context']['r2']
        if output%4 or not 0x20000000<=output<=0x2037fffc:raise ValueError('GPIO result outside bounded SRAM')
        runtime=runtime.replace('    e.StartAll()\n',"    observer.CaptureSram(m,'GPIO-role-sample-return',"+str(output)+',1)\n'+'    e.StartAll()\n')
    marker += "    gi=m['sysbus.guard'].GpioRoleInput\n    Console.WriteLine('BLACKWALL_GPIO_ROLE_INPUT '+json.dumps(dict(selected=gi is not None,level=(int(gi.Level) if gi is not None else -1),reads=(int(gi.Reads) if gi is not None else 0),budget=(int(gi.ReadBudget) if gi is not None else 0),read_pc=(int(gi.ReadPc) if gi is not None else None),last_context_pc=(int(gi.LastContextPc) if gi is not None else None),last_context_pin=(int(gi.LastContextPin) if gi is not None else None),pin=156,known_mask=0x10000000,other_bits_are_padding=True,consumer_gated=True,physical_level_known=False)))\n"
    if a.timer0_profile!='unknown':
        contract=json.loads((s/'timer0-sync-contract-03/report.json').read_text())
        if not contract['passed'] or contract['count']!=118:raise ValueError('Missing Timer0 setup source contract')
        meta=next(row for row in contract['cases'] if row['case']==key);setup=int(meta['setup'],0)
        code={i.address:(i.mnemonic,i.op_str) for i in Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS).disasm(raw[setup-0x438000:setup+0x4a-0x438000],setup)}
        if code.get(setup+0x24)!=('movs','r0, #0') or code.get(setup+0x48)!=('pop','{r4, pc}'):raise ValueError('Original Timer0 observation sites differ')
        points=[('Timer0-config-return',setup+0x24),('Timer0-setup-return',setup+0x48),('Timer0-ISR-entry',int(meta['vector_handler'],0))]
        readiness_points += [label for label,_ in points]
        runtime=runtime.replace('    e.StartAll()\n',''.join("    observer.AddPoint('"+label+"',"+str(address)+')\n' for label,address in points)+'    e.StartAll()\n')
    marker += "    t=m['sysbus.guard'].Timer14\n    Console.WriteLine('BLACKWALL_TIMER0 '+json.dumps(dict(selected=(bool(t.Timer0Enabled) if t is not None else False),control=(int(t.Timer0Control) if t is not None else None),counter=(int(t.Timer0Counter) if t is not None else None),compare0=(int(t.Timer0Compare0) if t is not None else None),compare1=(int(t.Timer0Compare1) if t is not None else None),mode=(int(t.Timer0Mode) if t is not None else None),running=(bool(t.Timer0Running) if t is not None else False),global_enable=(int(t.GlobalEnable) if t is not None else None),interrupt_enable=(int(t.Enable) if t is not None else None),interrupt_status=(int(t.Status) if t is not None else None),IRQ=(bool(t.Timer0IRQ.IsSet) if t is not None else False),frequency=(int(t.Timer0Frequency) if t is not None else None),nominal_hfrc_hz=96000000,physical_timing_verified=False)))\n"
    if a.compact_storage:
        # Repeated storage operations are already counted by the model markers.
        # Keep every poll outcome and KV/header stage, without discarding events.
        for label in ['status-result', 'CQFLAGS-saved', 'MSPI-power-off-return', 'XIP-retention-restored', 'MSPI-retention-state-restored']:
            lines = runtime.splitlines(keepends=True)
            adds = [line for line in lines if "observer.AddPoint('" + label + "'," in line]
            if len(adds) > 1:
                raise ValueError('Ambiguous compact storage point')
            if adds:
                runtime = ''.join(line for line in lines if "observer.AddPoint('" + label + "'," not in line and "observer.CaptureSram(m,'" + label + "'," not in line)
                suppressed_points.append(label)
    runtime = runtime.replace('except Exception as error:\n', marker + 'except Exception as error:\n')
    compile(runtime, 'run.py', 'exec')
    (out / 'run.py').write_text(runtime)
    (out / 'board.repl').write_text(board)
    (out / 'strict.cs').write_bytes(models(s))
    derived = {f: digest(out / f) for f in FILES}
    (out / 'derived-inputs.json').write_text(json.dumps(dict(derived=derived, base={f: digest(src / f) for f in FILES}), indent=2) + '\n')
    log = execute(['docker', 'run', '--rm', '--network', 'none', '--memory', '512m', '--cpus', '1', '--pids-limit', '128', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--mount', f'type=bind,source={out},target=/work,readonly', IMAGE, '--disable-gui', '--console', '-p', '-e', 'quit', '/work/probe.resc'], out, 'renode', timeout=None)
    observed = parse_log(log)
    validate_assets(out, derived)
    def read_marker(tag):
        rows = [json.loads(line.split(' ', 1)[1]) for line in log.splitlines() if line.startswith(tag + ' ')]
        if len(rows) != 1:
            raise ValueError(tag)
        return rows[0]
    off = read_marker('BLACKWALL_MSPI_CONTROLLER_OFF')
    obs = read_marker('BLACKWALL_OBSERVATION')
    if obs['dropped_events'] or len(obs['events']) != obs['sequence']:
        raise ValueError('Lost observer events')
    previous = prior['selected_observation']['events']
    if suppressed_points:
        previous = [dict(event, sequence=i + 1) for i, event in enumerate(event for event in previous if event['label'] not in suppressed_points)]
    comparison_events = obs['events']
    if readiness_points:
        comparison_events = [dict(event, sequence=i + 1) for i, event in enumerate(event for event in comparison_events if event['label'] not in readiness_points)]
    if comparison_events[:len(previous)] != previous:
        raise ValueError('Original event prefix changed')
    if a.response == 'unknown' and boundary_state(observed) != boundary_state(prior['observed']):
        raise ValueError('Unknown default changed boundary')
    report = dict(passed=True, observed=observed, controller_off=off, selected_observation=obs,
                  case=key, response=a.response, original_prefix_events=len(previous), compact_status_results_only=compact_status,
                  suppressed_observation_points=suppressed_points,
                  readiness_observation_points=readiness_points,
                  nor_scenario=('synthetic-blank-kvdb-and-nvdb' if a.erased_nvdb else 'synthetic-blank-kvdb' if a.erased_kvdb else 'none'),
                  littlefs_access=('read-write' if a.littlefs_writable else 'read-only' if a.blank_littlefs else 'none'),
                  hardware_validated=False, boot_verified=False, display_verified=False,
                  scope='Original main, source-reset controller state loss and retained external NOR hypothesis')
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(case=key, response=a.response, pc=hex(observed['pc']), off=off,
                          guards=[g for g in observed['guards'] if g['accesses']])), flush=True)


if __name__ == '__main__':
    main()
