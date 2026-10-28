#!/usr/bin/env python3
"""Compact approved ED drawings; optionally simplify baked glyph geometry.
Preserve all appearance/timing tags and protected lines byte-for-byte.
"""
from pathlib import Path
import re,argparse,json,hashlib,collections,ctypes as C
import glyph_geometry as geo
geo.bind(geo.G,'GEOSTopologyPreserveSimplify',[geo.P,C.c_double],geo.P)

def compact_path(path,old_scale,new_scale):
 scale=2**(new_scale-old_scale)
 def number(m):return str(round(float(m[0])*scale))
 out=re.sub(r'-?\d+(?:\.\d+)?',number,path)
 # ASS permits repeated coordinate groups after l/b without repeating command.
 tokens=out.split();result=[];command=None
 for t in tokens:
  if t in ('m','n','l','b','s','p','c'):
   if t==command and t in ('l','b'):continue
   command=t
  result.append(t)
 return ' '.join(result)

def run(source,output,tolerance,scale):
 raw=source.read_bytes();result=[];counts=collections.Counter();before_pts=after_pts=0
 for line in raw.splitlines(keepends=True):
  if not line.startswith(b'Dialogue:'):result.append(line);continue
  p=line.rstrip(b'\r\n').decode().split(',',9)
  if p[3] not in ('ED - Viator','ED - Cloud') or not re.search(r'\\p[1-9](?=[\\}])',p[9]):result.append(line);continue
  header,path=p[9].rsplit('}',1);m=re.findall(r'\\p([1-9])(?=\\|$)',header);assert len(m)==1;oldscale=int(m[0])
  if oldscale!=1:
   divisor=2**(oldscale-1);path=re.sub(r'-?\d+(?:\.\d+)?',lambda m:format(float(m[0])/divisor,'.8f').rstrip('0').rstrip('.'),path);oldscale=1
  before_pts+=len(re.findall(r'-?\d+(?:\.\d+)?',path))//2
  if p[3]=='ED - Viator' and tolerance and len(re.findall(r'-?\d+(?:\.\d+)?',path))>=6:
   assert set(re.findall(r'[a-z]',path))<=set('ml')
   g=geo.mask_geometry(path);simple=geo.G.GEOSTopologyPreserveSimplify(g,tolerance);assert simple;geo.G.GEOSGeom_destroy(g);path=geo.ass_path(simple);geo.G.GEOSGeom_destroy(simple);counts['glyph_shapes_simplified']+=1
  path=compact_path(path,oldscale,scale);after_pts+=len(re.findall(r'-?\d+(?:\.\d+)?',path))//2
  header,n=re.subn(r'\\p[1-9](?=\\|$)',lambda m:'\\p'+str(scale),header);assert n==1;p[9]=header+'}'+path;nl=b'\r\n'if line.endswith(b'\r\n')else b'\n';result.append(','.join(p).encode()+nl);counts[p[3]]+=1
 new=b''.join(result);oldlines=raw.splitlines(keepends=True);newlines=new.splitlines(keepends=True);assert len(oldlines)==len(newlines)
 for a,b in zip(oldlines,newlines):
  if a==b:continue
  x,y=a.split(b',',9),b.split(b',',9);assert x[:9]==y[:9] and x[3]in(b'ED - Cloud',b'ED - Viator')
 output.write_bytes(new);report={'source_sha256':hashlib.sha256(raw).hexdigest(),'candidate_sha256':hashlib.sha256(new).hexdigest(),'before_bytes':len(raw),'after_bytes':len(new),'reduction_percent':round(100*(1-len(new)/len(raw)),2),'counts':dict(counts),'before_coordinate_pairs':before_pts,'after_coordinate_pairs':after_pts,'native_simplification_tolerance_px':tolerance,'drawing_scale':scale,'coordinate_quantization_step_px':1/2**(scale-1),'all_other_Text_tags_and_event_fields_preserved':True,'non_ED_bytes_unchanged':True};output.with_suffix('.validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--tolerance',type=float,default=.10);p.add_argument('--scale',type=int,default=5);a=p.parse_args();run(a.source,a.output,a.tolerance,a.scale)
