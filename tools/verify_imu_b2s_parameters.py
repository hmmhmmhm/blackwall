"""Check ordered eight-field parameter storage without rewriting opaque program bytes."""
import verify_imu_patch_ram as patch
harness=patch.harness
harness.DRIVER=harness.DRIVER.replace('p=BlackwallImuPatchRam(owner,dhex,fhex,-1)','p=BlackwallImuPatchRam(owner,dhex,fhex,-1,True)')
EXTRA='''
check('b2s-no-outside-field',not p.TryWrite(0x1616,0xff) and p.ParameterBytes==0)
check('b2s-no-field-skip',not p.TryWrite(0x161c,1) and p.ParameterBytes==0)
check('b2s-select-read-before-write',p.BeginRead(0x1618) and p.ReadNext()==24 and p.ReadRemaining>0)
fields=[0x1618,0x1619,0x161a,0x161b,0x161c,0x161d,0x161e,0x161f,0x1614,0x1615,0x163c,0x163d,0x163e,0x163f,0x1640,0x1641,0x1642,0x1643,0x1638,0x1639]
for k,address in enumerate(fields):check('b2s-field-byte',p.TryWrite(address,0x80+k) and owner.RamByte(address)==0x80+k)
check('b2s-parameter-complete',p.ParameterBytes==20 and p.WrittenBytes==424 and p.ReadRemaining==0 and p.Loaded)
check('b2s-no-second-copy',not p.TryWrite(0x1618,1) and p.ParameterBytes==20)
check('b2s-neighbors',owner.RamByte(0x1613)==19 and owner.RamByte(0x1616)==22 and owner.RamByte(0x163a)==58 and owner.RamByte(0x1644)==68)
'''
harness.DRIVER=harness.DRIVER.replace('for marker in [0x801570f1,1]:',EXTRA+'\nfor marker in [0x801570f1,1]:')
if __name__=='__main__':harness.main()
