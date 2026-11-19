# Connection-complete event and GPIO117 ingress path

bw373, E13/E05. This contract research connects the [app-level time-setting final value](../../architecture/tpl-time-native-rtc-consumption.md) to actual device input. Thirty-three isolated ARM scenarios across three originals were verified. No new native run, connection creation, or model change occurred.

## Event consumed by original HCI decoder

H4 bytes for a virtual peripheral connection candidate are:

`043e1301004000010011223344556618000000c80000`

They comprise H4 type 4, LE Meta event 3e, length 19, subevent 1, status 0, handle 0040, role 1, address type 0, six explicit virtual address bytes, interval 24, latency 0, supervision timeout 200, and clock accuracy 0. These were not read from an actual controller. Handle 0041, role 0, and failure status 1 were also tested as distinct inputs.

Original H4 parser allocation/assembly and actual HCI event processor delivery to the registered callback were executed. Callback argument header, status, handle, role, address, interval/latency/timeout, clock accuracy, and zero initialization of two RPAs were compared. Split 1/2/3/21 inputs produced no callback from prefix alone and the same fields after suffix. A truncated input missing its last byte also returned without callback. Timeout was not verified.

Execution continued from the registered HCI callback through the original pointer table to immediately before actual BLX selecting the **DM connection handler**. Stack/registers were not reseeded and callback table not changed in between. DM's 144 bytes remained unchanged through this boundary.

| Target | H4 parser | HCI event processor | Registered callback | DM connection handler |
| --- | --- | --- | --- | --- |
| stock24 | 571eda | 5a3840 | 4fa030 | 4d445c |
| stock23/Faceclaw38 | 54c1d2 | 58998c | 4e6b4c | 4ce01c |

Older upper handlers had different register layout and length. The failed reuse of 2.4 call offset was retained; discovery was changed to use each unique original function prefix and actual BL. Version addresses or offsets are not forcibly accepted.

## Remaining prerequisites for connection creation

The original DM handler has a branch calling new CCB allocation after peer-address lookup→special-state lookup when status 0 and role 1. This accords with basic peripheral allocation flow in [pinned Arm Cordio dm_conn.c](https://github.com/ARMmbed/mbed-os/blob/54e8693ef4ff7e025018094f290a1d5cf380941f/connectivity/FEATURE_BLE/libraries/cordio_stack/ble-host/sources/stack/dm/dm_conn.c). Full version equivalence of public source and target firmware is not claimed.

Calling the upper handler to completion in the current standalone fixture stops at **UART1 0x4003a018 read**. DM table remains unchanged. This is a UART1 debug/log output boundary, not a claim that an existing main board with UART fails there. Logger was not disabled and UART read was not replaced with an arbitrary value. Final DM allocation/rejection for success, central, and failure-status inputs is not reported as verified. Connection, ATT admission, and security remain incomplete.

## Original GPIO117→WSF notification

Pinned Apollo510 SVD assigns GPIO0_607F IRQ59. GPIO117 is group 3 bit 21, with addresses:

| Operation | Address |
| --- | --- |
| Enable | 40010560 |
| Pending/status | 40010564 |
| Clear | 40010568 |
| Software set | 4001056c |

GPIO enable word 3 in existing three-original powersave captures is 2097152, with bit 21 set. Those reports were verified by existing manifest hashes. SVD was also checked against its pinned SHA.

The IRQ59 handler in the original vector table calls GPIO dispatcher, whose actual SRAM callback/parameter table points to the function registered on pin117. In standalone ARM, supplying IRQ59 and bit 21 to the original dispatcher caused the registered callback to increment interrupt counter by 1, call original `WsfSetEvent(handlerId,1)`, and return normally. Actual callbacks, handler IDs, and counter addresses per source are in the report. This did not generate an actual IRQ.

Current `BlackwallGpioInterruptIdle` only stores enable and records clear, always returning status 0. It generates no IRQ output. The EM9305 peer also has no unsolicited runtime event queue after startup completion and has ready 0. Therefore adding event bytes alone will not make the receive task operate.

## Next implementation unit and exit criteria

Keep existing peer and GPIO ownership while connecting an optional runtime path:

1. Enqueue one explicit connection-complete event only after startup complete with CS high. Reject incomplete startup, in-transfer, duplicate enqueue, and unsupported events. Define ownership and retry state after reset/abort.
2. Connect pending-event ready-high to existing GPIO117 read path, generating GPIO pending bit 21 and IRQ59 after checking actual configuration/enable. Original ISR clear must lower IRQ and agree with byte consumption/CS commit. Host must not directly write NVIC pending or task flags.
3. Natively verify original SPI read/H4/HCI/WSF/DM path consumes the event. Observe new CCB/handle lookup and additional controller commands required. Do not arbitrarily ACK unsupported commands.
4. Determine if this path can execute before the natural GAF barrier. If not, transition to E05 normal service. If possible, supply ATT time-setting message in the same run and connect to bw372's final value. Pin device role, failure controls, and time limits before execution.

This research is not evidence of completing that implementation or a normal connection. Overall 4/16=25.0%, API 3/6, and existing acceptance remain.

## Verification material

Each of three originals had event/callback 8, truncation 1, UART boundary 1, and GPIO callback 1: 33 total. Frozen tool report matched source05 byte for byte. Arm Mbed pinned commit's hci_evt.c/h, hci_api.h, dm_conn.c, dm_conn_sm.c, and dm_api.h were obtained and Git blobs/SHA256 checked. Web reader had a cache miss; CLI download and hash verification obtained them. They informed original decoder field layout and were not copied as simulation code.

Existing 41 reports from bw369 and frozen byte identity existed, but a missing completion manifest blocked this dependency check. Existing results and six public source blobs were rechecked to complete the record; firmware was not rerun. Failures where callback scan included the next function and older-version call offset was wrong were also retained.

```sh
<private-python> tools/probe_hci_connection_ingress.py <simulator> <new-private-output>
```

Results, pinned source, GPIO contract, failure records, and frozen tool are bundled in private `simulator/hci-connection-research-01/manifest.json`. Original firmware and SRAM remain outside Git; no physical BLE/USB/UART, installation, persistent write, or external publication occurred.
