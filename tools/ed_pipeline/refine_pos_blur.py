#!/usr/bin/env python3
"""Patch current approved ED geometry and phase blur without rebuilding clouds.
Only Dialogue Text in ED - Cloud / ED - Viator is changed; source is never written.
"""
from pathlib import Path
import argparse, re, hashlib, json, collections

def ms(t):
    h,m,s=t.split(':'); return round((int(h)*3600+int(m)*60+float(s))*1000)
def fmt(v): return f'{v:.6f}'.rstrip('0').rstrip('.')
def shift_vector(path,dy):
    # Optional ASS vector clip scale: coordinates are in 2**(scale-1) units.
    scale=1
    m=re.match(r'\s*(\d+),',path)
    if m: scale=2**(int(m[1])-1); prefix=path[:m.end()]; path=path[m.end():]
    else: prefix=''
    assert path.lstrip().startswith('m '),path[:50]
    i=0
    def number(m):
        nonlocal i
        value=fmt(float(m[0])+dy*scale) if i%2 else m[0]; i+=1; return value
    out=re.sub(r'-?\d+(?:\.\d+)?',number,path)
    assert i%2==0
    return prefix+out

def run(source,output,dy):
    raw=source.read_bytes(); lines=raw.splitlines(keepends=True); spans={}
    for line in lines:
        if not line.startswith(b'Dialogue:'): continue
        p=line.rstrip(b'\r\n').decode().split(',',9)
        if p[3]=='ED - Viator' and (p[4].startswith(('cloud-in-','cloud-out-','flow-'))):
            a,z=ms(p[1]),ms(p[2]); old=spans.get(p[4],(a,z)); spans[p[4]]=(min(old[0],a),max(old[1],z))
    counts=collections.Counter(); result=[]
    for line in lines:
        if not line.startswith(b'Dialogue:'): result.append(line); continue
        p=line.rstrip(b'\r\n').decode().split(',',9)
        if p[3] not in ('ED - Cloud','ED - Viator'): result.append(line); continue
        original=p[9]; text=original
        if p[3]=='ED - Cloud':
            header,path=text.split('}',1);text=header+'}'+shift_vector(path,dy)
        else:
            text,n=re.subn(r'\\pos\(([-\d.]+),([-\d.]+)\)',lambda m:'\\pos('+m[1]+','+fmt(float(m[2])+dy)+')',text);assert n==1
            text,n=re.subn(r'\\(i?clip)\(([^)]*)\)',lambda m:'\\'+m[1]+'('+shift_vector(m[2],dy)+')',text);counts['masks_shifted']+=n
            name=p[4]; a,z=ms(p[1]),ms(p[2]); phase=None
            if name in spans:
                start,end=spans[name]; phase='out' if ('-out' in name or name.startswith('cloud-out-')) else 'in'
                peak=10.0 if name.startswith('cloud-') else 6.0
            elif name=='scene-color-P01': start=a;end=a+870;phase='in';peak=10.0
            if phase:
                def blur(t):
                    u=min(1,max(0,(t-start)/(end-start))); u=u*u*(3-2*u)
                    return .6+(peak-.6)*((u if phase=='out' else 1-u)**0.65)
                # Rebase to each existing event's clock, including 30ms mask rows.
                # 30ms knots keep smoothstep consistent across split/merged rows.
                knots=sorted({a,z,*range(start,end+1,30),end})
                knots=[t for t in knots if a<=t<=z]
                tag='\\blur'+fmt(blur(a))
                for t0,t1 in zip(knots,knots[1:]):
                    if abs(blur(t1)-blur(t0))>1e-8:tag+=f'\\t({t0-a},{t1-a},\\blur{fmt(blur(t1))})'
                text,n=re.subn(r'\\blur[\d.]+',lambda m:tag,text,count=1);assert n==1;counts['text_events_blur_'+phase]+=1
                # With a border present libass blurs its edge, leaving the fill sharp.
                # Phase rows need borderless glyphs so blur softens the actual letters.
                head,body=text.rsplit('}',1); text=head+'}{\\bord0\\xbord0\\ybord0}'+body
        p[9]=text; nl=b'\r\n' if line.endswith(b'\r\n') else b'\n'
        newline=','.join(p).encode()+nl
        assert newline.split(b',',9)[:9]==line.split(b',',9)[:9]
        result.append(newline);counts[p[3]]+=1
    new=b''.join(result)
    assert len(new.splitlines())==len(raw.splitlines())
    def protected(blob):return [l for l in blob.splitlines(keepends=True) if not(l.startswith(b'Dialogue:') and l.split(b',',9)[3] in (b'ED - Cloud',b'ED - Viator'))]
    assert protected(raw)==protected(new)
    output.write_bytes(new)
    report={'source_sha256':hashlib.sha256(raw).hexdigest(),'candidate_sha256':hashlib.sha256(new).hexdigest(),'shift_y_px':dy,'counts':dict(counts),'timing_and_non_Text_fields_unchanged':True,'non_ED_bytes_unchanged':True,'stable_text_blur':0.6,'cloud_phase_peak_text_blur':10.0,'flow_peak_text_blur':6.0,'phase_spans_ms':spans}
    output.with_suffix('.validation.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='phase_spans_ms'},indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--dy',type=float,default=-10);a=p.parse_args();run(a.source,a.output,a.dy)
