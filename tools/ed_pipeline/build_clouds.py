#!/usr/bin/env python3
"""Cloud revision: eight broad cloudlets already distributed at their own positions.
No previous cloud silhouette or partition geometry is used.
Only the approved text and continuous timing are inherited.
"""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from cloud_clip import union_clip

ROOT=Path(__file__).resolve().parent

def smooth(u):
    u=max(0.,min(1.,u))
    return u*u*(3-2*u)

def ms(t):
    h,m,s=t.split(':')
    return round((int(h)*3600+int(m)*60+float(s))*1000)

def ass(t):
    cs=round(t/10)
    return f'{cs//360000}:{cs//6000%60:02}:{cs//100%60:02}.{cs%100:02}'

def ellipse(cx,cy,rx,ry):
    if min(rx,ry)<.3:return ''
    k=.55228475
    v=[(cx-rx,cy),(cx-rx,cy-k*ry),(cx-k*rx,cy-ry),(cx,cy-ry),
       (cx+k*rx,cy-ry),(cx+rx,cy-k*ry),(cx+rx,cy),
       (cx+rx,cy+k*ry),(cx+k*rx,cy+ry),(cx,cy+ry),
       (cx-k*rx,cy+ry),(cx-rx,cy+k*ry),(cx-rx,cy)]
    f=lambda p:f'{p[0]:.1f} {p[1]:.1f}'
    return 'm '+f(v[0])+' '+' '.join('b '+' '.join(f(p) for p in v[i:i+3]) for i in range(1,13,3))

def cloud_model(pair,seed,margin_trim=4):
    """Eight territories: five low billows and three upper billows.
    Two broad ellipses per territory replace the previous fine scallops.
    Margin comes from line bounds, not random per-pair decoration.
    """
    jx,jy,jr,jb=pair['jp_box'];vx,vy,vr,vb=pair['vi_box']
    clusters=[]
    # Lower bank: broad, evenly spaced arcs with a consistent lower clearance.
    lower_left=min(vx,jx)
    a=lower_left+36;b=vr-40
    step=(b-a)/4
    for i in range(5):
        x=a+step*i
        rx=82 if i in (0,4) else max(90,step*1.16)
        ry=70
        clusters.append({'x':x,'y':1010,'bank':'lower','puffs':[
            (0,0,rx,ry,'body'),
            (-rx*.12,-23,rx*.62,43,'crown')]})
    # Upper bank: three large rounded heads rather than many little teeth.
    a=jx+35;b=jr-40
    step=(b-a)/2
    for i in range(3):
        x=a+step*i
        rx=82 if i in (0,2) else max(94,step*1.16)
        ry=67 if i!=1 else 70
        y=956
        clusters.append({'x':x,'y':y,'bank':'upper','puffs':[
            (0,0,rx,ry,'body'),
            ((-.12 if i!=1 else .08)*rx,-29 if i!=1 else -34,
             rx*.62,45 if i!=1 else 51,'crown')]})
    if margin_trim:
        for cluster in clusters:
            cluster['puffs']=[(dx,dy,rx-margin_trim,ry-margin_trim,role)
                              for dx,dy,rx,ry,role in cluster['puffs']]
    return clusters

def shape(model,layer,phase='main',u=1,mask_inset=0):
    """Shared rule: eight small clouds already occupy their own territories.
    In: grow all eight locally and join. Out: reverse that growth, then evaporate.
    No common birth point, arbitrary per-cloud delays, or replacement silhouette.
    """
    allp=[]
    left=min(c['x'] for c in model);right=max(c['x'] for c in model)
    center=(left+right)/2
    span=max(1,(right-left)/2)
    for i,c in enumerate(model):
        x,y=c['x'],c['y'];direction=(x-center)/span
        if phase=='in':
            q=smooth(u)
            shrink=1
            px=x+direction*12*(1-q)
            py=y+14*(1-q)
        elif phase=='out':
            q=1-smooth(u/.72)
            shrink=1-smooth((u-.72)/.28)
            drift=smooth(u)
            px=x+direction*46*drift
            py=y-(42 if c['bank']=='lower' else 62)*drift
        else:
            q=1;shrink=1;px=x;py=y
        base_rx=c['puffs'][0][2]
        for k,(dx,dy,rx,ry,role) in enumerate(c['puffs']):
            # Each seed has a readable cloud proportion, including on long lines.
            seed_rx=27 if k==0 else 18
            seed_ry=19 if k==0 else 14
            seed_dx=0 if k==0 else (-7 if dx<0 else 7)
            seed_dy=0 if k==0 else -10
            ex=px+(seed_dx+(dx-seed_dx)*q)*shrink
            ey=py+(seed_dy+(dy-seed_dy)*q)*shrink
            erx=(seed_rx+(rx-seed_rx)*q)*shrink
            ery=(seed_ry+(ry-seed_ry)*q)*shrink
            grow=6*shrink if layer==0 else 0
            allp.append(ellipse(ex,ey+(4*shrink if layer==0 else 0),max(0,erx+grow-mask_inset),max(0,ery+grow-mask_inset)))
    return ' '.join(p for p in allp if p)

def event(start,end,layer,path,alpha,blur,fade=None,name=''):
    color='E2BA95' if layer==0 else 'FFFFFF'
    extra=f'\\fad({fade[0]},{fade[1]})' if fade else ''
    text=f'{{\\an7\\pos(0,0)\\bord0\\shad0\\c&H{color}&\\3c&H{color}&\\1a&H{alpha:02X}&\\blur{blur:.2f}{extra}\\p1}}{path}'
    return (start,layer,f'Dialogue: {layer},{ass(start)},{ass(end)},ED - Cloud,{name},0,0,0,,{text}')

def transition_plan(cfg):
    result=[]
    for group in cfg['groups']:
        for a,z in zip(group,group[1:]):
            begin=ms(cfg['main_timing'][z-1]['start'])
            end=ms(cfg['main_timing'][a-1]['end'])
            assert end-begin==500
            result.append({'a':a,'b':z,'start':begin,'end':end})
    return result

def hold_windows(cfg):
    windows={p['pair']:[ms(t['start']),ms(t['end'])] for p,t in zip(cfg['pairs'],cfg['main_timing'])}
    for transition in transition_plan(cfg):
        windows[transition['a']][1]=transition['start']
        windows[transition['b']][0]=transition['end']
    return windows

def morph_model(a,z,u):
    q=smooth(u)
    lerp=lambda x,y:x+(y-x)*q
    return [{'x':lerp(ca['x'],cz['x']),'y':lerp(ca['y'],cz['y']),'bank':ca['bank'],
             'puffs':[(lerp(pa[0],pz[0]),lerp(pa[1],pz[1]),lerp(pa[2],pz[2]),lerp(pa[3],pz[3]),pa[4])
                      for pa,pz in zip(ca['puffs'],cz['puffs'])]}
            for ca,cz in zip(a,z)]

def generate(cfg):
    design=cfg['design'];seed=design['seed'];step=design['step_ms']
    models={p['pair']:cloud_model(p,seed,design.get('margin_trim_px',4)) for p in cfg['pairs']}
    events=[]
    windows=hold_windows(cfg)
    for pair in cfg['pairs']:
        idx=pair['pair'];begin,end=windows[idx]
        for layer in [0,1]:
            events.append(event(begin,end,layer,shape(models[idx],layer),0x35 if layer==0 else 0x15,18 if layer==0 else 10,name=f'main-P{idx:02}'))
    for transition in transition_plan(cfg):
        begin,end=transition['start'],transition['end'];duration=end-begin
        for i in range(math.ceil(duration/step)):
            t=i*step;u=t/duration
            model=morph_model(models[transition['a']],models[transition['b']],u)
            for layer in [0,1]:
                events.append(event(begin+t,min(end,begin+t+step),layer,shape(model,layer),0x35 if layer==0 else 0x15,18 if layer==0 else 10,name=f'morph-P{transition["a"]:02}-P{transition["b"]:02}'))
    for group in cfg['groups']:
        for phase,idx,duration in [('in',group[0],design['intro_ms']),('out',group[-1],design['outro_ms'])]:
            pair=cfg['pairs'][idx-1]
            start=ms(pair['start'])-duration if phase=='in' else ms(pair['end'])
            steps=math.ceil(duration/step)
            for i in range(steps):
                u=min(1,i*step/duration)
                for layer in [0,1]:
                    alpha=0x35 if layer==0 else 0x15;blur=18 if layer==0 else 10
                    # Same absolute 900ms window and linear opacity as text \fad.
                    opacity_time=min(1,i*step/duration)
                    if phase=='out':
                        alpha=round(alpha+(255-alpha)*opacity_time)
                        blur+=(8 if layer==0 else 12)*smooth(u)
                    else:
                        alpha=round(255-(255-alpha)*opacity_time)
                    path=shape(models[idx],layer,phase,u)
                    if path:events.append(event(start+i*step,start+min(duration,(i+1)*step),layer,path,alpha,blur,name=f'{phase}-P{idx:02}'))
    return sorted(events,key=lambda e:(e[0],e[1])),models

def paint_text(parts,opacity,clip,dy=0,blur=0):
    txt=re.sub(r'\\fad\(\d+,\d+\)','',parts[9])
    if dy:
        txt=re.sub(r'\\pos\(([-\d.]+),([-\d.]+)\)',lambda m:f'\\pos({m.group(1)},{float(m.group(2))+dy:.3f})',txt)
    if 'Noto Serif JP' in txt:
        txt=re.sub(r'\\4a&H([0-9A-Fa-f]+)&',lambda m:f'\\4a&H{round(255-(255-int(m.group(1),16))*opacity):02X}&',txt)
        extra=''
    else:
        extra=f'\\alpha&H{round(255*(1-opacity)):02X}&'
    extra+=f'\\blur{blur:.3f}'
    marker=re.match(r'^\{=\d+\}',txt);metadata=marker.group(0) if marker else ''
    return metadata+'{'+extra+'\\clip('+clip+')}'+txt[len(metadata):]

def text_events(cfg,models):
    first={g[0] for g in cfg['groups']};last={g[-1] for g in cfg['groups']}
    result=[];step=cfg['design']['step_ms'];clip_cache={};windows=hold_windows(cfg)
    transitions=transition_plan(cfg)
    for index,source in enumerate(cfg['approved_text']):
        idx=index%21+1;pair=cfg['pairs'][idx-1];parts=source.rstrip('\r\n').split(',',9)
        lang='jp' if index>=21 else 'vi'
        main=parts.copy();main[1]=ass(windows[idx][0]);main[2]=ass(windows[idx][1])
        main[9]=re.sub(r'\\fad\(\d+,\d+\)',lambda m:'\\fad(0,0)',main[9],count=1)
        exported=[','.join(main)]
        # Outer cloud-mask effect, with a gentle additional text fade.
        for phase,allowed in [('in',idx in first),('out',idx in last)]:
            if not allowed:continue
            duration=cfg['design']['intro_ms' if phase=='in' else 'outro_ms']
            begin=ms(pair['start'])-duration if phase=='in' else ms(pair['end'])
            for i in range(math.ceil(duration/step)):
                u=i*step/duration;key=('edge',idx,phase,i)
                if key not in clip_cache:clip_cache[key]=union_clip(shape(models[idx],1,phase,u,mask_inset=4))
                clip=clip_cache[key]
                if not clip:continue
                cloud_a=round(0x15+(255-0x15)*u) if phase=='out' else round(255-(255-0x15)*u)
                inherited=(255-cloud_a)/(255-0x15)
                gentle=(smooth(u) if phase=='in' else 1-smooth(u))**cfg['design']['text_fade_power']
                row=parts.copy();row[1]=ass(begin+i*step);row[2]=ass(begin+min(duration,(i+1)*step));row[4]=f'cloud-{phase}-P{idx:02}'
                row[9]=paint_text(parts,inherited*gentle,clip)
                exported.append(','.join(row))
        # Fixed text crossfades with exactly the same smoothstep as the cloud morph.
        for transition in transitions:
            if idx not in (transition['a'],transition['b']):continue
            outgoing=idx==transition['a'];begin,end=transition['start'],transition['end'];duration=end-begin
            for i in range(math.ceil(duration/step)):
                t=i*step;u=t/duration;q=smooth(u)
                key=('flow',transition['a'],transition['b'],i)
                if key not in clip_cache:
                    model=morph_model(models[transition['a']],models[transition['b']],u)
                    clip_cache[key]=union_clip(shape(model,1,mask_inset=4))
                clip=clip_cache[key]
                if not clip:continue
                distance=cfg['design']['continuous_slide_px']
                dy=0
                opacity=1-q if outgoing else q
                blur=0
                row=parts.copy();row[1]=ass(begin+t);row[2]=ass(min(end,begin+t+step))
                role='out' if outgoing else 'in';row[4]=f'flow-P{transition["a"]:02}-P{transition["b"]:02}-{role}'
                row[9]=paint_text(parts,opacity,clip,dy,blur)
                exported.append(','.join(row))
        result.append(exported)
    return result

def protected(blob):
    return [line for line in blob.splitlines(keepends=True) if not(line.startswith(b'Dialogue:') and line.split(b',',9)[3] in (b'ED - Cloud',b'ED - Viator'))]

def build(master_path,output,cfg):
    master=master_path.read_bytes()
    assert hashlib.sha256(master).hexdigest()==cfg['master_sha256'],'Master changed; reconcile before rebuilding.'
    events,models=generate(cfg)
    nl=b'\r\n' if b'\r\n' in master else b'\n'
    cloud=[e[2].encode()+nl for e in events]
    expanded_text=text_events(cfg,models)
    text=iter(expanded_text)
    result=[];inserted=False;count=0
    for line in master.splitlines(keepends=True):
        parts=line.split(b',',9) if line.startswith(b'Dialogue:') else []
        style=parts[3] if parts else None
        if style==b'ED - Cloud':
            if not inserted:result.extend(cloud);inserted=True
        elif style==b'ED - Viator':
            result.extend(row.encode()+nl for row in next(text));count+=1
        else:result.append(line)
    assert inserted and count==42
    candidate=b''.join(result)
    assert protected(master)==protected(candidate)
    output.write_bytes(candidate)
    report={'master_sha256':hashlib.sha256(master).hexdigest(),'candidate_sha256':hashlib.sha256(candidate).hexdigest(),'protected_lines':len(protected(master)),'approved_text_rows':count,'cloud_events':len(events),'text_events':sum(map(len,expanded_text)),'geometry':'eight distributed cloudlets, two broad puffs each; simultaneous local growth; reverse breakup and evaporation','source_puffs':{str(k):sum(len(c['puffs']) for c in v) for k,v in models.items()}}
    output.with_suffix('.validation.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--master',type=Path,default=Path('/media/cuongba956/Download/One room/Maquia.vi.ass'))
    parser.add_argument('--output',type=Path,default=ROOT/'Maquia.vi.rebuilt.ass')
    parser.add_argument('--scene',type=Path,default=ROOT/'scene.json')
    args=parser.parse_args()
    build(args.master,args.output,json.loads(args.scene.read_text()))
