# Original ARM contract for EDMP initialization

bw-0332 identified the behavior required at bw331's next stop. **It does not claim new Renode main progress or successful internal IMU EDMP execution.** This is standalone ARM analysis connected to original main's current SRAM and call frame; the integrated stop remains the `a24f=00` write.

## Initialization sequence identified

Entry is `553ebc` for stock 2.4 and `520064` for stock 2.3 and pinned CFW. The same contract was confirmed in all three images.

1. Write three IRQ program addresses `4000,4004,4008` little-endian to `a24f..a254`, and stack address high byte `02` to `a255`.
2. Read `FIFO_SRAM_SLEEP` (`a2a7`) and set its low two bits.
3. Check that EDMP enable is off. Prepare internal SRAM service request `0118=01000000`, start address `011c=0000`, size `0120=0018`, and value `011e=00`. This requests initialization of IMU internal SRAM `0000..17ff`, not the glasses' MRAM flash.
4. Unmask INT2 on-demand and set EDMP enable and host message. After a 200 µs delay, the original waits for idle bit 1 of `a297`, then restores the mask and original enable value.
5. Decimation initialization sets three interrupt masks to `3f` and uses INT1 on-demand. After setting init/enable it performs host message, 200 µs delay, idle wait, and mask/enable restoration. Finally unmasking INT0 accelerometer and gyroscope data-ready makes `a271` `3c`. Default GAF mode `03` is written at driver structure offset `12`.

With normal explicit input there are 39 register/SRAM transactions and two idle queries. Initial bytes `00,a5,ff`, immediate idle/two waits, one read error, and already-enabled EDMP inputs were distinguished. When already enabled, upper init's IRQ/power configuration occurs first even if each service returns an error. This is not an atomic rollback function.

On a read error, init accumulates errors with status OR and continues later steps. Original upper caller `orrs → cmp → beq` takes the success branch only when accumulated error is 0. This is evidence of error handling at this call boundary, not a fail-safe guarantee for the entire application.

## Evidence and analysis limits

`tools/inspect_imu_edmp_init.py` checks capture hashes pinned in the bw331 manifest and derives init/configure from the BL target of the actual stack return. It executes internal instructions and branches of original functions, but replaces four callees—register read/write, SRAM write, and sleep—with explicit ABI stubs. Completion values are also test inputs. This standalone Thumb analysis uses Unicorn Cortex-M7 configuration and differs from emulation of Renode M55 main or the IMU's internal dedicated processor. No memory-write observer is used.

- Three images × three initial values × four profiles: 36 original wrapper conditions.
- Three images × two accumulated states × two return states: 12 actual upper caller gate conditions.
- Report and inspector artifacts from frozen-source rerun are byte-identical.
- Hash and syntax checks for 480 current Python sources. This is not a count of full functional tests.
- Eleven existing peripherals/observers match bw331 hashes. No new C# behavior or native main execution.

Two initial assumptions failed: IRQ ROM base 0 and final INT0 mask `3f`. Actual original output and TDK definitions corrected these to `4000` and `3c`. Failure logs were preserved and original binaries were not changed to match expectations.

The configure → SRAM power → memset service → decimation sequence was compared against [TDK EDMP source at the pinned commit](https://github.com/tdk-invn-oss/motion.arduino.ICM45608/blob/646f55a6ec119b59d9ebce47af660842b53e5506/src/imu/inv_imu_edmp.c). Two C/H files were rechecked against canonical Git tree blob SHAs and original license notices preserved. The public driver is not guaranteed to be the exact physical G2 version.

Proprietary ARM images and SRAM remain outside Git. Details are in `~/Library/Application Support/Blackwall/simulator/imu-edmp-init-source-05/`, frozen rerun in `imu-edmp-init-source-frozen-01/`, and verification manifest in `imu-edmp-init-verification-01/`.

## Requirements for the next model

Current `BlackwallImuEdmpQuiesce` handles only disable/idle, not new enable/on-demand services. Existing idle values must not be reused to complete both services immediately.

A follow-up implementation must validate IRQ/stack, SRAM power, and service parameters and transition to busy only on a valid host request. It must provide completion over virtual time and a missing-completion control, checking the SRAM initialization range and neighboring-byte preservation. Describe decimation as limited service-completion modeling, not execution of actual filter or sensor-fusion algorithms. Reject unsupported services, addresses, and sizes before application. Compare the disabled profile against existing CPU/full observations.

Then rerun original main to determine whether EDMP is passed and resume external ODR/FIFO and nonzero main frame/viewer paths. Overall scope v2 remains **13/29 = 44.8%**. Full boot, integrated UI, physical sensor, and device recovery remain incomplete.
