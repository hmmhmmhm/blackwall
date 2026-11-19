.syntax unified
.thumb
.cpu cortex-m4
.global _start
.thumb_func
_start:
    push {lr}
    movs r1, #9
    movs r2, #0
    ldr r0, =0x20002000
    bl initialization
    bl state_getter
    cmp r0, #2
    bne other_state
    movs r0, #0
    bl codec_check
