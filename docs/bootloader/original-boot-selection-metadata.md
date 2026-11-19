# Original boot manager's OTA marker read

BW537 directly decoded original 2.4 function 42e57c. At PC 42e582 it reads word 7fe000 from r0 and returns 1 only if it equals 55555555, otherwise 0. The upstream private 2.4 port also uses ORIGINAL_FLAG Thumb address 42e57d. This does not claim the metadata word is included in the boot image component.

Existing KeyDbSlotStorage already connects OtaMarkerRead, and the cleared profile provides ffffffff. The existing model also skips MRAM programming when main's startup clear request already has that value. Rather than create a new data region, optional BootReadPc and BootReads were added to OtaMarkerRead. Boot consumption is permitted only at verified 42e582 with r0=7fe000 and address=7fe000. Existing startup/setter consumption and address/width/write guards remain.

This consistently supplies the existing synthetic clear state to boot; it does not mean a physical G2 marker was read or this persistent word extracted from an official bundle. Pending/unknown are distinguished rather than assumed normal.

## Verification

- `private:simulator/boot-marker-source-bw537-01/source-proof.json`: original SHA, literal/comparison, and port binding.
- Same folder `change-proof.json`: existing marker component change, no writes permitted.
- `private:simulator/boot-marker-red-bw537-01/report.json`: reproduced previous model rejecting boot caller.
- `private:simulator/boot-marker-green-bw537-01/report.json`: 20 checks passed including clear/pending/unknown, boot PC/r0/address, main/setter preservation, and width/write blocking. This is a pure C# contract test, distinct from original ARM execution.

The current native candidate checks original boot selection/handoff/main with the same ten-second/host 300-second profile. Completed-frame stop requires nonuniform pixels; a simple clear frame is not judged final-screen success.

## Original selection path and cleanup

The original read marker ffffffff once and selected the no-update branch. UART logged GO TO APP, app SP 2007fb00, and reset 5fbe3f at vector 438000. After 51,815,298 original instructions/5.1816 virtual seconds, it stopped at PC 41ba1a writing MCUPERFREQ 40021000=15. This is a pre-handoff LP-mode request; the existing model supports only HP requests. Code/system protection and CFSR/HFSR errors were 0; handoff/main/frame were not yet reached. Offline image SHA pinning is distinct from boot's original selection behavior; this log is not interpreted as cryptographic image verification.

Authoritative record: `private:simulator/original-boot-marker-native-bw537-01/frontier-proof.json`. An identical 149773-byte boot dump was verified and cleaned up, and owned Docker removal for three runs confirmed. Source/model/actual logs/hashes/reproduction commands remain.
