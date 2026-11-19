namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using Antmicro.Renode.Core;
    using Antmicro.Renode.Peripherals.CPU;
    using Antmicro.Renode.Peripherals.Bus;

    public sealed class BlackwallPendingRomProgram
    {
        public BlackwallPendingRomProgram(IMachine machine,CortexM cpu,BlackwallMemoryStartup power,BlackwallOtaMarkerRead marker,byte[] initial,string fault)
        {
            if(fault!="success" && fault!="rom-error" && fault!="interrupt-0" && fault!="interrupt-1" && fault!="stuck")throw new ArgumentException("Reviewed pending ROM fault required");
            this.machine=machine;this.cpu=cpu;this.power=power;this.fault=fault;
            State=new BlackwallPendingMetadata(initial);marker.BindPersistent(State);
            cpu.AddHook(0x0200ff20,(c,a)=>Program());
        }
        public void CheckEntry(uint instructions)
        {
            Entries++;BlockInstructions=instructions;var bus=machine.SystemBus;
            Key=(uint)cpu.GetRegister(0).RawValue;Operation=(uint)cpu.GetRegister(1).RawValue;Source=(uint)cpu.GetRegister(2).RawValue;Offset=(uint)cpu.GetRegister(3).RawValue;
            Words=bus.ReadDoubleWord(cpu.GetRegister(13).RawValue);Primask=(uint)cpu.GetRegister(28).RawValue;
            // The pinned engine emits a zero-instruction block for this PC hook.
            // Permit that model boundary only; executing even the backend trap is rejected.
            if(instructions!=0 || Entries!=1 || Key!=0x12344321 || Operation!=1 || Source!=0x20022d68 || Offset!=0xff800 || Words!=4 || Primask!=1)
            {Violation=true;throw new CpuAbortException("Pending metadata ROM ABI/range boundary");}
            Payload=bus.ReadBytes(Source,16,true);
            foreach(var b in Payload)if(b!=255){Violation=true;throw new CpuAbortException("Unexpected metadata payload");}
            if((power.Registers[0x40021018].Value&0x80)==0){Unready=true;throw new CpuAbortException("Pending ROM not ready");}
            if(fault.StartsWith("interrupt-"))
            {ProgrammedWords=fault=="interrupt-1"?1:0;State.Program(Payload,ProgrammedWords);Interrupted=true;throw new CpuAbortException("Declared virtual MRAM interruption");}
        }
        private void Program()
        {
            if(Entries!=1 || Violation || Unready || Interrupted)throw new InvalidOperationException("Unvalidated ROM execution");
            Calls++;Status=fault=="rom-error"?7u:0u;
            if(Status==0){State.Program(Payload,4);ProgrammedWords=4;}
            cpu.SetRegister(0,Status);cpu.PC=cpu.GetRegister(14).RawValue;
        }
        public BlackwallPendingMetadata State {get;}
        public uint Entries {get;private set;}public uint Calls {get;private set;}public uint Status {get;private set;}
        public uint BlockInstructions {get;private set;}
        public uint Key {get;private set;}public uint Operation {get;private set;}public uint Source {get;private set;}public uint Offset {get;private set;}public uint Words {get;private set;}public uint Primask {get;private set;}
        public int ProgrammedWords {get;private set;}
        public bool Violation {get;private set;}public bool Unready {get;private set;}public bool Interrupted {get;private set;}
        public byte[] Payload {get;private set;}
        private readonly IMachine machine;private readonly CortexM cpu;private readonly BlackwallMemoryStartup power;private readonly string fault;
    }
}
