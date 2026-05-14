"""Hành vi vi phạm chuẩn — controlled vocab cho ``ViPhamChiTiet.hanh_vi_chuan``.

Mỗi enum value khớp với 1 hành vi đã được nhận diện trong văn bản pháp luật
Việt Nam (Luật / Nghị định / Thông tư xử phạt vi phạm hành chính chuyên ngành,
BLHS 2015). Mục đích: agent count được "bao nhiêu vụ trốn thuế" mà không phải
fuzzy-match free-text.

VLM emit ``hanh_vi_chi_tiet`` (raw text từ văn bản, đúng ngôn từ pháp lý) và
``hanh_vi_chuan`` (1 trong list bên dưới, không match → "khac"). 2 field song
song — không mất nguyên văn, vẫn aggregate được.

Mở rộng: gặp hành vi mới hay xuất hiện trong "khac" → thêm vào enum tương ứng.
"""
from __future__ import annotations

from enum import Enum


class HanhVi(str, Enum):
    """Hành vi vi phạm chuẩn. Group theo lĩnh vực để dễ maintain (~50 giá trị)."""

    # ── đất đai (NĐ 91/2019, NĐ 102/2014, NĐ 04/2022) ──
    SU_DUNG_DAT_SAI_MUC_DICH = "su_dung_dat_sai_muc_dich"
    LAN_CHIEM_DAT = "lan_chiem_dat"
    KHONG_SU_DUNG_DAT = "khong_su_dung_dat"
    GIAO_DAT_TRAI_THAM_QUYEN = "giao_dat_trai_tham_quyen"
    CHO_THUE_DAT_TRAI_QUY_DINH = "cho_thue_dat_trai_quy_dinh"
    CHUYEN_NHUONG_DAT_TRAI_QUY_DINH = "chuyen_nhuong_dat_trai_quy_dinh"
    THU_HOI_DAT_TRAI_QUY_DINH = "thu_hoi_dat_trai_quy_dinh"
    BOI_THUONG_GPMB_SAI = "boi_thuong_gpmb_sai"
    XAC_DINH_GIA_DAT_SAI = "xac_dinh_gia_dat_sai"
    CAP_GCN_TRAI_QUY_DINH = "cap_gcn_trai_quy_dinh"

    # ── tài sản công (NĐ 151/2017, Luật QLSDTSC 2017) ──
    CHO_THUE_TS_CONG_TRAI_QUY_DINH = "cho_thue_ts_cong_trai_quy_dinh"
    BAN_THANH_LY_TS_CONG_SAI = "ban_thanh_ly_ts_cong_sai"
    MUA_SAM_TS_CONG_SAI_QUY_DINH = "mua_sam_ts_cong_sai_quy_dinh"
    SU_DUNG_TS_CONG_LANG_PHI = "su_dung_ts_cong_lang_phi"
    CHIEM_DUNG_TS_CONG = "chiem_dung_ts_cong"

    # ── đấu thầu / đầu tư công (Luật ĐT 2013, NĐ 24/2024) ──
    CHI_DINH_THAU_TRAI_QUY_DINH = "chi_dinh_thau_trai_quy_dinh"
    THONG_THAU = "thong_thau"
    GIAN_LAN_HO_SO_DU_THAU = "gian_lan_ho_so_du_thau"
    CHIA_NHO_GOI_THAU = "chia_nho_goi_thau"
    THANH_TOAN_SAI_QUY_DINH = "thanh_toan_sai_quy_dinh"
    NGHIEM_THU_KHONG_DUNG_KHOI_LUONG = "nghiem_thu_khong_dung_khoi_luong"
    CHAT_LUONG_CONG_TRINH_KEM = "chat_luong_cong_trinh_kem"

    # ── thuế (Luật Quản lý thuế 2019, BLHS Đ.200) ──
    KE_KHAI_THUE_SAI = "ke_khai_thue_sai"
    CHE_GIAU_DOANH_THU = "che_giau_doanh_thu"
    TRON_THUE = "tron_thue"
    MUA_BAN_HOA_DON_TRAI_PHEP = "mua_ban_hoa_don_trai_phep"
    HOAN_THUE_SAI = "hoan_thue_sai"
    CHUYEN_GIA_LACH_THUE = "chuyen_gia_lach_thue"

    # ── xăng dầu (NĐ 99/2020, NĐ 95/2021) ──
    KINH_DOANH_XANG_DAU_KHONG_PHEP = "kinh_doanh_xang_dau_khong_phep"
    PHA_TRON_XANG_KEM_CHAT_LUONG = "pha_tron_xang_kem_chat_luong"
    BUON_LAU_XANG_DAU = "buon_lau_xang_dau"
    BAN_XANG_DAU_SAI_GIA = "ban_xang_dau_sai_gia"

    # ── khoáng sản (NĐ 36/2020, Luật KS 2010) ──
    KHAI_THAC_KS_KHONG_PHEP = "khai_thac_ks_khong_phep"
    KHAI_THAC_NGOAI_PHAM_VI = "khai_thac_ngoai_pham_vi"
    KHONG_PHUC_HOI_MOI_TRUONG = "khong_phuc_hoi_moi_truong"
    GIAN_LAN_SAN_LUONG_KHAI_THAC = "gian_lan_san_luong_khai_thac"
    XUAT_KHAU_KS_TRAI_QUY_DINH = "xuat_khau_ks_trai_quy_dinh"

    # ── môi trường (NĐ 45/2022) ──
    XA_THAI_VUOT_QUY_CHUAN = "xa_thai_vuot_quy_chuan"
    KHONG_DTM_TRUOC_DAU_TU = "khong_dtm_truoc_dau_tu"
    CHON_LAP_CHAT_THAI_SAI = "chon_lap_chat_thai_sai"

    # ── ngân sách (Luật NSNN 2015) ──
    CHI_SAI_DU_TOAN = "chi_sai_du_toan"
    CHI_VUOT_DU_TOAN = "chi_vuot_du_toan"
    KHONG_QUYET_TOAN_DUNG_HAN = "khong_quyet_toan_dung_han"
    THU_NSNN_SAI_QUY_DINH = "thu_nsnn_sai_quy_dinh"

    # ── DNNN / cổ phần hoá ──
    XAC_DINH_GIA_TRI_DN_SAI = "xac_dinh_gia_tri_dn_sai"
    BAN_CO_PHAN_UU_DAI_SAI = "ban_co_phan_uu_dai_sai"
    QUAN_LY_VON_LANG_PHI = "quan_ly_von_lang_phi"

    # ── y tế / giáo dục ──
    MUA_THUOC_THIET_BI_Y_TE_SAI = "mua_thuoc_thiet_bi_y_te_sai"
    THU_PHI_GIAO_DUC_SAI = "thu_phi_giao_duc_sai"
    MUA_THIET_BI_GIAO_DUC_SAI = "mua_thiet_bi_giao_duc_sai"

    # ── trách nhiệm công vụ (BLHS Đ.219, Đ.353, Đ.356, Đ.357, Đ.360) ──
    CO_Y_LAM_TRAI_QUY_DINH = "co_y_lam_trai_quy_dinh"        # Đ.219
    THAM_O_TAI_SAN = "tham_o_tai_san"                         # Đ.353
    LOI_DUNG_CHUC_VU_QUYEN_HAN = "loi_dung_chuc_vu_quyen_han" # Đ.356
    LAM_DUNG_CHUC_VU_QUYEN_HAN = "lam_dung_chuc_vu_quyen_han" # Đ.355
    THIEU_TRACH_NHIEM_GAY_HAU_QUA = "thieu_trach_nhiem_gay_hau_qua"  # Đ.360

    # ── catch-all ──
    KHAC = "khac"


# Mapping enum → label tiếng Việt đầy đủ. Dùng để in trong báo cáo/UI cho lãnh
# đạo (vì raw enum khó đọc), và embed vào prompt để VLM hiểu nghĩa.
LABELS_VI: dict[HanhVi, str] = {
    HanhVi.SU_DUNG_DAT_SAI_MUC_DICH: "Sử dụng đất sai mục đích",
    HanhVi.LAN_CHIEM_DAT: "Lấn chiếm đất",
    HanhVi.KHONG_SU_DUNG_DAT: "Không sử dụng đất",
    HanhVi.GIAO_DAT_TRAI_THAM_QUYEN: "Giao đất trái thẩm quyền",
    HanhVi.CHO_THUE_DAT_TRAI_QUY_DINH: "Cho thuê đất trái quy định",
    HanhVi.CHUYEN_NHUONG_DAT_TRAI_QUY_DINH: "Chuyển nhượng đất trái quy định",
    HanhVi.THU_HOI_DAT_TRAI_QUY_DINH: "Thu hồi đất trái quy định",
    HanhVi.BOI_THUONG_GPMB_SAI: "Bồi thường, giải phóng mặt bằng sai",
    HanhVi.XAC_DINH_GIA_DAT_SAI: "Xác định giá đất sai",
    HanhVi.CAP_GCN_TRAI_QUY_DINH: "Cấp giấy chứng nhận quyền sử dụng đất trái quy định",

    HanhVi.CHO_THUE_TS_CONG_TRAI_QUY_DINH: "Cho thuê tài sản công trái quy định",
    HanhVi.BAN_THANH_LY_TS_CONG_SAI: "Bán, thanh lý tài sản công sai quy định",
    HanhVi.MUA_SAM_TS_CONG_SAI_QUY_DINH: "Mua sắm tài sản công sai quy định",
    HanhVi.SU_DUNG_TS_CONG_LANG_PHI: "Sử dụng tài sản công lãng phí",
    HanhVi.CHIEM_DUNG_TS_CONG: "Chiếm dụng tài sản công",

    HanhVi.CHI_DINH_THAU_TRAI_QUY_DINH: "Chỉ định thầu trái quy định",
    HanhVi.THONG_THAU: "Thông thầu",
    HanhVi.GIAN_LAN_HO_SO_DU_THAU: "Gian lận hồ sơ dự thầu",
    HanhVi.CHIA_NHO_GOI_THAU: "Chia nhỏ gói thầu để chỉ định thầu",
    HanhVi.THANH_TOAN_SAI_QUY_DINH: "Thanh toán sai quy định",
    HanhVi.NGHIEM_THU_KHONG_DUNG_KHOI_LUONG: "Nghiệm thu không đúng khối lượng",
    HanhVi.CHAT_LUONG_CONG_TRINH_KEM: "Chất lượng công trình kém",

    HanhVi.KE_KHAI_THUE_SAI: "Kê khai thuế không đúng",
    HanhVi.CHE_GIAU_DOANH_THU: "Che giấu doanh thu",
    HanhVi.TRON_THUE: "Trốn thuế",
    HanhVi.MUA_BAN_HOA_DON_TRAI_PHEP: "Mua bán hoá đơn trái phép",
    HanhVi.HOAN_THUE_SAI: "Hoàn thuế sai",
    HanhVi.CHUYEN_GIA_LACH_THUE: "Chuyển giá để lách thuế",

    HanhVi.KINH_DOANH_XANG_DAU_KHONG_PHEP: "Kinh doanh xăng dầu không phép",
    HanhVi.PHA_TRON_XANG_KEM_CHAT_LUONG: "Pha trộn xăng kém chất lượng",
    HanhVi.BUON_LAU_XANG_DAU: "Buôn lậu xăng dầu",
    HanhVi.BAN_XANG_DAU_SAI_GIA: "Bán xăng dầu sai giá quy định",

    HanhVi.KHAI_THAC_KS_KHONG_PHEP: "Khai thác khoáng sản không phép",
    HanhVi.KHAI_THAC_NGOAI_PHAM_VI: "Khai thác ngoài phạm vi giấy phép",
    HanhVi.KHONG_PHUC_HOI_MOI_TRUONG: "Không thực hiện phục hồi môi trường",
    HanhVi.GIAN_LAN_SAN_LUONG_KHAI_THAC: "Gian lận sản lượng khai thác",
    HanhVi.XUAT_KHAU_KS_TRAI_QUY_DINH: "Xuất khẩu khoáng sản trái quy định",

    HanhVi.XA_THAI_VUOT_QUY_CHUAN: "Xả thải vượt quy chuẩn",
    HanhVi.KHONG_DTM_TRUOC_DAU_TU: "Không đánh giá tác động môi trường trước đầu tư",
    HanhVi.CHON_LAP_CHAT_THAI_SAI: "Chôn lấp chất thải sai quy định",

    HanhVi.CHI_SAI_DU_TOAN: "Chi ngân sách sai dự toán",
    HanhVi.CHI_VUOT_DU_TOAN: "Chi ngân sách vượt dự toán",
    HanhVi.KHONG_QUYET_TOAN_DUNG_HAN: "Không quyết toán ngân sách đúng hạn",
    HanhVi.THU_NSNN_SAI_QUY_DINH: "Thu NSNN sai quy định",

    HanhVi.XAC_DINH_GIA_TRI_DN_SAI: "Xác định giá trị doanh nghiệp sai",
    HanhVi.BAN_CO_PHAN_UU_DAI_SAI: "Bán cổ phần ưu đãi sai quy định",
    HanhVi.QUAN_LY_VON_LANG_PHI: "Quản lý vốn nhà nước lãng phí",

    HanhVi.MUA_THUOC_THIET_BI_Y_TE_SAI: "Mua thuốc, thiết bị y tế sai quy định",
    HanhVi.THU_PHI_GIAO_DUC_SAI: "Thu phí giáo dục sai quy định",
    HanhVi.MUA_THIET_BI_GIAO_DUC_SAI: "Mua thiết bị giáo dục sai quy định",

    HanhVi.CO_Y_LAM_TRAI_QUY_DINH: "Cố ý làm trái quy định (Đ.219 BLHS)",
    HanhVi.THAM_O_TAI_SAN: "Tham ô tài sản (Đ.353 BLHS)",
    HanhVi.LOI_DUNG_CHUC_VU_QUYEN_HAN: "Lợi dụng chức vụ, quyền hạn (Đ.356 BLHS)",
    HanhVi.LAM_DUNG_CHUC_VU_QUYEN_HAN: "Lạm dụng chức vụ, quyền hạn (Đ.355 BLHS)",
    HanhVi.THIEU_TRACH_NHIEM_GAY_HAU_QUA: "Thiếu trách nhiệm gây hậu quả nghiêm trọng (Đ.360 BLHS)",

    HanhVi.KHAC: "Khác",
}


def hanh_vi_list_for_prompt() -> str:
    """Render list as `value — label` lines to embed in the extraction prompt."""
    return "\n".join(f"  {hv.value} — {LABELS_VI[hv]}" for hv in HanhVi)
