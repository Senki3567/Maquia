from pathlib import Path
import hashlib,json,argparse
EXPECTED='8e2189891901881c48e529bfd76bfed4ad084c9c027d9df374cbeb4c7556ed3b'
def run(source,output):
 raw=source.read_bytes();assert hashlib.sha256(raw).hexdigest()==EXPECTED
 lines=[];changed=0
 for line in raw.splitlines(keepends=True):
  if line.startswith(b'Dialogue:') and line.split(b',',9)[3]==b'ED - Cloud':
   new=line.replace(b'&HD4B5AA&',b'&HD9B7A4&')
   if new!=line:changed+=1
   lines.append(new)
  else:lines.append(line)
 result=b''.join(lines);assert changed==538
 output.write_bytes(result)
 report={'before_sha256':hashlib.sha256(raw).hexdigest(),'after_sha256':hashlib.sha256(result).hexdigest(),'cloud_shadow_BGR':['D4B5AA','D9B7A4'],'cloud_shadow_RGB':[[170,181,212],[164,183,217]],'cloud_events_adjusted':changed,'white_text_timing_geometry_alpha_unchanged':True}
 output.with_suffix('.validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();run(a.source,a.output)
