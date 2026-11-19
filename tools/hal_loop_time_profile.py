"""Explicit uniform-instruction approximation derived from the pinned HAL spin loop."""
from fractions import Fraction

HAL_COMMIT='61b293a49db34030c545f99101f7ebf6a3050314'
HAL_SHA256='20a26a34ceb7835fa2a233bbbf2454f5f43e13aeb1ab43d51f5ff14a38f579a3'

def profile(mode):
 if mode not in ('lp','hp'):raise ValueError('Declared LP or HP mode required')
 nominal_clock_mhz={'lp':96,'hp':250}[mode]
 exact=Fraction(nominal_clock_mhz*2,3)
 # Integer MIPS keeps the selected board input explicit; round to nearest, never fit to a timeout.
 mips=(exact.numerator+exact.denominator//2)//exact.denominator
 return dict(name='hal-loop-equivalent-v1',mode=mode,mips=mips,source_commit=HAL_COMMIT,source_sha256=HAL_SHA256,source_clock_mhz=nominal_clock_mhz,loop_instructions=2,source_cycles_per_iteration=3,unrounded_mips=dict(numerator=exact.numerator,denominator=exact.denominator),rounding_relative_error=float(Fraction(mips,1)/exact-1),scope='uniform instruction rate approximating the HAL loop, not per-opcode or physical cycle timing',physical_clock_verified=False,default_board_changed=False)
