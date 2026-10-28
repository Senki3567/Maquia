#!/usr/bin/env python3
"""Bake only ED text vector clips into actual font-outline intersections.
The full editable input and per-row source mapping remain in the output directory.
"""
from pathlib import Path
import argparse,re,json,hashlib,collections
import glyph_geometry as geo
import native_font_geometry as native

def value(tags,name,default):
 matches=re.findall(r'\\'+name+r'(-?\d+(?:\.\d+)?)',tags);return float(matches[-1]) if matches else default

def get_geometry(text):
 jp='\\fnNoto Serif JP'in text;lyric=re.sub(r'\{[^}]*\}','',text);fs=value(text,'fs',48 if jp else 52);fx=value(text,'fscx',100);fy=value(text,'fscy',100);pos=re.findall(r'\\pos\(([-\d.]+),([-\d.]+)\)',text);assert len(pos)==1;px,py=map(float,pos[0]);assert '\\N'not in lyric and '\\n'not in lyric
 # Layout transforms need time-dependent geometry; reject rather than silently bake.
 for body in re.findall(r'\\t\(([^)]*)\)',text):
  assert not re.search(r'\\(?:pos|move|fs[pcxy]*|fr[xyz]|fa[xy])',body),body
 assert not re.search(r'\\(?:move|fr[xyz]|fa[xy])',text),text
 wkt,rings,advance,desc=native.outline(lyric,jp,fs,fx,fy,value(text,'fsp',0))
 align=value(text,'an',3)
 if align==3:dx,dy=px-advance,py-desc
 elif align==2:dx,dy=px-advance/2,py-desc
 elif align==8:dx,dy=px-advance/2,py+native.line_metrics(jp,fs,fy)[0]
 else:raise AssertionError(('Unsupported glyph anchor',align))
 return geo.translated(wkt,dx,dy),lyric,jp

def tokens(content):
 i=0
 while i<len(content):
  if content[i]!='\\':i+=1;continue
  m=re.match(r'\\([1-4]?[a-z]+)',content[i:]);assert m,content[i:i+30];name=m[1];j=i+len(m[0]);k=j;depth=0
  while k<len(content):
   if content[k]=='(' :depth+=1
   elif content[k]==')':depth-=1
   if content[k]=='\\' and depth==0:break
   k+=1
  yield name,content[j:k];i=k

def appearance(text,jp):
 def keep(content):
  out=''
  for name,arg in tokens(content):
   if name=='t':
    m=re.fullmatch(r'\(([^\\]*)(\\.*)\)',arg);assert m,arg
    child=keep(m[2]);out+=('\\t('+m[1]+child+')') if child else ''
   elif name in ['blur','alpha']:out+='\\'+name+arg
   elif jp and name in ['4c','4a']:out+='\\'+('c' if name=='4c' else '1a')+arg
   elif not jp and name in ['c','1c','1a']:out+='\\'+name+arg
  return out
 return ''.join(keep(block) for block in re.findall(r'\{([^}]*)\}',text))

def validate_cut_tags(text):
 # Fail before discarding a newly introduced effect; these are the audited tags.
 allowed={'blur','t','alpha','clip','iclip','an','pos','fscx','fscy','fsp','shad','c','1c','2c','3c','4c','1a','2a','3a','4a','ybord','xbord','bord','b','fs','fn','ko'}
 dynamic={'blur','alpha','c','1c','2c','3c','4c','1a','2a','3a','4a'}
 def check(content,in_transform=False):
  for name,arg in tokens(content):
   assert name in (dynamic if in_transform else allowed),('Unsupported effect would be lost',name,arg)
   if name=='t':
    m=re.fullmatch(r'\(([^\\]*)(\\.*)\)',arg);assert m,arg;check(m[2],True)
   elif name=='ko':assert float(arg)==0,('Karaoke is not static',arg)
   elif name=='b':assert float(arg)==0,('Bold must be included in glyph geometry',arg)
   elif name=='shad':assert abs(float(arg))<=.001,('Shadow must be included in glyph geometry',arg)
   elif name=='an':assert int(arg)in(2,3,8),('Unsupported glyph anchor',arg)
 for content in re.findall(r'\{([^}]*)\}',text):check(content)
 for name in ['bord','xbord','ybord']:assert value(text,name,-1)==0,('Cut glyphs require an explicitly borderless phase',name)


def make_shape(text,cut=True):
 validate_cut_tags(text)
 wkt,lyric,jp=get_geometry(text);g=geo.read(wkt);m=re.findall(r'\\(i?clip)\(([^)]*)\)',text)
 if cut:
  assert len(m)==1
  inv,path=m[0];assert path.lstrip().startswith('m '),path[:60];mask=geo.mask_geometry(path);g=geo.op('GEOSDifference' if inv=='iclip' else 'GEOSIntersection',g,mask)
 if geo.G.GEOSisEmpty(g):path='m 0 0 l 0 0 0 0'
 else:path=geo.ass_path(g)
 geo.G.GEOSGeom_destroy(g)
 # Full appearance is retained, with JP shadow-based glyphs mapped to shape fill.
 result='{\\an7\\pos(0,0)\\fscx100\\fscy100\\fsp0\\bord0\\shad0\\pbo0'+appearance(text,jp)+'\\p1}'+path
 assert '\\clip('not in result and '\\iclip('not in result
 return result,lyric,jp

def run(source,output):
 raw=source.read_bytes();assert not re.search(rb'(?mi)^Kerning:\s*(?:yes|1)\s*$',raw),'Explicit kerning needs to be passed to the layout engine';lines=raw.splitlines(keepends=True);result=[];mapping=[];counts=collections.Counter()
 for index,line in enumerate(lines):
  if not line.startswith(b'Dialogue:'):result.append(line);continue
  p=line.rstrip(b'\r\n').decode().split(',',9)
  if p[3]!='ED - Viator' or not re.search(r'\\i?clip\(',p[9]):result.append(line);continue
  old=p[9];p[9],lyric,jp=make_shape(old);nl=b'\r\n'if line.endswith(b'\r\n')else b'\n';result.append(','.join(p).encode()+nl);counts['JP'if jp else 'VI']+=1;mapping.append({'physical_line':index+1,'language':'JP'if jp else 'VI','lyric':lyric,'original_event':line.decode().rstrip('\r\n')})
  if len(mapping)%100==0:print('converted',len(mapping),flush=True)
 new=b''.join(result);assert len(lines)==len(new.splitlines(keepends=True))
 for old,newline in zip(lines,new.splitlines(keepends=True)):
  if old==newline:continue
  a,b=old.split(b',',9),newline.split(b',',9);assert a[:9]==b[:9]and a[3]==b'ED - Viator'and b'\\clip('in a[9]
 output.write_bytes(new);output.with_suffix('.source-map.json').write_text(json.dumps(mapping,ensure_ascii=False,indent=2));report={'source_sha256':hashlib.sha256(raw).hexdigest(),'candidate_sha256':hashlib.sha256(new).hexdigest(),'converted_events':dict(counts),'total_converted':len(mapping),'remaining_ED_text_clips':sum(b'\\clip('in l.split(b',',9)[9]for l in new.splitlines()if l.startswith(b'Dialogue:')and l.split(b',',9)[3]==b'ED - Viator'),'only_previously_clipped_ED_Text_changed':True,'flatten_tolerance_native_px':.08,'outline_sources':{'VI':geo.FONT_VI,'JP':geo.FONT_JP},'JP_variable_weight':400,'JP_renderer_ink_compensation_radius_px':0,'layout_engine':'FreeType 256px + HarfBuzz with libass metrics and spacing'};output.with_suffix('.validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();run(a.source,a.output)
