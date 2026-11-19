# NOR RDID and RX FIFO Contract

Task bw-0171. Analyzed source, manufacturer material, and saved original requests. This stage did not identify the chip installed in an actual G2 or confirm successful RX. Overall goal completion remained 13/29 (44.8%).

Page 27 of the pinned [MX25U25643G v1.1 manufacturer datasheet](https://www.macronix.com/Lists/Datasheet/Attachments/8766/MX25U25643G,%201.8V,%20256Mb,%20v1.1.pdf) describes 24-bit output for command 9F, and page 31 Table 6 specifies C2/25/39 in manufacturer/type/density order. The PDF hash reused the existing research pin. Page 31 was rendered to PNG using macOS PDFKit to check the actual table columns and values; the original, text, and PNG were preserved outside Git. This is specification evidence for a device profile, not identification of the chip fitted to G2.

Public MSPI metadata places RXFIFO at offset `14` (32 bits) and RXENTRIES at offset `1C` (six-bit word count), both with reset 0. These were also checked by M55 C offsetof compilation. The HAL reads FIFO words when RXENTRIES is nonzero and copies only the required final 1–3 bytes from a temporary word to the destination.

The 42 checks in `inspect_mspi1_rdid_contract.py` verified source pins, FIFO layout, original main, saved stop/stack, the actual RX function's word reads/entry polling/byte-copy loop, and call return points. Inputs were the three originals from existing `mspi1-xip-mixed-main-01`; they were not rerun. The 24-byte descriptor specifies length 3, RX, command 9F, and turnaround.

| Item | Stock 2.4 | Stock 2.3 / Faceclaw |
| --- | --- | --- |
| FIFO function | `4E6468` | `4D9094` |
| FIFO call return point | `4E8A5E` | `4DB68A` |
| Destination buffer | `20329B90` | `2033F970` |
| Destination word immediately before request | `40061088` | `40061088` |

Buffer addresses were compared with the saved descriptor pointer and stack range. A subsequent test with an explicit device model can observe at that return point whether the original CPU copies C2 25 39 and preserves the fourth byte 40. The host must not write the ID into RAM or change CPU return values.

The next model keeps identity profile default `none` and supplies the documented ID only for an explicit `mx25u25643g` profile. FIFO indicates one word only after three response bytes arrive and consumes it on read. Reads from an empty or incomplete FIFO are unsupported. Even if unused high bytes of the final word use model padding 0, do not treat them as extra flash data; independently verify the original's three-byte copy. Unknown flash backing, status registers, and program/erase are not supplied. The profile is neither an arbitrary ID chosen to pass firmware checks nor a physical compatibility verdict.

At this stage production models and the original execution endpoint were unchanged; there was no glasses access, flash, or persistent write. Full boot, integrated display, and physical recovery remained incomplete.
