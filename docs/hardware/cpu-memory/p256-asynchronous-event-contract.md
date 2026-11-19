# P-256 Asynchronous Responses and Original WSF Delivery Contract

bw-0294. Used three saved states where natural M55 execution had reached immediately before transmitting `2025`. This analysis calls original ARM code in Unicorn M7 with synthetic entry, stack, and registers; it is not a new natural M55 execution or physical device test.

## Response formats and test input

`2025` uses Command Status followed by a separate LE Read Local P-256 Public Key Complete event. It does not return ordinary Command Complete. Checked the search index of a [distributed SIG specification §7.8.36](https://community.renesas.com/cfs-file/__key/communityserver-discussions-components-files/297/Core_5F00_v5.2.pdf) and the [official completion event §7.7.65.8](https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core-61/out/en/host-controller-interface/host-controller-interface-functional-specification.html).

- H4 Command Status: `04 0f 04 00 01 25 20`, seven bytes total.
- H4 LE completion: `04 3e 42 08 00` + X 32 bytes + Y 32 bytes, 69 bytes total.
- X/Y use the public P-256 generator point, each little-endian. Compared the search index of [NIST's public coordinates](https://nvlpubs.nist.gov/nistpubs/legacy/sp/nistspecialpublication800-90a.pdf) and also checked the curve equation. This document was not adopted as randomness-generation guidance. No actual device key or randomness was used.

## Path confirmed in original code

Original HCI parser/handler converts LE subevent 8 into internal event `0x25`. The crypto callback removes a request from the pending queue and calls the state-2 public-key consumer. The consumer reverses the byte order of X and Y separately, 32 bytes each, stores them at request `+4` and `+0x24`, and stores status at `+3`. Both big-endian coordinates exactly matched the test input.

The request is delivered as WSF owner 1 event `0x41`. Popping the original global message queue and invoking the registered owner handler leads to owner 6 event `0x34`. Original message-free is called after each delivery to preserve message lifetime. Afterwards, a 36-byte request with header `01 17 20 20` appears in the original HCI transmit queue. This is [LE Encrypt, SIG §7.8.22](https://community.renesas.com/cfs-file/__key/communityserver-discussions-components-files/297/Core_5F00_v5.2.pdf). Payload and derived state are retained only in private evidence; cryptographic completion and subsequent persistent storage were not executed.

Call order came from original queues, callbacks, and registry. Since WSF handlers were directly called in the synthetic test, this is not evidence of natural task scheduling, interrupts, or completed app initialization.

| Scenario | Coordinates stored in request | WSF owner 1→6 | Subsequent HCI `2017` |
| --- | --- | --- | --- |
| No event | No | None | None |
| Status success only | No | None | None |
| Status error only | No | None | None |
| Status success + completion success | Yes | Confirmed | Confirmed |
| Status success + completion error/zero coordinates | Differs from test point; status 1 stored | Confirmed | Confirmed |
| Completion success without Status | Yes | Confirmed | None |
| Status success + completion wire one byte short | No | None | None |
| Incorrect ordinary Command Complete | No | None | None |

The occurrence of `2017` after error completion alone does not show that the error was ignored or normal recovery succeeded. Absence of subsequent transmission without Status may relate to original command-credit flow, but this test did not establish the detailed cause. Do not replace these conditions with arbitrary success in the virtual model.

## Provenance, verification, and constraints

- Tool: `tools/inspect_p256_event_contract.py`.
- Three images × eight conditions, 24 scenarios total. Original HCI handling and WSF pop/handler/free reached return sentinels without execution errors.
- For each image, checked all natural-capture audit file hashes and original parser/ring analysis pins.
- A simple contiguous 64-byte search also finds residual data in freed receive blocks. This was not treated as valid public-key state; actual pending-request payload and the consumer's big-endian result were compared.
- Initial exploration failed because older handler instruction layout differs and stock 2.4 relative offsets were applied unchanged. The final tool locates each original's branches, literals, and callback table to check the contract.
- Allocator prefix and payload differed by eight bytes. The final tool uses the actual pointer returned by original queue-pop.
- Final analysis is private `p256-event-source-06`; reanalysis with 44 pinned Python dependencies in `p256-event-source-07` has byte-identical reports and saved SRAM/WORK. Manifest: `p256-event-verification-01/manifest.json`. Initial exploration results were preserved.
- Four peripheral-model hashes match the preceding stage. No new native execution, device access, or web installer/recovery boot/CFW artifact change occurred.

Next implement the exact order, response counts, and RDY/CS lifetime of these two asynchronous events in an opt-in peer and connect WSF delivery and `2017` generation in natural M55 execution. Then check original consumption of AES input and exact test results while continuing the app/display path. Overall product completion remained scope v2, 13/29 = 44.8%. Normal boot, integrated display, and readiness for physical installation were not yet established.
