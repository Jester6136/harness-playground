# Glossary — map snake_case ↔ camelCase + quy tắc diễn giải

## Map snake ↔ camel (cùng nghĩa, khác format giữa các tool)

3 tool dùng 2 quy ước đặt tên khác nhau. Khi user hỏi 1 thuật ngữ, đây là cách lookup.

| snake_case (tool A/B) | camelCase (tool C) | Nghĩa |
|---|---|---|
| `gcn_id` | `id` (trong `giayChungNhans[]`) | UUID GCN |
| `so_hieu_gcn` | `soHieuGcn` | Số hiệu GCN |
| `so_ho_so_goc` | `soHoSoGoc` | Số hồ sơ gốc |
| `so_vao_so` / `ngay_vao_so` | `soVaoSo` / `ngayVaoSo` | Số / ngày vào sổ |
| `tinh_trang_gcn` | `tinhTrangGcn` | Trạng thái GCN |
| `loai_gcn` | (chỉ `loaiGcnId` UUID) | Loại GCN — tool C không join ra tên |
| `can_cu_phap_ly` | `canCuPhapLy` | Căn cứ pháp lý |
| `ten_nguoi_ky` | `tenNguoiKy` | Người ký |
| `ghi_chu_trang1` ... `ghi_chu_trang2` | `ghiChuTrang1` ... `ghiChuTrang4` | Ghi chú trang (tool C có thêm 3, 4) |
| `thua_dat_id` | `id` (trong `thuaDats[]`) | UUID thửa đất |
| `so_hieu_to_ban_do` / `so_thu_tu_thua` | `soHieuToBanDo` / `soThuTuThua` | Tờ bản đồ / số thửa |
| `dien_tich` | `dienTich` | Diện tích đo đạc (m²) |
| `dien_tich_phap_ly` | `dienTichPhapLy` | Diện tích pháp lý (m²) |
| (không có) | `dienTichBanDo` | Diện tích trên bản đồ — chỉ tool C |
| `dia_chi_thua_dat` / `dia_chi_chu` / `dia_chi_nha` | `diaChi` (theo context) | Địa chỉ |
| `ten_xa` | (chỉ `xaId` UUID) | Tên xã — tool C không join |
| `muc_dich_su_dung` | `daMdsdds[].loaiMdsdd.tenMucDich` | Mục đích sử dụng đất |
| `dien_tich_mdsdd` | `daMdsdds[].dienTich` | Diện tích mục đích |
| `thoi_han_su_dung` | `daMdsdds[].thoiHanSuDung` | Thời hạn |
| `ngay_het_han_su_dung` | `daMdsdds[].ngayHetHanSuDung` | Ngày hết hạn |
| (không có) | `daMdsdds[].thoiHanSuDungLauDai` | Cờ lâu dài — chỉ tool C |
| `nguon_goc_sdd` / `ten_nguon_goc_sdd` | (không có trong tool C) | Nguồn gốc SDĐ — chỉ tool A |
| `phap_nhan_id` / `loai_doi_tuong` | `phapNhanSdds[].id` / `.loaiDoiTuong` | Pháp nhân + loại |
| `ho_ten` | `caNhan.hoTen` (hoặc trong các nested cá nhân khác) | Họ tên |
| `ngay_sinh` | `caNhan.ngaySinh` | Ngày sinh |
| `gioi_tinh` | `caNhan.gioiTinh` | Giới tính |
| `mst_ca_nhan` | `caNhan.maSoThue` | MST cá nhân |
| `ten_dan_toc` | (chỉ `caNhan.danTocId` UUID) | Dân tộc — tool C không join |
| `quoc_tich` | (chỉ `caNhan.quocTichId` UUID) | Quốc tịch — tool C không join |
| `ten_to_chuc` / `ten_viet_tat` | `toChuc.tenToChuc` / `.tenVietTat` | Tổ chức |
| `ma_so_doanh_nghiep` | `toChuc.maSoDoanhNghiep` | MST doanh nghiệp |
| `mst_to_chuc` | `toChuc.maSoThue` | MST tổ chức |
| `dia_chi_to_chuc` | `toChuc.diaChi` | Địa chỉ tổ chức |
| (chỉ tool A) `nha_*`, `ctxd_*`, `*_hang_muc` | (không có trong C) | Nhà / CTXD — tool C bỏ qua |
| `file_scan_path` / `file_scan_name` | `papers[].filePath` / `.fileName` | File scan |
| `so_gcn_quet` / `ngay_cap_quet` / `so_bien_nhan` | `hoSoQuets[].soGcn` / `.ngayCap` / `.soBienNhan` | Hồ sơ quét |

## Bảng giá trị mã (chung cho cả 3 tool)

`loai_doi_tuong` / `loaiDoiTuong`:

| Mã | Ý nghĩa |
|---|---|
| 1 | Cá nhân |
| 2 | Tổ chức |
| 3 | Hộ gia đình |
| 4 | Vợ chồng |
| 5 | Cộng đồng dân cư |

## Quy tắc diễn giải

1. **Tool A/B (flat, snake_case)**: nhiều row có cùng `gcn_id` là do JOIN bung ra, không phải nhiều GCN. **Gộp theo `gcn_id`** trước khi tóm tắt cho user.
2. **Tool B ít trường hơn A** (không có nhà/ctxd/sơ đồ/nguồn gốc). Nếu user cần các thông tin đó thì sau khi có `so_hieu_gcn` từ B, gọi tiếp A để load chi tiết.
3. **Tool C (nested, camelCase)**: luôn 1 row, lặp qua từng mảng con. `loaiDoiTuong` quyết định nested object nào của `phapNhanSdds[]` là non-null — đừng đọc nhầm `caNhan` khi loại là 2 (tổ chức).
4. **Trường null/missing**: bỏ qua khi tóm tắt. Nếu user hỏi đích danh thì nói "chưa có dữ liệu".
5. **Trường UUID-only ở tool C** (vd. `xaId`, `loaiGcnId`, `danTocId`): tool C không join ra tên, chỉ trả ID. Nếu user cần tên thì giải thích cần tra qua tool khác hoặc sang A để có `ten_xa`, `loai_gcn`...
6. **Trường ngoài glossary nhưng có trong raw JSON**: vẫn trả lời theo tên gốc + suy đoán nghĩa từ tên. Đừng từ chối vì "không có trong tài liệu".
