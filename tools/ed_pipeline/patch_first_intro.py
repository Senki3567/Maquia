#!/usr/bin/env python3
"""P01 only: replace cloud/text growth intro with footage-matched color reveal."""
from pathlib import Path
import re,json,hashlib,argparse
ROOT=Path(__file__).resolve().parent
EXPECTED='ddfcd9c1c832bb845dbeeb71014e41eb306b90f7ffda2d8b46b15e5177b5eaa4'
def ms(t):
 h,m,s=t.split(':');return round((int(h)*3600+int(m)*60+float(s))*1000)
def selected(line):
 if not line.startswith(b'Dialogue:'):return False
 p=line.rstrip(b'\r\n').decode().split(',',9)
 return (p[3]=='ED - Cloud' and p[4] in ['in-P01','main-P01']) or (p[3]=='ED - Viator' and (p[4]=='cloud-in-P01' or ms(p[1])==6587310))
def run(source,output):
 raw=source.read_bytes();assert hashlib.sha256(raw).hexdigest()==EXPECTED,'Baseline changed; reconcile before patch'
 cfg=json.loads((ROOT/'scene-fade.json').read_text());start=6586440;a=cfg['fade_start_ms']-start;b=cfg['fade_end_ms']-start
 result=[];removed=0;changed=0;colors=[]
 for line in raw.splitlines(keepends=True):
  if not selected(line):result.append(line);continue
  p=line.rstrip(b'\r\n').decode().split(',',9);nl=b'\r\n' if line.endswith(b'\r\n') else b'\n'
  if p[4] in ['in-P01','cloud-in-P01']:removed+=1;continue
  original=p[9];p[1]='1:49:46.44';p[4]='scene-color-P01'
  def color(m):
   tag=m[1];value=m[2];colors.append({'tag':tag,'target':value})
   return '\\'+tag+'&HF2F2F2&'+f'\\t({a},{b},\\{tag}&H{value}&)'
  p[9]=re.sub(r'\\([1-4]?c)&(?:H)?([0-9A-Fa-f]{6})&?',color,p[9])
  assert p[9]!=original and '\\clip' not in p[9] and '\\fad' not in p[9]
  result.append(','.join(p).encode()+nl);changed+=1
 assert changed==4 and removed>0
 new=b''.join(result)
 # Every byte outside the explicitly selected first-intro/main events is identical.
 assert [l for l in raw.splitlines(keepends=True) if not selected(l)]==[l for l in new.splitlines(keepends=True) if not(l.startswith(b'Dialogue:') and l.split(b',',9)[4]==b'scene-color-P01')]
 output.write_bytes(new)
 report={'source_sha256':hashlib.sha256(raw).hexdigest(),'candidate_sha256':hashlib.sha256(new).hexdigest(),'removed_first_intro_events':removed,'replaced_main_events':changed,'fixed_shape_and_position':True,'intro_alpha_animation':False,'color_initial':'F2F2F2 (242 RGB; measured footage white)','color_transition_absolute_ms':[cfg['fade_start_ms'],cfg['fade_end_ms']],'other_events_and_sections_byte_identical':True,'bytes':len(new)}
 output.with_suffix('.validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);args=p.parse_args();run(args.source,args.output)
