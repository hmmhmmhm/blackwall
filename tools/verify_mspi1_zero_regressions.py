"""Replay unchanged ideal/fixed sampling and RDID fixtures with zero-turnaround support."""
import verify_mspi1_sampling_regressions as replay
replay.CASES=[('mspi1-sampling-unit-02','BLACKWALL_MSPI1_SAMPLING_UNIT',51),('mspi1-sampling-fixed-01','BLACKWALL_MSPI1_SAMPLING_UNIT',33),('mspi1-rdid-unit-02','BLACKWALL_MSPI1_RDID_UNIT',30)]
if __name__=='__main__':replay.main()
