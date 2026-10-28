"""Font outline geometry in libass layout, HarfBuzz shaping and GEOS Boolean cuts."""
import ctypes as C,ctypes.util,math,re
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools.pens.basePen import BasePen
from functools import lru_cache
H=C.CDLL(ctypes.util.find_library('harfbuzz'));G=C.CDLL(ctypes.util.find_library('geos_c'))
def bind(lib,name,args,result):
 f=getattr(lib,name);f.argtypes=args;f.restype=result;return f
P=C.c_void_p;I=C.c_int;U=C.c_uint
for name,args,res in [('hb_blob_create_from_file_or_fail',[C.c_char_p],P),('hb_face_create',[P,U],P),('hb_font_create',[P],P),('hb_ot_font_set_funcs',[P],None),('hb_font_set_scale',[P,I,I],None),('hb_buffer_create',[],P),('hb_buffer_add_utf8',[P,C.c_char_p,I,U,I],None),('hb_buffer_guess_segment_properties',[P],None),('hb_shape',[P,P,P,U],None),('hb_buffer_get_length',[P],U),('hb_buffer_get_glyph_infos',[P,P],P),('hb_buffer_get_glyph_positions',[P,P],P),('hb_buffer_destroy',[P],None),('hb_font_destroy',[P],None),('hb_face_destroy',[P],None),('hb_blob_destroy',[P],None)]:bind(H,name,args,res)
class Info(C.Structure):_fields_=[('gid',U),('mask',U),('cluster',U),('var1',U),('var2',U)]
class Pos(C.Structure):_fields_=[('xa',I),('ya',I),('xo',I),('yo',I),('var',U)]
for name,args,res in [('initGEOS',[P,P],None),('GEOSWKTReader_create',[],P),('GEOSWKTReader_read',[P,C.c_char_p],P),('GEOSWKTWriter_create',[],P),('GEOSWKTWriter_write',[P,P],P),('GEOSWKTWriter_setRoundingPrecision',[P,I],None),('GEOSGeom_destroy',[P],None),('GEOSFree',[P],None),('GEOSSymDifference',[P,P],P),('GEOSUnion',[P,P],P),('GEOSIntersection',[P,P],P),('GEOSDifference',[P,P],P),('GEOSisEmpty',[P],C.c_byte),('GEOSisValid',[P],C.c_byte),('GEOSMakeValid',[P],P)]:bind(G,name,args,res)
G.initGEOS(None,None);reader=G.GEOSWKTReader_create();writer=G.GEOSWKTWriter_create();G.GEOSWKTWriter_setRoundingPrecision(writer,3)
def read(wkt):
 g=G.GEOSWKTReader_read(reader,wkt.encode());assert g,wkt[:100];return g
def write(g):
 p=G.GEOSWKTWriter_write(writer,g);assert p
 try:return C.string_at(p).decode()
 finally:G.GEOSFree(p)
def op(fn,a,b):
 c=getattr(G,fn)(a,b);assert c,fn;G.GEOSGeom_destroy(a);G.GEOSGeom_destroy(b);return c
def polygon(pts):
 if pts[0]!=pts[-1]:pts=pts+[pts[0]]
 return read('POLYGON (('+','.join(f'{x:.6f} {y:.6f}' for x,y in pts)+'))')
def ring_geometry(rings,nonzero=False):
 areas=[sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(r,r[1:]+r[:1]))/2 for r in rings]
 sign=1 if not areas or max(areas,key=abs)>0 else -1
 out=read('POLYGON EMPTY');holes=read('POLYGON EMPTY')
 for pts,area in zip(rings,areas):
  if len(pts)<3:continue
  g=polygon(pts)
  if not G.GEOSisValid(g):new=G.GEOSMakeValid(g);G.GEOSGeom_destroy(g);g=new
  if nonzero and area*sign<0:holes=op('GEOSUnion',holes,g)
  else:out=op('GEOSUnion' if nonzero else 'GEOSSymDifference',out,g)
 return op('GEOSDifference',out,holes)
class Flatten(BasePen):
 def __init__(self,glyphset,sx,sy,dx=0):super().__init__(glyphset);self.sx=sx;self.sy=sy;self.dx=dx;self.rings=[];self.pts=[]
 def xy(self,p):return (p[0]*self.sx+self.dx,-p[1]*self.sy)
 def _moveTo(self,p):self.pts=[self.xy(p)]
 def _lineTo(self,p):self.pts.append(self.xy(p))
 def _curveToOne(self,b,c,d):
  a=self.pts[-1];b,c,d=map(self.xy,(b,c,d));self.curve(a,b,c,d)
 def curve(self,a,b,c,d):
  # Flatness <= 0.08 native px; actual cubic outlines remain recoverable in source font.
  def dist(p):
   vx,vy=d[0]-a[0],d[1]-a[1];den=math.hypot(vx,vy);return abs(vx*(a[1]-p[1])-(a[0]-p[0])*vy)/den if den else math.dist(p,a)
  if max(dist(b),dist(c))<.08:self.pts.append(d);return
  def mid(x,y):return ((x[0]+y[0])/2,(x[1]+y[1])/2)
  ab,bc,cd=mid(a,b),mid(b,c),mid(c,d);abc,bcd=mid(ab,bc),mid(bc,cd);center=mid(abc,bcd);self.curve(a,ab,abc,center);self.curve(center,bcd,cd,d)
 def _qCurveToOne(self,b,d):
  a=self._getCurrentPoint();self._curveToOne((a[0]+2*(b[0]-a[0])/3,a[1]+2*(b[1]-a[1])/3),(d[0]+2*(b[0]-d[0])/3,d[1]+2*(b[1]-d[1])/3),d)
 def _closePath(self):
  if len(self.pts)>=3:self.rings.append(self.pts)
  self.pts=[]
 def _endPath(self):self._closePath()
FONT_VI='/home/cuongba956/.local/share/fonts/KNK_Fonts/#9slide04 spectral medium.ttf'
FONT_JP='/home/cuongba956/.local/share/fonts/Google/TrueType/Noto Serif JP/Noto_Serif_JP_ExtraLight.ttf'
@lru_cache(None)
def font(path):
 f=TTFont(path)
 # Variable outlines are evaluated lazily per used glyph at wght=400.
 return f
@lru_cache(None)
def outline(text,jp,fs,fx,fy,spacing=0):
 path=FONT_JP if jp else FONT_VI;f=font(path);upem=f['head'].unitsPerEm
 # Match libass FreeType REAL_DIM sizing using Win metrics.
 height=f['OS/2'].usWinAscent+f['OS/2'].usWinDescent;sx=fs/height*fx/100;sy=fs/height*fy/100
 # Use the instantiated font for both shaping and outline selection.
 b=H.hb_blob_create_from_file_or_fail(path.encode());face=H.hb_face_create(b,0);hbfont=H.hb_font_create(face);H.hb_ot_font_set_funcs(hbfont);H.hb_font_set_scale(hbfont,upem,upem)
 if 'fvar' in f:
  class Variation(C.Structure):_fields_=[('tag',U),('value',C.c_float)]
  v=Variation(int.from_bytes(b'wght','big'),400);bind(H,'hb_font_set_variations',[P,C.POINTER(Variation),U],None)(hbfont,C.byref(v),1)
 buf=H.hb_buffer_create();utf=text.encode();H.hb_buffer_add_utf8(buf,utf,len(utf),0,len(utf));H.hb_buffer_guess_segment_properties(buf);H.hb_shape(hbfont,buf,None,0);n=H.hb_buffer_get_length(buf);infos=C.cast(H.hb_buffer_get_glyph_infos(buf,None),C.POINTER(Info));positions=C.cast(H.hb_buffer_get_glyph_positions(buf,None),C.POINTER(Pos));gs=f.getGlyphSet(location={'wght':400}) if 'fvar' in f else f.getGlyphSet();order=f.getGlyphOrder();x=0;out=read('POLYGON EMPTY');allrings=[]
 for i in range(n):
  pos=positions[i];pen=Flatten(gs,sx,sy,(x+pos.xo)*sx+i*spacing*fx/100);gs[order[infos[i].gid]].draw(pen)
  rings=[[(xx,yy-pos.yo*sy) for xx,yy in r] for r in pen.rings];allrings.extend(rings);g=ring_geometry(rings,nonzero=True);out=op('GEOSUnion',out,g);x+=pos.xa
 wkt=write(out);G.GEOSGeom_destroy(out);H.hb_buffer_destroy(buf);H.hb_font_destroy(hbfont);H.hb_face_destroy(face);H.hb_blob_destroy(b)
 return wkt,allrings,x*sx+max(0,n-1)*spacing*fx/100

def rings_wkt(wkt):
 return [[tuple(map(float,p.strip().split()[:2])) for p in ring.split(',')] for ring in re.findall(r'\(([^()]+)\)',wkt)]
def translated(wkt,dx,dy):
 # Coordinate transform preserves polygon/hole structure.
 return re.sub(r'(-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?)',lambda m:f'{float(m[1])+dx:.6f} {float(m[2])+dy:.6f}',wkt)
def mask_geometry(path):
 n=list(map(float,re.findall(r'-?\d+(?:\.\d+)?',path)));assert path.lstrip().startswith('m ')
 rings=[]
 for c in re.findall(r'm\s+([^m]+)',path):
  a=list(map(float,re.findall(r'-?\d+(?:\.\d+)?',c)));rings.append(list(zip(a[::2],a[1::2])))
 return ring_geometry(rings)
def ass_path(g):
 # GEOS outer/hole orientations are retained for ASS nonzero winding.
 return ' '.join('m '+' l '.join(f'{x:.3f} {y:.3f}' for x,y in ring[:-1]) for ring in rings_wkt(write(g)) if len(set(ring))>=3)
