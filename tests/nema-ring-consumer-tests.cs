using System;
using System.IO;
using System.Linq;
using Antmicro.Renode.Peripherals.Miscellaneous;

namespace Antmicro.Renode.Peripherals.Miscellaneous {
public sealed class RingConsumerTests : Antmicro.Renode.Peripherals.IPeripheral
{
    public void Reset() { }
    static int checks;
    static void Check(bool pass,string name) { if(!pass)throw new Exception(name); checks++; }
    static uint Word(byte[] ram,uint address) { return BitConverter.ToUInt32(ram,(int)(address-0x20000000)); }
    static void Put(byte[] ram,uint address,uint value) { Array.Copy(BitConverter.GetBytes(value),0,ram,(int)(address-0x20000000),4); }
    static NemaRingConsumer Engine(byte[] ram,uint start,uint size,bool areaCoverage=false)
    {
        return new NemaRingConsumer(start,size,
            (address,count)=>ram.Skip((int)(address-0x20000000)).Take(count).ToArray(),
            (address,data)=>Array.Copy(data,0,ram,(int)(address-0x20000000),data.Length),areaCoverage);
    }
    static void Reject(byte[] ram,uint start,uint size,uint bell,string name)
    {
        var before=(byte[])ram.Clone();var e=Engine(ram,start,size);bool rejected=false;
        try { e.Submit(bell); } catch(InvalidOperationException) { rejected=true; }
        Check(rejected,name+" rejected");
        Check(ram.SequenceEqual(before) && e.ConsumedWords==0 && e.CompletedId==0 && !e.InterruptPending && e.Cursor==start,name+" atomic");
    }
    public static void Main(string[] args)
    {
        foreach(var folder in Directory.GetDirectories(args[0]))
        {
            var cfg=File.ReadAllLines(Path.Combine(folder,"config.txt")).Select(UInt32.Parse).ToArray();
            uint start=cfg[0],size=cfg[1],bell=cfg[2],list=cfg[3];
            var source=File.ReadAllBytes(Path.Combine(folder,"sram.bin"));
            uint destination=Word(source,list+4),stride=Word(source,list+12)&65535,res=Word(source,list+20);
            int bytes=checked((int)(stride*(res>>16)));
            var ram=(byte[])source.Clone();var e=Engine(ram,start,size);e.Submit(bell);
            Check(e.ListsConsumed==1 && e.Draws==1 && e.ConsumedWords==24 && e.Cursor==(bell&~7U),"native packet consumed");
            Check(e.CompletedId==0 && !e.InterruptPending,"no footer no completion");
            Check(ram.Skip((int)(destination-0x20000000)).Take(bytes).All(x=>x==0),"native black clear");
            Check(e.PixelsWritten==(res&65535)*(res>>16),"native full rectangle dimensions");
            Check(ram.Take((int)(destination-0x20000000)).SequenceEqual(source.Take((int)(destination-0x20000000))) &&
                ram.Skip((int)(destination-0x20000000)+bytes).SequenceEqual(source.Skip((int)(destination-0x20000000)+bytes)),"native neighbor preservation");
            // The same real ring prefix, but relocated list/destination, padded stride and partial clip.
            ram=(byte[])source.Clone();uint relocated=0x20080000,frame=0x20090000;
            Array.Copy(source,(int)(list-0x20000000),ram,(int)(relocated-0x20000000),96);
            Put(ram,(bell&~7U)-12,relocated);
            Put(ram,relocated+4,frame);Put(ram,relocated+12,0x0900000c);Put(ram,relocated+20,0x00040008);
            Put(ram,relocated+28,0x00010002);Put(ram,relocated+36,0x00030006);
            Put(ram,relocated+68,0xffffffff);Put(ram,relocated+84,0x00040008);
            for(int i=0;i<48;i++)ram[frame-0x20000000+i]=0x5a;
            e=Engine(ram,start,size);e.Submit(bell);
            for(int y=0;y<4;y++)for(int x=0;x<12;x++)
                Check(ram[frame-0x20000000+y*12+x]==(y>=1 && y<3 && x>=2 && x<6?255:0x5a),"clip/padding preservation");
            Check(e.PixelsWritten==8 && e.CompletedId==0,"dynamic rectangle consumed");
            var footer=bell&~7U;
            uint[] values={0x148,1,0xf8,1,0xff0000f0,footer+32,0xff0000f4,size};
            for(int i=0;i<values.Length;i++)Put(ram,footer+(uint)i*4,values[i]);
            var badFooter=(byte[])ram.Clone();Put(badFooter,footer+28,0);
            Reject(badFooter,start,size,(footer+32)|4,"wrong footer ring size");
            e.Submit((footer+32)|4);
            Check(e.CompletedId==1 && e.InterruptPending && e.ListsConsumed==1,"completion after consumed work");
            e.AcknowledgeInterrupt();Check(!e.InterruptPending && e.CompletedId==1,"ack preserves ID");
            e.Reset();Check(e.Cursor==start && e.CompletedId==0 && e.ConsumedWords==0 && !e.InterruptPending,"reset invalidates state");
            foreach(var change in new[]{new uint[]{list,0xdead},new uint[]{list+12,0x09000001},new uint[]{list+4,start},
                new uint[]{list+4,0x1000},new uint[]{list+68,0x7fffffff},
                new uint[]{list+52,0x80000000},new uint[]{start+4,1},new uint[]{list+92,3}})
            {
                ram=(byte[])source.Clone();Put(ram,change[0],change[1]);Reject(ram,start,size,bell,"invalid "+change[0]+"/"+change[1]);
            }
            Reject((byte[])source.Clone(),start,size,(bell&~7U)|6,"doorbell flags");
            Reject((byte[])source.Clone(),start,size,(start+size+16)|4,"doorbell outside ring");
            // A valid list followed by an unsupported packet must not partly clear the frame.
            ram=(byte[])source.Clone();Put(ram,footer,0xdead);Put(ram,footer+4,0);
            Reject(ram,start,size,(footer+8)|4,"unsupported trailing packet");
            ram=(byte[])source.Clone();e=Engine(ram,start,size);Put(ram,start,0x148);Put(ram,start+4,1);
            bool failed=false;try{e.Submit((start+8)|4);}catch(InvalidOperationException){failed=true;}
            Check(failed && e.CompletedId==0 && !e.InterruptPending,"no completion without work");
            if(File.Exists(Path.Combine(folder,"config-second.txt")))
            {
                var second=File.ReadAllLines(Path.Combine(folder,"config-second.txt")).Select(UInt32.Parse).ToArray();
                var shapeSource=File.ReadAllBytes(Path.Combine(folder,"sram-second.bin"));
                uint shapeList=second[3],surface=Word(shapeSource,shapeList+4);
                foreach(uint color in new uint[]{0xff000000,0xffffffff})
                {
                    ram=(byte[])shapeSource.Clone();Put(ram,shapeList+68,color);
                    for(int k=0;k<576*288;k++)ram[surface-0x20000000+k]=0x5a;
                    var before=(byte[])ram.Clone();e=Engine(ram,second[0],second[1]);e.Submit(second[2]);
                    int[] left={576,6,4,3,2,2,1,1};uint changed=0;
                    for(int y=0;y<288;y++)for(int x=0;x<576;x++)
                    {
                        bool inside=y!=0 && x>=(y<8?left[y]:1);
                        Check(ram[surface-0x20000000+y*576+x]==(inside?(byte)color:0x5a),"native rounded stream coverage");
                        if(inside)changed++;
                    }
                    Check(e.Draws==15 && e.ListsConsumed==1 && e.ConsumedWords==108 && e.PixelsWritten==changed,"native stream draw accounting");
                    Check(ram.Take((int)(surface-0x20000000)).SequenceEqual(before.Take((int)(surface-0x20000000))) && ram.Skip((int)(surface-0x20000000)+576*288).SequenceEqual(before.Skip((int)(surface-0x20000000)+576*288)),"native shape neighbor preservation");
                }
                // State changes between draws must affect subsequent pixels in list order.
                ram=(byte[])source.Clone();uint stream=0x20080000,frame2=0x20090000;
                Array.Copy(source,(int)(list-0x20000000),ram,(int)(stream-0x20000000),96);
                Put(ram,(bell&~7U)-12,stream);Put(ram,(bell&~7U)-4,42);
                Put(ram,stream+4,frame2);Put(ram,stream+12,0x0900000c);Put(ram,stream+20,0x00040008);
                Put(ram,stream+28,0);Put(ram,stream+36,0x00040008);Put(ram,stream+68,0xff000000);Put(ram,stream+84,0x00040008);
                uint[] extra={0x12c,0xffffffff,0x104,0x0002fffd,0x108,0x0002000a,0xff000100,1,0x104,0x00060003,0x108,0xfffe0003,0xff000100,1,0x104,0x00030007,0x108,0x00030007,0xff000100,1};
                Put(ram,(bell&~7U)-4,24+(uint)extra.Length);
                for(int k=0;k<extra.Length;k++)Put(ram,stream+96+(uint)k*4,extra[k]);
                for(int k=0;k<48;k++)ram[frame2-0x20000000+k]=0x5a;
                e=Engine(ram,start,size);e.Submit(bell);
                for(int y=0;y<4;y++)for(int x=0;x<12;x++)Check(ram[frame2-0x20000000+y*12+x]==(x>=8?0x5a:y==2 || x==3 || y==3 && x==7?255:0),"ordered signed axis lines");
                Check(e.Draws==4,"rectangle and three axis lines");
                // Diagonals remain explicitly unsupported and cannot partly clear the surface.
                Put(ram,stream+96+5*4,0x0003000a);Reject(ram,start,size,bell,"diagonal after valid rectangle");
            }
            if(File.Exists(Path.Combine(folder,"config-quad.txt")))
            {
                var cfgQuad=File.ReadAllLines(Path.Combine(folder,"config-quad.txt")).Select(UInt32.Parse).ToArray();
                var quadSource=File.ReadAllBytes(Path.Combine(folder,"sram-quad.bin"));
                Reject((byte[])quadSource.Clone(),cfgQuad[0],cfgQuad[1],cfgQuad[2],"quad strict default");
                ram=(byte[])quadSource.Clone();uint surface=Word(ram,cfgQuad[3]+4);
                Put(ram,cfgQuad[3]+68,0xffffffff);
                for(int k=0;k<576*288;k++)ram[surface-0x20000000+k]=0;
                e=Engine(ram,cfgQuad[0],cfgQuad[1],true);e.Submit(cfgQuad[2]);
                var rendered=ram.Skip((int)(surface-0x20000000)).Take(576*288).ToArray();
                Check(e.Draws==15 && e.ConsumedWords==252,"native vertex stream consumed");
                Check(rendered.Any(v=>v>0 && v<255) && rendered.Any(v=>v==255),"reference edge coverage creates gray and solid pixels");
                uint cursor=cfgQuad[2]&~7U;
                uint[] continuation={0xf0,cfgQuad[3],0x200f4,252,0xf0,cfgQuad[3],0x200f4,252};
                for(int k=0;k<continuation.Length;k++)Put(ram,cursor+(uint)k*4,continuation[k]);
                e.Submit((cursor+32)|4);
                uint[] batchFooter={0x148,3,0xf8,1,0xff0000f0,cursor+64,0xff0000f4,cfgQuad[1]};
                for(int k=0;k<batchFooter.Length;k++)Put(ram,cursor+32+(uint)k*4,batchFooter[k]);
                Put(ram,cursor+36,1);bool wrongId=false;var beforeFooter=(byte[])ram.Clone();
                try{e.Submit((cursor+64)|4);}catch(InvalidOperationException){wrongId=true;}
                Check(wrongId && ram.SequenceEqual(beforeFooter) && e.CompletedId==0 && !e.InterruptPending,"wrong batch ID cannot complete work");
                Put(ram,cursor+36,3);
                e.Submit((cursor+64)|4);
                Check(e.CompletedId==3 && e.ListsConsumed==3 && e.InterruptPending,"completion covers every pending list");
                // An axis-aligned fractional square has exact analytical intersection areas.
                ram=(byte[])source.Clone();uint qlist=0x20080000,qframe=0x20090000;
                Array.Copy(source,(int)(list-0x20000000),ram,(int)(qlist-0x20000000),72);
                Put(ram,(bell&~7U)-12,qlist);Put(ram,(bell&~7U)-4,36);
                Put(ram,qlist+4,qframe);Put(ram,qlist+12,0x0900000c);Put(ram,qlist+20,0x00040008);
                Put(ram,qlist+28,0);Put(ram,qlist+36,0x00040008);Put(ram,qlist+68,0xffffffff);
                uint[] vertices={0x120,0x4000,0x124,0x4000,0x130,0x2c000,0x134,0x4000,0x140,0x2c000,0x144,0x2c000,0x150,0x4000,0x154,0x2c000,0xff000100,0x07800005};
                for(int k=0;k<vertices.Length;k++)Put(ram,qlist+72+(uint)k*4,vertices[k]);
                for(int k=0;k<48;k++)ram[qframe-0x20000000+k]=(byte)(k%12>=8?0x5a:0);
                e=Engine(ram,start,size,true);e.Submit(bell);
                byte[] expected={143,191,143,191,255,191,143,191,143};
                for(int y=0;y<4;y++)for(int x=0;x<12;x++)Check(ram[qframe-0x20000000+y*12+x]==(x>=8?0x5a:x<3 && y<3?expected[y*3+x]:0),"analytical square area and padding");
                foreach(uint mask in new uint[]{0,0x02800000})
                {
                    Put(ram,qlist+72+17*4,mask|5);
                    for(int k=0;k<48;k++)ram[qframe-0x20000000+k]=(byte)(k%12>=8?0x5a:0);
                    e=Engine(ram,start,size,true);e.Submit(bell);
                    for(int y=0;y<3;y++)for(int x=0;x<3;x++)Check(ram[qframe-0x20000000+y*12+x]==(mask==0 || x==1?255:191),"per-edge AA selection");
                }
                Put(ram,qlist+72+17*4,0x07800005);
                // Reversing a convex winding preserves fully antialiased area.
                uint[] reversed={0x4000,0x4000,0x4000,0x2c000,0x2c000,0x2c000,0x2c000,0x4000};
                for(int k=0;k<8;k++)Put(ram,qlist+72+(uint)(2*k+1)*4,reversed[k]);
                for(int k=0;k<48;k++)ram[qframe-0x20000000+k]=0;
                e=Engine(ram,start,size,true);e.Submit(bell);
                for(int y=0;y<3;y++)for(int x=0;x<3;x++)Check(ram[qframe-0x20000000+y*12+x]==expected[y*3+x],"winding invariance");
                // Translation through the viewport boundary clips signed fixed coordinates.
                for(int k=0;k<8;k++)Put(ram,qlist+72+(uint)(2*k+1)*4,unchecked(reversed[k]-0x10000));
                for(int k=0;k<48;k++)ram[qframe-0x20000000+k]=0;
                e=Engine(ram,start,size,true);e.Submit(bell);
                byte[] clippedExpected={255,191,191,143};
                for(int y=0;y<2;y++)for(int x=0;x<2;x++)Check(ram[qframe-0x20000000+y*12+x]==clippedExpected[y*2+x],"signed fixed-coordinate clip");
                for(int k=0;k<vertices.Length;k++)Put(ram,qlist+72+(uint)k*4,vertices[k]);
                // Empty clips are emitted by the original off-screen border path.
                var empty=(byte[])source.Clone();Put(empty,list+28,0x03000240);var prior=(byte[])empty.Clone();
                e=Engine(empty,start,size);e.Submit(bell);Check(e.PixelsWritten==0 && empty.SequenceEqual(prior),"empty clip is a no-op");
                // Concave/self-crossing quads must reject the complete doorbell before DMA.
                Put(ram,qlist+72+5*4,0);Put(ram,qlist+72+7*4,0x40000);
                prior=(byte[])ram.Clone();e=Engine(ram,start,size,true);bool rejected=false;
                try{e.Submit(bell);}catch(InvalidOperationException){rejected=true;}
                Check(rejected && ram.SequenceEqual(prior) && e.Draws==0 && e.CompletedId==0,"invalid quad atomic rejection");
            }
        }
        Console.WriteLine("BLACKWALL_RING_TESTS "+checks);
    }
}
}
