#!/usr/bin/env python3
"""Natural organic bottom-centred (\\an2) ED layout; rebuild both cloud banks and their masks.
Starts from the current master plus the audited editable pre-glyph layout.
Refined for natural cumulus shape asymmetry and snug bottom margin.
"""
from pathlib import Path
import re, json, hashlib, bisect, argparse, random
import numpy as np
import native_font_geometry as native
import glyph_geometry as geo
from cut_text_shapes import value, tokens
from cloud_clip import union_clip

def ms(t):
    h, m, s = t.split(':')
    return round((int(h)*3600 + int(m)*60 + float(s))*1000)

def stamp(t):
    c = round(t / 10)
    return f'{c//360000}:{c//6000%60:02}:{c//100%60:02}.{c%100:02}'

def fmt(v):
    return f'{v:.6f}'.rstrip('0').rstrip('.')

def contours(path):
    return re.findall(r'm\s+[^m]+', path)

def ellipse_info(path):
    n = list(map(float, re.findall(r'-?\d+(?:\.\d+)?', path)))
    xs = n[::2]; ys = n[1::2]
    return ((min(xs)+max(xs))/2, (min(ys)+max(ys))/2, (max(xs)-min(xs))/2, (max(ys)-min(ys))/2)

def make_cloud_profile(pair, vi_width, jp_width, cx=960):
    """Keep the good 8-cluster skeleton of the original an2 cloud.

    Each of five base clusters and three crown clusters consists of one main
    lobe plus a smaller, offset helper lobe.  The helper lobes fill joins; they
    must not read as a second regular row.  Every pair gets its own asymmetric
    spacing, sizes, slopes and tower side.
    """
    rng = random.Random(0xA2C10D + pair * 1009)
    lower_width = max(vi_width, jp_width)
    base_left_margin, base_right_margin = rng.uniform(40.0, 50.0), rng.uniform(40.0, 50.0)
    crown_left_margin, crown_right_margin = rng.uniform(40.0, 50.0), rng.uniform(40.0, 50.0)
    left = cx - lower_width / 2.0 - base_left_margin
    right = cx + lower_width / 2.0 + base_right_margin
    base_width = right - left

    # Five irregular base clusters cover the longer line.  End clusters define
    # the requested margins; the three inner centres deliberately avoid a
    # repeating cadence.
    base_u = [0.0, rng.uniform(0.17, 0.25), rng.uniform(0.43, 0.56),
              rng.uniform(0.70, 0.81), 1.0]
    base_ry = [rng.uniform(58.0, 70.0) for _ in range(5)]
    base_rx = [rng.uniform(0.18, 0.24) * base_width for _ in range(5)]
    base_rx[0] = min(base_rx[0], base_width * 0.20)
    base_rx[-1] = min(base_rx[-1], base_width * 0.20)
    x0, x1 = left + base_rx[0], right - base_rx[-1]
    base = []
    for i, u in enumerate(base_u):
        x = x0 + (x1 - x0) * u
        bottom = rng.uniform(1068.5, 1071.0)
        base.append([x, bottom - base_ry[i], base_rx[i], base_ry[i]])

    # Three crown clusters cover the shorter JP line.  Their baseline is not
    # a row: one becomes an off-centre tower and the other two fall by unequal
    # amounts to form the stepped shoulders.
    crown_left = cx - jp_width / 2.0 - crown_left_margin
    crown_right = cx + jp_width / 2.0 + crown_right_margin
    crown_width = crown_right - crown_left
    crown_rx = [rng.uniform(0.27, 0.36) * crown_width for _ in range(3)]
    crown_rx[0] = min(crown_rx[0], crown_width * 0.31)
    crown_rx[-1] = min(crown_rx[-1], crown_width * 0.31)
    c0, c1 = crown_left + crown_rx[0], crown_right - crown_rx[-1]
    middle_u = rng.uniform(0.39, 0.61)
    crown_x = [c0, c0 + (c1 - c0) * middle_u, c1]
    high = rng.randrange(3)
    high_top = rng.uniform(850.0, 864.0)
    top_offsets = [rng.uniform(24.0, 45.0), rng.uniform(13.0, 34.0), rng.uniform(24.0, 45.0)]
    top_offsets[high] = 0.0
    # Keep the other shoulder unequal even when random values are close.
    other = [i for i in range(3) if i != high]
    if abs(top_offsets[other[0]] - top_offsets[other[1]]) < 8.0:
        top_offsets[other[1]] += 10.0
    crown = []
    for i in range(3):
        ry = rng.uniform(67.0, 86.0)
        crown.append([crown_x[i], high_top + top_offsets[i] + ry, crown_rx[i], ry])

    # Interleave each main lobe with a smaller offset helper, preserving the
    # original 16-contour contract without creating 16 equally visible puffs.
    puffs = []
    for i, main in enumerate(base + crown):
        x, y, rx, ry = main
        helper_scale = rng.uniform(0.50, 0.67)
        side = -1 if rng.random() < 0.5 else 1
        helper = [x + side * rx * rng.uniform(0.08, 0.22),
                  y - ry * rng.uniform(0.25, 0.48),
                  rx * helper_scale,
                  ry * rng.uniform(0.50, 0.66)]
        puffs.extend((main, helper))
    return puffs

def blend_profiles(a, b, t):
    return [[x + (y - x) * t for x, y in zip(pa, pb)] for pa, pb in zip(a, b)]

def scale_profile(profile, scale, ox, oy):
    return [[ox + (x - ox) * scale, oy + (y - oy) * scale, rx * scale, ry * scale]
            for x, y, rx, ry in profile]

def natural_an2_cloud(path, profile):
    parts = contours(path)
    assert len(parts) == 16
    centers = [ellipse_info(c) for c in parts]
    out = []
    for i, p in enumerate(parts):
        ecx, ecy, erx, ery = centers[i]
        tcx, tcy, trx, try_ = profile[i]
        
        idx_pt = 0
        def f(m):
            nonlocal idx_pt
            v = float(m.group(0))
            if idx_pt % 2 == 0:
                new_v = (v - ecx) * trx / erx + tcx
            else:
                new_v = (v - ecy) * try_ / ery + tcy
            idx_pt += 1
            return fmt(new_v)
            
        out.append(re.sub(r'-?\d+(?:\.\d+)?', f, p))
        
    return ' '.join(out)

def inset_mask(path):
    out = []
    for part in contours(path):
        cx, cy, rx, ry = ellipse_info(part)
        nx = rx - 4.08
        ny = ry - 4.0
        if min(nx, ny) < 0.3:
            continue
        idx_pt = 0
        def f(m):
            nonlocal idx_pt
            v = float(m.group(0))
            v = cx + (v - cx) * nx / rx if idx_pt % 2 == 0 else cy + (v - cy) * ny / ry
            idx_pt += 1
            return fmt(v)
        out.append(re.sub(r'-?\d+(?:\.\d+)?', f, part))
    return union_clip(' '.join(out)) if out else 'm 0 0 l 0 0 0 0'

def rebase(text, delta):
    if delta == 0:
        return text
    completed = {}
    def trans(m):
        a, b = int(m[1]), int(m[2])
        body = m[3]
        assert not (a < delta < b), ('A split would restart an active transform', delta, m[0])
        if b <= delta:
            for k, v in tokens(body):
                completed[k] = v
            return ''
        return f'\\t({a-delta},{b-delta},{body})'
    text = re.sub(r'\\t\((\d+),(\d+),(\\[^)]*)\)', trans, text)
    for k, v in completed.items():
        pattern = r'\\' + re.escape(k) + r'(?![a-z])[^\\}()]*'
        text, n = re.subn(pattern, lambda m: '\\' + k + v, text, count=1)
        assert n == 1, (k, text[:150])
    return text

def build(master, source, output, work, cx=960, dy=-6):
    raw = master.read_bytes()
    work.mkdir(parents=True, exist_ok=True)
    source_raw = source.read_bytes()
    src = source_raw.splitlines(keepends=True)
    
    master_native = [l.split(b',', 9) for l in raw.splitlines() if l.startswith(b'Dialogue:') and l.split(b',', 9)[3] == b'ED - Viator' and b'MaquiaED' not in l]
    source_native = [l.split(b',', 9) for l in source_raw.splitlines() if l.startswith(b'Dialogue:') and l.split(b',', 9)[3] == b'ED - Viator' and b'\\clip(' not in l]
    assert master_native == source_native, 'Current native ED rows differ from audited source; reconcile edits first'
    
    comments = {l.split(b',', 9)[8].decode(): l.split(b',', 9)[9].decode() for l in raw.splitlines() if l.startswith(b'Comment:') and l.split(b',', 9)[8].startswith(b'ED_SOURCE:')}
    assert len(comments) == 42
    
    rows = [l.decode().rstrip('\r\n').split(',', 9) for l in src if l.startswith(b'Dialogue:') and l.split(b',', 9)[3] in [b'ED - Cloud', b'ED - Viator']]
    white = []
    cloud_rows = []
    layouts = {}
    groups = []
    counts = {'VI': 0, 'JP': 0}
    group = None
    
    for p in rows:
        if p[3] != 'ED - Viator':
            continue
        lyric = re.sub(r'\{[^}]*\}', '', p[9])
        lang = 'JP' if '\\fnNoto Serif JP' in p[9] else 'VI'
        if group is None or (group['lang'], group['lyric']) != (lang, lyric):
            counts[lang] += 1
            group = {'lang': lang, 'pair': counts[lang], 'lyric': lyric}
            groups.append(group)
            key = f'ED_SOURCE:P{counts[lang]:02}:{lang}'
            assert comments[key].strip() == lyric.strip(), ('Current source lyric differs', key)
        p.append((group['lang'], group['pair']))
        if p[4] in ['', 'scene-color-P01']:
            text = p[9]
            jp = lang == 'JP'
            fs = value(text, 'fs', 48 if jp else 52)
            fx = value(text, 'fscx', 100)
            fy = value(text, 'fscy', 100)
            sp = value(text, 'fsp', 0)
            px, py = map(float, re.search(r'\\pos\(([^,]+),([^)]+)\)', text).groups())
            _, _, advance, desc = native.outline(lyric, jp, fs, fx, fy, sp)
            bottom = py + dy
            layouts[p[10]] = {'pair': group['pair'], 'language': lang, 'lyric': lyric, 'bottom_anchor': [cx, bottom], 'advance': advance, 'vertical_shift': dy}
    assert counts == {'VI': 21, 'JP': 21}
    
    pair_widths = {}
    for item in layouts.values():
        pair_widths.setdefault(item['pair'], {})[item['language']] = item['advance']
    assert all(set(widths) == {'VI', 'JP'} for widths in pair_widths.values())
    profiles = {pair: make_cloud_profile(pair, widths['VI'], widths['JP'], cx)
                for pair, widths in pair_widths.items()}

    cloud_source_rows = [p for p in rows if p[3] == 'ED - Cloud']
    effect_times = {}
    for p in cloud_source_rows:
        effect_times.setdefault(p[4], set()).add(ms(p[1]))
    effect_times = {effect: sorted(times) for effect, times in effect_times.items()}

    def profile_for(p):
        effect = p[4]
        pairs = [int(x) for x in re.findall(r'P(\d+)', effect)]
        assert pairs, ('Cloud event has no pair identity', effect)
        times = effect_times[effect]
        idx = bisect.bisect_left(times, ms(p[1]))
        progress = idx / max(1, len(times) - 1)
        if effect.startswith('morph-'):
            assert len(pairs) == 2
            return blend_profiles(profiles[pairs[0]], profiles[pairs[1]], progress)
        base = profiles[pairs[-1]]
        if effect.startswith('in-'):
            return scale_profile(base, 0.48 + 0.52 * progress, cx, 1070.0)
        if effect.startswith('out-'):
            return scale_profile(base, 1.0 - 0.62 * progress, cx, 870.0)
        return base

    for p in rows:
        if p[3] != 'ED - Cloud':
            continue
        h, path = p[9].rsplit('}', 1)
        newpath = natural_an2_cloud(path, profile_for(p))
        p[9] = h + '}' + newpath
        cloud_rows.append(p[:10])
        if p[0] == 'Dialogue: 1':
            white.append({'a': ms(p[1]), 'z': ms(p[2]), 'path': newpath, 'mask': None})
            
    white.sort(key=lambda x: x['a'])
    starts = [x['a'] for x in white]
    
    def at(t):
        i = bisect.bisect_right(starts, t) - 1
        if i < 0 or t >= white[i]['z']:
            return None
        return white[i]
        
    def mask(s):
        if s is None:
            return 'm 0 0 l 0 0 0 0'
        if s['mask'] is None:
            s['mask'] = inset_mask(s['path'])
        return s['mask']
        
    final_text = []
    splits = 0
    for p in rows:
        if p[3] != 'ED - Viator':
            continue
        row = p[:10]
        text = row[9]
        oldpy = float(re.search(r'\\pos\([^,]+,([^)]+)\)', text)[1])
        bottom = oldpy + dy
        # Replace \an3 with \an2
        text = re.sub(r'\\an3(?=[\\}])', r'\\an2', text)
        text = re.sub(r'\\pos\([^)]*\)', lambda m: f'\\pos({fmt(cx)},{fmt(bottom)})', text)
        text = re.sub(r'\\i?clip\([^)]*\)', '', text)
        phase = p[4].startswith(('flow-', 'cloud-in-', 'cloud-out-'))
        if not phase:
            row[9] = text
            final_text.append(row)
            continue
        a, z = ms(p[1]), ms(p[2])
        boundaries = {a, z}
        for frame in white:
            if a < frame['a'] < z:
                boundaries.add(frame['a'])
            if a < frame['z'] < z:
                boundaries.add(frame['z'])
        cuts = sorted(boundaries)
        splits += len(cuts) - 2
        for begin, end in zip(cuts, cuts[1:]):
            r = row.copy()
            r[1] = stamp(begin)
            r[2] = stamp(end)
            r[9] = '{\\clip(' + mask(at(begin)) + ')}' + rebase(text, begin - a)
            final_text.append(r)
            
    ed = iter([*cloud_rows, *final_text])
    out = []
    inserted = False
    for l in raw.splitlines(keepends=True):
        if l.startswith(b'Dialogue:') and l.split(b',', 9)[3] in [b'ED - Cloud', b'ED - Viator']:
            if not inserted:
                out.extend(','.join(r).encode() + b'\n' for r in ed)
                inserted = True
        elif l.startswith(b'Style: ED - Viator,') or l.startswith(b'Style: ED - Cloud,'):
            p = l.rstrip(b'\r\n').split(b',')
            p[18] = b'2'
            out.append(b','.join(p) + b'\n')
        else:
            out.append(l)
            
    blob = b''.join(out)
    output.write_bytes(blob)
    cfg = {
        'master': str(master.resolve()),
        'master_sha256': hashlib.sha256(raw).hexdigest(),
        'audited_editable_source': str(source.resolve()),
        'source_sha256': hashlib.sha256(source_raw).hexdigest(),
        'center_x': cx,
        'vertical_shift': dy,
        'glyph_anchor': [cx, 1080],
        'layouts': list(layouts.values()),
        'cloud_events': len(cloud_rows),
        'text_events': len(final_text),
        'added_phase_splits': splits,
        'native_main_rows': 42,
        'all_phase_masks_rebuilt_from_recentered_cloud': True,
        'cloud_pair_widths': pair_widths,
        'cloud_margin_px': {'minimum': 40, 'maximum': 50, 'left_right_independent': True},
        'cloud_profile_seed': '0xA2C10D + pair*1009',
        'cloud_bank_rule': 'Original an2 skeleton retained: 5 irregular base clusters cover the longer line and 3 asymmetric crown clusters cover JP; each main lobe has one smaller offset join-filler, never a second regular row.'
    }
    (work / 'layout.json').write_text(json.dumps(cfg, ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k, v in cfg.items() if k != 'layouts'}, indent=2))

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('master', type=Path)
    p.add_argument('source', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('work', type=Path)
    p.add_argument('--dy', type=float, default=-6)
    a = p.parse_args()
    build(a.master, a.source, a.output, a.work, dy=a.dy)
