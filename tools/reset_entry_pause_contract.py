"""Complete an owned reset-entry pause before publishing its completion flag."""
import hashlib
BASE_SHA='7ce4ac4fc54dec355bc1c99af541ecad8a31ca5f772e110b133e3c6a080d38cd'
def completed_pause(source):
 if hashlib.sha256(source.encode()).hexdigest()!=BASE_SHA:raise ValueError('Changed pinned reset-entry observer')
 old='callback=(c,a)=>{Seen=true;machine.Pause();};'
 if source.count(old)!=1:raise ValueError('Unknown reset-entry pause boundary')
 return source.replace(old,'callback=(c,a)=>{machine.Pause();Seen=true;};',1)
