import re
from pathlib import Path

def mask(text):
 return re.sub(r'//[^\n]*|/\*[\s\S]*?\*/|@"(?:[^"]|"")*"|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',lambda m:' '*len(m.group()),text)
def types(text):
 m=mask(text);out={}
 for d in re.finditer(r'^    public (?:(?:sealed|abstract|static) )?(?:class|interface|enum) (\w+)\b',m,re.M):
  b=m.index('{',d.end());depth=1;i=b+1
  while depth:depth+=int(m[i]=='{')-int(m[i]=='}');i+=1
  out[d.group(1)]=(d.start(),i,text[d.start():i])
 return out

def compose(model,current):
 old=types(model);desired=types(current);changes=[];replacements=[];extra=[]
 for name,(_,_,code) in desired.items():
  if name in old:
   start,end,before=old[name]
   if before!=code:replacements.append((start,end,code));changes.append(name)
  else:extra.append(code);changes.append('add:'+name)
 for start,end,code in sorted(replacements,reverse=True):model=model[:start]+code+model[end:]
 if extra:model+='\nnamespace Antmicro.Renode.Peripherals.Miscellaneous\n{\n'+'\n'.join(extra)+'\n}\n'
 return model,changes
