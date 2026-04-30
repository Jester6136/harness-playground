# Schema — `lookup_gcn_by_so_hieu`

Tra cứu chi tiết 1 GCN theo số hiệu. Trả `{rows: [...], count, capped}` — flat rows, **snake_case**.

**Quan trọng**: 1 GCN có thể trải ra nhiều row do JOIN với pháp nhân + thửa đất + nhà + ctxd + paper. Khi tóm tắt cho user, **gộp theo `gcn_id`** (hoặc `phap_nhan_id` / `thua_dat_id` tuỳ ngữ cảnh) trước khi liệt kê.

## GCN

| Trường | Ý nghĩa |
|---|---|
| `gcn_id` | UUID GCN |
| `so_hieu_gcn` | Số hiệu GCN |
| `so_ho_so_goc` | Số hồ sơ gốc |
| `so_vao_so`, `ngay_vao_so` | Số / ngày vào sổ |
| `tinh_trang_gcn` | Trạng thái (đang hiệu lực / thu hồi / ...) |
| `loai_gcn` | Loại GCN (cấp lần đầu / cấp đổi / ...) |
| `can_cu_phap_ly` | Căn cứ pháp lý |
| `ten_nguoi_ky` | Người ký |
| `ghi_chu_trang1`, `ghi_chu_trang2` | Ghi chú trang 1/2 |

## Thửa đất

| Trường | Ý nghĩa |
|---|---|
| `thua_dat_id` | UUID thửa đất |
| `so_hieu_to_ban_do`, `so_thu_tu_thua` | Số tờ bản đồ / số thửa |
| `dien_tich`, `dien_tich_phap_ly` | Diện tích đo đạc / pháp lý (m²) |
| `dia_chi_thua_dat` | Địa chỉ thửa đất |
| `ten_xa` | Tên xã/phường |

## Mục đích sử dụng đất

| Trường | Ý nghĩa |
|---|---|
| `muc_dich_su_dung` | Tên mục đích (vd. "đất chuyên trồng lúa") |
| `dien_tich_mdsdd` | Diện tích cho mục đích này (m²) |
| `thoi_han_su_dung` | Thời hạn (lâu dài / có hạn) |
| `ngay_het_han_su_dung` | Ngày hết hạn |
| `nguon_goc_sdd` | Nguồn gốc sử dụng đất (chi tiết) |
| `ten_nguon_goc_sdd` | Tên nguồn gốc (mã hoá) |

## Chủ sở hữu — `phap_nhan_id`, `loai_doi_tuong` (1=cá nhân, 2=tổ chức)

Nếu `loai_doi_tuong = 1` (cá nhân):

| Trường | Ý nghĩa |
|---|---|
| `ho_ten` | Họ tên |
| `ngay_sinh` | Ngày sinh |
| `gioi_tinh` | Giới tính |
| `dia_chi_chu` | Địa chỉ chủ |
| `mst_ca_nhan` | Mã số thuế cá nhân |
| `ten_dan_toc` | Dân tộc |
| `quoc_tich` | Quốc tịch (tên Việt Nam) |

Nếu `loai_doi_tuong = 2` (tổ chức):

| Trường | Ý nghĩa |
|---|---|
| `ten_to_chuc` | Tên tổ chức |
| `ten_viet_tat` | Tên viết tắt |
| `ma_so_doanh_nghiep` | Mã số doanh nghiệp |
| `mst_to_chuc` | Mã số thuế tổ chức |
| `dia_chi_to_chuc` | Địa chỉ |

## Tài sản — Nhà

| Trường | Ý nghĩa |
|---|---|
| `nha_id` | UUID nhà |
| `so_nha` | Số nhà |
| `dien_tich_san`, `dien_tich_xay_dung` | Diện tích sàn / xây dựng (m²) |
| `so_tang` | Số tầng |
| `nam_xay_dung` | Năm xây dựng |
| `dia_chi_nha` | Địa chỉ nhà |
| `ket_cau_nha` | Loại kết cấu (bê tông / gỗ / ...) |
| `ten_loai_cap_nha` | Cấp nhà |
| `ten_hang_muc_nha`, `tang_so`, `dt_hang_muc` | Hạng mục nhà |

## Tài sản — Công trình xây dựng (CTXD)

| Trường | Ý nghĩa |
|---|---|
| `ctxd_id` | UUID CTXD |
| `ten_cong_trinh` | Tên công trình |
| `dt_ctxd` | Diện tích (m²) |
| `hang_muc_ctxd` | Hạng mục CTXD |

## Sơ đồ + Hồ sơ quét

| Trường | Ý nghĩa |
|---|---|
| `file_path_so_do`, `file_path_anh_so_do` | Đường dẫn sơ đồ |
| `ty_le_in_so_do` | Tỷ lệ in |
| `so_bien_nhan` | Số biên nhận hồ sơ |
| `so_gcn_quet` | Số GCN trên hồ sơ quét |
| `ngay_cap_quet` | Ngày cấp |
| `ghi_chu_ho_so` | Ghi chú |
| `file_scan_path`, `file_scan_name` | File scan vật lý |
