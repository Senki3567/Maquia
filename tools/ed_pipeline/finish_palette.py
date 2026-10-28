#!/usr/bin/env python3
"""Minor final ED palette and text softness adjustment; all timing/geometry intact."""
from pathlib import Path
import argparse,re,hashlib,json,collections
EXPECTED='7390d40ec2ea52b6892a847d258a72ca49cf7f7eea6fbf113a4e2673fad82a4e'
PALETTE={'E2BA95':'D4B5AA','FFFFFF':'F8F2F2'} # ASS BGR; pale periwinkle shadow and cool off-white core
BLUR='0.5'
def run(source,output):
 raw=source.read_bytes();assert hashlib.sha256(raw).hexdigest()==EXPECTED,'Master changed; reconcile'
 records=[];counts=collections.Counter()
 for line in raw.splitlines(keepends=True):
  if not line.startswith(b'Dialogue:'):records.append(line);continue
  p=line.rstrip(b'\r\n').decode().split(',',9);nl=b'\r\n' if line.endswith(b'\r\n') else b'\n';text=p[9]
  if p[3]=='ED - Cloud':
   def replace(m):
    value=m[2];new=PALETTE.get(value,value)
    if new!=value:counts['cloud_color_tags_adjusted']+=1
    return m[1]+new+'&'
   p[9]=re.sub(r'(\\(?:[1-4]?c)&H)([0-9A-F]{6})&',replace,text)
   if p[9]!=text:counts['cloud_events_adjusted']+=1
  elif p[3]=='ED - Viator':
   assert '\\blur' not in text
   marker=re.match(r'^\{=\d+\}',text);metadata=marker[0] if marker else ''
   p[9]=metadata+'{\\blur'+BLUR+'}'+text[len(metadata):];counts['text_events_softened']+=1
  else:records.append(line);continue
  newline=','.join(p).encode()+nl
  oldparts=line.rstrip(b'\r\n').split(b',',9);assert newline.rstrip(b'\r\n').split(b',',9)[:9]==oldparts[:9]
  records.append(newline)
 result=b''.join(records)
 def protected(blob):return [l for l in blob.splitlines(keepends=True) if not(l.startswith(b'Dialogue:') and l.split(b',',9)[3] in (b'ED - Cloud',b'ED - Viator'))]
 assert protected(raw)==protected(result)
 output.write_bytes(result)
 report={'source_sha256':hashlib.sha256(raw).hexdigest(),'candidate_sha256':hashlib.sha256(result).hexdigest(),'palette_ASS_BGR':PALETTE,'text_blur_px':float(BLUR),'counts':dict(counts),'all_non_Text_fields_unchanged':True,'non_ED_bytes_unchanged':True,'first_intro_white_F2F2F2_preserved':True}
 output.with_suffix('.validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();run(a.source,a.output)
