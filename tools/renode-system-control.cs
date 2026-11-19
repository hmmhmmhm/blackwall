namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Core.Structure.Registers;
    using Antmicro.Renode.Peripherals.CPU;
    using Antmicro.Renode.Peripherals.IRQControllers;

    public sealed class BlackwallSystemControl
    {
        public BlackwallSystemControl(IMachine machine,CortexM cpu,NVIC nvic,bool coherentICache,bool coherentDCache=false,bool sramAddressMaintenance=false)
        {
            if(coherentDCache && !coherentICache) throw new ArgumentException("Data cache requires coherent instruction memory");
            if(sramAddressMaintenance && !coherentDCache) throw new ArgumentException("SRAM address maintenance requires coherent data cache");
            this.machine=machine;this.cpu=cpu;this.nvic=nvic;FunctionalICache=coherentICache;
            DataCache=coherentDCache ? new BlackwallCoherentDataCache(sramAddressMaintenance) : null;
        }
        public void Attach()
        {
            if(attached) throw new InvalidOperationException("System control already attached");
            nvic.RegisterCollection.DefineRegister(0xf50).WithValueField(0,32,FieldMode.Write,name:"functional_ICIALLU");
            foreach(var offset in new long[]{0xf5c,0xf60,0xf64,0xf68,0xf6c,0xf70,0xf74})
                nvic.RegisterCollection.DefineRegister(offset).WithValueField(0,32,FieldMode.Write,name:"guarded_data_maintenance");
            var bus=machine.SystemBus;
            bus.SetHookBeforePeripheralWrite<byte>(nvic,(v,o)=>(byte)Write(o,1,v));
            bus.SetHookBeforePeripheralWrite<ushort>(nvic,(v,o)=>(ushort)Write(o,2,v));
            bus.SetHookBeforePeripheralWrite<uint>(nvic,(v,o)=>(uint)Write(o,4,v));
            bus.SetHookBeforePeripheralWrite<ulong>(nvic,(v,o)=>Write(o,8,v));
            bus.SetHookAfterPeripheralRead<byte>(nvic,(v,o)=>(byte)Read(o,1,v));
            bus.SetHookAfterPeripheralRead<ushort>(nvic,(v,o)=>(ushort)Read(o,2,v));
            bus.SetHookAfterPeripheralRead<uint>(nvic,(v,o)=>(uint)Read(o,4,v));
            bus.SetHookAfterPeripheralRead<ulong>(nvic,(v,o)=>Read(o,8,v));
            machine.PeripheralReset += (m,peripheral) =>
            {
                if(!ReferenceEquals(peripheral,cpu)) return;
                ICacheEnabled=false;
                Invalidations=CcrReads=CcrWrites=0;
                DataCache?.Reset();
            };
            attached=true;
        }
        private static bool Touches(long o,int width,long target) => o < target+4 && o+width > target;
        private ulong Read(long offset,int width,ulong value)
        {
            if(offset < 0xd88 && offset+width > 0xd80)
            {
                if(DataCache!=null && DataCache.TryRead(offset,width,out var geometry)) return geometry;
                Stop("read",offset,width,0);
            }
            if(offset < 0xf78 && offset+width > 0xf58) Stop("read",offset,width,0);
            if(Touches(offset,width,0xf50)) Stop("read",offset,width,0);
            if(Touches(offset,width,0xd14))
            {
                if(offset!=0xd14 || width!=4) Stop("read",offset,width,0);
                CcrReads++;
                if(FunctionalICache) return (value & ~(IC|DC)) | (ICacheEnabled ? IC : 0)
                    | (DataCache!=null && DataCache.Enabled ? DC : 0);
            }
            return value;
        }
        private ulong Write(long offset,int width,ulong value)
        {
            if((offset < 0xd88 && offset+width > 0xd80) || (offset < 0xf78 && offset+width > 0xf58))
            {
                if(DataCache!=null && DataCache.TryWrite(offset,width,value)) return 0;
                Stop("write",offset,width,value);
            }
            if(Touches(offset,width,0xf50))
            {
                if(!FunctionalICache || offset!=0xf50 || width!=4 || value!=0) Stop("write",offset,width,value);
                Invalidations++;
                return 0;
            }
            if(Touches(offset,width,0xd14))
            {
                if(offset!=0xd14 || width!=4) Stop("write",offset,width,value);
                if(!FunctionalICache)
                {
                    if((value & (IC|DC))!=0) Stop("write",offset,width,value);
                    return value;
                }
                var current=(ulong)cpu.ConfigurationAndControlRegister & ~(IC|DC);
                if((value & ~(IC|DC))!=current || ((value & IC)!=0 && Invalidations==0)
                    || ((value & DC)!=0 && DataCache==null)
                    || (DataCache!=null && !DataCache.CanSetEnabled((value & DC)!=0)))
                    Stop("write",offset,width,value);
                ICacheEnabled=(value & IC)!=0;
                if(DataCache!=null) DataCache.SetEnabled((value & DC)!=0);
                CcrWrites++;
                return value & ~(IC|DC);
            }
            return value;
        }
        private void Stop(string operation,long offset,int width,ulong value)
        {
            Violations++; LastOperation=operation;LastAddress=0xe000e000+(ulong)offset;
            LastWidth=width;LastValue=value;LastPC=cpu.PC.RawValue;
            throw new CpuAbortException("BLACKWALL unsupported system control");
        }
        public bool FunctionalICache { get; }
        public BlackwallCoherentDataCache DataCache { get; }
        public bool ICacheEnabled { get; private set; }
        public int Invalidations { get; private set; }
        public int CcrReads { get; private set; }
        public int CcrWrites { get; private set; }
        public int Violations { get; private set; }
        public string LastOperation { get; private set; }="none";
        public ulong LastAddress { get; private set; }
        public ulong LastPC { get; private set; }
        public ulong LastValue { get; private set; }
        public int LastWidth { get; private set; }
        private const ulong IC=1UL<<17,DC=1UL<<16;
        private readonly IMachine machine;
        private readonly CortexM cpu;
        private readonly NVIC nvic;
        private bool attached;
    }

    public sealed class BlackwallCoherentDataCache
    {
        public BlackwallCoherentDataCache(bool sramAddressMaintenance=false) { SramAddressMaintenance=sramAddressMaintenance; }
        public void Reset()
        {
            Enabled=Selected=false;
            Array.Clear(initialized,0,initialized.Length);
            InitializedLines=SelectorReads=SelectorWrites=GeometryReads=Invalidations=Cleans=CleanInvalidations=0;
            AddressInvalidations=AddressCleans=AddressCleanInvalidations=AddressUnificationCleans=0;
            LastAddressLine=0;
        }
        public bool TryRead(long offset,int width,out ulong value)
        {
            value=0;
            if(width!=4 || !Selected) return false;
            if(offset==0xd84) { SelectorReads++; return true; }
            if(offset==0xd80) { GeometryReads++; value=0xf03fe019; return true; }
            return false;
        }
        public bool TryWrite(long offset,int width,ulong value)
        {
            if(width!=4) return false;
            if(offset==0xf5c || offset==0xf64 || offset==0xf68 || offset==0xf70)
            {
                var line=value&~31UL;
                if(!SramAddressMaintenance || value>uint.MaxValue || line<0x20000000 || line>=0x20380000)return false;
                if(offset==0xf5c)AddressInvalidations++;
                else if(offset==0xf64)AddressUnificationCleans++;
                else if(offset==0xf68)AddressCleans++;
                else AddressCleanInvalidations++;
                LastAddressLine=line; return true;
            }
            if(offset==0xd84 && value==0) { Selected=true; SelectorWrites++; return true; }
            if(!Selected || (value & ~0xc0003fe0UL)!=0) return false;
            if(offset==0xf60) Invalidations++;
            else if(offset==0xf6c) Cleans++;
            else if(offset==0xf74) CleanInvalidations++;
            else return false;
            if(offset!=0xf6c)
            {
                var index=(int)(((value>>5)&511)*4+(value>>30));
                if(!initialized[index]) { initialized[index]=true; InitializedLines++; }
            }
            return true;
        }
        public bool CanSetEnabled(bool enabled) => !enabled || Enabled || InitializedLines==2048;
        public void SetEnabled(bool enabled)
        {
            if(!CanSetEnabled(enabled)) throw new InvalidOperationException("Data cache not initialized");
            if(Enabled && !enabled) { Array.Clear(initialized,0,initialized.Length); InitializedLines=0; }
            Enabled=enabled;
        }
        public bool Enabled { get; private set; }
        public bool SramAddressMaintenance { get; }
        public ulong LastAddressLine { get; private set; }
        public int AddressInvalidations { get; private set; }
        public int AddressUnificationCleans { get; private set; }
        public int AddressCleans { get; private set; }
        public int AddressCleanInvalidations { get; private set; }
        public bool Selected { get; private set; }
        public int SelectorReads { get; private set; }
        public int SelectorWrites { get; private set; }
        public int GeometryReads { get; private set; }
        public int InitializedLines { get; private set; }
        public int Invalidations { get; private set; }
        public int Cleans { get; private set; }
        public int CleanInvalidations { get; private set; }
        private readonly bool[] initialized=new bool[2048];
    }
}
