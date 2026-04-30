"""SQL templates for the geohub_lis Postgres database.

Each constant is a parametric query using psycopg `%s` placeholders.
Never format user input into these strings — pass it via the `params`
tuple to `cursor.execute(sql, params)`.
"""

# Tra cứu Giấy chứng nhận theo số hiệu GCN.
GET_GCN_BY_SO_HIEU = """SELECT
    -- ========== GIẤY CHỨNG NHẬN ==========
    gcn.id                          AS gcn_id,
    gcn.so_hieu_gcn,
    gcn.so_ho_so_goc,
    gcn.so_vao_so,
    gcn.ngay_vao_so,
    gcn.tinh_trang_gcn,
    gcn.can_cu_phap_ly,
    gcn.ten_nguoi_ky,
    gcn.ghi_chu_trang1,
    gcn.ghi_chu_trang2,
    loai_gcn.ten_loai             AS loai_gcn,

    -- ========== THỬA ĐẤT ==========
    td.id                          AS thua_dat_id,
    td.so_hieu_to_ban_do,
    td.so_thu_tu_thua,
    td.dien_tich,
    td.dien_tich_phap_ly,
    td.dia_chi                     AS dia_chi_thua_dat,
    xa.ten_xa,
    loai_mdsdd.ten_muc_dich        AS muc_dich_su_dung,
    dam.dien_tich                  AS dien_tich_mdsdd,
    dam.thoi_han_su_dung,
    dam.ngay_het_han_su_dung,
    nguon_goc.chi_tiet             AS nguon_goc_sdd,
    lng_sdd.ten_nguon_goc_sdd,

    -- ========== CHỦ SỞ HỮU (pháp nhân) ==========
    pn.id                          AS phap_nhan_id,
    pn.loai_doi_tuong,

    -- Cá nhân
    cn.ho_ten,
    cn.ngay_sinh,
    cn.gioi_tinh,
    cn.dia_chi                     AS dia_chi_chu,
    cn.ma_so_thue                  AS mst_ca_nhan,
    dt.ten_dan_toc,
    qt.ten_viet_nam                AS quoc_tich,

    -- Tổ chức
    tc.ten_to_chuc,
    tc.ten_viet_tat,
    tc.ma_so_doanh_nghiep,
    tc.ma_so_thue                  AS mst_to_chuc,
    tc.dia_chi                     AS dia_chi_to_chuc,

    -- ========== TÀI SẢN TRÊN ĐẤT ==========
    nha.id                         AS nha_id,
    nha.so_nha,
    nha.dien_tich_san,
    nha.dien_tich_xay_dung,
    nha.so_tang,
    nha.nam_xay_dung,
    nha.dia_chi                    AS dia_chi_nha,
    lkn.ten_loai_ket_cau           AS ket_cau_nha,
    lcn.ten_loai_cap_nha,

    hmn.ten_hang_muc_nha,
    hmn.tang_so,
    hmn.dien_tich_san              AS dt_hang_muc,

    ctxd.id                        AS ctxd_id,
    ctxd.ten_cong_trinh,
    ctxd.dien_tich                 AS dt_ctxd,
    hmctxd.ten_hang_muc            AS hang_muc_ctxd,

    -- ========== SƠ ĐỒ & FILE ==========
    sdg.file_path_so_do,
    sdg.file_path_anh_so_do,
    sdg.ty_le_in_so_do,

    hsq.so_bien_nhan,
    hsq.so_gcn                     AS so_gcn_quet,
    hsq.ngay_cap                   AS ngay_cap_quet,
    hsq.ghi_chu                    AS ghi_chu_ho_so,
    paper.file_path                AS file_scan_path,
    paper.file_name                AS file_scan_name

FROM lis.giay_chung_nhan gcn

LEFT JOIN lis.loai_gcn              loai_gcn  ON loai_gcn.id  = gcn.loai_gcn_id
LEFT JOIN lis.so_do_gcn             sdg       ON sdg.giay_chung_nhan_id = gcn.id

LEFT JOIN lis.dang_ky_thua          dkt       ON dkt.giay_chung_nhan_id = gcn.id
LEFT JOIN lis.da_mdsdd              dam       ON dam.id        = dkt.da_mdsdd_id
LEFT JOIN lis.thua_dat              td        ON td.id         = dam.thua_dat_id
LEFT JOIN lis.xa                    xa        ON xa.id         = td.xa_id
LEFT JOIN lis.loai_mdsdd            loai_mdsdd ON loai_mdsdd.id = dam.loai_mdsdd_id
LEFT JOIN lis.nguon_goc_sdd_thua_dat nguon_goc ON nguon_goc.thua_dat_id = td.id
LEFT JOIN lis.loai_nguon_goc_sdd    lng_sdd   ON lng_sdd.id   = nguon_goc.loai_nguon_goc_sdd_id

LEFT JOIN lis.phap_nhan_sdd         pn        ON pn.id         = dkt.phap_nhan_sdd_id

LEFT JOIN lis.ca_nhan               cn        ON cn.id         = pn.doi_tuong_sdd_id
                                             AND pn.loai_doi_tuong = 1
LEFT JOIN lis.dan_toc               dt        ON dt.id         = cn.dan_toc_id
LEFT JOIN lis.quoc_tich             qt        ON qt.id         = cn.quoc_tich_id

LEFT JOIN lis.to_chuc               tc        ON tc.id         = pn.doi_tuong_sdd_id
                                             AND pn.loai_doi_tuong = 2

LEFT JOIN lis.dang_ky_nha           dkn       ON dkn.giay_chung_nhan_id = gcn.id
LEFT JOIN lis.nha                   nha       ON nha.id        = dkn.nha_id
LEFT JOIN lis.loai_ket_cau_nha      lkn       ON lkn.id  = nha.loai_ket_cau_nha_id
LEFT JOIN lis.loai_cap_nha          lcn       ON lcn.id  = nha.loai_cap_nha_id
LEFT JOIN lis.dang_ky_hang_muc_nha  dkhmn     ON dkhmn.giay_chung_nhan_id = gcn.id
                                             AND dkhmn.nha_id = nha.id
LEFT JOIN lis.hang_muc_nha          hmn       ON hmn.id  = dkhmn.hang_muc_nha_id

LEFT JOIN lis.dang_ky_hang_muc_ctxd dkhmc     ON dkhmc.giay_chung_nhan_id = gcn.id
LEFT JOIN lis.hang_muc_ctxd         hmctxd    ON hmctxd.id = dkhmc.hang_muc_ctxd_id
LEFT JOIN lis.ctxd                  ctxd      ON ctxd.id  = hmctxd.ctxd_id

LEFT JOIN lis.ho_so_quet hsq ON TRIM(UPPER(hsq.so_gcn)) = TRIM(UPPER(gcn.so_hieu_gcn))
                             AND hsq.xa_id = gcn.xa_id
LEFT JOIN lis.paper paper ON paper.ho_so_quet_id = hsq.id

WHERE gcn.so_hieu_gcn = %s

ORDER BY
    gcn.id,
    pn.id,
    td.id,
    paper.thu_tu_sap_xep;"""


# Tra cứu các GCN gắn với một số giấy tờ định danh (CMND/CCCD/MST/...) của chủ.
GET_GCN_BY_GIAY_TO_DINH_DANH = """
WITH chu_so_huu AS (
    SELECT
        gtpn.so_giay_to,
        gtpn.loai_giay_to,
        gtpn.ngay_cap,
        gtpn.noi_cap,
        COALESCE(cn.ho_ten, tc.ten_to_chuc) AS ten_chu,
        pn.id AS phap_nhan_id
    FROM lis.giay_to_phap_nhan gtpn
    LEFT JOIN lis.ca_nhan       cn ON cn.id = gtpn.doi_tuong_so_huu_giay_to_id
    LEFT JOIN lis.to_chuc       tc ON tc.id = gtpn.doi_tuong_so_huu_giay_to_id
    LEFT JOIN lis.phap_nhan_sdd pn ON pn.doi_tuong_sdd_id = gtpn.doi_tuong_so_huu_giay_to_id
    WHERE TRIM(UPPER(gtpn.so_giay_to)) = TRIM(UPPER(%s))
),
gcn_ids AS (
    SELECT c.*, dkt.giay_chung_nhan_id AS gcn_id
    FROM chu_so_huu c
    JOIN lis.dang_ky_thua dkt ON dkt.phap_nhan_sdd_id = c.phap_nhan_id
    WHERE dkt.giay_chung_nhan_id IS NOT NULL

    UNION

    SELECT c.*, dkn.giay_chung_nhan_id
    FROM chu_so_huu c
    JOIN lis.dang_ky_nha dkn ON dkn.phap_nhan_sdd_id = c.phap_nhan_id
    WHERE dkn.giay_chung_nhan_id IS NOT NULL

    UNION

    SELECT c.*, dkhmc.giay_chung_nhan_id
    FROM chu_so_huu c
    JOIN lis.dang_ky_hang_muc_ctxd dkhmc ON dkhmc.phap_nhan_sdd_id = c.phap_nhan_id
    WHERE dkhmc.giay_chung_nhan_id IS NOT NULL
)
SELECT DISTINCT
    g.so_giay_to,
    g.loai_giay_to,
    g.ngay_cap,
    g.noi_cap,
    g.ten_chu,

    gcn.id                          AS gcn_id,
    gcn.so_hieu_gcn,
    gcn.so_ho_so_goc,
    gcn.so_vao_so,
    gcn.ngay_vao_so,
    gcn.tinh_trang_gcn,
    loai_gcn.ten_loai               AS loai_gcn,

    td.so_hieu_to_ban_do,
    td.so_thu_tu_thua,
    td.dien_tich,
    td.dien_tich_phap_ly,
    td.dia_chi                      AS dia_chi_thua_dat,
    xa.ten_xa,
    loai_mdsdd.ten_muc_dich         AS muc_dich_su_dung,
    dam.thoi_han_su_dung,
    dam.ngay_het_han_su_dung,

    hsq.so_gcn                      AS so_gcn_quet,
    hsq.ngay_cap                    AS ngay_cap_quet,
    paper.file_path                 AS file_scan_path,
    paper.file_name                 AS file_scan_name,
    paper.thu_tu_sap_xep

FROM gcn_ids g

JOIN  lis.giay_chung_nhan   gcn         ON gcn.id        = g.gcn_id
LEFT JOIN lis.loai_gcn      loai_gcn    ON loai_gcn.id   = gcn.loai_gcn_id

LEFT JOIN lis.dang_ky_thua  dkt         ON dkt.giay_chung_nhan_id = gcn.id
LEFT JOIN lis.da_mdsdd      dam         ON dam.id         = dkt.da_mdsdd_id
LEFT JOIN lis.thua_dat      td          ON td.id          = dam.thua_dat_id
LEFT JOIN lis.xa            xa          ON xa.id          = td.xa_id
LEFT JOIN lis.loai_mdsdd    loai_mdsdd  ON loai_mdsdd.id  = dam.loai_mdsdd_id

LEFT JOIN lis.ho_so_quet    hsq         ON TRIM(UPPER(hsq.so_gcn)) = TRIM(UPPER(gcn.so_hieu_gcn))
                                       AND hsq.xa_id = gcn.xa_id
LEFT JOIN lis.paper         paper       ON paper.ho_so_quet_id = hsq.id

ORDER BY
    gcn.ngay_vao_so DESC,
    paper.thu_tu_sap_xep;"""


# Snapshot đầy đủ một Đơn đăng ký theo id.
CHECK_DON_DANG_KY = """select "d0"."id" as "id", "d0"."xa_id" as "xaId", "d0"."dai_dien_khai_trinh_id" as "daiDienKhaiTrinhId", "d0"."ma_don" as "maDon", "d0"."ma_ho_so_luu" as "maHoSoLuu", "d0"."ma_vach" as "maVach", "d0"."dong_su_dung" as "dongSuDung", "d0"."da_dang_ky" as "daDangKy", "d0"."ngay_dang_ky" as "ngayDangKy", "d0"."cap_giay_nguoi_dai_dien" as "capGiayNguoiDaiDien", "d0"."kieu_giay_nguoi_dai_dien" as "kieuGiayNguoiDaiDien", "d0"."dai_dien_cap_giay_id" as "daiDienCapGiayId", "d0"."qtdl_nguoi_cap_nhat" as "qtdlNguoiCapNhat", "d0"."qtdl_thoi_diem_cap_nhat" as "qtdlThoiDiemCapNhat", "d0"."qtdl_hanh_dong_cap_nhat" as "qtdlHanhDongCapNhat", "phapNhanSdds"."r" as "phapNhanSdds", "thuaDats"."r" as "thuaDats", "daMdsdds"."r" as "daMdsdds", "giayChungNhans"."r" as "giayChungNhans" from "lis"."don_dang_ky" as "d0" left join lateral(select coalesce(json_agg(row_to_json("t".*)), '[]') as "r" from (select "d1"."id" as "id", "d1"."doi_tuong_sdd_id" as "doiTuongSddId", "d1"."loai_doi_tuong" as "loaiDoiTuong", "d1"."qtdl_nguoi_cap_nhat" as "qtdlNguoiCapNhat", "d1"."qtdl_thoi_diem_cap_nhat" as "qtdlThoiDiemCapNhat", "d1"."qtdl_hanh_dong_cap_nhat" as "qtdlHanhDongCapNhat", "caNhan"."r" as "caNhan", "hoGiaDinh"."r" as "hoGiaDinh", "voChong"."r" as "voChong", "toChuc"."r" as "toChuc", "congDongDanCu"."r" as "congDongDanCu" from "lis"."phap_nhan_sdd" as "d1" inner join "lis"."phap_nhan_sdd_don_dang_ky" as "tr0" on "tr0"."phap_nhan_sdd_id" = "d1"."id" left join lateral(select row_to_json("t".*) "r" from (select "d2"."id" as "id", "d2"."loai_doi_tuong_sdd_id" as "loaiDoiTuongSddId", "d2"."quoc_tich_id" as "quocTichId", "d2"."dan_toc_id" as "danTocId", "d2"."gioi_tinh" as "gioiTinh", "d2"."ho_ten" as "hoTen", "d2"."nam_sinh" as "namSinh", "d2"."ngay_sinh" as "ngaySinh", "d2"."dia_chi" as "diaChi", "d2"."ma_so_thue" as "maSoThue", "d2"."qtdl_nguoi_cap_nhat" as "qtdlNguoiCapNhat", "d2"."qtdl_thoi_diem_cap_nhat" as "qtdlThoiDiemCapNhat", "d2"."qtdl_hanh_dong_cap_nhat" as "qtdlHanhDongCapNhat", "giayToPhapNhan"."r" as "giayToPhapNhan" from "lis"."ca_nhan" as "d2" left join lateral(select coalesce(json_agg(row_to_json("t".*)), '[]') as "r" from (select "d3"."id" as "id", "d3"."doi_tuong_so_huu_giay_to_id" as "doiTuongSoHuuGiayToId", "d3"."loai_giay_to" as "loaiGiayTo", "d3"."so_giay_to" as "soGiayTo", "d3"."ngay_cap" as "ngayCap", "d3"."ngay_het_han" as "ngayHetHan", "d3"."noi_cap" as "noiCap", "d3"."ghi_chu" as "ghiChu" from "lis"."giay_to_phap_nhan" as "d3" where "d2"."id" = "d3"."doi_tuong_so_huu_giay_to_id") as "t") as "giayToPhapNhan" on true where "d1"."doi_tuong_sdd_id" = "d2"."id" limit 1) as "t") as "caNhan" on true left join lateral(select row_to_json("t".*) "r" from (select "d2"."id" as "id", "d2"."chu_ho_id" as "chuHoId", "d2"."vo_chong_chu_ho_id" as "voChongChuHoId", "d2"."in_ho_ong_ba" as "inHoOngBa", "d2"."qtdl_nguoi_cap_nhat" as "qtdlNguoiCapNhat", "d2"."qtdl_thoi_diem_cap_nhat" as "qtdlThoiDiemCapNhat", "d2"."qtdl_hanh_dong_cap_nhat" as "qtdlHanhDongCapNhat", "chuHo"."r" as "chuHo" from "lis"."ho_gia_dinh" as "d2" left join lateral(select row_to_json("t".*) "r" from (select "d3"."id" as "id", "d3"."loai_doi_tuong_sdd_id" as "loaiDoiTuongSddId", "d3"."quoc_tich_id" as "quocTichId", "d3"."dan_toc_id" as "danTocId", "d3"."gioi_tinh" as "gioiTinh", "d3"."ho_ten" as "hoTen", "d3"."nam_sinh" as "namSinh", "d3"."ngay_sinh" as "ngaySinh", "d3"."dia_chi" as "diaChi", "d3"."ma_so_thue" as "maSoThue", "d3"."qtdl_nguoi_cap_nhat" as "qtdlNguoiCapNhat", "d3"."qtdl_thoi_diem_cap_nhat" as "qtdlThoiDiemCapNhat", "d3"."qtdl_hanh_dong_cap_nhat" as "qtdlHanhDongCapNhat", "giayToPhapNhan"."r" as "giayToPhapNhan" from "lis"."ca_nhan" as "d3" left join lateral(select coalesce(json_agg(row_to_json("t".*)), '[]') as "r" from (select "d4"."id" as "id", "d4"."doi_tuong_so_huu_giay_to_id" as "doiTuongSoHuuGiayToId", "d4"."loai_giay_to" as "loaiGiayTo", "d4"."so_giay_to" as "soGiayTo", "d4"."ngay_cap" as "ngayCap", "d4"."ngay_het_han" as "ngayHetHan", "d4"."noi_cap" as "noiCap", "d4"."ghi_chu" as "ghiChu" from "lis"."giay_to_phap_nhan" as "d4" where "d3"."id" = "d4"."doi_tuong_so_huu_giay_to_id") as "t") as "giayToPhapNhan" on true where "d2"."chu_ho_id" = "d3"."id" limit 1) as "t") as "chuHo" on true where "d1"."doi_tuong_sdd_id" = "d2"."id" limit 1) as "t") as "hoGiaDinh" on true left join lateral(select row_to_json("t".*) "r" from (select "d2"."id" as "id", "d2"."nguoi_thu_nhat_id" as "nguoiThuNhatId", "d2"."nguoi_thu_hai_id" as "nguoiThuHaiId", "d2"."qtdl_nguoi_cap_nhat" as "qtdlNguoiCapNhat", "d2"."qtdl_thoi_diem_cap_nhat" as "qtdlThoiDiemCapNhat", "d2"."qtdl_hanh_dong_cap_nhat" as "qtdlHanhDongCapNhat", "nguoiThuNhat"."r" as "nguoiThuNhat", "nguoiThuHai"."r" as "nguoiThuHai" from "lis"."vo_chong" as "d2" left join lateral(select row_to_json("t".*) "r" from (select "d3"."id" as "id", "d3"."loai_doi_tuong_sdd_id" as "loaiDoiTuongSddId", "d3"."quoc_tich_id" as "quocTichId", "d3"."dan_toc_id" as "danTocId", "d3"."gioi_tinh" as "gioiTinh", "d3"."ho_ten" as "hoTen", "d3"."nam_sinh" as "namSinh", "d3"."ngay_sinh" as "ngaySinh", "d3"."dia_chi" as "diaChi", "d3"."ma_so_thue" as "maSoThue", "d3"."qtdl_nguoi_cap_nhat" as "qtdlNguoiCapNhat", "d3"."qtdl_thoi_diem_cap_nhat" as "qtdlThoiDiemCapNhat", "d3"."qtdl_hanh_dong_cap_nhat" as "qtdlHanhDongCapNhat", "giayToPhapNhan"."r" as "giayToPhapNhan" from "lis"."ca_nhan" as "d3" left join lateral(select coalesce(json_agg(row_to_json("t".*)), '[]') as "r" from (select "d4"."id" as "id", "d4"."doi_tuong_so_huu_giay_to_id" as "doiTuongSoHuuGiayToId", "d4"."loai_giay_to" as "loaiGiayTo", "d4"."so_giay_to" as "soGiayTo", "d4"."ngay_cap" as "ngayCap", "d4"."ngay_het_han" as "ngayHetHan", "d4"."noi_cap" as "noiCap", "d4"."ghi_chu" as "ghiChu" from "lis"."giay_to_phap_nhan" as "d4" where "d3"."id" = "d4"."doi_tuong_so_huu_giay_to_id") as "t") as "giayToPhapNhan" on true where "d2"."nguoi_thu_nhat_id" = "d3"."id" limit 1) as "t") as "nguoiThuNhat" on true left join lateral(select row_to_json("t".*) "r" from (select "d3"."id" as "id", "d3"."loai_doi_tuong_sdd_id" as "loaiDoiTuongSddId", "d3"."quoc_tich_id" as "quocTichId", "d3"."dan_toc_id" as "danTocId", "d3"."gioi_tinh" as "gioiTinh", "d3"."ho_ten" as "hoTen", "d3"."nam_sinh" as "namSinh", "d3"."ngay_sinh" as "ngaySinh", "d3"."dia_chi" as "diaChi", "d3"."ma_so_thue" as "maSoThue", "d3"."qtdl_nguoi_cap_nhat" as "qtdlNguoiCapNhat", "d3"."qtdl_thoi_diem_cap_nhat" as "qtdlThoiDiemCapNhat", "d3"."qtdl_hanh_dong_cap_nhat" as "qtdlHanhDongCapNhat", "giayToPhapNhan"."r" as "giayToPhapNhan" from "lis"."ca_nhan" as "d3" left join lateral(select coalesce(json_agg(row_to_json("t".*)), '[]') as "r" from (select "d4"."id" as "id", "d4"."doi_tuong_so_huu_giay_to_id" as "doiTuongSoHuuGiayToId", "d4"."loai_giay_to" as "loaiGiayTo", "d4"."so_giay_to" as "soGiayTo", "d4"."ngay_cap" as "ngayCap", "d4"."ngay_het_han" as "ngayHetHan", "d4"."noi_cap" as "noiCap", "d4"."ghi_chu" as "ghiChu" from "lis"."giay_to_phap_nhan" as "d4" where "d3"."id" = "d4"."doi_tuong_so_huu_giay_to_id") as "t") as "giayToPhapNhan" on true where "d2"."nguoi_thu_hai_id" = "d3"."id" limit 1) as "t") as "nguoiThuHai" on true where "d1"."doi_tuong_sdd_id" = "d2"."id" limit 1) as "t") as "voChong" on true left join lateral(select row_to_json("t".*) "r" from (select "d2"."id" as "id", "d2"."loai_doi_tuong_sdd_id" as "loaiDoiTuongSddId", "d2"."ten_to_chuc" as "tenToChuc", "d2"."ten_viet_tat" as "tenVietTat", "d2"."ten_to_chuc_ta" as "tenToChucTa", "d2"."nguoi_dai_dien_id" as "nguoiDaiDienId", "d2"."ma_so_doanh_nghiep" as "maSoDoanhNghiep", "d2"."ma_so_thue" as "maSoThue", "d2"."dia_chi" as "diaChi", "d2"."ghi_chu" as "ghiChu", "d2"."qtdl_nguoi_cap_nhat" as "qtdlNguoiCapNhat", "d2"."qtdl_thoi_diem_cap_nhat" as "qtdlThoiDiemCapNhat", "d2"."qtdl_hanh_dong_cap_nhat" as "qtdlHanhDongCapNhat", "giayToPhapNhan"."r" as "giayToPhapNhan" from "lis"."to_chuc" as "d2" left join lateral(select coalesce(json_agg(row_to_json("t".*)), '[]') as "r" from (select "d3"."id" as "id", "d3"."doi_tuong_so_huu_giay_to_id" as "doiTuongSoHuuGiayToId", "d3"."loai_giay_to" as "loaiGiayTo", "d3"."so_giay_to" as "soGiayTo", "d3"."ngay_cap" as "ngayCap", "d3"."ngay_het_han" as "ngayHetHan", "d3"."noi_cap" as "noiCap", "d3"."ghi_chu" as "ghiChu" from "lis"."giay_to_phap_nhan" as "d3" where "d2"."id" = "d3"."doi_tuong_so_huu_giay_to_id") as "t") as "giayToPhapNhan" on true where "d1"."doi_tuong_sdd_id" = "d2"."id" limit 1) as "t") as "toChuc" on true left join lateral(select row_to_json("t".*) "r" from (select "d2"."id" as "id", "d2"."loai_doi_tuong_sdd_id" as "loaiDoiTuongSddId", "d2"."ten_cong_dong" as "tenCongDong", "d2"."nguoi_dai_dien_id" as "nguoiDaiDienId", "d2"."dia_chi" as "diaChi", "d2"."ghi_chu" as "ghiChu", "d2"."qtdl_nguoi_cap_nhat" as "qtdlNguoiCapNhat", "d2"."qtdl_thoi_diem_cap_nhat" as "qtdlThoiDiemCapNhat", "d2"."qtdl_hanh_dong_cap_nhat" as "qtdlHanhDongCapNhat", "giayToPhapNhan"."r" as "giayToPhapNhan" from "lis"."cong_dong_dan_cu" as "d2" left join lateral(select coalesce(json_agg(row_to_json("t".*)), '[]') as "r" from (select "d3"."id" as "id", "d3"."doi_tuong_so_huu_giay_to_id" as "doiTuongSoHuuGiayToId", "d3"."loai_giay_to" as "loaiGiayTo", "d3"."so_giay_to" as "soGiayTo", "d3"."ngay_cap" as "ngayCap", "d3"."ngay_het_han" as "ngayHetHan", "d3"."noi_cap" as "noiCap", "d3"."ghi_chu" as "ghiChu" from "lis"."giay_to_phap_nhan" as "d3" where "d2"."id" = "d3"."doi_tuong_so_huu_giay_to_id") as "t") as "giayToPhapNhan" on true where "d1"."doi_tuong_sdd_id" = "d2"."id" limit 1) as "t") as "congDongDanCu" on true where "d0"."id" = "tr0"."don_dang_ky_id") as "t") as "phapNhanSdds" on true left join lateral(select coalesce(json_agg(row_to_json("t".*)), '[]') as "r" from (select "d1"."id" as "id", "d1"."xa_id" as "xaId", "d1"."tai_lieu_do_dac_id" as "taiLieuDoDacId", "d1"."so_hieu_to_ban_do" as "soHieuToBanDo", "d1"."so_thu_tu_thua" as "soThuTuThua", "d1"."so_hieu_to_ban_do_cu" as "soHieuToBanDoCu", "d1"."so_thu_tu_thua_cu" as "soThuTuThuaCu", "d1"."dien_tich" as "dienTich", "d1"."dien_tich_phap_ly" as "dienTichPhapLy", "d1"."dien_tich_ban_do" as "dienTichBanDo", "d1"."dia_chi" as "diaChi", "d1"."la_to_thua_2_cap" as "laToThua2Cap", "d1"."qtdl_nguoi_cap_nhat" as "qtdlNguoiCapNhat", "d1"."qtdl_thoi_diem_cap_nhat" as "qtdlThoiDiemCapNhat", "d1"."qtdl_hanh_dong_cap_nhat" as "qtdlHanhDongCapNhat" from "lis"."thua_dat" as "d1" inner join "lis"."dang_ky_thua" as "tr0" on "tr0"."thua_dat_id" = "d1"."id" where "d0"."id" = "tr0"."don_dang_ky_id") as "t") as "thuaDats" on true left join lateral(select coalesce(json_agg(row_to_json("t".*)), '[]') as "r" from (select "d1"."id" as "id", "d1"."thua_dat_id" as "thuaDatId", "d1"."loai_mdsdd_id" as "loaiMdsddId", "d1"."dien_tich" as "dienTich", "d1"."su_dung_chung" as "suDungChung", "d1"."thoi_han_su_dung" as "thoiHanSuDung", "d1"."ngay_het_han_su_dung" as "ngayHetHanSuDung", "d1"."thoi_han_su_dung_lau_dai" as "thoiHanSuDungLauDai", "d1"."qtdl_nguoi_cap_nhat" as "qtdlNguoiCapNhat", "d1"."qtdl_thoi_diem_cap_nhat" as "qtdlThoiDiemCapNhat", "d1"."qtdl_hanh_dong_cap_nhat" as "qtdlHanhDongCapNhat", "loaiMdsdd"."r" as "loaiMdsdd" from "lis"."da_mdsdd" as "d1" inner join "lis"."dang_ky_thua" as "tr0" on "tr0"."da_mdsdd_id" = "d1"."id" left join lateral(select row_to_json("t".*) "r" from (select "d2"."id" as "id", "d2"."khoa_cha_id" as "khoaChaId", "d2"."ky_hieu_muc_dich" as "kyHieuMucDich", "d2"."ky_hieu_bang_so" as "kyHieuBangSo", "d2"."ten_muc_dich" as "tenMucDich", "d2"."ten_day_du" as "tenDayDu", "d2"."thu_tu_sap_xep" as "thuTuSapXep", "d2"."dmdc_hieu_luc" as "dmdcHieuLuc", "d2"."qtdl_nguoi_cap_nhat" as "qtdlNguoiCapNhat", "d2"."qtdl_thoi_diem_cap_nhat" as "qtdlThoiDiemCapNhat", "d2"."qtdl_hanh_dong_cap_nhat" as "qtdlHanhDongCapNhat" from "lis"."loai_mdsdd" as "d2" where "d1"."loai_mdsdd_id" = "d2"."id" limit 1) as "t") as "loaiMdsdd" on true where "d0"."id" = "tr0"."don_dang_ky_id") as "t") as "daMdsdds" on true left join lateral(select coalesce(json_agg(row_to_json("t".*)), '[]') as "r" from (select "d1"."id" as "id", "d1"."xa_id" as "xaId", "d1"."loai_gcn_id" as "loaiGcnId", "d1"."hinh_thuc_so_huu" as "hinhThucSoHuu", "d1"."da_cong_nhan_phap_ly" as "daCongNhanPhapLy", "d1"."tinh_trang_gcn" as "tinhTrangGcn", "d1"."ma_vach" as "maVach", "d1"."so_hieu_gcn" as "soHieuGcn", "d1"."so_ho_so_goc" as "soHoSoGoc", "d1"."so_ho_so_goc_cu" as "soHoSoGocCu", "d1"."so_vao_so" as "soVaoSo", "d1"."so_vao_so_cu" as "soVaoSoCu", "d1"."ngay_vao_so" as "ngayVaoSo", "d1"."ngay_vao_so_cu" as "ngayVaoSoCu", "d1"."can_cu_phap_ly" as "canCuPhapLy", "d1"."don_vi_cap" as "donViCap", "d1"."uy_quyen_ky" as "uyQuyenKy", "d1"."ky_thay" as "kyThay", "d1"."ten_nguoi_ky" as "tenNguoiKy", "d1"."ghi_chu_trang1" as "ghiChuTrang1", "d1"."ghi_chu_trang2" as "ghiChuTrang2", "d1"."ghi_chu_trang3" as "ghiChuTrang3", "d1"."ghi_chu_trang4" as "ghiChuTrang4", "d1"."qtdl_nguoi_cap_nhat" as "qtdlNguoiCapNhat", "d1"."qtdl_thoi_diem_cap_nhat" as "qtdlThoiDiemCapNhat", "d1"."qtdl_hanh_dong_cap_nhat" as "qtdlHanhDongCapNhat", "hoSoQuets"."r" as "hoSoQuets" from "lis"."giay_chung_nhan" as "d1" inner join "lis"."phap_nhan_sdd_don_dang_ky" as "tr0" on "tr0"."giay_chung_nhan_id" = "d1"."id" left join lateral(select coalesce(json_agg(row_to_json("t".*)), '[]') as "r" from (select "d2"."id" as "id", "d2"."khoa_cha_id" as "khoaChaId", "d2"."ds_ho_so_quet_id" as "dsHoSoQuetId", "d2"."xa_id" as "xaId", "d2"."so_ho_so" as "soHoSo", "d2"."so_bien_nhan" as "soBienNhan", "d2"."loai_gcn_id" as "loaiGcnId", "d2"."so_gcn" as "soGcn", "d2"."ngay_cap" as "ngayCap", "d2"."nen_ban_do" as "nenBanDo", "d2"."so_ho_so_goc" as "soHoSoGoc", "d2"."so_ho_so" as "khoHoSo", "d2"."day_ho_so" as "dayHoSo", "d2"."hop_ho_so" as "hopHoSo", "d2"."vi_tri_ho_so" as "viTriHoSo", "d2"."ghi_chu" as "ghiChu", "d2"."so_vao_so" as "soVaoSo", "d2"."ho_ten" as "hoTen", "d2"."so_cmnd" as "soCmnd", "d2"."so_vao_so_cu" as "soVaoSoCu", "d2"."ngay_vao_so_cu" as "ngayVaoSoCu", "d2"."so_ho_so_goc_cu" as "soHoSoGocCu", "d2"."giay_moi_nhat" as "giayMoiNhat", "d2"."qtdl_nguoi_cap_nhat" as "qtdlNguoiCapNhat", "d2"."qtdl_thoi_diem_cap_nhat" as "qtdlThoiDiemCapNhat", "d2"."qtdl_hanh_dong_cap_nhat" as "qtdlHanhDongCapNhat", "papers"."r" as "papers" from "lis"."ho_so_quet" as "d2" left join lateral(select coalesce(json_agg(row_to_json("t".*)), '[]') as "r" from (select "d3"."id" as "id", "d3"."ho_so_quet_id" as "hoSoQuetId", "d3"."thu_tu_sap_xep" as "thuTuSapXep", "d3"."file_type" as "fileType", "d3"."file_name" as "fileName", "d3"."file_path" as "filePath", "d3"."qtdl_nguoi_cap_nhat" as "qtdlNguoiCapNhat", "d3"."qtdl_thoi_diem_cap_nhat" as "qtdlThoiDiemCapNhat", "d3"."qtdl_hanh_dong_cap_nhat" as "qtdlHanhDongCapNhat" from "lis"."paper" as "d3" where "d2"."id" = "d3"."ho_so_quet_id") as "t") as "papers" on true where "d1"."so_hieu_gcn" = "d2"."so_gcn") as "t") as "hoSoQuets" on true where "d0"."id" = "tr0"."don_dang_ky_id") as "t") as "giayChungNhans" on true where "d0"."id" = %s limit 1"""
