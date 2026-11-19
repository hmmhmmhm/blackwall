namespace Antmicro.Renode.Peripherals.Miscellaneous
{
    using System;
    using System.Collections.Generic;
    // Functional binary-solid L8 profile, not a shader ISA or physical raster implementation.
    public sealed class NemaRingConsumer
    {
        public NemaRingConsumer(uint start,uint size,Func<uint,int,byte[]> read,Action<uint,byte[]> write,bool areaCoverage=false,bool packingReference=false,bool textureReference=false)
        {
            Require((start&7)==0 && size>=16 && size<=65536 && size%16==0,"Invalid ring configuration");
            Range(start,size);this.start=start;this.size=size;this.read=read;this.write=write;this.areaCoverage=areaCoverage;this.packingReference=packingReference;this.textureReference=textureReference;Reset();
        }
        public void Submit(uint doorbell)
        {
            Require((doorbell&7)==4,"Unsupported doorbell flags");
            uint end=doorbell&~7U;
            Require(end>=start && (ulong)end<(ulong)start+size,"Doorbell outside ring");
            Require(end>Cursor,"Empty or wrapped ring is unsupported in this profile");
            var bytes=Read(Cursor,end-Cursor);var ring=new uint[bytes.Length/4];
            Buffer.BlockCopy(bytes,0,ring,0,bytes.Length);
            int position=0;
            if(!initialized)
            {
                var prefix=InitialWords();Require(ring.Length>=prefix.Length,"Incomplete GPU initialization");
                for(int i=0;i<prefix.Length;i++)Require(ring[i]==prefix[i],"Unsupported IMEM/register initialization");
                position=prefix.Length;
            }
            uint lists=0,words=0,pixels=0,draws=0,id=CompletedId,pending=uncompletedLists;
            bool irq=InterruptPending;var effects=new List<Effect>();var inputs=new List<Span>();
            var state=new Dictionary<uint,uint>(registers);
            while(position<ring.Length)
            {
                uint command=ring[position];
                if(command==0xf0)
                {
                    Require(position+4<=ring.Length && ring[position+2]==0x200f4,"Invalid list packet");
                    uint address=ring[position+1],length=ring[position+3];
                    Require((address&3)==0 && length>=2 && length<=4096 && length%2==0,"Unsupported command list size/alignment");
                    var listBytes=Read(address,length*4);var list=new uint[length];
                    Buffer.BlockCopy(listBytes,0,list,0,listBytes.Length);
                    inputs.Add(new Span(address,length*4));Render(list,state,effects,ref draws,ref pixels);
                    lists++;words+=length;pending++;position+=4;
                }
                else if(command==0x148)
                {
                    Require(position+8==ring.Length && pending>0,"Completion requires prior work and final hold");
                    uint next=(id+pending)&0xffffff;
                    Require(next!=0 && ring[position+1]==next && ring[position+2]==0xf8 && ring[position+3]==1
                        && ring[position+4]==0xff0000f0 && ring[position+5]==end
                        && ring[position+6]==0xff0000f4 && ring[position+7]==size,"Unsupported completion footer");
                    id=next;irq=true;pending=0;position+=8;
                }
                else throw new InvalidOperationException("Unsupported ring opcode: "+command.ToString("x"));
            }
            foreach(var effect in effects)
            {
                Require(!Overlap(effect.Address,(uint)effect.Bytes.Length,start,size),"Framebuffer overlaps ring");
                foreach(var input in inputs)Require(!Overlap(effect.Address,(uint)effect.Bytes.Length,input.Address,input.Length),"Framebuffer overlaps list");
            }
            for(int i=0;i<effects.Count;i++)for(int j=0;j<i;j++)
                Require(!Overlap(effects[i].Address,(uint)effects[i].Bytes.Length,effects[j].Address,(uint)effects[j].Bytes.Length),"Overlapping draws in one doorbell are unsupported");
            // All guest-controlled ranges, commands and footer validation precede DMA/state effects.
            foreach(var effect in effects)
            {
                write(effect.Address,effect.Bytes);
                LastSurfaceAddress=effect.Address;LastSurfaceStride=effect.Stride;LastSurfaceWidth=effect.Width;LastSurfaceHeight=effect.Height;
                if(effect.PackingSource!=0){LastPackingSource=effect.PackingSource;LastPackingStride=effect.PackingStride;LastPackingWidth=effect.Width*2;LastPackingHeight=effect.Height;PackingSubmits++;}
            }
            initialized=true;Cursor=end;CompletedId=id;InterruptPending=irq;uncompletedLists=pending;
            registers=state;ListsConsumed+=lists;Draws+=draws;ConsumedWords+=words;PixelsWritten+=pixels;
        }
        private void Render(uint[] list,Dictionary<uint,uint> state,List<Effect> effects,ref uint draws,ref uint pixels)
        {
            for(int i=0;i<list.Length;i+=2)
            {
                uint command=list[i],value=list[i+1];
                switch(command)
                {
                    case 0:case 4:case 8:case 0x110:case 0x114:case 0x1d0:case 0x118:case 0x11c:case 0x12c:case 0x104:case 0x108:
                    case 0x120:case 0x124:case 0x130:case 0x134:case 0x140:case 0x144:case 0x150:case 0x154:
                        state[command]=value;break;
                    case 0x10:case 0x14:case 0x18:case 0x1c:case 0x20:case 0x24:case 0x28:
                    case 0x160:case 0x164:case 0x168:case 0x16c:case 0x170:case 0x174:
                    case 0xc4:case 0xc8:case 0xcc:case 0x204:case 0x1d8:
                        Require(packingReference || textureReference,"Texture state requires explicit reference profile");state[command]=value;break;
                    case 0xff000100:
                        Raster(state,value,effects,ref pixels);draws++;break;
                    default:throw new InvalidOperationException("Unsupported command opcode: "+command.ToString("x"));
                }
            }
        }
        private static uint Get(Dictionary<uint,uint> state,uint key)
        {
            uint value;Require(state.TryGetValue(key,out value),"Draw before required GPU state");return value;
        }
        private static int X(uint packed) {return (short)(packed&65535);}
        private static int Y(uint packed) {return (short)(packed>>16);}
        private void Raster(Dictionary<uint,uint> s,uint command,List<Effect> effects,ref uint pixels)
        {
            if(packingReference && s.ContainsKey(0x11c) && Get(s,0x11c)==0x181f8000)
            {RasterPacking(s,command,effects,ref pixels);return;}
            if(textureReference && s.ContainsKey(0x11c) && (Get(s,0x11c)==0x141f801f || Get(s,0x11c)==0x141f8000))
            {RasterTexture(s,command,effects,ref pixels);return;}
            Require((Get(s,0x1d0)==0x504 || (textureReference && Get(s,0x1d0)==1)) && Get(s,0x118)==0x90000000 && Get(s,0x11c)==0x141f001f,"Unsupported shader/raster profile");
            uint color=Get(s,0x12c);uint red=(color>>16)&255,green=(color>>8)&255,blue=color&255;
            Require(color==0xff000000 || color==0xffffffff || (textureReference && red==green && green==blue),"Only binary or explicit reference grayscale colors are supported");
            int alpha=(int)(color>>24);bool sourceCopy=Get(s,0x1d0)==1;
            uint address=Get(s,0),format=Get(s,4),stride=format&65535,res=Get(s,8),width=res&65535,height=res>>16;
            Require((format>>16)==0x0900 && width>0 && height>0 && width<=1024 && height<=1024
                && stride>=width && stride<=4096,"Unsupported L8 surface");
            if((command&~0x07800000U)==5)
            {
                Require(areaCoverage,"Quad coverage requires explicit area-reference profile");
                RasterQuad(s,command,effects,address,stride,width,height,(byte)color,alpha,sourceCopy,ref pixels);return;
            }
            uint startXY=Get(s,0x104),endXY=Get(s,0x108),clipMin=Get(s,0x110),clipMax=Get(s,0x114);
            int x0=X(startXY),y0=Y(startXY),x1=X(endXY),y1=Y(endXY);
            int cx0=X(clipMin),cy0=Y(clipMin),cx1=X(clipMax),cy1=Y(clipMax);
            if(command==2)Require(x0<=x1 && y0<=y1,"Invalid rectangle bounds");
            else if(command==1)
            {
                Require(x0==x1 || y0==y1,"Diagonal lines are unsupported");
                int a=x0,b=y0;x0=Math.Min(x0,x1);y0=Math.Min(y0,y1);x1=Math.Max(a,x1)+1;y1=Math.Max(b,y1)+1;
            }
            else throw new InvalidOperationException("Unsupported raster command: "+command);
            x0=Math.Max(0,Math.Max(x0,cx0));y0=Math.Max(0,Math.Max(y0,cy0));
            x1=Math.Min((int)width,Math.Min(x1,cx1));y1=Math.Min((int)height,Math.Min(y1,cy1));
            uint count=(uint)(Math.Max(0,x1-x0)*Math.Max(0,y1-y0));
            Require((ulong)pixels+count<=16777216,"Pixel operation budget exceeded");
            Effect effect=Surface(effects,address,stride,width,height);
            for(int y=y0;y<y1;y++)for(int x=x0;x<x1;x++){int at=y*(int)stride+x;effect.Bytes[at]=sourceCopy?(byte)color:(byte)(((byte)color*alpha+effect.Bytes[at]*(255-alpha)+127)/255);}
            pixels+=count;
        }
        // Nominal identity/translation point-sampled texture policy; missing matrix axes are identity.
        private void RasterTexture(Dictionary<uint,uint> s,uint command,List<Effect> effects,ref uint pixels)
        {
            uint blend=Get(s,0x1d0);Require(command==2 && (blend==1 || blend==0x504) && Get(s,0x118)==0,"Unsupported texture shader");
            uint address=Get(s,0),format=Get(s,4),stride=format&65535,res=Get(s,8),width=res&65535,height=res>>16;
            uint src=Get(s,0x10),sf=Get(s,0x14),ss=sf&65535,sr=Get(s,0x18),sw=sr&65535,sh=sr>>16;
            uint textureFormat=sf>>24,sampling=(sf>>16)&255;bool a4=textureFormat==0x34,l4=textureFormat==0x35;Require(format>>16==0x0900 && width>0 && height>0 && width<=1024 && height<=1024 && stride>=width && stride<=4096 &&
                ((sampling==0 || sampling==9) && (a4 || l4 || textureFormat==9)) && sw>0 && sh>0 && sw<=2048 && sh<=1024 && ss>0 && ss<=4096 && ss>=((a4 || l4)?(sw+1)/2:sw),"Unsupported texture surface");
            foreach(uint axis in new uint[]{0x160,0x170})if(s.ContainsKey(axis))Require(Get(s,axis)==0x3f800000,"Unsupported texture scale");
            foreach(uint axis in new uint[]{0x164,0x16c})if(s.ContainsKey(axis))Require(Get(s,axis)==0,"Unsupported texture shear");
            float tx=BitConverter.ToSingle(BitConverter.GetBytes(Get(s,0x168)),0),ty=BitConverter.ToSingle(BitConverter.GetBytes(Get(s,0x174)),0);
            Require(!float.IsNaN(tx) && !float.IsInfinity(tx) && !float.IsNaN(ty) && !float.IsInfinity(ty) && Math.Abs(tx)<4096 && Math.Abs(ty)<4096,"Invalid texture translation");
            Require(sampling!=9 || (tx==Math.Floor(tx) && ty==Math.Floor(ty)),"Filtered texture requires integer reference alignment");
            uint length=ss*sh;Require((src>=0x20000000 && (ulong)src+length<=0x20380000) || (src>=0x438000 && (ulong)src+length<=0x7c0000),"Texture source outside declared memory");
            Require(!Overlap(src,length,address,stride*height),"Texture source/destination overlap");
            foreach(var e in effects)Require(!Overlap(src,length,e.Address,(uint)e.Bytes.Length),"Texture source aliases pending draw");
            var input=read(src,(int)length);Require(input!=null && input.Length==length,"Incomplete texture source");var target=Surface(effects,address,stride,width,height);
            uint a=Get(s,0x104),b=Get(s,0x108),c=Get(s,0x110),d=Get(s,0x114);
            int x0=Math.Max(0,Math.Max(X(a),X(c))),y0=Math.Max(0,Math.Max(Y(a),Y(c)));
            int x1=Math.Min((int)width,Math.Min(X(b),X(d))),y1=Math.Min((int)height,Math.Min(Y(b),Y(d)));
            Require(X(a)<=X(b) && Y(a)<=Y(b),"Invalid texture rectangle");
            uint count=(uint)(Math.Max(0,x1-x0)*Math.Max(0,y1-y0));Require((ulong)pixels+count<=16777216,"Pixel operation budget exceeded");
            uint color=a4?Get(s,0x1c):0;
            if(Get(s,0x11c)==0x141f8000)
                Require(blend==0x504 && Get(s,0xc4)==0 && Get(s,0xc8)==0x080c0002 && Get(s,0xcc)==0x80076187 &&
                    (!a4 || Get(s,0x204)==color) && Get(s,0x1d8)==Get(s,0x204),"Unsupported dynamic A4 color shader");
            if(a4)Require(((color>>16)&255)==((color>>8)&255) && ((color>>8)&255)==(color&255),"Unsupported non-grayscale A4 color");
            for(int y=y0;y<y1;y++)for(int x=x0;x<x1;x++)
            {
                int ix=(int)Math.Floor(x+0.5+tx),iy=(int)Math.Floor(y+0.5+ty);
                // At integer translation, center-based bilinear reduces to one texel; transparent border stays untouched.
                if(sampling==9 && (ix<0 || iy<0 || ix>=sw || iy>=sh))continue;
                int sx=Math.Max(0,Math.Min((int)sw-1,ix)),sy=Math.Max(0,Math.Min((int)sh-1,iy));
                int sample=(a4 || l4)?((input[sy*(int)ss+sx/2]>>(sx%2==0?4:0))&15)*17:input[sy*(int)ss+sx];
                int alpha=a4?(sample*(int)(color>>24)+127)/255:(Get(s,0x11c)==0x141f8000?(int)(Get(s,0x204)>>24):255);
                int value=a4?(byte)color:sample;int at=y*(int)stride+x;
                target.Bytes[at]=(byte)((value*alpha+(blend==1?0:target.Bytes[at]*(255-alpha))+127)/255);
            }
            pixels+=count;
        }
        // center-msb-alpha-high-reference-v1: declared functional policy, not physical GPU validation.
        private void RasterPacking(Dictionary<uint,uint> s,uint command,List<Effect> effects,ref uint pixels)
        {
            uint blend=Get(s,0x1d0),shader=Get(s,0xcc);bool first=blend==1;
            Require(command==2 && (first || blend==0x101) && Get(s,0x118)==0 && Get(s,0xc4)==0 && Get(s,0xc8)==0x080c0102 &&
                shader==(first ? 0x8a0761c7U:0x80076185U) && Get(s,0x1c)==0xff000000,"Unsupported packing shader");
            Require(Get(s,0x160)==0x40800000 && Get(s,0x164)==0 && Get(s,0x168)==(first ? 0xc0000000U:0U) &&
                Get(s,0x16c)==0 && Get(s,0x170)==0x3f800000 && Get(s,0x174)==0,"Unsupported packing matrix");
            if(!first)Require(Get(s,0x204)==0 && Get(s,0x1d8)==0,"Unsupported packing constants");
            uint address=Get(s,0x20),format=Get(s,0x24),stride=format&65535,res=Get(s,0x28),width=res&65535,height=res>>16;
            uint source=Get(s,0x10),sf=Get(s,0x14),ss=sf&65535,sr=Get(s,0x18),sw=sr&65535,sh=sr>>16;
            Require(format>>16==0x4500 && width>0 && height>0 && width<=512 && height<=1024 && stride>=width && stride<=4096 &&
                sf>>16==(first ? 0x3400U:0x3500U) && sw==width*4 && sh==height && ss==width*2,"Unsupported packing surfaces");
            Require(Get(s,0)==address && Get(s,4)==(0x35000000U|stride) && Get(s,8)==((height<<16)|(width*2)),"Packing target alias mismatch");
            Require(!Overlap(source,ss*sh,address,stride*height),"Packing source/destination overlap");
            foreach(var e in effects)Require(!Overlap(source,ss*sh,e.Address,(uint)e.Bytes.Length),"Packing source aliases pending draw");
            var packed=Read(source,ss*sh);var target=Surface(effects,address,stride,width,height);target.PackingSource=source;target.PackingStride=ss;
            uint a=Get(s,0x104),b=Get(s,0x108),c=Get(s,0x110),d=Get(s,0x114);
            int x0=Math.Max(0,Math.Max(X(a),X(c))),y0=Math.Max(0,Math.Max(Y(a),Y(c)));
            int x1=Math.Min((int)width,Math.Min(X(b),X(d))),y1=Math.Min((int)height,Math.Min(Y(b),Y(d)));
            Require(X(a)<=X(b) && Y(a)<=Y(b),"Invalid packing rectangle");
            uint count=(uint)(Math.Max(0,x1-x0)*Math.Max(0,y1-y0));Require((ulong)pixels+count<=16777216,"Pixel operation budget exceeded");
            for(int y=y0;y<y1;y++)for(int x=x0;x<x1;x++)
            {
                int src=y*(int)ss+x*2+(first ? 0:1),dst=y*(int)stride+x;
                byte high=(byte)(packed[src]>>4);
                target.Bytes[dst]=first ? (byte)(high<<4):(byte)Math.Min(255,target.Bytes[dst]+high);
            }
            pixels+=count;
        }
        private Effect Surface(List<Effect> effects,uint address,uint stride,uint width,uint height)
        {
            Effect effect=effects.Find(e=>e.Address==address);
            if(effect==null)
            {
                foreach(var previous in effects)Require(!Overlap(address,stride*height,previous.Address,(uint)previous.Bytes.Length),"Overlapping surface views are unsupported");
                effect=new Effect(address,Read(address,stride*height),stride,width,height);effects.Add(effect);
            }
            Require(effect.Stride==stride && effect.Width==width && effect.Height==height,"Surface layout changed within a doorbell");
            return effect;
        }
        private void RasterQuad(Dictionary<uint,uint> s,uint command,List<Effect> effects,uint address,uint stride,uint width,uint height,byte color,int alpha,bool sourceCopy,ref uint pixels)
        {
            var vertices=new Point[4];
            for(uint i=0;i<4;i++)vertices[i]=new Point((int)Get(s,0x120+i*16)/65536.0,(int)Get(s,0x124+i*16)/65536.0);
            double area=0;for(int i=0;i<4;i++)area+=Cross(vertices[i],vertices[(i+1)%4]);
            Require(area!=0,"Degenerate quad is unsupported");double orientation=area>0?1:-1;
            for(int i=0;i<4;i++)Require(orientation*Edge(vertices[i],vertices[(i+1)%4],vertices[(i+2)%4])>=0,"Non-convex quad is unsupported");
            double minX=vertices[0].X,maxX=minX,minY=vertices[0].Y,maxY=minY;
            foreach(var v in vertices){minX=Math.Min(minX,v.X);maxX=Math.Max(maxX,v.X);minY=Math.Min(minY,v.Y);maxY=Math.Max(maxY,v.Y);}
            uint low=Get(s,0x110),high=Get(s,0x114);
            int x0=Math.Max(0,Math.Max(X(low),(int)Math.Floor(minX))),y0=Math.Max(0,Math.Max(Y(low),(int)Math.Floor(minY)));
            int x1=Math.Min((int)width,Math.Min(X(high),(int)Math.Ceiling(maxX))),y1=Math.Min((int)height,Math.Min(Y(high),(int)Math.Ceiling(maxY)));
            uint count=(uint)(Math.Max(0,x1-x0)*Math.Max(0,y1-y0));Require((ulong)pixels+count<=16777216,"Pixel operation budget exceeded");
            var surface=Surface(effects,address,stride,width,height);
            for(int y=y0;y<y1;y++)for(int x=x0;x<x1;x++)
            {
                double coverage=Coverage(vertices,orientation,command,x,y);
                if(coverage<=0)continue;
                double effective=coverage*(sourceCopy ? 1.0:alpha/255.0);
                int index=y*(int)stride+x;surface.Bytes[index]=(byte)Math.Floor(color*effective+surface.Bytes[index]*(1-effective)+0.5);
            }
            pixels+=count;
        }
        private static double Coverage(Point[] vertices,double orientation,uint command,int x,int y)
        {
            var polygon=new List<Point>{new Point(x,y),new Point(x+1,y),new Point(x+1,y+1),new Point(x,y+1)};
            var center=new Point(x+0.5,y+0.5);
            for(int i=0;i<4;i++)
            {
                var a=vertices[i];var b=vertices[(i+1)%4];
                if(a.X==b.X && a.Y==b.Y)continue;
                if((command&(1U<<(26-i)))==0)
                {
                    double distance=orientation*Edge(a,b,center);double dx=orientation*(b.X-a.X),dy=orientation*(b.Y-a.Y);
                    if(distance<0 || distance==0 && !(dy<0 || dy==0 && dx>0))return 0;
                    continue;
                }
                var clipped=new List<Point>();
                for(int j=0;j<polygon.Count;j++)
                {
                    var p=polygon[j];var q=polygon[(j+1)%polygon.Count];double dp=orientation*Edge(a,b,p),dq=orientation*Edge(a,b,q);
                    if(dp>=0)clipped.Add(p);
                    if((dp>=0)!=(dq>=0)){double t=dp/(dp-dq);clipped.Add(new Point(p.X+t*(q.X-p.X),p.Y+t*(q.Y-p.Y)));}
                }
                polygon=clipped;if(polygon.Count==0)return 0;
            }
            double area=0;for(int i=0;i<polygon.Count;i++)area+=Cross(polygon[i],polygon[(i+1)%polygon.Count]);
            return Math.Min(1,Math.Max(0,Math.Abs(area)*0.5));
        }
        private static double Cross(Point a,Point b){return a.X*b.Y-a.Y*b.X;}
        private static double Edge(Point a,Point b,Point p){return (b.X-a.X)*(p.Y-a.Y)-(b.Y-a.Y)*(p.X-a.X);}
        private struct Point {public Point(double x,double y){X=x;Y=y;}public readonly double X,Y;}
        private byte[] Read(uint address,uint length)
        {
            Range(address,length);var value=read(address,(int)length);
            Require(value!=null && value.Length==length,"Incomplete guest memory read");return value;
        }
        private static void Range(uint address,uint length)
        {
            Require(length>0 && address>=0x20000000 && (ulong)address+length<=0x20380000,"Outside guest SRAM");
        }
        private static bool Overlap(uint a,uint n,uint b,uint m) {return (ulong)a<(ulong)b+m && (ulong)b<(ulong)a+n;}
        private static void Require(bool condition,string reason) {if(!condition)throw new InvalidOperationException(reason);}
        // Canonical initial uploads observed in all three original native captures.
        // Register names/addresses: pinned Think Silicon Nema headers, NOTICE.md.
        private static uint[] InitialWords()
        {
            var v=new List<uint>{0xf8,0};
            for(uint slot=0x18;slot<=0x1f;slot++)v.AddRange(new uint[]{0xc4,slot,0xc8,slot==0x1f?0x08000002U:0,0xcc,slot==0x1f?0x80000009U:0});
            v.AddRange(new uint[]{0x1d0,1,0x200,0,0x204,0xffffffff,
                0xc4,0x16,0xc8,0x080c0182,0xcc,0x8a9f5a24,
                0xc4,0x17,0xc8,0x080c0182,0xcc,0x8a9f5a34,0x388,1,
                0xc4,0x15,0xc8,0x080c0182,0xcc,0x8a8761c6,
                0xc4,0x14,0xc8,0x004e0002,0xcc,0x800b0286,
                0xc4,0x13,0xc8,0x0a980002,0xcc,0x8081a046});
            return v.ToArray();
        }
        public void AcknowledgeInterrupt() {InterruptPending=false;}
        public void Reset() {Cursor=start;CompletedId=0;InterruptPending=false;initialized=false;uncompletedLists=0;ListsConsumed=Draws=ConsumedWords=PixelsWritten=0;LastSurfaceAddress=LastSurfaceStride=LastSurfaceWidth=LastSurfaceHeight=LastPackingSource=LastPackingStride=LastPackingWidth=LastPackingHeight=PackingSubmits=0;registers.Clear();}
        public uint Cursor { get; private set; }
        public uint CompletedId { get; private set; }
        public bool InterruptPending { get; private set; }
        public uint ListsConsumed { get; private set; }
        public uint Draws { get; private set; }
        public uint ConsumedWords { get; private set; }
        public uint PixelsWritten { get; private set; }
        public uint LastSurfaceAddress {get;private set;}
        public uint LastSurfaceStride {get;private set;}
        public uint LastSurfaceWidth {get;private set;}
        public uint LastSurfaceHeight {get;private set;}
        public uint LastPackingSource {get;private set;}
        public uint LastPackingStride {get;private set;}
        public uint LastPackingWidth {get;private set;}
        public uint LastPackingHeight {get;private set;}
        public uint PackingSubmits {get;private set;}
        public bool HasPendingWork=>uncompletedLists>0;
        private sealed class Span {public Span(uint address,uint length){Address=address;Length=length;}public readonly uint Address,Length;}
        private sealed class Effect {public Effect(uint address,byte[] bytes,uint stride,uint width,uint height){Address=address;Bytes=bytes;Stride=stride;Width=width;Height=height;}public uint PackingSource,PackingStride;public readonly uint Address,Stride,Width,Height;public readonly byte[] Bytes;}
        private readonly uint start,size;
        private readonly Func<uint,int,byte[]> read;
        private readonly Action<uint,byte[]> write;
        private readonly bool areaCoverage,packingReference,textureReference;
        private bool initialized;
        private uint uncompletedLists;
        private Dictionary<uint,uint> registers=new Dictionary<uint,uint>();
    }
}
