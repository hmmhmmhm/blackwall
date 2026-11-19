#include <stdint.h>
#define CCR (*(volatile uint32_t*)0xe000ed14)
#define ICI (*(volatile uint32_t*)0xe000ef50)
#define IC (1u<<17)
static void enable(void) { ICI=0; CCR=CCR|IC; }
void reset(void) {
 volatile uint32_t *result=(volatile uint32_t*)0x20000000;
 result[1]=result[2]=0;
 result[0]=0x11112222;
#if MODE == 1 || MODE == 11
 enable(); result[1]=CCR&IC;
#elif MODE == 2
 CCR=CCR|IC;
#elif MODE == 3
 ICI=1;
#elif MODE == 4
 *(volatile uint8_t*)0xe000ef50=0;
#elif MODE == 5
 result[1]=ICI;
#elif MODE == 6
 CCR=CCR|(1u<<16);
#elif MODE == 7
 *(volatile uint32_t*)0x100=0x47702007;
 result[1]=((uint32_t(*)(void))0x101)();
 enable();
 *(volatile uint8_t*)0x100=9;
 __asm volatile("dsb sy" ::: "memory");
 ICI=0;
 __asm volatile("isb sy" ::: "memory");
 result[2]=((uint32_t(*)(void))0x101)();
#elif MODE == 8
 enable(); *(volatile uint16_t*)0x100=0xf240;
 ((void(*)(void))0x101)();
#elif MODE == 9
 enable(); CCR=CCR&~IC; result[1]=CCR&IC;
#elif MODE == 10
 enable(); ICI=0; result[1]=CCR&IC;
#elif MODE == 12
 *(volatile uint8_t*)0xe000ed14=0;
#elif MODE == 13
 CCR=CCR^1;
#elif MODE == 14
 *(volatile uint32_t*)0xe000ed84=0;
#elif MODE == 15
 result[1]=*(volatile uint32_t*)0xe000ed80;
#elif MODE == 16
 *(volatile uint32_t*)0xe000ef60=0;
#endif
 result[0]=0x33334444;
 __asm volatile("ldr r0,=0x20000000\nldr r4,[r0,#4]\nldr r5,[r0,#8]\nldr r6,[r0]\n1: b 1b" ::: "r0","r4","r5","r6","memory");
 for(;;){}
}
__attribute__((section(".vectors"),used)) const uintptr_t vectors[]={0x2007fb00,(uintptr_t)reset};
