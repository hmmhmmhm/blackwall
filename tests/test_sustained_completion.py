import copy,struct,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from audit_sustained_completion import ui_wait_list, resource_summary, profile_summary, uart_stream_witness

class WaitTests(unittest.TestCase):
 def test_declared_profiles_keep_mock_identity_explicit(self):
  plan=dict(status_profile={'hex':'5a01'},rtc_profile={'name':'independent-weekday'},controller_version_profile={'name':'startup-mock','identity':'0d34120d5a007856','limit':32,'physical_identity_verified':False},uart_capture_profile={'name':'bounded-prefix','module':0,'prefix_capacity':4096})
  self.assertTrue(profile_summary(plan)['full_integration'])
  selector=copy.deepcopy(plan);selector['controller_version_profile'].update(startup_command_profile='version-and-advertising-stop',advertising_disable_limit=1)
  self.assertTrue(profile_summary(selector)['full_integration'])
  selector['controller_version_profile']['advertising_disable_limit']=2
  with self.assertRaises(ValueError):profile_summary(selector)
  selector['controller_version_profile'].update(startup_command_profile='version-and-advertising-reconfigure',advertising_disable_limit=1,advertising_parameters_hex='0106200f400640060001000000000000000700')
  self.assertTrue(profile_summary(selector)['full_integration'])
  selector['controller_version_profile']['advertising_parameters_hex']='0106200f000000000000000000000000000000'
  with self.assertRaises(ValueError):profile_summary(selector)
  old=copy.deepcopy(plan);old.pop('rtc_profile');self.assertFalse(profile_summary(old)['full_integration'])
  for mutate in [lambda p:p['controller_version_profile'].update(physical_identity_verified=True),lambda p:p['uart_capture_profile'].update(prefix_capacity=8192),lambda p:p['rtc_profile'].update(name='guessed')]:
   bad=copy.deepcopy(plan);mutate(bad)
   with self.assertRaises(ValueError):profile_summary(bad)
 def test_uart_stream_recomputed_and_corruptions_denied(self):
  transfers=[dict(target=0x20001000,data=b'hello'.hex())]
  observed=dict(dma=dict(starts=1,completions=1,transferred_bytes=5),tx_total=5,tx_hash=0xa430d84680aabd0b,tx_bytes=5,tx_dropped=0,tx_truncated=False)
  self.assertTrue(uart_stream_witness(transfers,1,observed)['passed'])
  for mutate in [lambda o:o.update(tx_hash=0),lambda o:o.update(tx_total=6),lambda o:o.update(tx_dropped=1),lambda o:o['dma'].update(completions=0),lambda o:o.update(tx_bytes=4)]:
   bad=copy.deepcopy(observed);mutate(bad)
   with self.assertRaises(ValueError):uart_stream_witness(transfers,1,bad)
  with self.assertRaises(ValueError):uart_stream_witness([dict(target=0x2037ffff,data='0102')],1,observed)
  with self.assertRaises(ValueError):uart_stream_witness(transfers,0,observed)
 def test_resource_samples_are_filtered_and_units_explicit(self):
  rows=[{"stats":[{"Name":"mine","CPUPerc":"99.5%","MemUsage":"0.5GiB / 1GiB"},{"Name":"other","CPUPerc":"200%","MemUsage":"2GiB / 4GiB"}]}]
  x=resource_summary(rows,"mine");self.assertEqual(x["samples"],1);self.assertEqual(x["max_sampled_memory_mib"],512);self.assertEqual(x["max_sampled_cpu_percent"],99.5)
  self.assertEqual(resource_summary(rows,"absent")["samples"],0)
 def fixture(self):
  m=bytearray(4096);q=0x20000100;t=0x20000500;c=q+0x24;n=t+24;s=c+8
  def w(a,v):struct.pack_into('<I',m,a-0x20000000,v)
  for a,v in [(q+0x38,0),(q+0x3c,96),(q+0x40,12),(c,1),(s,0xffffffff),(s+4,n),(s+8,n),(n+4,s),(n+8,s),(n+12,t),(n+16,c),(t+16,t),(t+44,5)]:w(a,v)
  m[t-0x20000000+52:t-0x20000000+60]=b'ui_task\0'
  return m,q,t
 def test_waiting(self):
  m,q,t=self.fixture();x=ui_wait_list(m,q);self.assertTrue(x['passed']);self.assertEqual(x['owner'],t)
 def test_invalid_links_and_owner(self):
  for address in [0x20000500+28,0x20000500+36,0x20000500+40]:
   m,q,t=self.fixture();struct.pack_into('<I',m,address-0x20000000,0)
   with self.assertRaises(ValueError):ui_wait_list(m,q)
 def test_pending_or_missing_receiver(self):
  for offset,value in [(0x38,1),(0x3c,0),(0x24,0)]:
   m,q,t=self.fixture();struct.pack_into('<I',m,q+offset-0x20000000,value)
   with self.assertRaises(ValueError):ui_wait_list(m,q)

if __name__=='__main__':unittest.main()
