"""Replay WEL, fixed status and reset cases with configuration unknown by default."""
import verify_mspi1_sampling_regressions as replay
replay.CASES=[('mspi1-write-enable-unit-03','BLACKWALL_WREN_UNIT',36),('mspi1-status-busy-unit-01','BLACKWALL_STATUS_BYTE',22),('mspi1-pio-unit-05','BLACKWALL_MSPI1_PIO_UNIT',26)]
if __name__=='__main__':replay.main()
