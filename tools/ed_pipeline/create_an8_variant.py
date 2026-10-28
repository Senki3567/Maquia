#!/usr/bin/env python3
"""Independent top-centred ED layout; rebuild both cloud banks and their masks.
Starts from the current master plus the audited editable pre-glyph layout.
"""
from pathlib import Path
import re,json,hashlib,bisect,ctypes as C,argparse
import native_font_geometry as native
import glyph_geometry as geo
from cut_text_shapes import value,tokens
from cloud_clip import union_clip

def ms(t):
 h,m,s=t.split(':');return round((int(h)*3600+int(m)*60+float(s))*1000)
def stamp(t):
 c=round(t/10);return f'{c//360000}:{c//6000%60:02}:{c//100%60:02}.{c%100:02}'
def fmt(v):return f'{v:.6f}'.rstrip('0').rstrip('.')
def contours(path):return re.findall(r'm\s+[^m]+',path)
def translate(path,dx,dy):
 i=0
 def f(m):
  nonlocal i
  v=float(m[0])+(dx if i%2==0 else dy);i+=1;return fmt(v)
 return re.sub(r'-?\d+(?:\.\d+)?',f,path)
def ellipse_info(path):
 n=list(map(float,re.findall(r'-?\d+(?:\.\d+)?',path)));xs=n[::2];ys=n[1::2];return((min(xs)+max(xs))/2,(min(ys)+max(ys))/2,(max(xs)-min(xs))/2,(max(ys)-min(ys))/2)
def centred_cloud(path,cx,dy):
 parts=contours(path);assert len(parts)==16
 # Each bank contains paired body/crown ellipses. Recenter each bank as a unit,
 # retaining all individual growth, breakup, radius and drift differences.
 centers=[ellipse_info(c)[0]for c in parts];lower=(centers[0]+centers[8])/2;upper=(centers[10]+centers[14])/2
 return ' '.join(translate(p,cx-(lower if i<10 else upper),dy)for i,p in enumerate(parts))
def inset_mask(path):
 out=[]
 for part in contours(path):
  cx,cy,rx,ry=ellipse_info(part);nx=rx-4.08;ny=ry-4
  if min(nx,ny)<.3:continue
  i=0
  def f(m):
   nonlocal i
   v=float(m[0]);v=cx+(v-cx)*nx/rx if i%2==0 else cy+(v-cy)*ny/ry;i+=1;return fmt(v)
  out.append(re.sub(r'-?\d+(?:\.\d+)?',f,part))
 return union_clip(' '.join(out))if out else'm 0 0 l 0 0 0 0'
def rebase(text,delta):
 if delta==0:return text
 completed={}
 def trans(m):
  a,b=int(m[1]),int(m[2]);body=m[3]
  assert not(a<delta<b),('A split would restart an active transform',delta,m[0])
  if b<=delta:
   for k,v in tokens(body):completed[k]=v
   return ''
  return f'\\t({a-delta},{b-delta},{body})'
 text=re.sub(r'\\t\((\d+),(\d+),(\\[^)]*)\)',trans,text)
 for k,v in completed.items():
  pattern=r'\\'+re.escape(k)+r'(?![a-z])[^\\}()]*'
  text,n=re.subn(pattern,lambda m:'\\'+k+v,text,count=1);assert n==1,(k,text[:150])
 return text

def build(master,source,output,work,cx=960,dy=-775):
 raw=master.read_bytes();work.mkdir(parents=True,exist_ok=True);source_raw=source.read_bytes();src=source_raw.splitlines(keepends=True)
 # Do not silently retarget stale lyrics or ignore current edits to native rows.
 master_native=[l.split(b',',9)for l in raw.splitlines()if l.startswith(b'Dialogue:')and l.split(b',',9)[3]==b'ED - Viator'and b'MaquiaEDCFF'not in l]
 source_native=[l.split(b',',9)for l in source_raw.splitlines()if l.startswith(b'Dialogue:')and l.split(b',',9)[3]==b'ED - Viator'and b'\\clip('not in l]
 assert master_native==source_native,'Current native ED rows differ from audited source; reconcile edits first'
 comments={l.split(b',',9)[8].decode():l.split(b',',9)[9].decode()for l in raw.splitlines()if l.startswith(b'Comment:')and l.split(b',',9)[8].startswith(b'ED_SOURCE:')};assert len(comments)==42
 rows=[l.decode().rstrip('\r\n').split(',',9)for l in src if l.startswith(b'Dialogue:')and l.split(b',',9)[3]in[b'ED - Cloud',b'ED - Viator']]
 white=[];cloud_rows=[];layouts={};groups=[];counts={'VI':0,'JP':0};group=None
 for p in rows:
  if p[3]!='ED - Viator':continue
  lyric=re.sub(r'\{[^}]*\}','',p[9]);lang='JP'if '\\fnNoto Serif JP'in p[9]else'VI'
  if group is None or(group['lang'],group['lyric'])!=(lang,lyric):
   counts[lang]+=1;group={'lang':lang,'pair':counts[lang],'lyric':lyric};groups.append(group);key=f'ED_SOURCE:P{counts[lang]:02}:{lang}';assert comments[key].strip()==lyric.strip(),('Current source lyric differs',key)
  p.append((group['lang'],group['pair']))
  if p[4]in['','scene-color-P01']:
   text=p[9];jp=lang=='JP';fs=value(text,'fs',48 if jp else 52);fx=value(text,'fscx',100);fy=value(text,'fscy',100);sp=value(text,'fsp',0);px,py=map(float,re.search(r'\\pos\(([^,]+),([^)]+)\)',text).groups());_,_,advance,desc=native.outline(lyric,jp,fs,fx,fy,sp);asc,_=native.line_metrics(jp,fs,fy);top=py-desc-asc+dy;layouts[p[10]]={'pair':group['pair'],'language':lang,'lyric':lyric,'top_anchor':[cx,top],'old_advance':advance,'vertical_shift':dy}
 assert counts=={'VI':21,'JP':21}
 for p in rows:
  if p[3]!='ED - Cloud':continue
  h,path=p[9].rsplit('}',1);newpath=centred_cloud(path,cx,dy);p[9]=h+'}'+newpath;cloud_rows.append(p[:10])
  if p[0]=='Dialogue: 1':white.append({'a':ms(p[1]),'z':ms(p[2]),'path':newpath,'mask':None})
 white.sort(key=lambda x:x['a']);starts=[x['a']for x in white]
 def at(t):
  i=bisect.bisect_right(starts,t)-1
  if i<0 or t>=white[i]['z']:return None
  return white[i]
 def mask(s):
  if s is None:return'm 0 0 l 0 0 0 0'
  if s['mask']is None:s['mask']=inset_mask(s['path'])
  return s['mask']
 final_text=[];splits=0
 for p in rows:
  if p[3]!='ED - Viator':continue
  row=p[:10];text=row[9];jp=p[10][0]=='JP';fs=value(text,'fs',48 if jp else 52);fy=value(text,'fscy',100);_,desc=native.line_metrics(jp,fs,fy);asc,_=native.line_metrics(jp,fs,fy);oldpy=float(re.search(r'\\pos\([^,]+,([^)]+)\)',text)[1]);top=oldpy-asc-desc+dy
  text=re.sub(r'\\an3(?=[\\}])',r'\\an8',text);text=re.sub(r'\\pos\([^)]*\)',lambda m:f'\\pos({fmt(cx)},{fmt(top)})',text);text=re.sub(r'\\i?clip\([^)]*\)','',text)
  phase=p[4].startswith(('flow-','cloud-in-','cloud-out-'))
  if not phase:row[9]=text;final_text.append(row);continue
  a,z=ms(p[1]),ms(p[2]);boundaries={a,z}
  for frame in white:
   if a<frame['a']<z:boundaries.add(frame['a'])
   if a<frame['z']<z:boundaries.add(frame['z'])
  cuts=sorted(boundaries);splits+=len(cuts)-2
  for begin,end in zip(cuts,cuts[1:]):
   r=row.copy();r[1]=stamp(begin);r[2]=stamp(end);r[9]='{\\clip('+mask(at(begin))+')}'+rebase(text,begin-a);final_text.append(r)
 ed=iter([*cloud_rows,*final_text]);replacement=['.'.encode()]
 # Keep current non-ED events, comments and project metadata, replacing only ED.
 out=[];inserted=False
 for l in raw.splitlines(keepends=True):
  if l.startswith(b'Dialogue:')and l.split(b',',9)[3]in[b'ED - Cloud',b'ED - Viator']:
   if not inserted:
    out.extend(','.join(r).encode()+b'\n'for r in ed);inserted=True
  elif l.startswith(b'Style: ED - Viator,')or l.startswith(b'Style: ED - Cloud,'):
   p=l.rstrip(b'\r\n').split(b',');p[18]=b'8';out.append(b','.join(p)+b'\n')
  else:out.append(l)
 blob=b''.join(out);output.write_bytes(blob);cfg={'master':str(master.resolve()),'master_sha256':hashlib.sha256(raw).hexdigest(),'audited_editable_source':str(source.resolve()),'source_sha256':hashlib.sha256(source_raw).hexdigest(),'center_x':cx,'vertical_shift':dy,'glyph_anchor':[cx,40],'layouts':list(layouts.values()),'cloud_events':len(cloud_rows),'text_events':len(final_text),'added_phase_splits':splits,'native_main_rows':42,'all_phase_masks_rebuilt_from_recentered_cloud':True,'cloud_bank_rule':'Recenter upper and lower banks independently at each original snapshot; retain cubic contours, scale, breakup and relative drift.'};(work/'layout.json').write_text(json.dumps(cfg,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in cfg.items()if k!='layouts'},indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('master',type=Path);p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('work',type=Path);p.add_argument('--dy',type=float,default=-775);a=p.parse_args();build(a.master,a.source,a.output,a.work,dy=a.dy)
