# Extending the original boot execution budget

Status: bw533 in progress. The goal is continuous original bootloader→main→display integration; executing a long delay loop alone does not complete it.

The previous HFADJ candidate ran 2.009 virtual seconds/20,092,252 instructions with guard/fault 0. Original delay function was entered 2027 times and returned 2026; budget ended in the last original count 4166642 loop. This is not conclusively an infinite hang or failure.

This run retains the same stock 2.4 boot/main, C# model, board, observation points, and 10 MIPS, changing only run.py's virtual execution limit from two to ten seconds. Host 120-second and Docker 300-second limits remain. Counters, PC, branches, returns, and device phases are unchanged. Input SHAs and change comparison are retained in `private:simulator/original-boot-ten-second-native-bw533-01/plan.json`.

This is virtual time measured in Renode's 10 MIPS functional model, not evidence of physical G2 boot time or cycle accuracy. The event ring retains only 128 entries, while total hit count/first sequence per observation point are recorded separately. The complete order of unsaved individual events is not claimed.

## bw533 result

On the same model/board, execution ended after 39,954,475 instructions/3.9955 virtual seconds at an MSPI1 power-off strict boundary, not the ten-second limit. PC 41c222 is the original write changing shared request 8400→400; XOR 8000 was compared with MSPI1 mask 8000 and on state. UART1 request 400 remains. All prior delays returned, with 9247 entries and returns each. Memory/system protection and CFSR/HFSR errors 0; boot manager/handoff/main/frame not reached.

Authoritative record: `private:simulator/original-boot-ten-second-native-bw533-01/frontier-proof.json`. Boot-manager observation address 42e650 was also checked against current 2.4 original push/sub prologue and 42e666 BL flag call; non-arrival was not attributed to an address error. Next compare actual MSPI1 registers/queue/transfer state and CanShutdown conditions.

An identical 149773-byte boot dump was verified and cleaned up, and owned Docker removal confirmed. Actual logs/original SHA/model/commands/analysis remain.
