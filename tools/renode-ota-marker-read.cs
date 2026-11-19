namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using Antmicro.Renode.Peripherals;

    // Immutable by default; persistent virtual metadata requires an explicit binding.
    public sealed class BlackwallOtaMarkerRead : IPeripheral
    {
        public BlackwallOtaMarkerRead(string profile="unknown",uint startupPc=0,uint setterEntry=0,uint bootReadPc=0)
        {
            if(profile!="unknown" && profile!="cleared" && profile!="pending"
                || (profile!="unknown" || startupPc!=0 || setterEntry!=0)
                    && (!Valid(startupPc) || !Valid(setterEntry) || !Valid(setterEntry+0x56) || startupPc>=setterEntry && startupPc<=setterEntry+0x56))
                throw new ArgumentException("Explicit marker profile and distinct original read consumers required");
            if(bootReadPc!=0 && (bootReadPc<0x410000 || bootReadPc>=0x438000 || (bootReadPc&1)!=0))
                throw new ArgumentException("Boot marker requires an aligned original boot code consumer");
            Profile=profile;StartupPc=startupPc;SetterEntry=setterEntry;BootReadPc=bootReadPc;Reset();
        }
        private static bool Valid(uint pc)=>pc>=0x438000 && pc<0x800000 && (pc&1)==0;
        public void BindPersistent(BlackwallPendingMetadata state)
        {
            if(persistent!=null)throw new InvalidOperationException("Persistent metadata already bound");
            if(state==null || Profile=="unknown")throw new ArgumentException("Explicit known virtual metadata required");
            persistent=state;
        }
        public void Reset() { Reads=BootReads=StartupReads=SetterReads=LastReadPc=0; }
        public bool TrySample(uint pc,uint r0,uint r4,ulong address,out uint value)
        {
            value=0;
            if(Profile=="unknown" || address!=0x7fe000)return false;
            if(BootReadPc!=0 && pc==BootReadPc && r0==address)BootReads++;
            else if(pc==StartupPc && r0==address)StartupReads++;
            else if((pc==SetterEntry+0x12 || pc==SetterEntry+0x3e || pc==SetterEntry+0x56) && r4==address)SetterReads++;
            else return false;
            Reads++;LastReadPc=pc;value=persistent==null ? (Profile=="cleared"?0xffffffffu:0x55555555u) : persistent.Marker;return true;
        }
        public string Profile {get;}
        public uint StartupPc {get;}
        public uint SetterEntry {get;}
        public uint BootReadPc {get;}
        public uint BootReads {get;private set;}
        public uint Reads {get;private set;}
        public uint StartupReads {get;private set;}
        public uint SetterReads {get;private set;}
        public uint LastReadPc {get;private set;}
        private BlackwallPendingMetadata persistent;
    }
    public sealed class BlackwallPendingMetadata
    {
        public BlackwallPendingMetadata(byte[] initial)
        {
            if(initial==null || initial.Length!=16)throw new ArgumentException("Exact synthetic16byte metadata required");
            data=(byte[])initial.Clone();
        }
        public byte[] Bytes => (byte[])data.Clone();
        public uint Marker => (uint)(data[0]|data[1]<<8|data[2]<<16|data[3]<<24);
        public void Program(byte[] input,int words)
        {
            if(input==null || input.Length!=16 || words<0 || words>4)throw new ArgumentException("Bounded virtual metadata program required");
            Array.Copy(input,data,words*4);
        }
        private readonly byte[] data;
    }
}
