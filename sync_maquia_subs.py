#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_maquia_subs.py
Đồng bộ thoại Việt đã chỉnh sửa (từ Google Sheet hoặc CSV) vào Maquia.vi.ass
Bảo toàn 100% style, timing, prefix tags (fad/pos/c/3c/bord...), cấu trúc layer và font attachments.

Hỗ trợ bảng 4 cột:
  [Actor, Thoại Việt, Maquia WIP Việt gốc (sửa cột này), Trans Note]
"""

import os
import sys
import csv
import json
import argparse
import subprocess
import hashlib
import shutil

def compute_sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def fetch_from_google_sheet(spreadsheet_id, sheet_name="Sheet1"):
    temp_csv = f"/tmp/gsheet_export_{spreadsheet_id}.csv"
    cmd = ["gsheets", "readonly", "export", spreadsheet_id, temp_csv, "--format", "csv", "--sheet", sheet_name]
    print(f"[FETCH] Running: {' '.join(cmd)}")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[ERROR] Failed to fetch from Google Sheet: {res.stderr}", file=sys.stderr)
        sys.exit(1)
    
    rows = []
    with open(temp_csv, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for r in reader:
            if r:
                rows.append(r)
    return header, rows

def read_from_csv(csv_path):
    rows = []
    with open(csv_path, 'r', encoding='utf-8-sig', errors='replace') as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for r in reader:
            if r:
                rows.append(r)
    return header, rows

def sync_subtitles(source_csv=None, sheet_id=None, manifest_path=None, target_ass=None, output_ass=None, sync_col="b", apply=False, dry_run=False):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if not manifest_path:
        manifest_path = os.path.join(script_dir, "maquia_sync_manifest.json")
    if not os.path.exists(manifest_path):
        print(f"[ERROR] Manifest not found: {manifest_path}", file=sys.stderr)
        sys.exit(1)

    print(f"[MANIFEST] Loading {manifest_path}...")
    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)

    if not target_ass:
        target_ass = manifest.get("vi_file", "/media/cuongba956/Download/One room/Maquia.vi.ass")
    if not os.path.exists(target_ass):
        print(f"[ERROR] Target ASS file not found: {target_ass}", file=sys.stderr)
        sys.exit(1)

    if sheet_id:
        print(f"[SOURCE] Fetching from Google Sheet: {sheet_id}...")
        header, edited_rows = fetch_from_google_sheet(sheet_id)
    elif source_csv:
        print(f"[SOURCE] Reading from CSV: {source_csv}...")
        header, edited_rows = read_from_csv(source_csv)
    else:
        print("[ERROR] Must specify either --csv or --sheet", file=sys.stderr)
        sys.exit(1)

    groups = manifest["groups"]
    expected_count = len(groups)
    print(f"[INFO] Header: {header}")
    print(f"[INFO] Loaded {len(edited_rows)} rows (expected: {expected_count}).")

    if len(edited_rows) != expected_count:
        print(f"[ERROR] Row count mismatch! Sheet/CSV has {len(edited_rows)} rows, but manifest expects {expected_count}.", file=sys.stderr)
        print("[HINT] Make sure no rows were added or deleted in the spreadsheet.", file=sys.stderr)
        sys.exit(1)

    # Dynamic column identification from header
    header_clean = [h.strip() for h in header] if header else []
    
    actor_col_idx = 0
    note_col_idx = len(header_clean) - 1
    thoai_viet_col_idx = 1
    wip_col_idx = None

    for i, h in enumerate(header_clean):
        h_lower = h.lower()
        if "actor" in h_lower or "người nói" in h_lower:
            actor_col_idx = i
        elif "trans note" in h_lower or "ghi chú" in h_lower:
            note_col_idx = i
        elif "thoại việt" in h_lower:
            thoai_viet_col_idx = i
        elif "wip" in h_lower or "việt gốc" in h_lower:
            wip_col_idx = i

    if sync_col and sync_col.lower() in ['wip', 'old']:
        if wip_col_idx is not None:
            target_col_idx = wip_col_idx
            col_name_label = header_clean[wip_col_idx]
        else:
            target_col_idx = 1
            col_name_label = "WIP Column"
    else:
        # Default: always sync from "Thoại Việt"
        target_col_idx = thoai_viet_col_idx
        col_name_label = header_clean[thoai_viet_col_idx] if len(header_clean) > thoai_viet_col_idx else "Thoại Việt"

    print(f"[CONFIG] Syncing text from '{col_name_label}' (col idx {target_col_idx}). Actor from col idx {actor_col_idx}, Note verified from col idx {note_col_idx}.")



    mismatches = []
    changes = []
    for idx, (g, r) in enumerate(zip(groups, edited_rows)):
        actor = r[actor_col_idx].strip() if len(r) > actor_col_idx else ""
        new_text = r[target_col_idx].strip() if len(r) > target_col_idx else ""
        note = r[note_col_idx].strip() if len(r) > note_col_idx else ""


        if actor != g["actor"]:
            mismatches.append((idx + 2, "Actor", g["actor"], actor))
        if note != g["trans_note"]:
            mismatches.append((idx + 2, "Trans Note", g["trans_note"][:30], note[:30]))

        orig_text = g["text"]
        if new_text != orig_text:
            changes.append({
                "row_id": g["row_id"],
                "sheet_row": idx + 2,
                "actor": g["actor"],
                "old_text": orig_text,
                "new_text": new_text,
                "lines": g["lines"]
            })

    if mismatches:
        print(f"[ERROR] Detected {len(mismatches)} structural row mismatches between sheet and manifest!", file=sys.stderr)
        for row_num, field, expected, actual in mismatches[:10]:
            print(f"  Row {row_num} [{field}] Expected: '{expected}' != Got: '{actual}'", file=sys.stderr)
        print("[ABORT] Sync stopped to prevent misaligned replacements.", file=sys.stderr)
        sys.exit(1)

    print(f"[VALIDATION] Row structure 100% verified across all {expected_count} rows.")
    print(f"[CHANGES] Found {len(changes)} compact rows with modified dialogue.")

    if not changes:
        print("[RESULT] No dialogue changes detected. File is already in sync.")
        return

    print("\n--- SAMPLE MODIFICATIONS ---")
    for c in changes[:10]:
        print(f"Row {c['sheet_row']} [{c['actor']}] (affects {len(c['lines'])} ASS lines):")
        print(f"  - OLD: {c['old_text']}")
        print(f"  + NEW: {c['new_text']}")
    if len(changes) > 10:
        print(f"... and {len(changes) - 10} more changed rows.")
    print("----------------------------\n")

    if dry_run:
        print("[DRY RUN] Done. No files were written.")
        return

    with open(target_ass, 'r', encoding='utf-8-sig', errors='replace') as f:
        ass_lines = f.readlines()

    total_ass_lines_updated = 0
    for c in changes:
        target_content = c["new_text"]
        for l in c["lines"]:
            line_idx = l["file_line_idx"]
            orig_line = ass_lines[line_idx]
            kind, rest = orig_line.split(':', 1)
            parts = rest.split(',', 9)
            assert kind.strip() == 'Dialogue', f"Safety error: Expected Dialogue at line {line_idx}, got '{kind}'"
            assert parts[3].strip() == l["style"], f"Safety error: Expected style '{l['style']}' at line {line_idx}, got '{parts[3]}'"
            newline_char = '\r\n' if orig_line.endswith('\r\n') else '\n'
            parts[9] = l["prefix_tags"] + target_content + newline_char
            ass_lines[line_idx] = kind + ':' + ','.join(parts)
            total_ass_lines_updated += 1


    print(f"[APPLY] Total ASS dialogue lines unpacked and updated: {total_ass_lines_updated}")

    if apply:
        backup_path = target_ass + ".bak"
        print(f"[BACKUP] Creating backup at {backup_path}...")
        shutil.copy2(target_ass, backup_path)
        dest_path = target_ass
    else:
        if not output_ass:
            output_ass = target_ass.replace('.ass', '.candidate.ass')
        dest_path = output_ass

    print(f"[WRITE] Saving updated subtitles to {dest_path}...")
    with open(dest_path, 'w', encoding='utf-8-sig', newline='') as f:
        f.writelines(ass_lines)

    new_sha256 = compute_sha256(dest_path)
    print(f"[SUCCESS] Subtitles successfully written to {dest_path} (SHA-256: {new_sha256})")

def main():
    parser = argparse.ArgumentParser(description="Sync Vietnamese dialogue from Google Sheet / CSV into Maquia.vi.ass")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--csv", help="Path to edited CSV file")
    group.add_argument("--sheet", help="Google Sheet Spreadsheet ID")
    parser.add_argument("--manifest", help="Path to maquia_sync_manifest.json")
    parser.add_argument("--target-ass", help="Path to target Maquia.vi.ass")
    parser.add_argument("--output-ass", help="Path to output candidate ASS")
    parser.add_argument("--sync-col", default="auto", choices=["auto", "viet", "wip"], help="Which column to sync: 'auto'/'viet' (Thoại Việt) or 'wip' (Maquia WIP Việt gốc)")

    parser.add_argument("--apply", action="store_true", help="Directly update Maquia.vi.ass (creates .bak backup)")
    parser.add_argument("--dry-run", action="store_true", help="Check changes without modifying files")

    args = parser.parse_args()
    sync_subtitles(
        source_csv=args.csv,
        sheet_id=args.sheet,
        manifest_path=args.manifest,
        target_ass=args.target_ass,
        output_ass=args.output_ass,
        sync_col=args.sync_col,
        apply=args.apply,
        dry_run=args.dry_run
    )

if __name__ == '__main__':
    main()
