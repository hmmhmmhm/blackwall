# Explicit controller information profiles and natural main consumption

bw-0291. Four information responses were connected to the virtual peer based on the original buffer-consumption contract. Natural mains of stock 2.4, stock 2.3, and Faceclaw38 prepared a `202a` query after cumulative command/reply 14/14. Overall 13/29=44.8%, full boot, and integrated display remain incomplete.

## Selected mock data

| Query | H4 response length | Supplied data |
| --- | ---: | --- |
| `2002` LE buffer | 10 | Length 27 / packet count 4 or length 251 / packet count 8 |
| `201c` supported states | 15 | `ff01000000000000` |
| `200f` Filter Accept List size | 8 | 4 |
| `2003` LE local features | 15 | Same eight bytes as the previously specified vendor feature mask |

Responses contain normal status and explicit data. Format follows Bluetooth SIG command definitions: [Core 6.1 §7.8.2, §7.8.27, §7.8.14, §7.8.3](https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core-61/out/en/host-controller-interface/host-controller-interface-functional-specification.html). These are not actual EM9305 information or measurements. Distinguish source-supported packet format from selected virtual capabilities. Feature-mask equality is a virtual-controller consistency assumption, not evidence that the actual chip supports the entire requested mask.

Only `le-basic-27x4` and `le-large-251x8` profiles are allowed. The numbers name buffer length and packet count, not chip version or performance class. Remaining state, list, and feature assumptions also apply as shown in the table. Actual ACL transmission, fragmentation, and credit decrement for LE buffers were not verified here.

## Model and boundary

Optional `controllerInformationProfile` was added to `renode-em9305-reset.cs`. Default null retains previous behavior. Explicit vendor/address and standard initialization scenarios must precede it. Unknown or empty names, arbitrary 0/0 profiles, and activation without prior standard initialization are rejected.

Only the exact four commands and 10/15/8/15-byte replies are supplied. No success response is fabricated for unreviewed commands. Command acceptance and reply consumption wait until CS release; invalid payload or receive length is rejected before state changes. Vendor 3 and standard 4 records remain separate from information commands. Reset does not automatically rearm the scenario.

Lengths and data were pinned to avoid turning the command-specific return-data shortage found in bw290 into a normal fixture. This does not mean a length check was added to original firmware. Original firmware bytes, branches, and returns were unchanged.

## Original functions and natural main results

First, both profiles passed original pop → parser → upper handler in each image. Six profiles and 24 assumed completion events total are synthetic Unicorn M7 call tests. Original buffer-length getter, two RAM packet-count copies, eight-byte state, list size, and eight-byte features were directly compared. The next `01 2a 20 00` packet was prepared.

On Renode M55, all three images ran with the basic profile and stock 2.4 additionally with the large profile. Each reached command/reply 14/14, frame 34, IOM 68, and application drain 12 from original reset. The next record length was 4 and actual packet `01 2a 20 00`. An unsupported GPIO read at original write-ready stopped execution, so that next command itself was not transmitted. PCs were 2.4 `501676`, older versions `549fce`.

Saved SRAM reflected basic length 27/packet count 4/4 and large 251/8/8. State, list size, and feature data also matched the source contract. Faceclaw's raw feature field stored selected mock `ff7d...`. This does not determine actual PHY negotiation or hardware support.

Stock 2.4 with information disabled exactly matched previous CPU, instruction count, events, and boundary: command/reply 10/10, frame 26, IOM 52, with no new information responses supplied.

## Verification scope and evidence

Final unit verification covered 234 basic-profile/capacity conditions, 396 large-profile/two-byte-split conditions, and 58 existing default conditions. Checks cover profile values and lengths, partial commit, command rejection, previous record preservation, frame totals, blocking the next command, and constructor constraints. The first red was the absence of the new argument.

`prepare_controller_information_candidate.py` checks original source/SRAM SHA then writes a new plan only inside the private simulator. Output outside private is rejected before source reads. Material retained in the simulator outside Git:

- `controller-information-source-01`, `-02`: 6/24 software results and identical pinned reanalysis.
- `controller-information-unit-03`, `-02`, `controller-information-legacy-01`: 234/396/58 conditions.
- `controller-information-main-01/{stock24,stock23,cfw}`: natural execution with basic profile.
- `controller-information-large-01/stock24`, `controller-information-control-01/stock24`: large profile and off control. Large-profile 2.3/Faceclaw native runs were not performed.
- `controller-information-saved-audit-01`: five saved audits.
- `controller-information-contract-01`, `-02`, `controller-information-verification-01/manifest.json`: identical analysis and pinned Python 40, model 4, source/unit/native/audit SHAs.

IOM/keyDB/marker and web gate match previous SHAs. No glasses/case access, flash, OTA, or persistent write occurred. Next determine what information privacy/data-length initialization after `202a` requires, bind explicit mock responses, and connect natural app loop/display initialization with original glyph/GPU paths.
