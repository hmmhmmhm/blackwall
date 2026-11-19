"""Offline resident ARM writer boot-prefix/tail/full restoration lifetime experiment."""
import argparse
import hashlib
import json
from pathlib import Path
from run_recovery_m55_writer import prepare_capture,run_case,ROOT
from run_original_boot_screen import PRIVATE
from check_virtual_restore import assess


def sha(data):return hashlib.sha256(data).hexdigest()


def run(output):
    output=Path(output).resolve()
    if output.exists() or not output.is_relative_to(PRIVATE) or output.is_relative_to(ROOT):raise ValueError('Fresh private output required')
    stock=(PRIVATE/'recovery/boot-2-4-analysis/boot-2.4.0.24.bin').read_bytes()
    if len(stock)!=149773 or sha(stock)!='ecb91896234392e2b98ec80b1ac3ebf4aa27726d3cbed10927edf0b44d83d665':raise ValueError('Pinned original stock24 boot required')
    parent=PRIVATE/'simulator/full-main-restore-bw564-02';initial_path=parent/'vector/exports/final-mram.bin';initial=initial_path.read_bytes();parent_report=json.loads((parent/'report.json').read_text())
    if sha(initial)!=parent_report['final_mram_sha256'] or sha(initial[0x10000:0x37000])!='5ac1b02d337b57e0d25886a06296df2d5932af1f31168c416e64b50c5417a91d' or sha(initial[0x38000:0x38000+3700068])!='df8cfddf3bd29a8351129a8364a8e0dafb347ffc7bfcbca5b52fdd973a7cce4a':raise ValueError('Actual pinned restored main/research boot snapshot required')
    backup=bytearray(initial);backup[0x10000:0x37000]=stock+bytes(159744-len(stock))
    for pc in (0x4160e8,0x416378,0x41d92c,0x41b8ec,0x41bd92,0x41bde4,0x42e84c):
        if initial[pc-0x400000:pc-0x400000+16]!=backup[pc-0x400000:pc-0x400000+16]:raise ValueError('Stock helper stub would mask changed instructions')
    output.mkdir(mode=0o700,parents=True);(output/'virtual-original-mram.bin').write_bytes(backup);(output/'runner-source.py').write_bytes(Path(__file__).read_bytes())
    (output/'manifest.json').write_text(json.dumps(dict(initial_source=str(initial_path),initial_sha256=sha(initial),virtual_original_sha256=sha(backup),modified_regions=[dict(space='mram',address=0x410000,bytes=159744)],stock_boot_bytes=149773,virtual_original_tail_bytes=9971,assumption='Original tail is explicitly zero in this synthetic virtual pre-modification snapshot; not inferred from a physical device or official bundle',stubbed_stock_helper_bytes_equal=True,hardware_accessed=False),indent=2)+'\n')
    stock_parts={'boot':sha(backup[0x10000:0x10000+149773]),'boot-tail':sha(backup[0x10000+149773:0x37000]),'main':sha(backup[0x38000:0x38000+3700068])}
    extents={'boot':dict(space='mram',address=0x410000,bytes=149773),'boot-tail':dict(space='mram',address=0x410000+149773,bytes=9971),'main':dict(space='mram',address=0x438000,bytes=3700068)}
    rows=[];candidate=PRIVATE/'recovery/private-boot-24-candidate-01'
    for name,destination,length in [('prefix',0x410000,149776),('whole',0x410000,159744),('tail-after-prefix',0x434910,9968)]:
        before_path=output/'prefix/native/exports/final-mram.bin' if name=='tail-after-prefix' else initial_path
        before=before_path.read_bytes();data=bytes(backup[destination-0x400000:destination-0x400000+length]);case=output/name
        prepare_capture(candidate,case/'capture',data,destination=destination,boot_restore=True,mram_before=before_path)
        r=run_case(case/'capture',case/'native',allow_incomplete=True)
        final=(case/'native/exports/final-mram.bin').read_bytes();written=r['observed']['programmed_bytes']
        if not 0<=written<=length or written%4:raise ValueError('Invalid observed programming prefix')
        expected=bytearray(before);expected[destination-0x400000:destination-0x400000+written]=data[:written]
        if final!=expected or sha(final)!=r['final_mram_sha256']:raise ValueError('Whole MRAM differs from observed actual word prefix')
        observed={'boot':sha(final[0x10000:0x10000+149773]),'boot-tail':sha(final[0x10000+149773:0x37000]),'main':sha(final[0x38000:0x38000+3700068])}
        restore=assess(stock_parts,observed,['boot','boot-tail','main'],True,stock_extents=extents,modified_regions=[dict(space='mram',address=0x410000,bytes=159744)])
        row=dict(case=name,programmed_bytes=written,requested_bytes=length,normal_writer_completion=r['passed'],result_seen=r['observed']['result_seen'],context_returns=r['observed']['context_returns'],host_limit_reached=r['observed']['host_limit_reached'],changed_code_fetches=r['observed']['changed_code_fetches'],first_changed_code_pc=r['observed']['first_changed_code_pc'],original_code_word=r['observed']['original_code_word'],updated_code_word=r['observed']['updated_code_word'],final_mram_sha256=sha(final),stock_boot_prefix_restored=observed['boot']==stock_parts['boot'],full_stock_bytes=restore['full_stock_bytes'],all_virtual_mram_original=final==backup,whole_mram_prefix_verified=True,restoration=restore)
        (case/'assessment.json').write_text(json.dumps(row,indent=2)+'\n');rows.append(row);print(json.dumps(row),flush=True)
        if name=='prefix' and not r['passed']:raise ValueError('Stock prefix did not complete; tail case cannot reuse its state')
    result=dict(cases=rows,hardware_accessed=False,actual_boot_rom_executed=False,same_board_uart_recovery_verified=False,physical_icache_modeled=False,scope='Actual compiled isolated ARM resident writer with declared coherent executable-IO ROM model; complete known synthetic original MRAM; not physical full-stock assurance')
    (output/'report.json').write_text(json.dumps(result,indent=2)+'\n');return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args();run(a.output)
if __name__=='__main__':main()
