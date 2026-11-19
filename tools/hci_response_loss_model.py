"""Drop one declared simulated advertising completion, without fabricating a timeout."""
from runtime_reconnect_model import component


def compose(model):
    _,old=component();new=old
    def change(a,b):
        nonlocal new
        if new.count(a)!=1:raise ValueError('Unknown response-loss boundary')
        new=new.replace(a,b)
    change('bool runtimeReadvertise=false)', 'bool runtimeReadvertise=false,bool runtimeDropFirstReadvertisingReply=false)')
    change('            RuntimeReadvertise=runtimeReadvertise;', '''            if(runtimeDropFirstReadvertisingReply && !runtimeReadvertise)throw new ArgumentException("Reply loss requires explicit readvertising");
            DropFirstReadvertisingReply=runtimeDropFirstReadvertisingReply;
            RuntimeReadvertise=runtimeReadvertise;''')
    change('        public bool RuntimeReadvertise {get;}', '''        public bool RuntimeReadvertise {get;}
        public bool DropFirstReadvertisingReply {get;}
        public int ReadvertisingRepliesDropped {get;private set;}
        public event Action ReadvertisingReplyDropped;''')
    change('            readvertisingPending=false;ReadvertisingCommands=ReadvertisingReplies=0;', '            ReadvertisingRepliesDropped=0;readvertisingPending=false;ReadvertisingCommands=ReadvertisingReplies=0;')
    change('''                            phase=Phase.ReplyQueued;runtimeLevel(true);
                        }
                        else if(runtimeWriteKind==1)''', '''                            if(DropFirstReadvertisingReply && ReadvertisingCommands==1)
                            {
                                readvertisingPending=false;ReadvertisingRepliesDropped++;phase=Phase.Complete;runtimeLevel(false);
                                ReadvertisingReplyDropped?.Invoke();
                            }
                            else {phase=Phase.ReplyQueued;runtimeLevel(true);}
                        }
                        else if(runtimeWriteKind==1)''')
    if model.count(old)!=1:raise ValueError('Unknown declared controller component')
    return model.replace(old,new)
