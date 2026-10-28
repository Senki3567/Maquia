#!/usr/bin/env python3
"""Install the approved an2 joins candidate into the Maquia master, guarded."""

from collections import Counter
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import tempfile

from fontTools import subset
from fontTools.ttLib import TTFont

from ass_attachments import append_font, blocks, read_fonts, replace_font


ROOT = Path(__file__).resolve().parents[2]
MASTER = ROOT / 'Maquia.vi.ass'
CANDIDATE = ROOT / 'Maquia.vi.ED-an2-joins.ass'
ARCHIVE = ROOT / '.archive/ed-an2-installed-20261019'
MASTER_SHA = 'f6de8b69f84f8c14142dfb568010ffc06af80a1aa005493f7c72dda40e9b6765'
CANDIDATE_SHA = '6bd41532f7e33319c8a3938d129bc30bf89b2af16d268732b7b2da1eb59d5e76'
SLIDE_FONT = Path('/home/cuongba956/.local/share/fonts/KNK_Fonts/#9slide04 spectral medium.ttf')
NOTO_FONT = Path('/home/cuongba956/.local/share/fonts/Google/TrueType/Noto Serif JP/Noto_Serif_JP_ExtraLight.ttf')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def event_lines(blob, ed):
    section = b''
    result = []
    for line in blob.splitlines(keepends=True):
        if re.fullmatch(rb'\[[^]]+\]\r?\n', line):
            section = line.strip()
        elif section == b'[Events]' and line.startswith((b'Dialogue:', b'Comment:')):
            fields = line.split(b',', 9)
            if fields[3].startswith(b'ED') == ed:
                result.append(line)
    return result


def remove_font(blob, name):
    found = [block for block in blocks(blob) if block[0] == name]
    if len(found) != 1:
        raise ValueError(f'expected exactly one {name} attachment')
    _, start, _, end = found[0]
    return blob[:start] + blob[end:]


def main():
    original = MASTER.read_bytes()
    proposed = CANDIDATE.read_bytes()
    if sha(original) != MASTER_SHA or sha(proposed) != CANDIDATE_SHA:
        raise ValueError('master/candidate hash differs from reviewed version')
    if event_lines(original, False) != event_lines(proposed, False):
        raise ValueError('candidate changed non-ED events')
    old_ed = event_lines(original, True)
    new_ed = event_lines(proposed, True)
    if len(old_ed) != 1919 or len(new_ed) != 2688:
        raise ValueError('unexpected ED event counts')
    if b'MaquiaEDCFFbacae33c' in b''.join(new_ed):
        raise ValueError('old ED font still referenced')
    fonts = read_fonts(proposed)
    if set(fonts) != {'CarynVI-MaquiaSketch.ttf', 'MaquiaEDRepaired.otf',
                      'MaquiaEDBottom-minimal.otf'}:
        raise ValueError(f'unexpected candidate fonts: {list(fonts)}')
    if sha(fonts['MaquiaEDBottom-minimal.otf']) != sha((ROOT / 'MaquiaEDBottom-joins.otf').read_bytes()):
        raise ValueError('new ED font attachment differs from reviewed font')

    # Only the 21 direct Japanese lyric events use Noto; retain its shaping
    # tables and variable axes while subsetting the exact rendered characters.
    jp_text = []
    for line in new_ed:
        if line.startswith(b'Dialogue:') and b'\\fnNoto Serif JP' in line:
            text = line.decode('utf-8').split(',', 9)[9]
            jp_text.append(re.sub(r'\{[^}]*\}', '', text).strip())
    if len(jp_text) != 21:
        raise ValueError(f'expected 21 direct Japanese lyric events, got {len(jp_text)}')
    opts = subset.Options()
    opts.layout_features = ['*']
    opts.name_IDs = ['*']
    opts.name_languages = ['*']
    font = TTFont(NOTO_FONT)
    subsetter = subset.Subsetter(options=opts)
    subsetter.populate(text=''.join(jp_text))
    subsetter.subset(font)
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    noto_subset = ARCHIVE / 'NotoSerifJP-Maquia-subset.ttf'
    font.save(noto_subset)
    subset_bytes = noto_subset.read_bytes()
    subset_cmap = TTFont(noto_subset).getBestCmap()
    missing = sorted(set(map(ord, ''.join(jp_text))) - set(subset_cmap))
    if missing:
        raise ValueError(f'missing Japanese subset codepoints: {missing}')

    final = remove_font(proposed, 'MaquiaEDRepaired.otf')
    final = replace_font(final, 'MaquiaEDBottom-minimal.otf',
                         'MaquiaEDBottom-joins.otf', fonts['MaquiaEDBottom-minimal.otf'])
    final = append_font(final, '#9slide04 spectral medium.ttf', SLIDE_FONT.read_bytes())
    final = append_font(final, 'NotoSerifJP-Maquia-subset.ttf', subset_bytes)
    final_fonts = read_fonts(final)
    if set(final_fonts) != {'CarynVI-MaquiaSketch.ttf', 'MaquiaEDBottom-joins.otf',
                            '#9slide04 spectral medium.ttf', 'NotoSerifJP-Maquia-subset.ttf'}:
        raise ValueError(f'wrong final fonts: {list(final_fonts)}')
    if event_lines(final, True) != new_ed or event_lines(final, False) != event_lines(original, False):
        raise ValueError('event payload changed during font integration')
    if MASTER.read_bytes() != original:
        raise ValueError('master changed during staging')

    backup = ARCHIVE / 'Maquia.vi.ass.before-an2-joins.ass'
    if backup.exists():
        raise FileExistsError(f'backup already exists: {backup}')
    shutil.copy2(MASTER, backup)
    if backup.read_bytes() != original:
        raise ValueError('backup verification failed')
    with tempfile.NamedTemporaryFile(dir=ROOT, prefix='.Maquia.vi.ass.stage-', delete=False) as handle:
        handle.write(final)
        staged = Path(handle.name)
    try:
        if MASTER.read_bytes() != original:
            raise ValueError('master changed before install')
        os.replace(staged, MASTER)
    finally:
        staged.unlink(missing_ok=True)
    if MASTER.read_bytes() != final:
        raise ValueError('master readback mismatch')
    report = {
        'master_before_sha256': sha(original),
        'candidate_sha256': sha(proposed),
        'master_after_sha256': sha(final),
        'backup': str(backup),
        'ed_events_before': len(old_ed),
        'ed_events_after': len(new_ed),
        'non_ed_events_unchanged': True,
        'fonts': {name: {'bytes': len(data), 'sha256': sha(data)}
                  for name, data in final_fonts.items()},
        'noto_subset_characters': len(set(''.join(jp_text))),
    }
    (ARCHIVE / 'install-manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
