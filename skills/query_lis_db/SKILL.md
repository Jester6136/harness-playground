---
name: query_lis_db
description: Tra cứu Giấy chứng nhận quyền sử dụng đất, thửa đất, đơn đăng ký trong DB LIS (geohub_lis). Dùng khi user hỏi theo số hiệu GCN, số giấy tờ định danh chủ sở hữu, hoặc id đơn đăng ký.
---

## Khi nào dùng

Main agent delegate cho `query_lis_db` khi user hỏi về:

- **GCN**: "tra cứu GCN số ...", "thửa đất của ai", "diện tích / mục đích / tài sản trên đất của GCN ...".
- **Chủ sở hữu**: "ai là chủ thửa đất", "các GCN của người có CMND/CCCD/MST ...".
- **Đơn đăng ký**: "thông tin đơn id ...", "snapshot đơn", **"sức khoẻ" / "tình trạng" / "đầy đủ" / "thiếu" đơn đăng ký**.

KHÔNG dùng cho câu hỏi chung không có mã định danh (vd. "có bao nhiêu GCN trong hệ thống") — skill chỉ tra cứu theo định danh.

## Domain concept: "sức khoẻ" của Đơn đăng ký

Khi user dùng từ "sức khoẻ", "tình trạng", "đầy đủ", "thiếu", "khoẻ không" kèm id đơn → đây là khái niệm domain (KHÔNG phải sức khoẻ con người). Đơn được coi là **đầy đủ** khi cả 4 nhóm có ít nhất 1 phần tử: `phapNhanSdds` (chủ sở hữu), `thuaDats` (thửa đất), `daMdsdds` (mục đích sử dụng), `giayChungNhans` (GCN liên quan). Thiếu nhóm nào = đơn cần bổ sung dữ liệu nhóm đó.

## Tools

| Tool | Khi gọi |
|---|---|
| `lookup_gcn_by_so_hieu(so_hieu_gcn)` | Số hiệu GCN ("CH...", "BA...", chuỗi chữ+số) |
| `lookup_gcn_by_giay_to_dinh_danh(so_giay_to)` | Số CMND/CCCD/hộ chiếu/MST của chủ |
| `check_don_dang_ky(don_dang_ky_id)` | UUID đơn đăng ký |
| `lis_schema_doc(topic)` | Tra schema reference — **gọi trước khi diễn giải nếu chưa rõ format** |

## Quy trình

1. Xác định loại định danh user cung cấp → chọn 1 trong 3 lookup tool. Nếu mơ hồ, hỏi lại trước khi gọi.
2. Truyền nguyên văn chuỗi định danh (KHÔNG tự thêm dấu nháy, không format).
3. Tool trả `{rows, count, capped}`. Nếu `count = 0` → "không tìm thấy". Nếu `error` → báo lỗi DB.
4. **Trước khi diễn giải raw JSON cho user, gọi `lis_schema_doc(topic=<tên tool vừa gọi>)`** để load schema chính xác (lazy, chỉ load khi cần). Mỗi tool query có 1 doc reference riêng:
   - Sau `lookup_gcn_by_so_hieu(...)` → `lis_schema_doc(topic="lookup_gcn_by_so_hieu")`.
   - Sau `lookup_gcn_by_giay_to_dinh_danh(...)` → `lis_schema_doc(topic="lookup_gcn_by_giay_to_dinh_danh")`.
   - Sau `check_don_dang_ky(...)` → `lis_schema_doc(topic="check_don_dang_ky")`.
   - Khi user hỏi thuật ngữ chéo (snake↔camel) hoặc giá trị mã (loaiDoiTuong, ...) → `lis_schema_doc(topic="glossary")`.
   - Không nhớ topic nào có → `lis_schema_doc(topic="index")`.
5. Tóm tắt kết quả bằng tiếng Việt: chủ sở hữu, vị trí thửa đất, mục đích sử dụng, diện tích, tài sản. KHÔNG in raw JSON trừ khi user yêu cầu.
6. `capped = true` → nói thêm "kết quả đã giới hạn 50 dòng đầu, có thể còn thêm".

## Lưu ý an toàn

- Tham số luôn nguyên văn — psycopg tự bind an toàn (không SQL injection).
- KHÔNG ghép SQL hay tự build query — skill chỉ có 3 template cố định.
- User yêu cầu sửa/xoá → từ chối (read-only).
