# Raw IMU FIFO storage and consumption plan

bw467. This is the first unit of approved E12 device implementation. It brings the original parser/read contract to an actual buffer without generating GAF computation or a sensor-ready flag.

Rather than mixing storage logic into the existing identity peer's large initialization state machine, optional `BlackwallImuRawFifo` owns the packet queue and read leases. Later I²C integration reuses this component. Having the host calculate each read response was not selected because it lacks independent device state.

Supported profile is a 16-byte raw frame (header 0x68), maximum 2048 bytes/128 packets, with explicit byte order. Default is disabled. Two bytes of count register 0x12 snapshot packet count; FIFO data 0x14 starts only complete reads in packet multiples. Output chunks may be split within a transaction, but packets are consumed only upon successful completion of the full read. Input appended during reading does not change the reserved prefix.

This local implementation unit without a commit does not change existing peer/IOM/GPIO wiring. Physical consumption rules on partial transaction interruption are unknown, so finish, reselection, and flush before completion are rejected and reset discards the test state. Flush clears only an idle queue and preserves configuration and cumulative diagnostics. Actual device 0x20 writes and GPIO threshold connection come later.

Verification proceeds from API-absent red to native unit execution loading the C# component in actual Renode. Check defensive copies of input/return arrays, two non-consuming count reads, data order/chunking/commit, concurrent tail append, capacity and invalid header/length rejection, flush/reset/default off, and interruption boundaries. Do not report a new original ARM main run or successful FIFO bus integration.
