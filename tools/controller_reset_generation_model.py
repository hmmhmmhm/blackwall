"""Bounded opt-in reset generations for the pinned strict controller component."""
from hci_response_loss_model import compose as loss_compose
from runtime_reconnect_model import component


def compose(model):
    _,base=component();old=loss_compose(base);new=old
    def change(a,b):
        nonlocal new
        if new.count(a)!=1:raise ValueError('Unknown reset generation boundary: '+a[:60])
        new=new.replace(a,b)
    change('bool runtimeDropFirstReadvertisingReply=false)', 'bool runtimeDropFirstReadvertisingReply=false,int controllerResetLimit=0)')
    change('            DropFirstReadvertisingReply=runtimeDropFirstReadvertisingReply;', '''            if(controllerResetLimit<0 || controllerResetLimit>4 || (controllerResetLimit>0 && !runtimeReadvertise))throw new ArgumentException("Bounded reset generations require explicit runtime initialization");
            ControllerResetLimit=controllerResetLimit;
            DropFirstReadvertisingReply=runtimeDropFirstReadvertisingReply;''')
    change('        public bool DropFirstReadvertisingReply {get;}', '''        public bool DropFirstReadvertisingReply {get;}
        public int ControllerResetLimit {get;}
        public int ControllerGeneration {get;private set;}
        public string ControllerGenerationHistory=>string.Join(";",generationHistory);
        public string ResetGenerationRejection {get;private set;}="";
        private readonly System.Collections.Generic.List<string> generationHistory=new System.Collections.Generic.List<string>();
        private bool generationHeld,generationEligible;
        private void ClearGenerationState()
        {
            phase=Phase.Unreleased;headerUsed=false;
            Position=Headers=Payloads=Frames=PayloadBytes=Aborts=CommandsAccepted=Replies=WriteHeaders=chunkSize=0;
            p256Event=0;
            runtimeActive=runtimeRandPending=runtimeRssiPending=runtimeRemotePending=false;runtimeWriteKind=0;runtimeCurrent=null;
            RuntimeEventsConsumed=RuntimeHostAclConsumed=RuntimeRandCommandsAccepted=RuntimeRandRepliesConsumed=RuntimeRssiCommandsAccepted=RuntimeRssiRepliesConsumed=RuntimeRemoteCommandsAccepted=RuntimeRemoteRepliesConsumed=0;
            readvertisingPending=false;ReadvertisingCommands=ReadvertisingReplies=ReadvertisingRepliesDropped=0;
            transmitted.Clear();written.Clear();accepted.Clear();readvertisingAccepted.Clear();runtimeLevel?.Invoke(false);
        }''')
    # Only the peer Reset, not the GPIO reset adapter Reset, has this signature/body.
    change('''        public void Reset()
        {
            phase=Phase.Unreleased;CsKnown=false;CsHigh=true;headerUsed=false;''', '''        public void Reset()
        {
            generationHeld=generationEligible=false;ControllerGeneration=0;generationHistory.Clear();ResetGenerationRejection="";
            phase=Phase.Unreleased;CsKnown=false;CsHigh=true;headerUsed=false;''')
    change('''        public void HoldReset()
        {
            phase=HasReadScenario && Frames>0?Phase.Exhausted:Phase.Unreleased;Position=0;headerUsed=false;''', '''        public void HoldReset()
        {
            if(ControllerResetLimit>0 && (Frames>0 || ControllerGeneration>0))
            {
                if(!generationHeld)
                {
                    generationHeld=true;
                    generationEligible=ControllerGeneration<ControllerResetLimit && phase==Phase.Complete && CsKnown && CsHigh
                        && !RuntimeEventPending && (written.Count==0 || written.Count==CurrentCommand.Length) && runtimeWriteKind==0 && CommandsAccepted==CommandLimit && Replies==ExpectedReplyEvents;
                    ResetGenerationRejection=generationEligible?"":ControllerGeneration>=ControllerResetLimit?"generation-limit":"unfinished-or-selected-transport";
                }
            }
            phase=HasReadScenario && Frames>0?Phase.Exhausted:Phase.Unreleased;Position=0;headerUsed=false;''')
    change('''        public void QualifiedRelease(bool valid) { if(phase!=Phase.Exhausted)phase=valid?Phase.Queued:Phase.Unreleased; }''', '''        public void QualifiedRelease(bool valid)
        {
            if(ControllerResetLimit>0 && (Frames>0 || ControllerGeneration>0) && !generationHeld)
            {
                ResetGenerationRejection="missing-assertion";phase=Phase.Exhausted;return;
            }
            if(ControllerResetLimit>0 && generationHeld)
            {
                generationHeld=false;
                if(!valid || !generationEligible || !CsKnown || !CsHigh)
                {
                    ResetGenerationRejection=!valid?"short-pulse":!generationEligible?ResetGenerationRejection:"selected-at-release";
                    generationEligible=false;phase=Phase.Exhausted;return;
                }
                generationHistory.Add(ControllerGeneration+":"+Frames+":"+CommandsAccepted+":"+Replies+":"+RuntimeEventsConsumed+":"+ReadvertisingCommands+":"+ReadvertisingReplies+":"+ReadvertisingRepliesDropped+":"+string.Join(",",accepted)+":"+ReadvertisingAccepted);
                ClearGenerationState();ControllerGeneration++;generationEligible=false;ResetGenerationRejection="";phase=Phase.Queued;return;
            }
            if(phase!=Phase.Exhausted)phase=valid?Phase.Queued:Phase.Unreleased;
        }''')
    if model.count(old)!=1:raise ValueError('Unknown loss/reconnect controller composition')
    return model.replace(old,new)
