"""Exercise the host progress loop past 15 observations without launching Renode."""
import json,sys,textwrap,types
from probe_mspi1_sampling_main import LIVE_WAIT

def run(turns,block=LIVE_WAIT):
 state=dict(ticks=0,lines=[],flush=0)
 class Cpu:
  PC=types.SimpleNamespace(RawValue=0x40)
  @property
  def ExecutedInstructions(self):return state['ticks']*100
  def GetRegister(self,n):return types.SimpleNamespace(RawValue=100000-state['ticks'])
 class Machine:
  @property
  def IsPaused(self):return state['ticks']>=turns
  def __getitem__(self,key):assert key=='sysbus.cpu';return Cpu()
 class Console:
  @staticmethod
  def WriteLine(line):state['lines'].append(line)
  class Out:
   @staticmethod
   def Flush():state['flush']+=1
 def sleep(seconds):
  assert seconds==1.0
  state['ticks']+=1
 old=sys.modules.get('System');sys.modules['System']=types.SimpleNamespace(Console=Console)
 try:exec(compile(textwrap.dedent(block),'live-wait','exec'),dict(m=Machine(),time=types.SimpleNamespace(sleep=sleep)))
 finally:
  if old is None:sys.modules.pop('System',None)
  else:sys.modules['System']=old
 rows=[json.loads(x.split(' ',1)[1]) for x in state['lines']]
 assert state['ticks']==turns and state['flush']==len(rows) and [x['seconds'] for x in rows]==list(range(5,turns+1,5))
 assert all(x['pc']==0x40 and x['instructions']==x['seconds']*100 for x in rows)
 return turns
if __name__=='__main__':
 print(json.dumps(dict(passed=True,cases=[run(n) for n in [0,6,16]])))
