"""Actual ARM word-prefix cuts followed by fresh original boot selection."""
import argparse
import hashlib
import json
from pathlib import Path
from run_recovery_m55_writer import prepare_capture,run_case,ROOT
from run_original_boot_screen import PRIVATE
from run_restored_boot import run as reboot


def sha(data):return hashlib.sha256(data).hexdigest()


def retire_writer_duplicates(folder,capture,baseline,cut):
    folder=Path(folder);capture=Path(capture);baseline=Path(baseline)
    final=(folder/'exports/final-mram.bin').read_bytes();payload=(capture/'payload.bin').read_bytes();before=baseline.read_bytes()
    expected=bytearray(before);expected[0x38010:0x38010+cut*4]=payload[:cut*4]
    report=json.loads((folder/'report.json').read_text())
    if final!=expected or sha(final)!=report['final_mram_sha256']:raise ValueError('Independent cut reconstruction failed')
    (folder/'exports/programmed-prefix.bin').write_bytes(payload[:cut*4])
    removed=[]
    for name,ref in [('mram.bin',baseline),('sram.bin',capture/'sram.bin'),('payload.bin',capture/'payload.bin')]:
        p=folder/name
        if p.read_bytes()!=ref.read_bytes():raise ValueError('Duplicate differs')
        removed.append(dict(name=name,reference=str(ref),bytes=p.stat().st_size,sha256=sha(p.read_bytes())));p.unlink()
    p=folder/'exports/final-mram.bin';removed.append(dict(name='exports/final-mram.bin',bytes=len(final),sha256=sha(final),reconstruction='baseline plus actual programmed-prefix.bin at offset0x38010'));p.unlink()
    result=dict(whole_mram_reconstructed=True,baseline=str(baseline),removed=removed,removed_bytes=sum(r['bytes'] for r in removed))
    (folder/'cleanup.json').write_text(json.dumps(result,indent=2)+'\n');return result


def run(restore,output):
    restore=Path(restore).resolve();output=Path(output).resolve()
    if not restore.is_relative_to(PRIVATE) or output.exists() or not output.is_relative_to(PRIVATE) or output.is_relative_to(ROOT):raise ValueError('Private restore input and fresh output required')
    capture=restore/'body-capture';manifest=json.loads((capture/'snapshot.json').read_text())
    if manifest.get('full_main_restore') is not True or manifest.get('destination')!=0x438010 or manifest['payload_bytes']!=3700064:raise ValueError('Whole-main capture required')
    output.mkdir(parents=True,mode=0o700);(output/'runner-source.py').write_bytes(Path(__file__).read_bytes());rows=[]
    for cut in (0,4,64,68):
        case=output/f'cut-{cut}';r=run_case(capture,case/'writer',interrupt_after_words=cut)
        b=reboot(case/'writer',case/'boot','incomplete')
        cleanup=retire_writer_duplicates(case/'writer',capture,capture/'mram.bin',cut)
        rows.append(dict(cut_words=cut,writer_passed=r['passed'],boot_passed=b['passed'],boot_classification=b['classification'],main=b['main'],handoff=b['handoff'],cleanup_bytes=cleanup['removed_bytes']))
        print(json.dumps(rows[-1]),flush=True)
    # Explicit fault fixture: existing valid stock vectors, body initially corrupt.
    # No claim that vector-last makes such a partial image unbootable.
    case=output/'valid-vectors';case.mkdir(mode=0o700)
    before=bytearray((capture/'mram.bin').read_bytes());main=PRIVATE/'simulator/sustained-render-guard-native-01/stock24/main.bin'
    before[0x38000:0x38010]=main.read_bytes()[:16];initial=case/'initial-mram.bin';initial.write_bytes(before)
    (case/'fixture.json').write_text(json.dumps(dict(initial_sha256=sha(before),base_capture=str(capture),change='Stock main first16 bytes retained; rest of main deliberately corrupt. All metadata/boot unchanged.',hardware_accessed=False),indent=2)+'\n')
    prepare_capture(PRIVATE/'recovery/private-boot-24-candidate-01',case/'capture',(capture/'payload.bin').read_bytes(),full_main_restore=True,mram_before=initial)
    r=run_case(case/'capture',case/'writer',interrupt_after_words=68)
    b=reboot(case/'writer',case/'boot','interrupted-valid-vectors')
    cleanup=retire_writer_duplicates(case/'writer',case/'capture',initial,68)
    rows.append(dict(case='retained-valid-vectors',cut_words=68,writer_passed=r['passed'],boot_passed=b['passed'],boot_classification=b['classification'],main=b['main'],handoff=b['handoff'],cleanup_bytes=cleanup['removed_bytes']))
    result=dict(passed=all(x['writer_passed'] and x['boot_passed'] for x in rows),cases=rows,
                hardware_accessed=False,rom_programming_modeled=True,scope='Declared atomic-word virtual cuts plus fresh bootloader reset; not physical power-loss behavior, same-board recovery, or proof that every interrupted update is safe')
    (output/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('restore',type=Path);p.add_argument('output',type=Path);a=p.parse_args();run(a.restore,a.output)
if __name__=='__main__':main()
