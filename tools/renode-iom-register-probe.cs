namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using Antmicro.Renode.Peripherals.I2C;

    // Explicit synthetic version/config and optional one-frame input; no physical defaults or DFU.
    public sealed class BlackwallIomRegisterProbe : II2CPeripheral
    {
        public BlackwallIomRegisterProbe(BlackwallStrictIom owner,string profile,int initialGestureThreshold=-1,bool eventPointerProbe=false,string eventFrameHex=null,bool reusableEventFrames=false)
        {
            if(owner==null || owner.Module!=5 || (profile!="pointer-01-only" && profile!="package-version-only" && profile!="touch-startup-config"))throw new ArgumentException("Explicit IOM5 diagnostic profile required");
            if(profile=="touch-startup-config" ? initialGestureThreshold<0 || initialGestureThreshold>65535 : initialGestureThreshold!=-1)throw new ArgumentException("Explicit startup threshold required only for touch-startup-config");
            if(eventPointerProbe && profile!="touch-startup-config")throw new ArgumentException("Event pointer probe requires explicit startup profile");
            if(reusableEventFrames && eventFrameHex==null)throw new ArgumentException("Reusable event reports require an initial declared frame");
            if(eventFrameHex!=null)
            {
                if(!eventPointerProbe || eventFrameHex.Length!=32)throw new ArgumentException("One explicit 16-byte event requires the startup event profile");
                foreach(var c in eventFrameHex)if(!Uri.IsHexDigit(c))throw new ArgumentException("Event frame must be hexadecimal");
                eventFrame=new byte[16];
                for(var i=0;i<16;i++)eventFrame[i]=Convert.ToByte(eventFrameHex.Substring(i*2,2),16);
                initialEventFrame=(byte[])eventFrame.Clone();
            }
            this.owner=owner;Profile=profile;InitialGestureThreshold=initialGestureThreshold;EventPointerProbe=eventPointerProbe;ReusableEventFrames=reusableEventFrames;Reset();
        }
        public void Reset()
        {
            PointerSelected=false;Pointer=0;PointerWrites=ReadAttempts=Finishes=LastReadCount=VersionReads=ReturnedBytes=GestureReads=ConfigWrites=StatusReads=0;LastReadPointer=-1;readConsumed=false;ConfigReplyPending=false;GestureThreshold=InitialGestureThreshold<0 ? (ushort)0:(ushort)InitialGestureThreshold;
            EventReadOffset=EventReadChunks=EventFramesCompleted=EventFrameReloads=0;
            if(EventFrameEnabled)Array.Copy(initialEventFrame,eventFrame,16);
        }
        public bool TryLoadEventFrame(byte[] data)
        {
            if(!ReusableEventFrames || data==null || data.Length!=16 || ConfigReplyPending
                || EventReadOffset!=16 || !readConsumed || !owner.Quiescent)return false;
            Array.Copy(data,eventFrame,16);
            EventReadOffset=0;EventFrameReloads++;
            // A new pointer write must select this report, even if the old pointer was 03.
            readConsumed=true;
            return true;
        }
        public void Write(byte[] data)
        {
            if(EventFrameEnabled && ((EventReadOffset>0 && EventReadOffset<16) ||
                (data!=null && data.Length==1 && data[0]==3 && EventFramesCompleted!=0 && (!ReusableEventFrames || EventReadOffset==16))))
            { owner.RejectDiagnosticPeerAccess("peer-write",data==null ? 0u:(uint)data.Length);return; }
            if(Profile=="touch-startup-config" && !ConfigReplyPending && data!=null && data.Length==3 && data[0]==7)
            {
                var threshold=(ushort)(data[1]|(data[2]<<8));
                if(threshold==0) {owner.RejectDiagnosticPeerAccess("peer-write",3);return;}
                GestureThreshold=threshold;ConfigWrites++;ConfigReplyPending=true;Pointer=7;PointerSelected=true;readConsumed=false;return;
            }
            if(ConfigReplyPending || data==null || data.Length!=1 || (data[0]!=1 && !(Profile=="touch-startup-config" && (data[0]==8 || (EventPointerProbe && data[0]==3)))))
            {
                owner.RejectDiagnosticPeerAccess("peer-write",data==null ? 0u:(uint)data.Length);return;
            }
            Pointer=data[0];PointerSelected=true;PointerWrites++;readConsumed=false;
        }
        public byte[] Read(int count=1)
        {
            ReadAttempts++;LastReadCount=count;LastReadPointer=PointerSelected ? (int)Pointer:-1;
            if(EventFrameEnabled && PointerSelected && Pointer==3 && !readConsumed && count==4)
            {
                // Inspect the existing engine's read-only CMDSTATUS, without adding a guest read.
                var status=((Antmicro.Renode.Peripherals.SPI.BlackwallPollingIomEngine)owner).ReadDoubleWord(0x12c);
                if((status&31)!=2 || ((status>>8)&0xfff)!=(uint)(16-EventReadOffset))
                { owner.RejectDiagnosticPeerAccess("peer-read",unchecked((uint)count));return new byte[0]; }
                var chunk=new byte[4];Array.Copy(eventFrame,EventReadOffset,chunk,0,4);
                EventReadOffset+=4;EventReadChunks++;ReturnedBytes+=4;
                if(EventReadOffset==16) { readConsumed=true;EventFramesCompleted++; }
                return chunk;
            }
            if(ConfigReplyPending && count==3)
            {
                ConfigReplyPending=false;readConsumed=true;StatusReads++;ReturnedBytes+=3;
                return new byte[] {7,0,0x17};
            }
            if(Profile=="touch-startup-config" && PointerSelected && Pointer==8 && !readConsumed && count==2)
            {
                readConsumed=true;GestureReads++;ReturnedBytes+=2;
                return new byte[] {(byte)GestureThreshold,(byte)(GestureThreshold>>8)};
            }
            if(Profile!="pointer-01-only" && PointerSelected && Pointer==1 && !readConsumed && count==4)
            {
                readConsumed=true;VersionReads++;ReturnedBytes+=4;
                return new byte[] {2,2,9,0};
            }
            owner.RejectDiagnosticPeerAccess("peer-read",unchecked((uint)count));
            return new byte[0];
        }
        public void FinishTransmission() { Finishes++; }
        public bool PointerSelected {get;private set;}
        public byte Pointer {get;private set;}
        public int PointerWrites {get;private set;}
        public int ReadAttempts {get;private set;}
        public int LastReadCount {get;private set;}
        public int LastReadPointer {get;private set;}
        public int Finishes {get;private set;}
        public string Profile {get;}
        public int VersionReads {get;private set;}
        public int ReturnedBytes {get;private set;}
        public int InitialGestureThreshold {get;}
        public ushort GestureThreshold {get;private set;}
        public int GestureReads {get;private set;}
        public int ConfigWrites {get;private set;}
        public int StatusReads {get;private set;}
        public bool ConfigReplyPending {get;private set;}
        public bool EventPointerProbe {get;}
        public bool ReusableEventFrames {get;}
        public bool EventFrameEnabled=>eventFrame!=null;
        public int EventReadOffset {get;private set;}
        public int EventReadChunks {get;private set;}
        public int EventFramesCompleted {get;private set;}
        public int EventFrameReloads {get;private set;}
        private readonly byte[] eventFrame,initialEventFrame;
        private bool readConsumed;
        private readonly BlackwallStrictIom owner;
    }
}
