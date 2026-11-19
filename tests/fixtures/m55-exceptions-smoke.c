#include <stdint.h>

#define REG(address) (*(volatile uint32_t *)(address))
#define MAIL ((volatile uint32_t *)0x20000000)

static uint32_t exception_number(void) {
    uint32_t value;
    __asm volatile("mrs %0, ipsr" : "=r"(value));
    return value;
}

void fault(void) {
    MAIL[7] = exception_number();
    for (;;) {}
}

void svc(void) { MAIL[1] = exception_number(); }
void pendsv(void) { MAIL[2] = exception_number(); }
void irq0(void) { MAIL[3] = exception_number(); }
void irq28(void) { MAIL[12] = exception_number(); MAIL[13]++; }
void systick(void) {
    MAIL[4]++;
    MAIL[5] = exception_number();
}

static uint32_t vector_double(uint32_t value) {
    __asm volatile("vdup.32 q0, %0\n"
                   "vadd.i32 q0, q0, q0\n"
                   "vmov %0, s0" : "+r"(value) : : "q0");
    return value;
}

void reset(void) {
    MAIL[0]=MAIL[1]=MAIL[2]=MAIL[3]=MAIL[4]=MAIL[5]=0;
    MAIL[6]=MAIL[7]=MAIL[8]=MAIL[9]=MAIL[10]=MAIL[11]=0;
    MAIL[12]=MAIL[13]=MAIL[14]=MAIL[15]=0;
    REG(0xe000ed88) = 0xf00000;
    __asm volatile("dsb\nisb\ncpsie i");
    MAIL[6] = vector_double(7);
    __asm volatile("svc #0");
    REG(0xe000ed04) = 1u << 28;
    while (MAIL[2] == 0) {}
    REG(0xe000e100) = 1;
    REG(0xe000e200) = 1;
    while (MAIL[3] == 0) {}
    REG(0xe000e014) = 999;
    REG(0xe000e018) = 0;
    REG(0xe000e010) = 7;
    while (MAIL[4] < 3) { __asm volatile("wfi"); }
    REG(0xe000e010) = 0;
    REG(0xe000e180) = 1u << 28;
    REG(0xe000e200) = 1u << 28;
    MAIL[14] = (REG(0xe000e200) >> 28) & 1;
    REG(0xe000e280) = 1u << 28;
    MAIL[15] = (REG(0xe000e200) >> 28) & 1;
    REG(0xe000e100) = 1u << 28;
    REG(0xe000e200) = 1u << 28;
    while (MAIL[13] == 0) {}
    REG(0xe000e180) = 1u << 28;

    REG(0xe000ed24) |= 1u << 16;
    REG(0xe000ed94) = 5; /* MPU enabled with privileged default map. */
    __asm volatile("dsb\nisb" ::: "memory");
    MAIL[8] = REG(0xe000ed24) & (1u << 16);
    MAIL[9] = REG(0xe000ed94) & 7;
    __asm volatile("dmb" ::: "memory");
    REG(0xe000ed24) &= ~(1u << 16);
    REG(0xe000ed94) &= ~1u;
    __asm volatile("dsb\nisb" ::: "memory");
    MAIL[10] = REG(0xe000ed24) & (1u << 16);
    MAIL[11] = REG(0xe000ed94) & 7;
    MAIL[0] = 0x600d;
    for (;;) { __asm volatile("wfi"); }
}

__attribute__((section(".vectors"), used))
const uintptr_t vectors[45] = {
    0x20010000, (uintptr_t)reset, (uintptr_t)fault, (uintptr_t)fault,
    (uintptr_t)fault, (uintptr_t)fault, (uintptr_t)fault, 0, 0, 0, 0,
    (uintptr_t)svc, (uintptr_t)fault, 0, (uintptr_t)pendsv,
    (uintptr_t)systick, (uintptr_t)irq0,
    [44] = (uintptr_t)irq28
};
