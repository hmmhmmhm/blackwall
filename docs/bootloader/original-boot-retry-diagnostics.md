# Diagnosing repeated behavior during original boot

BW535 collected UART TX, SRAM stack, and pure NOR state under a 4.2-second virtual limit using the same model, original, board, and retention connection. Host limit was 240 seconds. Only getters and SRAM reads were added after stop; CPU registers/instruction count were exact before export. CanPowerDown/SyncTime, which can advance model state, were not called.

## Observed behavior

UART1's 1110 bytes logged NOR-interface initialization, successful timing check, Flash ID C22539 and MX25U25643G recognition, QE status check, and /firmware directory creation in order. Automatic scan selected a 32-fine-step window and RxDQSDelay 14. No Flash init/ID failure message appears in this log scope. There is no basis to judge repeated MSPI power transitions as Flash initialization failure retries; they are interpreted as normal timing check/reconfiguration and filesystem initialization. This is the declared ideal-sdr functional profile's result, not a measured physical timing window.

Stop-stack candidate 42144f was compared with original 42144a BL 4176ce; this point is the logging path of check_and_create_directories. No claim is made of a complete stack unwind or that every stack word is a return address.

The run ended at virtual limit after 42,000,289 instructions/4.2000289 virtual seconds. Guard/code/system protection and CFSR/HFSR errors were 0; boot manager/handoff/main were not reached. Main/display integration goal remains 2/8 (25%).

## Material and cleanup

Authoritative record: `private:simulator/original-boot-retry-diagnostic-native-bw535-01/diagnostic-proof.json`. Actual UART log, stack, NOR state, model/image SHAs, and reproduction commands remain private. An identical 149773-byte boot dump was verified and removed, and owned Docker removal confirmed.

Next compare a board without detailed delay-function entry/return observations. Those two observations occupy most of the event ring and obscure important boot stages. Keep model, firmware, and device inputs unchanged and compare existing UART-log prefix and NOR initialization results. Observation changes can affect execution timing, so exact instruction-count identity or performance improvement is not claimed in advance.
