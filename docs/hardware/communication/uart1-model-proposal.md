# UART1 model and reuse scope

Status: source investigation and existing runtime PL011 TX probe complete. Full boot, display, and physical UART verification remain incomplete.

## Choice

Connect UART1 within the already approved Renode-based simulator development scope. Three alternatives were compared. Mapping existing PL011 unchanged risks silently handling Ambiq-specific bits, DMA, ID, and unsupported offsets. Reusing PL011's TX/configuration engine through a verification adapter reduces duplication and strictly blocks unsupported behavior. A full custom UART implementation may be needed for long-term extension, but there is currently no reason to rewrite the verified core. Therefore choose an adapter limited to the source-supported polling TX subset. This does not expand authorization to hardware access, a new platform, or external distribution.

## Evidence

UART source at pinned HAL commit 61b293a was compared with the official DFP SVD. UART1 base 4003a000 reuses the UART0 type. Sixteen register offsets were compile-checked against a current Mac LLVM 21 C struct, and 104 field masks matched the pinned header. PWRCTRL.DEVPWREN/STATUS UART1 mask is 400. HAL FIFO depth is 32.

[Renode 1.17.0 source](https://github.com/renode/renode-infrastructure/tree/066a7f13c052215632d469c995c89aea37c573b1/src/Emulator/Peripherals/Peripherals/UART) PL011 and UARTBase were checked. Byte-identical assembly between that source and the execution image was not proved. A pinned runtime probe observed CR 300/FR 90, vendor-bit readback, and TX bytes BW\n. Detailed source/hash/probe evidence is in private uart1-research-01.

Ambiq CR clock 3..6, TXBUSY bit 8, TXCMP interrupt 0, and DMA extensions differ from PL011. SVD FR reset 0 is also distinct from PL011's empty FIFO 90. The model explicitly assumes idle-empty/instant-TX; it does not claim actual reset or timing.

## Implementation contract

`--uart1-model active|stuck-off` is added to existing GPU/ADC power profiles. It composes only request/status bit 400 and blocks unknown bits or simultaneous multi-domain changes. Existing masks and default unselected behavior remain. Actual rail/clock latency is unverified. UART MMIO is allowed only with power on; a high guard references a single adapter owned low. Existing strict bus mapping remains; permissive PL011 unknown offset/ID handling is not used to bypass it.

Only polling TX and basic configuration are allowed. Eight-bit TX requires CLKSEL=HFRC24 (code 1)/CLKEN/UARTEN/TXE and retains at most 4096 bytes in private capture. Virtual 24 MHz and instantaneous TX/FIFO-empty assumptions differ from actual baud/frame timing. RX data, IRDA/loopback/flow control, nonzero interrupt enable, DMA, and vendor ID are blocked. IEC accepts defined clear requests but forwards only implemented core causes. No actual RX/DMA/TXCMP events are generated. Whether UART1 is a log or another binary link remains undecided until actual main bytes are observed.

## Execution verification and diagnostic correction

The 44 checks in `uart1-unit-02` covered synthetic-state polling TX, blocking, capture limit, power responses, and seven baud inputs. The 14 checks in `uart1-shared-bank-02` called actual fixture GPU/ADC/UART shared branches to verify rejection of unknown bits and simultaneous multiple changes, state/counter preservation, preservation of other domains on a single cancellation, and high-owner and byte-width blocking. These were directly seeded states, not a substitute for full firmware initialization.

The pinned runtime PL011 baud diagnostic discarded the fractional divider. For example, IBRD 13/FBRD 1 returned 115384. Division by zero raised in initial independent review was not reproduced in actual execution. The first reproduction script failed serializing System.UInt32 to JSON; after int conversion seven inputs were observed. Original failure logs and observations are retained separately in private uart1-baud-red-01 and uart1-baud-observation-01. The diagnostic was corrected to integer expression 96,000,000/(64×IBRD+FBRD). A zero divisor yields 0; this does not implement physical baud or time-based transmission.

Active main 3 (stock 2.4/2.3/Faceclaw) in the pre-baud-fix source snapshot ran through UART1 power on and CR 0→8, with TX 0 bytes. All stopped writing 10000 to D2ASPARE (400201b0). Stuck-off attempted UART MMIO and the model blocked it; this does not mean firmware safe fallback succeeded. With UART unselected, execution stops at existing power request 40021004=400. Private uart1-verification-01 contains results for this earlier snapshot; do not mix them with post-fix main results.
