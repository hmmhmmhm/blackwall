# Boot self-restoration lifetime verification plan

2026-11-17 · bw-0567 · BV11 follow-up. Current 7/12=58.3%; the overall denominator is unchanged. No physical writes, Astra, new CFW features, or external publication.

- [x] Check pinned Renode execution-code cache with synthetic M55 caller/callee. If emulator translation cache continues executing overwritten code, the result cannot be interpreted as recovery success. Distinguish explicit cache-invalidation controls from unverified physical I-cache.
- [x] Preserve existing main/default write permissions, allowing only boot experiment options for fixed prefix 410000/149776 bytes, tail 434910/9968 bytes, and full 410000/159744 bytes. First test option mixing, alignment/address/range, and forbidden writes.
- [x] Define a known **entire synthetic virtual pre-modification MRAM**. Tail 0 outside stock boot's 149773 bytes applies only to this virtual state and is not inferred as an actual device's original tail. Preserve existing actually restored main/metadata and lineage.
- [x] Restore stock boot prefix with the original compiled RAM writer and check ACK/readback, changed range, and subsequent callback/context return. If successful, check a new boot reset→main from the actual result, but do not call it full stock while append remains.
- [x] Use the same writer for complete boot footprint or remaining tail restoration. Collect actual CPU attempts, code bytes, UART progress, and MRAM prefix before/after overwriting resident callback/return code. Distinguish unsupported cache boundary, CPU fault, timeout, and program completion.
- [x] Compare results against all modified-component hashes and natural reboot. If full restoration/reboot falls short, retain BV11 incomplete. Do not implement a new RAM-independent recovery payload and turn the goal into CFW feature development.
- [x] Record pinned source/log/hash/state and actual restoration limits in docs. Clean duplicate inputs/dumps/native containers after completion, preserving reproduction commands.

Final: [results](boot-self-restore-results.md). Three code-cache controls, C# range 60, host 30, existing ARM regression 4, three boot-writer runs, three new resets, and independent 80-check audit passed. Full stock itself failed, so BV11 remains partial and overall 7/12. Duplicate 101227347 bytes were cleaned up and termination of 19 owned natives confirmed.
