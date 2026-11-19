using System;using System.Linq;using System.Reflection;using Antmicro.Renode.Peripherals.Miscellaneous;
public static class TextureTests {static int checks;static void Check(bool b,string s){if(!b)throw new Exception(s);checks++;}
public static void Run(){foreach(int mode in new[]{0,1,2,3,4,5,6,7,8,9,10})foreach(int fmt in new[]{0,1,2}){bool a4=fmt==1;bool l4=fmt==2;
 uint start=0x20001000,cl=0x20002000;var ram=new byte[0x10000];Action<uint,uint> put=(a,b)=>Buffer.BlockCopy(BitConverter.GetBytes(b),0,ram,(int)(a-0x20000000),4);
 var prefix=(uint[])typeof(NemaRingConsumer).GetMethod("InitialWords",BindingFlags.NonPublic|BindingFlags.Static).Invoke(null,null);
 for(int k=0;k<prefix.Length;k++)put(start+(uint)k*4,prefix[k]);uint at=start+(uint)prefix.Length*4;
 uint[] list={0,0x20004000,4,0x0900000a,8,0x00030008,0x110,0,0x114,0x00030008,0x1d0,a4?0x504U:1U,0x118,0,0x11c,0x141f801f,0x1c,0xffffffff,
 0x10,mode==3?0x10000000U:0x20003000U,0x14,a4?0x34000002U:l4?0x35000002U:0x09000004U,0x18,0x00010004,0x168,0xc0000000,0x174,0xbf800000,
 0x160,mode==2?0x40000000U:0x3f800000U,0x164,0,0x16c,0,0x170,0x3f800000,0x104,0x00010002,0x108,0x00020006,0xff000100,2};
 if((mode==6 || mode==7 || mode==8) && a4)list[17]=0x80ffffff;
 if(mode==7 || mode==8 || mode==9 || mode==10){if(mode>=9){list[11]=0x504;list[21]|=0x00090000;list[17]=a4?0x80ffffffU:0U;}if(mode==10)list[25]=0xbfc00000;list[15]=0x141f8000;uint color=mode>=9?(a4?0x80ffffffU:0x80000000U):list[17];list=list.Take(list.Length-2).Concat(new uint[]{0xc4,0,0xc8,0x080c0002,0xcc,mode==8?0xdeadbeefU:0x80076187U,0x204,color,0x1d8,color}).Concat(list.Skip(list.Length-2)).ToArray();}
 if(mode==5)list[15]=0xdeadbeef;
 if(mode==4)list[list.Length-3]=0x00020005; // valid clipped width3
 put(at,0xf0);put(at+4,cl);put(at+8,0x200f4);put(at+12,(uint)list.Length);
 for(int k=0;k<list.Length;k++)put(cl+(uint)k*4,list[k]);
 if(a4 || l4){ram[0x3000]=0x05;ram[0x3001]=0xaf;}else{ram[0x3000]=0;ram[0x3001]=85;ram[0x3002]=170;ram[0x3003]=255;}
 for(int k=0;k<30;k++)ram[0x4000+k]=64;var before=(byte[])ram.Clone();
 var e=new NemaRingConsumer(start,4096,(a,n)=>ram.Skip((int)(a-0x20000000)).Take(n).ToArray(),(a,b)=>Buffer.BlockCopy(b,0,ram,(int)(a-0x20000000),b.Length),false,false,mode!=0);
 bool bad=false;try{e.Submit((at+16)|4);}catch(InvalidOperationException){bad=true;}
 if(mode==0 || mode==2 || mode==3 || mode==5 || mode==8 || mode==10 || (mode==7 && !a4)){Check(bad && ram.SequenceEqual(before) && e.Draws==0,"unsupported atomic rejection");continue;}
 Check(!bad && e.Draws==1,"accepted texture");int width=mode==4?3:4;
 for(int k=0;k<4;k++){int alpha=(a4 && (mode==6 || mode==7 || mode==9))?(k*85*128+127)/255:k*85;byte value=(byte)(a4?(255*alpha+64*(255-alpha)+127)/255:alpha);if(mode==9 && !a4)value=(byte)((k*85*128+64*127+127)/255);Check(ram[0x4000+12+k]==(k<width?value:(byte)64),"translated/clip pixel");}
 for(int k=0;k<30;k++)if(k<12 || k>=12+width)Check(ram[0x4000+k]==64,"padding/outside preserved");
 Check(e.LastSurfaceWidth==8 && e.LastSurfaceStride==10 && e.LastSurfaceHeight==3,"dimensions");
 }
 foreach(uint color in new uint[]{0x0d000000,0x80ffffff,0x80646464,0xffff0000})foreach(bool enabled in new[]{false,true}){
 uint start=0x20001000,cl=0x20002000;var ram=new byte[0x10000];Action<uint,uint> put=(a,b)=>Buffer.BlockCopy(BitConverter.GetBytes(b),0,ram,(int)(a-0x20000000),4);
 var prefix=(uint[])typeof(NemaRingConsumer).GetMethod("InitialWords",BindingFlags.NonPublic|BindingFlags.Static).Invoke(null,null);
 for(int k=0;k<prefix.Length;k++)put(start+(uint)k*4,prefix[k]);uint at=start+(uint)prefix.Length*4;
 uint[] list={0,0x20004000,4,0x09000004,8,0x00010004,0x110,0,0x114,0x00010004,0x1d0,0x504,0x118,0x90000000,0x11c,0x141f001f,0x12c,color,0x104,0,0x108,0x00010004,0xff000100,2};
 put(at,0xf0);put(at+4,cl);put(at+8,0x200f4);put(at+12,(uint)list.Length);for(int k=0;k<list.Length;k++)put(cl+(uint)k*4,list[k]);
 for(int k=0;k<4;k++)ram[0x4000+k]=64;var before=(byte[])ram.Clone();
 var e=new NemaRingConsumer(start,4096,(a,n)=>ram.Skip((int)(a-0x20000000)).Take(n).ToArray(),(a,b)=>Buffer.BlockCopy(b,0,ram,(int)(a-0x20000000),b.Length),false,false,enabled);
 bool bad=false;try{e.Submit((at+16)|4);}catch(InvalidOperationException){bad=true;}
 if(!enabled || color==0xffff0000){Check(bad && ram.SequenceEqual(before) && e.Draws==0,"partial/color strict atomic rejection");continue;}
 byte expected=color==0x0d000000?(byte)61:color==0x80ffffff?(byte)160:(byte)82;
 Check(!bad && e.Draws==1,"gray alpha accepted");for(int k=0;k<4;k++)Check(ram[0x4000+k]==expected,"independent grayscale blend values");
 }
 Console.WriteLine("BLACKWALL_TEXTURE_CHECKS "+checks);}}
