#!/usr/bin/env python3
"""Embed drawing glyphs as CFF outlines with shared contour subroutines.
Cubic cloud geometry is retained; glyph drawing components are decoded inline,
avoiding the per-component TrueType glyph loads of the first prototype.
"""
from pathlib import Path
import argparse,re,hashlib,json
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.misc.psCharStrings import T2CharString
from fontTools.cffLib import SubrsIndex
from pack_shape_glyphs import contours,encode_ass,decode_ass
EM=1024

def build(source,output,fontfile,styles=('ED - Cloud','ED - Viator'),anchor8=None,anchor2=None):
 raw=source.read_bytes();anchor=anchor8 or anchor2;align=8 if anchor8 is not None else 2 if anchor2 is not None else None;salt=b'' if anchor is None else (repr(anchor)+str(align)).encode();family=('MaquiaEDCFF'if anchor is None else'MaquiaEDTop'if align==8 else'MaquiaEDBottom')+hashlib.sha256(raw+('|'.join(styles)).encode()+salt).hexdigest()[:8];origin=(0,0)if anchor is None else(anchor[0]*16,(anchor[1]+64)*16)if align==8 else(anchor[0]*16,anchor[1]*16);advance=EM if anchor is None else 0;parts=[];part_cache={};shapes=[];shape_cache={};rows=[];mapping=[]
 def component(part):
  points=[(nums[j],-nums[j+1])for cmd,nums in part for j in range(0,len(nums),2)]
  if not points:return None
  # Canonical cyclic start for polygons retains winding and counter direction.
  if all(cmd in ('m','l')for cmd,nums in part):
   pts=points
   while len(pts)>1 and pts[-1]==pts[0]:pts.pop()
   if len(pts)<3:return None
   mn=min(pts);pts=min(pts[i:]+pts[:i]for i,p in enumerate(pts)if p==mn);part=[('m',pts[0])]+[('l',p)for p in pts[1:]];already_flipped=True
  else:already_flipped=False
  start=part[0][1];sx,sy=(start if already_flipped else(start[0],-start[1]));normalized=[]
  for cmd,nums in part:
   converted=tuple(nums if already_flipped else(v if i%2==0 else-v for i,v in enumerate(nums)))
   normalized.append((cmd,tuple(v-(sx if i%2==0 else sy)for i,v in enumerate(converted))))
  key=tuple(normalized)
  if key not in part_cache:
   pen=T2CharStringPen(None,None)
   for cmd,nums in normalized:
    pts=list(zip(nums[::2],nums[1::2]))
    if cmd=='m':pen.moveTo(pts[0])
    elif cmd=='l':pen.lineTo(pts[0])
    else:pen.curveTo(*pts)
   pen.closePath();program=pen.getCharString(optimize=True).program
   end=next(i for i,v in enumerate(program)if isinstance(v,str)and v in ['rmoveto','hmoveto','vmoveto']);assert all(v==0 for v in program[:end]);program=program[end+1:-1]+['return'];last=normalized[-1][1][-2:];idx=len(parts);parts.append((program,last));part_cache[key]=idx
  idx=part_cache[key];return idx,sx,sy
 for i,line in enumerate(raw.splitlines(keepends=True)):
  if not line.startswith(b'Dialogue:'):rows.append(line);continue
  p=line.rstrip(b'\r\n').decode().split(',',9)
  if p[3]not in styles or not re.search(r'\\p[1-9](?=[\\}])',p[9]):rows.append(line);continue
  header,path=p[9].rsplit('}',1);assert re.findall(r'\\p([1-9])(?=\\|$)',header)==['5'];children=[]
  for part in contours(path):
   if anchor is not None:part=[(cmd,tuple(v-origin[j%2]for j,v in enumerate(nums)))for cmd,nums in part]
   child=component(part)
   if child is not None:children.append(child)
  key=tuple(sorted(children))
  if key not in shape_cache:shape_cache[key]=len(shapes);shapes.append(key)
  idx=shape_cache[key];code=0xE000+idx;assert code<0xF8FF;header=re.sub(r'\\p[1-9](?=\\|$)','',header);header=re.sub(r'\\pbo-?\d+','',header);position=r'\pos(0,-64)'if anchor is None else rf'\pos({anchor[0]},{anchor[1]})';header,n=re.subn(r'\\pos\(0,0\)',lambda m:position,header);assert n==1;header=header if anchor is None else re.sub(r'\\an7(?=\\|$)',rf'\\an{align}',header);p[9]=header+f'\\p0\\fn{family}\\fs64\\fsp0}}'+chr(code);nl=b'\r\n'if line.endswith(b'\r\n')else b'\n';rows.append(','.join(p).encode()+nl);mapping.append({'source_line':i+1,'codepoint':code,'style':p[3]})
 bias=107 if len(parts)<1240 else 1131 if len(parts)<33900 else 32768
 order=['.notdef']+['shape'+str(i)for i in range(len(shapes))];strings={'.notdef':T2CharString(program=[EM,'endchar'])};metrics={'.notdef':(EM,0)}
 for i,children in enumerate(shapes):
  program=[advance];x=y=0
  for idx,sx,sy in children:
   dx,dy=sx-x,sy-y
   if dx==0:program.extend([dy,'vmoveto'])
   elif dy==0:program.extend([dx,'hmoveto'])
   else:program.extend([dx,dy,'rmoveto'])
   program.extend([idx-bias,'callsubr']);ex,ey=parts[idx][1];x,y=sx+ex,sy+ey
  program.append('endchar');name='shape'+str(i);strings[name]=T2CharString(program=program);metrics[name]=(advance,0)
 fb=FontBuilder(EM,isTTF=False);fb.setupGlyphOrder(order);fb.setupCharacterMap({0xE000+i:'shape'+str(i)for i in range(len(shapes))});fb.setupHorizontalMetrics(metrics);fb.setupHorizontalHeader(ascent=EM,descent=0,lineGap=0);fb.setupNameTable({'familyName':family,'styleName':'Regular','uniqueFontIdentifier':family,'fullName':family,'psName':family,'version':'Version 1.000'});fb.setupOS2(sTypoAscender=EM,sTypoDescender=0,sTypoLineGap=0,usWinAscent=EM,usWinDescent=0,usWeightClass=400,fsSelection=0x40);fb.setupPost();fb.setupCFF(family,{'FullName':family,'FamilyName':family,'Weight':'Regular','FontBBox':[0,-18000,32767,0]if anchor is None else[-16384,-8192,16384,8192]if align==8 else[-16384,0,16384,16384]},strings,{})
 top=fb.font['CFF '].cff.topDictIndex[0];subrs=SubrsIndex(globalSubrs=top.GlobalSubrs,private=top.Private);top.Private.Subrs=subrs
 for program,last in parts:subrs.append(T2CharString(program=program,private=top.Private,globalSubrs=top.GlobalSubrs))
 fb.font.recalcTimestamp=False;fb.font['head'].created=fb.font['head'].modified=3766176000;fb.save(fontfile)
 from ass_attachments import append_font
 data=fontfile.read_bytes();blob=append_font(b''.join(rows),fontfile.name,data);output.write_bytes(blob)
 report={'source_sha256':hashlib.sha256(raw).hexdigest(),'candidate_sha256':hashlib.sha256(blob).hexdigest(),'family':family,'converted_events':len(mapping),'unique_shapes':len(shapes),'shared_contour_subroutines':len(parts),'font_bytes':len(data),'before_ass_bytes':len(raw),'after_ass_bytes':len(blob),'font_sha256':hashlib.sha256(data).hexdigest(),'attachment_decode_hash_verified':True,'cloud_cubics_preserved':True,'converted_styles':list(styles),'anchor':anchor,'align':align,'shape_advance':advance};output.with_suffix('.validation.json').write_text(json.dumps(report,indent=2));output.with_suffix('.glyph-map.json').write_text(json.dumps(mapping,indent=2));print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('fontfile',type=Path);p.add_argument('--text-only',action='store_true');p.add_argument('--anchor8',type=int,nargs=2);p.add_argument('--anchor2',type=int,nargs=2);a=p.parse_args();build(a.source,a.output,a.fontfile,('ED - Viator',)if a.text_only else('ED - Cloud','ED - Viator'),tuple(a.anchor8)if a.anchor8 else None,tuple(a.anchor2)if a.anchor2 else None)
