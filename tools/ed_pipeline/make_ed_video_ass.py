#!/usr/bin/env python3
"""Make a standalone, time-zero ED ASS with three-second head/tail padding."""

from pathlib import Path
import hashlib
import re


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'Maquia.vi.ass'
OUTPUT = ROOT / 'Maquia.ED-an2-joins.video.ass'
SOURCE_SHA = '127cfeaa6d495e15ed5b5e0a69aa4d353a01666eafe42694ed5f4857e8ef61ca'
FIRST_ED_CS = 658644
HEAD_CS = 300
END_ED_CS = 682023
TAIL_CS = 300


def centiseconds(value):
    hours, minutes, rest = value.split(':')
    seconds, cents = rest.split('.')
    return (int(hours) * 3600 + int(minutes) * 60 + int(seconds)) * 100 + int(cents)


def stamp(value):
    if value < 0:
        raise ValueError('negative shifted timestamp')
    return f'{value // 360000}:{value // 6000 % 60:02}:{value // 100 % 60:02}.{value % 100:02}'


def main():
    raw = SOURCE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA:
        raise ValueError('approved master changed')
    lines = raw.splitlines(keepends=True)
    section = b''
    output = []
    dialogues = comments = 0
    for line in lines:
        if re.fullmatch(rb'\[[^]]+\]\r?\n', line):
            section = line.strip()
        if section == b'[Events]' and line.startswith((b'Dialogue:', b'Comment:')):
            fields = line.rstrip(b'\r\n').decode('utf-8').split(',', 9)
            if not fields[3].startswith('ED'):
                continue
            for index in (1, 2):
                fields[index] = stamp(centiseconds(fields[index]) - FIRST_ED_CS + HEAD_CS)
            line = ','.join(fields).encode('utf-8') + (b'\r\n' if line.endswith(b'\r\n') else b'\n')
            dialogues += fields[0].startswith('Dialogue:')
            comments += fields[0].startswith('Comment:')
        output.append(line)
    if (dialogues, comments) != (2646, 42):
        raise ValueError(f'unexpected ED event counts: {dialogues}, {comments}')
    blob = b''.join(output)
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    OUTPUT.write_bytes(blob)
    print(f'output={OUTPUT} dialogues={dialogues} comments={comments} '
          f'head_seconds={HEAD_CS / 100:.2f} tail_seconds={TAIL_CS / 100:.2f} '
          f'duration_seconds={(END_ED_CS - FIRST_ED_CS + HEAD_CS + TAIL_CS) / 100:.2f} '
          f'sha256={hashlib.sha256(blob).hexdigest()}')


if __name__ == '__main__':
    main()
