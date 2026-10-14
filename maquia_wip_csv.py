#!/usr/bin/env python3
"""Gộp Maquia WIP.csv để biên tập, rồi bung lại CSV và ASS đầy đủ.

Chỉ cột "Việt gốc (sửa cột này)" trong CSV gọn được dùng làm bản sửa.
Nguồn và ba ASS được khóa bằng SHA-256 khi tạo bảng gọn. Lệnh export tạo
file mới; không ghi vào Maquia WIP.csv hay Maquia.vi.ass.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE_CSV = ROOT / "Maquia WIP.csv"
COMPACT_CSV = ROOT / "Maquia WIP.gon.csv"
MANIFEST = ROOT / "Maquia WIP.gon.map.json"
VI_ASS = ROOT / "Maquia.vi.ass"
FROM_JP_ASS = ROOT / "Maquia.vi.from-jp.ass"
JP_ASS = ROOT / "Maquia.ass"
DEFAULT_FULL_CSV = ROOT / "Maquia WIP.day-du.csv"
DEFAULT_OUTPUT_ASS = ROOT / "Maquia.vi.tu-WIP.ass"

HEADER = [
    "Dòng ASS gốc",
    "Số dòng",
    "Ghi chú xử lý",
    "Người nói",
    "Việt dịch từ Nhật",
    "Việt gốc (sửa cột này)",
    "Ghi chú đối chiếu Nhật",
]
NOTE_ID = re.compile(r"^\{(\d{4})\}\s*(.*)$", re.DOTALL)
REPEAT = re.compile(r"GIỮ LẶP/LAYER ×(\d+)")
TAG = re.compile(r"\{[^{}]*\}")
PREFIX_ONLY = re.compile(r"((?:\{[^{}]*\})*)([^{}]*)\Z", re.DOTALL)
EVENT_FORMAT = [
    "Layer", "Start", "End", "Style", "Name", "MarginL", "MarginR",
    "MarginV", "Effect", "Text",
]


@dataclass
class AssEvent:
    line_index: int
    fields: dict[str, str]


@dataclass
class AssFile:
    raw: bytes
    bom: bytes
    lines: list[str]
    dialogue: list[AssEvent]


def fail(message: str) -> None:
    raise ValueError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.reader(handle))


def csv_bytes(rows: list[list[str]], *, bom: bool, newline: str,
              final_newline: bool) -> bytes:
    out = io.StringIO(newline="")
    writer = csv.writer(out, lineterminator=newline)
    writer.writerows(rows)
    value = out.getvalue()
    if not final_newline and value.endswith(newline):
        value = value[:-len(newline)]
    return (b"\xef\xbb\xbf" if bom else b"") + value.encode("utf-8")


def split_ending(line: str) -> tuple[str, str]:
    if line.endswith("\r\n"):
        return line[:-2], "\r\n"
    if line.endswith("\n") or line.endswith("\r"):
        return line[:-1], line[-1]
    return line, ""


def read_ass(path: Path) -> AssFile:
    raw = path.read_bytes()
    bom = b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b""
    lines = raw[len(bom):].decode("utf-8").splitlines(keepends=True)
    section = ""
    event_format: list[str] = []
    dialogue: list[AssEvent] = []
    for line_index, line in enumerate(lines):
        body, _ = split_ending(line)
        stripped = body.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped
            continue
        if section != "[Events]":
            continue
        if stripped.startswith("Format:"):
            event_format = [part.strip() for part in stripped[7:].split(",")]
            if event_format != EVENT_FORMAT:
                fail(f"Format Events không hỗ trợ trong {path.name}: {event_format}")
        elif body.startswith("Dialogue:"):
            if not event_format:
                fail(f"Dialogue đứng trước Format trong {path.name}")
            values = body[len("Dialogue:"):].lstrip().split(",", len(event_format) - 1)
            if len(values) != len(event_format):
                fail(f"Dialogue hỏng ở dòng vật lý {line_index + 1} của {path.name}")
            dialogue.append(AssEvent(line_index, dict(zip(event_format, values))))
    return AssFile(raw, bom, lines, dialogue)


def visible(text: str) -> str:
    return TAG.sub("", text)


def prefix_and_visible(text: str) -> tuple[str, str]:
    match = PREFIX_ONLY.fullmatch(text)
    if not match:
        fail("Text ASS có tag nằm giữa câu; cần xử lý riêng để giữ styling")
    return match.group(1), match.group(2)


def note_parts(value: str, row_number: int) -> tuple[str, str]:
    match = NOTE_ID.fullmatch(value)
    if not match or int(match.group(1)) != row_number:
        fail(f"Mã note không khớp dòng CSV {row_number}")
    return match.group(1), match.group(2)


def validate_sources(rows: list[list[str]], vi: AssFile, direct: AssFile,
                     japanese: AssFile) -> tuple[list[str], list[tuple[str, ...]], list[int]]:
    if not rows or any(len(row) != 5 for row in rows):
        fail("CSV gốc phải có đúng 5 cột ở mọi hàng")
    count = len(rows)
    for name, ass in (("Việt", vi), ("dịch từ Nhật", direct), ("Nhật", japanese)):
        if len(ass.dialogue) < count:
            fail(f"ASS {name} có ít hơn {count} dòng Dialogue")

    notes: list[str] = []
    keys: list[tuple[str, ...]] = []
    fallback_rows: list[int] = []
    for index, row in enumerate(rows):
        number = index + 1
        _, note = note_parts(row[4], number)
        a = vi.dialogue[index].fields
        b = direct.dialogue[index].fields
        j = japanese.dialogue[index].fields
        if row[0] != a["Effect"] or row[1] != a["Name"]:
            fail(f"Effect/Name ở dòng {number} không khớp ASS Việt")
        if row[2] != visible(b["Text"]):
            fail(f"Cột dịch từ Nhật ở dòng {number} không khớp ASS tương ứng")
        if note != j["Effect"].strip():
            fail(f"Ghi chú Nhật ở dòng {number} không khớp ASS Nhật")
        _, vi_text = prefix_and_visible(a["Text"])
        if row[3] != vi_text:
            if vi_text == "" and row[3] == row[2]:
                fallback_rows.append(number)
            else:
                fail(f"Cột Việt gốc ở dòng {number} không khớp ASS Việt")
        notes.append(note)
        keys.append((row[1], row[2], row[3], note, visible(j["Text"]), j["Name"]))
    return notes, keys, fallback_rows


def make_groups(rows: list[list[str]], keys: list[tuple[str, ...]]) -> tuple[list[list[int]], list[int]]:
    anchors: dict[int, list[int]] = {}
    members: set[int] = set()
    unmerged_flags: list[int] = []
    for index, row in enumerate(rows):
        match = REPEAT.search(row[0])
        if not match:
            continue
        repeat_count = int(match.group(1))
        candidates = [
            candidate for candidate in range(index + 1, min(len(rows), index + 41))
            if keys[candidate] == keys[index]
            and rows[candidate][0] == ""
            and candidate not in members
        ]
        if len(candidates) < repeat_count - 1:
            unmerged_flags.append(index + 1)
            continue
        group = [index] + candidates[:repeat_count - 1]
        anchors[index] = group
        members.update(group[1:])

    groups: list[list[int]] = []
    for index in range(len(rows)):
        if index in members:
            continue
        groups.append([item + 1 for item in anchors.get(index, [index])])
    used = sorted(item for group in groups for item in group)
    if used != list(range(1, len(rows) + 1)):
        fail("Các nhóm không phủ đúng mỗi dòng gốc một lần")
    return groups, unmerged_flags


def source_hashes() -> dict[str, str]:
    return {path.name: sha256(path) for path in (SOURCE_CSV, VI_ASS, FROM_JP_ASS, JP_ASS)}


def write_file(path: Path, data: bytes, *, force: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        fail(f"Đầu ra đã tồn tại: {path}. Dùng --force nếu muốn tạo lại")
    with tempfile.NamedTemporaryFile(prefix=f".{path.name}.", dir=path.parent,
                                     delete=False) as handle:
        temp_path = Path(handle.name)
        handle.write(data)
    try:
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def build() -> None:
    if COMPACT_CSV.exists() or MANIFEST.exists():
        fail("CSV gọn hoặc map đã có; không ghi đè bản người dùng có thể đã sửa")
    rows = read_csv(SOURCE_CSV)
    vi, direct, japanese = (read_ass(path) for path in (VI_ASS, FROM_JP_ASS, JP_ASS))
    notes, keys, fallback_rows = validate_sources(rows, vi, direct, japanese)
    groups, unmerged_flags = make_groups(rows, keys)
    compact = [HEADER]
    for group in groups:
        first = group[0] - 1
        row = rows[first]
        compact.append([
            " ".join(f"{item:04d}" for item in group),
            str(len(group)), row[0], row[1], row[2], row[3], notes[first],
        ])
    manifest = {
        "version": 1,
        "source_hashes": source_hashes(),
        "source_rows": len(rows),
        "groups": groups,
        "fallback_rows": fallback_rows,
        "unmerged_flags": unmerged_flags,
    }
    write_file(COMPACT_CSV, csv_bytes(compact, bom=True, newline="\r\n",
                                      final_newline=True), force=False)
    write_file(MANIFEST, (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
               force=False)
    merged = sum(len(group) > 1 for group in groups)
    print(f"Đã tạo {COMPACT_CSV.name}: {len(groups)} hàng từ {len(rows)} dòng gốc; "
          f"gộp {merged} nhóm; {len(fallback_rows)} dòng Việt gốc đang trống trong ASS.")
    print(f"Giữ riêng hai cặp khác người nói ở dòng {', '.join(map(str, unmerged_flags))}.")


def load_edited(compact_path: Path) -> tuple[list[list[str]], list[list[str]], dict, int]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("version") != 1:
        fail("Phiên bản map không hỗ trợ")
    current_hashes = source_hashes()
    for name, expected in manifest["source_hashes"].items():
        if current_hashes.get(name) != expected:
            fail(f"Nguồn {name} đã đổi sau khi tạo CSV gọn; cần đối chiếu và tạo map mới")
    source_rows = read_csv(SOURCE_CSV)
    if len(source_rows) != manifest["source_rows"]:
        fail("Số dòng CSV gốc đã đổi")
    compact = read_csv(compact_path)
    if not compact or compact[0] != HEADER:
        fail("Tiêu đề CSV gọn đã đổi")
    if any(len(row) != len(HEADER) for row in compact):
        fail("Có hàng CSV gọn không đủ 7 cột")
    expected_groups = {tuple(group) for group in manifest["groups"]}
    if len(compact) - 1 != len(expected_groups):
        fail("Số nhóm trong CSV gọn đã đổi")
    seen: set[tuple[int, ...]] = set()
    expanded = [row.copy() for row in source_rows]
    edited_groups = 0
    for row in compact[1:]:
        try:
            group = tuple(int(item) for item in row[0].split())
        except ValueError:
            fail(f"Mã dòng nguồn không hợp lệ: {row[0]!r}")
        if group not in expected_groups or group in seen:
            fail(f"Nhóm dòng nguồn bị đổi hoặc lặp: {row[0]!r}")
        seen.add(group)
        original = source_rows[group[0] - 1]
        _, note = note_parts(original[4], group[0])
        if row[1] != str(len(group)) or [row[2], row[3], row[4], row[6]] != [
            original[0], original[1], original[2], note,
        ]:
            fail(f"Cột tham chiếu của nhóm {row[0]} đã đổi; chỉ sửa cột Việt gốc")
        new_text = row[5]
        if "\r" in new_text or "\n" in new_text:
            fail(f"Nhóm {row[0]} có xuống dòng thật; dùng ký hiệu ASS \\N")
        if "{" in new_text or "}" in new_text:
            fail(f"Nhóm {row[0]} chứa ngoặc tag ASS trong cột Việt gốc")
        if new_text != original[3]:
            edited_groups += 1
        for number in group:
            expanded[number - 1][3] = new_text
    if seen != expected_groups:
        fail("CSV gọn thiếu nhóm")
    return source_rows, expanded, manifest, edited_groups


def patch_ass(vi: AssFile, expanded: list[list[str]]) -> tuple[bytes, int]:
    lines = vi.lines.copy()
    changed = 0
    for index, row in enumerate(expanded):
        event = vi.dialogue[index]
        original_text = event.fields["Text"]
        prefix, old_visible = prefix_and_visible(original_text)
        new_visible = row[3]
        if new_visible == old_visible:
            continue
        raw_line, ending = split_ending(lines[event.line_index])
        parts = raw_line.split(",", len(EVENT_FORMAT) - 1)
        if len(parts) != len(EVENT_FORMAT) or parts[-1] != original_text:
            fail(f"Không thể giữ nguyên trường ASS ở Dialogue {index + 1}")
        lines[event.line_index] = ",".join(parts[:-1]) + "," + prefix + new_visible + ending
        changed += 1
    output = vi.bom + "".join(lines).encode("utf-8")
    return output, changed


def export(compact_path: Path, full_path: Path, ass_path: Path, *, force: bool) -> None:
    protected = {path.resolve() for path in
                 (SOURCE_CSV, COMPACT_CSV, compact_path, MANIFEST, VI_ASS, FROM_JP_ASS, JP_ASS,
                  Path(__file__).resolve())}
    if full_path.resolve() in protected or ass_path.resolve() in protected:
        fail("Đầu ra không được trùng file nguồn hoặc CSV đang biên tập")
    if full_path.resolve() == ass_path.resolve():
        fail("Hai đầu ra phải khác nhau")
    if not force and (full_path.exists() or ass_path.exists()):
        fail("Đầu ra đã tồn tại; dùng --force nếu muốn tạo lại")
    source_rows, expanded, manifest, edited_groups = load_edited(compact_path)
    source_raw = SOURCE_CSV.read_bytes()
    if expanded == source_rows:
        full_data = source_raw
    else:
        newline = "\r\n" if b"\r\n" in source_raw else "\n"
        full_data = csv_bytes(expanded, bom=source_raw.startswith(b"\xef\xbb\xbf"),
                              newline=newline, final_newline=source_raw.endswith(b"\n"))
    vi = read_ass(VI_ASS)
    ass_data, changed_events = patch_ass(vi, expanded)
    write_file(full_path, full_data, force=force)
    write_file(ass_path, ass_data, force=force)
    print(f"Đã bung {len(expanded)} dòng vào {full_path}")
    print(f"Đã tạo {ass_path}: {changed_events} Text đổi; {edited_groups} nhóm được sửa "
          f"trong CSV gọn; {len(manifest['fallback_rows'])} dòng nguồn Việt trống "
          "sẽ nhận lời trong CSV.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build", help="Tạo CSV gọn và map từ bốn file nguồn hiện tại")
    export_parser = sub.add_parser("export", help="Bung CSV gọn và tạo ASS Việt ứng viên")
    export_parser.add_argument("--compact", type=Path, default=COMPACT_CSV)
    export_parser.add_argument("--csv-out", type=Path, default=DEFAULT_FULL_CSV)
    export_parser.add_argument("--ass-out", type=Path, default=DEFAULT_OUTPUT_ASS)
    export_parser.add_argument("--force", action="store_true",
                               help="Ghi đè hai đầu ra đã tạo trước đó")
    args = parser.parse_args()
    if args.command == "build":
        build()
    else:
        export(args.compact, args.csv_out, args.ass_out, force=args.force)


if __name__ == "__main__":
    try:
        main()
    except (OSError, UnicodeError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"Lỗi: {exc}", file=sys.stderr)
        sys.exit(1)
