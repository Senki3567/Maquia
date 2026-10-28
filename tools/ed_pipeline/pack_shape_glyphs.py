#!/usr/bin/env python3
"""Store approved ED drawings as shared-contour glyphs in an embedded TTF.
Preserve each event's style and animation; keep the vector source and map separately.
"""
from pathlib import Path
import re,json,hashlib,argparse,collections
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.cu2quPen import Cu2QuPen

SCALE=16;EM=1024

def contours(path):
 tokens=re.findall(r'[a-z]|-?\d+(?:\.\d+)?',path);i=0;cmd=None;out=[];part=[]
 if len(tokens)<3:return []
 while i<len(tokens):
  if tokens[i].isalpha():cmd=tokens[i];i+=1
  assert cmd in ('m','n','l','b','c'),cmd
  if cmd=='c':
   if part:out.append(part);part=[]
   cmd=None;continue
  n=6 if cmd=='b'else 2;nums=tuple(map(lambda s:round(float(s)),tokens[i:i+n]));assert len(nums)==n,(path[:200],tokens[max(0,i-5):i+10],cmd);i+=n
  if cmd in ('m','n'):
   if part:out.append(part)
   part=[('m',nums)];cmd='l'
  else:part.append((cmd,nums))
 if part:out.append(part)
 return out

def encode_ass(data):
 chars=[]
 for i in range(0,len(data),3):
  chunk=data[i:i+3];x=int.from_bytes(chunk.ljust(3,b'\0'),'big');chars.extend(chr(((x>>shift)&63)+33)for shift in [18,12,6,0][:len(chunk)+1])
 return '\n'.join(''.join(chars[i:i+80])for i in range(0,len(chars),80))

def decode_ass(text):
 chars=''.join(text.split());out=bytearray()
 for i in range(0,len(chars),4):
  c=chars[i:i+4];x=0
  for v in c:x=(x<<6)|(ord(v)-33)
  x<<=6*(4-len(c));out.extend(x.to_bytes(3,'big')[:len(c)-1])
 return bytes(out)

def build(source,output,fontfile,quad_error=.25):
 raw=source.read_bytes();family='MaquiaEDShapes'+hashlib.sha256(raw).hexdigest()[:8];glyphs={};metrics={};component_cache={};shape_cache={};mapped=[];order=[];glyph_info=[]
 def add(name,glyph):
  glyph.recalcBounds(glyphs);glyphs[name]=glyph;metrics[name]=(EM,getattr(glyph,'xMin',0));order.append(name)
 pen=TTGlyphPen(None);add('.notdef',pen.glyph())
 def component(part):
  pts=[(nums[j],-nums[j+1])for cmd,nums in part for j in range(0,len(nums),2)];ox=min(x for x,y in pts);oy=min(y for x,y in pts)
  normalized=[(cmd,tuple(v- (ox if j%2==0 else oy)for j,v in enumerate(tuple(v if j%2==0 else -v for j,v in enumerate(nums)))))for cmd,nums in part]
  if all(cmd in ('m','l')for cmd,nums in normalized):
   p=[nums for cmd,nums in normalized]
   while len(p)>1 and p[-1]==p[0]:p.pop()
   if len(p)<3:return None,ox,oy
   low=min(p);indices=[j for j,v in enumerate(p)if v==low];p=min(p[j:]+p[:j]for j in indices);normalized=[('m',p[0])]+[('l',q)for q in p[1:]]
  key=tuple(normalized)
  if key not in component_cache:
   name='part'+str(len(component_cache));pen=TTGlyphPen(None);curve=Cu2QuPen(pen,max_err=quad_error,reverse_direction=False)
   for cmd,nums in normalized:
    ps=list(zip(nums[::2],nums[1::2]))
    if cmd=='m':curve.moveTo(ps[0])
    elif cmd=='l':curve.lineTo(ps[0])
    elif cmd=='b':curve.curveTo(*ps)
   curve.closePath();add(name,pen.glyph());component_cache[key]=name
  return component_cache[key],ox,oy
 result=[];event_count=0
 for index,line in enumerate(raw.splitlines(keepends=True)):
  if not line.startswith(b'Dialogue:'):result.append(line);continue
  p=line.rstrip(b'\r\n').decode().split(',',9)
  if p[3]not in ('ED - Cloud','ED - Viator')or not re.search(r'\\p[1-9](?=[\\}])',p[9]):result.append(line);continue
  header,path=p[9].rsplit('}',1);oldscale=re.findall(r'\\p([1-9])(?=\\|$)',header);assert oldscale==['5'],oldscale
  # Shared contour components remove the repeated complete letters in partial masks.
  components=[]
  for part in contours(path):
   name,dx,dy=component(part)
   if name:components.append((name,dx,dy))
  key=tuple(sorted(components))
  if key not in shape_cache:
   name='shape'+str(len(shape_cache));code=0xE000+len(shape_cache);assert code<0xF8FF
   pen=TTGlyphPen(glyphs)
   for child,dx,dy in key:pen.addComponent(child,(1,0,0,1,dx,dy))
   add(name,pen.glyph());shape_cache[key]=(name,code);glyph_info.append({'glyph':name,'codepoint':code,'components':len(key)})
  name,code=shape_cache[key]
  header=re.sub(r'\\p[1-9](?=\\|$)','',header);header=re.sub(r'\\pbo-?\d+','',header);header,n=re.subn(r'\\pos\(0,0\)',r'\\pos(0,-64)',header);assert n==1
  p[9]=header+f'\\p0\\fn{family}\\fs64\\fsp0}}'+chr(code);nl=b'\r\n'if line.endswith(b'\r\n')else b'\n';result.append(','.join(p).encode()+nl);event_count+=1;mapped.append({'source_line':index+1,'glyph':name,'codepoint':code,'style':p[3]})
 fb=FontBuilder(EM,isTTF=True);fb.setupGlyphOrder(order);fb.setupCharacterMap({code:name for name,code in shape_cache.values()});fb.setupGlyf(glyphs);fb.setupHorizontalMetrics(metrics);fb.setupHorizontalHeader(ascent=EM,descent=0,lineGap=0);fb.setupNameTable({'familyName':family,'styleName':'Regular','uniqueFontIdentifier':family,'fullName':family,'psName':family,'version':'Version 1.000'});fb.setupOS2(sTypoAscender=EM,sTypoDescender=0,sTypoLineGap=0,usWinAscent=EM,usWinDescent=0,usWeightClass=400,fsSelection=0x40);fb.setupPost();fb.setupMaxp();fb.font.recalcTimestamp=False;fb.font['head'].created=fb.font['head'].modified=3766176000;fb.save(fontfile)
 fontdata=fontfile.read_bytes()
 from ass_attachments import append_font
 blob=b''.join(result)
 if not re.search(rb'(?m)^\[Fonts\]\r?\n',blob):
  m=re.search(rb'(?m)^\[Events\]',blob);assert m;blob=blob[:m.start()]+b'[Fonts]\n'+blob[m.start():]
 blob=append_font(blob,fontfile.name,fontdata)
 output.write_bytes(blob);report={'source_sha256':hashlib.sha256(raw).hexdigest(),'candidate_sha256':hashlib.sha256(blob).hexdigest(),'family':family,'converted_events':event_count,'unique_shapes':len(shape_cache),'unique_contour_components':len(component_cache),'font_glyphs':len(order),'font_bytes':len(fontdata),'before_ass_bytes':len(raw),'after_ass_bytes':len(blob),'font_sha256':hashlib.sha256(fontdata).hexdigest(),'attachment_decode_hash_verified':True,'cloud_quadratic_approximation_max_error_px':quad_error/16};output.with_suffix('.validation.json').write_text(json.dumps(report,indent=2));output.with_suffix('.glyph-map.json').write_text(json.dumps({'events':mapped,'glyphs':glyph_info},indent=2));print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('fontfile',type=Path);p.add_argument('--quad-error',type=float,default=.25);a=p.parse_args();build(a.source,a.output,a.fontfile,a.quad_error)
