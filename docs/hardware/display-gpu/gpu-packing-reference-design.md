# Packed-pixel functional reference profile design

Status: design proposal awaiting user review. No implementation or native execution occurred. Existing strict/area-reference behavior and completion judgments remain.

## Problem and alternatives

The original 102 words were verified through shader generation, but Apollo sampling, AL44 layout, and quantization remain unverified. Another IP manual's bit 29 description differs from Apollo headers. Current strict mode rejects this list.

Choices: (1) retain rejection until evidence of actual hardware agreement, (2) retain strict and execute declared mathematical rules in a separate explicit functional reference profile, (3) apply those rules by default. Option 2 is recommended; 3 is not proposed. Profile 2 results are not evidence of Apollo physical pixel accuracy.

## One proposed reference policy

Name: `center-msb-alpha-high-reference-v1`. Default off; must be explicitly selected in CLI.

- Support only generation contracts of the two original shaders: first SRC and second FORCE_A|ADD, TEX2 AL44 target, TEX1 A4/L4 source, point/clamp, observed affine matrix. Reject other shaders, filters, formats, and reserved bits.
- Add 0.5 to integer pixel coordinates, apply original matrix, then floor/boundary clamp. This is a **chosen reference rule**, not a verified interpretation of Apollo MATMULT bit 29. Inputs with bit 29 set are unsupported in this profile.
- Read A4/L4 high nibble first and expand 0..15 to 0..255. A4 RGB is TEX_COLOR, L4 is luminance. Store AL44 as high four bits alpha, low four luminance. Channel reduction uses high four bits. These are explicit functional-model rules, not a guarantee of actual GPU quantization.
- First pass writes A4 sample alpha and black RGB to AL44; second adds L4 sample and forced alpha 0. Process each original draw's source/state without copying a saved expected screen.
- Default strict continues rejecting conversion. Existing area-reference means only quad coverage and does not automatically enable packing policy.

## Integration and failure behavior

Pass the profile through existing GPU consumer, Renode adapter, and display runner. Record coverage/packing profiles separately in capture and audit. Reject unsupported shaders, state, addresses, overlap, and malformed footers before DMA/completion/state commit. When reading prior draw results from the same doorbell, account for pending surface contents or explicitly reject that overlap. Do not bypass existing cache, IRQ, ring ID, or other contracts.

Record format and interpreted size/stride in frame capture so an AL44 288×288 byte surface is not mistaken for L8 or a complete 576×288 frame. Verify actual guest buffer and DMA results without injecting independent CPU expectations into guest RAM. Do not change original ARM/RTOS branches, PC, TCB, or returns. Existing API test-caller diagnosis remains distinct from natural main.

## Verification and exit criteria

Test eight hypothesis-distinguishing rows, all input brightnesses, each pass and order, nonzero destination, row padding, clip, boundary clamp, and atomic rejection of invalid shaders/matrices, addresses, and footers. Units verify consistency of mathematical reference rules, not an oracle for physical behavior.

Under the same profile, judge whether original native execution reaches buffer write → completion/IRQ → original waiter resumption → frame wrapper. Retain strict-failure control and profile-tampering audit. Once diagnosis is connected, return to natural main IMU/device input → UI path before further expanding GPU scope.

Introducing this profile alone does not declare E05/E09 or project completion. Tests requiring physical GPU agreement remain unsupported/unknown. All 16 conditions, current 3/16, and API checklist 3/6 do not change by approval or design writing.
