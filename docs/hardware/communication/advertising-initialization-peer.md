# Advertising initialization and natural M55 continuation

bw-0300. The five transactions in the [original advertising contract](address-advertising-contract.md) were connected to an optional strict peer. Original ARM mains for stock 2.4, stock 2.3, and Faceclaw38 ran from Renode M55 reset entry. No actual glasses, case, or radio were accessed.

## Model and input

The `advertisingInitializationHex` option was added to the event peer in `renode-em9305-reset.cs`. It is available only when the AES32 transaction is specified. It handles provenance-pinned `2005/2006/2008/2009/200a` requests and successful Command Complete responses in order. The address must equal the virtual startup address and use static-random format. Parameters, AD length, type, padding, and enable value are checked. Different commands, payloads, or order, or exceeding the 59-command budget, are blocked.

The GPIO reset hypothesis, IOM transfer engine, existing key DB, and OTA marker models were unchanged. The new option defaults off. Original main PC, branches, and returns were not forced and firmware bytes were not patched. This model supplies explicit virtual responses to verified host requests; it is not execution of actual EM9305 firmware or reproduction of radio behavior.

`prepare_advertising_candidate.py` checks original main, full SRAM, and previous analysis fixture hashes and creates a private plan. Address, device name, manufacturer payload, and AES test input remain outside Git. An explicit 120-second observation limit and [post-stop SRAM collection](../../research/paused-observation-snapshot.md) were used, but the guest actually stopped earlier at an unsupported request.

## Natural execution results

All three images handled **59 commands and 60 responses**, 230 SPI CS frames, and 460 IOM commands. All five advertising requests and five responses were consumed, and two existing AES32 and P256 events remained. Each added 10 bytes after existing UART1 output and four actual M55 UART1 IRQ entries.

| Image | Next stop PC | Unsupported request |
| --- | --- | --- |
| Stock 2.4 | `0x58236c` | IOM7 peer write `02 07`, length 2 |
| Stock 2.3 | `0x57b014` | Same |
| Faceclaw38 | `0x57b014` | Same |

Guard `address=0x0501` is the **existing PMIC pointer**; the rejected new payload is `02 07`. It does not mean the pointer was updated to `0x0207` or that reading that register succeeded. No arbitrary value was returned for the request. The next PMIC contract is to be investigated in the original caller and public specification.

The original candidate expected bounded idle after advertising, so the initial semantic judgment of all three runs failed. Original failure reports and plan were preserved and a separate saved audit performed against the actual strict boundary. The CPU was not rerun to overwrite failure or execution settings changed. Full SRAM was collected at actual guest stop, with PC and instruction count unchanged before/after collection.

Stock 2.3/CFW executed 73,264,795/73,087,774 instructions and observed 3,366/3,340 events respectively. Reaching the same IOM7 boundary is not presented as complete equivalence of their paths. Analysis attributing this difference to a particular Faceclaw feature has not been performed.

## Verification and preservation

- Unit checks passed: 1,245 advertising enabled, 1,138 disabled, and 3,398 split transfers with write capacity 2. Invalid command bytes, response lengths, constructor inputs, and access after budget exhaustion are rejected.
- Four native runs: three candidates and default-off control. The control exactly matched previous CPU, instruction count, events, and stop point.
- Four saved audits passed; 32 Python runner tests passed.
- Repeated saved analysis with 53 frozen Python dependencies produced byte-identical report and analyzer files.
- The initial red for missing constructor, two unit failures caused by old input remaining after a test-address change, and initial native semantic mismatch were preserved.

Pinned evidence: `private:simulator/advertising-peer-verification-01/manifest.json`. Inspector: `tools/inspect_advertising_profiles.py`. Do not expand this into verification of full boot, app loop, integrated display, actual advertising, or installability. Web installer, recovery boot, and installation CFW were not changed. Overall completion is scope v2, 13/29=44.8%.

Next investigate the IOM7 `02 07` caller, read consumption, and status selection conditions to explicitly model only the needed PMIC state, then continue original stock/CFW execution toward app and display. Device-specific hardware verification and installation approval remain separate.
