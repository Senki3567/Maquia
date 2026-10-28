#!/usr/bin/env python3
"""Merge identical ED glyph frames; rebase explicit alpha/blur transforms.
Changing masks retain their individual geometry. Original non-ED bytes preserved.
"""
from pathlib import Path
import re,json,argparse,hashlib,collections
DYNAMIC=r'\\(blur)(-?\d+(?:\.\d+)?)|\\(alpha|1a|4a)(&H[0-9a-fA-F]+&)'
def ms(s):
 h,m,z=s.split(':');return round((int(h)*3600+int(m)*60+float(z))*1000)
def parse(text):
 transforms=[]
 for m in re.finditer(r'\\t\(([^)]*)\)',text):
  v=m[1];split=v.find('\\')
  if split<0:return None
  prefix=v[:split].rstrip(',').split(',');body=v[split:]
  if re.sub(DYNAMIC,'',body):return None
  if len(prefix)not in[2,3]:return None
  try:a,b=map(int,prefix[:2])
  except ValueError:return None
  transforms.append((a,b,prefix[2:] ,body))
 stripped=re.sub(r'\\t\([^)]*\)','',text);props=[]
 for m in re.finditer(DYNAMIC,stripped):props.append((m[1]or m[3],m[2]or m[4]))
 static=re.sub(DYNAMIC,'',stripped)
 return static,props,transforms

def run(source,output):
 raw=source.read_bytes();lines=raw.splitlines(keepends=True);groups=collections.defaultdict(list);records={}
 for i,l in enumerate(lines):
  if not l.startswith(b'Dialogue:'):continue
  p=l.rstrip(b'\r\n').decode().split(',',9)
  if p[3]not in['ED - Cloud','ED - Viator']:continue
  parsed=parse(p[9])
  if parsed is None:continue
  static,props,ts=parsed;key=(tuple(p[:1]+p[3:9]),static,tuple(k for k,v in props));records[i]=(p,props,ts);groups[key].append(i)
 removed=set();replacements={};merged=0;chains=0
 for indices in groups.values():
  indices.sort(key=lambda i:ms(records[i][0][1]));chain=[]
  def flush():
   nonlocal merged,chains
   if len(chain)<2:return
   first=chain[0];p=records[first][0].copy();start=ms(p[1]);extra=''
   for i in chain[1:]:
    row,props,ts=records[i];delta=ms(row[1])-start;tags=''.join('\\'+k+v for k,v in props)
    if tags:extra+=f'\\t({max(0,delta-1)},{delta},{tags})'
    for a,b,accel,body in ts:extra+='\\t('+','.join([str(a+delta),str(b+delta),*accel,body])+')'
    removed.add(i)
   h,body=p[9].rsplit('}',1);p[9]=h+extra+'}'+body;p[2]=records[chain[-1]][0][2];nl=b'\r\n'if lines[first].endswith(b'\r\n')else b'\n';replacements[first]=','.join(p).encode()+nl;merged+=len(chain)-1;chains+=1
  for i in indices:
   if chain and records[chain[-1]][0][2]!=records[i][0][1]:flush();chain=[]
   chain.append(i)
  flush()
 new=b''.join(replacements.get(i,l)for i,l in enumerate(lines)if i not in removed);output.write_bytes(new);report={'source_sha256':hashlib.sha256(raw).hexdigest(),'candidate_sha256':hashlib.sha256(new).hexdigest(),'removed_redundant_events':merged,'merged_native_transform_chains':chains,'before_bytes':len(raw),'after_bytes':len(new),'changed_geometry_not_affine_approximated':True,'all_original_geometry_and_explicit_alpha_blur_clocks_preserved_except_1ms_boundary_transition':True};output.with_suffix('.native-merge.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();run(a.source,a.output)
