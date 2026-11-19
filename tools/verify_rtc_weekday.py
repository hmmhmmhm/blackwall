"""Extend the existing RTC regression with independent weekday field experiments."""
import argparse,json
from pathlib import Path
import verify_rtc_adapter as original

EXTRA='''
import clr
from Antmicro.Renode.Utilities import TypeManager
clr.AddReference(TypeManager.Instance.GetTypeByName('Antmicro.Renode.Peripherals.Miscellaneous.BlackwallRtcAdapter').Assembly)
from Antmicro.Renode.Peripherals.Miscellaneous import BlackwallRtcAdapter
ind=BlackwallRtcAdapter(m,True,True)
ind.WriteDoubleWord(0,1)
ind.WriteDoubleWord(0x20,0x23595999)
ind.WriteDoubleWord(0x24,0x10000101)
ind.WriteDoubleWord(0,0)
check('independent-weekday-commit',ind.Commits==1 and ind.WeekdayMismatches==1)
check('independent-weekday-not-normalized',ind.ReadDoubleWord(0x20)==0x23595999 and ind.ReadDoubleWord(0x24)==0x10000101)
'''
AFTER='''
check('independent-midnight-carry',ind.ReadDoubleWord(0x20)==1 and ind.ReadDoubleWord(0x24)==0x11000102)
ind.WriteDoubleWord(0,1)
ind.WriteDoubleWord(0x20,0)
blocked('independent-invalid-weekday-seven',ind,lambda:ind.WriteDoubleWord(0x24,0x17000101))
ind.WriteDoubleWord(0x24,0x16000101)
ind.WriteDoubleWord(0,0)
check('independent-valid-commit-and-mismatch-count',ind.Commits==2 and ind.WeekdayMismatches==1)
ind.Reset()
check('independent-reset-clears-weekday-anchor',ind.Commits==0 and ind.WeekdayMismatches==0 and ind.ReadDoubleWord(0x20)==0 and ind.ReadDoubleWord(0x24)==0x16000101)
'''

def main():
 import sys
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);args=p.parse_args()
 original.SETUP+=EXTRA
 ms,name,phase=original.PHASES[0];original.PHASES[0]=(ms,name,phase+AFTER)
 sys.argv=[sys.argv[0],str(args.output)]
 original.main()

if __name__=='__main__':main()
