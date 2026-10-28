#!/usr/bin/env python3
"""Align actual JP ink right edges to the VI reference, one offset per lyric pair."""
from pathlib import Path
import argparse,json,re,hashlib,collections
ROOT=Path(__file__).resolve().parent

def pair_id(parts,index,main_indices):
 if index in main_indices:return main_indices[index]
 if parts[4].startswith('flow-'):
  m=re.fullmatch(r'flow-P(\d+)-P(\d+)-(in|out)',parts[4]);assert m
  return int(m[1] if m[3]=='out' else m[2])
 m=re.search(r'P(\d+)',parts[4]);assert m,parts[4];return int(m[1])

def run(source,output):
 raw=source.read_bytes();cfg=json.loads((ROOT/'measurements.json').read_text());assert hashlib.sha256(raw).hexdigest()==cfg['source_sha256'],'Master changed; reconcile'
 main={p['JP_main_index']:p['pair'] for p in cfg['pairs']};offsets={p['pair']:p['JP_shift_x'] for p in cfg['pairs']};counts=collections.Counter();result=[]
 for index,line in enumerate(raw.splitlines(keepends=True)):
  if not line.startswith(b'Dialogue:'):result.append(line);continue
  p=line.rstrip(b'\r\n').decode().split(',',9)
  if p[3]!='ED - Viator' or '\\fnNoto Serif JP' not in p[9]:result.append(line);continue
  pair=pair_id(p,index,main);dx=offsets[pair];original=p[9]
  def position(m):
   x=float(m[1])+dx;xstr=str(int(x)) if x.is_integer() else str(x)
   return '\\pos('+xstr+','+m[2]+')'
  p[9],n=re.subn(r'\\pos\(([-\d.]+),([-\d.]+)\)',position,p[9]);assert n==1
  if p[9]==original:result.append(line);continue
  # Only \pos x changes. All masks remain fixed in cloud/screen coordinates.
  assert re.sub(r'\\pos\([^)]*\)','',original)==re.sub(r'\\pos\([^)]*\)','',p[9])
  nl=b'\r\n' if line.endswith(b'\r\n') else b'\n';result.append(','.join(p).encode()+nl);counts[pair]+=1
 new=b''.join(result);output.write_bytes(new)
 def protected(b):return [l for l in b.splitlines(keepends=True) if not(l.startswith(b'Dialogue:') and l.split(b',',9)[3]==b'ED - Viator' and b'\\fnNoto Serif JP' in l)]
 assert protected(raw)==protected(new)
 report={'source_sha256':hashlib.sha256(raw).hexdigest(),'candidate_sha256':hashlib.sha256(new).hexdigest(),'JP_events_shifted':sum(counts.values()),'per_pair_x_offset':offsets,'per_pair_event_count':dict(counts),'only_JP_pos_x_changed':True,'VI_clouds_timing_masks_colors_blur_other_data_byte_identical':True,'current_user_blur_0_6_preserved':True}
 output.with_suffix('.validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();run(a.source,a.output)
