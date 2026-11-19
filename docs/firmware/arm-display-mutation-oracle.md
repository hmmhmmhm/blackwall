# Actual ARM display test mutation and independent pixel expectation

bw-0435. A newly registered stock 2.4-based candidate executed an **actual ARM test mutation changing nine white dots to black** in the original UI and render tasks. Display records were not edited afterward, and results were not copied into the GPU model. Virtual phone communication and app/RTC behavior were also preserved on the same image. This is an emulator verification fixture, not Blackwall user feature development or physical CFW installation.

## Code change and standalone ARM verification

The unique color adapter and actual BL target were decoded from the fixed stock main SHA256 `df8cfddf…`. The adapter extracts three bytes and alpha from the input color word and calls a four-instruction packer. The packer consists only of three ORRs and BX LR, with no MMIO, OS, or memory access.

The original global packer was preserved. LLVM 21 appended a 14-byte copy of the packer to the end of main, changing only the last ORR to an alpha shift. The adapter's four-byte BL was connected to this copy. The generated machine code length, instructions, and BL destination were decoded again; reset vector/SP and all other original prefix bytes matched. Opcodes were not guessed manually and hardware-check branches were not bypassed.

Candidate SHA256 is `786caf868ff7d8b831ac7112ba5e6bc2db62890ac97e7aa728d50740558cb6ed`. It was registered through the existing raw-main registry and display anchor checks. This does not mean general support for a new ABI; it is a fixture compatible with the current observation and caller anchors.

The actual original and candidate adapters were executed on an auxiliary Unicorn M7 with 24 color/alpha inputs. Original return values matched the source byte order, and candidate returns matched `alpha << 24`. The remaining general registers, flags, SP, and entire WORK memory matched between runs. There were no hooks, callee stubs, or MMIO maps. This standalone function verification is separate from the M55 main run below.

The first colored-input check failed because it expected the original adapter to preserve the input word's RGB order. The expectation was corrected after checking the actual loads `r2=[sp]`, `r1=[sp+1]`, `r0=[sp+2]` and ORRs. This failure occurred before registration and native execution; the source, binary, and mistaken expectation from that attempt were retained separately. It was not resolved by pixel manipulation in test code or a GPU change.

## Expectations fixed before execution

On the existing functional model's initially black L8 surface, zero RGB for every submitted color leaves only black draws. Alpha and geometry are preserved, so the expected surface is **all zero across 165,888 bytes at 576×288**. The expected file and SHA256 were created and fixed before candidate M55 execution.

For final SRAM, a strict hypothesis set only the known surface region in the stock capture to zero and preserved the remainder. Intermediate color could remain in the command buffer or inactive stack, so this hypothesis was not guaranteed to pass before execution. No policy was added to change the expected hash after execution or hide failure. The complete event record at declared observation points and complete SRAM at initial/UI/display points were also required to match stock.

## Actual M55 results

The new candidate ran from main reset with the same model, board, synthetic API inputs, observer, and GPU profile. The existing UI diagnostic API caller was retained; the run was not presented as natural GAF initialization or complete main execution. Execution inputs matched the stock baseline except for candidate main and its verified memory length.

| Check | Result |
|---|---|
| Candidate display execution contract | 20 checks passed |
| Actual guest surface | All zero, matching the pre-execution pixel SHA |
| Display difference | Only the original 684 white pixels changed 255→0; nine white dots disappeared |
| Final SRAM difference | Only the same 684 bytes changed, matching the predicted full SRAM SHA |
| Initial/UI/display SRAM snapshots | Byte-identical to stock |
| Events, hit counts, and samples at declared observation points | Values match stock |
| Original UI/display/renderer tasks and stacks | Checks passed |
| Model, input, or caller differences | None |

Matching final full SRAM values does not mean there were no intermediate writes. Complete transient color changes in commands and stack were not traced. A full PC trace was not collected either, and the candidate packer's call destination intentionally differs.

Comparing this actual capture again against normal stock expectations causes `expected_surface` and `expected_final_sram` to fail with exit 1. Comparing against the intended-change expectations fixed before execution passes both with exit 0. Both use the same actual guest result. Unlike the synthetic artifact control in bw434, this pixel change resulted from execution of an actual registered ARM image.

## Input and communication preserved with the same candidate

The candidate with the same SHA ran from main reset in a separate same-model scenario, confirming virtual phone GPIO/HCI/ATT input→original BLE/app task→RTC commit. The candidate's 28 checks and comparison against the existing stock baseline passed. Device input without a PC seed, original tasks/stacks, app state and queue, and RTC date were preserved. Initial, immediately post-connection, and final SRAM and communication observations also matched stock.

There were two new M55 runs: one display and one communication preservation. Existing material was reused for the original baseline. All 29 integrated audit checks passed, and actual surface PNGs with original on the left and candidate on the right were directly inspected. Public runner, comparator, and GPU model sources have not changed since bw434. Unit checks on the same source were not repeated merely to increase the count.

## Remaining scope and preserved material

The current native mutation covers one stock24 family. It does not establish verification of new test candidates in the stock23/Faceclaw families. Next, check unverified combinations in the E15 original-family/new-candidate scenario matrix against the same criteria. Natural GAF computation, final GPU packing, the entire UI, and continuous display remain incomplete. E09/E15/E16 remain partial, and the total remains 8/16=50.0%.

Material is kept outside Git in `simulator/arm-display-mutation-research-01/`: `build-fixture.py`, original interpretation and compiler/linker material, 24 standalone ARM cases, registration snapshot, pre-execution expectations and provenance, two native runs and comparisons, detection of the actual difference under normal expectations, `verify.py`, PNGs, and a hash manifest. The failed initial byte-order expectation was isolated separately. Proprietary main is not committed to Git.

There was no physical access, flash/OTA, persistent write, subagent, or external posting.
