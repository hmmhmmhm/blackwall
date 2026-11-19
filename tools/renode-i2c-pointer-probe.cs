namespace Antmicro.Renode.Peripherals.Miscellaneous
{
using System;
using Antmicro.Renode.Peripherals.I2C;
using Antmicro.Renode.Peripherals.CPU;
    // Explicit synthetic pointer and optional two-bit ADC config; not a PMIC model.
    public sealed class BlackwallI2cPointerProbe : II2CPeripheral
    {
        public BlackwallI2cPointerProbe(int adcConfig=-1)
        {
            if(adcConfig < -1 || adcConfig > 3) throw new ArgumentException("Explicit ADC config must be -1 (unknown) or 0..3");
            InitialAdcConfig=adcConfig; Reset();
        }
        public void Reset()
        {
            Pointer=-1; Writes=Finishes=ReadAttempts=ReturnedReads=AccessCount=0;
            LastAddress=LastValue=0; LastWidth=0; LastOperation="none"; pending=false;
        }
        private void Block(string operation,int length,ulong value=0)
        {
            AccessCount++; LastAddress=Pointer<0 ? 0ul : (ulong)Pointer;
            LastWidth=length; LastOperation=operation; LastValue=value;
            throw new CpuAbortException("Blackwall pointer probe unsupported "+operation);
        }
        public void Write(byte[] data)
        {
            if(pending || data==null || data.Length!=2 || data[0]!=5 || data[1]!=9)
            {
                Block("peer-write-unsupported",data==null ? 0 : data.Length, data!=null && data.Length>=2 ? (ulong)((data[0]<<8)|data[1]) : 0);
                return;
            }
            Pointer=0x0509; Writes++; pending=true;
        }
        public byte[] Read(int count=1)
        {
            ReadAttempts++;
            if(!pending && Pointer==0x0509 && count==1 && InitialAdcConfig>=0)
            {
                pending=true; ReturnedReads++;
                return new byte[] { (byte)InitialAdcConfig };
            }
            Block("peer-read-unknown",count);
            return null;
        }
        public void FinishTransmission()
        {
            if(!pending) { Block("peer-finish-without-pointer",0);return; }
            pending=false; Finishes++;
        }
        public int InitialAdcConfig {get;}
        public int ReturnedReads {get;private set;}
        public int Pointer {get;private set;}
        public int Writes {get;private set;}
        public int Finishes {get;private set;}
        public int ReadAttempts {get;private set;}
        public int AccessCount {get;private set;}
        public ulong LastAddress {get;private set;}
        public int LastWidth {get;private set;}
        public ulong LastValue {get;private set;}
        public string LastOperation {get;private set;}
        private bool pending;
    }
}
