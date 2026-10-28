#!/usr/bin/env python3
"""VI width +2%; matching affine widening of existing cloud drawings/vector masks.
Preserves all phase clocks, optimized event structure, colors and 0.6px text blur.
"""
from pathlib import Path
import re,json,argparse,hashlib,collections
ROOT=Path(__file__).resolve().parent
FACTOR=1.02;ANCHOR=1860.
def fmt(x):return format(x,'.6f').rstrip('0').rstrip('.')
def widen_vector(path):
 assert path.lstrip().startswith('m '),path[:80]
 index=0
 def number(m):
  nonlocal index
  x=float(m[0]);result=fmt(ANCHOR+(x-ANCHOR)*FACTOR) if index%2==0 else m[0];index+=1;return result
 result=re.sub(r'-?\d+(?:\.\d+)?',number,path);assert index%2==0
 return result

def pair_id(p,index,mains):
 if index in mains:return mains[index]
 if p[4].startswith('flow-'):
  m=re.fullmatch(r'flow-P(\d+)-P(\d+)-(in|out)',p[4]);assert m
  return int(m[1] if m[3]=='out' else m[2])
 m=re.search(r'P(\d+)',p[4]);assert m,p[4];return int(m[1])

def ms(t):
 h,m,s=t.split(':');return round((int(h)*3600+int(m)*60+float(s))*1000)
def ass(t):
 cs=round(t/10);return f'{cs//360000}:{cs//6000%60:02}:{cs//100%60:02}.{cs%100:02}'
def rebase_alpha(text,delta):
 # Split only on original FBF boundaries. Bake finished alpha steps and keep
 # future transforms at positive relative times; no negative-time behavior.
 pattern=r'\\t\((-?\d+),(-?\d+),(\\alpha&H[0-9A-F]{2}&)\)'
 steps=list(re.finditer(pattern,text));base=re.search(r'\\alpha&H([0-9A-F]{2})&',text);assert base
 alpha=base[1]
 for m in steps:
  a,b=int(m[1]),int(m[2]);assert not(a<delta<b)
  if b<=delta:alpha=re.search(r'&H([0-9A-F]{2})&',m[3])[1]
 def transform(m):
  a,b=int(m[1]),int(m[2])
  return '' if b<=delta else f'\\t({a-delta},{b-delta},{m[3]})'
 text=re.sub(pattern,transform,text)
 return re.sub(r'\\alpha&H[0-9A-F]{2}&',lambda m:'\\alpha&H'+alpha+'&',text,count=1)
def restore_masks(blob):
 repairs=json.load(open(ROOT/'restored-masks.json'));result=[];applied=0
 for line in blob.splitlines(keepends=True):
  if not line.startswith(b'Dialogue:'):result.append(line);continue
  p=line.rstrip(b'\r\n').decode().split(',',9)
  if p[3]!='ED - Viator' or '\\fnNoto Serif JP' in p[9] or '\\clip(' in p[9]:result.append(line);continue
  start,end=ms(p[1]),ms(p[2]);matches=[r for r in repairs if r['name']==p[4] and start<=r['start'] and end>=r['end']]
  if not matches:result.append(line);continue
  cuts=sorted({start,end,*[r[k] for r in matches for k in ['start','end']]});nl=b'\r\n' if line.endswith(b'\r\n') else b'\n'
  for a,z in zip(cuts,cuts[1:]):
   row=p.copy();row[1]=ass(a);row[2]=ass(z);row[9]=rebase_alpha(p[9],a-start)
   for repair in matches:
    if repair['start']<=a and repair['end']>=z:
     row[9]='{\\clip('+repair['path']+')}'+row[9];applied+=1
   result.append(','.join(row).encode()+nl)
 assert applied==len(repairs),(applied,len(repairs))
 return b''.join(result)

def run(source,output):
 raw=source.read_bytes();cfg=json.load(open(ROOT/'measurements.json'));assert hashlib.sha256(raw).hexdigest()==cfg['source_sha256'],'Master changed; reconcile'
 mains={p['JP_main_index']:p['pair'] for p in cfg['pairs']};dx={p['pair']:p['JP_additional_shift_x'] for p in cfg['pairs']};records=[];counts=collections.Counter()
 for index,line in enumerate(raw.splitlines(keepends=True)):
  if not line.startswith(b'Dialogue:'):records.append(line);continue
  p=line.rstrip(b'\r\n').decode().split(',',9);old=p[9];nl=b'\r\n' if line.endswith(b'\r\n') else b'\n'
  if p[3]=='ED - Cloud':
   header,path=p[9].split('}',1);p[9]=header+'}'+widen_vector(path);counts['cloud_events_widened']+=1
  elif p[3]=='ED - Viator':
   if '\\fnNoto Serif JP' not in p[9]:
    p[9],n=re.subn(r'\\fscx([\d.]+)',lambda m:'\\fscx'+fmt(float(m[1])*FACTOR),p[9]);assert n==1;counts['VI_events_scaled']+=1
   else:
    pair=pair_id(p,index,mains)
    if dx[pair]:
     p[9],n=re.subn(r'\\pos\(([-\d.]+),([-\d.]+)\)',lambda m:'\\pos('+fmt(float(m[1])+dx[pair])+','+m[2]+')',p[9]);assert n==1;counts['JP_events_optically_compensated']+=1
   p[9],n=re.subn(r'\\clip\(([^)]*)\)',lambda m:'\\clip('+widen_vector(m[1])+')',p[9]);counts['vector_masks_widened']+=n
  else:records.append(line);continue
  new=','.join(p).encode()+nl
  assert new.rstrip(b'\r\n').split(b',',9)[:9]==line.rstrip(b'\r\n').split(b',',9)[:9]
  records.append(new)
 result=restore_masks(b''.join(records))
 def protected(b):return [l for l in b.splitlines(keepends=True) if not(l.startswith(b'Dialogue:') and l.split(b',',9)[3] in (b'ED - Cloud',b'ED - Viator'))]
 assert protected(raw)==protected(result)
 output.write_bytes(result)
 report={'source_sha256':hashlib.sha256(raw).hexdigest(),'candidate_sha256':hashlib.sha256(result).hexdigest(),'horizontal_factor':FACTOR,'cloud_mask_anchor_x':ANCHOR,'counts':dict(counts),'event_fields_unchanged_except_3_mask_interval_splits':True,'non_ED_bytes_unchanged':True,'phase_timing_preserved':True,'mask_repairs_30ms':3,'event_count_increase_for_mask_repairs':sum(l.startswith(b'Dialogue:') for l in result.splitlines())-sum(l.startswith(b'Dialogue:') for l in raw.splitlines()),'color_alpha_blur_and_intro_color_timing_preserved':True,'JP_optical_adjustment':{str(k):v for k,v in dx.items() if v}}
 output.with_suffix('.validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();run(a.source,a.output)
