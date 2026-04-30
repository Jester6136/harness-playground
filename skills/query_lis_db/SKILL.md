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

| Tool | Khi gọi | Output |
|---|---|---|
| `lookup_gcn_by_so_hieu(so_hieu_gcn)` | Số hiệu GCN ("CH...", "BA...", chuỗi chữ+số) | Text đã format: chủ, thửa, mục đích, nhà/ctxd, file scan |
| `lookup_gcn_by_giay_to_dinh_danh(so_giay_to)` | Số CMND/CCCD/hộ chiếu/MST của chủ | Text đã format: danh sách GCN + thửa đất |
| `check_don_dang_ky(don_dang_ky_id)` | UUID đơn đăng ký | Text đã format: 4 nhóm + tình trạng đầy đủ/thiếu |
| `lis_schema_doc(topic)` | Chỉ dùng khi cần tra schema cho flex query | Raw markdown schema |

## Quy trình

1. Xác định loại định danh user cung cấp → chọn 1 trong 3 lookup tool. Nếu mơ hồ, hỏi lại trước khi gọi.
2. Truyền nguyên văn chuỗi định danh (KHÔNG tự thêm dấu nháy, không format).
3. Tool trả **text đã định dạng sẵn bằng tiếng Việt** — relay trực tiếp cho user, KHÔNG diễn giải lại.
4. Nếu tool trả `"Lỗi DB: ..."` → báo lỗi kết nối DB cho user.
5. Nếu tool trả `"Không tìm thấy..."` → thông báo không có kết quả.
6. Nếu kết quả có dòng `*(Kết quả đã giới hạn 50 dòng...)*` → giữ nguyên dòng đó.

## Lưu ý an toàn

- Tham số luôn nguyên văn — psycopg tự bind an toàn (không SQL injection).
- KHÔNG ghép SQL hay tự build query — skill chỉ có 3 template cố định.
- User yêu cầu sửa/xoá → từ chối (read-only).
