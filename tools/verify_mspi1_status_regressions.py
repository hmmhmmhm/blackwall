"""Replay frozen ID, zero-turnaround and NOR reset fixtures with status-byte support."""
import sys
import verify_mspi1_sampling_regressions as replay
replay.CASES=[('mspi1-rdid-unit-02','BLACKWALL_MSPI1_RDID_UNIT',30),('mspi1-zero-unit-02','BLACKWALL_ZERO_RDID',36),('mspi1-pio-unit-05','BLACKWALL_MSPI1_PIO_UNIT',26)]
if __name__=='__main__':
 if '--reset-only' in sys.argv:
  sys.argv.remove('--reset-only');replay.CASES=replay.CASES[-1:]
 replay.main()
