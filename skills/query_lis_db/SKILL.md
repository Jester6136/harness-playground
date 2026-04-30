---
name: query_lis_db
description: Tra cứu dữ liệu Giấy chứng nhận quyền sử dụng đất, thửa đất, đơn đăng ký trong DB LIS (geohub_lis). Dùng khi user hỏi về số hiệu GCN, số giấy tờ định danh chủ sở hữu, hoặc id đơn đăng ký.
---

## Khi nào dùng skill này

Main agent nên delegate cho `query_lis_db` khi user hỏi về:

- **Giấy chứng nhận (GCN) quyền sử dụng đất**: "tra cứu GCN số ...", "thửa đất của ai", "diện tích / mục đích sử dụng / tài sản trên đất của GCN ...".
- **Chủ sở hữu**: "ai là chủ thửa đất", "các GCN của người có CMND/CCCD/MST ...".
- **Đơn đăng ký**: "thông tin đơn đăng ký id ...", "snapshot đơn đăng ký", **"sức khoẻ"/"tình trạng"/"đầy đủ"/"thiếu" đơn đăng ký**.

KHÔNG dùng cho câu hỏi chung không có mã định danh cụ thể (ví dụ: "có bao nhiêu GCN trong hệ thống") — skill chỉ hỗ trợ tra cứu theo định danh.

## Domain concept: "sức khoẻ" của Đơn đăng ký

Khi user hỏi **"sức khoẻ", "tình trạng", "đầy đủ", "thiếu", "khoẻ không"** kèm 1 id đơn đăng ký → đây KHÔNG phải sức khoẻ con người. Đó là khái niệm domain: kiểm tra đơn đăng ký có đủ 4 nhóm dữ liệu liên quan hay không.

Một đơn đăng ký được coi là **đầy đủ / "khoẻ"** khi cả 4 nhóm đều có ít nhất 1 phần tử:

| Nhóm | Ý nghĩa | Thiếu nghĩa là |
|---|---|---|
| `phapNhanSdds`   | Pháp nhân sử dụng đất (chủ sở hữu)        | Chưa có chủ sở hữu |
| `thuaDats`       | Thửa đất                                  | Chưa gắn thửa đất nào |
| `daMdsdds`       | Mục đích sử dụng đất                      | Chưa khai báo mục đích |
| `giayChungNhans` | Giấy chứng nhận liên quan                 | Chưa cấp / liên kết GCN |

Cách kiểm tra:
1. Gọi `check_don_dang_ky(don_dang_ky_id)`.
2. Parse JSON → row đầu tiên có 4 trường array trên.
3. Đếm length từng nhóm. Nhóm nào length=0 hoặc null → thiếu.
4. Trả về cho user dạng:
   - "Đơn ĐẦY ĐỦ" + tóm tắt count 4 nhóm; HOẶC
   - "Đơn THIẾU: nhóm X, Y. Cần bổ sung ..." + count các nhóm còn lại.

KHÔNG đi tìm thông tin sức khoẻ con người trong dữ liệu đơn — không có cột nào như vậy.

## Tools available

- `lookup_gcn_by_so_hieu(so_hieu_gcn)` — tra cứu chi tiết 1 GCN theo số hiệu.
- `lookup_gcn_by_giay_to_dinh_danh(so_giay_to)` — tra cứu các GCN gắn với 1 số giấy tờ (CMND/CCCD/MST/hộ chiếu).
- `check_don_dang_ky(don_dang_ky_id)` — snapshot đầy đủ 1 đơn đăng ký theo UUID.

## Steps

1. Xác định loại định danh user cung cấp:
   - Số hiệu GCN (thường có dạng "CH...", "BA...", chuỗi chữ + số) → `lookup_gcn_by_so_hieu`.
   - Số CMND/CCCD (9 hoặc 12 chữ số), MST, hộ chiếu → `lookup_gcn_by_giay_to_dinh_danh`.
   - UUID hoặc id đơn đăng ký → `check_don_dang_ky`.
2. Nếu mơ hồ, hỏi lại user xác nhận loại định danh trước khi gọi tool.
3. Gọi đúng 1 tool, truyền nguyên văn chuỗi định danh (KHÔNG tự thêm dấu nháy, không format).
4. Tool trả JSON `{rows, count, capped}`. Nếu `count = 0` → báo "không tìm thấy". Nếu `error` → báo lỗi DB cho user.
5. Tóm tắt kết quả bằng tiếng Việt: chủ sở hữu, vị trí thửa đất, mục đích sử dụng, diện tích, tài sản. Không in raw JSON ra cho user trừ khi họ yêu cầu.
6. `capped = true` → nói thêm "kết quả đã giới hạn 50 dòng đầu, có thể còn thêm".

## Glossary cột (Vietnamese)

Dùng để diễn giải kết quả raw JSON cho user:

| Cột                  | Ý nghĩa                                        |
|---|---|
| `so_hieu_gcn`        | Số hiệu Giấy chứng nhận                        |
| `so_vao_so` / `ngay_vao_so` | Số / ngày vào sổ đăng ký              |
| `tinh_trang_gcn`     | Trạng thái GCN (đang hiệu lực / thu hồi / ...) |
| `loai_gcn`           | Loại GCN (cấp lần đầu / cấp đổi / ...)         |
| `so_hieu_to_ban_do` / `so_thu_tu_thua` | Số tờ bản đồ / số thứ tự thửa |
| `dien_tich`          | Diện tích đo đạc (m²)                          |
| `dien_tich_phap_ly`  | Diện tích pháp lý (m²)                         |
| `dia_chi_thua_dat`   | Địa chỉ thửa đất                               |
| `ten_xa`             | Tên xã/phường                                  |
| `muc_dich_su_dung`   | Mục đích sử dụng đất                           |
| `thoi_han_su_dung`   | Thời hạn sử dụng (lâu dài / có thời hạn)       |
| `nguon_goc_sdd`      | Nguồn gốc sử dụng đất                          |
| `loai_doi_tuong`     | 1 = cá nhân, 2 = tổ chức, 3 = hộ gia đình      |
| `ho_ten` / `ten_to_chuc` | Tên chủ (cá nhân / tổ chức)                |
| `mst_ca_nhan` / `mst_to_chuc` | Mã số thuế                            |
| `nha_*`              | Thông tin nhà (diện tích sàn, số tầng, năm xây)|
| `ctxd_*`             | Thông tin công trình xây dựng                  |
| `file_scan_path`     | Đường dẫn file scan hồ sơ trên hệ thống        |

## Lưu ý an toàn

- Luôn truyền tham số nguyên văn cho tool — psycopg tự bind an toàn (không SQL injection).
- KHÔNG thử ghép SQL hay tự build query — skill này không có tool query tự do.
- Nếu user yêu cầu sửa / xoá dữ liệu → từ chối, giải thích đây là tool read-only.
