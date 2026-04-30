# Schema — `lookup_gcn_by_giay_to_dinh_danh`

Tra cứu các GCN gắn với 1 số giấy tờ định danh chủ sở hữu (CMND/CCCD/MST/hộ chiếu). Trả `{rows: [...], count, capped}` — flat rows, **snake_case**.

**Quan trọng**:
- Mỗi chủ có thể đứng tên nhiều GCN, mỗi GCN có thể trải nhiều row (do JOIN). Gộp theo `gcn_id` khi tóm tắt.
- **Phạm vi hẹp hơn `lookup_gcn_by_so_hieu`**: KHÔNG có thông tin nhà, ctxd, sơ đồ, nguồn gốc SDĐ, chi tiết chủ (chỉ có `ten_chu` đã COALESCE). Nếu user cần các thông tin đó, sau khi có `so_hieu_gcn` từ tool này, gọi tiếp `lookup_gcn_by_so_hieu` để load chi tiết.

## Giấy tờ định danh đã tra

| Trường | Ý nghĩa |
|---|---|
| `so_giay_to`, `loai_giay_to` | Số / loại giấy tờ |
| `ngay_cap`, `noi_cap` | Ngày / nơi cấp |
| `ten_chu` | Tên chủ (đã COALESCE cá nhân/tổ chức — chỉ có tên, không có ngày sinh, MST, địa chỉ) |

## GCN

| Trường | Ý nghĩa |
|---|---|
| `gcn_id` | UUID GCN |
| `so_hieu_gcn`, `so_ho_so_goc` | Định danh GCN |
| `so_vao_so`, `ngay_vao_so` | Sổ vào |
| `tinh_trang_gcn` | Trạng thái |
| `loai_gcn` | Loại GCN |

## Thửa đất

| Trường | Ý nghĩa |
|---|---|
| `so_hieu_to_ban_do`, `so_thu_tu_thua` | Tờ bản đồ / số thửa |
| `dien_tich`, `dien_tich_phap_ly` | Diện tích (m²) |
| `dia_chi_thua_dat`, `ten_xa` | Vị trí |

## Mục đích sử dụng đất

| Trường | Ý nghĩa |
|---|---|
| `muc_dich_su_dung` | Tên mục đích |
| `thoi_han_su_dung` | Thời hạn |
| `ngay_het_han_su_dung` | Ngày hết hạn |

## Hồ sơ quét

| Trường | Ý nghĩa |
|---|---|
| `so_gcn_quet`, `ngay_cap_quet` | Số / ngày trên hồ sơ |
| `file_scan_path`, `file_scan_name` | File scan vật lý |
| `thu_tu_sap_xep` | Thứ tự sắp xếp file |
