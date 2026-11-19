"""Optional exact runtime HCI selector: local version and captured advertising stop."""
from runtime_local_version_model import component as version_component


def component():
    _, old = version_component(completed_startup=True)
    new = old

    def change(before, after, count=1):
        nonlocal new
        if new.count(before) != count:
            raise ValueError('Unknown startup command boundary: ' + before[:65])
        new = new.replace(before, after)

    change('int runtimeLocalVersionLimit=0)', 'int runtimeLocalVersionLimit=0,int startupAdvertisingDisableLimit=0)')
    change('            RuntimeLocalVersionLimit=runtimeLocalVersionLimit;', '''            if(startupAdvertisingDisableLimit<0 || startupAdvertisingDisableLimit>32
                || startupAdvertisingDisableLimit!=0 && runtimeLocalVersionReply==null)
                throw new ArgumentException("Advertising disable requires explicit startup version profile and limit0..32");
            StartupAdvertisingDisableLimit=startupAdvertisingDisableLimit;
            RuntimeLocalVersionLimit=runtimeLocalVersionLimit;''')
    change('        public int RuntimeLocalVersionLimit {get;}', '''        public int StartupAdvertisingDisableLimit {get;}
        public int AdvertisingDisableCommands {get;private set;}
        public int AdvertisingDisableReplies {get;private set;}
        public bool AdvertisingStopped {get;private set;}
        private bool advertisingDisablePending;
        private static readonly byte[] advertisingDisableCommand={1,10,32,1,0};
        private static readonly byte[] advertisingDisableReply={4,14,4,1,10,32,0};
        private byte[][] StartupWriteCandidates
        {
            get
            {
                var commands=new System.Collections.Generic.List<byte[]>();
                if(LocalVersionCommands<RuntimeLocalVersionLimit)commands.Add(localVersionCommand);
                if(AdvertisingDisableCommands<StartupAdvertisingDisableLimit)commands.Add(advertisingDisableCommand);
                return commands.Where(command=>written.Count<=command.Length && written.SequenceEqual(command.Take(written.Count))).ToArray();
            }
        }
        public int RuntimeLocalVersionLimit {get;}''')
    change('LocalVersionCommands=LocalVersionReplies=0;', 'AdvertisingDisableCommands=AdvertisingDisableReplies=0;AdvertisingStopped=false;LocalVersionCommands=LocalVersionReplies=0;')
    change('runtimeLocalVersionPending=runtimeActive=', 'advertisingDisablePending=runtimeLocalVersionPending=runtimeActive=', 2)
    change('runtimeLocalVersionReply!=null && LocalVersionCommands<RuntimeLocalVersionLimit',
           'runtimeLocalVersionReply!=null && (LocalVersionCommands<RuntimeLocalVersionLimit || AdvertisingDisableCommands<StartupAdvertisingDisableLimit)')
    change('{ LocalVersionCommands++;runtimeLocalVersionPending=true;phase=Phase.ReplyQueued;runtimeLevel(true); }', '''{
                            if(written.SequenceEqual(advertisingDisableCommand))
                            { AdvertisingDisableCommands++;AdvertisingStopped=true;advertisingDisablePending=true; }
                            else { LocalVersionCommands++;runtimeLocalVersionPending=true; }
                            phase=Phase.ReplyQueued;runtimeLevel(true);
                        }''')
    change('                if(runtimeLocalVersionPending)\n', '''                if(advertisingDisablePending)
                { advertisingDisablePending=false;AdvertisingDisableReplies++;phase=Phase.Complete;runtimeLevel(false);return; }
                if(runtimeLocalVersionPending)
''')
    change('public bool RuntimeEventPending=>runtimeLocalVersionPending ||', 'public bool RuntimeEventPending=>advertisingDisablePending || runtimeLocalVersionPending ||')
    change('if(runtimeWriteKind==LocalVersionWriteKind)return localVersionCommand;',
           'if(runtimeWriteKind==LocalVersionWriteKind)return StartupWriteCandidates.FirstOrDefault()??localVersionCommand;')
    change('                if(runtimeLocalVersionPending)return runtimeLocalVersionReply;',
           '                if(advertisingDisablePending)return advertisingDisableReply;\n                if(runtimeLocalVersionPending)return runtimeLocalVersionReply;')
    change('            return phase==Phase.WritePayloadReady && WriteCapacity>0 && length==Math.Min(WriteCapacity,CurrentCommand.Length-written.Count);', '''            if(phase==Phase.WritePayloadReady && runtimeWriteKind==LocalVersionWriteKind)
                return WriteCapacity>0 && length>0 && StartupWriteCandidates.Any(command=>length==Math.Min(WriteCapacity,command.Length-written.Count));
            return phase==Phase.WritePayloadReady && WriteCapacity>0 && length==Math.Min(WriteCapacity,CurrentCommand.Length-written.Count);''')
    change('            if(phase==Phase.WritePayloadActive)\n', '''            if(phase==Phase.WritePayloadActive && runtimeWriteKind==LocalVersionWriteKind)
                return Position+length<=chunkSize && StartupWriteCandidates.Any(command=>written.Count+length<=command.Length
                    && chunkSize==Math.Min(WriteCapacity,command.Length-(written.Count-Position))
                    && Enumerable.Range(0,length).All(i=>(byte)(word>>(8*i))==command[written.Count+i]));
            if(phase==Phase.WritePayloadActive)
''')
    change('        public bool TryQueueRuntimeConnection()\n        {',
           '        public bool TryQueueRuntimeConnection()\n        {\n            if(AdvertisingStopped)return false;')
    return old, new


def compose(model):
    old, new = component()
    if model.count(old) != 1:
        raise ValueError('One pinned startup version component required')
    return model.replace(old, new, 1)
