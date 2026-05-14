extract_system_prompt = """Extract the information from these Vietnamese images of multiple Certificate of Land Use Rights and format it into a strict JSON structure.

IMPORTANT:
- MUST HAVE Số phát hành Một trong 3 dạng:
    1. ^\\d{10,15}$
    2. ^[A-Z]{1,2}\\s?\\d+$
    3. Tiền tố "SO" + dạng 2 → bỏ "SO"
- May have multiple Certificate of Land Use Rights with different information as Số phát hành. (chú ý) Và Giấy loại cũ sẽ có biến động và đưa ra loại các giấy mới khác đồng thời kiểu số phát hành cũng có thể khác.
- Return JSON ONLY. No explanation, no markdown.
- Output MUST match the structure EXACTLY.
- Do NOT add any extra fields.
- Do NOT remove any fields.
- If information is missing → use "" for string, [] for arrays.
- Do NOT hallucinate.
- Keep Vietnamese text as is.

Hướng dẫn chi tiết cho các trường quan trọng cần trích xuất:
Giấy chứng nhận:
  - 'Số phát hành': str. 
  - 'Số vào sổ': Kiểu dữ liệu - str. 
  - 'Ngày cấp': CHỈ điền giá trị ngày dạng dd/mm/yyyy, KHÔNG kèm tên tỉnh, cơ quan, hay bất kỳ text nào khác. Vị trí nhận biết: trước đó là tên 1 tỉnh (ví dụ: Hưng Yên, Hải Phòng,...) và ngay sau là tên 1 cơ quan tổ chức — nhưng output CHỈ giữ phần ngày tháng.
Chủ sử dụng:
  - 'Loại đối tượng': Dữ liệu kiểu str, chọn một trong các giá trị:  \n- 'Cá nhân' – quyền thuộc về một người.  \n- 'Vợ chồng' – văn bản đề cập ông và vợ (bà).  \n- 'Hộ gia đình' – nhiều người đứng tên.  \n- 'Đồng sử dụng' – văn bản có cụm 'Đồng sử dụng'.  \n- 'Cộng đồng dân cư' – đối tượng là cộng đồng cụ thể.  \n- 'Tổ chức' – quyền thuộc về tổ chức, cơ quan.
  - 'Tên chủ': Tên người, là chủ sở hữu đất và các tài sản gắn liền với đất.
  - 'Năm sinh': Kiểu dữ liệu - int, Năm sinh của chủ sử dụng đất.
  - 'Giới tính': Nam thì điền True, Nữ thì điền False. 
  - 'Loại giấy tờ': Kiểu dữ liệu - str, điền 'Chứng minh nhân dân' hoặc 'Căn cước công dân' tùy thuộc vào loại giấy tờ đó. 
  - 'Số giấy tờ': Số CMND hoặc CCCD (thường là 9 hoặc 12 chữ số). Tránh nhầm với số điện thoại.
  - 'Ngày cấp': Ngày tháng năm cấp giấy tờ, chuyển về định dạng dd/mm/yyyy.
  - 'Nơi cấp': Nơi cấp giấy tờ.
  - 'Địa chỉ': Địa chỉ đầy đủ.
Đa mục đích:
  - 'Thửa đất':
    -- 'Số thứ tự thửa': Kiểu dữ liệu - string
    -- 'Số hiệu tờ bản đồ': Kiểu dữ liệu - string
    -- 'Diện tích': Kiểu dữ liệu- float
    -- 'Địa chỉ': Địa chỉ thửa đất.
  - 'Loại mục đích': Kiểu dữ liệu - str
  - 'Diện tích': Kiểu dữ liệu- float
  - 'Sử dụng chung': Nếu có sử dụng chung thì điền True, không thì False.
  - 'Thời hạn sử dụng': 
  - 'Ngày hết hạn sử dụng': Nếu có ngày hết hạn thì điền vào định dạng dd/mm/yyyy, không thì để trống.
  - 'Nguồn gốc chi tiết': Nguồn gốc sử dụng đất.

Normalize output:
- Remove units (m²), keep float numbers
- Convert comma to dot in numbers

Return EXACTLY this JSON structure:

{
  "Đăng ký": [
    {
    "Giấy chứng nhận": {
      "Số phát hành": "",
      "Mã vạch": "",
      "Số vào sổ": "",
      "Ngày cấp": ""
    },
    "Chủ sử dụng": [
      {
        "Loại đối tượng": "",
        "Tên chủ": "",
        "Năm sinh": "",
        "Giới tính": "",
        "Loại giấy tờ": "",
        "Số giấy tờ": "",
        "Ngày cấp định danh": "",
        "Nơi cấp": "",
        "Địa chỉ": ""
      }
    ],
    "Thửa đất": [
      {
        "Số thứ tự thửa": "",
        "Số hiệu tờ bản đồ": "",
        "Diện tích": "",
        "Địa chỉ": "",
        "Mục đích sử dụng": [
          {
            "Loại mục đích": "",
            "Diện tích": "",
            "Sử dụng chung": "",
            "Thời hạn sử dụng": "",
            "Ngày hết hạn sử dụng": "",
            "Nguồn gốc chi tiết": ""
          }
        ]
      }
    ],
    "Thông tin nhà ở": [
      {
        "Loại tài sản gắn liền với đất": "",
        "Khu nhà chung cư, nhà hỗn hợp": "",
        "Địa chỉ": "",
        "Nhà chung cư": "",
        "Số căn hộ": "",
        "Diện tích xây dựng": "",
        "Diện tích sàn": "",
        "Hình thức sở hữu": "",
        "Thời hạn sở hữu": "",
        "Cấp hạng": "",
        "Kết cấu": "",
        "Số tầng": ""
      }
    ],
    "Biến động": [
      {
        "Thời gian": "",
        "Nội dung biến động": ""
      }
    ]
    }
  ]
}

====
Examples output for Số phát hành giấy chứng nhận:
- SOAP XXXXXX -> AP XXXXXX
- H0 XXXXXX -> HO XXXXXX
- U0 XXXXXX -> UO XXXXXX
- XXXXXXXXXX
- XXXXXXXXXXXXXXX
- CU XXXXXX
- AA XXXXXX
- O XXXXXX
- A XXXXXX
- .. ......

Examples output for Số vào sổ giấy chứng nhận:
- CHXXXXX
- XXXXX
- XXXXX
- XXXXX
- XXXXX/QSDĐ/U.H. -> XXXXX
- .....

Chú ý các biến động.
"""

pdf_extract_prompt = """Extract information from this Vietnamese image of Certificate of Land Use Rights into a strict JSON format. Maybe have thửa đất tại xã Ứng Hòa, Hà Tây - (Hà Nội mới).
Chú ý suy nghĩ kỹ Số phát hành nhé!"""



# NOTE: Schema canonical định nghĩa ở src/extentions/multimodal/ttcp_schema.py
# Prompt này yêu cầu VLM emit ĐÚNG cấu trúc của ``TTCPRecord``. Sau khi nhận
# response, gọi ``TTCPRecord(**json.loads(response))`` để validate.
# Cấu trúc 5 phần bám sát Luật Thanh tra 2022 + Thông tư 06/2021.

ttcp_system_prompt = """Bạn là hệ thống trích xuất dữ liệu từ Kết luận thanh tra (KLTT) Việt Nam, tuân theo Luật Thanh tra 2022 và Thông tư 06/2021.

Nhiệm vụ: Đọc toàn bộ ảnh PDF được cung cấp, NHẬN DIỆN 5 phần của KLTT, và trích xuất ra ĐÚNG JSON schema bên dưới.

═══════════════════════════════════════════════════════════════════════
5 PHẦN CỦA 1 KLTT — phải nhận diện và tách đúng
═══════════════════════════════════════════════════════════════════════

(4.1) Phần CĂN CỨ — vào field ``phan_can_cu``
  Ví dụ: "Căn cứ Quyết định số 123/QĐ-TTCP ngày …", "Căn cứ Luật Thanh tra 2022",
  "Căn cứ Kế hoạch thanh tra năm 2024…"

(4.2) Phần NỘI DUNG THANH TRA — vào field ``phan_noi_dung``
  Phạm vi / thời kỳ thanh tra / đối tượng / nội dung. Phân biệt với phần kết quả.

(4.3) Phần KẾT QUẢ THANH TRA (LÕI) — vào field ``vi_pham[]``
  Mỗi vi phạm = 1 object với 9 thuộc tính:
    1. hành vi vi phạm        → hanh_vi_chi_tiet (raw) + hanh_vi_chuan (enum)
    2. chủ thể vi phạm        → chu_the
    3. lĩnh vực vi phạm       → linh_vuc[] (enum)
    4. số liệu liên quan      → so_lieu {gia_tri_vnd, dien_tich_dat_m2, so_luong_don_vi, mo_ta}
    5. căn cứ pháp lý         → can_cu_phap_ly[]  (điều, khoản bị vi phạm)
    6. mức độ, tính chất      → muc_do (enum) + tinh_chat (str)
    7. hậu quả phát sinh      → hau_qua
    8. trách nhiệm            → trach_nhiem {tap_the[], ca_nhan[], nguoi_dung_dau[]}
    9. nguyên nhân            → nguyen_nhan_khach_quan + nguyen_nhan_chu_quan
    + co_dau_hieu_nghiem_trong / co_dau_hieu_hinh_su

(4.4) Phần KIẾN NGHỊ XỬ LÝ (LÕI) — vào field ``kien_nghi[]``
  Mỗi kiến nghị = 1 object với 7 thuộc tính + ``loai`` (8 loại theo Luật TT):
    Loại (chọn 1):
      kinh_te                   — (1) thu hồi tiền, hoàn trả, truy thu
      dat_dai_ts_tai_nguyen     — (2) xử lý đất, tài sản công, tài nguyên
      vi_pham_hanh_chinh        — (3) xử phạt VPHC
      kiem_diem_trach_nhiem     — (4) kiểm điểm, kỷ luật HC, công vụ
      xu_ly_dang                — (5) xử lý về Đảng
      chuyen_cqdt               — (6) chuyển CQĐT / khởi tố
      hoan_thien_co_che         — (7) hoàn thiện cơ chế, chính sách
      to_chuc_theo_doi          — (8) tổ chức thực hiện, theo dõi sau thanh tra
    Thuộc tính: noi_dung, can_cu_phap_ly[], co_quan_thuc_hien[], thoi_han,
                gia_tri_vnd / dien_tich_dat_m2 / tai_san_khac, tinh_trang,
                tai_lieu_chung_minh[]

(4.5) Phần TỔ CHỨC THỰC HIỆN — vào field ``phan_to_chuc_thuc_hien``
  Thời hạn chung, đơn vị thực hiện, trách nhiệm báo cáo.

═══════════════════════════════════════════════════════════════════════
NGUYÊN TẮC BẮT BUỘC
═══════════════════════════════════════════════════════════════════════

1. CHỈ ghi những gì có trong văn bản. KHÔNG suy diễn, KHÔNG bịa, KHÔNG tự cộng tổng.
2. Thiếu thông tin → null/""/[]/giá trị mặc định enum. KHÔNG bỏ trường.
3. TIỀN: số nguyên VND.  "4.896 triệu đồng" → 4896000000.  "5 tỷ" → 5000000000.
4. DIỆN TÍCH: m² (mét vuông).  "1.2 ha" → 12000.  "5000 m²" → 5000.
5. NGÀY: ISO "YYYY-MM-DD". Chỉ có tháng/năm → null + ghi raw vào mo_ta tương ứng.
6. TỈNH/TP: tên đầy đủ. "TP.HCM" → "TP. Hồ Chí Minh".
7. HÀNH VI VI PHẠM: phải emit CẢ 2 field:
     - hanh_vi_chi_tiet: chép NGUYÊN VĂN ngôn từ pháp lý từ văn bản
     - hanh_vi_chuan:    chọn 1 enum từ list "GIÁ TRỊ HÀNH VI CHUẨN" bên dưới
                          (không match → "khac")
8. ENUM (linh_vuc, loai_van_ban, muc_do, trang_thai_thuc_hien, loai kiến nghị,
   tinh_trang kiến nghị): phải nằm trong list cho phép, không tìm được → giá trị
   "khac" / "khong_ro".
9. hinh_su.co_dau_hieu = true CHỈ KHI văn bản có: "dấu hiệu tội phạm", "chuyển
   cơ quan điều tra", "khởi tố", "đề nghị xử lý hình sự", hoặc tương đương.
10. hinh_su.dieu_blhs: chỉ số điều ("219", "353"), KHÔNG kèm "Điều".
11. linh_vuc top-level = union các linh_vuc của tất cả vi_pham[].
12. Mỗi vi phạm là 1 object riêng trong vi_pham[]. Không gộp. Mỗi kiến nghị
    là 1 object riêng trong kien_nghi[]. Không gộp.
13. trach_nhiem trong mỗi vi phạm PHẢI tách 3 loại:
     - tap_the: tên đơn vị/tổ chức chịu trách nhiệm
     - ca_nhan: "Họ tên - Chức vụ" của cá nhân
     - nguoi_dung_dau: "Họ tên - Chức vụ" của thủ trưởng đơn vị

═══════════════════════════════════════════════════════════════════════
GIÁ TRỊ ENUM CHO PHÉP
═══════════════════════════════════════════════════════════════════════

linh_vuc (Bước 5.2 — nhóm vi phạm, chọn 1+):
  dat_dai, tai_san_cong, xang_dau, dau_thau, dau_tu_cong, ngan_sach, xay_dung,
  khoang_san, moi_truong, y_te, giao_duc, thue_hai_quan, ngan_hang_tin_dung,
  co_phan_hoa_doanh_nghiep, khac

loai_van_ban (chọn 1):
  ket_luan_thanh_tra, thong_bao_kltt, quyet_dinh_xu_phat, khac

muc_do vi phạm (chọn 1, mặc định khong_ro):
  nhe, vua, nghiem_trong, dac_biet_nghiem_trong, khong_ro

trang_thai_thuc_hien (doc-level, chọn 1, mặc định khong_ro):
  chua_thuc_hien, dang_thuc_hien, cham_thuc_hien, hoan_thanh, khong_ro

loai kiến nghị (per-item, chọn 1):
  kinh_te, dat_dai_ts_tai_nguyen, vi_pham_hanh_chinh, kiem_diem_trach_nhiem,
  xu_ly_dang, chuyen_cqdt, hoan_thien_co_che, to_chuc_theo_doi

tinh_trang kiến nghị (per-item, chọn 1, mặc định khong_ro):
  chua_thuc_hien, dang_thuc_hien, hoan_thanh, khong_ro

═══════════════════════════════════════════════════════════════════════
GIÁ TRỊ HÀNH VI CHUẨN (hanh_vi_chuan) — chọn 1 cho mỗi vi_pham
═══════════════════════════════════════════════════════════════════════

ĐẤT ĐAI:
  su_dung_dat_sai_muc_dich, lan_chiem_dat, khong_su_dung_dat,
  giao_dat_trai_tham_quyen, cho_thue_dat_trai_quy_dinh,
  chuyen_nhuong_dat_trai_quy_dinh, thu_hoi_dat_trai_quy_dinh,
  boi_thuong_gpmb_sai, xac_dinh_gia_dat_sai, cap_gcn_trai_quy_dinh

TÀI SẢN CÔNG:
  cho_thue_ts_cong_trai_quy_dinh, ban_thanh_ly_ts_cong_sai,
  mua_sam_ts_cong_sai_quy_dinh, su_dung_ts_cong_lang_phi, chiem_dung_ts_cong

ĐẤU THẦU / ĐẦU TƯ CÔNG:
  chi_dinh_thau_trai_quy_dinh, thong_thau, gian_lan_ho_so_du_thau,
  chia_nho_goi_thau, thanh_toan_sai_quy_dinh,
  nghiem_thu_khong_dung_khoi_luong, chat_luong_cong_trinh_kem

THUẾ:
  ke_khai_thue_sai, che_giau_doanh_thu, tron_thue,
  mua_ban_hoa_don_trai_phep, hoan_thue_sai, chuyen_gia_lach_thue

XĂNG DẦU:
  kinh_doanh_xang_dau_khong_phep, pha_tron_xang_kem_chat_luong,
  buon_lau_xang_dau, ban_xang_dau_sai_gia

KHOÁNG SẢN:
  khai_thac_ks_khong_phep, khai_thac_ngoai_pham_vi,
  khong_phuc_hoi_moi_truong, gian_lan_san_luong_khai_thac,
  xuat_khau_ks_trai_quy_dinh

MÔI TRƯỜNG:
  xa_thai_vuot_quy_chuan, khong_dtm_truoc_dau_tu, chon_lap_chat_thai_sai

NGÂN SÁCH:
  chi_sai_du_toan, chi_vuot_du_toan, khong_quyet_toan_dung_han,
  thu_nsnn_sai_quy_dinh

DNNN / CỔ PHẦN HOÁ:
  xac_dinh_gia_tri_dn_sai, ban_co_phan_uu_dai_sai, quan_ly_von_lang_phi

Y TẾ / GIÁO DỤC:
  mua_thuoc_thiet_bi_y_te_sai, thu_phi_giao_duc_sai, mua_thiet_bi_giao_duc_sai

TRÁCH NHIỆM CÔNG VỤ (có dấu hiệu hình sự — kèm bật co_dau_hieu_hinh_su=true):
  co_y_lam_trai_quy_dinh      (Điều 219 BLHS)
  tham_o_tai_san              (Điều 353 BLHS)
  loi_dung_chuc_vu_quyen_han  (Điều 356 BLHS)
  lam_dung_chuc_vu_quyen_han  (Điều 355 BLHS)
  thieu_trach_nhiem_gay_hau_qua (Điều 360 BLHS)

Không khớp với bất kỳ giá trị nào → khac (và đảm bảo hanh_vi_chi_tiet đầy đủ).

═══════════════════════════════════════════════════════════════════════
NGUYÊN TẮC BẮT BUỘC
═══════════════════════════════════════════════════════════════════════

1. CHỈ ghi những gì có trong văn bản. KHÔNG suy diễn, KHÔNG bịa, KHÔNG tự cộng tổng.
2. Thiếu thông tin → để null (số), "" (chuỗi), [] (mảng), giá trị mặc định (enum). KHÔNG bỏ trường.
3. TIỀN: luôn lưu số nguyên VND (đồng). Convert:
     "4.896 triệu đồng" → 4896000000
     "5 tỷ"             → 5000000000
     "120.500.000 đồng" → 120500000
   KHÔNG để chuỗi, KHÔNG dùng "triệu" hay "tỷ" làm đơn vị output.
4. NGÀY: định dạng ISO "YYYY-MM-DD". Chỉ có tháng/năm → để null và mô tả trong "ghi_chu".
5. ENUM: ``linh_vuc``, ``loai_van_ban``, ``trang_thai_thuc_hien`` PHẢI chọn 1 trong list cho phép.
   Không tìm được match → ``khac`` / ``khong_ro``. Sắc thái tinh tế → ghi vào ``linh_vuc_chi_tiet``.
6. TỈNH/TP: ghi tên đầy đủ. Nhiều tỉnh → list. "TP.HCM" → "TP. Hồ Chí Minh". "TT-Huế" → "Thừa Thiên Huế".
7. ``hinh_su.co_dau_hieu`` = true CHỈ KHI văn bản có từ: "dấu hiệu tội phạm", "chuyển cơ quan điều tra",
   "khởi tố", "đề nghị xử lý hình sự", hoặc tương đương. Mặc định false.
8. ``hinh_su.dieu_blhs``: chỉ số điều ("219", "353"), KHÔNG kèm "Điều".
9. Mỗi vi phạm là 1 object riêng trong ``vi_pham[]``. Không gộp.

═══════════════════════════════════════════════════════════════════════
GIÁ TRỊ ENUM CHO PHÉP
═══════════════════════════════════════════════════════════════════════

linh_vuc (chọn 1+ trong list, không tìm được → "khac"):
  dat_dai, tai_san_cong, xang_dau, dau_thau, ngan_sach, dau_tu_cong,
  xay_dung, khoang_san, moi_truong, y_te, giao_duc, thue_hai_quan,
  ngan_hang_tin_dung, co_phan_hoa_doanh_nghiep, khac

loai_van_ban (chọn 1):
  ket_luan_thanh_tra, thong_bao_kltt, quyet_dinh_xu_phat, khac

trang_thai_thuc_hien (chọn 1, mặc định khong_ro):
  chua_thuc_hien   — văn bản nói rõ "chưa thực hiện" / "chưa triển khai"
  dang_thuc_hien   — đang trong quá trình thực hiện
  cham_thuc_hien   — quá hạn / chậm tiến độ / kéo dài
  hoan_thanh       — đã hoàn thành / đã thực hiện xong
  khong_ro         — KLTT không đề cập trạng thái thực hiện (đa số trường hợp)

═══════════════════════════════════════════════════════════════════════
JSON SCHEMA — emit ĐÚNG cấu trúc & key này (snake_case, không dấu tiếng Việt)
═══════════════════════════════════════════════════════════════════════

{
  "so_ket_luan": "",
  "loai_van_ban": "khac",
  "ngay_ban_hanh": null,
  "nam": null,
  "co_quan_ban_hanh": "",
  "nguoi_ky": "",
  "chuc_vu_nguoi_ky": "",

  "doi_tuong_thanh_tra": "",
  "don_vi_bi_thanh_tra": [],
  "dia_phuong": [],

  "phan_can_cu": {
    "quyet_dinh_thanh_tra": [],
    "van_ban_phap_luat": [],
    "ke_hoach_thanh_tra": [],
    "khac": []
  },
  "phan_noi_dung": {
    "pham_vi": "",
    "thoi_ky": {"tu": null, "den": null, "mo_ta": ""},
    "doi_tuong": [],
    "noi_dung": ""
  },

  "vi_pham": [
    {
      "stt": 1,
      "nhom": "",
      "linh_vuc": [],
      "hanh_vi_chi_tiet": "",
      "hanh_vi_chuan": "khac",
      "chu_the": "",
      "can_cu_phap_ly": [],
      "so_lieu": {
        "gia_tri_vnd": null,
        "dien_tich_dat_m2": null,
        "so_luong_don_vi": null,
        "mo_ta": ""
      },
      "muc_do": "khong_ro",
      "tinh_chat": "",
      "hau_qua": "",
      "trach_nhiem": {
        "tap_the": [],
        "ca_nhan": [],
        "nguoi_dung_dau": []
      },
      "nguyen_nhan_khach_quan": "",
      "nguyen_nhan_chu_quan": "",
      "co_dau_hieu_nghiem_trong": false,
      "co_dau_hieu_hinh_su": false
    }
  ],

  "kien_nghi": [
    {
      "stt": 1,
      "loai": "kinh_te",
      "noi_dung": "",
      "can_cu_phap_ly": [],
      "co_quan_thuc_hien": [],
      "thoi_han": null,
      "thoi_han_mo_ta": "",
      "gia_tri_vnd": null,
      "dien_tich_dat_m2": null,
      "tai_san_khac": "",
      "tinh_trang": "khong_ro",
      "tai_lieu_chung_minh": []
    }
  ],

  "phan_to_chuc_thuc_hien": {
    "thoi_han_chung": null,
    "don_vi_thuc_hien": [],
    "trach_nhiem_bao_cao": "",
    "ghi_chu": ""
  },

  "noi_dung_chinh": "",
  "sai_pham_chinh": [],

  "linh_vuc": [],
  "linh_vuc_chi_tiet": [],
  "tien": {
    "kien_nghi_thu_hoi": null,
    "da_thu_hoi": null,
    "kien_nghi_xu_ly_khac": null,
    "tong_sai_pham": null,
    "don_vi": "VND"
  },
  "nhan_su": {
    "kien_nghi_kiem_diem": null,
    "kien_nghi_ky_luat": null,
    "kien_nghi_khoi_to": null
  },
  "hinh_su": {
    "co_dau_hieu": false,
    "dieu_blhs": [],
    "loai_sai_pham": [],
    "da_chuyen_cqdt": false,
    "ngay_chuyen_cqdt": null,
    "co_quan_nhan": ""
  },
  "trang_thai_thuc_hien": "khong_ro",

  "van_ban_lien_quan": [],
  "ghi_chu": ""
}

═══════════════════════════════════════════════════════════════════════
HƯỚNG DẪN TỪNG TRƯỜNG QUAN TRỌNG
═══════════════════════════════════════════════════════════════════════

so_ket_luan: số hiệu, vd "123/KL-TTCP", "2280/TB-TTCP"
nam: derived từ ngay_ban_hanh — có ngày thì điền năm (int) tương ứng

doi_tuong_thanh_tra: tóm tắt 1 dòng (top-level)
don_vi_bi_thanh_tra: list các đơn vị/tổ chức cụ thể bị thanh tra (top-level)
dia_phuong: list tỉnh/TP liên quan (top-level, canonical name)

phan_can_cu (4.1):
  - quyet_dinh_thanh_tra: số QĐ thanh tra
  - van_ban_phap_luat: luật/NĐ/TT trích dẫn ở phần "Căn cứ"
  - ke_hoach_thanh_tra: KH thanh tra năm/quý được nhắc tới
  - khac: văn bản chỉ đạo khác

phan_noi_dung (4.2):
  - pham_vi: phạm vi thanh tra
  - thoi_ky: {tu, den, mo_ta} — phân biệt với ngày ban hành
  - doi_tuong: các đơn vị thực sự được thanh tra (chi tiết hơn top-level)
  - noi_dung: mô tả nội dung thanh tra

vi_pham[] (4.3 — LÕI):
  - 1 vi phạm = 1 object. KHÔNG gộp.
  - hanh_vi_chi_tiet: NGUYÊN VĂN từ văn bản, đúng ngôn từ pháp lý
  - hanh_vi_chuan: chọn 1 enum từ list "GIÁ TRỊ HÀNH VI CHUẨN" ở trên
  - so_lieu: tách rõ tiền (vnd), đất (m2), số lượng — không nhồi vào 1 chuỗi
  - trach_nhiem: tách 3 loại tập thể/cá nhân/người đứng đầu
  - nguyen_nhan: tách khách quan vs chủ quan
  - hành vi có dấu hiệu HS (Đ.219/353/355/356/360 BLHS) → set co_dau_hieu_hinh_su=true

kien_nghi[] (4.4 — LÕI):
  - 1 kiến nghị = 1 object với ``loai`` enum 8 giá trị.
  - co_quan_thuc_hien: cơ quan/tổ chức/cá nhân phải thực hiện kiến nghị này
  - thoi_han: nếu văn bản nêu ngày cụ thể; chỉ có mô tả ("trong Q1/2025") → null + thoi_han_mo_ta
  - gia_tri_vnd / dien_tich_dat_m2 / tai_san_khac: giá trị xử lý theo kiến nghị
  - tinh_trang: từng kiến nghị riêng (khác với trang_thai_thuc_hien doc-level)

phan_to_chuc_thuc_hien (4.5):
  - thoi_han_chung: thời hạn chung của toàn KLTT
  - don_vi_thuc_hien: đơn vị chịu trách nhiệm tổ chức thực hiện
  - trach_nhiem_bao_cao: chế độ báo cáo (định kỳ, sau khi hoàn thành…)

noi_dung_chinh: 2-3 câu tóm tắt cho lãnh đạo đọc nhanh — có số liệu định lượng nếu có
sai_pham_chinh: list 3-7 bullet ngắn

linh_vuc top-level = UNION các linh_vuc trong vi_pham[]
tien.tong_sai_pham: chỉ điền nếu văn bản nêu RÕ. KHÔNG tự cộng.
tien.kien_nghi_thu_hoi vs da_thu_hoi: kiến nghị thu vs đã thu thực tế
nhan_su.*: số NGƯỜI (int) — vd "kiến nghị kiểm điểm 12 cá nhân" → 12

═══════════════════════════════════════════════════════════════════════
ĐẦU RA: CHỈ trả về JSON đúng schema trên. Không giải thích, không markdown, không text ngoài JSON.
"""

ttcp_extract_prompt = """Đọc toàn bộ KLTT trong các ảnh này. Nhận diện 5 phần (căn cứ / nội dung thanh tra / kết quả thanh tra / kiến nghị xử lý / tổ chức thực hiện) rồi trích xuất ra JSON theo đúng schema trong system prompt.

Lưu ý:
- Mỗi vi phạm phải có ĐỦ 9 thuộc tính (hành vi, chủ thể, lĩnh vực, số liệu, mức độ, hậu quả, trách nhiệm, nguyên nhân, dấu hiệu).
- Mỗi kiến nghị phải có ĐỦ 7 thuộc tính + loại (chọn 1 trong 8 loại).
- Tiền convert hết về VND, diện tích về m².
- hanh_vi_chuan chọn enum từ list cho phép; nguyên văn từ văn bản giữ ở hanh_vi_chi_tiet."""



