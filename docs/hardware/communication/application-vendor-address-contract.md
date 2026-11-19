# Original contract for public address setting and subsequent initialization

bw-0287. Investigated using saved main/SRAM and original ARM functions from three images. No new native main run, controller response-model change, or physical access occurred. Overall product completion remains 13/29=44.8%, with full boot and integrated display incomplete.

## Command identification and source limitations

Manufacturer datasheet search-index text identifies `fc43` as **EMSG Set Public Address**, with six-byte parameter and one-byte return status. [EM9305 datasheet](https://www.emmicroelectronic.com/sites/default/files/products/datasheets/EM9305-DS.pdf). The original host's actual pending packet matches `01 43 fc 06` followed by six address bytes from RAM.

Search-indexed versions 4.5.1/4.5.3 also say a completion event occurs before CPU reset. Persistence and reboot meaning of the address change are unclear, so do not classify it as merely RAM configuration or a persistent NVM write. Direct PDF opening redirected to a Swatch company page; a complete PDF was not newly obtained and verified. Search-index text is not presented as full latest-PDF review. Index versions, URL, and access limitations are in an outside-Git manufacturer source note.

Controller internal code and physical behavior were not verified. A host RAM setter does not imply controller configuration is nonpersistent. No actual command transmission occurred here.

## Original address data path

| Item | Stock 2.4 | Stock 2.3 / Faceclaw38 |
| --- | --- | --- |
| `fc43` constructor | `4dd3f6` | `4c9bb2` |
| Host RAM setter | `4dd3c0` | `4c9b7c` |
| Six-byte address global | `20076ac0` | `200773c0` |

The constructor calls original generic command function with R0=`fc43`, R1=6, and R2=the global above. Actual native next-packet parameters matched the six global bytes. Function tests with arbitrary ascending/descending six-byte inputs also preserved byte order. Actual snapshot address bytes were not copied into documentation or code; private report hashes were compared. This was not collection of the user's actual glasses address.

Executing the whole original RAM setter returns 0 and preserves the existing global for null or all-zero addresses; nonzero addresses copy six bytes into RAM global and return 1. This is host RAM setter behavior, not a test setting an actual controller address or storing it persistently.

## Completion event and next initialization dependency

An explicit function-call sequence connected original ring pop → H4 parser → upper handler (event mask 1). It used original allocator and actual SRAM without function stubs or original branch changes. This is a Unicorn M7 test using synthetic entry/register/stack, distinct from natural Renode main.

| Assumed input | Original host result |
| --- | --- |
| No event | Only existing record consumed, no new command |
| `fc43` Command Complete, status 0 | Prepares `fff2`, eight-byte parameter, record length 12 |
| Same event, status 1 | Prepares same next command |
| Event with opcode `fc44` | Prepares same next command |

As in the prior Reset stage, this control shows that progress in current state cannot be interpreted as evidence of opcode/status consistency validation. It is not a conclusion that all states behave alike or that firmware as a whole does not validate. A virtual peer must retain a boundary checking exact commands and explicit responses.

Additionally, function tests **assuming** status-0 completion for `fff2` after `fc43` prepared `fcc4` next, with one-byte parameter and record length 5. This is not evidence those commands executed or succeeded on a controller; it identifies one more initialization dependency. Detailed meaning and eight-byte composition of `fff2`, and response/side effects of `fcc4`, remain for investigation.

## Evidence and next work

`tools/inspect_application_vendor_address.py` checks per image constructor 3, RAM setter 3, completion event 4, and sequential handling of two assumed events 1: 33 conditions total. It runs after checking original main/SRAM/saved audit and prior ring/parser analysis SHAs. An initial auxiliary check confused packet start and parameter start, corrected by comparing after the four-byte header. The final checker uses the pointer in actual register context. The first CLI run's missing argument was rejected before creating files; it was run with two correct paths.

Outside-Git simulator `application-vendor-address-source-01`, `-02` results match; `application-vendor-address-verification-01/manifest.json` pins Python 30 and analysis/source-note SHAs. Four IOM/reset peer/keyDB/marker models and web source are unchanged.

Next investigate `fc43 → fff2 → fcc4` creation and response consumption as one initialization flow and connect it to a virtual scenario explicitly stating unknown controller reset/persistence assumptions. Proceed from confirmed command-specific contracts; do not auto-success unknown commands. The integrated goal of natural app loop/display initialization and original glyph/GPU calls remains.
