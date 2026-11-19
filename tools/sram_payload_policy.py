"""Compose a default-deny, byte-exact SRAM execution domain into the frozen policy."""
def bind(model,gate_source):
    if 'public void BindSramPayload(' in model:return model
    edits=[
      ('            validatedBlocks.Clear();\n            Violations = WrittenBytes = 0;', '            validatedBlocks.Clear();\n            SramPayload?.Reset(); SramPayloadBlocks=0;\n            Violations = WrittenBytes = 0;'),
      ('        public void Attach()\n        {', '''        public void BindSramPayload(byte[] image,uint entryOffset)
        {
            if(attached || SramPayload!=null) throw new InvalidOperationException("Bind one reviewed SRAM image before attaching");
            SramPayload=new BlackwallSramPayloadGate(image,entryOffset,(address,count)=>machine.SystemBus.ReadBytes(address,count,true));
        }
        public BlackwallSramPayloadGate SramPayload {get;private set;}
        public uint SramPayloadBlocks {get;private set;}

        public void Attach()
        {'''),
      ('            if(pc < 0x40000 && validatedBlocks.TryGetValue(pc,out var cachedSize)', '''            if(pc>=0x20000000 && pc<0x20080000)
            {
                if(SramPayload==null || (SramPayload.BaseAddress==0 && !SramPayload.TryEnter(pc)))Stop("execute-outside-code",pc,2);
                SramPayloadBlocks++;
            }
            if(pc < 0x40000 && validatedBlocks.TryGetValue(pc,out var cachedSize)'''),
      ('                var inItcm = address+2 <= 0x40000;', '''                var inItcm = address+2 <= 0x40000;
                ushort payloadWord=0;
                var inPayload=address>=0x20000000 && address<0x20080000 && SramPayload!=null && SramPayload.TryReadWord(address,out payloadWord);'''),
      ('if(!inMain && !inBoot && !inItcm) Stop(', 'if(!inMain && !inBoot && !inItcm && !inPayload) Stop('),
      (': inBoot ? boot.ReadWord((long)(address-BootBase)) : itcm.ReadWord((long)address);', ': inBoot ? boot.ReadWord((long)(address-BootBase)) : inPayload ? payloadWord : itcm.ReadWord((long)address);'),
      ('                var width = (first >> 11) >= 0x1d ? 4 : 2;', '''                var width = (first >> 11) >= 0x1d ? 4 : 2;
                if(inPayload && width==4)
                {
                    ushort nextWord;
                    if(!SramPayload.TryReadWord(address+2,out nextWord))Stop("execute-outside-code",address,4);
                }''')]
    # Attach belongs to several peripherals in the combined source; constrain all edits to this class.
    start=model.index('    public sealed class BlackwallMemoryPolicy : IPeripheral');end=model.index('\nnamespace ',start)
    section=model[start:end]
    for old,new in edits:
        if section.count(old)!=1:raise ValueError('Unique SRAM policy boundary required: '+old)
        section=section.replace(old,new)
    return model[:start]+section+model[end:]+'\n'+gate_source
