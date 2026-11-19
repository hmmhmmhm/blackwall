"""Replay disabled CQ init and current WRDI with full flags unknown by default."""
import verify_mspi1_sampling_regressions as replay
replay.CASES=[('mspi1-cq-init-unit-02','BLACKWALL_MSPI1_CQ_INIT_UNIT',33),('mspi1-write-disable-unit-02','BLACKWALL_WRDI_UNIT',23)]
if __name__=='__main__':replay.main()
