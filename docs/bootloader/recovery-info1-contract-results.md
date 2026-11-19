# Recovery initialization INFO1 contract and B0 alternative research

2026-11-17 · bw-0575. Overall verification is **10/12=83.3%**; BV05/06 authentication/recovery remain incomplete. Original boot execution and pinned public source were compared without physical glasses access or installation.

## Findings

- INFO1 `0x42003370` begins the POWERSTATE0 calibration table. Saved native logs show trim 1 attempted to copy 16 words, trim 2 twenty words, to `0x20026ba4` and stopped at the first four-byte read. These match respective first request lengths in public PCM2.1/2.2. Total sparse requests are 23/28 words. This alone does not verify full binary ABI or actual calibration values.
- PCM0.7 init in public HAL commit `61b293a49db34030c545f99101f7ebf6a3050314` returns success only and makes no additional INFO1 reads. The B0 PCM0.7 branch does not register the two Tempco postpone/pending callback slots. This is a source-supported alternative, not grounds to remove original patch callback protections.
- A new Renode run of original 2.3 public current patch/same-bundle main with synthetic MCU revision `0x21`, trim 1 strictly stopped at `PC 0x42f878`, reading `MCUCTRL.SIMOBUCK1 0x40020340`. CPU fault/policy errors 0; worker/main/auth/recovery entries 0. Compared with prior chip23/trim1 input only one board revision line differs; runtime/model/original images are identical.
- The next original instruction sets SIMOBUCK1 HPTRIMEN bit 31, corresponding to public PCM0.7 TON update. A subsequent model must handle seven configuration fields across SIMOBUCK1/2/4/6/7 together. Public reset is SIMOBUCK1 `0x00400000`, others 0. These are digital reset contracts, not actual device factory calibration or analog behavior.

## Verification and limitations

All 23 judgments in `tools/review_recovery_info1_contract.py` passed, checking pinned Git blob hashes, first original native request, B0 input difference, original instructions, and TON field masks. Frozen audit-source.py reran in `/tmp` and passed. Four `test_upstream_boot_probe.py` tests passed. Default revision remains existing 0x23.

The first audit script failed due to some HTML/header field-name differences. Zero-reset fields were handled as 0 without position conversion and nonzero fields checked against header masks. Audit then rejected a draft incorrectly transcribing every native request as 16 words/destination 0x20026da4. It was corrected to actual logs trim 1=16/trim 2=20 and destination 0x20026ba4. Failed audit 01 is diagnostic history; final passing evidence is 03.

Runner cleaned four duplicate images from the new B0 run totaling **8,164,696 bytes**; owned native process state is removed. Original inputs, public source, model, logs, hashes, and audit scripts remain for reproduction. Physical G2 MCU revision was not observed and B0 compatibility is not claimed. Existing version matrix authorization status was unchanged.

Evidence: `private:simulator/recovery-info1-audit-bw575-03/report.json`, `private:simulator/upstream23-b0-pcm07-native-bw575-01/report.json`, `private:simulator/recovery-info1-research-bw575-01/`.

Next implement and test a separate opt-in B0 TON configuration group based on source masks/resets, then resume the same original reset path. Do not complete BV05/06 before worker/auth success.
