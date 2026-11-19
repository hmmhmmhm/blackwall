ENTRY(reset)
MEMORY {
    CODE (rx) : ORIGIN = 0x00000000, LENGTH = 64K
    SRAM (rw) : ORIGIN = 0x20000000, LENGTH = 64K
}
SECTIONS {
    .vectors : { KEEP(*(.vectors)) } > CODE
    .text : { *(.text*) *(.rodata*) } > CODE
    /DISCARD/ : { *(.ARM.exidx*) *(.comment*) }
}
