# Optional Dependency Isolation for the Shared Runtime CLI

bw-0431. One package import in `font_wrapper_contract.py` was moved into its actual consumer, `direct_call_candidates()`. The communication runner's help and default Thumb decoder no longer import an optional package parser. Branch analysis that needs it continues to use the same parser. The package parser, firmware, device models, and execution scenarios were not changed.

## Confirmed cause and change scope

The shared runtime imports `inspect_ambiq_target.decode`, which uses the font wrapper's BASE/discovery helpers. The old eager import also read `blackwall_package.branch_target`, which was not used at that point. At task start that source was a macOS dataless file. A previously used auxiliary wrapper preloaded a verified module from a private path.

When an import finder in a fresh Python process blocked lookup of the optional package, three import checks—help, decoder, and branch analysis—all failed with the old code. After the change, help and decoder work; the dependency is required only when actual branch analysis is called. The parser name was not simply deleted or replaced with a new implementation. Saved before/after source differs only in import location. No other repository module was found using that name as a public re-export from the font wrapper.

A later broader `rg` search materialized the dataless file locally. Its source SHA-256 then matched the previously verified copy `0e68e622…`. The file was not overwritten. The effect is verified by fresh-process import blocking independent of actual availability, not by claiming the file remains absent.

## Actual command and saved assessment

Help was checked without the auxiliary wrapper:

```sh
<private-python> tools/run_runtime_connection_m55.py --help
```

Existing stock and registered-candidate `stock24` captures were reaudited directly with the CLI. Stock passed 25 checks and candidate 28; values and bytes exactly matched existing verification JSON. No new ARM run or model change occurred. The first audit path mistakenly pointed at the case's parent folder and failed because the profile was missing; that failure was retained, then the correct `stock24` path was used.

Actual branch analysis also decoded a synthetic BL using existing package source of known hash and recovered the original target. This separately verifies the analysis path requiring the dependency; it does not mean the shared CLI needs the auxiliary wrapper.

Three public regressions, the same three on a frozen copy, two font-wrapper checks for the three existing originals, and 14 progress-management checks passed. Material, before/after source, and failure logs are retained in private `runtime-cli-import-isolation-research-01`. This covers help/decoder dependency isolation and preservation of existing assessments; it is not completion evidence for full new-environment setup, frames, or shared scenario/comparison orchestration.

## Next work

Reuse `run_runtime_connection_m55.py` and `compare_runtime_firmware.py` to connect candidate execution or saved audit and baseline comparison in one command. Keep candidate execution assessment and comparison assessment separate; do not turn a candidate failure into success because the regression was expected. Do not rerun the same baseline unnecessarily.

E15/E16 remain partial and overall progress remains 8/16 = 50.0%. No physical-device access, writes, subagent, or external publication occurred.
