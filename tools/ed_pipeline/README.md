# Hướng Dẫn Tái Tạo / Sửa Lời ED Viator Cloud FX

## Audit bổ sung và cài font — 2026-10-18

Bản hiện hành đã sửa lỗi ghép font nhúng: không được dùng regex `^\[` để tìm cuối block font, vì uuencoded có thể bắt đầu bằng `[`. Dùng `ass_attachments.py`, rồi kiểm hash toàn bộ attachment với font chuẩn. Packer đã chuyển sang bộ ghi này.

Font ED chuẩn hiện tại: `MaquiaEDCFFbacae33c`; file dự án `fonts/MaquiaEDCFFbacae33c.otf`, cài ở `/home/cuongba956/.local/share/fonts/MaquiaED/MaquiaEDCFFbacae33c.otf`. Bản cũ/trùng đã sao lưu và gỡ. Caryn Sketch, Spectral Medium và Noto Serif JP cần được cài để Aegisub preview, không dựa riêng vào Fonts trong ASS. Mỗi lần sinh font mới phải kiểm hash bản cài, gỡ/thay bản custom cũ theo phạm vi đã cho phép và cập nhật cache.

Báo cáo đầy đủ: `.archive/ed-audit-20261018/REPORT.vi.md`. Bộ kiểm hình/clock và kiểm font nhúng độc lập với font hệ thống đã được bổ sung. Dừng nếu xuất hiện tag layout/animation chưa bake được; không bỏ tag để làm file nhỏ hơn.

## Sửa lỗi bảo toàn hình và chuyển pha — 2026-10-18

Bản glyph cũ `MaquiaEDCFF4077dc1b` không còn là mốc nghiệm thu: bước font → shape đã bỏ sót `fsp-0.5`, dùng layout/kerning chưa khớp renderer và bù nét Nhật thủ công. So glyph với shape đã sai không phát hiện được lỗi này.

- `native_font_geometry.py` hiện dựng layout theo libass 0.17.1 không hinting: FreeType REAL_DIM 256 px, metrics advance tương ứng, HarfBuzz theo Kerning của thiết kế (mặc định tắt), ligature theo spacing, spacing cả ký tự cuối và embolden từ FreeType. Không dùng bù nét Nhật 0.35 px nữa.
- `cut_text_shapes.py` dùng bộ dựng này và từ chối biến đổi layout theo thời gian chưa hỗ trợ; vẫn gọt hình thật và không đưa clip chữ trở lại.
- Mức giản lược đang dùng: 0.025 px; tọa độ p5, lượng tử 1/16 px. Giữ lại ranh giới event/đồng hồ của bản font nguồn, không chạy bước gộp phase trong lần sửa này.
- Bằng chứng: `.archive/ed-motion-fix-20261018/all42-layout.json` so 42 dòng đầy đủ với chữ native trước cắt; `verification.json` kiểm đóng gói trên chuỗi chuyển pha; `scope.json` kiểm phần ngoài ED và Comment nguồn.
- Mốc kỹ thuật trước cắt vẫn là `.archive/ed-shape-cut-20261018/before.ass`; lời cho lần sửa mới luôn đọc từ Comment hiện hành trong master.

## Luồng sửa lời hiện hành — 2026-10-18

`Maquia.vi.ass` hiện có 42 dòng **Comment nguồn** gom thành một khối riêng ngay trước toàn bộ ED full FX: 21 Việt + 21 Nhật, xếp từng cặp P01 Việt–Nhật đến P21 Việt–Nhật.

- Actor: `Nguồn Việt P01` / `Nguồn Nhật P01` ... `P21`.
- Effect: `ED_SOURCE:P01:VI` / `ED_SOURCE:P01:JP`.
- Sửa trực tiếp lời trong **Text của Comment**, giữ nguyên mã Effect và trạng thái Comment.
- Những Comment này là nguồn lời hiện hành. Sửa Comment chưa tự đổi phần glyph/hiệu ứng đang hiển thị; sau đó yêu cầu dựng lại hiệu ứng theo lời mới.
- Khi dựng lại, phải đọc Comment mới trong master, không lấy lời cũ từ backup. Giữ thiết kế vị trí/màu/blur hiện tại, tính lại layout và mask theo chữ mới, sinh lại shape/glyph/font rồi kiểm ảnh trước khi thay master.

Trích nguồn mới nhất để dựng lại:

```sh
python3 tools/ed_pipeline/ed_sources.py extract Maquia.vi.ass /tmp/Maquia-ED-current-lyrics.json
```

Mapping và mẫu chữ/font editable trước chuyển glyph nằm ở:
`tools/ed_pipeline/current-source-map.json` và
`.archive/ed-shape-cut-20261018/before.ass`.
Mapping gắn từng event FX với mã nguồn, không gộp hai câu lặp khác cặp.

Các bước generator ở tài liệu cũ bên dưới mô tả những giai đoạn trước tối ưu glyph; khi dựng lại cần đối chiếu với luồng hiện hành này thay vì chạy lại nguyên chuỗi cũ.

---

Thư mục này chứa đầy đủ công cụ, đặc tả và phông chữ để sửa lời và sinh lại chính xác hiệu ứng mây (Cloud FX) cho đoạn ED phim Maquia.

---

## 1. Cấu trúc và vai trò các file

| File / Thư mục | Vai trò |
|---|---|
| `CODEX_HANDOFF.md` | Đặc tả tọa độ 21 cặp bounding box, thời gian, thông số layer mây, bezier arcs và quy chuẩn in/out. |
| `sync_continuous_text_and_clouds.py` | Script sinh mây cơ sở theo 5 cụm continuous và tính toán FBF morphing giữa các cặp câu. |
| `build_clouds.py` | Generator sinh mây v7 hoàn chỉnh trực tiếp vào file ASS. |
| `patch_first_intro.py` | Xử lý pha lead-in câu đầu (P01) mọc mây từ đáy chữ. |
| `finish_palette.py` & `adjust_blue.py` | Bảng màu chuẩn: Layer 0 viền xanh tím nhạt `&HD9B7A4&`, Layer 1 lõi trắng dịu `&HF8F2F2&`. |
| `align_ink.py` | Tự động đo nét và bù vị trí tiếng Nhật thẳng mép phải với tiếng Việt. |
| `resize_vi_and_clouds.py` | Nới rộng font Việt +2% (`fscx139.689`) và đồng bộ nới shape mây + mask. |
| `fonts/` | Chứa toàn bộ các phông chữ được dùng cho ED (Caryn, Rough, Spectral, Noto Serif JP...). |

---

## 2. Quy trình khi cần sửa lời hoặc time lại

### Bước 1: Sửa nội dung lời / timing
1. Mở [`Maquia.vi.ass`](file:///media/cuongba956/Download/One%20room/Maquia.vi.ass) trong Aegisub.
2. Lọc các dòng mang Style `ED - Viator` (21 cặp: 21 câu JP + 21 câu VI).
3. Sửa câu chữ hoặc thời gian theo ý muốn.
4. Nếu thay đổi độ dài câu lớn làm lệch bounding box:
   - Cập nhật tọa độ `jp_box` và `vi_box` trong `pairs_data` tại `CODEX_HANDOFF.md` và `sync_continuous_text_and_clouds.py`.

### Bước 2: Sinh lại hiệu ứng mây
Chạy generator từ thư mục dự án:
```bash
python3 tools/ed_pipeline/sync_continuous_text_and_clouds.py
```
Script sẽ đọc `Maquia.vi.ass`, tính toán morphing, sinh các dòng `ED - Cloud` và xuất ra `Maquia.vi.candidate.ass`.

### Bước 3: Kiểm định và cập nhật Master
1. Kiểm tra cấu trúc ASS:
```bash
python3 /home/cuongba956/.gemini/config/skills/ass-studio/scripts/ass_tools.py inspect Maquia.vi.candidate.ass
```
2. So sánh bảo toàn 5.114 dòng thoại phim:
```bash
python3 -c '
with open("Maquia.vi.ass") as f1, open("Maquia.vi.candidate.ass") as f2:
    l1 = [l for l in f1 if "ED -" not in l]
    l2 = [l for l in f2 if "ED -" not in l]
    assert l1 == l2, "Lệch dòng thoại phim!"
print("PASSED: 5114 dòng thoại gốc bảo toàn 100%.")
'
```
3. Sau khi ưng ý, chốt candidate thành master:
```bash
cp Maquia.vi.candidate.ass Maquia.vi.ass
```

### Bước 4: Cắt và đóng gói lại bản Lossless MKV
1. Sinh file phụ đề rời đã shift mốc cắt:
```bash
python3 -c '
with open("Maquia.vi.ass", "r", encoding="utf-8") as f:
    lines = f.readlines()
offset_ms = 6559386 # mốc keyframe 01:49:19.386
cut_end_ms = 6858000
def ts_to_ms(ts):
    p = ts.strip().split(":")
    return (int(p[0])*3600 + int(p[1])*60 + int(p[2].split(".")[0]))*1000 + int(p[2].split(".")[1])*10
def ms_to_ts(ms):
    cs = max(0, ms) // 10
    return f"{cs//360000}:{cs//6000%60:02}:{cs//100%60:02}.{cs%100:02}"
out = []
in_ev = False
for l in lines:
    if l.startswith("[Events]"): in_ev = True; out.append(l)
    elif not in_ev or l.startswith("Format:"): out.append(l)
    elif l.startswith(("Dialogue:", "Comment:")):
        p = l.split(",", 9)
        s, e = ts_to_ms(p[1]), ts_to_ms(p[2])
        if e <= offset_ms or s >= cut_end_ms: continue
        p[1] = ms_to_ts(s - offset_ms); p[2] = ms_to_ts(e - offset_ms)
        out.append(",".join(p))
with open("Maquia.ED.vi.ass", "w", encoding="utf-8") as f: f.writelines(out)
'
```

2. Đóng gói MKV stream copy 100% lossless:
```bash
mkvmerge -o "Maquia_ED_lossless.mkv" \
  --split parts:01:49:19.386-01:54:17.893 \
  --audio-tracks 1 \
  --video-tracks 0 \
  --no-subtitles \
  --no-attachments \
  "Maquia - When the Promised Flower Blooms [BD] [AV1] [ItachiUchiha].mkv" \
  --track-name 0:"Vietnamese ED [Master Clouds FX + Kanji]" \
  --language 0:vie \
  --default-track-flag 0:yes \
  "Maquia.ED.vi.ass" \
  --attach-file tools/ed_pipeline/fonts/0-CarynVI-MaquiaSketch.ttf \
  --attach-file tools/ed_pipeline/fonts/1-Caryn.ttf \
  --attach-file tools/ed_pipeline/fonts/3-CarynVI-Maquia.ttf \
  --attach-file tools/ed_pipeline/fonts/5-rough.ttf
```
