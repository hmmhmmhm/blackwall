# Public-Scope Candidates and G2 Visualization Research

2026-11-18 · bw-0586. This is a working copy created without a publication decision or external posting. Its purpose is to provide research and execution evidence useful to G2 firmware and custom developers while excluding personal information and materials without redistribution rights.

## Public candidate classification

- Materials to review first: emulator and analysis source in `tools/`; synthetic fixtures and tests; `docs/` research on boot/main, memory, display, input, BLE, sensors, and recovery; per-version comparisons, failure cases, and reproduction procedures; upstream sources and applicable notices. This classification does not mean safety or licenses have been verified for every file. Recovery protocols and research information are not categorically excluded as sensitive merely because of their subject. Clearly state physical-validation status for actual device-writing methods and distinguish them from what tools actually do.
- Default exclusions: actual device identifiers and backups, device secrets, private keys, stock/CFW firmware and boot binaries without confirmed redistribution rights, private SRAM/wire captures and actual device records, local paths, internal agent settings, and personal work logs. Exclude or separately review `local/`, `.agents/`, `AGENTS.md`, `ALIGNS.md`, `docs/data/work-log.tsv`, `docs/archive/device-inventory.md`, `docs/research/private-recovery-candidate.md`, and `tests/fixtures/original-boot-screen-observation.json`. If executable code depends on these materials, create public synthetic fixtures and a different execution path.
- Deferred: `web/` installation research, firmware-derived fixtures, material subject to upstream permissions/licenses, and user/third-party photographs. Review per-file provenance, distribution rights, and user experience. Do not redistribute original firmware or images merely because they are useful for research.

A limited regular-expression search across 1,593 untracked files found zero key/password/token assignment forms, zero private-key PEM markers, zero exact matches for specific serial/MAC values in user photos, and `<user-home>/` paths in five files. Results apply only to detected patterns and files at that time; they do not rule out obfuscated secrets, binary contents, or all leaked records. Separate checks remain for ignored files such as `*.bin`, tracked history, symlinks, image metadata, each code fixture and its context, and the final staged diff. Some token-like strings were identified as portions of identifiers or synthetic tests; they were not confirmed as real secrets. The values themselves are not included in this document.

Blackwall had no project LICENSE at the time. Renode/MIT and some source notices appear in [NOTICE](../../NOTICE.md) and `licenses/`. Select among MIT/GPL and other candidates only after checking derivation of actual published files and upstream conditions; do not automatically assume MIT-only distribution when including GPL code. This is not a formal legal opinion.

## Public hardware sources

- [Display Tech Center teardown video](https://www.youtube.com/watch?v=4C5AhvTf2fI): its public chapter list includes the frame at 11:19 and battery, antenna, and PCBA teardown at 20:32. Opening the original YouTube video was restricted during this search, so individual frames and chip markings were not verified. Also consult the [creator's analysis](https://displaytechcenter.com/2026/03/01/even-realities-g2-optical-analysis/).
- [FCC internal photos](https://fccid.io/2BFKR-G2/Internal-Photos/Internal-photos-8787893): a six-page internal-photo exhibit submitted by Even Realities is publicly indexed. Reuse rights require separate confirmation.
- [Manufacturer's G2 construction explanation](https://www.evenrealities.com/it-IT/blogs/even-insider/how-we-rebuilt-g2-from-the-inside-out): manufacturer description of processor, battery, and antenna placement in each temple and the FPC communicating across the frame. This does not establish a specific chip's location in a photo.
- Two user-supplied photos show temple-board outline, connectors, and relative component placement, but markings, both sides, and orientation are not sufficiently confirmed to identify a particular rectangle as Apollo510B or a specific IMU. Copyright and permission to publish the photos also require separate confirmation.

## Visualization proposals

A. **Board-centered interactive map:** depict left/right temples and boards close to the photos, with selectable chips and connectors. Good for understanding physical placement, but specific component locations require evidence.

B. **Communication-flow timeline:** select a scenario with execution records, such as boot, touch, display, or recovery, and replay requests and responses. Easy to connect directly to actual emulator events, but less physically evocative of the board.

C. **Recommended hybrid:** overlay stepwise flows on the board map and show time, sender → receiver, bus, and observational evidence on the right. Limit the first version to one original-screen scenario. Label devices and lines as `actually observed`, `code/source-based`, `functional model`, or `unknown`, with filters, pause, and event details. Do not animate segments without original Boot ROM execution or both-side/case behavior as actual validation. Label frames without records as illustrative estimates and do not merge them with observed events.

This was a conceptual proposal. Implement after discussing scope, evidence needed for the board, and presentation with the user. Attached photos were not uploaded externally or redistributed.

## README reference

The [DAISO MCP README](https://github.com/hmmhmmhm/daiso-mcp) uses a project name and one-line description, large hero image, key-service table, shortcuts, scenario banners, and detailed documentation links to establish hierarchy. A similar information hierarchy and original graphics were proposed for Blackwall. Do not include unverified features, fake badges, physical-safety guarantees, or unauthorized redistribution of original materials. A separate initial public README draft is in [public-readme-draft.md](public-readme-draft.md).
