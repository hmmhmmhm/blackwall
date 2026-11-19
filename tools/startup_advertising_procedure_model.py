"""Opt-in captured advertising reconfiguration, with version reads between stages."""
from startup_hci_commands_model import component as selector_component

PARAMETERS = '0106200f400640060001000000000000000700'


def component():
    _, old = selector_component()
    new = old

    def change(before, after):
        nonlocal new
        if new.count(before) != 1:
            raise ValueError('Unknown advertising procedure boundary: ' + before[:65])
        new = new.replace(before, after, 1)

    change('int startupAdvertisingDisableLimit=0)', 'int startupAdvertisingDisableLimit=0,string startupAdvertisingParametersHex=null)')
    change('            StartupAdvertisingDisableLimit=startupAdvertisingDisableLimit;', '''            if(startupAdvertisingParametersHex!=null)
            {
                if(startupAdvertisingDisableLimit!=1 || startupAdvertisingParametersHex!="''' + PARAMETERS + '''")
                    throw new ArgumentException("One captured advertising parameter procedure required");
                advertisingProcedureCommands=new byte[][]{advertisingDisableCommand,Parse(startupAdvertisingParametersHex,19),advertisingCommands[4]};
            }
            StartupAdvertisingDisableLimit=startupAdvertisingDisableLimit;''')
    change('        public int StartupAdvertisingDisableLimit {get;}', '''        public int AdvertisingProcedureStep {get;private set;}
        public int AdvertisingParameterCommands {get;private set;}
        public int AdvertisingParameterReplies {get;private set;}
        public int AdvertisingEnableCommands {get;private set;}
        public int AdvertisingEnableReplies {get;private set;}
        private readonly byte[][] advertisingProcedureCommands;
        private static readonly byte[] advertisingParametersReply={4,14,4,1,6,32,0};
        public int StartupAdvertisingDisableLimit {get;}''')
    change('if(AdvertisingDisableCommands<StartupAdvertisingDisableLimit)commands.Add(advertisingDisableCommand);', '''if(advertisingProcedureCommands!=null)
                {
                    if(AdvertisingProcedureStep<advertisingProcedureCommands.Length)commands.Add(advertisingProcedureCommands[AdvertisingProcedureStep]);
                }
                else if(AdvertisingDisableCommands<StartupAdvertisingDisableLimit)commands.Add(advertisingDisableCommand);''')
    change('AdvertisingDisableCommands=AdvertisingDisableReplies=0;', 'AdvertisingProcedureStep=AdvertisingParameterCommands=AdvertisingParameterReplies=AdvertisingEnableCommands=AdvertisingEnableReplies=0;AdvertisingDisableCommands=AdvertisingDisableReplies=0;')
    change('LocalVersionCommands<RuntimeLocalVersionLimit || AdvertisingDisableCommands<StartupAdvertisingDisableLimit)',
           'LocalVersionCommands<RuntimeLocalVersionLimit || AdvertisingDisableCommands<StartupAdvertisingDisableLimit || (advertisingProcedureCommands!=null && AdvertisingProcedureStep<3))')
    change('                            if(written.SequenceEqual(advertisingDisableCommand))', '''                            if(advertisingProcedureCommands!=null && AdvertisingProcedureStep==1 && written.SequenceEqual(advertisingProcedureCommands[1]))
                            { AdvertisingParameterCommands++;advertisingDisablePending=true; }
                            else if(advertisingProcedureCommands!=null && AdvertisingProcedureStep==2 && written.SequenceEqual(advertisingProcedureCommands[2]))
                            { AdvertisingEnableCommands++;AdvertisingStopped=false;advertisingDisablePending=true; }
                            else if(written.SequenceEqual(advertisingDisableCommand))''')
    change('{ advertisingDisablePending=false;AdvertisingDisableReplies++;phase=Phase.Complete;runtimeLevel(false);return; }', '''{
                    advertisingDisablePending=false;
                    if(advertisingProcedureCommands==null || AdvertisingProcedureStep==0)AdvertisingDisableReplies++;
                    else if(AdvertisingProcedureStep==1)AdvertisingParameterReplies++;
                    else AdvertisingEnableReplies++;
                    if(advertisingProcedureCommands!=null)AdvertisingProcedureStep++;
                    phase=Phase.Complete;runtimeLevel(false);return;
                }''')
    change('if(advertisingDisablePending)return advertisingDisableReply;',
           'if(advertisingDisablePending)return advertisingProcedureCommands!=null && AdvertisingProcedureStep==1 ? advertisingParametersReply : advertisingDisableReply;')
    new = new.replace('advertisingDisablePending', 'advertisingControlPending')
    return old, new


def compose(model):
    old, new = component()
    if model.count(old) != 1:
        raise ValueError('One pinned startup selector component required')
    return model.replace(old, new, 1)
