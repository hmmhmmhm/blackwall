#include <stdint.h>
#define MAIL ((volatile uint32_t *)0x20000000)

void fault(void) {
    uint32_t value;
    __asm volatile("mrs %0, ipsr" : "=r"(value));
    MAIL[15] = value;
    for (;;) {}
}

void reset(void) {
    uint32_t psplim, msplim, psp, msp, value;
    __asm volatile("mrs %0, psplim" : "=r"(psplim));
    __asm volatile("mrs %0, msplim" : "=r"(msplim));
    __asm volatile("mrs %0, psp" : "=r"(psp));
    __asm volatile("mrs %0, msp" : "=r"(msp));
    MAIL[1] = psplim; MAIL[2] = msplim; MAIL[3] = psp; MAIL[4] = msp;
    value = 0x20002000;
    __asm volatile("msr psplim, %0\nisb\nmrs %0, psplim" : "+r"(value) : : "memory");
    MAIL[5] = value;
    value = 0x20001000;
    __asm volatile("msr msplim, %0\nisb\nmrs %0, msplim" : "+r"(value) : : "memory");
    MAIL[6] = value;
    value = 0x20008000;
    __asm volatile("msr psp, %0\nisb\nmrs %0, psp" : "+r"(value) : : "memory");
    MAIL[7] = value;
    __asm volatile("msr psplim, %0\nmsr msplim, %1\nmsr psp, %2\nisb"
                   : : "r"(psplim), "r"(msplim), "r"(psp) : "memory");
    __asm volatile("mrs %0, psplim" : "=r"(value)); MAIL[8] = value;
    __asm volatile("mrs %0, msplim" : "=r"(value)); MAIL[9] = value;
    __asm volatile("mrs %0, psp" : "=r"(value)); MAIL[10] = value;
    MAIL[0] = 0x600d;
    for (;;) {}
}

__attribute__((section(".vectors"), used))
const uintptr_t vectors[16] = {
    0x2000f000, (uintptr_t)reset, (uintptr_t)fault, (uintptr_t)fault,
    (uintptr_t)fault, (uintptr_t)fault, (uintptr_t)fault
};
