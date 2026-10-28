import math
import numpy as np
import sys
import os
import re

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

def get_standard_cloud_points(jp_box, vi_box, layer='white', seed=42):
    rng = np.random.RandomState(seed)
    jp_x1, jp_y1, jp_x2, jp_y2 = jp_box
    vi_x1, vi_y1, vi_x2, vi_y2 = vi_box
    
    if layer == 'blue':
        M_top, M_bot, M_left, M_right = 34, 32, 38, 38
    else:
        M_top, M_bot, M_left, M_right = 26, 22, 28, 28

    r_x = min(1908, max(jp_x2, vi_x2) + M_right)
    y_top_jp = jp_y1 - M_top
    y_bot_vi = vi_y2 + M_bot
    
    l_x_vi = vi_x1 - M_left
    y_top_vi = vi_y1 - M_top
    l_x_jp = jp_x1 - M_left
    
    segments = []
    
    # 1. Right side (2 segments)
    p_tr = (r_x - 12, y_top_jp)
    p_r_mid = (r_x + 6, (y_top_jp * 0.4 + y_bot_vi * 0.6))
    p_br = (r_x - 16, y_bot_vi)
    segments.append((p_tr, p_r_mid, (0.8, -0.5), 16 if layer=='white' else 20))
    segments.append((p_r_mid, p_br, (0.7, 0.7), 12 if layer=='white' else 16))
    
    # 2. Bottom base (3 segments)
    bot_pts = []
    for i in range(4):
        t = i / 3.0
        bx = (r_x - 16) * (1 - t) + (l_x_vi + 20) * t
        by = y_bot_vi + math.sin(t * math.pi * 2.5) * 3.0 + rng.uniform(-1.0, 1.0)
        bot_pts.append((bx, by))
    for i in range(3):
        b_val = rng.uniform(4, 7) if layer=='white' else rng.uniform(7, 11)
        segments.append((bot_pts[i], bot_pts[i+1], (0.0, 1.0), b_val))
        
    # 3. Left nose of VI (2 segments)
    p_bl = (l_x_vi + 20, y_bot_vi)
    p_l_vi_mid = (l_x_vi - 6, (y_bot_vi + y_top_vi)/2.0)
    p_tl_vi = (l_x_vi + 18, y_top_vi)
    segments.append((p_bl, p_l_vi_mid, (-0.8, 0.6), 14 if layer=='white' else 18))
    segments.append((p_l_vi_mid, p_tl_vi, (-0.8, -0.6), 16 if layer=='white' else 20))
    
    # 4. VI top ridge (2 segments)
    w_vi = (l_x_jp - 15) - (l_x_vi + 18)
    p_v_mid = (l_x_vi + 18 + w_vi * 0.55, y_top_vi + rng.uniform(-1.5, 1.5))
    p_v_end = (l_x_jp - 15, y_top_vi)
    segments.append(((l_x_vi + 18, y_top_vi), p_v_mid, (0.0, -1.0), rng.uniform(14, 18) if layer=='white' else rng.uniform(11, 14)))
    segments.append((p_v_mid, p_v_end, (0.0, -1.0), rng.uniform(12, 16) if layer=='white' else rng.uniform(9, 12)))
    
    # 5. Step transition (2 segments)
    p_step_0 = (l_x_jp - 15, y_top_vi)
    p_step_mid = (l_x_jp - 4, (y_top_vi * 0.45 + y_top_jp * 0.55))
    p_step_1 = (l_x_jp + 22, y_top_jp)
    segments.append((p_step_0, p_step_mid, (-0.75, -0.65), 14 if layer=='white' else 17))
    segments.append((p_step_mid, p_step_1, (-0.45, -0.9), 16 if layer=='white' else 19))
    
    # 6. JP top ridge (3 segments)
    jp_top_w = (r_x - 12) - (l_x_jp + 22)
    p1 = (l_x_jp + 22 + jp_top_w * 0.28, y_top_jp + rng.uniform(-1.5, 1.5))
    p2 = (l_x_jp + 22 + jp_top_w * 0.72, y_top_jp + rng.uniform(-2, 1))
    p3 = (r_x - 12, y_top_jp)
    segments.append(((l_x_jp + 22, y_top_jp), p1, (0.0, -1.0), rng.uniform(14, 18) if layer=='white' else rng.uniform(11, 14)))
    segments.append((p1, p2, (0.0, -1.0), rng.uniform(20, 26) if layer=='white' else rng.uniform(15, 19)))
    segments.append((p2, p3, (0.0, -1.0), rng.uniform(14, 18) if layer=='white' else rng.uniform(11, 14)))
    
    pts_list = [segments[0][0]]
    for seg in segments:
        p0, p1, normal, bulge = seg
        c = bezier_arc(p0, p1, bulge, normal)
        pts_list.append((c[0], c[1]))
        pts_list.append((c[2], c[3]))
        pts_list.append((c[4], c[5]))
        
    return pts_list

def pts_to_ass_path(pts_list):
    cmds = [f"m {int(round(pts_list[0][0]))} {int(round(pts_list[0][1]))}"]
    for i in range(1, len(pts_list), 3):
        c1 = pts_list[i]
        c2 = pts_list[i+1]
        p_end = pts_list[i+2]
        cmds.append(f"b {int(round(c1[0]))} {int(round(c1[1]))} {int(round(c2[0]))} {int(round(c2[1]))} {int(round(p_end[0]))} {int(round(p_end[1]))}")
    return " ".join(cmds)

def ass_to_ms(t_str):
    h, m, s = t_str.split(':')
    return int(round((int(h)*3600 + int(m)*60 + float(s))*1000))

def ms_to_ass(ms):
    th = ms // 3600000
    ms %= 3600000
    tm = ms // 60000
    ms %= 60000
    ts = ms / 1000.0
    return f"{th}:{tm:02d}:{ts:05.2f}"

def make_puff_path(cx, cy, rx, ry):
    kx = rx * 0.55228475
    ky = ry * 0.55228475
    p = []
    p.append(f"m {int(round(cx - rx))} {int(round(cy))}")
    p.append(f"b {int(round(cx - rx))} {int(round(cy - ky))} {int(round(cx - kx))} {int(round(cy - ry))} {int(round(cx))} {int(round(cy - ry))}")
    p.append(f"b {int(round(cx + kx))} {int(round(cy - ry))} {int(round(cx + rx))} {int(round(cy - ky))} {int(round(cx + rx))} {int(round(cy))}")
    p.append(f"b {int(round(cx + rx))} {int(round(cy + ky))} {int(round(cx + kx))} {int(round(cy + ry))} {int(round(cx))} {int(round(cy + ry))}")
    p.append(f"b {int(round(cx - kx))} {int(round(cy + ry))} {int(round(cx - rx))} {int(round(cy + ky))} {int(round(cx - rx))} {int(round(cy))}")
    return " ".join(p)

def get_lead_in_skeleton(jp_box, vi_box, seed=42):
    rng = np.random.RandomState(seed)
    jp_x1, jp_y1, jp_x2, jp_y2 = jp_box
    vi_x1, vi_y1, vi_x2, vi_y2 = vi_box
    r_x = max(jp_x2, vi_x2) + 28
    l_x_vi = vi_x1 - 28
    l_x_jp = jp_x1 - 28
    y_top_jp = jp_y1 - 26
    y_bot_vi = vi_y2 + 22
    y_top_vi = vi_y1 - 26
    w_total = r_x - l_x_vi
    
    anchor_x = l_x_vi + w_total * 0.70
    anchor_y = y_bot_vi + 12.0
    nodes = []
    
    # 1. Bottom nodes (spread outwards from anchor along bottom edge)
    n_bot = max(6, int(round(w_total / 55.0)))
    for i in range(n_bot):
        frac = (i + 0.5) / n_bot
        tx = l_x_vi + frac * w_total
        ty = y_bot_vi - 10 + rng.uniform(-4, 4)
        rx = rng.uniform(62, 78)
        ry = rng.uniform(42, 54)
        delay = abs(frac - 0.70) * 0.42
        nodes.append({"tx": tx, "ty": ty, "rx": rx, "ry": ry, "delay": delay})
        
    # 2. Core inner nodes (bubbling upward into space between VI & JP)
    n_core = max(5, int(round(w_total / 65.0)))
    for i in range(n_core):
        frac = (i + 0.5) / n_core
        tx = l_x_vi + frac * w_total
        ty = (y_top_vi + y_bot_vi) / 2.0 + rng.uniform(-5, 5)
        rx = rng.uniform(70, 88)
        ry = rng.uniform(46, 60)
        delay = 0.15 + abs(frac - 0.70) * 0.38
        nodes.append({"tx": tx, "ty": ty, "rx": rx, "ry": ry, "delay": delay})
        
    # 3. VI top ridge
    w_vi = max(30, l_x_jp - l_x_vi)
    n_vi = max(2, int(round(w_vi / 50.0)))
    for i in range(n_vi):
        frac = (i + 0.5) / n_vi
        tx = l_x_vi + frac * w_vi
        ty = y_top_vi + 8 + rng.uniform(-4, 4)
        rx = rng.uniform(55, 72)
        ry = rng.uniform(36, 48)
        delay = 0.25 + (1.0 - frac) * 0.32
        nodes.append({"tx": tx, "ty": ty, "rx": rx, "ry": ry, "delay": delay})
        
    # 4. JP top ridge
    w_jp = r_x - l_x_jp
    n_jp = max(3, int(round(w_jp / 50.0)))
    for i in range(n_jp):
        frac = (i + 0.5) / n_jp
        tx = l_x_jp + frac * w_jp
        ty = y_top_jp + 10 + rng.uniform(-4, 4)
        rx = rng.uniform(58, 76)
        ry = rng.uniform(38, 50)
        delay = 0.22 + frac * 0.28
        nodes.append({"tx": tx, "ty": ty, "rx": rx, "ry": ry, "delay": delay})
        
    # 5. Outer caps
    nodes.append({"tx": l_x_vi + 12, "ty": (y_top_vi + y_bot_vi)/2.0, "rx": 58, "ry": 48, "delay": 0.48})
    nodes.append({"tx": r_x - 10, "ty": (y_top_jp + y_bot_vi)/2.0, "rx": 64, "ry": 52, "delay": 0.25})
    
    return nodes, anchor_x, anchor_y

def get_lead_out_clusters(jp_box, vi_box, seed=42):
    rng = np.random.RandomState(seed)
    jp_x1, jp_y1, jp_x2, jp_y2 = jp_box
    vi_x1, vi_y1, vi_x2, vi_y2 = vi_box
    r_x = max(jp_x2, vi_x2) + 28
    l_x_vi = vi_x1 - 28
    l_x_jp = jp_x1 - 28
    y_top_jp = jp_y1 - 26
    y_bot_vi = vi_y2 + 22
    y_top_vi = vi_y1 - 26
    w_total = r_x - l_x_vi
    mid_x = (l_x_vi + r_x) / 2.0
    
    # Bottom clusters
    n_bot = max(3, int(round(w_total / 180.0)))
    clusters = []
    for i in range(n_bot):
        frac = (i + 0.5) / n_bot
        cx = l_x_vi + frac * w_total
        cy = y_bot_vi - 10 + rng.uniform(-6, 6)
        vx = (cx - mid_x) * 0.20 + rng.uniform(-10, 10)
        vy = rng.uniform(-40, -25)
        clusters.append({"cx": cx, "cy": cy, "vx": vx, "vy": vy, "r_base": rng.uniform(46, 56)})
        
    # VI top ridge
    w_vi = max(30, l_x_jp - l_x_vi)
    n_vi = max(1, int(round(w_vi / 180.0)))
    for i in range(n_vi):
        frac = (i + 0.5) / n_vi
        cx = l_x_vi + frac * w_vi
        cy = y_top_vi + 16 + rng.uniform(-4, 4)
        vx = (cx - mid_x) * 0.24 - 15.0
        vy = rng.uniform(-50, -32)
        clusters.append({"cx": cx, "cy": cy, "vx": vx, "vy": vy, "r_base": rng.uniform(44, 52)})
        
    # JP top ridge
    w_jp = r_x - l_x_jp
    n_jp = max(2, int(round(w_jp / 160.0)))
    for i in range(n_jp):
        frac = (i + 0.5) / n_jp
        cx = l_x_jp + frac * w_jp
        cy = y_top_jp + 14 + rng.uniform(-4, 4)
        vx = (cx - mid_x) * 0.24 + 10.0
        vy = rng.uniform(-60, -40)
        clusters.append({"cx": cx, "cy": cy, "vx": vx, "vy": vy, "r_base": rng.uniform(44, 54)})
        
    puffs = []
    for c in clusters:
        # Primary puff
        puffs.append({"cx": c["cx"], "cy": c["cy"], "rx": c["r_base"], "ry": c["r_base"] * 0.75, "vx": c["vx"], "vy": c["vy"]})
        # Satellite puff
        puffs.append({"cx": c["cx"] + rng.uniform(-15, 15), "cy": c["cy"] + rng.uniform(-10, 10), "rx": c["r_base"] * 0.70, "ry": c["r_base"] * 0.55, "vx": c["vx"] * 1.2, "vy": c["vy"] * 1.2})
        
    return puffs

pairs_data = [
  {"pair": 1, "start": "1:49:47.31", "end": "1:49:54.03", "jp_box": [1534, 931, 1869, 981], "vi_box": [1446, 987, 1868, 1037]},
  {"pair": 2, "start": "1:49:54.86", "end": "1:50:01.49", "jp_box": [1583, 930, 1864, 981], "vi_box": [1433, 984, 1866, 1037]},
  {"pair": 3, "start": "1:50:01.91", "end": "1:50:09.46", "jp_box": [1441, 930, 1864, 982], "vi_box": [1235, 987, 1869, 1045]},
  {"pair": 4, "start": "1:50:09.46", "end": "1:50:13.17", "jp_box": [1625, 930, 1857, 980], "vi_box": [1393, 986, 1869, 1037]},
  {"pair": 5, "start": "1:50:13.17", "end": "1:50:22.01", "jp_box": [1578, 930, 1863, 980], "vi_box": [1056, 984, 1863, 1037]},
  {"pair": 6, "start": "1:50:44.24", "end": "1:50:53.17", "jp_box": [1390, 930, 1864, 980], "vi_box": [945, 986, 1869, 1037]},
  {"pair": 7, "start": "1:50:53.17", "end": "1:50:59.22", "jp_box": [1578, 930, 1866, 982], "vi_box": [1265, 986, 1870, 1045]},
  {"pair": 8, "start": "1:50:59.22", "end": "1:51:04.43", "jp_box": [1672, 934, 1868, 986], "vi_box": [1433, 987, 1871, 1039]},
  {"pair": 9, "start": "1:51:04.43", "end": "1:51:09.64", "jp_box": [1586, 935, 1869, 985], "vi_box": [1296, 987, 1871, 1041]},
  {"pair": 10, "start": "1:51:10.06", "end": "1:51:21.61", "jp_box": [1343, 930, 1854, 982], "vi_box": [1292, 986, 1869, 1038]},
  {"pair": 11, "start": "1:51:34.92", "end": "1:51:42.47", "jp_box": [1534, 931, 1866, 982], "vi_box": [1422, 987, 1868, 1037]},
  {"pair": 12, "start": "1:51:42.47", "end": "1:51:49.47", "jp_box": [1625, 930, 1866, 981], "vi_box": [1475, 987, 1863, 1038]},
  {"pair": 13, "start": "1:51:49.47", "end": "1:51:57.02", "jp_box": [1394, 930, 1866, 981], "vi_box": [1042, 986, 1869, 1038]},
  {"pair": 14, "start": "1:51:57.02", "end": "1:52:00.78", "jp_box": [1578, 931, 1868, 982], "vi_box": [1393, 984, 1869, 1037]},
  {"pair": 15, "start": "1:52:00.78", "end": "1:52:09.33", "jp_box": [1491, 930, 1864, 980], "vi_box": [1190, 986, 1871, 1038]},
  {"pair": 16, "start": "1:52:42.69", "end": "1:52:58.33", "jp_box": [1252, 930, 1856, 982], "vi_box": [970, 986, 1871, 1038]},
  {"pair": 17, "start": "1:53:01.67", "end": "1:53:10.56", "jp_box": [1390, 930, 1864, 982], "vi_box": [1072, 986, 1866, 1037]},
  {"pair": 18, "start": "1:53:10.56", "end": "1:53:16.73", "jp_box": [1672, 930, 1862, 978], "vi_box": [1286, 986, 1868, 1037]},
  {"pair": 19, "start": "1:53:16.73", "end": "1:53:21.86", "jp_box": [1719, 930, 1862, 978], "vi_box": [1578, 981, 1870, 1037]},
  {"pair": 20, "start": "1:53:21.86", "end": "1:53:27.49", "jp_box": [1539, 930, 1869, 981], "vi_box": [1298, 984, 1868, 1037]},
  {"pair": 21, "start": "1:53:27.49", "end": "1:53:39.33", "jp_box": [1343, 930, 1854, 982], "vi_box": [1292, 986, 1869, 1038]}
]

# Precompute standard cloud shapes for each pair
pair_shapes = {}
for p in pairs_data:
    idx = p["pair"]
    seed = idx * 101 + 7
    w_pts = get_standard_cloud_points(p["jp_box"], p["vi_box"], layer='white', seed=seed)
    b_pts = get_standard_cloud_points(p["jp_box"], p["vi_box"], layer='blue', seed=seed)
    pair_shapes[idx] = {
        'white_path': pts_to_ass_path(w_pts),
        'blue_path': pts_to_ass_path(b_pts),
    }

# 5 Natural Song Verses
groups = [
    [1, 2, 3, 4, 5],
    [6, 7, 8, 9, 10],
    [11, 12, 13, 14, 15],
    [16],
    [17, 18, 19, 20, 21]
]

# Compute timing and fade tags for each pair (synchronized for text and clouds)
pair_timing_info = {}

for grp in groups:
    n_pairs = len(grp)
    first_p = pairs_data[grp[0] - 1]
    last_p = pairs_data[grp[-1] - 1]
    t_grp_start = ass_to_ms(first_p['start'])
    t_grp_end = ass_to_ms(last_p['end'])
    
    if n_pairs == 1:
        p_idx = grp[0]
        pair_timing_info[p_idx] = {
            'text_start': t_grp_start,
            'text_end': t_grp_end,
            'cloud_start': t_grp_start - 250,
            'cloud_end': t_grp_end,
            'f_in': 'orig',
            'f_out': 'orig',
            'cloud_fad': '\\fad(250,250)'
        }
    else:
        transitions = []
        for j in range(n_pairs - 1):
            idx_a = grp[j]
            idx_b = grp[j+1]
            p_a = pairs_data[idx_a - 1]
            p_b = pairs_data[idx_b - 1]
            t_a_end = ass_to_ms(p_a['end'])
            t_b_start = ass_to_ms(p_b['start'])
            gap = t_b_start - t_a_end
            
            t_mid = t_a_end if gap <= 0 else int(round((t_a_end + t_b_start) / 2.0))
            half_w = 250
            transitions.append({
                'idx_a': idx_a,
                'idx_b': idx_b,
                't_mid': t_mid,
                'half_w': half_w,
            })
            
        for i, p_idx in enumerate(grp):
            if i == 0:
                t_s = t_grp_start
                f_in = 'orig'
                t_e = transitions[0]['t_mid'] + transitions[0]['half_w']
                f_out = 500
                c_s = t_grp_start - 250
                c_e = t_e
                c_fad = '\\fad(250,500)'
            elif i == n_pairs - 1:
                t_s = transitions[-1]['t_mid'] - transitions[-1]['half_w']
                f_in = 500
                t_e = t_grp_end
                f_out = 'orig'
                c_s = t_s
                c_e = t_grp_end
                c_fad = '\\fad(500,250)'
            else:
                t_s = transitions[i-1]['t_mid'] - transitions[i-1]['half_w']
                f_in = 500
                t_e = transitions[i]['t_mid'] + transitions[i]['half_w']
                f_out = 500
                c_s = t_s
                c_e = t_e
                c_fad = '\\fad(500,500)'
                
            pair_timing_info[p_idx] = {
                'text_start': t_s,
                'text_end': t_e,
                'cloud_start': c_s,
                'cloud_end': c_e,
                'f_in': f_in,
                'f_out': f_out,
                'cloud_fad': c_fad
            }

all_cloud_events = []

for grp in groups:
    first_p = pairs_data[grp[0] - 1]
    last_p = pairs_data[grp[-1] - 1]
    t_grp_start = ass_to_ms(first_p['start'])
    t_grp_end = ass_to_ms(last_p['end'])
    
    # 1. Lead-in FX (Anchor-based Organic Swelling & Upward Expansion)
    nodes_in, ax, ay = get_lead_in_skeleton(first_p['jp_box'], first_p['vi_box'], seed=grp[0]*107 + 3)
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
                
        if not paths:
            continue
            
        combined_path = " ".join(paths)
        alpha_w = int(round(0x75 - prog * (0x75 - 0x15)))
        alpha_b = int(round(0x8A - prog * (0x8A - 0x35)))
        blur_w = int(round(14 - prog * 4))
        blur_b = int(round(18 - prog * 4))
        
        all_cloud_events.append((f_s, 0, f"Dialogue: 0,{ms_to_ass(f_s)},{ms_to_ass(f_e)},ED - Cloud,,0,0,0,,{{\\an7\\pos(0,0)\\c&HE2BA95&\\3c&HE2BA95&\\bord0\\shad0\\blur{blur_b}\\1a&H{alpha_b:02X}&\\p1}}{combined_path}"))
        all_cloud_events.append((f_s, 1, f"Dialogue: 1,{ms_to_ass(f_s)},{ms_to_ass(f_e)},ED - Cloud,,0,0,0,,{{\\an7\\pos(0,0)\\c&HFFFFFF&\\3c&HFFFFFF&\\bord0\\shad0\\blur{blur_w}\\1a&H{alpha_w:02X}&\\p1}}{combined_path}"))
        
    # 2. Main Clouds
    for p_idx in grp:
        t_info = pair_timing_info[p_idx]
        c_s = t_info['cloud_start']
        c_e = t_info['cloud_end']
        fad_tag = t_info['cloud_fad']
        b_path = pair_shapes[p_idx]['blue_path']
        w_path = pair_shapes[p_idx]['white_path']
        all_cloud_events.append((c_s, 0, f"Dialogue: 0,{ms_to_ass(c_s)},{ms_to_ass(c_e)},ED - Cloud,,0,0,0,,{{\\an7\\pos(0,0)\\c&HE2BA95&\\3c&HE2BA95&\\bord0\\shad0\\blur18\\1a&H35&{fad_tag}\\p1}}{b_path}"))
        all_cloud_events.append((c_s, 1, f"Dialogue: 1,{ms_to_ass(c_s)},{ms_to_ass(c_e)},ED - Cloud,,0,0,0,,{{\\an7\\pos(0,0)\\c&HFFFFFF&\\3c&HFFFFFF&\\bord0\\shad0\\blur10\\1a&H15&{fad_tag}\\p1}}{w_path}"))
        
    # 3. Lead-out FX (Core Evaporation & Multi-Cluster Drift Dispersion)
    puffs_out = get_lead_out_clusters(last_p['jp_box'], last_p['vi_box'], seed=grp[-1]*107 + 9)
    n_lo = 16
    frame_dur_lo = 100
    t_lo_start = t_grp_end - 250
    for f in range(n_lo):
        prog = f / (n_lo - 1.0)
        f_s = t_lo_start + f * frame_dur_lo
        f_e = t_lo_start + (f + 1) * frame_dur_lo
        
        paths = []
        for p in puffs_out:
            tau = prog
            e = tau**1.3
            cx = p["cx"] + p["vx"] * e
            cy = p["cy"] + p["vy"] * e
            rx = p["rx"] * max(0.04, 1.0 - 0.88 * tau)
            ry = p["ry"] * max(0.04, 1.0 - 0.88 * tau)
            if rx > 3 and ry > 3:
                paths.append(make_puff_path(cx, cy, rx, ry))
                
        if not paths:
            continue
            
        combined_path = " ".join(paths)
        alpha_w = int(round(0x15 + prog * (0xFA - 0x15)))
        alpha_b = int(round(0x35 + prog * (0xFA - 0x35)))
        blur_w = int(round(10 + prog * 12))
        blur_b = int(round(14 + prog * 12))
        
        all_cloud_events.append((f_s, 0, f"Dialogue: 0,{ms_to_ass(f_s)},{ms_to_ass(f_e)},ED - Cloud,,0,0,0,,{{\\an7\\pos(0,0)\\c&HE2BA95&\\3c&HE2BA95&\\bord0\\shad0\\blur{blur_b}\\1a&H{alpha_b:02X}&\\p1}}{combined_path}"))
        all_cloud_events.append((f_s, 1, f"Dialogue: 1,{ms_to_ass(f_s)},{ms_to_ass(f_e)},ED - Cloud,,0,0,0,,{{\\an7\\pos(0,0)\\c&HFFFFFF&\\3c&HFFFFFF&\\bord0\\shad0\\blur{blur_w}\\1a&H{alpha_w:02X}&\\p1}}{combined_path}"))

# Sort cloud events
all_cloud_events.sort(key=lambda x: (x[0], x[1]))
cloud_lines = [ev[2] + "\n" for ev in all_cloud_events]

# Update Text Lines for ED - Viator
master_file = "/media/cuongba956/Download/One room/Maquia.vi.ass"
candidate_file = "/media/cuongba956/Download/One room/Maquia.vi.candidate.ass"

with open(master_file, "r", encoding="utf-8") as f:
    master_lines = f.readlines()

def update_viator_line(line, p_idx):
    t_info = pair_timing_info[p_idx]
    parts = line.split(',', 9)
    parts[1] = ms_to_ass(t_info['text_start'])
    parts[2] = ms_to_ass(t_info['text_end'])
    
    txt = parts[9]
    m = re.search(r'\\fad\((\d+),(\d+)\)', txt)
    if m:
        orig_in, orig_out = m.group(1), m.group(2)
        f_in = orig_in if t_info['f_in'] == 'orig' else str(t_info['f_in'])
        f_out = orig_out if t_info['f_out'] == 'orig' else str(t_info['f_out'])
        new_fad = f"\\fad({f_in},{f_out})"
        parts[9] = txt[:m.start()] + new_fad + txt[m.end():]

    # Ensure explicit \pos to prevent libass collision avoidance jumping during continuous transitions
    is_jp = 'Noto Serif JP' in parts[9]
    if is_jp:
        jp_y = 980 if p_idx in [8, 9] else 976
        pos_tag = f"\\pos(1860,{jp_y})"
    else:
        pos_tag = "\\pos(1860,1040)"
        
    if '\\pos(' not in parts[9]:
        parts[9] = parts[9].replace('\\an3', f'\\an3{pos_tag}')
        
    return ','.join(parts)

new_lines = []
inserted_clouds = False
viator_counter = 0

for line in master_lines:
    if line.startswith("Dialogue:") and "ED - Cloud" in line:
        if not inserted_clouds:
            new_lines.extend(cloud_lines)
            inserted_clouds = True
        continue
    elif line.startswith("Dialogue:") and "ED - Viator" in line:
        p_idx = (viator_counter % 21) + 1
        updated_l = update_viator_line(line, p_idx)
        new_lines.append(updated_l)
        viator_counter += 1
    else:
        new_lines.append(line)

with open(candidate_file, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print(f"Updated {viator_counter} Viator text lines.")
print(f"Generated {len(cloud_lines)} cloud lines.")
print(f"Successfully generated {candidate_file}")
