"""Pin and adapt an MIT Renode timer engine to the public Apollo510 clock contract."""
import hashlib
from pathlib import Path
SHA='01759fe4e1066245743a8b09645a5f905f80b22df631452252d535867d2f38f3'
def load_engine(simulator):
 data=(Path(simulator)/'stimer-engine-research-01/AmbiqApollo4_SystemTimer.cs').read_bytes()
 if hashlib.sha256(data).hexdigest()!=SHA:raise ValueError('Unreviewed STIMER engine')
 text=data.decode()
 def replace(old,new,count=1):
  nonlocal text
  if text.count(old)!=count:raise ValueError('STIMER source adaptation differs: '+old[:60])
  text=text.replace(old,new)
 replace('AmbiqApollo4_SystemTimer','BlackwallStimerEngine',6)
 # Counter advancement must come from Renode time, never from a register write.
 begin=text.index('                            if((compareRegisters[registerIndex].CompareValue - (uint)newValue) > 3)')
 end=text.index('                            compareRegisters[registerIndex].CompareValue = Value + (uint)newValue;',begin)
 text=text[:begin]+'                            // Explicit immediate-write timing model; no synthetic counter increment.\n'+text[end:]
 replace('uint.MaxValue,','0x100000000UL,',2)
 replace('frequencySet = 32 * khz;','frequencySet = 32768;')
 replace('frequencySet = 16 * khz;','frequencySet = 16384;')
 replace('            case ClockSelectValues.XTAL_1KHZ:\n            case ClockSelectValues.LFRC_1KHZ:\n                frequencySet = 1 * khz;\n                break;','            case ClockSelectValues.XTAL_1KHZ:\n                frequencySet = 1024;\n                break;\n            case ClockSelectValues.LFRC_1KHZ:\n                frequencySet = 900;\n                break;')
 update='                systemTimer.Frequency = frequencySet;\n                Array.ForEach(compareRegisters, register => register.Frequency = frequencySet);\n'
 replace(update,'')
 replace('            if(frequencySet != InvalidFrequency)\n','            systemTimer.Frequency = frequencySet;\n            Array.ForEach(compareRegisters, register => register.Frequency = frequencySet);\n            if(frequencySet != InvalidFrequency)\n')
 replace('        private void DefineRegisters()','        public void LoadCounter(uint value)\n        {\n            systemTimer.Value=value;\n            Array.ForEach(compareRegisters, register => register.UpdateState());\n        }\n\n        private void DefineRegisters()')
 start=text.index('using System;');end=text.index('namespace Antmicro.Renode.Peripherals.Timers');imports=text[start:end];text=text[:start]+text[end:]
 replace('namespace Antmicro.Renode.Peripherals.Timers\n{\n','namespace Antmicro.Renode.Peripherals.Timers\n{\n'+imports)
 if 'systemTimer.Increment(' in text:raise ValueError('Forced counter advancement remains')
 return text
