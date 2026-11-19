"""Opt-in, exact data-first advertising order for a qualified later generation."""
from runtime_reconnect_model import component
from hci_response_loss_model import compose as loss_compose
from controller_reset_generation_model import compose as generation_compose

def compose(model):
    _,base=component();old=generation_compose(loss_compose(base));new=old
    def change(a,b):
        nonlocal new
        if new.count(a)!=1:raise ValueError('Unknown post-reset advertising boundary')
        new=new.replace(a,b)
    change('int controllerResetLimit=0)', 'int controllerResetLimit=0,bool postResetAdvertisingDataFirst=false)')
    change('            ControllerResetLimit=controllerResetLimit;', '''            if(postResetAdvertisingDataFirst && controllerResetLimit==0)throw new ArgumentException("Post-reset order requires explicit reset generations");
            PostResetAdvertisingDataFirst=postResetAdvertisingDataFirst;
            ControllerResetLimit=controllerResetLimit;''')
    change('        public int ControllerResetLimit {get;}', '''        public int ControllerResetLimit {get;}
        public bool PostResetAdvertisingDataFirst {get;}
        private int AdvertisingIndex(int index)=>PostResetAdvertisingDataFirst && ControllerGeneration>0 ? postResetAdvertisingOrder[index] : index;
        private static readonly int[] postResetAdvertisingOrder={0,2,3,1,4};''')
    change('advertisingCommands[Math.Min(CommandsAccepted-54,4)]','advertisingCommands[AdvertisingIndex(Math.Min(CommandsAccepted-54,4))]')
    change('advertisingReplies[Math.Min(CommandsAccepted-55,4)]','advertisingReplies[AdvertisingIndex(Math.Min(CommandsAccepted-55,4))]')
    if model.count(old)!=1:raise ValueError('Unknown generation component')
    return model.replace(old,new)
