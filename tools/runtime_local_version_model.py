"""Exact optional HCI 0x1001 identity replies; preserve the pinned shared controller."""
import hashlib
from pathlib import Path

BASE_SHA='3f830d6cd1cb66d4114ee04f156e3d54d05eac61de22983771aae3d463d7b4c0'

def component(*,completed_startup=False):
 old=Path(__file__).with_name('renode-em9305-reset.cs').read_text()
 if hashlib.sha256(old.encode()).hexdigest()!=BASE_SHA:raise ValueError('Changed controller baseline')
 new=old
 def change(a,b,count=1):
  nonlocal new
  if new.count(a)!=count:raise ValueError('Unknown local version boundary '+a[:60])
  new=new.replace(a,b)
 change('string runtimeDisconnectEventHex=null)','string runtimeDisconnectEventHex=null,string runtimeLocalVersionHex=null,int runtimeLocalVersionLimit=0)')
 change('            Reset();\n        }\n        public bool TryQueueRuntimeDisconnect()', '''            if(runtimeLocalVersionHex==null ? runtimeLocalVersionLimit!=0 : runtimeLocalVersionLimit<1 || runtimeLocalVersionLimit>32)
                throw new ArgumentException("Local version limit/profile mismatch");
            if(runtimeLocalVersionHex!=null)
            {
                if(runtimeRemoteReplies==null)throw new ArgumentException("Local version requires the explicit completed ATT/remote workflow");
                runtimeLocalVersionReply=new byte[]{4,14,12,1,1,16,0}.Concat(Parse(runtimeLocalVersionHex,8)).ToArray();
            }
            RuntimeLocalVersionLimit=runtimeLocalVersionLimit;
            Reset();
        }
        public int RuntimeLocalVersionLimit {get;}
        public int LocalVersionCommands {get;private set;}
        public int LocalVersionReplies {get;private set;}
        private const int LocalVersionWriteKind=0x1001;
        private readonly byte[] runtimeLocalVersionReply;
        private bool runtimeLocalVersionPending;
        private static readonly byte[] localVersionCommand={1,1,16,0};
        public bool TryQueueRuntimeDisconnect()''')
 change('runtimeActive=runtimeRandPending=runtimeRssiPending=runtimeRemotePending=false;', 'runtimeLocalVersionPending=runtimeActive=runtimeRandPending=runtimeRssiPending=runtimeRemotePending=false;',2)
 change('            transmitted.Clear();written.Clear();accepted.Clear();','            LocalVersionCommands=LocalVersionReplies=0;\n            transmitted.Clear();written.Clear();accepted.Clear();')
 change('            if(!high && phase==Phase.Complete && runtimeRandReplies!=null', '''            if(!high && phase==Phase.Complete && runtimeLocalVersionReply!=null && LocalVersionCommands<RuntimeLocalVersionLimit
                && RuntimeEventsConsumed==3 && RuntimeRemoteRepliesConsumed==2 && !RuntimeEventPending
                && runtimeConfigured!=null && runtimeConfigured())
            {
                if(runtimeWriteKind==0){runtimeWriteKind=LocalVersionWriteKind;written.Clear();}
                if(runtimeWriteKind==LocalVersionWriteKind)phase=Phase.WriteHeaderReady;
            }
            if(!high && phase==Phase.Complete && runtimeRandReplies!=null''')
 change('                        if(runtimeWriteKind==1) { RuntimeRandCommandsAccepted++;', '''                        if(runtimeWriteKind==LocalVersionWriteKind)
                        { LocalVersionCommands++;runtimeLocalVersionPending=true;phase=Phase.ReplyQueued;runtimeLevel(true); }
                        else if(runtimeWriteKind==1) { RuntimeRandCommandsAccepted++;''')
 change('                if(runtimeActive)\n                {', '''                if(runtimeLocalVersionPending)
                { runtimeLocalVersionPending=false;LocalVersionReplies++;phase=Phase.Complete;runtimeLevel(false);return; }
                if(runtimeActive)
                {''')
 change('public bool RuntimeEventPending=>runtimeActive ||','public bool RuntimeEventPending=>runtimeLocalVersionPending || runtimeActive ||')
 change('                if(runtimeWriteKind==1)return runtimeRandCommand;','                if(runtimeWriteKind==LocalVersionWriteKind)return localVersionCommand;\n                if(runtimeWriteKind==1)return runtimeRandCommand;')
 change('                if(runtimeActive)return runtimeCurrent;','                if(runtimeLocalVersionPending)return runtimeLocalVersionReply;\n                if(runtimeActive)return runtimeCurrent;')
 if completed_startup:
  change('if(runtimeRemoteReplies==null)throw new ArgumentException("Local version requires the explicit completed ATT/remote workflow");',
         'if(!HasAdvertisingInitializationScenario || runtimeEvent==null)throw new ArgumentException("Local version requires explicit completed startup and runtime GPIO profile");')
  change('&& RuntimeEventsConsumed==3 && RuntimeRemoteRepliesConsumed==2 && !RuntimeEventPending',
         '&& CommandsAccepted==CommandLimit && Replies==ExpectedReplyEvents\n                && RuntimeEventsConsumed==0 && RuntimeRemoteRepliesConsumed==0 && !RuntimeEventPending')
 return old,new

def compose(model,*,completed_startup=False):
 old,new=component(completed_startup=completed_startup)
 if model.count(old)!=1:raise ValueError('Expected one pinned controller component')
 return model.replace(old,new,1)
