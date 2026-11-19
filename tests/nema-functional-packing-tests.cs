using System;using System.Linq;using System.Collections.Generic;using System.Reflection;
using Antmicro.Renode.Peripherals.Miscellaneous;
public static class PackingTests {
 static void Check(bool b,string s){if(!b)throw new Exception(s);checks++;}static int checks;
 public static void Run(){uint start=0x20001000,cl=0x20002000;uint[] words=new uint[]{0U,536887296U,4U,889192450U,8U,65540U,272U,0U,276U,65538U,32U,536887296U,36U,1157627906U,40U,65538U,272U,0U,276U,65538U,16U,536883200U,20U,872415236U,24U,65544U,372U,0U,360U,3221225472U,352U,1082130432U,356U,0U,364U,0U,368U,1065353216U,464U,1U,280U,0U,196U,0U,200U,135004418U,204U,2315739591U,284U,404717568U,28U,4278190080U,260U,0U,264U,65538U,4278190336U,2U,16U,536883200U,20U,889192452U,24U,65544U,372U,0U,360U,0U,352U,1082130432U,356U,0U,364U,0U,368U,1065353216U,464U,257U,280U,0U,196U,0U,200U,135004418U,204U,2147967365U,284U,404717568U,516U,0U,472U,0U,260U,0U,264U,65538U,4278190336U,2U,272U,0U,276U,65538U};
 foreach(bool enabled in new[]{false,true})for(int v=0;v<256;v++){
 var ram=new byte[0x10000];Action<uint,uint> put=(a,b)=>Buffer.BlockCopy(BitConverter.GetBytes(b),0,ram,(int)(a-0x20000000),4);
 var prefix=(uint[])typeof(NemaRingConsumer).GetMethod("InitialWords",BindingFlags.NonPublic|BindingFlags.Static).Invoke(null,null);
 for(int k=0;k<prefix.Length;k++)put(start+(uint)k*4,prefix[k]);uint at=start+(uint)prefix.Length*4;
 put(at,0xf0);put(at+4,cl);put(at+8,0x200f4);put(at+12,(uint)words.Length);
 for(int k=0;k<words.Length;k++)put(cl+(uint)k*4,words[k]);
 ram[0x3000]=(byte)v;ram[0x3001]=(byte)(255-v);ram[0x3002]=(byte)(v^0xa5);ram[0x3003]=(byte)(v^0x5a);
 ram[0x4000]=0x7b;ram[0x4001]=0x4d;var before=(byte[])ram.Clone();
 var e=new NemaRingConsumer(start,4096,(a,n)=>ram.Skip((int)(a-0x20000000)).Take(n).ToArray(),(a,b)=>Buffer.BlockCopy(b,0,ram,(int)(a-0x20000000),b.Length),false,enabled);
 bool rejected=false;try{e.Submit((at+16)|4);}catch(InvalidOperationException){rejected=true;}
 if(!enabled){Check(rejected && ram.SequenceEqual(before) && e.Draws==0,"strict atomic rejection");continue;}
 Check(!rejected && e.Draws==2 && e.PixelsWritten==4,"two passes");
 Check(ram[0x4000]==((v&0xf0)|((255-v)>>4)),"pair0");Check(ram[0x4001]==(((v^0xa5)&0xf0)|((v^0x5a)>>4)),"pair1");
 Check(e.LastSurfaceWidth==2 && e.LastSurfaceHeight==1 && e.LastSurfaceStride==2,"packed dimensions");
 Check(e.PackingSubmits==1 && e.LastPackingSource==0x20003000 && e.LastPackingStride==4 && e.LastPackingWidth==4 && e.LastPackingHeight==1,"completed packing provenance");
 }
 foreach(int mutation in new[]{0,1,2}){
 var ram=new byte[0x10000];Action<uint,uint> put=(a,b)=>Buffer.BlockCopy(BitConverter.GetBytes(b),0,ram,(int)(a-0x20000000),4);
 var prefix=(uint[])typeof(NemaRingConsumer).GetMethod("InitialWords",BindingFlags.NonPublic|BindingFlags.Static).Invoke(null,null);
 for(int k=0;k<prefix.Length;k++)put(start+(uint)k*4,prefix[k]);uint at=start+(uint)prefix.Length*4;
 var invalid=(uint[])words.Clone();
 for(int k=0;k<invalid.Length;k+=2){if(mutation==0 && invalid[k]==0xcc){invalid[k+1]=0xdeadbeef;break;}if(mutation==1 && invalid[k]==0x24){invalid[k+1]=0x45010002;break;}if(mutation==2 && invalid[k]==0x10)invalid[k+1]=0x20004000;}
 put(at,0xf0);put(at+4,cl);put(at+8,0x200f4);put(at+12,(uint)invalid.Length);
 for(int k=0;k<invalid.Length;k++)put(cl+(uint)k*4,invalid[k]);var before=(byte[])ram.Clone();
 var e=new NemaRingConsumer(start,4096,(a,n)=>ram.Skip((int)(a-0x20000000)).Take(n).ToArray(),(a,b)=>Buffer.BlockCopy(b,0,ram,(int)(a-0x20000000),b.Length),false,true);
 bool rejected=false;try{e.Submit((at+16)|4);}catch(InvalidOperationException){rejected=true;}
 Check(rejected && ram.SequenceEqual(before) && e.Draws==0 && e.Cursor==start,"invalid packing atomic rejection");
 }
 Console.WriteLine("BLACKWALL_PACKING_CHECKS "+checks);}
}