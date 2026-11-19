#include <stdint.h>
#define REG(a) (*(volatile uint32_t *)(a))
#define SELECT REG(0xe000ed84)
#define SIZE REG(0xe000ed80)
#define CCR REG(0xe000ed14)
#define INV REG(0xe000ef60)
#define CLEAN REG(0xe000ef6c)
#define BOTH REG(0xe000ef74)
static void sweep(uint32_t address) {
    for(uint32_t set=0;set<512;set++)
        for(uint32_t way=0;way<4;way++) REG(address)=(way<<30)|(set<<5);
}
static void enable(void) { REG(0xe000ef50)=0; sweep(0xe000ef60); CCR=CCR|0x30000; }
void reset(void) {
    volatile uint32_t *result=(volatile uint32_t *)0x20000000;
    result[0]=0x11112222; result[1]=result[2]=0;
#if MODE == 102
    SELECT=1;
#elif MODE == 103
    result[1]=SIZE;
#elif MODE == 104
    *(volatile uint8_t *)0xe000ed84=0;
#elif MODE == 113
    SIZE=0;
#elif MODE == 115
    SELECT=0;
#elif MODE == 118
    result[1]=INV;
#else
    SELECT=0;
#if MODE == 100
    result[1]=SIZE; enable(); sweep(0xe000ef6c); sweep(0xe000ef74); result[2]=CCR&0x30000;
#elif MODE == 105
    INV=1;
#elif MODE == 106
    CCR=CCR|0x10000;
#elif MODE == 107
    for(uint32_t i=0;i<2048;i++) INV=0;
    CCR=CCR|0x10000;
#elif MODE == 108
    sweep(0xe000ef6c); CCR=CCR|0x10000;
#elif MODE == 109
    enable(); CCR=CCR&~0x10000; CCR=CCR|0x10000;
#elif MODE == 110
    REG(0xe000ef50)=0; sweep(0xe000ef74); CCR=CCR|0x30000; result[1]=SIZE; result[2]=CCR&0x30000;
#elif MODE == 111
    *(volatile uint8_t *)0xe000ef60=0;
#elif MODE == 112
    result[1]=INV;
#elif MODE == 114
    CCR=CCR|1;
#elif MODE == 116
    enable(); REG(0x438000)=0;
#elif MODE == 117
    INV=1u<<14;
#endif
#endif
    result[0]=0x33334444;
    for(;;) __asm volatile("nop");
}
__attribute__((section(".vectors"),used)) const uintptr_t vectors[]={0x2007fb00,(uintptr_t)reset};
