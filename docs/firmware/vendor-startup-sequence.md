# Vendor Initialization Bundle and Stock/Faceclaw Feature Differences

bw-0288. Original reset runs for stock 2.4, stock 2.3, and Faceclaw38 were connected to a virtual controller, confirming transmission/reception of `fc43 → fff2 → fcc4` through preparation of the next command. Overall completion remains 13/29=44.8%. This is not full boot, integrated display, or physical BLE success.

## Original contract and CFW difference

The `fff2` constructor sets the first six bytes of a feature global and transmits eight bytes. It does not change the remaining two bytes. Original ARM tests with two existing tails confirmed preservation; the tail in the currently verified main snapshot is 00/00.

| Image | Eight bytes prepared by actual original host |
| --- | --- |
| Stock 2.4/stock 2.3 | `ff7c010fb8190000` |
| Faceclaw38 | `ff7d010fb8190000` |

Faceclaw adds only byte 1 bit 0. Pinned g2flash [patch_compress.py](https://github.com/jimrandomh/g2flash/blob/845f665e0dfdcfd06b7d3a294388de6f17a5bd59/patches/patch_compress.py#L83) describes this as exposing LE 2M in Set Local Feature. `7c205070` at stock 2.3 `4c9b3c` was directly compared with `7d205070` in Faceclaw. This difference was confirmed in original-function tests and strict packet acceptance in natural main. Actual PHY negotiation, 2M connection, and throughput were not verified. Upstream comments on 2.2.9 hardware are not imported as physical verification of these two versions.

Here `fff2` is an HCI vendor opcode, not the GATT characteristic UUID of the same value. Referenced upstream commit is `845f665e0dfdcfd06b7d3a294388de6f17a5bd59`, license GPL-3.0; patch source and LICENSE SHAs are recorded in private source notes. The entire upstream project was not copied.

The `fcc4` constructor prepares a command only when the signed input byte is −27..+6. All 256 byte inputs were checked using original ARM for each image. Current natural main requests +6. Manufacturer index defines this as EMSRC Set RF Power and specifies three response bytes: status, maximum, actual. See [manufacturer datasheet](https://www.emmicroelectronic.com/sites/default/files/products/datasheets/9305-DS.pdf). Thus the H4 Command Complete fixture is nine bytes. Maximum/actual output 6/6 are explicit virtual values, not actual chip maximum output or measurements.

## Virtual model and unit verification

Optional `vendorStartupHex` was added to `renode-em9305-reset.cs`. Default null retains existing behavior. Only after successful version and Reset scenarios does it allow the following 27-byte bundle:

- `fc43`: four-byte header + six-byte explicit address. All-zero addresses are rejected.
- `fff2`: four-byte header + one explicitly selected eight-byte stock/CFW mask above.
- `fcc4`: four-byte header + output 6 confirmed in current original code.

Arbitrary opcodes, other features, unreviewed outputs, order, and lengths are not allowed. A command is accepted only after the exact complete payload and CS rising are observed. Responses also respect IOM completion and CS release order. Vendor reply lengths are fixed at 7/7/9 bytes; the next command is unsupported. Application GPIO responds only in explicit consumed/reply-ready/drained states.

This is a virtual controller fixture advancing the Apollo host, not a model reproducing EM9305 original code, physical RF, CPU reset, or address persistence. In particular controller reboot/persistence for `fc43` remains unconfirmed; this fixture assumes no additional controller reboot. It is not used as hardware installation or command-transmission safety evidence.

Final unit verification has 123 default-capacity conditions, 217 two-byte-split conditions, and 58 existing default-configuration conditions. Initial red was a missing new constructor argument. Checks cover constructor rejection, incorrect payload, partial commit, reply length, next-command blocking, no automatic reset rearming, and frame counts.

## Natural main results and prediction correction

From original reset, all three images showed command/reply 6/6, CS frames 15, IOM commands 30, three vendor acceptances, and four application drains. Address, feature, and power commands each consumed virtual responses; ring state became:

`write offset1300, read offset1040, used260, capacity2080, stride260`

The next actual record is length 12, header `01 01 0c 08`. R8=12, R9=0, R10=actual packet pointer and SRAM bytes were compared. This opcode is HCI Set Event Mask, per [Bluetooth Core 6.1 §7.3.1](https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core-61/out/en/host-controller-interface/host-controller-interface-functional-specification.html). Execution stopped on an unsupported GPIO query for the next transfer, so this command itself had not yet been transmitted. Original write-ready PC is 2.4 `501676`, 2.3/Faceclaw `549fce`.

The first 2.4 plan expected frames 13/IOM 26, but capacity 9 split length-10/12 commands into two frames each, yielding actual 15/30. Execution passed but those two semantic checks failed; the raw report was preserved. Source and unit transfers were checked and a separate reviewed plan/saved audit used for judgment, without rerunning CPU. Correct 15/30 contract was applied to the other two images afterward. Unit tests also added normal/split frame-total checks.

Feature-off stock 2.4 control exactly matched existing CPU, instruction count, events, and boundary, with command/reply 3/3, frames 7, IOM 14. Pending `fc43` and subsequent transmission/reception and preparation of next `0c01` did not proceed.

## Tools, evidence, and next work

`prepare_vendor_startup_candidate.py` pins commands from verified software contracts and SRAM and writes plans **only inside the private simulator**. Addresses are not copied into Git docs/code. Simulator inside Git or output outside private scope is rejected before reading source. An initial implementation issue where a hash-helper import pulled in Unicorn was removed using stdlib hashlib.

Preserved outside Git in simulator:

- `vendor-startup-source-01`, `-02`: 777 original conditions and pinned-dependency reanalysis match. Constructor/range checks are Unicorn M7 with synthetic entry/register/stack, distinct from natural main.
- `vendor-startup-unit-03`, `-04`, `vendor-startup-legacy-01`: 123/217/58 conditions.
- `vendor-startup-main-01/{stock24,stock23,cfw}`, `vendor-startup-control-01/stock24`: four native runs, including preserved initial 2.4 semantic failure.
- `vendor-startup-saved-audit-01`: four saved audits.
- `vendor-startup-contract-01`, `-02`, `vendor-startup-verification-01/manifest.json`: identical results, pins for 33 Python files, four models, upstream source/license, and evidence SHAs.

IOM/keyDB/marker models and web gate were unchanged. Next investigate the standard HCI initialization contract after Set Event Mask as a group and connect natural app loop/display initialization and original glyph/GPU calls. No glasses/case access or firmware installation occurred.
