from pathlib import Path
import sys,json,re,numpy as np,hashlib
sys.path.insert(0,'/home/cuongba956/.codex/skills/ass-studio/scripts')
from libass_render import Renderer
ROOT=Path(__file__).resolve().parent
SOURCE=Path('work/alignment/before.ass')
def ms(t):
 h,m,s=t.split(':');return round((int(h)*3600+int(m)*60+float(s))*1000)
def language(p):return 'JP' if '\\fnNoto Serif JP' in p[9] else 'VI'
def main_rows(raw):
 rows={'VI':[],'JP':[]}
 for index,line in enumerate(raw.splitlines(keepends=True)):
  if not line.startswith(b'Dialogue:'):continue
  p=line.rstrip(b'\r\n').decode().split(',',9)
  if p[3]=='ED - Viator' and p[4] in ['', 'scene-color-P01']:rows[language(p)].append((index,p))
 for lang in rows:rows[lang].sort(key=lambda r:ms(r[1][1]));assert len(rows[lang])==21,(lang,len(rows[lang]))
 return rows

def measure(r,p,dx=0):
 row=p.copy();row[1]='0:00:00.00';row[2]='0:00:10.00'
 row[9]=re.sub(r'\\t\([^)]*\)','',row[9]);row[9]=re.sub(r'\\pos\(([-\d.]+),([-\d.]+)\)',lambda m:'\\pos('+str(float(m[1])+dx)+','+m[2]+')',row[9])
 if r.track:r.a.ass_free_track(r.track);r.track=None
 r.load((prefix+','.join(row)+'\n').encode());h,_=r.render(5000);bitmap=np.zeros((1080,1920),dtype=np.uint8)
 while h:
  z=h.contents
  if z.w>0 and z.h>0 and (z.color&255)<255:
   a=np.ctypeslib.as_array(z.bitmap,shape=(z.h*z.stride,)).reshape(z.h,z.stride)[:,:z.w]
   x0=max(0,z.x);x1=min(1920,z.x+z.w);y0=max(0,z.y);y1=min(1080,z.y+z.h)
   if x0<x1 and y0<y1:
    local=a[y0-z.y:y1-z.y,x0-z.x:x1-z.x];alpha=np.rint(local.astype(float)*(1-(z.color&255)/255)).astype(np.uint8)
    bitmap[y0:y1,x0:x1]=np.maximum(bitmap[y0:y1,x0:x1],alpha)
  h=z.next
 bounds={}
 for threshold in [1,16,64,128]:
  ys,xs=np.where(bitmap>=threshold);assert len(xs);bounds[str(threshold)]=[int(xs.min()),int(ys.min()),int(xs.max())+1,int(ys.max())+1]
 return bounds
if __name__=='__main__':
 raw=SOURCE.read_bytes();prefix=raw.decode('utf-8-sig').split('[Events]')[0]+'[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'
 rows=main_rows(raw);r=Renderer((1920,1080),(1920,1080),['/media/cuongba956/Download/One room'],cache_mb=64);result=[]
 for i in range(21):
  vi=measure(r,rows['VI'][i][1]);jp=measure(r,rows['JP'][i][1]);dx=vi['128'][2]-jp['128'][2];after=measure(r,rows['JP'][i][1],dx)
  assert after['128'][2]==vi['128'][2]
  result.append({'pair':i+1,'VI_main_index':rows['VI'][i][0],'JP_main_index':rows['JP'][i][0],'VI_bounds':vi,'JP_bounds_before':jp,'JP_shift_x':dx,'JP_bounds_after':after,'VI_text':re.sub(r'\{[^}]*\}','',rows['VI'][i][1][9]),'JP_text':re.sub(r'\{[^}]*\}','',rows['JP'][i][1][9])})
 r.close();report={'source_sha256':hashlib.sha256(raw).hexdigest(),'size':[1920,1080],'edge_definition':'right edge of rendered glyph coverage >= 128/255, blur 0.6 retained; VI is the per-pair reference','pairs':result};(ROOT/'measurements.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print([(r['pair'],r['VI_bounds']['128'][2],r['JP_bounds_before']['128'][2],r['JP_shift_x']) for r in result])
