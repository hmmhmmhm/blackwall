.syntax unified
.thumb
.cpu cortex-m55
.section .vectors,"a",%progbits
.word 0x20001000
.word reset
.section .text,"ax",%progbits
.global reset, loop, store_result, after_store
.thumb_func
reset:
    movs r0, #3
loop:
    subs r0, #1
    bne loop
    movs r1, #42
    ldr r2, =0x20000000
store_result:
    str r1, [r2]
after_store:
    nop
halt:
    b halt
