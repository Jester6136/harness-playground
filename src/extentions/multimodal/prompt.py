system_prompt = """Extract information from this Vietnamese image documents into a strict JSON format.

IMPORTANT:
- Return JSON ONLY. No explanation, no markdown.
- Output MUST match the structure EXACTLY.
- Do NOT add any extra fields.
- Do NOT remove any fields.
- If information is missing → use "" for string, [] for arrays.
- Do NOT hallucinate.
- Keep Vietnamese text as is.

Hướng dẫn chi tiết cho các trường quan trọng cần trích xuất:
Giấy chứng nhận:
  - 'Số phát hành': Kiểu dữ liệu-str. Là chuỗi kí tự ngay sau tiêu ngữ hoặc cơ quan tổ chức và địa chỉ (khoảng 15 số). Hoặc loại 2 là gồm 2 chữ cái in hoa theo sau là 6 chữ số. Hoặc là SỐ nối liền với số phát hành (ví dụ: SỐCM 812388 thì số phát hành là CM 812388).
  - 'Số vào sổ': Kiểu dữ liệu - str. 
  - 'Ngày cấp': Điền vào định dạng dd/mm/yyyy, mô tả vị trí xuất hiện: trước đó là tên 1 tỉnh (ví dụ: Hưng Yên, Hải Phòng,...) và ngay sau là tên 1 cơ quan tổ chức.
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
Thông tin nhà ở (tài sản gắn liền với đất):
  - Loại tài sản gắn liền với đất: Là loại tài sản gắn liền với đất, gồm: Nhà ở riêng lẻ, Căn hộ chung cư,...
  - Khu nhà chung cư, nhà hỗn hợp: Là tên khu nhà chung cư, hỗn hợp.
  - Địa chỉ: Là địa chỉ của nhà ở.
  - Nhà chung cư: Là tên nhà chung cư.
  - Số căn hộ: Là số căn hộ chung cư.
  - Diện tích xây dựng: Kiểu dữ liệu - float, Là diện tích xây dựng của tài sản.
  - Diện tích sàn: Kiểu dữ liệu - float, Là diện tích sàn của tài sản.
  - Hình thức sở hữu: Là hình thức sở hữu của chủ sở hữu đối với tài sản gắn liền với đất. 
  - Thời hạn sở hữu: Là thời gian sở hữu của chủ sở hữu đối với tài sản. 
  - Cấp hạng: Là cấp hạng của tài sản gắn liền với đất. 

Normalize output:
- Remove units (m²), keep float numbers
- Convert comma to dot in numbers

Return EXACTLY this JSON structure:

{
  "Đăng ký": {
    "Giấy chứng nhận": {
      "Số phát hành giấy chứng nhận": "",
      "Mã vạch": "",
      "Số vào sổ": "",
      "Ngày cấp GCN": ""
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
}"""

pdf_detect_prompt = """Extract information from this Vietnamese image documents into a strict JSON format."""