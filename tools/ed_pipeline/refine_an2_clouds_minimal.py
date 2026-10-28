#!/usr/bin/env python3
"""Correct peak height and shoulder joins on all 21 original an2 clouds.

The 16 original contours retain their size and number.  Only two inner base
pairs and three crown pairs move; the text masks follow the corrected clouds.
Translation follows animation scale and morph progress.
"""
from pathlib import Path
import argparse
import bisect
import hashlib
import json
import math
import random
import re

from create_an2_variant import ellipse_info, inset_mask
import native_font_geometry as native


NUMBER = re.compile(r'-?\d+(?:\.\d+)?')


def contours(path):
    return re.findall(r'm\s+[^m]+', path)


def ellipse_ry(path):
    values = list(map(float, NUMBER.findall(path)))
    ys = values[1::2]
    return (max(ys) - min(ys)) / 2.0


def move_xy(path, dx, dy):
    point_index = 0

    def replace(match):
        nonlocal point_index
        value = float(match.group(0))
        value += dy if point_index % 2 else dx
        point_index += 1
        return f'{value:.6f}'.rstrip('0').rstrip('.')

    return NUMBER.sub(replace, path)


def ms(stamp):
    hours, minutes, seconds = stamp.split(':')
    return round((int(hours) * 3600 + int(minutes) * 60 + float(seconds)) * 1000)


def pair_adjustments(pair, vi_width, jp_width, jp_ink_top):
    """Small changes measured against each pair's original shoulder span."""
    gap = max(0.0, (max(vi_width, jp_width) - jp_width) / 2.0)
    rng = random.Random(0xA2C10D + pair * 1009)
    variation = rng.uniform(-1.5, 1.5)
    base_left = (-min(35.0, gap * 0.16), -min(20.0, gap * 0.10))
    base_right = (min(25.0, gap * 0.12), -min(18.0, gap * 0.09))
    # The original crown contour tops are identical across the 21 pairs.  Set
    # the tallest dome from actual JP ink, then descend by 8 and 22 px.
    crown_top = jp_ink_top - 45.0 + variation
    crown_left = (-min(35.0, gap * 0.17), crown_top - 830.95)
    crown_middle = (0.0, crown_top + 8.0 - 845.24)
    crown_right = (min(20.0, gap * 0.08), crown_top + 22.0 - 890.2)
    return ((2, 3, *base_left, 59.0, 35.0),
            (6, 7, *base_right, 63.0, 37.0),
            (10, 11, *crown_left, 85.0, 55.0),
            (12, 13, *crown_middle, 71.0, 51.0),
            (14, 15, *crown_right, 50.0, 33.0))


def blend_adjustments(left, right, progress):
    return tuple((a[0], a[1], a[2] + (b[2] - a[2]) * progress,
                  a[3] + (b[3] - a[3]) * progress, a[4], a[5])
                 for a, b in zip(left, right))


def crown_valley(parts, left, right):
    """Deepest exposed join between two original main crown contours."""
    x0 = ellipse_info(parts[left])[0]
    x1 = ellipse_info(parts[right])[0]
    lo, hi = sorted((x0, x1))
    ellipses = [ellipse_info(part) for i, part in enumerate(parts) if i not in (11, 15)]
    worst = (lo, -float('inf'))
    for step in range(121):
        x = lo + (hi - lo) * (0.15 + 0.70 * step / 120)
        heights = [cy - ry * math.sqrt(max(0.0, 1 - ((x - cx) / rx) ** 2))
                   for cx, cy, rx, ry in ellipses if rx and abs(x - cx) <= rx]
        if heights and min(heights) > worst[1]:
            worst = (x, min(heights))
    return worst


def join_adjustments(path, jp_ink_top):
    parts = contours(path)
    extras = []
    for left, right, helper in ((10, 12, 11), (12, 14, 15)):
        valley_x, valley_y = crown_valley(parts, left, right)
        cx, cy, _, ry = ellipse_info(parts[helper])
        # A join less than 25 px above the ink reads as a clipped/tangent
        # edge.  Reuse its existing small lobe, without adding new clouds.
        if valley_y > jp_ink_top - 25:
            extras.append((helper, valley_x - cx, jp_ink_top - 40 - (cy - ry), ry))
        else:
            extras.append((helper, 0.0, 0.0, ry))
    return tuple(extras)


def blend_extras(left, right, progress):
    return tuple((a[0], a[1] + (b[1] - a[1]) * progress,
                  a[2] + (b[2] - a[2]) * progress, a[3])
                 for a, b in zip(left, right))


def refine(path, specs, extras=()):
    parts = contours(path)
    if len(parts) != 16:
        raise ValueError(f'expected 16 contours, found {len(parts)}')

    # The radii are from the original steady an2 shapes; scaling the movement
    # by each live radius preserves the existing grow/morph/shrink animation.
    for main, helper, dx, dy, main_ry, helper_ry in specs:
        scale = ellipse_ry(parts[main]) / main_ry
        parts[main] = move_xy(parts[main], dx * scale, dy * scale)
        scale = ellipse_ry(parts[helper]) / helper_ry
        parts[helper] = move_xy(parts[helper], dx * scale, dy * scale)
    for helper, dx, dy, reference_ry in extras:
        scale = ellipse_ry(parts[helper]) / reference_ry
        parts[helper] = move_xy(parts[helper], dx * scale, dy * scale)
    return ' '.join(parts)


def build(source, layout, output):
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != 'cda025e2f784b9a1bf98adb05914fd5038394351db07976ab0002bffbe7e9755':
        raise ValueError('expected the original an2 editable source')
    layout_data = json.loads(layout.read_text())
    widths = {}
    jp_ink_tops = {}
    for item in layout_data['layouts']:
        widths.setdefault(str(item['pair']), {})[item['language']] = item['advance']
        if item['language'] == 'JP':
            _, rings, advance, descent = native.outline(item['lyric'], True, 48, 141.19, 118.58, 0)
            if abs(advance - item['advance']) > 0.01:
                raise ValueError(f'JP layout changed for pair {item["pair"]}')
            jp_ink_tops[item['pair']] = item['bottom_anchor'][1] - descent + min(
                y for ring in rings for _, y in ring)
    adjustments = {int(pair): pair_adjustments(int(pair), value['VI'], value['JP'],
                                               jp_ink_tops[int(pair)])
                   for pair, value in widths.items()}
    if set(adjustments) != set(range(1, 22)):
        raise ValueError('expected widths for all 21 pairs')
    effect_times = {}
    steady_paths = {}
    for line in raw.splitlines():
        if not line.startswith(b'Dialogue:'):
            continue
        fields = line.decode('utf-8').split(',', 9)
        if fields[3] == 'ED - Cloud':
            effect_times.setdefault(fields[4], set()).add(ms(fields[1]))
            if fields[0] == 'Dialogue: 1' and re.fullmatch(r'(?:main|scene-color)-P\d+', fields[4]):
                pair = int(fields[4].split('P')[1])
                steady_paths.setdefault(pair, fields[9].rsplit('}', 1)[1])
    effect_times = {effect: sorted(times) for effect, times in effect_times.items()}
    if set(steady_paths) != set(range(1, 22)):
        raise ValueError('expected steady cloud paths for all 21 pairs')
    extras = {pair: join_adjustments(refine(path, adjustments[pair]), jp_ink_tops[pair])
              for pair, path in steady_paths.items()}
    for pair in sorted(extras):
        print(f'P{pair:02}: joins=' + ', '.join(
            f'{index}: dx={dx:.1f}, dy={dy:.1f}' for index, dx, dy, _ in extras[pair]))

    def shifts_for(fields):
        effect = fields[4]
        pairs = [int(number) for number in re.findall(r'P(\d+)', effect)]
        if not pairs:
            raise ValueError(f'cloud effect has no pair: {effect}')
        if effect.startswith('morph-'):
            if len(pairs) != 2:
                raise ValueError(effect)
            times = effect_times[effect]
            progress = bisect.bisect_left(times, ms(fields[1])) / max(1, len(times) - 1)
            return (blend_adjustments(adjustments[pairs[0]], adjustments[pairs[1]], progress),
                    blend_extras(extras[pairs[0]], extras[pairs[1]], progress))
        return adjustments[pairs[-1]], extras[pairs[-1]]

    changed = 0
    white = []
    out = []
    for line in raw.splitlines(keepends=True):
        if line.startswith(b'Dialogue:'):
            fields = line.rstrip(b'\r\n').decode('utf-8').split(',', 9)
            if fields[3] == 'ED - Cloud':
                head, path = fields[9].rsplit('}', 1)
                new_path = refine(path, *shifts_for(fields))
                fields[9] = head + '}' + new_path
                if fields[0] == 'Dialogue: 1':
                    white.append((ms(fields[1]), ms(fields[2]), new_path))
                newline = b'\r\n' if line.endswith(b'\r\n') else b'\n'
                line = ','.join(fields).encode('utf-8') + newline
                changed += 1
        out.append(line)
    if changed != 1076:
        raise ValueError(f'expected 1076 cloud events, changed {changed}')
    white.sort()
    starts = [item[0] for item in white]
    mask_cache = {}

    def mask_at(time):
        idx = bisect.bisect_right(starts, time) - 1
        if idx < 0 or time >= white[idx][1]:
            return 'm 0 0 l 0 0 0 0'
        if idx not in mask_cache:
            mask_cache[idx] = inset_mask(white[idx][2])
        return mask_cache[idx]

    fixed = []
    clips = 0
    for line in out:
        if line.startswith(b'Dialogue:'):
            fields = line.rstrip(b'\r\n').decode('utf-8').split(',', 9)
            if fields[3] == 'ED - Viator' and fields[9].startswith('{\\clip('):
                old_clip = re.match(r'^\{\\clip\([^}]*\)\}', fields[9])
                if old_clip is None:
                    raise ValueError(f'bad clip: {fields[4]}')
                fields[9] = '{\\clip(' + mask_at(ms(fields[1])) + ')}' + fields[9][old_clip.end():]
                newline = b'\r\n' if line.endswith(b'\r\n') else b'\n'
                line = ','.join(fields).encode('utf-8') + newline
                clips += 1
        fixed.append(line)
    if clips != 1528:
        raise ValueError(f'expected 1528 text clips, changed {clips}')
    output.write_bytes(b''.join(fixed))
    print(f'changed_cloud_events={changed} rebuilt_text_clips={clips} pairs={len(adjustments)}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('layout', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    build(args.source, args.layout, args.output)
