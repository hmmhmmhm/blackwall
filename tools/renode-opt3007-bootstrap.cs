namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using Antmicro.Renode.Peripherals.I2C;
    // TI SBOS864 register interface with an explicit instant, constant-light scenario.
    // No optical response, analog conversion timing, thresholds, or interrupt delivery.
    public sealed class BlackwallOpt3007Bootstrap : II2CPeripheral
    {
        public BlackwallOpt3007Bootstrap(BlackwallStrictIom owner,int resultWord=0)
        {
            if(owner==null || owner.Module!=2 || resultWord<0 || resultWord>0xbfff)throw new ArgumentException("IOM2 and explicit bounded OPT3007 light sample required");
            this.owner=owner;ResultWord=(ushort)resultWord;Reset();
        }
        public void Reset(){Pointer=cursor=0;configuration=0xc810;low=0xc000;high=0xbfff;Reads=Writes=Rejections=0;}
        private static bool Known(int address)=>address>=0 && address<=3 || address==0x7e || address==0x7f;
        public bool TryWrite(byte[] data)
        {
            if(data==null || (data.Length!=1 && data.Length!=3) || !Known(data[0]))return false;
            if(data.Length==3)
            {
                if(data[0]<1 || data[0]>3)return false;
                ushort value=(ushort)((data[1]<<8)|data[2]);
                if(data[0]==1)configuration=(ushort)(value&0xfe1f);
                else if(data[0]==2)low=value;else high=value;
            }
            Pointer=data[0];cursor=0;Writes++;return true;
        }
        public bool TryRead(int count,out byte[] data)
        {
            data=null;if(count<1 || count>2 || cursor+count>2)return false;
            ushort value=Pointer==0 ? ResultWord:Pointer==1 ? (ushort)(configuration|((configuration&0x600)!=0 ? 0x80:0)):
                Pointer==2 ? low:Pointer==3 ? high:Pointer==0x7e ? (ushort)0x5449:(ushort)0x3001;
            data=new byte[count];for(int k=0;k<count;k++)data[k]=(byte)(value>>(8*(1-cursor-k)));
            cursor+=count;Reads++;return true;
        }
        public void Write(byte[] data){if(!TryWrite(data)){Rejections++;owner.RejectDiagnosticPeerAccess("opt3007-write",data==null?0u:(uint)data.Length);}}
        public byte[] Read(int count=1){if(TryRead(count,out var data))return data;Rejections++;owner.RejectDiagnosticPeerAccess("opt3007-read",(uint)count);return new byte[0];}
        public void FinishTransmission(){cursor=0;}
        public string FunctionalProfile=>"constant-light-instant-conversion-v1";
        public ushort ResultWord {get;}
        public int Pointer {get;private set;}
        public int Reads {get;private set;}
        public int Writes {get;private set;}
        public int Rejections {get;private set;}
        private int cursor;private ushort configuration,low,high;
        private readonly BlackwallStrictIom owner;
    }
}
