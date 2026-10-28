#!/usr/bin/env python3
"""Editable ED lyric comments; source IDs survive glyph/FBF optimization.
Comments are authoritative for future lyric edits. Inserting never changes
existing rows; extraction reads the latest comments from the supplied ASS.
"""
from pathlib import Path
import argparse,re,json,hashlib,collections
MARKER='ED_SOURCE:'
def events(blob):
 for i,line in enumerate(blob.splitlines(keepends=True)):
  if line.startswith((b'Dialogue:',b'Comment:')):
   yield i,line.rstrip(b'\r\n').decode().split(',',9)

def extract(source,output):
 raw=source.read_bytes();rows=[]
 for i,p in events(raw):
  if p[0].startswith('Comment:')and p[8].startswith(MARKER):
   m=re.fullmatch(r'ED_SOURCE:P(\d{2}):(VI|JP)',p[8]);assert m,p[8]
   rows.append({'id':p[8],'pair':int(m[1]),'language':m[2],'start':p[1],'end':p[2],'text':p[9],'physical_line':i+1})
 assert len(rows)==42 and len({r['id']for r in rows})==42,'Expected 42 unique ED source comments'
 assert collections.Counter(r['language']for r in rows)=={'VI':21,'JP':21}
 for lang in ['VI','JP']:assert sorted(r['pair']for r in rows if r['language']==lang)==list(range(1,22))
 data={'ass_sha256':hashlib.sha256(raw).hexdigest(),'authoritative_source':'Comment events with Effect ED_SOURCE:Pxx:VI/JP','lyrics':rows};output.write_text(json.dumps(data,ensure_ascii=False,indent=2));print('Extracted 42 current source comments')

def insert(source,font_source,output):
 raw=source.read_bytes();original=font_source.read_bytes();assert not any(p[8].startswith(MARKER)for i,p in events(raw)),'Editable sources already exist; preserve user edits and use extract'
 source_rows=[];groups=[];pair_counts=collections.Counter()
 for i,p in events(original):
  if not p[0].startswith('Dialogue:')or p[3]!='ED - Viator':continue
  lyric=re.sub(r'\{[^}]*\}','',p[9]);lang='JP'if '\\fnNoto Serif JP'in p[9]else'VI'
  if not groups or (groups[-1]['language'],groups[-1]['text'])!=(lang,lyric):
   pair_counts[lang]+=1;groups.append({'pair':pair_counts[lang],'language':lang,'text':lyric,'rows':[]})
  g=groups[-1];g['rows'].append(p);source_rows.append((len(groups)-1,p))
 assert len(groups)==42 and pair_counts=={'VI':21,'JP':21}
 def identity(p):return p[0],p[1],tuple(p[3:9])
 cursor=0;starts={};mapping=[];counts=collections.Counter()
 for i,p in events(raw):
  if not p[0].startswith('Dialogue:')or p[3]!='ED - Viator':continue
  while cursor<len(source_rows)and identity(source_rows[cursor][1])!=identity(p):cursor+=1
  assert cursor<len(source_rows),('Current ED row is not mapped to editable baseline',i+1,p[:9])
  group,_=source_rows[cursor];starts.setdefault(group,i);counts[group]+=1;mapping.append({'effect_line_before_insert':i+1,'source_id':f"{MARKER}P{groups[group]['pair']:02}:{groups[group]['language']}"});cursor+=1
 assert len(starts)==42
 inserts={};manifest=[]
 for gidx,g in enumerate(groups):
  mains=[p for p in g['rows']if p[4]in['','scene-color-P01']];assert len(mains)==1,(gidx,len(mains));main=mains[0];row=main.copy();row[0]='Comment: '+main[0].split(': ',1)[1];row[4]=f"Nguồn {'Việt'if g['language']=='VI'else'Nhật'} P{g['pair']:02}";row[8]=f"{MARKER}P{g['pair']:02}:{g['language']}";row[9]=g['text'];line_index=starts[gidx];oldline=raw.splitlines(keepends=True)[line_index];nl=b'\r\n'if oldline.endswith(b'\r\n')else b'\n';inserts[line_index]=','.join(row).encode()+nl
  manifest.append({'id':row[8],'pair':g['pair'],'language':g['language'],'text':g['text'],'start':row[1],'end':row[2],'original_main_template':','.join(main),'current_FX_events':counts[gidx]})
 lines=raw.splitlines(keepends=True);new=b''.join(inserts.get(i,b'')+line for i,line in enumerate(lines));assert [l for l in new.splitlines(keepends=True)if not(l.startswith(b'Comment:')and l.split(b',',9)[8].startswith(MARKER.encode()))]==lines
 output.write_bytes(new);output.with_suffix('.source-map.json').write_text(json.dumps({'editable_font_source':str(font_source.resolve()),'editable_font_source_sha256':hashlib.sha256(original).hexdigest(),'groups':manifest,'FX_source_ids':mapping},ensure_ascii=False,indent=2));report={'before_sha256':hashlib.sha256(raw).hexdigest(),'after_sha256':hashlib.sha256(new).hexdigest(),'comments_added':42,'VI_sources':21,'JP_sources':21,'source_groups_matched':42,'existing_Dialogue_and_Comment_rows_byte_identical':True,'all_other_lines_byte_identical':True,'added_bytes':len(new)-len(raw)};output.with_suffix('.validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();s=p.add_subparsers(dest='command',required=True);a=s.add_parser('insert');a.add_argument('source',type=Path);a.add_argument('font_source',type=Path);a.add_argument('output',type=Path);a=s.add_parser('extract');a.add_argument('source',type=Path);a.add_argument('output',type=Path);args=p.parse_args()
 if args.command=='insert':insert(args.source,args.font_source,args.output)
 else:extract(args.source,args.output)
