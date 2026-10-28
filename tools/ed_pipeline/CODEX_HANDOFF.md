# HANDOFF SPECIFICATION: ED VIATOR CLOUD FX & TEXT CONTINUITY

## 1. Project Context & File Paths
- **Workspace Dir**: `/media/cuongba956/Download/One room`
- **Master ASS**: [`Maquia.vi.ass`](file:///media/cuongba956/Download/One%20room/Maquia.vi.ass) (5502 dòng, 3632 dialogue, 5114 dòng thoại/sign giữ nguyên $100\%$)
- **Candidate ASS**: [`Maquia.vi.candidate.ass`](file:///media/cuongba956/Download/One%20room/Maquia.vi.candidate.ass)
- **Video Source**: [`Maquia - When the Promised Flower Blooms [BD] [AV1] [ItachiUchiha].mkv`](file:///media/cuongba956/Download/One%20room/Maquia%20-%20When%20the%20Promised%20Flower%20Blooms%20%5BBD%5D%20%5BAV1%5D%20%5BItachiUchiha%5D.mkv) (1920x1080, AV1)
- **Primary Generator Script**: [`sync_continuous_text_and_clouds.py`](file:///media/cuongba956/Download/One%20room/sync_continuous_text_and_clouds.py)
- **Verification Tooling**:
  - `python3 /home/cuongba956/.gemini/config/skills/ass-studio/scripts/ass_tools.py inspect <file.ass>`
  - `python3 /home/cuongba956/.gemini/config/skills/ass-studio/scripts/libass_render.py`

---

## 2. Hard Requirements & Invariants
1. **Bảo toàn dữ liệu**:
   - 5114 dòng thoại phim, biển hiệu (Sign-CưongwtBas), attachment font và extradata (`{=7}` trên P21) tuyệt đối không được sai lệch dù 1 byte.
   - Chỉ được can thiệp đúng 2 style: `ED - Viator` (42 dòng: 21 JP + 21 VI) và `ED - Cloud`.
2. **Khắc phục triệt để lỗi nhảy text (libass collision avoidance)**:
   - Tất cả dòng `ED - Viator` căn lề `\an3` bắt buộc có `\pos` tường minh:
     - VI: `\pos(1860,1040)`
     - JP (P08, P09): `\pos(1860,980)`
     - JP (các câu khác): `\pos(1860,976)`
3. **Phân nhóm liên tục (5 tự nhiên theo bài hát)**:
   - **Group 1**: P01 $\to$ P05 (Continuous)
   - **Group 2**: P06 $\to$ P10 (Continuous)
   - **Group 3**: P11 $\to$ P15 (Continuous)
   - **Group 4**: P16 (Đơn lẻ, có cả Lead-in và Lead-out)
   - **Group 5**: P17 $\to$ P21 (Continuous)

---

## 3. Data Specification: 21 Pairs Bounding Boxes & Timing
Tọa độ bounding box gốc `[x1, y1, x2, y2]` (native 1920x1080):

```python
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
```

---

## 4. Current State & User Expectations

### A. Chuyển line liên tục (Continuous Cross-Morphing) — ĐÃ DUYỆT
- Giữa 2 câu liên tiếp (ví dụ P01 $\to$ P02, P02 $\to$ P03):
  - Tìm trung điểm chuyển tiếp: $t_{mid} = \text{round}((t_{end\_A} + t_{start\_B}) / 2)$.
  - Cửa sổ chồng lấn 500ms: $[t_{mid} - 250\text{ms}, t_{mid} + 250\text{ms}]$.
  - Cả text và shape mây đều cross-fade $\pm 250\text{ms}$ đồng bộ tại chỗ. Không đổi phần này.

### B. Vấn đề cốt lõi cần giải quyết: Lead-In và Lead-Out
User phản hồi gắt gao:
> *"vấn đề về kích thước khi in và out, các đám mây cũng đéo còn là mây nhỏ dần thành mây lớn nữa là sao"*
> *"chỉ 1 vài cụm mây nhỏ to dần xong thì shape mây to gốc vẫn fade in. tôi cần thực sự các mảng mây hình thành lên mây lớn. thậm chí bản chắp vá kia còn quá thưa thớt mây nhỏ nữa, chả giống như nó hình thành đám mây lớn"*

#### 1. Yêu cầu Visual Lead-In (Dòng đầu mỗi nhóm: P01, P06, P11, P16, P17)
- **Kích thước bắt đầu**: Bắt buộc phải **NHỎ** (compact, chỉ $\sim 100-150\text{px}$ bề ngang ở đáy chữ), tuyệt đối không được rải điểm phủ kín toàn màn hình ngay từ frame đầu tiên.
- **Quy trình hình thành**:
  - Xuất phát từ đáy chữ (anchor point ở đáy dòng tiếng Việt).
  - Các quầng mây nhỏ sôi bốc lên, phình to kích thước ($R$ nở dần).
  - Lan tỏa dần sang trái và lên trên theo chiều đọc của chữ.
  - Các cụm mây nhỏ liên kết dày đặc, bồi đắp và hợp thành khối mây lớn hoàn chỉnh ôm trọn 2 dòng chữ.
- **Handoff sang Main Cloud**: Khi mây đã hình thành $100\%$, khớp liền mạch vào shape mây chính, không để lộ hiện tượng shape to fade in song song độc lập.
- **Thời lượng**: Khoảng $1200\text{ms} - 1500\text{ms}$ trước khi câu hát bắt đầu.

#### 2. Yêu cầu Visual Lead-Out (Dòng cuối mỗi nhóm: P05, P10, P15, P16, P21)
- **Quy trình tan rã**:
  - Không được giữ nguyên shape mây lớn to đùng rồi chỉ giảm alpha $\to 0$.
  - Khối mây lớn phải nứt vỡ ở phần lõi (core).
  - Rã thành 6 - 8 quầng mây nhỏ riêng biệt (cloudlet clusters).
  - Các quầng mây nhỏ này trôi tản về các hướng (lên trên vào không trung, dạt sang hai bên).
  - Vừa trôi vừa teo nhỏ bán kính ($R \to 0$), blur tăng dần, bốc hơi hoàn toàn vào nền trời.
- **Thời lượng**: Kéo dài khoảng $1400\text{ms} - 1600\text{ms}$ sau khi câu hát kết thúc.

---

## 5. Cloud Layering & Visual Specs
Mây gồm 2 layer vẽ vector `\p1`:
1. **Layer 0 (Lớp viền/bóng xanh)**:
   - Màu: `\c&HE2BA95&\3c&HE2BA95&`
   - Blur: `\blur18` (tĩnh), tăng lên `\blur26` khi tan biến.
   - Alpha: `\1a&H35&` (khoảng 80% opacity), tăng lên `\1a&HFA&` khi tan.
2. **Layer 1 (Lớp lõi trắng)**:
   - Màu: `\c&HFFFFFF&\3c&HFFFFFF&`
   - Blur: `\blur10` (tĩnh), tăng lên `\blur22` khi tan biến.
   - Alpha: `\1a&H15&` (khoảng 92% opacity), tăng lên `\1a&HFA&` khi tan.

---

## 6. Verification Steps for Codex
Mỗi khi sinh file `Maquia.vi.candidate.ass`, Codex cần chạy kiểm định:

```bash
# 1. Chạy inspect kiểm tra cấu trúc và cảnh báo ASS
python3 /home/cuongba956/config/skills/ass-studio/scripts/ass_tools.py inspect "/media/cuongba956/Download/One room/Maquia.vi.candidate.ass"
# Bắt buộc: "warnings": [], "undefined_styles": []

# 2. Kiểm tra không làm lệch các dòng thoại khác
python3 -c '
with open("/media/cuongba956/Download/One room/Maquia.vi.ass") as f1, open("/media/cuongba956/Download/One room/Maquia.vi.candidate.ass") as f2:
    l1 = [l for l in f1 if "ED -" not in l]
    l2 = [l for l in f2 if "ED -" not in l]
    assert l1 == l2, "Lệch dòng thoại phim!"
print("PASSED: 5114 non-ED lines strictly preserved.")
'

# 3. Render frame đối chứng bằng libass
python3 -c '
import sys
sys.path.append("/home/cuongba956/.gemini/config/skills/ass-studio/scripts")
import libass_render
r = libass_render.Renderer((1920, 1080), (1920, 1080), ["/media/cuongba956/Download/One room"])
with open("/media/cuongba956/Download/One room/Maquia.vi.candidate.ass", "rb") as f:
    r.load(f.read())
head, _ = r.render(6586300) # Kiểm tra frame lead-in
r.png(head, "/media/cuongba956/Download/One room/test_codex_render.png")
r.close()
'
```
