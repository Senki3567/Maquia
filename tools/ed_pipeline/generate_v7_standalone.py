#!/usr/bin/env python3
"""Generate independent Maquia.vi.v7.ass with v7 organic clouds and centered an2 layout."""

import json
import math
from pathlib import Path
import re
import numpy as np

ROOT = Path("/media/cuongba956/Download/One room")
MASTER = ROOT / "Maquia.vi.ass"
OUTPUT = ROOT / "Maquia.vi.v7.ass"

def ass_to_ms(stamp):
    h, m, s = stamp.strip().split(":")
    return round((int(h) * 3600 + int(m) * 60 + float(s)) * 1000)

def ms_to_ass(ms):
    cs = max(0, round(ms / 10))
    return f"{cs//360000}:{cs//6000%60:02}:{cs//100%60:02}.{cs%100:02}"

def bezier_arc(p0, p1, bulge, outward_n):
    x0, y0 = p0
    x1, y1 = p1
    dx = x1 - x0
    dy = y1 - y0
    dist = math.hypot(dx, dy)
    if dist < 1e-4:
        return [round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1), round(x1, 1), round(y1, 1)]
    nx, ny = outward_n
    c1x = x0 + dx * 0.22 + nx * bulge * 1.35
    c1y = y0 + dy * 0.22 + ny * bulge * 1.35
    c2x = x0 + dx * 0.78 + nx * bulge * 1.35
    c2y = y0 + dy * 0.78 + ny * bulge * 1.35
    return [round(c1x, 1), round(c1y, 1), round(c2x, 1), round(c2y, 1), round(x1, 1), round(y1, 1)]

def pts_to_ass_path(segments):
    path = []
    first = True
    for p0, p1, n, bulge in segments:
        if first:
            path.append(f"m {int(round(p0[0]))} {int(round(p0[1]))}")
            first = False
        ctrls = bezier_arc(p0, p1, bulge, n)
        path.append(f"b {int(round(ctrls[0]))} {int(round(ctrls[1]))} {int(round(ctrls[2]))} {int(round(ctrls[3]))} {int(round(ctrls[4]))} {int(round(ctrls[5]))}")
    return " ".join(path)

def make_puff_path(cx, cy, rx, ry):
    kx = rx * 0.55228475
    ky = ry * 0.55228475
    p = [
        f"m {int(round(cx - rx))} {int(round(cy))}",
        f"b {int(round(cx - rx))} {int(round(cy - ky))} {int(round(cx - kx))} {int(round(cy - ry))} {int(round(cx))} {int(round(cy - ry))}",
        f"b {int(round(cx + kx))} {int(round(cy - ry))} {int(round(cx + rx))} {int(round(cy - ky))} {int(round(cx + rx))} {int(round(cy))}",
        f"b {int(round(cx + rx))} {int(round(cy + ky))} {int(round(cx + kx))} {int(round(cy + ry))} {int(round(cx))} {int(round(cy + ry))}",
        f"b {int(round(cx - kx))} {int(round(cy + ry))} {int(round(cx - rx))} {int(round(cy + ky))} {int(round(cx - rx))} {int(round(cy))}",
    ]
    return " ".join(p)

def get_standard_cloud_points(jp_box, vi_box, layer='white', seed=42):
    rng = np.random.RandomState(seed)
    jp_x1, jp_y1, jp_x2, jp_y2 = jp_box
    vi_x1, vi_y1, vi_x2, vi_y2 = vi_box
    
    if layer == 'blue':
        M_top, M_bot, M_left, M_right = 38, 36, 42, 42
    else:
        M_top, M_bot, M_left, M_right = 28, 24, 30, 30

    r_x = max(jp_x2, vi_x2) + M_right
    l_x_vi = vi_x1 - M_left
    l_x_jp = jp_x1 - M_left
    y_top_jp = jp_y1 - M_top
    y_bot_vi = vi_y2 + M_bot
    y_top_vi = vi_y1 - M_top
    
    segments = []
    
    # 1. Right side (2 segments)
    p_tr = (r_x - 12, y_top_jp)
    p_r_mid = (r_x + 6, (y_top_jp * 0.4 + y_bot_vi * 0.6))
    p_br = (r_x - 16, y_bot_vi)
    segments.append((p_tr, p_r_mid, (0.8, -0.5), 16 if layer=='white' else 20))
    segments.append((p_r_mid, p_br, (0.7, 0.7), 12 if layer=='white' else 16))
    
    # 2. Bottom base (4 segments)
    bot_pts = []
    for i in range(5):
        t = i / 4.0
        bx = (r_x - 16) * (1 - t) + (l_x_vi + 20) * t
        by = y_bot_vi + math.sin(t * math.pi * 2.5) * 3.0 + rng.uniform(-1.0, 1.0)
        bot_pts.append((bx, by))
    for i in range(4):
        b_val = rng.uniform(5, 8) if layer=='white' else rng.uniform(8, 12)
        segments.append((bot_pts[i], bot_pts[i+1], (0.0, 1.0), b_val))
        
    # 3. Left side of VI (2 segments)
    p_bl = (l_x_vi + 20, y_bot_vi)
    p_l_vi_mid = (l_x_vi - 6, (y_bot_vi + y_top_vi)/2.0)
    p_tl_vi = (l_x_vi + 18, y_top_vi)
    segments.append((p_bl, p_l_vi_mid, (-0.8, 0.6), 14 if layer=='white' else 18))
    segments.append((p_l_vi_mid, p_tl_vi, (-0.8, -0.6), 16 if layer=='white' else 20))
    
    # 4. VI top ridge (2 segments)
    w_vi = max(20.0, (l_x_jp - 15) - (l_x_vi + 18))
    p_v_mid = (l_x_vi + 18 + w_vi * 0.55, y_top_vi + rng.uniform(-1.5, 1.5))
    p_v_end = (max(l_x_vi + 20, l_x_jp - 15), y_top_vi)
    segments.append(((l_x_vi + 18, y_top_vi), p_v_mid, (0.0, -1.0), rng.uniform(14, 18) if layer=='white' else rng.uniform(11, 14)))
    segments.append((p_v_mid, p_v_end, (0.0, -1.0), rng.uniform(12, 16) if layer=='white' else rng.uniform(9, 12)))
    
    # 5. Step transition (2 segments)
    p_step_0 = p_v_end
    p_step_mid = (l_x_jp - 4, (y_top_vi * 0.45 + y_top_jp * 0.55))
    p_step_1 = (l_x_jp + 22, y_top_jp)
    segments.append((p_step_0, p_step_mid, (-0.75, -0.65), 14 if layer=='white' else 17))
    segments.append((p_step_mid, p_step_1, (-0.45, -0.9), 16 if layer=='white' else 19))
    
    # 6. JP top ridge (3 segments)
    w_jp = (r_x - 12) - (l_x_jp + 22)
    p_j_mid1 = (l_x_jp + 22 + w_jp * 0.32, y_top_jp - 2.0 + rng.uniform(-1.5, 1.5))
    p_j_mid2 = (l_x_jp + 22 + w_jp * 0.70, y_top_jp + 1.0 + rng.uniform(-1.5, 1.5))
    segments.append((p_step_1, p_j_mid1, (0.0, -1.0), rng.uniform(18, 23) if layer=='white' else rng.uniform(14, 18)))
    segments.append((p_j_mid1, p_j_mid2, (0.0, -1.0), rng.uniform(22, 28) if layer=='white' else rng.uniform(17, 22)))
    segments.append((p_j_mid2, p_tr, (0.3, -0.9), rng.uniform(16, 20) if layer=='white' else rng.uniform(12, 16)))
    
    return segments

def get_lead_in_skeleton(jp_box, vi_box, seed=42):
    rng = np.random.RandomState(seed)
    jp_x1, jp_y1, jp_x2, jp_y2 = jp_box
    vi_x1, vi_y1, vi_x2, vi_y2 = vi_box
    r_x = max(jp_x2, vi_x2) + 30
    l_x_vi = vi_x1 - 30
    l_x_jp = jp_x1 - 30
    y_top_jp = jp_y1 - 28
    y_bot_vi = vi_y2 + 24
    y_top_vi = vi_y1 - 28
    w_total = r_x - l_x_vi
    
    anchor_x = (l_x_vi + r_x) / 2.0
    anchor_y = y_bot_vi - 10
    
    nodes = []
    
    # Bottom billows
    n_bot = max(3, int(round(w_total / 120.0)))
    for i in range(n_bot):
        frac = (i + 0.5) / n_bot
        tx = l_x_vi + frac * w_total
        ty = y_bot_vi - 15 + rng.uniform(-6, 6)
        rx = rng.uniform(60, 78)
        ry = rng.uniform(42, 54)
        delay = abs(frac - 0.5) * 0.25
        nodes.append({"tx": tx, "ty": ty, "rx": rx, "ry": ry, "delay": delay})
        
    # Core body billows
    n_core = max(4, int(round(w_total / 85.0)))
    for i in range(n_core):
        frac = (i + 0.5) / n_core
        tx = l_x_vi + frac * w_total
        ty = (y_top_vi + y_bot_vi) / 2.0 + rng.uniform(-6, 6)
        rx = rng.uniform(68, 86)
        ry = rng.uniform(45, 58)
        delay = 0.12 + abs(frac - 0.5) * 0.32
        nodes.append({"tx": tx, "ty": ty, "rx": rx, "ry": ry, "delay": delay})
        
    # Crown domes (covering JP)
    w_jp = r_x - l_x_jp
    n_jp = max(3, int(round(w_jp / 70.0)))
    for i in range(n_jp):
        frac = (i + 0.5) / n_jp
        tx = l_x_jp + frac * w_jp
        ty = y_top_jp + 12 + rng.uniform(-4, 4)
        rx = rng.uniform(60, 78)
        ry = rng.uniform(40, 52)
        delay = 0.22 + frac * 0.25
        nodes.append({"tx": tx, "ty": ty, "rx": rx, "ry": ry, "delay": delay})
        
    return nodes, anchor_x, anchor_y

def get_lead_out_clusters(jp_box, vi_box, seed=42):
    rng = np.random.RandomState(seed)
    jp_x1, jp_y1, jp_x2, jp_y2 = jp_box
    vi_x1, vi_y1, vi_x2, vi_y2 = vi_box
    r_x = max(jp_x2, vi_x2) + 30
    l_x_vi = vi_x1 - 30
    l_x_jp = jp_x1 - 30
    y_top_jp = jp_y1 - 28
    y_bot_vi = vi_y2 + 24
    y_top_vi = vi_y1 - 28
    w_total = r_x - l_x_vi
    mid_x = (l_x_vi + r_x) / 2.0
    
    clusters = []
    
    # 4 Bottom drifting clusters
    n_bot = 4
    for i in range(n_bot):
        frac = (i + 0.5) / n_bot
        cx = l_x_vi + frac * w_total
        cy = y_bot_vi - 10 + rng.uniform(-6, 6)
        vx = (cx - mid_x) * 0.22 + rng.uniform(-10, 10)
        vy = rng.uniform(-42, -26)
        clusters.append({"cx": cx, "cy": cy, "vx": vx, "vy": vy, "r_base": rng.uniform(48, 58)})
        
    # 3 Crown drifting clusters
    w_jp = r_x - l_x_jp
    n_jp = 3
    for i in range(n_jp):
        frac = (i + 0.5) / n_jp
        cx = l_x_jp + frac * w_jp
        cy = y_top_jp + 14 + rng.uniform(-4, 4)
        vx = (cx - mid_x) * 0.26 + rng.uniform(-8, 8)
        vy = rng.uniform(-58, -38)
        clusters.append({"cx": cx, "cy": cy, "vx": vx, "vy": vy, "r_base": rng.uniform(46, 56)})
        
    puffs = []
    for c in clusters:
        puffs.append({"cx": c["cx"], "cy": c["cy"], "rx": c["r_base"], "ry": c["r_base"] * 0.75, "vx": c["vx"], "vy": c["vy"]})
        puffs.append({"cx": c["cx"] + rng.uniform(-16, 16), "cy": c["cy"] + rng.uniform(-12, 12), "rx": c["r_base"] * 0.68, "ry": c["r_base"] * 0.55, "vx": c["vx"] * 1.25, "vy": c["vy"] * 1.25})
        
    return puffs

def main():
    raw_master = MASTER.read_bytes()
    master_lines = raw_master.splitlines(keepends=True)
    
    # Read layout advances
    with open(ROOT / ".archive/ed-an2-natural-20261019/layout.json") as f:
        layout_data = json.load(f)
    vi_adv = {item["pair"]: item["advance"] for item in layout_data["layouts"] if item["language"] == "VI"}
    jp_adv = {item["pair"]: item["advance"] for item in layout_data["layouts"] if item["language"] == "JP"}
    
    # Read synchronized source lines from master
    sources_vi = []
    sources_jp = []
    for line in master_lines:
        if line.startswith(b"Comment:") and b"ED_SOURCE:" in line:
            parts = line.decode("utf-8").split(",", 9)
            if ":VI" in parts[8]:
                sources_vi.append(parts)
            elif ":JP" in parts[8]:
                sources_jp.append(parts)
                
    assert len(sources_vi) == 21 and len(sources_jp) == 21
    
    pairs_data = []
    for p in range(1, 22):
        s_vi = sources_vi[p-1]
        v_w = vi_adv[p]
        j_w = jp_adv[p]
        # Coordinates in an2 centered at 960
        vi_box = [960.0 - v_w / 2.0, 972.0, 960.0 + v_w / 2.0, 1034.0]
        jp_box = [960.0 - j_w / 2.0, 912.0, 960.0 + j_w / 2.0, 970.0]
        pairs_data.append({
            "pair": p,
            "start": s_vi[1],
            "end": s_vi[2], # synchronized with JP!
            "vi_box": vi_box,
            "jp_box": jp_box,
            "vi_text": s_vi[9].strip(),
            "jp_text": sources_jp[p-1][9].strip()
        })
        
    # Precompute standard cloud shapes for each pair
    pair_shapes = {}
    for p in pairs_data:
        idx = p["pair"]
        seed = idx * 101 + 7
        w_pts = get_standard_cloud_points(p["jp_box"], p["vi_box"], layer="white", seed=seed)
        b_pts = get_standard_cloud_points(p["jp_box"], p["vi_box"], layer="blue", seed=seed)
        pair_shapes[idx] = {
            "white_path": pts_to_ass_path(w_pts),
            "blue_path": pts_to_ass_path(b_pts),
        }
        
    # Precompute timing for continuous groups
    groups = [
        [1, 2, 3, 4, 5],
        [6, 7, 8, 9, 10],
        [11, 12, 13, 14, 15],
        [16],
        [17, 18, 19, 20, 21]
    ]
    
    pair_timing_info = {}
    for grp in groups:
        n_pairs = len(grp)
        if n_pairs == 1:
            idx = grp[0]
            p = pairs_data[idx - 1]
            pair_timing_info[idx] = {
                "cloud_start": ass_to_ms(p["start"]),
                "cloud_end": ass_to_ms(p["end"]),
                "cloud_fad": r"\fad(500,500)",
                "text_start": ass_to_ms(p["start"]),
                "text_end": ass_to_ms(p["end"]),
                "text_fad": r"\fad(500,500)",
            }
        else:
            transitions = []
            for j in range(n_pairs - 1):
                idx_a = grp[j]
                idx_b = grp[j+1]
                t_a_end = ass_to_ms(pairs_data[idx_a - 1]["end"])
                t_b_start = ass_to_ms(pairs_data[idx_b - 1]["start"])
                t_mid = int(round((t_a_end + t_b_start) / 2.0))
                transitions.append({"t_mid": t_mid})
                
            for i, p_idx in enumerate(grp):
                p = pairs_data[p_idx - 1]
                if i == 0:
                    c_s = ass_to_ms(p["start"])
                    c_e = transitions[0]["t_mid"] + 250
                    fad = r"\fad(0,500)"
                elif i == n_pairs - 1:
                    c_s = transitions[-1]["t_mid"] - 250
                    c_e = ass_to_ms(p["end"])
                    fad = r"\fad(500,0)"
                else:
                    c_s = transitions[i-1]["t_mid"] - 250
                    c_e = transitions[i]["t_mid"] + 250
                    fad = r"\fad(500,500)"
                    
                pair_timing_info[p_idx] = {
                    "cloud_start": c_s,
                    "cloud_end": c_e,
                    "cloud_fad": fad,
                    "text_start": c_s,
                    "text_end": c_e,
                    "text_fad": fad,
                }
                
    all_cloud_events = []
    
    for grp in groups:
        first_p = pairs_data[grp[0] - 1]
        last_p = pairs_data[grp[-1] - 1]
        t_grp_start = ass_to_ms(first_p["start"])
        t_grp_end = ass_to_ms(last_p["end"])
        
        # 1. Lead-in FX (Anchor-based Organic Swelling & Upward Expansion)
        # For P01: user approved footage color match (scene-color-P01), for others use organic swelling
        if grp[0] == 1:
            # P01 scene color transition
            c_s = ass_to_ms(first_p["start"])
            c_e = pair_timing_info[1]["cloud_end"]
            b_path = pair_shapes[1]["blue_path"]
            w_path = pair_shapes[1]["white_path"]
            color_tag = r"\c&HF2F2F2&\t(970,4590,\c&HD9B7A4&)\3c&HF2F2F2&\t(970,4590,\3c&HD9B7A4&)"
            all_cloud_events.append((c_s, 0, f"Dialogue: 0,{ms_to_ass(c_s)},{ms_to_ass(c_e)},ED - Cloud,scene-color-P01,0,0,0,,{{\\an7\\pos(0,0){color_tag}\\bord0\\shad0\\blur18\\1a&H35&\\p1}}{b_path}"))
            color_tag_w = r"\c&HF2F2F2&\t(970,4590,\c&HF8F2F2&)\3c&HF2F2F2&\t(970,4590,\3c&HF8F2F2&)"
            all_cloud_events.append((c_s, 1, f"Dialogue: 1,{ms_to_ass(c_s)},{ms_to_ass(c_e)},ED - Cloud,scene-color-P01,0,0,0,,{{\\an7\\pos(0,0){color_tag_w}\\bord0\\shad0\\blur10\\1a&H15&\\p1}}{w_path}"))
        else:
            nodes_in, ax, ay = get_lead_in_skeleton(first_p["jp_box"], first_p["vi_box"], seed=grp[0]*107 + 3)
            n_li = 15
            frame_dur_li = 100
            t_li_start = t_grp_start - 1500
            for f in range(n_li):
                prog = f / (n_li - 1.0)
                f_s = t_li_start + f * frame_dur_li
                f_e = t_li_start + (f + 1) * frame_dur_li
                paths = []
                for node in nodes_in:
                    d = node["delay"]
                    if prog < d:
                        continue
                    tau = (prog - d) / (1.0 - d)
                    e = 1.0 - (1.0 - tau)**2.5
                    cx = ax + (node["tx"] - ax) * e
                    cy = ay + (node["ty"] - ay) * e
                    rx = node["rx"] * (0.12 + 0.88 * e)
                    ry = node["ry"] * (0.12 + 0.88 * e)
                    if rx > 3 and ry > 3:
                        paths.append(make_puff_path(cx, cy, rx, ry))
                if paths:
                    combined_path = " ".join(paths)
                    alpha_w = int(round(0x75 - prog * (0x75 - 0x15)))
                    alpha_b = int(round(0x8A - prog * (0x8A - 0x35)))
                    blur_w = int(round(14 - prog * 4))
                    blur_b = int(round(18 - prog * 4))
                    all_cloud_events.append((f_s, 0, f"Dialogue: 0,{ms_to_ass(f_s)},{ms_to_ass(f_e)},ED - Cloud,lead-in-P{grp[0]:02},0,0,0,,{{\\an7\\pos(0,0)\\c&HE2BA95&\\3c&HE2BA95&\\bord0\\shad0\\blur{blur_b}\\1a&H{alpha_b:02X}&\\p1}}{combined_path}"))
                    all_cloud_events.append((f_s, 1, f"Dialogue: 1,{ms_to_ass(f_s)},{ms_to_ass(f_e)},ED - Cloud,lead-in-P{grp[0]:02},0,0,0,,{{\\an7\\pos(0,0)\\c&HFFFFFF&\\3c&HFFFFFF&\\bord0\\shad0\\blur{blur_w}\\1a&H{alpha_w:02X}&\\p1}}{combined_path}"))
                    
        # 2. Main Clouds for this group
        for p_idx in grp:
            if grp[0] == 1 and p_idx == 1:
                continue # already handled with scene-color-P01
            t_info = pair_timing_info[p_idx]
            c_s = t_info["cloud_start"]
            c_e = t_info["cloud_end"]
            fad_tag = t_info["cloud_fad"]
            b_path = pair_shapes[p_idx]["blue_path"]
            w_path = pair_shapes[p_idx]["white_path"]
            all_cloud_events.append((c_s, 0, f"Dialogue: 0,{ms_to_ass(c_s)},{ms_to_ass(c_e)},ED - Cloud,main-P{p_idx:02},0,0,0,,{{\\an7\\pos(0,0)\\c&HE2BA95&\\3c&HE2BA95&\\bord0\\shad0\\blur18\\1a&H35&{fad_tag}\\p1}}{b_path}"))
            all_cloud_events.append((c_s, 1, f"Dialogue: 1,{ms_to_ass(c_s)},{ms_to_ass(c_e)},ED - Cloud,main-P{p_idx:02},0,0,0,,{{\\an7\\pos(0,0)\\c&HFFFFFF&\\3c&HFFFFFF&\\bord0\\shad0\\blur10\\1a&H15&{fad_tag}\\p1}}{w_path}"))
            
        # 3. Lead-out FX (Core Evaporation & Multi-Cluster Drift Dispersion)
        puffs_out = get_lead_out_clusters(last_p["jp_box"], last_p["vi_box"], seed=grp[-1]*107 + 9)
        n_lo = 16
        frame_dur_lo = 100
        t_lo_start = t_grp_end - 250
        for f in range(n_lo):
            prog = f / (n_lo - 1.0)
            f_s = t_lo_start + f * frame_dur_lo
            f_e = t_lo_start + (f + 1) * frame_dur_lo
            paths = []
            for p_c in puffs_out:
                tau = prog
                e = tau**1.3
                cx = p_c["cx"] + p_c["vx"] * e
                cy = p_c["cy"] + p_c["vy"] * e
                rx = p_c["rx"] * max(0.04, 1.0 - 0.88 * tau)
                ry = p_c["ry"] * max(0.04, 1.0 - 0.88 * tau)
                if rx > 3 and ry > 3:
                    paths.append(make_puff_path(cx, cy, rx, ry))
            if paths:
                combined_path = " ".join(paths)
                alpha_w = int(round(0x15 + prog * (0xFA - 0x15)))
                alpha_b = int(round(0x35 + prog * (0xFA - 0x35)))
                blur_w = int(round(10 + prog * 12))
                blur_b = int(round(14 + prog * 12))
                all_cloud_events.append((f_s, 0, f"Dialogue: 0,{ms_to_ass(f_s)},{ms_to_ass(f_e)},ED - Cloud,lead-out-P{grp[-1]:02},0,0,0,,{{\\an7\\pos(0,0)\\c&HE2BA95&\\3c&HE2BA95&\\bord0\\shad0\\blur{blur_b}\\1a&H{alpha_b:02X}&\\p1}}{combined_path}"))
                all_cloud_events.append((f_s, 1, f"Dialogue: 1,{ms_to_ass(f_s)},{ms_to_ass(f_e)},ED - Cloud,lead-out-P{grp[-1]:02},0,0,0,,{{\\an7\\pos(0,0)\\c&HFFFFFF&\\3c&HFFFFFF&\\bord0\\shad0\\blur{blur_w}\\1a&H{alpha_w:02X}&\\p1}}{combined_path}"))

    all_cloud_events.sort(key=lambda x: (x[0], x[1]))
    cloud_lines = [ev[2].encode("utf-8") + b"\n" for ev in all_cloud_events]
    print(f"Generated {len(cloud_lines)} v7 organic cloud lines.")
    
    # Generate Dialogue text lines for ED - Viator (21 VI + 21 JP)
    text_lines = []
    for p in pairs_data:
        idx = p["pair"]
        t_info = pair_timing_info[idx]
        t_s = ms_to_ass(t_info["text_start"])
        t_e = ms_to_ass(t_info["text_end"])
        fad = t_info["text_fad"]
        
        # Vietnamese line
        v_lyric = re.sub(r"\{[^}]*\}", "", p["vi_text"])
        meta = ""
        m = re.match(r"^\{=\d+\}", p["vi_text"])
        if m:
            meta = m.group(0)
        if idx == 1:
            # P01 scene color transition
            v_tag = r"{\blur10\t(0,30,\blur9.978693)\t(30,60,\blur9.916627)\t(60,90,\blur9.816401)\t(90,120,\blur9.680398)\t(120,150,\blur9.510834)\t(150,180,\blur9.309785)\t(180,210,\blur9.079217)\t(210,240,\blur8.821006)\t(240,270,\blur8.536963)\t(270,300,\blur8.228847)\t(300,330,\blur7.898383)\t(330,360,\blur7.547278)\t(360,390,\blur7.177237)\t(390,420,\blur6.789977)\t(420,450,\blur6.387247)\t(450,480,\blur5.970844)\t(480,510,\blur5.542637)\t(510,540,\blur5.104597)\t(540,570,\blur4.658825)\t(570,600,\blur4.207605)\t(600,630,\blur3.753455)\t(630,660,\blur3.299225)\t(660,690,\blur2.848217)\t(690,720,\blur2.404395)\t(720,750,\blur1.972737)\t(750,780,\blur1.559897)\t(780,810,\blur1.175694)\t(810,840,\blur0.837451)\t(840,870,\blur0.6)}{\an2\pos(960,1024)\fscx139.689\fscy124.51}{\fsp0}{\shad0\c&HF2F2F2&\t(970,4590,\c&H9A4719&)\3c&HF2F2F2&\t(970,4590,\3c&H9A4719&)\ybord0.3\b0}{\bord0\xbord0\ybord0}"
        else:
            fsp_val = r"\fsp-0.5" if idx in (8, 9) else r"\fsp0"
            v_tag = rf"{{\blur0.6}}{fad}{{\an2\pos(960,1024)\fscx139.689\fscy124.51}}{{{fsp_val}}}{{\shad0\c&H9A4719&\3c&H9A4719&\ybord0.3\b0}}"
        text_lines.append(f"Dialogue: 2,{t_s},{t_e},ED - Viator,VI-P{idx:02},0,0,0,,{meta}{v_tag}{v_lyric}".encode("utf-8") + b"\n")
        
        # Japanese line
        j_lyric = re.sub(r"\{[^}]*\}", "", p["jp_text"])
        if idx == 1:
            j_tag = r"{\blur10\t(0,30,\blur9.978693)\t(30,60,\blur9.916627)\t(60,90,\blur9.816401)\t(90,120,\blur9.680398)\t(120,150,\blur9.510834)\t(150,180,\blur9.309785)\t(180,210,\blur9.079217)\t(210,240,\blur8.821006)\t(240,270,\blur8.536963)\t(270,300,\blur8.228847)\t(300,330,\blur7.898383)\t(330,360,\blur7.547278)\t(360,390,\blur7.177237)\t(390,420,\blur6.789977)\t(420,450,\blur6.387247)\t(450,480,\blur5.970844)\t(480,510,\blur5.542637)\t(510,540,\blur5.104597)\t(540,570,\blur4.658825)\t(570,600,\blur4.207605)\t(600,630,\blur3.753455)\t(630,660,\blur3.299225)\t(660,690,\blur2.848217)\t(690,720,\blur2.404395)\t(720,750,\blur1.972737)\t(750,780,\blur1.559897)\t(780,810,\blur1.175694)\t(810,840,\blur0.837451)\t(840,870,\blur0.6)}{\an2\pos(960,960)\fscx141.19\fscy118.58}{\fnNoto Serif JP ExtraLight\fs48\ko0\bord0.4\4c&H9A4719&\c&HF2F2F2&\t(970,4590,\c&H9A4719&)\3c&HF2F2F2&\t(970,4590,\3c&H9A4719&)\4a&H00&}"
        else:
            j_tag = rf"{{\blur0.6}}{fad}{{\fnNoto Serif JP ExtraLight\fs48\ko0\bord0.4\4c&H9A4719&\c&H9A4719&\3c&H9A4719&\4a&H00&}}{{\an2\pos(960,960)\fscx141.19\fscy118.58}}"
        text_lines.append(f"Dialogue: 2,{t_s},{t_e},ED - Viator,JP-P{idx:02},0,0,0,,{j_tag}{j_lyric}".encode("utf-8") + b"\n")
        
    print(f"Generated {len(text_lines)} ED - Viator text lines.")
    
    # Assemble complete independent file Maquia.vi.v7.ass
    out_lines = []
    inserted_clouds = False
    inserted_text = False
    
    for line in master_lines:
        if line.startswith(b"Dialogue:") and b",ED - Cloud," in line:
            if not inserted_clouds:
                out_lines.extend(cloud_lines)
                inserted_clouds = True
            continue
        elif line.startswith(b"Dialogue:") and b",ED - Viator," in line:
            if not inserted_text:
                out_lines.extend(text_lines)
                inserted_text = True
            continue
        out_lines.append(line)
        
    OUTPUT.write_bytes(b"".join(out_lines))
    print(f"Successfully created independent v7 file: {OUTPUT}")

if __name__ == "__main__":
    main()
