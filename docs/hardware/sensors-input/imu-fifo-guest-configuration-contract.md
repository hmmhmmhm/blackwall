# Original FIFO configuration contract and 32-byte path

bw472's key finding is that **the FIFO enable branch of original initialization requests 32-byte frames including ES0 and ES1, with watermark 10**. The same request and setter result were confirmed in stock 2.4, stock 2.3, and Faceclaw38. Existing 16-byte FIFO remains valid as a separate experimental profile, but cannot be applied unchanged to this stock configuration branch.

This work used isolated M7 execution of original ARM and register read/write ABI responses. It is not a new M55 board run, completed natural initialization, or physical configuration verification. Overall 10/16=62.5%, E12 partial. The production model was not changed; the next implementation sequence was corrected to match actual requests.

## Original functions and actual request

| Role | Stock 2.4 | Stock 2.3/Faceclaw |
| --- | --- | --- |
| Advanced FIFO getter | 0x5530b4 | 0x51f25c |
| Advanced FIFO setter | 0x553196 | 0x51f33e |
| Generic register read | 0x556550 | 0x5226f8 |
| Generic register write | 0x556568 | 0x522710 |
| Original BL caller of setter | 0x4c30e4 | 0x4b7a28 |

SHA256 of the 908-byte setter body was `2a308db49035e1b394707af64c01f3b0a030c65521a7dca16c5aefc1cc4559c8` in all three images. Actual advanced getter/setter field accesses and calls were checked without inferring names or ABI from the basic FIFO setter.

In the branch where the saved SRAM enable flag is 1, the original caller specifies the following. This flag shares a slot with the existing GAF configuration flag, 0x20007873 in stock 2.4. This does not mean main naturally passed GAF and reached this point.

- Gyro/accel enable 1, hires 0.
- Watermark 10 read from an actual SRAM halfword; stock 2.4 slot is 0x20077ba6.
- Mode 2 (stop-on-full), depth 7 (2 KB).
- Comparator 1 (greater-or-equal).
- ES1/ES0 enable 1, ES0 data size 9 bytes.
- Compression 0, timestamp/FSYNC configuration 0.

After the original getter reads existing values, the caller overwrites these fields. Decimation and some preserved fields depend on getter responses. Decimation 9/6 and reserved configuration-bank bits in this test are explicit response fixtures, not claimed as physical initial values or actual main captures.

Original code was executed from an intermediate caller branch to setter entry to collect configuration bytes, which were then used in a new isolated setter call. The entire original caller start/return was not reproduced. Field offsets used by this binary were verified; they are not assumed equal to C `sizeof` from compiling the latest header with default enum sizes.

## Configuration sequence and ownership

For uncompressed input, original setter transactions are:

1. Read six bytes from 0x1d (FIFO_CONFIG0..4) and decimation at 0x28.
2. Lower interface enable at 0x21 and set mode at 0x1d to bypass.
3. Write six consecutive bytes from 0x1d. Watermark low/high are the second and third bytes of this group.
4. Write decimation at 0x28.
5. Read **internal register 0xa258 (SMC_CONTROL_0)** and RMW timestamp-related bits.
6. For enabled input, write mode → interface enable → compression, and original code updates device frame size and FIFO use/compression state.
7. Original helper initializes compression baseline memory. Do not treat this helper as FIFO flush.

With caller-produced ES0/ES1 configuration, original setter directly wrote device frame size 32, FIFO used 1, and compression 0. This is not a host-specified frame size 16 as in prior tests.

FIFO_CONFIG2/0x20 is already owned by the initial flush model. A copy of the same register in a separate bank would make flush and watermark comparator see different values. The new configuration bank must share the value with this single owner. Internal 0xa258 must also reuse existing timed indirect transport; a new read cannot be made immediately ready in place of initialization.

## Test scope and limits

In 180 setter runs (three originals × modes 0/1/2 × watermarks 0/2/128/257/65535 × comparators 0/1 × timestamps 0/1), sequence, byte preservation, return 0, frame 16, and FIFO use state were checked. This is the API contract for input without ES0/ES1, not evidence that every intended physical FIFO mode is safe. In particular, 32-byte stream mode requires separate datasheet constraint checks. The actual caller requests stop-on-full.

Three original caller fragments and three setters receiving their results bring the total to 186. All three callers had the same source-owned fields and frame32 result. Register ABI read/write responses are stubs and are not mixed with existing M55 IOM/RTOS integration evidence. Keep SDK/static, isolated ARM, native main, and physical verification distinct.

The new [TDK advanced header](https://github.com/tdk-invn-oss/motion.arduino.ICM45608/blob/646f55a6ec119b59d9ebce47af660842b53e5506/src/imu/inv_imu_driver_advanced.h) was directly checked against tree blob `d9aec20d0b1d38feba2b6dcfe302f8319fe255b2` at the existing pinned commit. Its SHA256 is `394b7c61d7c6195b66515029b4511f4ac913958a30fc391b33dd785d31062a25`. ES0 is defined as a nine-byte buffer and ES1 as six bytes. What their valid data mean in G2 requires a separate consumer contract.

The current constructor threshold profile limits watermark to queue capacity, but original setter also writes 65535 to the register. The actual guest configuration model must distinguish a valid 16-bit watermark from small FIFO capacity. Do not arbitrarily replace watermarks above capacity with normal values.

Saved audit passed 37 judgments. No new Docker/M55 run, physical access, subagents, or external publication. Evidence is preserved outside Git in `simulator/imu-fifo-config-contract-01` (180 runs, new header, audit), `imu-fifo-config-caller-contract-01` (six caller/setter runs), and `imu-fifo-config-manifest.json`.

## Next implementation sequence

1. Identify offsets, valid bits, and callback meanings of original 32-byte frame parser and ES0/ES1. Distinguish virtual byte input from actual sensor/GAF computation.
2. Connect a FIFO bank matching this frame contract. Handle mode/interface, sequential watermark writes, single 0x20 owner, decimation, and existing timed 0xa258 transport together.
3. In M55 API diagnosis, verify sample consumption **after the original setter creates the frame size**. This is the criterion for removing host frame-size configuration.
4. Connect verified INT1 configuration, GPIO38, and task dispatch. Retain current gate 0 and incomplete normal GAF boundaries.

This neither discards existing raw16/threshold2 tests nor reduces the overall goal. It corrects prerequisites for remaining E12 work to match the stock firmware's actual configuration request.
