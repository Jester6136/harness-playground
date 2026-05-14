"""Canonical schema cho extract Kết luận thanh tra (TTCP).

Cấu trúc bám sát Luật Thanh tra 2022 + Thông tư 06/2021 — 5 phần của 1 KLTT:
  4.1 phan_can_cu              — căn cứ (QĐ thanh tra, luật, kế hoạch…)
  4.2 phan_noi_dung            — phạm vi, thời kỳ, đối tượng, nội dung
  4.3 vi_pham[]                — kết quả thanh tra (9 thuộc tính/vi phạm)
  4.4 kien_nghi[]              — kiến nghị xử lý (8 loại × 7 thuộc tính)
  4.5 phan_to_chuc_thuc_hien   — thời hạn, đơn vị thực hiện, báo cáo

Song song:
  - Top-level aggregate fields (``tien.*``, ``hinh_su.*``, ``dia_phuong[]``,
    ``linh_vuc[]``…) cho Q&A lãnh đạo: count/sum/group_by nhanh, không phải
    scan nested.
  - ``raw_extract`` (lưu ngoài TTCPRecord, ở doc level) giữ JSON gốc VLM.

Convention
----------
- Tiền: số nguyên VND (đồng). "4.896 triệu đồng" → ``4896000000``.
- Diện tích: ``m2`` (mét vuông). "1.2 ha" → ``12000``.
- Ngày: ISO ``YYYY-MM-DD``. Không parse được → null + mô tả raw vào ``mo_ta``.
- Tỉnh: qua ``vn_provinces.canonicalize_list()`` trước khi save.
- Hành vi: 2 field song song — ``hanh_vi_chi_tiet`` (raw từ văn bản) +
  ``hanh_vi_chuan`` (enum ``HanhVi`` — xem ``ttcp_taxonomy.py``).
"""
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from src.extentions.multimodal.ttcp_taxonomy import HanhVi


# ── controlled vocabularies ────────────────────────────────────────────────


class LinhVuc(str, Enum):
    """Bước 5.2 — nhóm vi phạm. Embed list này vào prompt để VLM chọn enum."""
    DAT_DAI = "dat_dai"
    TAI_SAN_CONG = "tai_san_cong"
    XANG_DAU = "xang_dau"
    DAU_THAU = "dau_thau"
    DAU_TU_CONG = "dau_tu_cong"
    NGAN_SACH = "ngan_sach"
    XAY_DUNG = "xay_dung"
    KHOANG_SAN = "khoang_san"
    MOI_TRUONG = "moi_truong"
    Y_TE = "y_te"
    GIAO_DUC = "giao_duc"
    THUE_HAI_QUAN = "thue_hai_quan"
    NGAN_HANG_TIN_DUNG = "ngan_hang_tin_dung"
    CO_PHAN_HOA_DOANH_NGHIEP = "co_phan_hoa_doanh_nghiep"
    KHAC = "khac"


class LoaiVanBan(str, Enum):
    KET_LUAN_THANH_TRA = "ket_luan_thanh_tra"
    THONG_BAO_KLTT = "thong_bao_kltt"
    QUYET_DINH_XU_PHAT = "quyet_dinh_xu_phat"
    KHAC = "khac"


class MucDoViPham(str, Enum):
    """Mức độ vi phạm. KLTT thường nêu rõ; nếu không → khong_ro."""
    NHE = "nhe"
    VUA = "vua"
    NGHIEM_TRONG = "nghiem_trong"
    DAC_BIET_NGHIEM_TRONG = "dac_biet_nghiem_trong"
    KHONG_RO = "khong_ro"


class TrangThaiThucHien(str, Enum):
    """Trạng thái thực hiện KLTT (tổng thể cả văn bản)."""
    CHUA_THUC_HIEN = "chua_thuc_hien"
    DANG_THUC_HIEN = "dang_thuc_hien"
    CHAM_THUC_HIEN = "cham_thuc_hien"
    HOAN_THANH = "hoan_thanh"
    KHONG_RO = "khong_ro"


class LoaiKienNghi(str, Enum):
    """Bước 4.4 — 8 loại kiến nghị xử lý theo Luật Thanh tra."""
    KINH_TE = "kinh_te"                          # (1) thu hồi tiền, hoàn trả, truy thu
    DAT_DAI_TS_TAI_NGUYEN = "dat_dai_ts_tai_nguyen"   # (2) đất, tài sản công, tài nguyên
    VI_PHAM_HANH_CHINH = "vi_pham_hanh_chinh"    # (3) xử phạt VPHC
    KIEM_DIEM_TRACH_NHIEM = "kiem_diem_trach_nhiem"   # (4) kiểm điểm, kỷ luật HC
    XU_LY_DANG = "xu_ly_dang"                    # (5) xử lý về Đảng
    CHUYEN_CQDT = "chuyen_cqdt"                  # (6) chuyển CQĐT / khởi tố
    HOAN_THIEN_CO_CHE = "hoan_thien_co_che"      # (7) hoàn thiện cơ chế, chính sách
    TO_CHUC_THEO_DOI = "to_chuc_theo_doi"        # (8) tổ chức thực hiện, theo dõi


class TinhTrangKienNghi(str, Enum):
    """Tình trạng thực hiện từng kiến nghị (per-item, khác với
    ``TrangThaiThucHien`` ở doc level)."""
    CHUA_THUC_HIEN = "chua_thuc_hien"
    DANG_THUC_HIEN = "dang_thuc_hien"
    HOAN_THANH = "hoan_thanh"
    KHONG_RO = "khong_ro"


# ── nested models — value objects ──────────────────────────────────────────


class ThoiKy(BaseModel):
    """Thời kỳ thanh tra — khác với ngày ban hành kết luận."""
    tu: Optional[date] = None
    den: Optional[date] = None
    mo_ta: str = ""  # raw text khi không parse được, vd "2010-2013"


class SoLieuViPham(BaseModel):
    """Bước 5.4 — số liệu của 1 vi phạm. Đa đơn vị: tiền + diện tích + count."""
    gia_tri_vnd: Optional[float] = None         # số nguyên VND
    dien_tich_dat_m2: Optional[float] = None    # mét vuông
    so_luong_don_vi: Optional[int] = None       # số lượng (hồ sơ, đối tượng…)
    mo_ta: str = ""                              # raw khi không lượng hoá được


class TrachNhiem(BaseModel):
    """Bước 5.5 — tách 3 loại trách nhiệm."""
    tap_the: List[str] = []                      # tên đơn vị/tổ chức
    ca_nhan: List[str] = []                      # "Nguyễn Văn A - Phó GĐ Sở X"
    nguoi_dung_dau: List[str] = []               # "Nguyễn Văn B - GĐ Sở X"


# ── 5 phần KLTT (bước 4) ──────────────────────────────────────────────────


class PhanCanCu(BaseModel):
    """Bước 4.1 — căn cứ thanh tra."""
    quyet_dinh_thanh_tra: List[str] = []         # số QĐ thanh tra
    van_ban_phap_luat: List[str] = []            # luật, NĐ, TT trích dẫn
    ke_hoach_thanh_tra: List[str] = []           # KH thanh tra theo năm/quý
    khac: List[str] = []                          # văn bản chỉ đạo khác


class PhanNoiDung(BaseModel):
    """Bước 4.2 — nội dung thanh tra."""
    pham_vi: str = ""
    thoi_ky: ThoiKy = Field(default_factory=ThoiKy)
    doi_tuong: List[str] = []                    # các đơn vị thực sự bị thanh tra
    noi_dung: str = ""                            # mô tả nội dung thanh tra


class ViPhamChiTiet(BaseModel):
    """Bước 4.3 — 1 vi phạm với 9 thuộc tính theo yêu cầu nghiệp vụ."""
    stt: int = 0
    nhom: str = ""                                # nhóm văn bản tự phân chia
    linh_vuc: List[LinhVuc] = []                 # 5.2 nhóm vi phạm

    # 5.3 hành vi — raw + chuẩn
    hanh_vi_chi_tiet: str = ""                   # nguyên văn pháp lý từ văn bản
    hanh_vi_chuan: HanhVi = HanhVi.KHAC          # map sang vocab (xem taxonomy)

    chu_the: str = ""                             # 5.3 chủ thể vi phạm
    can_cu_phap_ly: List[str] = []               # 4.3(2) điều, khoản bị vi phạm
    so_lieu: SoLieuViPham = Field(default_factory=SoLieuViPham)  # 5.4
    muc_do: MucDoViPham = MucDoViPham.KHONG_RO   # 4.3 mức độ, tính chất
    tinh_chat: str = ""                           # mô tả tính chất ngắn
    hau_qua: str = ""                             # 4.3(3) hậu quả, thiệt hại
    trach_nhiem: TrachNhiem = Field(default_factory=TrachNhiem)  # 4.3(4) + 5.5
    nguyen_nhan_khach_quan: str = ""             # 4.3(5)
    nguyen_nhan_chu_quan: str = ""               # 4.3(5)
    co_dau_hieu_nghiem_trong: bool = False        # dấu hiệu nghiêm trọng
    co_dau_hieu_hinh_su: bool = False             # dấu hiệu tội phạm


class KienNghiChiTiet(BaseModel):
    """Bước 4.4 — 1 kiến nghị với 7 thuộc tính + loại."""
    stt: int = 0
    loai: LoaiKienNghi = LoaiKienNghi.KINH_TE     # 8 loại theo Luật Thanh tra
    noi_dung: str = ""                            # nội dung kiến nghị
    can_cu_phap_ly: List[str] = []                # căn cứ pháp lý
    co_quan_thuc_hien: List[str] = []             # cơ quan/tổ chức/cá nhân
    thoi_han: Optional[date] = None               # thời hạn (ISO)
    thoi_han_mo_ta: str = ""                      # raw khi không parse được

    # Giá trị xử lý — đa đơn vị (tiền / đất / TS khác)
    gia_tri_vnd: Optional[float] = None
    dien_tich_dat_m2: Optional[float] = None
    tai_san_khac: str = ""

    tinh_trang: TinhTrangKienNghi = TinhTrangKienNghi.KHONG_RO
    tai_lieu_chung_minh: List[str] = []           # tên báo cáo / văn bản


class PhanToChucThucHien(BaseModel):
    """Bước 4.5 — tổ chức thực hiện."""
    thoi_han_chung: Optional[date] = None
    don_vi_thuc_hien: List[str] = []
    trach_nhiem_bao_cao: str = ""
    ghi_chu: str = ""


# ── top-level aggregate models ─────────────────────────────────────────────


class Tien(BaseModel):
    """Tổng hợp tiền top-level — dùng cho aggregate. Convert mọi đơn vị → VND."""
    kien_nghi_thu_hoi: Optional[float] = None
    da_thu_hoi: Optional[float] = None
    kien_nghi_xu_ly_khac: Optional[float] = None   # giảm trừ, hoàn trả, xuất toán
    tong_sai_pham: Optional[float] = None
    don_vi: str = "VND"


class NhanSu(BaseModel):
    """Tổng hợp nhân sự top-level — đếm người."""
    kien_nghi_kiem_diem: Optional[int] = None
    kien_nghi_ky_luat: Optional[int] = None
    kien_nghi_khoi_to: Optional[int] = None


class HinhSu(BaseModel):
    """Tổng hợp dấu hiệu hình sự top-level."""
    co_dau_hieu: bool = False
    dieu_blhs: List[str] = []                      # ["219", "353"] — chỉ số
    loai_sai_pham: List[str] = []                  # tự do, vd "tron_thue"
    da_chuyen_cqdt: bool = False
    ngay_chuyen_cqdt: Optional[date] = None
    co_quan_nhan: Optional[str] = None


# ── top-level record ───────────────────────────────────────────────────────


class TTCPRecord(BaseModel):
    """Bản canonical 1 kết luận thanh tra. Cấu trúc đầy đủ 5 phần KLTT
    + top-level aggregate fields cho Q&A."""

    # ── nhận dạng văn bản ──
    so_ket_luan: Optional[str] = None
    loai_van_ban: LoaiVanBan = LoaiVanBan.KHAC
    ngay_ban_hanh: Optional[date] = None
    nam: Optional[int] = None                      # derived từ ngay_ban_hanh.year
    co_quan_ban_hanh: Optional[str] = None
    nguoi_ky: Optional[str] = None
    chuc_vu_nguoi_ky: Optional[str] = None

    # ── đối tượng (top-level, cho aggregate) ──
    doi_tuong_thanh_tra: Optional[str] = None      # tóm tắt 1 dòng
    don_vi_bi_thanh_tra: List[str] = []
    dia_phuong: List[str] = []                     # canonical 63 tỉnh/TP

    # ── 5 phần KLTT ──
    phan_can_cu: PhanCanCu = Field(default_factory=PhanCanCu)              # 4.1
    phan_noi_dung: PhanNoiDung = Field(default_factory=PhanNoiDung)        # 4.2
    vi_pham: List[ViPhamChiTiet] = []                                       # 4.3
    kien_nghi: List[KienNghiChiTiet] = []                                   # 4.4
    phan_to_chuc_thuc_hien: PhanToChucThucHien = Field(
        default_factory=PhanToChucThucHien                                  # 4.5
    )

    # ── tóm tắt cho lãnh đạo đọc nhanh ──
    noi_dung_chinh: str = ""                       # 2-3 câu
    sai_pham_chinh: List[str] = []                 # bullet 3-7 ý

    # ── top-level aggregate (derive được từ vi_pham/kien_nghi nhưng nhân đôi
    #     để Mongo index, query nhanh, không phải scan nested) ──
    linh_vuc: List[LinhVuc] = []                   # union of vi_pham[].linh_vuc
    linh_vuc_chi_tiet: List[str] = []              # supplementary free-text
    tien: Tien = Field(default_factory=Tien)
    nhan_su: NhanSu = Field(default_factory=NhanSu)
    hinh_su: HinhSu = Field(default_factory=HinhSu)
    trang_thai_thuc_hien: TrangThaiThucHien = TrangThaiThucHien.KHONG_RO

    # ── catch-all ──
    van_ban_lien_quan: List[str] = []
    ghi_chu: str = ""

    @field_validator("nam", mode="before")
    @classmethod
    def _derive_nam(cls, v, info):
        if v not in (None, "", 0):
            try:
                return int(v)
            except (TypeError, ValueError):
                return None
        d = info.data.get("ngay_ban_hanh")
        if isinstance(d, date):
            return d.year
        return None


# Schema JSON template — generate từ model, dùng làm reference trong prompt.
SCHEMA_JSON_TEMPLATE = TTCPRecord().model_dump_json(indent=2)
