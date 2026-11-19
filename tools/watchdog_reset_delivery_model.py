"""Opt-in main-only virtual boot cause and synchronized watchdog reset delivery."""
from pathlib import Path
import hashlib

PINS={'renode-watchdog.cs': '4a57f77ff0223a891a984482daef98f416a1099d7f93b63c3d1dd9cbc6a4c01b', 'renode-reset-controller.cs': '3ad7f301f4e97cd3a3c1885f1122c9fbd1fa2121faf76bf172072a9c04949b8a'}

def compose(model):
 root=Path(__file__).parent
 wd=(root/'renode-watchdog.cs').read_text();rst=(root/'renode-reset-controller.cs').read_text()
 if any(hashlib.sha256((root/n).read_bytes()).hexdigest()!=h for n,h in PINS.items()):raise ValueError('Changed pinned watchdog reset source')
 def once(source,old,new):
  if source.count(old)!=1:raise ValueError('Unknown watchdog reset boundary '+old[:70])
  return source.replace(old,new,1)
 # Baseline sources stay byte-for-byte intact on disk.
 if model.count(wd)!=1 or model.count(rst)!=1:raise ValueError('Expected one watchdog and reset controller')
 new=once(rst,'public BlackwallResetController() : base(0x1000, 0x40000000) { Reset(); }','''public BlackwallResetController(bool mainOnlyWatchdogBootContract=false) : base(0x1000, 0x40000000)
        {
            MainOnlyWatchdogBootContract=mainOnlyWatchdogBootContract;
            Reset();
        }
        public bool MainOnlyWatchdogBootContract {get;}
        public uint VirtualBootStatus {get;private set;}
        public uint WatchdogResetDeliveries {get;private set;}
        public bool WatchdogResetPending {get;private set;}
        public void PrepareWatchdogReset()
        {
            if(!MainOnlyWatchdogBootContract || !WatchdogResetEnabled || WatchdogResetPending)
                throw new System.InvalidOperationException("Watchdog reset requires an enabled declared virtual boot contract and no pending delivery");
            WatchdogResetPending=true;
            WatchdogResetDeliveries++;
        }''')
 new=once(new,'            Configuration = 0;','''            // Main-only boot handoff, not execution of the physical boot ROM/SBL.
            VirtualBootStatus=WatchdogResetPending ? 0x40u : 0;
            WatchdogResetPending=false;
            Configuration = 0;''')
 model=model.replace(rst,new,1)
 new=once(wd,'BlackwallResetController resetController = null) :','BlackwallResetController resetController = null, bool propagateSystemReset = false) :')
 new=once(new,'            this.machine = machine;','''            if(propagateSystemReset && (resetController==null || !resetController.MainOnlyWatchdogBootContract))
                throw new System.ArgumentException("Reset delivery requires the explicit main-only virtual boot contract");
            this.propagateSystemReset=propagateSystemReset;
            this.machine = machine;''')
 new=once(new,'                machine.PauseAndRequestEmulationPause();','''                if(propagateSystemReset && ResetAllowedByGate)
                {
                    resetController.PrepareWatchdogReset();
                    machine.RequestReset();
                }
                else machine.PauseAndRequestEmulationPause();''')
 new=once(new,'        private bool pending, interruptEnabled;','''        public bool PropagateSystemReset => propagateSystemReset;
        private readonly bool propagateSystemReset;
        private bool pending, interruptEnabled;''')
 new=once(new,'        public string ResetPropagation => resetController == null','''        public string ResetPropagation => propagateSystemReset
            ? "virtual synchronized machine reset; main-only boot cause contract, physical domains unverified"
            : resetController == null''')
 return model.replace(wd,new,1)+"""
namespace Antmicro.Renode.Peripherals.Miscellaneous {
 public sealed class BlackwallVirtualResetBootStatus : BlackwallStrictMMIO {
  public BlackwallVirtualResetBootStatus(BlackwallResetController resetController) : base(4,0x4000885c) {
   if(resetController==null || !resetController.MainOnlyWatchdogBootContract)throw new System.ArgumentException("Explicit main-only boot contract required");
   this.resetController=resetController;
  }
  public override uint ReadDoubleWord(long offset) {
   if(offset==0)return resetController.VirtualBootStatus;
   return base.ReadDoubleWord(offset);
  }
  private readonly BlackwallResetController resetController;
 }
}
"""
