namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals.CPU;
    using Antmicro.Renode.Peripherals.Memory;
    using Antmicro.Renode.Peripherals.Bus;
    public sealed class BlackwallBoundedMainRom
    {
        public BlackwallBoundedMainRom(IMachine machine,CortexM cpu,MappedMemory main,BlackwallMemoryStartup power,byte[] expected,uint status=0)
        {
            if(expected==null || expected.Length!=16 || status!=0 && status!=7)throw new ArgumentException("Reviewed 16-byte main ROM contract required");
            this.machine=machine;this.cpu=cpu;this.main=main;this.power=power;this.expected=(byte[])expected.Clone();Status=status;
            cpu.AddHook(0x0200ff20,(c,a)=>Program());
        }
        public void CheckEntry(uint instructions)
        {
            Entries++;BlockInstructions=instructions;var bus=machine.SystemBus;
            Key=cpu.GetRegister(0).RawValue;Operation=cpu.GetRegister(1).RawValue;Source=cpu.GetRegister(2).RawValue;WordOffset=cpu.GetRegister(3).RawValue;
            WordCount=bus.ReadDoubleWord(cpu.GetRegister(13).RawValue);Primask=cpu.GetRegister(28).RawValue;
            if(instructions!=0 || Entries!=1 || !BlackwallMramRangeContract.ValidProgramRequest(Key,Operation,WordOffset,WordCount,Source,Primask==1,0x438010,16))Fail("ROM ABI/range");
            if((power.Registers[0x40021018].Value&0x80)==0)Fail("ROM power unready");
            Payload=bus.ReadBytes(Source,16,true);
            for(var i=0;i<16;i++)if(Payload[i]!=expected[i])Fail("ROM input differs from approved source");
            Validated=true;
        }
        private void Fail(string why){Violation=true;Failure=why;throw new CpuAbortException("Bounded main ROM "+why);}
        private void Program()
        {
            if(!Validated || Violation || Calls!=0){Violation=true;Failure="Unvalidated ROM model execution";cpu.IsHalted=true;machine.PauseAndRequestEmulationPause();return;}
            Calls++;
            if(Status==0)
            {
                for(var i=0;i<16;i+=4){main.WriteDoubleWord(16+i,BitConverter.ToUInt32(Payload,i));ProgrammedBytes+=4;}
                cpu.OrderTranslationBlocksInvalidation(new IntPtr(0x438010),new IntPtr(0x438020));
            }
            cpu.SetRegister(0,Status);cpu.PC=cpu.GetRegister(14).RawValue;
        }
        public bool AllowInvalidation(ulong line)=>Validated&&!Violation&&ProgrammedBytes==16&&line==0x438000;
        public ulong Key{get;private set;}public ulong Operation{get;private set;}public ulong Source{get;private set;}public ulong WordOffset{get;private set;}public uint WordCount{get;private set;}public ulong Primask{get;private set;}
        public uint Entries{get;private set;}public uint Calls{get;private set;}public uint BlockInstructions{get;private set;}public uint ProgrammedBytes{get;private set;}public uint Status{get;}
        public bool Validated{get;private set;}public bool Violation{get;private set;}public string Failure{get;private set;}="none";public byte[] Payload{get;private set;}
        private readonly IMachine machine;private readonly CortexM cpu;private readonly MappedMemory main;private readonly BlackwallMemoryStartup power;private readonly byte[] expected;
    }
}
