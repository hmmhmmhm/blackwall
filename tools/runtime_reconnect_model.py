"""Opt-in exact advertising replay; preserve the shared pinned controller model."""
import hashlib
from pathlib import Path

BASE_SHA='3f830d6cd1cb66d4114ee04f156e3d54d05eac61de22983771aae3d463d7b4c0'


def component():
    old=Path(__file__).with_name('renode-em9305-reset.cs').read_text()
    if hashlib.sha256(old.encode()).hexdigest()!=BASE_SHA:raise ValueError('Unknown controller source')
    new=old
    def change(a,b):
        nonlocal new
        if new.count(a)!=1:raise ValueError('Unknown reconnect boundary: '+a[:65])
        new=new.replace(a,b)
    change('string runtimeDisconnectEventHex=null)', 'string runtimeDisconnectEventHex=null,bool runtimeReadvertise=false)')
    change('            Reset();\n        }\n        public bool TryQueueRuntimeDisconnect()', '''            if(runtimeReadvertise && runtimeDisconnect==null)throw new ArgumentException("Readvertise requires the completed explicit disconnect workflow");
            RuntimeReadvertise=runtimeReadvertise;
            Reset();
        }
        public bool RuntimeReadvertise {get;}
        public int ReadvertisingCommands {get;private set;}
        public int ReadvertisingReplies {get;private set;}
        public string ReadvertisingAccepted=>string.Join(";",readvertisingAccepted);
        public event Action ReadvertisingCompleted;
        public bool TryQueueRuntimeReconnection()
        {
            if(!RuntimeReadvertise || ReadvertisingReplies!=readvertisingOrder.Length || RuntimeEventsConsumed!=4 || RuntimeEventPending
                || runtimeConfigured==null || !runtimeConfigured() || phase!=Phase.Complete || !CsKnown || !CsHigh)return false;
            runtimeCurrent=runtimeEvent;runtimeActive=true;phase=Phase.ReplyQueued;runtimeLevel(true);return true;
        }
        private bool readvertisingPending;
        private static readonly int[] readvertisingOrder={1,4};
        private readonly System.Collections.Generic.List<string> readvertisingAccepted=new System.Collections.Generic.List<string>();
        public bool TryQueueRuntimeDisconnect()''')
    change('            transmitted.Clear();written.Clear();accepted.Clear();', '            readvertisingPending=false;ReadvertisingCommands=ReadvertisingReplies=0;readvertisingAccepted.Clear();\n            transmitted.Clear();written.Clear();accepted.Clear();')
    change('            if(!high && phase==Phase.Complete && runtimeRandReplies!=null', '''            if(!high && RuntimeReadvertise && RuntimeEventsConsumed==4 && ReadvertisingCommands<readvertisingOrder.Length && phase==Phase.Complete)
            {
                if(runtimeWriteKind==0){runtimeWriteKind=5;written.Clear();}
                if(runtimeWriteKind==5)phase=Phase.WriteHeaderReady;
            }
            if(!high && phase==Phase.Complete && runtimeRandReplies!=null''')
    change('                        if(runtimeWriteKind==1) { RuntimeRandCommandsAccepted++;', '''                        if(runtimeWriteKind==5)
                        {
                            readvertisingAccepted.Add(Hex(written));ReadvertisingCommands++;readvertisingPending=true;
                            phase=Phase.ReplyQueued;runtimeLevel(true);
                        }
                        else if(runtimeWriteKind==1) { RuntimeRandCommandsAccepted++;''')
    change('                if(runtimeActive)\n                {', '''                if(readvertisingPending)
                {
                    readvertisingPending=false;ReadvertisingReplies++;phase=Phase.Complete;runtimeLevel(false);
                    if(ReadvertisingReplies==readvertisingOrder.Length)ReadvertisingCompleted?.Invoke();
                    return;
                }
                if(runtimeActive)
                {''')
    change('public bool RuntimeEventPending=>runtimeActive ||', 'public bool RuntimeEventPending=>readvertisingPending || runtimeActive ||')
    change('                if(runtimeWriteKind==1)return runtimeRandCommand;', '                if(runtimeWriteKind==5)return advertisingCommands[readvertisingOrder[ReadvertisingCommands]];\n                if(runtimeWriteKind==1)return runtimeRandCommand;')
    change('                if(runtimeActive)return runtimeCurrent;', '                if(readvertisingPending)return advertisingReplies[readvertisingOrder[ReadvertisingCommands-1]];\n                if(runtimeActive)return runtimeCurrent;')
    return old,new


def compose(model):
    old,new=component()
    if model.count(old)!=1:raise ValueError('Unknown controller composition')
    return model.replace(old,new)
