#include <stdint.h>
#ifndef PROBE_MODE
#define PROBE_MODE 0
#endif
#define R(address) (*(volatile uint32_t *)(address))
#define MAIL ((volatile uint32_t *)0x20000000)
void fault(void) {
    uint32_t ipsr;
    __asm volatile("mrs %0, ipsr" : "=r"(ipsr));
    MAIL[7] = ipsr;
    for (;;) {}
}
void watchdog_irq(void) {
    uint32_t ipsr;
    __asm volatile("mrs %0, ipsr" : "=r"(ipsr));
    MAIL[1] = ipsr;
    MAIL[2] = R(0x40024204);
    MAIL[3] = R(0x4002400c);
    MAIL[4]++;
    R(0x40024208) = 1;
    MAIL[0] = 0x600d;
}
void reset(void) {
    for (unsigned i = 0; i < 8; i++) MAIL[i] = 0;
    MAIL[0] = 0x11112222;
#if PROBE_MODE == 1
    R(0xe000e100) = 2;
    R(0x40024200) = 1;
    R(0x40024000) = 0x02020a03;
#elif PROBE_MODE == 2
    R(0x40024000) = 0x05000001;
    MAIL[0] = 0xdead;
#elif PROBE_MODE == 3
    MAIL[5] = *(volatile uint16_t *)0x4002400c;
    MAIL[0] = 0xdead;
#elif PROBE_MODE == 4
    R(0x40024004) = 0xb3;
    MAIL[0] = 0xdead;
#elif PROBE_MODE == 5
    R(0x40000000) = 4;
    MAIL[0] = 0xdead;
#elif PROBE_MODE == 6
    R(0x40000004) = 0x1b;
    MAIL[0] = 0xdead;
#elif PROBE_MODE == 7
    MAIL[5] = *(volatile uint16_t *)0x40000000;
    MAIL[0] = 0xdead;
#endif
    for (;;) { __asm volatile("wfi"); }
}
__attribute__((section(".vectors"),used))
const uintptr_t vectors[18] = {
    0x20010000,(uintptr_t)reset,(uintptr_t)fault,(uintptr_t)fault,
    (uintptr_t)fault,(uintptr_t)fault,(uintptr_t)fault,0,0,0,0,
    (uintptr_t)fault,(uintptr_t)fault,0,(uintptr_t)fault,(uintptr_t)fault,
    (uintptr_t)fault,(uintptr_t)watchdog_irq
};
