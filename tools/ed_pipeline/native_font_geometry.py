"""FreeType outlines and advances matching the active libass 0.17 renderer.
Use real-dimension font sizes, hinted shaping metrics, unhinted outlines,
ASS kerning/ligature switches, scaled letter-spacing, and synthetic emboldening.
"""
import ctypes as C,ctypes.util
from functools import lru_cache
import glyph_geometry as geo
P=C.c_void_p;L=C.c_long;I=C.c_int;U=C.c_uint;S=C.c_short;US=C.c_ushort
F=C.CDLL(ctypes.util.find_library('freetype'));H=geo.H
class Vector(C.Structure):_fields_=[('x',L),('y',L)]
class BBox(C.Structure):_fields_=[('xMin',L),('yMin',L),('xMax',L),('yMax',L)]
class Generic(C.Structure):_fields_=[('data',P),('finalizer',P)]
class SizeMetrics(C.Structure):_fields_=[('x_ppem',US),('y_ppem',US),('x_scale',L),('y_scale',L),('ascender',L),('descender',L),('height',L),('max_advance',L)]
class SizeRec(C.Structure):_fields_=[('face',P),('generic',Generic),('metrics',SizeMetrics),('internal',P)]
class Outline(C.Structure):_fields_=[('n_contours',S),('n_points',S),('points',C.POINTER(Vector)),('tags',P),('contours',P),('flags',I)]
class Bitmap(C.Structure):_fields_=[('rows',U),('width',U),('pitch',I),('buffer',P),('num_grays',US),('pixel_mode',C.c_ubyte),('palette_mode',C.c_ubyte),('palette',P)]
class Metrics(C.Structure):_fields_=[(k,L)for k in ['width','height','horiBearingX','horiBearingY','horiAdvance','vertBearingX','vertBearingY','vertAdvance']]
class Slot(C.Structure):_fields_=[('library',P),('face',P),('next',P),('glyph_index',U),('generic',Generic),('metrics',Metrics),('linearHoriAdvance',L),('linearVertAdvance',L),('advance',Vector),('format',U),('bitmap',Bitmap),('bitmap_left',I),('bitmap_top',I),('outline',Outline)]
class Face(C.Structure):_fields_=[(k,L)for k in ['num_faces','face_index','face_flags','style_flags','num_glyphs']]+[('family_name',C.c_char_p),('style_name',C.c_char_p),('num_fixed_sizes',I),('available_sizes',P),('num_charmaps',I),('charmaps',P),('generic',Generic),('bbox',BBox),('units_per_EM',US)]+[(k,S)for k in ['ascender','descender','height','max_advance_width','max_advance_height','underline_position','underline_thickness']]+[('glyph',C.POINTER(Slot)),('size',C.POINTER(SizeRec)),('charmap',P)]
class Request(C.Structure):_fields_=[('type',I),('width',L),('height',L),('horiResolution',U),('vertResolution',U)]
MOVE=C.CFUNCTYPE(I,C.POINTER(Vector),P);LINE=MOVE;CONIC=C.CFUNCTYPE(I,C.POINTER(Vector),C.POINTER(Vector),P);CUBIC=C.CFUNCTYPE(I,C.POINTER(Vector),C.POINTER(Vector),C.POINTER(Vector),P)
class Funcs(C.Structure):_fields_=[('move',MOVE),('line',LINE),('conic',CONIC),('cubic',CUBIC),('shift',I),('delta',L)]
for name,args,res in [('FT_Init_FreeType',[C.POINTER(P)],I),('FT_New_Face',[P,C.c_char_p,L,C.POINTER(P)],I),('FT_Request_Size',[P,C.POINTER(Request)],I),('FT_Load_Glyph',[P,U,I],I),('FT_Outline_Embolden',[C.POINTER(Outline),L],I),('FT_Outline_Decompose',[C.POINTER(Outline),C.POINTER(Funcs),P],I),('FT_Done_Face',[P],I),('FT_MulFix',[L,L],L)]:geo.bind(F,name,args,res)
geo.bind(H,'hb_ft_font_create_referenced',[P],P);geo.bind(H,'hb_ft_font_set_load_flags',[P,I],None)
ADV=C.CFUNCTYPE(I,P,P,U,P)
geo.bind(H,'hb_font_create_sub_font',[P],P);geo.bind(H,'hb_font_funcs_create',[],P);geo.bind(H,'hb_font_funcs_set_glyph_h_advance_func',[P,ADV,P,P],None);geo.bind(H,'hb_font_set_funcs',[P,P,P,P],None);geo.bind(H,'hb_font_funcs_destroy',[P],None)
class Feature(C.Structure):_fields_=[('tag',U),('value',U),('start',U),('end',U)]
library=P();assert F.FT_Init_FreeType(C.byref(library))==0

def q(v):return round(v)
@lru_cache(None)
def outline(text,jp,fs,fx,fy,spacing=0,kerning=False):
 path=geo.FONT_JP if jp else geo.FONT_VI;face=P();assert F.FT_New_Face(library,path.encode(),3<<16 if jp else 0,C.byref(face))==0
 rec=C.cast(face,C.POINTER(Face)).contents;req=Request(1,0,256*64,0,0);assert F.FT_Request_Size(face,C.byref(req))==0
 parent=H.hb_ft_font_create_referenced(face);H.hb_ft_font_set_load_flags(parent,(1<<9)|(1<<11));font=H.hb_font_create_sub_font(parent)
 @ADV
 def advance(h,f,g,u):
  assert F.FT_Load_Glyph(face,g,(1<<9)|(1<<11))==0
  return rec.glyph.contents.metrics.horiAdvance
 funcs=H.hb_font_funcs_create();H.hb_font_funcs_set_glyph_h_advance_func(funcs,advance,None,None);H.hb_font_set_funcs(font,funcs,None,None)
 buf=H.hb_buffer_create();utf=text.encode();H.hb_buffer_add_utf8(buf,utf,len(utf),0,len(utf));H.hb_buffer_guess_segment_properties(buf)
 feats=(Feature*3)(*[Feature(int.from_bytes(tag,'big'),val,0,0xFFFFFFFF)for tag,val in [(b'kern',int(kerning)),(b'liga',int(spacing==0)),(b'clig',int(spacing==0))]])
 H.hb_shape(font,buf,C.cast(feats,P),3);n=H.hb_buffer_get_length(buf);infos=C.cast(H.hb_buffer_get_glyph_infos(buf,None),C.POINTER(geo.Info));poses=C.cast(H.hb_buffer_get_glyph_positions(buf,None),C.POINTER(geo.Pos));pen_x=0;space=q(spacing*fx/100*64);out=geo.read('POLYGON EMPTY');allrings=[]
 for i in range(n):
  glyph=infos[i].gid;assert glyph!=0,('Missing glyph',text,i);pos=poses[i];assert F.FT_Load_Glyph(face,glyph,(1<<1)|(1<<3)|(1<<9)|(1<<11))==0;slot=rec.glyph.contents
  if 400>geo.font(path)['OS/2'].usWeightClass+150:
   strength=F.FT_MulFix(rec.units_per_EM,rec.size.contents.metrics.y_scale)//64;assert F.FT_Outline_Embolden(C.byref(slot.outline),strength)==0
  origin=(pen_x+q(pos.xo*fx/100*fs/256))/64;pen=geo.Flatten({},fx/100*fs/256,fy/100*fs/256,origin)
  def pt(p):return p.contents.x/64,p.contents.y/64
  @MOVE
  def move(a,u):
   if pen.pts:pen.closePath()
   pen.moveTo(pt(a));return 0
  @LINE
  def line(a,u):pen.lineTo(pt(a));return 0
  @CONIC
  def conic(a,b,u):pen.qCurveTo(pt(a),pt(b));return 0
  @CUBIC
  def cubic(a,b,c,u):pen.curveTo(pt(a),pt(b),pt(c));return 0
  ofuncs=Funcs(move,line,conic,cubic,0,0);assert F.FT_Outline_Decompose(C.byref(slot.outline),C.byref(ofuncs),None)==0
  if pen.pts:pen.closePath()
  rings=[[(x,y-q(pos.yo*fy/100*fs/256)/64)for x,y in ring]for ring in pen.rings];allrings.extend(rings);g=geo.ring_geometry(rings,nonzero=True);out=geo.op('GEOSUnion',out,g)
  pen_x+=q(pos.xa*fx/100*fs/256)
  if i==n-1 or infos[i+1].cluster!=infos[i].cluster:pen_x+=space
 desc=F.FT_MulFix(-rec.descender,rec.size.contents.metrics.y_scale)/64*fy/100*fs/256
 wkt=geo.write(out);geo.G.GEOSGeom_destroy(out);H.hb_buffer_destroy(buf);H.hb_font_destroy(font);H.hb_font_funcs_destroy(funcs);H.hb_font_destroy(parent);F.FT_Done_Face(face)
 return wkt,allrings,pen_x/64,desc

@lru_cache(None)
def line_metrics(jp,fs,fy):
 """Return native ascent/descent at libass's normalized 256px size."""
 path=geo.FONT_JP if jp else geo.FONT_VI;face=P();assert F.FT_New_Face(library,path.encode(),3<<16 if jp else 0,C.byref(face))==0
 rec=C.cast(face,C.POINTER(Face)).contents;req=Request(1,0,256*64,0,0);assert F.FT_Request_Size(face,C.byref(req))==0
 scale=rec.size.contents.metrics.y_scale;mul=fy/100*fs/256/64
 asc=F.FT_MulFix(rec.ascender,scale)*mul;desc=F.FT_MulFix(-rec.descender,scale)*mul;F.FT_Done_Face(face)
 return asc,desc
